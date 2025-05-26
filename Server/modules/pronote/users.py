import pronotepy
import os
import asyncio
from loguru import logger
import sentry_sdk
import requests
from datetime import datetime
import aiohttp
import pytz
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from modules.security.encryption import decrypt

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
)

table_name = os.getenv('DB_STUDENT_TABLE_NAME')

class PronotifUser:
    def __init__(self, user_data):
        """Initialize user with data from database row"""
        # Core identifiers
        self.app_session_id = user_data['app_session_id']
        self.app_token = user_data.get('app_token')
        self.user_hash = user_data.get('user_hash')
        
        # Client connection
        self.client = None
        self.first_login = True
        
        # Student info
        self.student_fullname = user_data.get('student_fullname')
        self.student_firstname = user_data.get('student_firstname')
        self.student_class = user_data.get('student_class')
        
        # Credentials (encrypted)
        self.username = decrypt(user_data.get('student_username', ''))
        self.password = decrypt(user_data.get('student_password', ''))
        
        # Connection settings
        self.login_page_link = decrypt(user_data.get('login_page_link', ''))
        self.uuid = user_data.get('uuid')
        self.qr_code_login = bool(user_data.get('qr_code_login', 0))
        self.ent_used = bool(user_data.get('ent_used', 0))
        
        # Notification settings
        self.notification_delay = user_data.get('notification_delay', 5)
        self.fcm_token = user_data.get('fcm_token')
        
        # Time settings
        self.timezone = user_data.get('timezone', 'Europe/Paris')
        self.timezone_obj = pytz.timezone(self.timezone)
        
        # Lunch time
        self.lunch_times = {
            'monday': user_data.get('monday_lunch'),
            'tuesday': user_data.get('tuesday_lunch'),
            'wednesday': user_data.get('wednesday_lunch'),
            'thursday': user_data.get('thursday_lunch'),
            'friday': user_data.get('friday_lunch')
        }
        
        # Feature flags
        self.evening_menu = bool(user_data.get('evening_menu', 0))
        self.unfinished_homework_reminder = bool(user_data.get('unfinished_homework_reminder', 0))
        self.get_bag_ready_reminder = bool(user_data.get('get_bag_ready_reminder', 0))
        
        # Status tracking
        self.is_active = bool(user_data.get('is_active', 0))
        self.last_check_date = None
        self.class_message_printed_today = False
        self.menu_message_printed_today = False
        
        logger.debug(f"Initialized user {self.user_hash}")
    
    async def login(self) -> bool:
        """Attempt to log in to Pronote with user credentials"""
        try:
            if self.qr_code_login:
                self.client = pronotepy.Client.token_login(
                    self.login_page_link, 
                    username=self.username, 
                    password=self.password,
                    uuid=self.uuid
                )
            else:
                self.client = pronotepy.Client(
                    self.login_page_link, 
                    username=self.username, 
                    password=self.password
                )
                
            if self.client.logged_in:
                logger.success(f"User {self.user_hash} successfully logged in!")
                if self.qr_code_login:
                    # Update password for future logins
                    await self._save_password()
                return True
            else:
                logger.error(f"Failed to log in user {self.user_hash}")
                return False
                
        except Exception as e:
            logger.error(f"Login error for user {self.user_hash} : {e}")
            sentry_sdk.capture_exception(e)
            return False
            
    async def _save_password(self, db_connection=None) -> None:
        """Save updated token password to database"""
        from modules.security.encryption import encrypt
        from app import get_db_connection
        
        close_connection = False
        try:
            # If no connection provided, get one
            if not db_connection:
                db_connection = get_db_connection()
                close_connection = True
                
            cursor = db_connection.cursor()
            
            # Encrypt the new password
            encrypted_password = encrypt(self.client.password)
            
            # Update in database
            query = f"""
            UPDATE {table_name}
            SET student_password = %s, token_updated_at = NOW()
            WHERE app_session_id = %s AND is_active = 1
            """
            cursor.execute(query, (encrypted_password, self.app_session_id))
            db_connection.commit()
            
            if cursor.rowcount > 0:
                logger.success(f"Updated token password for user {self.user_hash}")
            else:
                logger.warning(f"Failed to update token password for user {self.user_hash}")
                
        except Exception as e:
            logger.error(f"Error saving new password for user {self.user_hash}: {e}")
            sentry_sdk.capture_exception(e)
        
        finally:
            if close_connection and db_connection:
                db_connection.close()
        
    async def check_session(self) -> None:
        """Check and refresh user's session if needed"""
        if self.first_login:
            self.first_login = False
            return
            
        try:
            if self.client.session_check():
                logger.warning(f"Session expired for user {self.user_hash} !")
                
                if self.qr_code_login:
                    # Reload user data to get fresh password if it was updated elsewhere
                    self.password = await self._reload_password()
                    
                    self.client = pronotepy.Client.token_login(
                        self.login_page_link, 
                        username=self.username, 
                        password=self.password,
                        uuid=self.uuid
                    )
                    
                    if self.client.logged_in:
                        logger.success(f"New session created for user {self.user_hash}")
                        await self._save_password()
                else:
                    self.client.refresh()
                    logger.success(f"Session refreshed for user {self.user_hash}")
                    
        except Exception as e:
            logger.error(f"Session check failed for user {self.user_hash}: {e}")
            await self.handle_error_with_relogin(e)
    
    async def _reload_password(self) -> str:
        """Reload password from database"""
        from app import get_db_connection
        
        connection = None
        try:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)
            
            query = f"""
            SELECT student_password
            FROM {table_name}
            WHERE app_session_id = %s AND is_active = 1
            """
            cursor.execute(query, (self.app_session_id,))
            result = cursor.fetchone()
            
            if result:
                return decrypt(result['student_password'])
            else:
                logger.error(f"User {self.app_session_id} not found in database or not active")
                return self.password  # Current password as fallback
                
        except Exception as e:
            logger.error(f"Failed to reload password for user {self.user_hash}: {e}")
            sentry_sdk.capture_exception(e)
            return self.password  # Current password as fallback
            
        finally:
            if connection:
                connection.close()
            
    async def handle_error_with_relogin(self, error) -> bool:
        """Handle errors by attempting to relogin"""
        logger.error(f"Error for user {self.user_hash}: {error}. Attempting relogin...")
        
        for attempt in range(5):
            try:
                if attempt > 0:
                    wait_time = 5 * (2 ** attempt)
                    logger.info(f"Retry attempt {attempt+1}/5 for user {self.user_hash} after waiting {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                    
                # Check if server is reachable
                if not await self.check_pronote_server():
                    logger.warning(f"Pronote server unreachable for user {self.user_hash} (attempt {attempt+1}/5)")
                    continue
                    
                # Attempt relogin
                if await self.login():
                    return True
                    
            except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectTimeout, 
                    requests.exceptions.ConnectionError) as e:
                logger.warning(f"Connection error during relogin for user {self.user_hash}: {e}")
                
            except Exception as e:
                logger.critical(f"Failed relogin for user {self.user_hash}: {e}")
                sentry_sdk.capture_exception(e)
                
        logger.error(f"All relogin attempts failed for user {self.user_hash}")
        return False
        
    async def check_pronote_server(self) -> bool:
        """Check if Pronote server is reachable"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.login_page_link, timeout=20) as resp:
                    return resp.status == 200
        except (aiohttp.ClientError, asyncio.TimeoutError, aiohttp.ServerTimeoutError) as e:
            logger.warning(f"Pronote server check failed for {self.user_hash}: {e}")
            return False
        
        except Exception as e:
            logger.error(f"Unexpected error checking Pronote server for {self.user_hash}: {e}")
            return False
    
    def update_from_db(self, user_data) -> None:
        """Update user with fresh data from database without reinitializing"""
        changes_made = False
        
        # Update core identifiers if needed
        if user_data.get('app_token') != self.app_token:
            self.app_token = user_data.get('app_token', self.app_token)
            changes_made = True
        
        # Update student info
        if user_data.get('student_fullname') != self.student_fullname:
            self.student_fullname = user_data.get('student_fullname')
            changes_made = True
        
        if user_data.get('student_firstname') != self.student_firstname:
            self.student_firstname = user_data.get('student_firstname')
            changes_made = True
        
        if user_data.get('student_class') != self.student_class:
            self.student_class = user_data.get('student_class')
            changes_made = True
        
        # Update credentials if they've changed
        new_username = decrypt(user_data.get('student_username', ''))
        new_password = decrypt(user_data.get('student_password', ''))
        if new_username != self.username or new_password != self.password:
            self.username = new_username
            self.password = new_password
            # Force re-login on next check
            self.first_login = True
            changes_made = True
        
        # Update connection settings
        new_login_page_link = decrypt(user_data.get('login_page_link', ''))
        if new_login_page_link != self.login_page_link:
            self.login_page_link = new_login_page_link
            # Force re-login on next check
            self.first_login = True
            changes_made = True
        
        if user_data.get('uuid') != self.uuid:
            self.uuid = user_data.get('uuid', self.uuid)
            changes_made = True

        new_qr_code_login = bool(user_data.get('qr_code_login', 0))
        if new_qr_code_login != self.qr_code_login:
            self.qr_code_login = new_qr_code_login
            changes_made = True

        new_ent_used = bool(user_data.get('ent_used', 0))
        if new_ent_used != self.ent_used:
            self.ent_used = new_ent_used
            changes_made = True

        if user_data.get('notification_delay') != self.notification_delay:
            self.notification_delay = user_data.get('notification_delay', self.notification_delay)
            changes_made = True

        if user_data.get('fcm_token') != self.fcm_token:
            self.fcm_token = user_data.get('fcm_token', self.fcm_token)
            changes_made = True
        
        # Update time settings
        new_timezone = user_data.get('timezone', self.timezone)
        if new_timezone != self.timezone:
            self.timezone = new_timezone
            self.timezone_obj = pytz.timezone(self.timezone)
        
        # Update lunch times
        for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']:
            if user_data.get(f'{day}_lunch') != self.lunch_times.get(day):
                self.lunch_times[day] = user_data.get(f'{day}_lunch', self.lunch_times.get(day))
                changes_made = True
        
        # Update feature flags
        self.evening_menu = bool(user_data.get('evening_menu', self.evening_menu))
        self.unfinished_homework_reminder = bool(user_data.get('unfinished_homework_reminder', self.unfinished_homework_reminder))
        self.get_bag_ready_reminder = bool(user_data.get('get_bag_ready_reminder', self.get_bag_ready_reminder))
        
        
        # Only log if something changed
        if changes_made:
            logger.debug(f"Updated user {self.user_hash} from database")