import asyncio
import os
import time
from loguru import logger
import sentry_sdk
from sentry_sdk import logger as sentry_logger
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
from dotenv import load_dotenv
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from modules.pronote.users import PronotifUser
from modules.messaging.firebase import send_notification_to_device

# Initialize Sentry
ignore_errors = [KeyboardInterrupt]
sentry_sdk.init(
    "https://8c5e5e92f5e18135e5c89280db44a056@o4508253449224192.ingest.de.sentry.io/4508253458726992", 
    enable_tracing=True,
    traces_sample_rate=1.0,
    environment="production",
    release="v0.9",
    server_name="Server",
    ignore_errors=ignore_errors,
     _experiments={
        "enable_logs": True,
    },

)

load_dotenv() # Load environment variables

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
    "host": os.getenv('DB_HOST'),
    "user": os.getenv('DB_USER'),
    "password": os.getenv('DB_PASSWORD'),
    "database": os.getenv('DB_NAME')
}
table_name = os.getenv('DB_STUDENT_TABLE_NAME')

# Connection pool configuration
DB_POOL_CONFIG = {
    "pool_name": "client_pool",
    "pool_size": int(os.getenv('DB_POOL_SIZE', '10')),
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

async def load_active_users() -> list:
    """Load all active users from the database using connection pooling"""
    global _previous_user_hashes, _existing_users
    users = []
    
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

async def user_process_loop(user:PronotifUser) -> None: 
    """Handle all checks and notifications for a single user with staggered timing"""
    try:
        # Login
        if not await user.login():
            logger.error(f"Failed to login user {user.user_hash}, skipping...")
            return
            
        no_internet_message = False
        instance_not_reachable_message = False
        
        # Add staggering based on user_hash
        user_offset = hash(user.user_hash) % 30  # 0-29 second offset
        logger.debug(f"User {user.user_hash} assigned offset of {user_offset} seconds")
        await asyncio.sleep(user_offset)  # Initial delay to distribute users
        
        while True:
            start_time = time.time()
            
            # Check connectivity
            internet_available = await check_internet_connection()
            server_reachable = await user.check_pronote_server() if internet_available else False
            
            if internet_available and server_reachable:
                if no_internet_message or instance_not_reachable_message:
                    logger.info(f"Connectivity restored for user {user.user_hash}")
                    no_internet_message = False
                    instance_not_reachable_message = False
                
                # Check session and perform all checks
                await user.check_session()
                
                # Run all notification checks in parallel
                await asyncio.gather(
                    lesson_check(user), 
                    menu_food_check(user), 
                    check_reminder_notifications(user)
                )
                
            else:
                if not no_internet_message and not instance_not_reachable_message:
                    logger.warning(f"Tasks paused for user {user.user_hash} - No internet or server unreachable")
                    no_internet_message = True
                    instance_not_reachable_message = True
            
            # Calculate time to next check with staggering
            current_seconds = datetime.now().second
            sleep_time = ((60 - current_seconds) + user_offset) % 60 or 60  # User's offset
            await asyncio.sleep(sleep_time)
            
    except Exception as e:
        logger.critical(f"Critical error in user loop for {user.user_hash}: {e}")
        sentry_sdk.capture_exception(e)

async def retry_with_backoff(func, user, *args, max_attempts=5) -> None:
    """Retry a function with exponential backoff"""
    timeout_incident_id = None
    
    for attempt in range(max_attempts):
        try:
            result = await func(user, *args)
            
            # If previously reported a timeout and now succeeded, mark it as resolved
            if timeout_incident_id:
                with sentry_sdk.new_scope() as scope:
                    scope.set_tag("status", "resolved")
                    scope.set_tag("user_id", user.user_hash)
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
                requests.exceptions.ConnectionError) as e:
            
            wait_time = 3 * (2 ** attempt)
            
            # On first timeout, create an incident in Sentry
            if attempt == 0:
                with sentry_sdk.new_scope() as scope:
                    scope.set_tag("error_type", "timeout")
                    scope.set_tag("function", func.__name__)
                    scope.set_tag("status", "ongoing")
                    scope.set_tag("user_id", user.user_hash)
                    timeout_incident_id = sentry_sdk.capture_message(
                        f"Timeout occurred in {func.__name__} for user {user.user_hash}",
                        level="error"
                    )
            
            if attempt == max_attempts - 1:
                # Update the incident
                with sentry_sdk.new_scope() as scope:
                    scope.set_tag("error_type", "timeout")
                    scope.set_tag("function", func.__name__)
                    scope.set_tag("status", "failed")
                    scope.set_tag("total_retries", str(max_attempts))
                    scope.set_tag("user_id", user.user_hash)
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
        return user_obj.client.lessons(date_from=today)
    
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

                async with aiofiles.open(emoji_path, 'r', encoding='utf-8') as emojis_data, aiofiles.open(subject_path, 'r', encoding='utf-8') as subjects_data:
                    emojis = json.loads(await emojis_data.read())
                    subjects = json.loads(await subjects_data.read())

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
                    det = subject_details["det"]
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

                if canceled:
                    # Send notification for canceled lesson
                    send_notification_to_device(
                        user.fcm_token,
                        title=f"❌ Cours annulé !",
                        body=f"Le cours {det}{extra_space}{name} initialement prévu à {class_start_time} est annulé.",
                    )
                    logger.success(f"Sent cancellation notification to user {user.user_hash}")

                elif not canceled:
                    if room_name is None:
                        class_time_message = f"Le cours {det}{extra_space}{name} commencera à {class_start_time}. {chosen_emoji}"

                    else:  
                        class_time_message = f"Le cours {det}{extra_space}{name} se fera en salle {room_name} et commencera à {class_start_time}. {chosen_emoji}"

                    #logger.debug(class_time_message)
        
                    # S grammar
                    s = "" if int(user.notification_delay) == 1 else "s"
                    title = f"🔔 Prochain cours dans {user.notification_delay} minute{s} !"

                    send_notification_to_device( 
                        user.fcm_token,
                        title=title,
                        body=f"{class_time_message}",
                    ) #Send notification using Firebase
                    logger.success(f"Sent lesson notification to user {user.user_hash}")
        
    except Exception as e:
        logger.error(f"Error checking lessons for user {user.user_hash}: {e}")
        sentry_sdk.capture_exception(e)

async def menu_food_check(user):
    """Check for upcoming menus and send notifications"""
    today = datetime.now(user.timezone_obj).date()
    
    # Reset the message printed flag if it's a new day
    current_date = datetime.now(user.timezone_obj).date()
    if user.last_check_date != current_date:
        user.menu_message_printed_today = False
        user.last_check_date = current_date
    
    # Skip if evening_menu is disabled
    if not user.evening_menu:
        return
    
    # Function to fetch menus from Pronote
    async def fetch_menus(user_obj):  # Accept user parameter
        return user_obj.client.menus(date_from=today, date_to=today)
    
    try:
        menus = await retry_with_backoff(fetch_menus, user)
        logger.info(menus)
        for menu in menus:
            logger.info(f"Menu found for user {user.user_hash}: {menu}")

        if not menus:
            if not user.menu_message_printed_today:
                logger.info(f"No menus found for user {user.user_hash} today")
                user.menu_message_printed_today = True
            return
        
        #TODO: Process menus and send notifications
        
    except Exception as e:
        logger.error(f"Error checking menus for user {user.user_hash}: {e}")
        sentry_sdk.capture_exception(e)

async def check_reminder_notifications(user):
    """Check for homework and bag reminders"""
    # Skip if reminders are disabled
    if not user.unfinished_homework_reminder and not user.get_bag_ready_reminder:
        return
    
    today = datetime.now(user.timezone_obj).date()
    
    # Implementation for homework reminders
    if user.unfinished_homework_reminder:
        pass  # TODO: Implement homework reminder logic
    
    # Implementation for "get bag ready" reminder
    if user.get_bag_ready_reminder:
        pass  # TODO: Implement "get bag ready" reminder logic

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