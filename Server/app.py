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
from jsonschema import validate
from jsonschema.exceptions import ValidationError
import bleach
import json
from flask_cors import CORS
from flask_talisman import Talisman

load_dotenv()

app = Flask(__name__)
# Parse CORS settings
cors_origins = os.getenv('CORS_ORIGINS').split(', ')
cors_methods = os.getenv('CORS_METHODS').split(', ')
cors_headers = os.getenv('CORS_HEADERS').split(', ')
cors_credentials = os.getenv('CORS_CREDENTIALS').lower() == 'true'

CORS(app, 
     resources={r"/*": {
         "origins": cors_origins,
         "methods": cors_methods,
         "allow_headers": cors_headers,
         "supports_credentials": cors_credentials
     }}
)

Talisman(app,
    force_https=True,
    strict_transport_security=True,
    session_cookie_secure=True,
    session_cookie_http_only=True
)

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
student_table_name = os.getenv('DB_STUDENT_TABLE_NAME')

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

initialized = False

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

def validate_lunch_times(lunch_times):
    expected_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    time_format = '%H:%M'
    
    if not isinstance(lunch_times, dict):
        return False
    
    if set(lunch_times.keys()) != set(expected_days):
        return False
        
    try:
        for time_str in lunch_times.values():
            datetime.strptime(time_str, time_format)
        return True
    except ValueError:
        return False

@app.route("/v1/app/qrscan", methods=["POST", "HEAD"])
@limiter.limit(str(os.getenv('SESSION_SETUP_LIMIT')) + " per minute")
def process_qr_code():
    
    if request.method == "HEAD":
        return jsonify({"message": ""}), 200
        
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 400

    try:
        request.timeout = 30
        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing request data"}), 400

        # Define required fields
        required_fields = [
            "session_id", "token", "login_page_link", "student_username", "student_password",
            "student_fullname", "student_firstname", "student_class",
            "ent_used", "qr_code_login", "uuid", "topic_name", "timezone",
            "notification_delay", "evening_menu",
            "unfinished_homework_reminder", "get_bag_ready_reminder"
        ]
        
        # Validate all string fields
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing {field}"}), 400
            if not isinstance(data[field], str):
                return jsonify({"error": f"Invalid {field} type, expected string"}), 400

        # Validate lunch_times
        if 'lunch_times' not in data:
            return jsonify({"error": "Missing lunch_times"}), 400
        
        if not validate_lunch_times(data['lunch_times']):
            return jsonify({"error": "Invalid lunch_times format"}), 400

        # Rate limit per session
        rate_key = f"qrscan_rate:{data['session_id']}"
        if redis_connection.exists(rate_key):
            return jsonify({"error": "Too many attempts for this session"}), 429
        redis_connection.setex(rate_key, 60, 1)

        # Validate session and token
        stored_token = redis_connection.get(f"session:{data['session_id']}")
        if not stored_token or stored_token.decode('utf-8') != data['token']:
            return jsonify({"error": "Invalid or expired session"}), 401

        # Sanitize all incoming string fields
        sanitized_payload = {}
        for key in required_fields:
            sanitized_payload[key] = bleach.clean(data[key])
        
        # Handle lunch times
        sanitized_payload['monday_lunch'] = bleach.clean(data['lunch_times']['Monday'])
        sanitized_payload['tuesday_lunch'] = bleach.clean(data['lunch_times']['Tuesday'])
        sanitized_payload['wednesday_lunch'] = bleach.clean(data['lunch_times']['Wednesday'])
        sanitized_payload['thursday_lunch'] = bleach.clean(data['lunch_times']['Thursday'])
        sanitized_payload['friday_lunch'] = bleach.clean(data['lunch_times']['Friday'])

        logger.debug(sanitized_payload)

        # Store the data
        connection = connection_pool.get_connection()
        cursor = connection.cursor()
        try:
            insert_query = f"""
                INSERT INTO {student_table_name} (
                    session_id, login_page_link, student_username, student_password,
                    student_fullname, student_firstname, student_class,
                    ent_used, qr_code_login, uuid, topic_name, timezone,
                    notification_delay, evening_menu,
                    unfinished_homework_reminder, get_bag_ready_reminder,
                    monday_lunch, tuesday_lunch, wednesday_lunch, thursday_lunch, friday_lunch
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """
            
            cursor.execute(insert_query, (
                sanitized_payload['session_id'],
                sanitized_payload['login_page_link'],
                sanitized_payload['student_username'],
                sanitized_payload['student_password'],
                sanitized_payload['student_fullname'],
                sanitized_payload['student_firstname'], 
                sanitized_payload['student_class'],
                sanitized_payload['ent_used'],
                sanitized_payload['qr_code_login'],
                sanitized_payload['uuid'],
                sanitized_payload['topic_name'],
                sanitized_payload['timezone'],
                sanitized_payload['notification_delay'],
                sanitized_payload['evening_menu'],
                sanitized_payload['unfinished_homework_reminder'],
                sanitized_payload['get_bag_ready_reminder'],
                sanitized_payload['monday_lunch'],
                sanitized_payload['tuesday_lunch'],
                sanitized_payload['wednesday_lunch'],
                sanitized_payload['thursday_lunch'],
                sanitized_payload['friday_lunch']
            ))
            connection.commit()

            # Mark the session as used
            update_query = f"UPDATE {auth_table_name} SET used = TRUE WHERE session_id = %s"
            cursor.execute(update_query, (sanitized_payload['session_id'],))
            connection.commit()

            logger.info(f"Student data stored for session: {sanitized_payload['session_id']}")

        except mysql.connector.Error as err:
            logger.error(f"MySQL error: {err}")
            return jsonify({"error": "Failed to store student data"}), 500

        finally:
            cursor.close()
            connection.close()

        return jsonify({
            "message": "QR payload processed successfully",
            "status": 200
        })

    except Exception as e:
        logger.error(f"Unexpected error in process_qr_code: {e}")
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

@app.before_request
def initialize():
    global initialized
    if not initialized:
        start_background_tasks()
        initialized = True

if __name__ == '__main__':
    app.run(host=os.getenv('HOST'), port=os.getenv('MAIN_PORT'))
