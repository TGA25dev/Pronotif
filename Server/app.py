from flask import Flask, request, jsonify
import mysql.connector
from mysql.connector import pooling
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import logging
from datetime import datetime, timedelta
import redis
from dotenv import load_dotenv
import os
import secrets
import threading
import time

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Setup logging
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

file_handler = logging.FileHandler('app.log')
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# MySQL Connection Pool
connection_pool = pooling.MySQLConnectionPool(
    pool_name=os.getenv('DB_POOL_NAME'),
    pool_size=int(os.getenv('DB_POOL_SIZE')),
    pool_reset_session=os.getenv('DB_POOL_RESET_SESSION'),
    host=os.getenv('DB_HOST'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    database=os.getenv('DB_NAME')
)

authcode = os.getenv('AUTHCODE')
auth_table_name = os.getenv('DB_AUTH_TABLE_NAME')

# Flask-Limiter and Redis Configuration
redis_connection = redis.Redis(
    host=os.getenv('REDIS_HOST'),
    port=int(os.getenv('REDIS_PORT')),
    db=int(os.getenv('REDIS_DB'))
)

limiter = Limiter(
    get_remote_address,
    app=app,
    storage_uri=f"redis://{os.getenv('REDIS_HOST')}:{int(os.getenv('LIMITER_PORT'))}"
)


@app.errorhandler(500)
def internal_error(error):
    logger.critical(f"Internal Server Error: {error}")
    return jsonify({'error': 'An internal error occurred'}), 500


@app.errorhandler(429)
def ratelimit_error(error):
    logger.warning(f"Rate limit exceeded: {error}")
    return jsonify({'error': 'Rate limit exceeded'}), 429


@app.errorhandler(404)
def page_not_found(error):
    logger.warning(f"Page not found: {error}")
    return jsonify({'error': 'Page not found'}), 404

# API Endpoints

@app.route('/ping', methods=['GET'])
@limiter.limit("10 per minute")
def test_endpoint():
    client_ip = request.remote_addr
    logger.info(f"{client_ip} Pong !")
    return jsonify({"message": "Pong !"}), 200

# Use Redis to store the state instead of a dictionary
def get_state():
    state = redis_connection.get('visibility_state')
    return bool(state and state.decode('utf-8') == 'True')

def set_state(enabled):
    redis_connection.set('visibility_state', str(enabled))

@app.route('/emc', methods=['GET'])
def toggle_visibility():
    if 'enable' in request.args:
        set_state(True)
        logger.info("Visibility state enabled")
        return jsonify({"status": "enabled"}), 200
    
    elif 'disable' in request.args:
        set_state(False)
        logger.info("Visibility state disabled")
        return jsonify({"status": "disabled"}), 200
    else:
        return jsonify({"error": "Invalid action"}), 400

@app.route('/state', methods=['GET'])
def get_visibility_state():
    return jsonify({"enabled": get_state()}), 200

#Setup Endpoints

@app.route("/v1/setup/session", methods=["POST", "HEAD"])
@limiter.limit(str(os.getenv('SESSION_SETUP_LIMIT')) + " per minute")
def generate_session():
    if request.method == "HEAD":
        return jsonify({"message": ""}), 200
    try:
        # Generate session ID and a temporary token
        session_id = secrets.token_urlsafe(16)
        token = secrets.token_urlsafe(32)
        
        current_time = datetime.now()
        expiry_minutes = int(os.getenv('SESSION_EXPIRY_M'))
        expiry_seconds = int(os.getenv('SESSION_EXPIRY_S'))

        data = {
            "session_id": session_id,
            "token": token,
            "created_at": current_time,
            "expires_at": current_time + timedelta(minutes=expiry_minutes),
            "used": False,
        }

        # Store the session in Redis
        try:
            redis_connection.setex(
                f"session:{session_id}",
                expiry_seconds,
                token
            )

        except redis.RedisError as e:
            logger.error(f"Redis error: {e}")
            return jsonify({"error": "Session storage failed"}), 500

        # Store in DB
        connection = connection_pool.get_connection()
        cursor = connection.cursor()
        try:
            cursor.execute(
                f"INSERT INTO {auth_table_name} (session_id, token, created_at, expires_at, used) VALUES (%s, %s, %s, %s, %s)",
                (session_id, token, data['created_at'], data['expires_at'], data['used'])
            )
            connection.commit()
            logger.info(f"Session created: {session_id}")

        except mysql.connector.Error as err:
            logger.error(f"MySQL error: {err}")
            return jsonify({"error": "Operation failed"}), 500
        
        finally:
            cursor.close()
            connection.close()

        return jsonify({
            "session_id": session_id,
            "token": token,
            "message": "Session generated successfully!",
            "status": 200
        })

    except Exception as e:
        logger.error(f"Unexpected error in generate_session: {e}")
        return jsonify({"error": "Internal server error"}), 500

# Background tasks
def cleanup_auth_sessions():
    while True:
        try:
            connection = connection_pool.get_connection()
            cursor = connection.cursor()
            current_time = datetime.now()

            # Delete only expired and inactive sessions
            delete_query = f"""
                DELETE FROM {auth_table_name} 
                WHERE expires_at <= %s 
                AND used = FALSE
            """
            
            cursor.execute(delete_query, (current_time,))
            deleted_count = cursor.rowcount
            
            if deleted_count > 0:
                connection.commit()
                logger.info(f"Cleaned up {deleted_count} expired and inactive sessions")
            
        except mysql.connector.Error as err:
            logger.error(f"MySQL error in cleanup task: {err}")

        except Exception as e:
            logger.error(f"Unexpected error in cleanup task: {e}")

        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'connection' in locals():
                connection.close()
            time.sleep(600)

def start_background_tasks():
    session_cleanup_thread = threading.Thread(target=cleanup_auth_sessions, daemon=True)
    session_cleanup_thread.start()

#App Endpoints

if __name__ == '__main__':
    start_background_tasks()
    app.run(host=os.getenv('HOST'), port=os.getenv('MAIN_PORT'))
