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
import hashlib

load_dotenv()

def validate_env_vars():
    required_vars = {
        'DB_HOST': str,
        'DB_USER': str,
        'DB_PASSWORD': str,
        'DB_NAME': str,
        'REDIS_HOST': str,
        'REDIS_PORT': int,
        'CORS_ORIGINS': str,
        'SESSION_EXPIRY_M': int,
        'SESSION_EXPIRY_S': int
    }
    
    for var, type_ in required_vars.items():
        value = os.getenv(var)
        if not value:
            raise ValueError(f"Missing required environment variable: {var}")
        try:
            type_(value)
        except ValueError:
            raise ValueError(f"Invalid type for {var}, expected {type_.__name__}")

try:
    validate_env_vars()
except ValueError as e:
    print(f"Environment validation failed: {e}")
    exit(1)

app = Flask(__name__)
# Parse CORS settings
cors_origins = [origin.strip() for origin in os.getenv('CORS_ORIGINS', '').split(',')]
cors_methods = [method.strip() for method in os.getenv('CORS_METHODS', '').split(',')]
cors_headers = [header.strip() for header in os.getenv('CORS_HEADERS', '').split(',')]
cors_credentials = os.getenv('CORS_CREDENTIALS', 'false').lower() == 'true'

CORS(app, 
     resources={r"/*": {
         "origins": cors_origins,
         "methods": cors_methods,
         "headers": cors_headers,
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
    
    logger.debug(f"Validating lunch_times: {lunch_times}")
    
    # Handle the exact string format being received
    if isinstance(lunch_times, str):
        try:
            # First, evaluate the string to convert None to null
            lunch_times = lunch_times.replace("None", "null")
            lunch_times = lunch_times.replace("'", '"')
            lunch_times_dict = json.loads(lunch_times)
            logger.debug(f"Parsed lunch_times to: {lunch_times_dict}")
            return isinstance(lunch_times_dict, dict) and all(day in lunch_times_dict for day in expected_days)
        except Exception as e:
            logger.error(f"Failed to parse lunch_times: {e}")
            return False
    
    return False

def generate_user_hash(payload):
    """Generate a unique hash for user identification"""
    # Combine critical fields that identify a unique user
    unique_string = f"{payload['login_page_link']}:{payload['student_username']}:{payload['student_class']}:{payload['student_fullname']}"
    return hashlib.sha256(unique_string.encode()).hexdigest()

def deactivate_previous_registrations(cursor, user_hash):
    """Deactivate any existing registrations for this user"""
    update_query = f"""
        UPDATE {student_table_name}
        SET is_active = FALSE
        WHERE user_hash = %s AND is_active = TRUE
    """
    cursor.execute(update_query, (user_hash,))

@app.route("/v1/app/qrscan", methods=["POST", "HEAD"])
@limiter.limit(str(os.getenv('QR_CODE_SCAN_LIMIT')) + " per minute")
def process_qr_code():

    if request.method == "OPTIONS":  # Handle preflight request
        response = jsonify({"message": "CORS preflight successful"})
        response.headers["Access-Control-Allow-Origin"] = "*"  # Your frontend domain
        response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        return response

    # Handling actual POST request
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 400

    if request.method == "HEAD":
        return jsonify({"message": ""}), 200
        
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 400

    try:
        request.timeout = 30
        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing request data"}), 400

        # Define required fields in the new QR payload
        required_fields = [
            "session_id", "token", "login_page_link", "student_username", "student_password",
            "student_fullname", "student_firstname", "student_class",
            "ent_used", "qr_code_login", "uuid", "topic_name", "timezone",
            "notification_delay", "evening_menu",
            "unfinished_homework_reminder", "get_bag_ready_reminder"
        ]
        
        # First validate all string fields
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing {field}"}), 400
            if not isinstance(data[field], str):
                return jsonify({"error": f"Invalid {field} type, expected string"}), 400

        # Validate lunch_times separately
        if 'lunch_times' not in data:
            return jsonify({"error": "Missing lunch_times"}), 400
        
        if not validate_lunch_times(data['lunch_times']):
            return jsonify({"error": "Invalid lunch_times format"}), 400

        # Rate limit per session remains
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
        
        # Parse lunch_times from string to dict
        try:
            lunch_times = data['lunch_times'].replace("None", "null")
            lunch_times = lunch_times.replace("'", '"')
            lunch_times_dict = json.loads(lunch_times)
            
            # Sanitize lunch times - handle null/None values
            for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']:
                day_key = day.lower() + '_lunch'
                value = lunch_times_dict.get(day)
                sanitized_payload[day_key] = bleach.clean(str(value)) if value is not None else None

        except Exception as e:
            logger.error(f"Error processing lunch_times: {e}")
            return jsonify({"error": "Invalid lunch_times format"}), 400

        logger.debug(sanitized_payload)

        app_session_id = secrets.token_urlsafe(16)
        app_token = secrets.token_urlsafe(32)

        # Generate user hash
        user_hash = generate_user_hash(sanitized_payload)

        timestamp = datetime.now()

        # Store the data in the student table
        connection = connection_pool.get_connection()
        cursor = connection.cursor()
        try:
            # Deactivate previous registrations
            deactivate_previous_registrations(cursor, user_hash)

            insert_query = f"""
                INSERT INTO {student_table_name} (
                    app_session_id, app_token, login_page_link, student_username, student_password,
                    student_fullname, student_firstname, student_class,
                    ent_used, qr_code_login, uuid, topic_name, timezone,
                    notification_delay, evening_menu,
                    unfinished_homework_reminder, get_bag_ready_reminder,
                    monday_lunch, tuesday_lunch, wednesday_lunch, thursday_lunch, friday_lunch,
                    user_hash, is_active, timestamp
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """
            
            cursor.execute(insert_query, (
                app_session_id,
                app_token,
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
                sanitized_payload['friday_lunch'],
                user_hash,
                1,  # is_active as integer 1 instead of TRUE
                timestamp
            ))

            # Mark the session as used in auth table
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

def cleanup_inactive_students():
    while True:
        try:
            connection = connection_pool.get_connection()
            cursor = connection.cursor()

            # Delete inactive student records
            delete_query = f"""
                DELETE FROM {student_table_name} 
                WHERE is_active = 0
            """
            
            cursor.execute(delete_query)
            deleted_count = cursor.rowcount
            
            if deleted_count > 0:
                connection.commit()
                logger.info(f"Cleaned up {deleted_count} inactive student records")
            
        except mysql.connector.Error as err:
            logger.error(f"MySQL error in student cleanup task: {err}")

        except Exception as e:
            logger.error(f"Unexpected error in student cleanup task: {e}")

        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'connection' in locals():
                connection.close()
            time.sleep(3600)  # Run every hour

def start_background_tasks():
    session_cleanup_thread = threading.Thread(target=cleanup_auth_sessions, daemon=True)
    student_cleanup_thread = threading.Thread(target=cleanup_inactive_students, daemon=True)
    
    session_cleanup_thread.start()
    student_cleanup_thread.start()

@app.before_request
def initialize():
    global initialized
    if not initialized:
        start_background_tasks()
        initialized = True

if __name__ == '__main__':
    app.run(host=os.getenv('HOST'), port=os.getenv('MAIN_PORT'))
