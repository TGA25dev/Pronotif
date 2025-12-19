import asyncio
import os
import time
import sys
import mysql.connector
from mysql.connector import pooling
from contextlib import contextmanager
from datetime import datetime, timedelta
from datetime import time as dt_time
import requests
import aiohttp
import aiofiles
import json
import random
import redis
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from modules.secrets.secrets_manager import get_secret

from modules.pronote.users import PronotifUser
from modules.messaging.firebase import send_notification_to_device

from modules.sentry.sentry_config import get_logger_enabled_sentry

sentry_sdk, sentry_logger, logger = get_logger_enabled_sentry()

# Send Loguru logs to Sentry
def sentry_sink(message):
    record = message.record
    level = record["level"].name.lower()
    sentry_logger = sentry_sdk.logger
    if hasattr(sentry_logger, level):
        getattr(sentry_logger, level)(record["message"], extra=record["extra"])
    else:
        sentry_logger.info(record["message"], extra=record["extra"])

# Configure Loguru
logger.remove()
logger.add(sys.stdout, level="TRACE")  # Local logs (with trace/success)
logger.add("notif_system_logs.log", level="TRACE", rotation="500 MB")  # File logging
logger.add(sentry_sink, level="DEBUG")  # Forward important logs to Sentry

DB_CONFIG = {
    "host": get_secret('DB_HOST'),
    "user": get_secret('DB_USER'),
    "password": get_secret('DB_PASSWORD'),
    "database": get_secret('DB_NAME')
}
table_name = get_secret('DB_STUDENT_TABLE_NAME')

# Connection pool configuration
DB_POOL_CONFIG = {
    "pool_name": "client_pool",
    "pool_size": int(get_secret('DB_POOL_SIZE', '10')),
    "pool_reset_session": True,
    **DB_CONFIG,
    "connect_timeout": 30,
    "get_warnings": True,
    "autocommit": True,
    "connection_timeout": 15
}

# Get the absolute path to the data directory
script_dir = os.path.dirname(os.path.abspath(__file__))  # /modules/pronote
server_dir = os.path.dirname(os.path.dirname(script_dir))
data_dir = os.path.join(server_dir, 'data')

# Initialize connection pool
try:
    connection_pool = pooling.MySQLConnectionPool(**DB_POOL_CONFIG)
    logger.info(f"Database connection pool initialized with size {DB_POOL_CONFIG['pool_size']}")
except Exception as e:
    logger.critical(f"Failed to initialize connection pool: {e}")
    sentry_sdk.capture_exception(e)
    sys.exit(1)

# Context manager for database connections
@contextmanager
def get_db_connection():
    """Get a database connection from the pool and handle errors"""
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
            
            yield connection
            break  # If successful, exit the retry loop
            
        except mysql.connector.errors.PoolError as err:
            # No available connections in pool
            retry_count += 1
            logger.warning(f"Pool error on attempt {retry_count}: {err}")
            
            if retry_count >= max_retries:
                logger.error("Connection pool exhausted after retries")
                sentry_sdk.capture_exception(err)
                raise
                
            # Wait before retrying
            time.sleep(0.5 * (2 ** retry_count))
            
        except mysql.connector.errors.InterfaceError as err:
            # Connection interface error
            retry_count += 1
            logger.warning(f"Connection interface error on attempt {retry_count}: {err}")
            
            if retry_count >= max_retries:
                logger.error("Failed to establish working connection after retries")
                sentry_sdk.capture_exception(err)
                raise
                
            time.sleep(0.5 * (2 ** retry_count))
            
        except mysql.connector.Error as err:
            # Other MySQL errors
            logger.error(f"Database error: {err}")
            sentry_sdk.capture_exception(err)
            raise
            
        finally:
            if connection:
                try:
                    connection.close()
                except Exception as e:
                    logger.error(f"Error closing connection: {e}")

# Store previous user list
_previous_user_hashes = set()
_existing_users = {}  # Cache of user objects by ID

# Lock for shared resources
user_update_lock = asyncio.Lock()

redis_client = redis.Redis(
    host=get_secret('REDIS_HOST'),
    port=int(get_secret('REDIS_PORT')),
    db=int(get_secret('REDIS_DB', '0')),
    password=get_secret('REDIS_PASSWORD', None),
)

async def load_active_users() -> list:
    """Load all active users from the database using connection pooling"""
    global _previous_user_hashes, _existing_users
    users = []
    
    async with user_update_lock:
        try:
            with get_db_connection() as connection:
                cursor = connection.cursor(dictionary=True)
                
                query = f"""
                SELECT *
                FROM {table_name}
                WHERE is_active = 1
                """
                cursor.execute(query)
                results = cursor.fetchall()
                
                # Process query results
                current_user_hashes = set()
                for user_data in results:
                    user_hash = user_data['user_hash']
                    current_user_hashes.add(user_hash)
                    
                    if user_hash in _existing_users:
                        # Update existing user with fresh data
                        _existing_users[user_hash].update_from_db(user_data)
                        users.append(_existing_users[user_hash])
                    else:
                        # Only create new users that don't already exist
                        new_user = PronotifUser(user_data)
                        _existing_users[user_hash] = new_user
                        users.append(new_user)
                
                # Clean up removed users
                for old_id in list(_existing_users.keys()):
                    if old_id not in current_user_hashes:
                        del _existing_users[old_id]
                        #Remove from Redis too
                        try:
                            redis_client.delete(f"user_session:{old_id}")
                        except Exception as e:
                            logger.error(f"Failed to remove user from Redis: {e}")
                
                #Store user sessions in Redis for sharing with app.py
                try:
                    for user_hash, user in _existing_users.items():
                        user_info = {
                            'app_session_id': user.app_session_id,
                            'user_hash': user.user_hash,
                            'logged_in': user.client and user.client.logged_in if user.client else False
                        }
                        redis_client.setex(
                            f"user_session:{user_hash}", 
                            300,  # 5 minutes TTL
                            json.dumps(user_info)
                        )
                except Exception as e:
                    logger.error(f"Failed to store user sessions in Redis: {e}")
                
                # Only log if the set of users has changed
                if current_user_hashes != _previous_user_hashes:
                    new_count = len(current_user_hashes - _previous_user_hashes)
                    removed_count = len(_previous_user_hashes - current_user_hashes)
                    logger.info(f"Loaded {len(users)} active users from database ({new_count} new, {removed_count} removed)")
                    _previous_user_hashes = current_user_hashes
                    
                return users
                
        except Exception as e:
            logger.error(f"Failed to load users: {e}")
            sentry_sdk.capture_exception(e)
            return []

async def check_internet_connection() -> bool:
    url = "http://www.google.com"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=15) as resp:
                return resp.status == 200
    except Exception:
        return False
    

async def get_user_by_auth(app_session_id: str, app_token: str) -> PronotifUser:
    """Get an existing PronotifUser instance by authentication credentials"""
    
    #first check local _existing_users 
    for user_hash, user in _existing_users.items():
        if user.app_session_id == app_session_id:
            #Verify token matches
            try:
                with get_db_connection() as connection:
                    cursor = connection.cursor(dictionary=True)
                    query = f"""
                    SELECT app_token FROM {table_name}
                    WHERE app_session_id = %s AND is_active = 1
                    """
                    cursor.execute(query, (app_session_id, app_token))
                    result = cursor.fetchone()
                    
                    if result and result['app_token'] == app_token:
                        logger.success(f"Found user {user_hash} in local cache for session {app_session_id}")
                        return user
            except Exception as e:
                logger.error(f"Error verifying user auth: {e}")
    
    try:
        with get_db_connection() as connection:
            cursor = connection.cursor(dictionary=True)
            query = f"""
            SELECT user_hash FROM {table_name}
            WHERE app_session_id = %s AND app_token = %s AND is_active = 1
            """
            cursor.execute(query, (app_session_id, app_token))
            result = cursor.fetchone()
            
            if not result:
                logger.warning(f"User with session {app_session_id} not found in database or invalid token")
                return None
                
            user_hash = result['user_hash']
            
            # Check if this user has an active session in Redis
            try:
                user_session_data = redis_client.get(f"user_session:{user_hash}")
                if user_session_data:
                    user_info = json.loads(user_session_data)
                    if user_info.get('logged_in'):
                        logger.success(f"Found active user session in Redis for {user_hash}")
                        # Create a temporary user object for API use
                        return await create_temp_user_for_api(user_hash, app_session_id, app_token)
                    else:
                        logger.warning(f"User {user_hash} found in Redis but not logged in - attempting direct login")
                        #Try direct login for immediate API access
                        return await create_temp_user_for_api(user_hash, app_session_id, app_token)
                else:
                    logger.info(f"User {user_hash} not found in Redis active sessions - attempting direct login")
                    # User not in Redis yet, create temporary user from database
                    return await create_temp_user_for_api(user_hash, app_session_id, app_token)
            except Exception as e:
                logger.error(f"Error checking Redis for user session: {e}")
            
            return None
                
    except Exception as e:
        logger.error(f"Error verifying user auth: {e}")
        return None

async def create_temp_user_for_api(user_hash: str, app_session_id: str, app_token: str) -> PronotifUser:
    """Create a temporary user for API access using existing session"""
    try:
        with get_db_connection() as connection:
            cursor = connection.cursor(dictionary=True)
            query = f"""
            SELECT * FROM {table_name}
            WHERE user_hash = %s AND app_session_id = %s AND app_token = %s AND is_active = 1
            """
            cursor.execute(query, (user_hash, app_session_id, app_token))
            result = cursor.fetchone()
            
            if result:
                # Create user and attempt login
                temp_user = PronotifUser(result)
                if await temp_user.login():
                    logger.info(f"Created temporary user for API access: {user_hash}")
                    return temp_user
                else:
                    logger.error(f"Failed to login temporary user for API: {user_hash}")
                    return None
            else:
                logger.error(f"User data not found for hash: {user_hash}")
                return None
                
    except Exception as e:
        logger.error(f"Error creating temporary user: {e}")
        return None


async def user_process_loop(user:PronotifUser) -> None: 
    """Handle all checks and notifications for a single user with staggered timing"""
    consecutive_failures = 0
    max_consecutive_failures = 10
    
    try:
        # Login
        if not await user.login():
            logger.error(f"Failed to login user {user.user_hash}, skipping...")
            return
            
        # Update Redis with logged in status
        try:
            user_info = {
                'app_session_id': user.app_session_id,
                'user_hash': user.user_hash,
                'logged_in': True
            }
            redis_client.setex(
                f"user_session:{user.user_hash}", 
                300,  # 5 minutes TTL
                json.dumps(user_info)
            )
        except Exception as e:
            logger.error(f"Failed to update Redis session for user {user.user_hash}: {e}")
            
        no_internet_message = False
        instance_not_reachable_message = False
        
        user_offset = hash(user.user_hash) % 30
        logger.debug(f"User {user.user_hash[:4]}**** assigned offset of {user_offset} seconds")
        await asyncio.sleep(user_offset)
        
        while True:
            start_time = time.time()
            
            try:
                # Check connectivity with longer timeout
                internet_available = await check_internet_connection()
                server_reachable = await user.check_pronote_server() if internet_available else False
                
                if internet_available and server_reachable:
                    if no_internet_message or instance_not_reachable_message:
                        logger.info(f"Connectivity restored for user {user.user_hash[:4]}****")
                        no_internet_message = False
                        instance_not_reachable_message = False
                        consecutive_failures = 0  # Reset failure counter
                    
                    await user.check_session()
                    
                    # Update Redis session status
                    try:
                        user_info = {
                            'app_session_id': user.app_session_id,
                            'user_hash': user.user_hash,
                            'logged_in': user.client and user.client.logged_in if user.client else False
                        }
                        redis_client.setex(
                            f"user_session:{user.user_hash}", 
                            300,  # 5 minutes TTL
                            json.dumps(user_info)
                        )
                    except Exception as e:
                        logger.error(f"Failed to update Redis session: {e}")
                    
                    # Run all notification checks in parallel
                    await asyncio.gather(
                        lesson_check(user), 
                        menu_food_check(user), 
                        check_reminder_notifications(user)
                    )
                    
                    consecutive_failures = 0  # Reset on success
                    
                else:
                    consecutive_failures += 1
                    if consecutive_failures >= max_consecutive_failures:
                        logger.critical(f"User {user.user_hash[:4]}**** has {consecutive_failures} consecutive failures. Pausing for 10 minutes.")
                        await asyncio.sleep(600)  # Wait 10 minutes before trying again
                        consecutive_failures = 0  # Reset after long wait
                    
                    if not no_internet_message and not instance_not_reachable_message:
                        logger.warning(f"Tasks paused for user {user.user_hash[:4]}**** - No internet or server unreachable")
                        no_internet_message = True
                        instance_not_reachable_message = True
                
            except Exception as loop_error:
                consecutive_failures += 1
                logger.error(f"Error in main loop for user {user.user_hash[:4]}****: {loop_error}")
                
                if consecutive_failures >= max_consecutive_failures:
                    logger.critical(f"Too many consecutive errors for user {user.user_hash[:4]}****. Pausing.")
                    await asyncio.sleep(600) #10min
                    consecutive_failures = 0
            
            # Calculate time to next check with adaptive timing based on failures
            base_sleep = 60 if consecutive_failures < 3 else 120  # Longer intervals during issues
            current_seconds = datetime.now().second
            sleep_time = ((base_sleep - current_seconds) + user_offset) % base_sleep or base_sleep
            await asyncio.sleep(sleep_time)
            
    except Exception as e:
        logger.critical(f"Critical error in user loop for {user.user_hash[:4]}****: {e}")
        sentry_sdk.capture_exception(e)
        
async def retry_with_backoff(func, user, *args, max_attempts=5) -> None:
    """Retry a function with exponential backoff"""
    timeout_incident_id = None
    
    for attempt in range(max_attempts):
        try:
            result = await func(user, *args)
            
            # If previously reported a timeout and now succeeded, mark it as resolved
            if timeout_incident_id:
                with sentry_sdk.push_scope() as scope:
                    scope.set_tag("error_type", "timeout")
                    scope.set_tag("function", func.__name__)
                    scope.set_tag("status", "resolved")
                    scope.set_tag("user_id", user.user_hash)
                    scope.fingerprint = ["pronotif", "timeout", func.__name__, user.user_hash]
                    sentry_sdk.capture_message(
                        f"Timeout resolved for {func.__name__} after {attempt} retries",
                        level="info"
                    )
                logger.success(f"Function {func.__name__} recovered for user {user.user_hash} after {attempt} retries")
                
            # Only log success if it's not the first attempt
            elif attempt > 0:
                logger.success(f"Function {func.__name__} succeeded for user {user.user_hash} after {attempt} retries")
            
            return result
            
        except (requests.exceptions.ReadTimeout, 
                requests.exceptions.ConnectTimeout, 
                requests.exceptions.ConnectionError,
                aiohttp.ClientError,
                asyncio.TimeoutError,
                aiohttp.ServerTimeoutError) as e:
            
            wait_time = 10 * (2 ** attempt)
            
            if attempt == 0:
                with sentry_sdk.push_scope() as scope:
                    scope.set_tag("error_type", "timeout")
                    scope.set_tag("function", func.__name__)
                    scope.set_tag("status", "ongoing")
                    scope.set_tag("user_id", user.user_hash)
                    scope.fingerprint = ["pronotif", "timeout", func.__name__, user.user_hash]
                    timeout_incident_id = sentry_sdk.capture_message(
                        f"Timeout occurred in {func.__name__} for user {user.user_hash}",
                        level="error"
                    )
            
            if attempt == max_attempts - 1:
                with sentry_sdk.push_scope() as scope:
                    scope.set_tag("error_type", "timeout")
                    scope.set_tag("function", func.__name__)
                    scope.set_tag("status", "failed")
                    scope.set_tag("total_retries", str(max_attempts))
                    scope.set_tag("user_id", user.user_hash)
                    scope.fingerprint = ["pronotif", "timeout", func.__name__, user.user_hash]
                    sentry_sdk.capture_message(
                        f"All retry attempts failed for {func.__name__} for user {user.user_hash}",
                        level="error"
                    )
                    
                if func.__name__ in ['fetch_lessons', 'fetch_menus']:
                    return []
                else:
                    return None
            
            logger.warning(f"Network error for user {user.user_hash}: {e}. "
                          f"Retrying in {wait_time} seconds... (Attempt {attempt + 1}/{max_attempts})")
            await asyncio.sleep(wait_time)

        except Exception as e:
            logger.error(f"Error in {func.__name__} for user {user.user_hash}: {e}")
            sentry_sdk.capture_exception(e)
            if not await user.handle_error_with_relogin(e):
                return [] if func.__name__ in ['fetch_lessons', 'fetch_menus'] else None
            raise

def get_i18n_value(lang: str, key: str, **kwargs) -> str:
    """Get translated value from i18n files with variable substitution"""
    global fr_file, en_file, es_file
    
    i18n_files = {
        'fr': fr_file,
        'en': en_file,
        'es': es_file
    }
    
    #Default to French
    translations = i18n_files.get(lang, fr_file)
    
    if not translations:
        logger.warning(f"No translations loaded for language: {lang}")
        return key
    
    #nested keys
    keys = key.split('.')
    value = translations
    
    for k in keys:
        if isinstance(value, dict):
            value = value.get(k)
        else:
            logger.warning(f"Missing translation key: {key} for language: {lang}")
            return key
    
    if not isinstance(value, str):
        logger.warning(f"Translation key {key} is not a string for language: {lang}")
        return key
    
    #placeholders substitution
    if kwargs:
        for placeholder, replacement in kwargs.items():
            
            value = value.replace(f"{{{placeholder}}}", str(replacement))
    
    return value


def inform_user_relogin_is_needed(user):
    """
    Inform the user that relogin in the app is needed via notification
    """
    lang = user.lang
    
    title = get_i18n_value(lang, 'notification.logoutInfoTitle')
    body = get_i18n_value(lang, 'notification.logoutInfoDesc')

    send_notification_to_device(
        user.fcm_token,
        title=title,
        body=body
    )
    
    # Clear session data from database
    try:
        with get_db_connection() as connection:
            cursor = connection.cursor()
            query = f"""
            UPDATE {table_name}
            SET app_session_id = NULL, 
                app_token = NULL
            WHERE user_hash = %s
            """
            cursor.execute(query, (user.user_hash,))
            connection.commit()
            logger.success(f"Cleared session data for user {user.user_hash[:4]}****")

    except Exception as e:
        logger.error(f"Failed to clear session data for user {user.user_hash[:4]}****: {e}")
        sentry_sdk.capture_exception(e)
    
    logger.info(f"Informed user {user.user_hash[4:]}**** about error that needed relogin")

async def lesson_check(user):
    """Check for upcoming lessons and send notifications"""
    today = datetime.now(user.timezone_obj).date()
    #other_day = today + timedelta(days=0)  # DEBUG
    
    # Reset the message printed flag if it's a new day
    current_date = datetime.now(user.timezone_obj).date()
    if user.last_check_date != current_date:
        user.class_message_printed_today = False
        user.last_check_date = current_date
    
    # Function to fetch lessons from Pronote
    async def fetch_lessons(user_obj):  # Accept user parameter
        return user_obj.client.lessons(date_from=today) #DEBUG (Switch to 'today' in prod)
    
    try:
        lessons = await retry_with_backoff(fetch_lessons, user)
        
        if not lessons:
            if not user.class_message_printed_today:
                logger.debug(f"No lessons found for user {user.user_hash} today")
                user.class_message_printed_today = True
            return
        
        current_time = datetime.now(user.timezone_obj).strftime("%H:%M")
        #logger.debug("Real Time: " + current_time) #DEBUG

        #fake_current_time = datetime.combine(other_day, dt_time(10, 15)) - timedelta(minutes=0) #DEBUG
        #logger.debug(f"Fake time: {fake_current_time}") #DEBUG

        lessons_by_time = {}
        for lesson in lessons:
            start_time = lesson.start.strftime("%H:%M")

            if (start_time not in lessons_by_time):
                lessons_by_time[start_time] = []
            lessons_by_time[start_time].append(lesson)

        # Process each time slot only once
        for start_time, lessons in lessons_by_time.items():
            lesson_start = datetime.strptime(start_time, "%H:%M").time()
            time_before_start = (datetime.combine(today, lesson_start) - timedelta(minutes=int(user.notification_delay))).time()

            #if fake_current_time.time() == time_before_start: # DEBUG
            if current_time == time_before_start.strftime("%H:%M"):
                if len(lessons) > 1:
                    #logger.debug(f"Multiple subjects: {len(lessons)}")
                    lesson_checks = max(lessons, key=lambda lesson: lesson.num)
                else:
                    lesson_checks = lessons[0]

                global subject
                subject = lesson_checks.subject.name         
                room_name = lesson_checks.classroom
                class_start_time = lesson_checks.start.strftime("%H:%M")
                canceled = lesson_checks.canceled
                status = lesson_checks.status
                num = lesson_checks.num

                #logger.debug("Debug Data : " + str(subject) + " " + str(room_name) + " " + str(class_start_time) + " " + str(canceled) + " " + str(status) + " " + str(num))

                # Load JSON data from files
                emoji_path = os.path.join(data_dir, 'emoji_cours_names.json')
                subject_path = os.path.join(data_dir, 'subject_names_format.json')

                try:
                    async with aiofiles.open(emoji_path, 'r', encoding='utf-8') as emojis_data, aiofiles.open(subject_path, 'r', encoding='utf-8') as subjects_data:
                        emojis = json.loads(await emojis_data.read())
                        subjects = json.loads(await subjects_data.read())
                        
                except (FileNotFoundError, json.JSONDecodeError) as e:
                    logger.error(f"Failed to load JSON files for user {user.user_hash}: {e}")
                    sentry_sdk.capture_exception(e)
                    emojis = {}
                    subjects = {}

                global lower_cap_subject_name
                lower_cap_subject_name = subject[0].capitalize() + subject[1:].lower()

                # Normalize function to simplify comparison
                def normalize(text:str) -> str:
                    """
                    Normalize a text string for comparison
                    """
                    
                    return text.lower().replace(' ', '').replace('-', '').replace('.', '').replace('é', 'e')

                # Create a dictionary of normalized short names to emojis
                normalized_emojis = {
                    normalize(name): (emoji if isinstance(emoji, list) else [emoji])
                    for name, emoji in emojis.items()
                }

                # Create a dictionary of normalized subject names
                normalized_subjects = {
                    normalize(key): details
                    for key, details in subjects.items()
                }

                # Normalize lower_cap_subject_name for comparison
                normalized_subject_key = normalize(lower_cap_subject_name)

                # Find subject details from the subjects JSON
                if normalized_subject_key in normalized_subjects:
                    subject_details = normalized_subjects[normalized_subject_key]
                    name = subject_details["name"]

                    if user.lang == "es":
                        det = "de"

                    else:
                        det = subject_details["det"] #french
                else:
                    name = lower_cap_subject_name
                    det = ":"  # default caracter if not found

                # Find matching emoji using the better subject name
                found_emoji_list = ['📝']  # Default emoji if no match is found
                normalized_name_key = normalize(name)
                for short_name, emoji_list in normalized_emojis.items():
                    # Use word boundary check or exact match
                    if (short_name in normalized_name_key or normalized_name_key == short_name):
                        #logger.debug(f"Debug Data : {name} {short_name} {emoji_list}")
                        found_emoji_list = emoji_list
                        break

                # Randomly choose an emoji from the matched emoji list
                chosen_emoji = random.choice(found_emoji_list)

                if det == "de" or det ==":":
                    extra_space = " "
                else:
                    extra_space = ""

                lang = user.lang
                
                if canceled:
                    # Send notification for canceled lesson
                    title = get_i18n_value(lang, 'notification.cancelledClassTitle')
                    body = get_i18n_value(lang, 'notification.cancelledClassBody',
                        det=det,
                        extra_space=extra_space,
                        name=name,
                        class_start_time=class_start_time
                    )
                    send_notification_to_device(
                        user.fcm_token,
                        title=title,
                        body=body,
                    )
                    logger.success(f"Sent cancellation notification to user {user.user_hash}")

                elif not canceled:
                    # S grammar for minutes
                    s = "" if int(user.notification_delay) == 1 else "s"
                    delay = user.notification_delay
                    
                    if room_name is None:
                        class_time_message = get_i18n_value(lang, 'notification.classTimeNoRoomMessageDesc',
                            det=det,
                            extra_space=extra_space,
                            name=name,
                            class_start_time=class_start_time,
                            chosen_emoji=chosen_emoji
                        )
                    else:  
                        class_time_message = get_i18n_value(lang, 'notification.classTimeRoomMessageDesc',
                            det=det,
                            extra_space=extra_space,
                            name=name,
                            room_name=room_name,
                            class_start_time=class_start_time,
                            chosen_emoji=chosen_emoji
                        )

                    title = get_i18n_value(lang, 'notification.classTimeMessageTitle',
                        delay=delay,
                        s=s
                    )

                    send_notification_to_device( 
                        user.fcm_token,
                        title=title,
                        body=class_time_message,
                    ) #Send notification using Firebase
                    logger.success(f"Sent lesson notification to user {user.user_hash}")
        
    except Exception as e:
        logger.error(f"Error checking lessons for user {user.user_hash}: {e}")
        sentry_sdk.capture_exception(e)

async def fetch_saved_menus(user, date):
    """Try to fetch saved menus from db"""

    school_name = user.student_school_name

    try:
        with get_db_connection() as connection:
            cursor = connection.cursor(dictionary=True)
            query = f"""
            SELECT menu_content
            FROM {get_secret('DB_MENUS_TABLE_NAME')}
            WHERE school_name = %s AND day = %s
            """
            cursor.execute(query, (school_name, date))
            result = cursor.fetchone()
            
            if result:
                logger.debug(result)
                logger.info(f"Fetched saved menus for user {user.user_hash[:4]}*** on {date}")
                return result['menu_content']
            else:
                logger.info(f"No saved menus found for user {user.user_hash[:4]}*** on {date}")
                return None
                
    except Exception as e:
        logger.error(f"Error fetching saved menus for user {user.user_hash[:4]}***: {e}")
        sentry_sdk.capture_exception(e)
        return None



async def menu_food_check(user):
    """Check for upcoming menus and send notifications"""
    today = datetime.now(user.timezone_obj).date()
    
    # Reset the message printed flag if it's a new day
    current_date = datetime.now(user.timezone_obj).date()
    if user.last_check_date != current_date:
        user.menu_message_printed_today = False
        user.last_check_date = current_date
    
    # Skip if evening or lunch menu is disabled
    if not user.evening_menu and not user.lunch_menu:
        return
    
    # Function to fetch menus from Pronote
    async def fetch_menus(user_obj):  # Accept user parameter
        return user_obj.client.menus(date_from=today, date_to=today)
    
    try:
        menus = await retry_with_backoff(fetch_menus, user)

        if not menus:
            if not user.menu_message_printed_today:
                logger.debug(f"No menus found for user {user.user_hash[:4]}**** today, checking saved menus...")

                fetched_menus = await fetch_saved_menus(user, today)
                user.menu_message_printed_today = True
            return
        
        current_time = datetime.now(user.timezone_obj).time()
        
        # Check for lunch time (user-specific lunch times)
        day_str = today.strftime('%A').lower()
        lunch_time = user.lunch_times.get(day_str)
        
        dinner_time = None
        
        if lunch_time is not None:
            lunch_hour, lunch_minute = lunch_time
            
            if current_time.hour == lunch_hour and current_time.minute == lunch_minute and user.lunch_menu:
                logger.info(f"Lunch time for user {user.user_hash[:4]}**** ! ({today.strftime('%A')} {lunch_hour:02d}:{lunch_minute:02d})")
                dinner_time = False
                await send_menu_notification(user, menus, dinner_time)
        
        # Check for dinner time at 18:55 if evening menu is enabled
        if current_time.hour == 18 and current_time.minute == 55 and user.evening_menu:
            logger.info(f"Dinner time for user {user.user_hash[:4]}**** ! ({today.strftime('%A')} 18:55)")
            dinner_time = True
            await send_menu_notification(user, menus, dinner_time)
        
    except Exception as e:
        logger.error(f"Error checking menus for user {user.user_hash[:4]}**** : {e}")
        sentry_sdk.capture_exception(e)

async def send_menu_notification(user, menus, dinner_time):
    """Send menu notifications to user"""
    
    def format_menu(menu_items) -> dict:
        """Format the menu items for notification"""
        
        def extract_relevant_item(item_string) -> str:
            """Extract the relevant item from a string or list of items"""
            # Handle both string and list inputs
            if isinstance(item_string, str):
                items = [elem.strip() for elem in item_string.split(',')]
            elif isinstance(item_string, list):
                items = [str(elem).strip() for elem in item_string]
            else:
                items = []

            # Heuristic to determine main dish
            def is_main_dish(item: str) -> bool:
                """Determine if an item is a main dish"""
                # Exclude items containing certain keywords or being very short
                if len(item.split()) <= 2:  # Generally, main dishes have few words
                    return True
                if "de" in item.lower():  # Avoid phrases with "de"
                    return False
                return True

            # Handle the case where items might be Menu.Food objects
            if isinstance(item_string, list):
                formatted_items = []
                for item in item_string:
                    if hasattr(item, 'name'):  # Check if it's a Menu.Food object with a name attribute
                        formatted_items.append(str(item.name))
                    else:
                        formatted_items.append(str(item))
                items = formatted_items
            
            main_dishes = [item for item in items if is_main_dish(item)]

            # If no main dish is detected, return everything to avoid data loss
            return ', '.join(main_dishes) if main_dishes else ', '.join(items)

        def get_menu_items(items) -> str:
            """Get the menu items for a category"""
            if not items:
                return ''
            # Apply extraction to strings of each category
            return extract_relevant_item(items)

        return {
            'first_meal': get_menu_items(menu_items.first_meal),
            'main_meal': get_menu_items(menu_items.main_meal),
            'side_meal': get_menu_items(menu_items.side_meal),
            'dessert': get_menu_items(menu_items.dessert),
        }

    lang = user.lang
    
    for menu in menus:
        if dinner_time is False and menu.is_lunch:
            # Format lunch menu items
            menu_items = format_menu(menu)

            if all(menu_items.values()):  # Check that all categories are present
                title = get_i18n_value(lang, 'notification.lunchTimeLunchTitle')
                body = get_i18n_value(lang, 'notification.lunchTimeLunchDesc',
                    menu_items=menu_items
                )

                send_notification_to_device(
                    user.fcm_token,
                    title=title,
                    body=body,
                )
                logger.success(f"Sent lunch menu notification to user {user.user_hash}")
            else:
                logger.warning(f"Incomplete lunch menu for {menu.date} for user {user.user_hash}. Skipping notification.")

        elif dinner_time is True and menu.is_dinner:
            # Format dinner menu items
            menu_items = format_menu(menu)

            if all(menu_items.values()):  # Check that all categories are present
                title = get_i18n_value(lang, 'notification.lunchTimeEveningTitle')
                body = get_i18n_value(lang, 'notification.lunchTimeEveningDesc',
                    menu_items=menu_items
                )

                send_notification_to_device(
                    user.fcm_token,
                    title=title,
                    body=body,
                )
                logger.success(f"Sent dinner menu notification to user {user.user_hash}")
            else:
                logger.warning(f"Incomplete dinner menu for {menu.date} for user {user.user_hash}. Skipping notification.")

async def check_reminder_notifications(user):
    """Check for homework and bag reminders"""
    # Skip if reminders are disabled
    if not user.unfinished_homework_reminder and not user.get_bag_ready_reminder:
        return
    
    current_time = datetime.now(user.timezone_obj).time()
    tomorrow_date = (datetime.now(user.timezone_obj) + timedelta(days=1)).date()

    unfinished_homework_reminder_time = user.unfinished_homework_reminder_time
    bag_ready_reminder_time = user.get_bag_ready_reminder_time

    try:
        #Helper function to convert timedelta to time object
        def timedelta_to_time(td):
            """Convert timedelta to time object"""
            if isinstance(td, timedelta):
                total_seconds = int(td.total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                return dt_time(hours, minutes)
            return td

        # Check if there are classes tomorrow
        class_checker = []
        for attempt in range(5):  # max_retries
            try:
                class_checker = user.client.lessons(date_from=tomorrow_date)
                break
            except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError) as e:
                if attempt < 4:  # max_retries - 1
                    logger.warning(f"Connection timeout during lesson check for user {user.user_hash[:4]}**** (attempt {attempt + 1}/5). Retrying in 3 seconds...")
                    await asyncio.sleep(3 * (2 ** attempt))
                else:
                    logger.error(f"Failed to check lessons after 5 attempts for user {user.user_hash[:4]}****: {e}")
                    sentry_sdk.capture_exception(e)
                    class_checker = []

            except Exception as e:
                logger.error(f"Unexpected error checking lessons for user {user.user_hash[:4]}****: {e}")
                if not await user.handle_error_with_relogin(e):
                    return
                class_checker = []
                break

        class_tomorrow = bool(class_checker)

        #Convert timedelta to time object for comparison
        bag_reminder_time = timedelta_to_time(bag_ready_reminder_time)
        homework_reminder_time = timedelta_to_time(unfinished_homework_reminder_time)

        # Bag ready reminder at defined time (HH:MM)
        #if -> current time matches reminder time and setting is enabled and there are classes tomorrow

        if (current_time.hour == bag_reminder_time.hour and current_time.minute == bag_reminder_time.minute and user.get_bag_ready_reminder and class_tomorrow):
            lang = user.lang
            
            title = get_i18n_value(lang, 'notification.getBagReadyTitle')
            body = get_i18n_value(lang, 'notification.getBagReadyDesc')
            
            send_notification_to_device(
                user.fcm_token,
                title=title,
                body=body,
            )
            logger.success(f"Sent bag ready reminder to user {user.user_hash[:4]}**** !")

        # Homework reminder at defined time (HH:MM)
        #if -> current time matches reminder time and setting is enabled and there are classes tomorrow

        if (current_time.hour == homework_reminder_time.hour and current_time.minute == homework_reminder_time.minute and user.unfinished_homework_reminder and class_tomorrow):
            
            try:
                homeworks = user.client.homework(tomorrow_date, tomorrow_date)
                not_finished_homeworks_count = 0
                
                if not homeworks:
                    logger.debug(f"No homeworks found for tomorrow for user {user.user_hash[:4]}****")
                    not_finished_homeworks_count = -1 # No homeworks means no unfinished ones so score is -1
                else:
                    # Count unfinished homework
                    for homework in homeworks:
                        if not homework.done:
                            not_finished_homeworks_count += 1
                
                # Set reminder message based on homework completion status
                lang = user.lang

                if not_finished_homeworks_count == -1:
                    pass #Do not send notification if no homework was found
                
                else:
                    if not_finished_homeworks_count == 0:
                        title = get_i18n_value(lang, 'notification.noUnfinishedHomeworkTitle')
                        body = get_i18n_value(lang, 'notification.noUnfinishedHomeworkDesc')

                    elif not_finished_homeworks_count > 1:
                        title = get_i18n_value(lang, 'notification.unfinishedHomeworkTitle')
                        body = get_i18n_value(lang, 'notification.unfinishedHomeworkDesc',
                            not_finished_homeworks_count=not_finished_homeworks_count
                        )

                    elif not_finished_homeworks_count == 1:
                        title = get_i18n_value(lang, 'notification.singleUnfinishedHomeworkTitle')
                        body = get_i18n_value(lang, 'notification.singleUnfinishedHomeworkDesc')

                    send_notification_to_device(
                        user.fcm_token,
                        title=title,
                        body=body,
                    )
                    logger.success(f"Sent homework reminder to user {user.user_hash[:4]}**** !")
                
            except Exception as homework_error:
                logger.error(f"Error checking homework for user {user.user_hash}: {homework_error}")
                sentry_sdk.capture_exception(homework_error)

    except Exception as e:
        logger.error(f"Error in reminder check for user {user.user_hash[:4]}****: {e}")
        sentry_sdk.capture_exception(e)

async def main():
    """Main function to run the multi-user system"""
    # Check internet connection
    if not await check_internet_connection():
        logger.critical("No internet connection! Program will close in 2 seconds...")
        await asyncio.sleep(2)
        sys.exit(1)
        
    # Initial user loading
    users = await load_active_users()
    if not users:
        logger.critical("No active users found! Program will close in 2 seconds...")
        await asyncio.sleep(2)
        sys.exit(1)


    #Initialize i18n
    global fr_file, en_file, es_file
    
    try:
        web_dir = os.path.join(os.path.dirname(server_dir), 'Web')
        locales_dir = os.path.join(web_dir, 'locales')
        
        with open(os.path.join(locales_dir, 'fr.json'), 'r', encoding='utf-8') as f:
            fr_file = json.load(f)
        
        with open(os.path.join(locales_dir, 'en.json'), 'r', encoding='utf-8') as f:
            en_file = json.load(f)
        
        with open(os.path.join(locales_dir, 'es.json'), 'r', encoding='utf-8') as f:
            es_file = json.load(f)
        
        logger.success("Loaded i18n translation files from Web/locales successfully")

    except FileNotFoundError as e:
        logger.error(f"Failed to load i18n files from Web/locales: {e}")
        sentry_sdk.capture_exception(e)
        sys.exit(1)
    
    # Start user processing tasks
    user_tasks = {}
    for user in users:
        task = asyncio.create_task(user_process_loop(user))
        user_tasks[user.user_hash] = task  # Use user_hash as key
    
    # Periodically check for new/updated/removed users
    while True:
        await asyncio.sleep(5 * 60)  # Check every 5 minutes
        
        try:
            current_users = await load_active_users()
            current_user_hashes = {user.user_hash for user in current_users}
            existing_user_hashes = set(user_tasks.keys())
            
            # Add new users
            for user in current_users:
                if user.user_hash not in existing_user_hashes:
                    logger.info(f"Adding new user: {user.user_hash}")
                    task = asyncio.create_task(user_process_loop(user))
                    user_tasks[user.user_hash] = task
            
            # Remove users that are no longer active
            for user_id in existing_user_hashes - current_user_hashes:
                logger.info(f"Removing user: {user_id}")
                task = user_tasks.pop(user_id)
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                    
        except Exception as e:
            logger.error(f"Error updating user list: {e}")
            sentry_sdk.capture_exception(e)

if __name__ == "__main__":
    asyncio.run(main())