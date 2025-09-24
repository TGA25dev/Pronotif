from flask import Flask, make_response, request, jsonify, session
from functools import wraps
import mysql.connector
from mysql.connector import pooling
import logging
from datetime import datetime, timedelta
import redis
import secrets
import threading
import time
import bleach
import json
from flask_cors import CORS
from flask_talisman import Talisman
from werkzeug.middleware.proxy_fix import ProxyFix
import hashlib
from contextlib import contextmanager
from flask_session import Session
from redis import Redis
import re
import asyncio
import os

from modules.sentry.sentry_config import sentry_sdk
from modules.secrets.secrets_manager import get_secret

from modules.security.encryption import encrypt, decrypt
from modules.admin.coquelicot import coquelicot_bp
from modules.admin.beta import beta_bp
from modules.ratelimit.ratelimiter import limiter

from modules.pronote.notification_system import  get_user_by_auth

#Login Part
from modules.login.get_data_fetcher import get_schools_from_city
from modules.login.temp_login.login import global_pronote_login
from modules.login.verify_manual_link import verify

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
        value = get_secret(var)
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
limiter.init_app(app)
app.wsgi_app = ProxyFix(
    app.wsgi_app,
    x_for=2,       # Number of proxies setting X-Forwarded-For
    x_proto=1,     # Number of proxies setting X-Forwarded-Proto
    x_host=1,      # Number of proxies setting X-Forwarded-Host
    x_port=0,      # Number of proxies setting X-Forwarded-Port
    x_prefix=0     # Number of proxies setting X-Forwarded-Prefix
)
# Parse CORS settings
cors_origins = [origin.strip() for origin in get_secret('CORS_ORIGINS').split(',')]
cors_methods = [method.strip() for method in get_secret('CORS_METHODS').split(',')]
cors_headers = [header.strip() for header in get_secret('CORS_HEADERS').split(',')]
cors_credentials = get_secret('CORS_CREDENTIALS')

CORS(app,
     resources={r"/*": {
         "origins": cors_origins,
         "methods": cors_methods or ["GET","POST","HEAD","OPTIONS"],
         "allow_headers": (cors_headers or []) + ["X-CSRF-Token"],
         "supports_credentials": cors_credentials.lower() == "true"
     }}
)

Talisman(app,
    force_https=True,
    strict_transport_security=True,
    session_cookie_secure=True,
    session_cookie_http_only=True
)

_shared_loop = {"loop": None}
def get_shared_loop():
    loop = _shared_loop.get("loop")
    if loop and loop.is_running():
        return loop
    loop = asyncio.new_event_loop()
    threading.Thread(target=loop.run_forever, daemon=True).start()
    _shared_loop["loop"] = loop
    return loop

# Setup logging
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger('pronotepy').setLevel(logging.WARNING)

app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_KEY_PREFIX'] = 'session:'
app.config['SESSION_REDIS'] = Redis(
    host=get_secret('REDIS_HOST'),
    port=int(get_secret('REDIS_PORT')),
    db=int(get_secret('REDIS_DB')),
    password=(get_secret("REDIS_PASSWORD"))
)

Session(app)

file_handler = logging.FileHandler('app.log')
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# MySQL Connection Pool
default_connection_pool_settings ={
    "pool_name": get_secret('DB_POOL_NAME'),
    "pool_size": int(get_secret('DB_POOL_SIZE')),
    "pool_reset_session": get_secret('DB_POOL_RESET_SESSION'),
    "host": get_secret('DB_HOST'),
    "user": get_secret('DB_USER'),
    "password": get_secret('DB_PASSWORD'),
    "database": get_secret('DB_NAME'),
    "connect_timeout": 30,
    "get_warnings": True,
    "autocommit": True,
    "connection_timeout": 15
}
connection_pool = pooling.MySQLConnectionPool(**default_connection_pool_settings)

auth_table_name = get_secret('DB_AUTH_TABLE_NAME')
student_table_name = get_secret('DB_STUDENT_TABLE_NAME')
beta_table_name = get_secret('DB_BETA_TABLE_NAME')
app.secret_key = get_secret('FLASK_KEY')
app.config['SESSION_COOKIE_SAMESITE'] = 'Strict'
app.config['SESSION_COOKIE_SECURE'] = True  #HTTPS
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)

# Flask-Limiter and Redis Configuration
redis_connection = redis.Redis(
    host=get_secret('REDIS_HOST'),
    port=int(get_secret('REDIS_PORT')),
    db=int(get_secret('REDIS_DB')),
    password=(get_secret("REDIS_PASSWORD"))
)

initialized = False

def require_beta_access(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Skip beta check for beta-related endpoints
        if request.endpoint in ['consume_code', 'verify_beta_access', 'verify_code']:
            return f(*args, **kwargs)
        
        # Check for beta tester cookie
        is_beta_tester = request.cookies.get('is_beta_tester')
        
        if is_beta_tester != '1':
            return jsonify({'error': 'Beta access required'}), 403
        
        return f(*args, **kwargs)
    
    return decorated_function

@app.errorhandler(500)
def internal_error(error):
    sentry_sdk.capture_exception(error)
    logger.critical(f"Internal Server Error: {error}")
    return jsonify({'error': 'An internal error occurred'}), 500


@app.errorhandler(429)
def ratelimit_error(error):
    sentry_sdk.set_context("rate_limit", {
        "ip": request.remote_addr,
        "endpoint": request.endpoint
    })
    
    # Get retry-after from the response if available
    retry_after = None
    if hasattr(error, 'description') and hasattr(error.description, 'headers'):
        retry_after = error.description.headers.get('Retry-After')
    
    sentry_sdk.capture_message("Rate limit exceeded", level="warning")
    logger.warning(f"Rate limit exceeded: {error}")
    
    return jsonify({
        'error': 'Rate limit exceeded',
        'retry_after': retry_after,
    }), 429, {'Retry-After': retry_after} if retry_after else {}


@app.errorhandler(404)
def page_not_found(error):
    logger.warning(f"Page not found: {error}")
    return jsonify({'error': 'Page not found'}), 404

# API Endpoints

@app.route('/ping', methods=['GET'])
@limiter.limit(str(get_secret('PING_LIMIT')) + " per minute")
def test_endpoint():
    """Ping endpoint to test server availability"""
    client_ip = request.remote_addr
    logger.info(f"{client_ip} Pong !")
    return jsonify({"message": "Pong !"}), 200

#PWA Login Endpoints
@app.route("/v1/login/get_schools", methods=["GET", "HEAD"])
@limiter.limit(str(get_secret('SESSION_SETUP_LIMIT')) + " per minute")
def get_school_names():
    """
    Endpoint get school names from a city name or coordinates.
    """

    if request.method == "HEAD":
        return jsonify({"message": ""}), 200

    with sentry_sdk.start_transaction(op="http.server", name="get_school_names"):
        if request.method == "HEAD":
            return jsonify({"message": ""}), 200

        city_name = (request.args.get('city_name'))
        coords = request.args.get('coords', 'false').lower() == 'true'
        lat = request.args.get('lat')
        lon = request.args.get('lon')

        if coords and (not lat or not lon):
            return jsonify({"error": "Latitude and longitude must be provided when coords is true"}), 400

        if not coords and not city_name:
            return jsonify({"error": "City name must be provided when coords is false"}), 400

        try:
            if coords:
                lat = float(lat)
                lon = float(lon)
                if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                    return jsonify({"error": "Invalid latitude or longitude values"}), 400
            else:
                city_name = bleach.clean(city_name)
                if len(city_name) < 2 or len(city_name) > 100:
                    return jsonify({"error": "City name length must be between 2 and 100 characters"}), 400

            schools = get_schools_from_city(city_name, coords, lat, lon)

            if schools is None:
                return jsonify({"error": "Failed to retrieve schools"}), 500

            if isinstance(schools, str):
                return jsonify({"error": schools}), 400

            return jsonify({
                "schools": schools,
                "status": 200
            })

        except ValueError:
            return jsonify({"error": "Invalid latitude or longitude format"}), 400
        
        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.error(f"Unexpected error in get_school_names: {e}")
            return jsonify({"error": "Internal server error"}), 500

#Setup Endpoints
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

@app.route("/v1/app/revoke-fcm-token", methods=["POST", "HEAD"])    
@limiter.limit(str(get_secret('REVOKE_FCM_TOKEN_LIMIT')) + " per minute")
#@require_beta_access
def revoke_fcm_token():
    """
    Revoke the Firebase Cloud Messaging token for the authenticated user
    """

    if request.method == "HEAD":
        return jsonify({"message": ""}), 200

    with sentry_sdk.start_transaction(op="http.server", name="revoke_fcm_token"):
        try:
            app_session_id = request.cookies.get('app_session_id')
            app_token = request.cookies.get('app_token')

            if not app_session_id or not app_token:
                logger.warning("FCM token revocation denied - missing authentication")
                return jsonify({"error": "Authentication required"}), 401

            with get_db_connection() as connection:
                cursor = connection.cursor(dictionary=True)
                try:
                    with sentry_sdk.start_span(op="db.query", description="Revoke FCM token"):
                        query = f"""
                            UPDATE {student_table_name}
                            SET fcm_token = NULL
                            WHERE app_session_id = %s AND app_token = %s AND is_active = TRUE
                        """
                        cursor.execute(query, (app_session_id, app_token))
                        connection.commit()

                        if cursor.rowcount > 0:
                            logger.info(f"FCM token revoked for user: {app_session_id}")
                            return jsonify({"message": "FCM token revoked", "status": 200})
                        else:
                            logger.error(f"Failed to revoke FCM token for user: {app_session_id}")
                            return jsonify({"error": "Failed to revoke FCM token"}), 500
                        
                except mysql.connector.Error as err:
                    sentry_sdk.capture_exception(err)
                    logger.error(f"MySQL error in FCM token revocation: {err}")
                    return jsonify({"error": "Internal server error"}), 500
                
                finally:
                    cursor.close()
                
        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.error(f"Unexpected error in FCM token revocation: {e}")
            return jsonify({"error": "Internal server error"}), 500                

@app.route("/v1/app/fcm-token", methods=["POST", "HEAD"])
@limiter.limit(str(get_secret('FCM_TOKEN_LIMIT')) + " per minute")
#@require_beta_access
def save_fcm_token():
    """
    Endpoint to receive and store Firebase Cloud Messaging token for a user
    """
    if request.method == "HEAD":
        return jsonify({"message": ""}), 200
    
    with sentry_sdk.start_transaction(op="http.server", name="save_fcm_token"):
        try:
            # Get auth cookies
            app_session_id = request.cookies.get('app_session_id')
            app_token = request.cookies.get('app_token')
            
            if not app_session_id or not app_token:
                logger.warning("FCM token update denied - missing authentication")
                return jsonify({"error": "Authentication required"}), 401
            
            # Verify request contains json
            if not request.is_json:
                return jsonify({"error": "Content-Type must be application/json"}), 400
            
            data = request.get_json()
            if not data or 'fcm_token' not in data:
                return jsonify({"error": "Missing FCM token in request body"}), 400
            
            # Sanitize inputs
            app_session_id = bleach.clean(app_session_id)
            app_token = bleach.clean(app_token)
            fcm_token = bleach.clean(data['fcm_token'])
            
            if not fcm_token or len(fcm_token) < 20:
                return jsonify({"error": "Invalid FCM token format"}), 400
            
            # Verify the session and store the token
            with get_db_connection() as connection:
                cursor = connection.cursor(dictionary=True)
                try:
                    with sentry_sdk.start_span(op="db.query", description="Verify user and store FCM token"):
                        # First check if user exists
                        query = f"""
                            SELECT app_session_id FROM {student_table_name}
                            WHERE app_session_id = %s AND app_token = %s AND is_active = TRUE
                        """
                        cursor.execute(query, (app_session_id, app_token))
                        result = cursor.fetchone()
                        
                        if not result:
                            logger.warning(f"FCM token update attempt with invalid credentials: {app_session_id}")
                            return jsonify({"error": "Invalid credentials"}), 401
                        
                        # Update the user record with the FCM token
                        update_query = f"""
                            UPDATE {student_table_name}
                            SET fcm_token = %s, token_updated_at = NOW()
                            WHERE app_session_id = %s AND app_token = %s AND is_active = TRUE
                        """
                        cursor.execute(update_query, (fcm_token, app_session_id, app_token))
                        connection.commit()
                        
                        if cursor.rowcount > 0:
                            logger.info(f"FCM token updated for user: {app_session_id}")
                            return jsonify({
                                "message": "FCM token saved successfully",
                                "status": 200
                            })
                        else:
                            logger.error(f"Failed to update FCM token for user: {app_session_id}")
                            return jsonify({"error": "Failed to save FCM token"}), 500
                
                except mysql.connector.Error as err:
                    sentry_sdk.capture_exception(err)
                    logger.error(f"MySQL error in FCM token endpoint: {err}")
                    return jsonify({"error": "Internal server error"}), 500
                
                finally:
                    cursor.close()
                
        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.error(f"Unexpected error in FCM token endpoint: {e}")
            return jsonify({"error": "Internal server error"}), 500

@app.route("/v1/app/firebase-config", methods=["GET"])
@limiter.limit(str(get_secret('FB_CONFIG_LIMIT')) + " per minute")
#@require_beta_access
def get_firebase_config():
    """
    Send the Firebase configuration to the authenticated user
    """

    if request.method == "HEAD":
        return jsonify({"message": ""}), 200
    
    with sentry_sdk.start_transaction(op="http.server", name="get_firebase_config"):
        try:
            # Get auth cookies
            app_session_id = request.cookies.get('app_session_id')
            app_token = request.cookies.get('app_token')
            
            if not app_session_id or not app_token:
                logger.warning("!!Firebase config access denied - missing authentication!!")
                return jsonify({"error": "Authentication required"}), 401
            
            # Sanitize inputs
            app_session_id = bleach.clean(app_session_id)
            app_token = bleach.clean(app_token)
            
            # Verify the session
            with get_db_connection() as connection:
                cursor = connection.cursor(dictionary=True)
                try:
                    with sentry_sdk.start_span(op="db.query", description="Verify user authentication"):
                        query = f"""
                            SELECT COUNT(*) as count
                            FROM {student_table_name}
                            WHERE app_session_id = %s AND app_token = %s AND is_active = TRUE
                        """
                        cursor.execute(query, (app_session_id, app_token))
                        result = cursor.fetchone()
                        
                        if not result or result['count'] == 0:
                            logger.warning(f"!!Firebase config access attempt with invalid credentials: {app_session_id}!!")
                            return jsonify({"error": "Invalid credentials"}), 401
                    
                        # User is authenticated, return Firebase config
                        firebase_config = {
                            "apiKey": get_secret('FB_API_KEY'),
                            "authDomain": get_secret('FB_AUTH_DOMAIN'),
                            "projectId": get_secret('FB_PROJECT_ID'),
                            "storageBucket": get_secret('FB_STORAGE_BUCKET'),
                            "messagingSenderId": get_secret('FB_MESSAGING_SENDER_ID'),
                            "appId": get_secret('FB_APP_ID')
                        }
                        
                        # Log the successful access
                        logger.info(f"Firebase config provided to authenticated user: {app_session_id}")
                        
                        # Return the config
                        response = jsonify(firebase_config)
                        cache_seconds = int(get_secret('FIREBASE_CONFIG_CACHE_SECONDS'))
                        response.headers['Cache-Control'] = f'private, max-age={cache_seconds}'
                        response.headers['X-Content-Type-Options'] = 'nosniff'
                        return response
                
                except mysql.connector.Error as err:
                    sentry_sdk.capture_exception(err)
                    logger.error(f"MySQL error in firebase config endpoint: {err}")
                    return jsonify({"error": "Internal server error"}), 500
                
                finally:
                    cursor.close()
                
        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.error(f"Unexpected error in firebase config endpoint: {e}")
            return jsonify({"error": "Internal server error"}), 500

@app.route("/v1/login/verifylink", methods=["POST", "HEAD"])
@limiter.limit(str(get_secret('QR_CODE_SCAN_LIMIT')) + " per minute")
#@require_beta_access
def verify_pronote_link():
    """
    Verify the given link is a valid Pronote link and return region
    """

    with sentry_sdk.start_transaction(op="http.server", name="verify_pronote_link"):
        if request.method == "HEAD":
            return jsonify({"message": ""}), 200

        if not request.is_json:
            return jsonify({"error": "Content-Type must be application/json"}), 400

        try:
            request.timeout = 60
            data = request.get_json()
            if not data:
                return jsonify({"error": "Missing request data"}), 400

            # Define required fields
            required_fields = [
                "manual_pronote_link"
            ]
            
            # Validate all string fields
            for field in required_fields:
                if field not in data:
                    return jsonify({"error": f"Missing {field}"}), 400
                
                if not isinstance(data[field], str):
                    return jsonify({"error": f"Invalid {field} type, expected string"}), 400

            # Sanitize all incoming string fields
            sanitized_payload = {}
            for key in required_fields:
                value = data[key]
                # Convert null values to None
                if value is None or (isinstance(value, str) and value.strip().lower() in ['null', 'none', '']):
                    sanitized_payload[key] = None
                else:
                    sanitized_payload[key] = bleach.clean(str(value))

            manual_pronote_link = sanitized_payload['manual_pronote_link']

            result = verify(manual_pronote_link)
            if not isinstance(result, dict):
                return jsonify({"error": "Failed to verify link"}), 500

            if result["isValid"] is False or not result.get("nomEtab") or result["isValid"] is None:
                return jsonify({
                    "error": "Invalid Pronote link",
                    "region": None,
                    "nomEtab": None,
                    "isValid": False
                }), 400

            #strip whitespace at the end and start from region URL and nomEtab
            if "region" in result and result["region"]:
                result["region"] = result["region"].strip()
            if "nomEtab" in result and result["nomEtab"]:
                result["nomEtab"] = result["nomEtab"].strip()
            
            return jsonify({
                "region": result["region"],
                "nomEtab": result["nomEtab"],
                "isValid": True,
                "status": 200
            })
        
        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.error(f"Unexpected error in verify_pronote_link: {e}")
            return jsonify({"error": "Internal server error"}), 500
    

@app.route("/v1/login/auth", methods=["POST", "HEAD"])
@limiter.limit(str(get_secret('QR_CODE_SCAN_LIMIT')) + " per minute")
def login_user():
    """
    Logs the user in by passing the data to another script and then call final endpoint
    """
    with sentry_sdk.start_transaction(op="http.server", name="login_user"):
        if request.method == "HEAD":
            return jsonify({"message": ""}), 200

        if not request.is_json:
            return jsonify({"error": "Content-Type must be application/json"}), 400

        try:
            request.timeout = 60
            data = request.get_json()
            if not data:
                return jsonify({"error": "Missing request data"}), 400

            # Define required fields
            required_fields = [
                "student_username", "student_password", "login_page_link", 
                "qr_code_login", "qrcode_data", "pin", "region"
            ]
            
            # Validate all string fields
            for field in required_fields:
                if field not in data:
                    return jsonify({"error": f"Missing {field}"}), 400
                
                if not isinstance(data[field], str):
                    return jsonify({"error": f"Invalid {field} type, expected string"}), 400

            # Sanitize all incoming string fields
            sanitized_payload = {}
            for key in required_fields:
                value = data[key]
                # Convert null values to None
                if value is None or (isinstance(value, str) and value.strip().lower() in ['null', 'none', '']):
                    sanitized_payload[key] = None
                else:
                    sanitized_payload[key] = bleach.clean(str(value))

            login_page_link = sanitized_payload['login_page_link']
            student_username = sanitized_payload['student_username']
            student_password = sanitized_payload['student_password']
            qr_code_login = sanitized_payload['qr_code_login']
            qrcode_data = sanitized_payload['qrcode_data']
            pin = sanitized_payload['pin']
            region = sanitized_payload['region']

            # Call the module to get user data
            user_data = global_pronote_login(
                login_page_link, 
                student_username, 
                student_password, 
                qr_code_login, 
                qrcode_data, 
                pin, 
                region,
            )
            
            if not isinstance(user_data, dict):
                return jsonify({"error": "Failed to retrieve user data"}), 500
            
            app_session_id = secrets.token_urlsafe(16)
            app_token = secrets.token_urlsafe(32)

            sanitized_payload.update(user_data)

            # Generate user hash (unique logical identity)
            user_hash = generate_user_hash(user_data)
            timestamp = datetime.now()

            encrypted_username   = encrypt(sanitized_payload['student_username'])
            encrypted_password   = encrypt(sanitized_payload['student_password'])
            encrypted_fullname   = encrypt(sanitized_payload['student_fullname'])
            encrypted_firstname  = encrypt(sanitized_payload['student_firstname'])
            encrypted_class      = encrypt(sanitized_payload['student_class'])
            encrypted_login_link = encrypt(sanitized_payload['login_page_link'])
            encrypted_region     = encrypt(sanitized_payload['region'])

            with get_db_connection() as connection:
                cursor = connection.cursor(dictionary=True)
                try:
                    # Look for existing user (latest active or inactive row)
                    cursor.execute(
                        f"SELECT app_session_id FROM {student_table_name} WHERE user_hash = %s ORDER BY timestamp DESC LIMIT 1",
                        (user_hash,)
                    )
                    existing = cursor.fetchone()

                    if existing:
                        old_app_session_id = existing['app_session_id']
                        # Update existing record (overwrite credentials + metadata)
                        update_query = f"""
                            UPDATE {student_table_name}
                            SET 
                                app_session_id = %s,
                                app_token = %s,
                                login_page_link = %s,
                                student_username = %s,
                                student_password = %s,
                                student_fullname = %s,
                                student_firstname = %s,
                                student_class = %s,
                                ent_used = %s,
                                qr_code_login = %s,
                                uuid = %s,
                                timezone = %s,
                                is_active = 1,
                                timestamp = %s,
                                region = %s
                            WHERE app_session_id = %s
                        """
                        cursor.execute(update_query, (
                            app_session_id,
                            app_token,
                            encrypted_login_link,
                            encrypted_username,
                            encrypted_password,
                            encrypted_fullname,
                            encrypted_firstname,
                            encrypted_class,
                            sanitized_payload['ent_used'],
                            sanitized_payload['qr_code_login'],
                            sanitized_payload['uuid'],
                            sanitized_payload['timezone'],
                            timestamp,
                            encrypted_region,
                            old_app_session_id
                        ))

                        connection.commit()
                        logger.info(f"User updated (overwrite) for hash: {user_hash[:12]}...")
                    else:
                        # Insert new record
                        insert_query = f"""
                            INSERT INTO {student_table_name} (
                                app_session_id, app_token, login_page_link, student_username, student_password,
                                student_fullname, student_firstname, student_class,
                                ent_used, qr_code_login, uuid, timezone,
                                user_hash, is_active, timestamp, region
                            ) VALUES (
                                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, %s, %s
                            )
                        """
                        cursor.execute(insert_query, (
                            app_session_id,
                            app_token,
                            encrypted_login_link,
                            encrypted_username,
                            encrypted_password,
                            encrypted_fullname,
                            encrypted_firstname,
                            encrypted_class,
                            sanitized_payload['ent_used'],
                            sanitized_payload['qr_code_login'],
                            sanitized_payload['uuid'],
                            sanitized_payload['timezone'],
                            user_hash,
                            timestamp,
                            encrypted_region
                        ))
                        logger.info(f"User created for hash: {user_hash[:12]}...")

                except mysql.connector.Error as err:
                    sentry_sdk.capture_exception(err)
                    logger.error(f"MySQL error: {err}")
                    return jsonify({"error": "Failed to store student data"}), 500
                
                finally:
                    cursor.close()

            response = make_response(jsonify({"message": "Authentication successful", "status": 200, "success": True}))
            response.set_cookie(
                'app_session_id', 
                app_session_id,
                httponly=True,
                secure=True,
                samesite='Strict',
                max_age=60*60*24*30
            )
            response.set_cookie(
                'app_token', 
                app_token,
                httponly=True,
                secure=True,
                samesite='Strict',
                max_age=60*60*24*30
            )
            return response
        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.error(f"Unexpected error in login_user: {e}")
            return jsonify({"error": "Internal server error"}), 500


@app.route('/v1/app/auth/refresh', methods=['POST', 'HEAD'])
@limiter.limit(str(get_secret('REFRESH_CRED_LIMIT')) + " per minute")
#@require_beta_access
def refresh_credentials():
    """
    Refresh the authentication tokens for the user
    """

    if request.method == "HEAD":
            return jsonify({"message": ""}), 200
    
    # Get cookies
    app_session_id = request.cookies.get('app_session_id')
    app_token = request.cookies.get('app_token')
    
    if not app_session_id or not app_token:
        logger.warning("!! Missing required parameters !!")
        return jsonify({"error": "Authentication required"}), 401
    
    with sentry_sdk.start_transaction(op="http.server", name="refresh_credentials"):
        try:
            # Sanitize inputs
            app_session_id = bleach.clean(app_session_id)
            app_token = bleach.clean(app_token)


            with get_db_connection() as connection:
                cursor = connection.cursor(dictionary=True)

                query = f"""
                    SELECT *
                    FROM {student_table_name}
                    WHERE app_session_id = %s AND app_token = %s 
                    AND is_active = 1
                """
                cursor.execute(query, (app_session_id, app_token))
                result = cursor.fetchone()

                if not result:
                    logger.warning(f"!!! Failed auth attempt: {app_session_id} !!!")
                    return jsonify({"error": "Invalid credentials"}), 401

                # Success - create new tokens and update database
                new_app_session_id = secrets.token_urlsafe(16)
                new_app_token = secrets.token_urlsafe(32)
                
                # Update the database with new tokens
                update_query = f"""
                    UPDATE {student_table_name}
                    SET app_session_id = %s, app_token = %s, timestamp = NOW()
                    WHERE app_session_id = %s AND app_token = %s
                """
                cursor.execute(update_query, (
                    new_app_session_id, new_app_token, app_session_id, app_token
                ))
                connection.commit()

                # Log the refresh event with context
                logger.info(f"Credentials refreshed for user: {result['app_session_id']}")
                
                # Return response with new secure cookies
                response = make_response(jsonify({
                    "message": "Authentication refreshed", 
                    "status": 200
                }))
                
                # Set new secure cookies
                response.set_cookie(
                    'app_session_id', 
                    new_app_session_id,
                    httponly=True, 
                    secure=True, 
                    samesite='Strict',
                    max_age=60*60*24*30,
                    #domain="pronotif.tech"
                )
                response.set_cookie(
                    'app_token', 
                    new_app_token,
                    httponly=True, 
                    secure=True, 
                    samesite='Strict',
                    max_age=60*60*24*30,
                    #domain="pronotif.tech"
                )
                
                # Add security headers
                response.headers['Cache-Control'] = 'no-store'
                response.headers['Pragma'] = 'no-cache'
                response.headers['X-Content-Type-Options'] = 'nosniff'
                
                return response

        except mysql.connector.Error as err:
            sentry_sdk.capture_exception(err)
            logger.error(f"Error: {err}")
            return jsonify({"error": "Internal server error"}), 500    
            
@app.route("/v1/app/fetch", methods=["GET"])
@limiter.limit(str(get_secret('FETCH_DATA_LIMIT')) + " per minute")
#@require_beta_access
def fetch_student_data():
    """
    Fetch and return the student data for the authenticated user
    """

    app_session_id = request.cookies.get('app_session_id')
    app_token = request.cookies.get('app_token')

    if not app_session_id or not app_token:
        return jsonify({"error": "Authentication required"}), 401

    # Get requested fields from query parameters
    requested_fields = request.args.get('fields')
    if not requested_fields:
        return jsonify({"error": "No fields specified"}), 400

    allowed_fields = {
        "student_firstname", "student_fullname", "student_class", 
        "login_page_link", "ent_used", 
        "qr_code_login", "timezone", "notification_delay", 
        "evening_menu", "unfinished_homework_reminder", 
        "get_bag_ready_reminder", "monday_lunch", "tuesday_lunch", 
        "wednesday_lunch", "thursday_lunch", "friday_lunch",
        "next_class_name", "next_class_room", "next_class_teacher", 
        "next_class_start", "next_class_end",
        "fcm_token", "token_updated_at", "timestamp", "is_active"
    }

    # Validate and sanitize requested fields
    fields = list(set(field.strip() for field in requested_fields.split(',') if field.strip() in allowed_fields))
    if not fields:
        return jsonify({"error": "Invalid or no fields specified"}), 400

    try:
        # Sanitize inputs
        app_session_id = bleach.clean(app_session_id)
        app_token = bleach.clean(app_token)

        # Separate DB fields from Pronote fields
        db_fields = [f for f in fields if not f.startswith(('next_class_'))]
        pronote_fields = [f for f in fields if f.startswith(('next_class_'))]
        
        response_data = {}

        # Get database fields first (also serves as authentication)
        if db_fields:
            with get_db_connection() as connection:
                cursor = connection.cursor(dictionary=True)
                try:
                    query = f"""
                        SELECT {', '.join(db_fields)}
                        FROM {student_table_name}
                        WHERE app_session_id = %s AND app_token = %s AND is_active = TRUE
                    """
                    cursor.execute(query, (app_session_id, app_token))
                    result = cursor.fetchone()

                    if not result:
                        logger.warning(f"Invalid credentials for session: {app_session_id[:4]}****")
                        return jsonify({"error": "Invalid credentials"}), 401

                    # Process DB fields
                    for field in db_fields:
                        if field not in result:
                            continue
                            
                        # Decrypt sensitive fields
                        if field in ['student_firstname', 'student_fullname', 'student_class', 'login_page_link']:
                            try:
                                response_data[field] = decrypt(result[field])
                            except Exception as e:
                                logger.error(f"Error decrypting {field}: {e}")
                                sentry_sdk.capture_exception(e)
                                response_data[field] = None
                        else:
                            response_data[field] = result[field]

                except mysql.connector.Error as err:
                    sentry_sdk.capture_exception(err)
                    logger.error(f"MySQL error: {err}")
                    return jsonify({"error": "Internal server error"}), 500

                finally:
                    cursor.close()
        else:
            # If no DB fields requested, still verify authentication
            with get_db_connection() as connection:
                cursor = connection.cursor()
                try:
                    query = f"""
                        SELECT 1 FROM {student_table_name}
                        WHERE app_session_id = %s AND app_token = %s AND is_active = TRUE
                    """
                    cursor.execute(query, (app_session_id, app_token))
                    if not cursor.fetchone():
                        return jsonify({"error": "Invalid credentials"}), 401
                finally:
                    cursor.close()

        # Get Pronote fields from existing user session if requested
        if pronote_fields:
            try:
                shared_loop = get_shared_loop()
                # Fetch user object with timeout
                fut_user = asyncio.run_coroutine_threadsafe(
                    get_user_by_auth(app_session_id, app_token),
                    shared_loop
                )
                user = fut_user.result(timeout=8)
                if user and user.client and user.client.logged_in:
                    fut_data = asyncio.run_coroutine_threadsafe(
                        user.get_pronote_data(pronote_fields),
                        shared_loop
                    )
                    pronote_data = fut_data.result(timeout=8)
                    response_data.update(pronote_data)
                else:
                    for field in pronote_fields:
                        response_data[field] = None
            except Exception as e:
                logger.error(f"Error fetching Pronote data: {e}")
                sentry_sdk.capture_exception(e)
                for field in pronote_fields:
                    response_data[field] = None

        response = jsonify({
            "data": response_data,
            "status": 200
        })
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    except Exception as e:
        sentry_sdk.capture_exception(e)
        logger.error(f"Unexpected error in fetch_student_data: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/v1/app/dynamic-banner", methods=["GET"])
@limiter.limit(str(get_secret('FETCH_DATA_LIMIT')) + " per minute")
#@require_beta_access
def get_banner_content():
    """
    Get the dynamic banner content from a JSON file
    """

    try:
        banner_file_path = os.path.join(os.path.dirname(__file__), 'banner.json')
        if not os.path.isfile(banner_file_path):
            return jsonify({"error": "Banner file not found"}), 404

        with open(banner_file_path, 'r', encoding='utf-8') as f:
            try:
                banner_data = json.load(f)
            except json.JSONDecodeError as e:
                logger.error(f"Error decoding banner JSON: {e}")
                return jsonify({"error": "Invalid banner data"}), 500

        # Validate banner data structure
        if not isinstance(banner_data, dict):
            return jsonify({"error": "Invalid banner data format"}), 500

        required_keys = {"message", "type", "link", "icon"}
        if not required_keys.issubset(banner_data.keys()):
            return jsonify({"error": "Incomplete banner data"}), 500

        # Sanitize banner content
        sanitized_banner = {
            "message": bleach.clean(banner_data.get("message", "")),
            "type": bleach.clean(banner_data.get("type", "")),
            "icon": bleach.clean(banner_data.get("icon", "")),
            "link": bleach.clean(banner_data.get("link", ""))
        }

        response = jsonify({
            "data": sanitized_banner,
            "status": 200
        })
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    except Exception as e:
        sentry_sdk.capture_exception(e)
        logger.error(f"Unexpected error in get_banner_content: {e}")
        return jsonify({"error": "Internal server error"}), 500

# BETA ENDPOINTS
@app.route('/v1/beta/verify-access', methods=['GET'])
@limiter.limit(str(get_secret('BETA_VERIFY_LIMIT')) + " per minute")
def verify_beta_access():
    """
    Verify if the user has beta access based on a cookie
    """
    if request.method == "HEAD":
        return jsonify({"message": ""}), 200
    # Check for the beta tester cookie
    is_beta_tester = request.cookies.get('is_beta_tester')
    
    if is_beta_tester == '1':
        return jsonify({'hasAccess': True})
    else:
        return jsonify({'hasAccess': False})
    
@app.route("/v1/beta/verify", methods=["POST", "HEAD"])
@limiter.limit(str(get_secret('BETA_VERIFY_LIMIT')) + " per minute")
def verify_code():
    """
    Verify a beta code
    """
    if request.method == "HEAD":
        return jsonify({"message": ""}), 200

    with sentry_sdk.start_transaction(op="http.server", name="verify_beta_code"):
        try:
            if not request.is_json:
                return jsonify({"success": False, "error": "Content-Type must be application/json"}), 400

            data = request.get_json()
            if not data:
                return jsonify({"success": False, "error": "Missing request data"}), 400

            code = data.get("code", "").strip().upper()
            if not code:
                return jsonify({"success": False, "error": "Code required"}), 400

            # Sanitize the code
            code = bleach.clean(code)
            
            # Validate code format
            if not re.match(r'^[A-Z0-9]{3}-[A-Z0-9]{3}-[A-Z0-9]{3}$', code):
                return jsonify({"success": False, "error": "Invalid code format"}), 400

            with get_db_connection() as connection:
                cursor = connection.cursor(dictionary=True)
                try:
                    with sentry_sdk.start_span(op="db.query", description="Verify beta code"):
                        cursor.execute(
                            f"SELECT code FROM {beta_table_name} WHERE code = %s AND is_used = 0", 
                            (code,)
                        )
                        result = cursor.fetchone()

                        if result:
                            logger.info(f"Beta code verified successfully")
                            return jsonify({"success": True}), 200
                        else:
                            logger.warning(f"Invalid beta code verification attempt")
                            return jsonify({"success": False, "error": "Invalid or expired code"}), 403

                except mysql.connector.Error as err:
                    sentry_sdk.capture_exception(err)
                    logger.error(f"MySQL error in beta verify: {err}")
                    return jsonify({"success": False, "error": "Internal server error"}), 500

                finally:
                    cursor.close()

        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.error(f"Unexpected error in verify_code: {e}")
            return jsonify({"success": False, "error": "Internal server error"}), 500

@app.route("/v1/beta/consume", methods=["POST", "HEAD"])
@limiter.limit(str(get_secret('BETA_CONSUME_LIMIT')) + " per hour")
def consume_code():
    """
    Consume a beta code
    """
    if request.method == "HEAD":
        return jsonify({"message": ""}), 200

    with sentry_sdk.start_transaction(op="http.server", name="consume_beta_code"):
        try:
            if not request.is_json:
                return jsonify({"success": False, "error": "Content-Type must be application/json"}), 400

            data = request.get_json()
            if not data:
                return jsonify({"success": False, "error": "Missing request data"}), 400

            code = data.get("code", "").strip().upper()
            if not code:
                return jsonify({"success": False, "error": "Code required"}), 400

            # Sanitize the code
            code = bleach.clean(code)
            
            # Validate code format
            if not re.match(r'^[A-Z0-9]{3}-[A-Z0-9]{3}-[A-Z0-9]{3}$', code):
                return jsonify({"success": False, "error": "Invalid code format"}), 400

            with get_db_connection() as connection:
                cursor = connection.cursor(dictionary=True)
                try:
                    with sentry_sdk.start_span(op="db.query", description="Consume beta code"):
                        # Verify the code exists and is unused
                        cursor.execute(
                            f"SELECT code FROM {beta_table_name} WHERE code = %s AND is_used = 0", 
                            (code,)
                        )
                        result = cursor.fetchone()

                        if result:
                            # Update the code as used
                            cursor.execute(
                                f"UPDATE {beta_table_name} SET is_used = 1, used_at = %s WHERE code = %s",
                                (datetime.now(), code)
                            )
                            connection.commit()
                            
                            logger.info(f"Beta code consumed successfully")
                            response = make_response(jsonify({"success": True}), 200)
                            # Set secure HTTP-only cookie for beta tester
                            response.set_cookie(
                                'is_beta_tester',
                                '1',
                                httponly=True,
                                secure=True,
                                samesite='Strict',
                                max_age=60*60*24*365  # 1 year
                                # domain="pronotif.tech"
                            )
                            return response
                        else:
                            logger.warning(f"Invalid beta code consumption attempt")
                            return jsonify({"success": False, "error": "Invalid or expired code"}), 403

                except mysql.connector.Error as err:
                    sentry_sdk.capture_exception(err)
                    logger.error(f"MySQL error in beta consume: {err}")
                    return jsonify({"success": False, "error": "Internal server error"}), 500

                finally:
                    cursor.close()

        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.error(f"Unexpected error in consume_code: {e}")
            return jsonify({"success": False, "error": "Internal server error"}), 500

#Internal endpoints
@app.route("/v1/internal/invalid_token", methods=["POST"])
@limiter.limit(str(get_secret('INTERNAL_ENDPOINTS_LIMIT')) + "per hour")
def invalid_token():
    """
    Internal endpoint to mark a user's firebase token as invalid
    """
    # Require internal auth
    auth_header = request.headers.get('X-Internal-Auth')
    if not auth_header or auth_header != get_secret('INTERNAL_API_KEY'):
        return jsonify({"error": "Unauthorized"}), 401
        
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 400
        
    data = request.get_json()
    if not data or 'fcm_token' not in data:
        return jsonify({"error": "Missing FCM token"}), 400
        
    fcm_token = bleach.clean(data['fcm_token'])
    
    with get_db_connection() as connection:
        cursor = connection.cursor()
        try:
            # Update all records with this token
            query = f"""
                UPDATE {student_table_name}
                SET fcm_token = NULL, token_updated_at = NOW()
                WHERE fcm_token = %s
            """
            cursor.execute(query, (fcm_token,))
            connection.commit()

            logger.info(f"FCM token invalidated for {cursor.rowcount} records")
            return jsonify({"success": True, "records_updated": cursor.rowcount}), 200
            
        except mysql.connector.Error as err:
            sentry_sdk.capture_exception(err)
            logger.error(f"MySQL error in invalid_token: {err}")
            return jsonify({"error": "Database error"}), 500
            
        finally:
            cursor.close()



# Background tasks
def cleanup_inactive_students():
    while True:
        try:
            with sentry_sdk.start_transaction(op="background_task", name="cleanup_inactive_students") as transaction:
                with get_db_connection() as connection:
                    cursor = connection.cursor()

                    with sentry_sdk.start_span(description="Delete inactive students"):
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
            sentry_sdk.capture_exception(err)
            logger.error(f"MySQL error in student cleanup task: {err}")

        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.error(f"Unexpected error in student cleanup task: {e}")

        finally:
            cursor.close()
            time.sleep(3600)  # every hour

def monitor_pool():
    last_used = 0
    while True:
        try:
            if hasattr(connection_pool, '_cnx_queue'):
                available = connection_pool._cnx_queue.qsize()
                total = int(get_secret('DB_POOL_SIZE'))
                used = total - available
                
                # Potential connection leak
                if used > last_used + 3:  # Sudden increase in used connections
                    logger.warning(f"Potential connection leak detected! Used connections jumped from {last_used} to {used}")
                    sentry_sdk.capture_message(f"Potential connection leak detected! Used connections jumped from {last_used} to {used}")
                
                last_used = used
                #logger.info(f"Connection pool status - Used: {used}, Available: {available}, Total: {total}") # Uncomment for debugging
                
                # Alert on low available connections
                if available < total * 0.2:  # 20% threshold
                    logger.warning(f"Connection pool running low!! Only {available} connections available !!")
                    sentry_sdk.capture_message(f"Connection pool running low! Only {available} connections available")

        except Exception as e:
            logger.error(f"Pool monitoring error: {e}")
            sentry_sdk.capture_exception(e)
        time.sleep(30)

def reset_connection_pool():
    global connection_pool
    logger.warning("Attempting to reset connection pool")
    try:
        # Create new pool
        connection_pool = pooling.MySQLConnectionPool(**default_connection_pool_settings)
        logger.info("Connection pool successfully reset")

    except Exception as e:
        sentry_sdk.capture_exception(e)
        logger.critical(f"Failed to reset connection pool: {e}")
        sentry_sdk.capture_exception(e)      

def start_background_tasks():
    student_cleanup_thread = threading.Thread(target=cleanup_inactive_students, daemon=True)
    pool_monitor_thread = threading.Thread(target=monitor_pool, daemon=True)
    
    student_cleanup_thread.start()
    pool_monitor_thread.start()

@contextmanager
def get_db_connection():
    connection = None
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            connection = connection_pool.get_connection()
            
            # Test if connection is valid
            cursor = connection.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            
            # Yield the connection for use
            try:
                yield connection
            finally:
               
                if connection:
                    connection.close()
            return 
            
        except mysql.connector.errors.PoolError as err:
            retry_count += 1
            logger.warning(f"Pool error on attempt {retry_count}: {err}")
            sentry_sdk.capture_exception(err)
            
            if retry_count >= max_retries:
                logger.critical("Connection pool exhausted after retries")
                raise
                
            if retry_count == max_retries - 1:
                reset_connection_pool()
            
            time.sleep(min(2 ** retry_count, 5))  #Backoff caped at 5 seconds
            
        except mysql.connector.Error as err:
            sentry_sdk.capture_exception(err)
            logger.error(f"Database error: {err}")
            raise
            
        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.error(f"Unexpected error: {e}")
            raise

initialized = False

_background_started = False
@app.before_request
def initialize():
    global initialized, _background_started
    if not initialized:
        initialized = True
    if not _background_started and get_secret("RUN_BG_TASKS") == "1":
        _background_started = True
        start_background_tasks()
    if request.method in ("POST","PUT","PATCH","DELETE") and request.endpoint not in ("login_user", "verify_code", "consume_code", "invalid_token"):
        c_cookie = request.cookies.get("csrf_token")
        c_header = request.headers.get("X-CSRF-Token")
        if not c_cookie or not c_header or c_cookie != c_header:
            return jsonify({"error": "CSRF validation failed"}), 403
        
@app.after_request
def set_csrf_cookie(resp):
    # Generate only if missing
    if not request.cookies.get("csrf_token"):
        token = secrets.token_urlsafe(16)
        resp.set_cookie(
            "csrf_token",
            token,
            domain=".pronotif.tech",
            secure=True,
            httponly=False,
            samesite="Strict",
            max_age=3600,
            path="/"
        )
    return resp

# Register blueprints
app.register_blueprint(coquelicot_bp)
app.register_blueprint(beta_bp)

if __name__ == '__main__':    
    # Start the Flask app
    app.run(host=get_secret('HOST'), port=get_secret('MAIN_PORT'))
