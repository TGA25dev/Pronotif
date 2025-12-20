import pronotepy
import os
import asyncio
from loguru import logger
import requests
from datetime import datetime, timedelta
from datetime import time as dt_time
import aiohttp
import pytz
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from modules.security.encryption import decrypt

from ..login.temp_login.pronotepy_monlycee import ile_de_france
from ..pronote.id_creator import generate_id

# Initialize Sentry
from modules.sentry.sentry_config import sentry_sdk

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
        
        # Session refresh tracking
        self.session_refresh_count = 0
        self.refresh_timestamps = []
        self.max_refreshes_per_window = 5
        self.refresh_window_minutes = 30

        #Pronote API Suspension Tracking
        self.suspended_until = None
        
        # Student info
        self.student_fullname = user_data.get('student_fullname')
        self.student_firstname = user_data.get('student_firstname')
        self.student_class = user_data.get('student_class')
        self.student_school_name = None  #To be fetched after login and not stored in db
        
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
        
        # Time and region settings
        self.timezone = user_data.get('timezone', 'Europe/Paris')
        self.timezone_obj = pytz.timezone(self.timezone)
        self.region = decrypt(user_data.get("region"))
        self.lang = user_data.get("lang", "fr")
        
        # Lunch time
        self.lunch_times = {
            'monday': user_data.get('monday_lunch'),
            'tuesday': user_data.get('tuesday_lunch'),
            'wednesday': user_data.get('wednesday_lunch'),
            'thursday': user_data.get('thursday_lunch'),
            'friday': user_data.get('friday_lunch')
        }

        #Reminder Timings
        self.unfinished_homework_reminder_time = user_data.get('unfinished_homework_reminder_time', '18:00') #def to 18:00
        self.get_bag_ready_reminder_time = user_data.get('get_bag_ready_reminder_time', '20:00') #def to 20:00
        
        # Feature flags
        self.lunch_menu = bool(user_data.get('lunch_menu', 0))
        self.evening_menu = bool(user_data.get('evening_menu', 0))
        self.unfinished_homework_reminder = bool(user_data.get('unfinished_homework_reminder', 0))
        self.get_bag_ready_reminder = bool(user_data.get('get_bag_ready_reminder', 0))
        self.new_grade_notification = bool(user_data.get('new_grade_notification', 0))
        
        # Status tracking
        self.is_active = bool(user_data.get('is_active', 0))
        self.last_check_date = None
        self.class_message_printed_today = False
        self.menu_message_printed_today = False
        self.relogin_needed_notified = False
        
        logger.debug(f"Initialized user {self.user_hash[:4]}**** from database")
    
    def _should_force_relogin(self) -> bool:
        """Check if we should force a full relogin based on refresh frequency"""
        now = datetime.now(self.timezone_obj)
        
        # Remove timestamps older than the window
        cutoff_time = now - timedelta(minutes=self.refresh_window_minutes)
        self.refresh_timestamps = [ts for ts in self.refresh_timestamps if ts > cutoff_time]
        
        # Check if the refresh limit has been exceded
        return len(self.refresh_timestamps) >= self.max_refreshes_per_window
    
    def _record_session_refresh(self) -> None:
        """Record a session refresh timestamp"""
        now = datetime.now(self.timezone_obj)
        self.refresh_timestamps.append(now)
        self.session_refresh_count += 1
        
        logger.debug(f"Session refresh #{len(self.refresh_timestamps)} for user {self.user_hash[:4]}****"
                    f"in last {self.refresh_window_minutes} minutes")
    
    def _reset_refresh_counter(self) -> None:
        """Reset the refresh counter after successful relogin"""
        self.refresh_timestamps.clear()
        self.session_refresh_count = 0
        logger.debug(f"Reset session refresh counter for user {self.user_hash[:4]}****")

    def is_suspended(self) -> bool:
        """Return True if this user/session is currently suspended"""
        if not self.suspended_until:
            return False
        return datetime.now(self.timezone_obj) < self.suspended_until

    async def login(self) -> bool:
        """Attempt to log in to Pronote with user credentials"""
        try:
            #if suspended skip login attempt
            if self.is_suspended():
                logger.warning(f"Skipping login for user {self.user_hash[:4]}**** — suspended until {self.suspended_until}")
                return False
            
            if self.qr_code_login:
                self.client = pronotepy.Client.token_login(
                    self.login_page_link, 
                    username=self.username, 
                    password=self.password,
                    uuid=self.uuid
                )
            elif self.ent_used and self.region:
                if self.region == "Île-de-France" or self.region == "https://psn.monlycee.net":
                    self.client = pronotepy.Client(
                        self.login_page_link,
                        ent=ile_de_france,
                        username=self.username, 
                        password=self.password
                    )
            else:
                self.client = pronotepy.Client(
                    self.login_page_link, 
                    username=self.username, 
                    password=self.password
                )
                
            if self.client.logged_in:
                logger.success(f"User {self.user_hash[:4]}**** successfully logged in!")
                self.relogin_needed_notified = False
                self._reset_refresh_counter()  # Reset counter on successful login

                self.student_school_name = generate_id(self.client.info.establishment) if self.client.info.establishment else None
                if not self.student_school_name:
                    logger.warning(f"Could not fetch school name for user {self.user_hash[:4]}**** after login")

                if self.qr_code_login:
                    # Update password for future logins
                    await self._save_password()
                return True
            else:
                logger.error(f"Failed to log in user {self.user_hash[:4]}****")
                return False
                
        except Exception as e:
            msg = str(e).lower()
            # Detect suspended IP error and set a pause window
            if "suspended" in msg or "ip address is suspended" in msg:
                self.suspended_until = datetime.now(self.timezone_obj) + timedelta(minutes=10)
                logger.critical(f"Login error for user {self.user_hash[:4]}**** : {e} -- IP suspended. Pausing tasks until {self.suspended_until}")
                sentry_sdk.capture_message(f"IP suspended for user {self.user_hash}; paused until {self.suspended_until}")
                return False

            else:
                logger.error(f"Login error for user {self.user_hash[:4]}**** : {e}")

                if "page html is different than expected" in msg and not self.relogin_needed_notified:
                    from modules.pronote.notification_system import inform_user_relogin_is_needed #Prevents circular import by importing here
                    inform_user_relogin_is_needed(self)
                    self.relogin_needed_notified = True

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
                logger.success(f"Updated token password for user {self.user_hash[:4]}****")
            else:
                logger.warning(f"Failed to update token password for user {self.user_hash[:4]}****")
                
        except Exception as e:
            logger.error(f"Error saving new password for user {self.user_hash[:4]}**** : {e}")
            sentry_sdk.capture_exception(e)
        
        finally:
            if close_connection and db_connection:
                db_connection.close()
        
    async def check_session(self) -> None:
        """Check and refresh user's session if needed"""

        if self.is_suspended():
            logger.warning(f"Skipping session check for user {self.user_hash[:4]}****  suspended until {self.suspended_until}")
            return
    
        if self.first_login:
            self.first_login = False
            return
            
        try:
            # session_check() : returns True if session was refreshed
            was_refreshed = self.client.session_check()
            
            if was_refreshed:
                logger.info(f"Session was automatically refreshed for user {self.user_hash[:4]}****")
                self._record_session_refresh()
                self.relogin_needed_notified = False
                
                # For QR code users -> save the updated password
                if self.qr_code_login:
                    await self._save_password()
            
        except Exception as e:
            logger.error(f"Session check failed for user {self.user_hash[:4]}****: {e}")
            
            # Check if we should force a full relogin
            if self._should_force_relogin():
                logger.warning(f"User {self.user_hash} exceeded refresh limit. Forcing full relogin...")
                if await self.login():
                    logger.success(f"Forced relogin successful for user {self.user_hash[:4]}****")

                else:
                    logger.error(f"Forced relogin failed for user {self.user_hash[:4]}****")
            else:
                # Manual refresh
                try:
                    self.client.refresh()
                    logger.success(f"Manual refresh successful for user {self.user_hash[:4]}****")
                    self._record_session_refresh()

                    self.relogin_needed_notified = False
                    
                    if self.qr_code_login:
                        await self._save_password()
                        
                except Exception as refresh_error:
                    logger.error(f"Manual refresh failed for user {self.user_hash[:4]}**** : {refresh_error}")
                    await self.handle_error_with_relogin(refresh_error)
    
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
            logger.error(f"Failed to reload password for user {self.user_hash[:4]}**** : {e}")
            sentry_sdk.capture_exception(e)
            return self.password  # Current password as fallback
            
        finally:
            if connection:
                connection.close()
            
    async def handle_error_with_relogin(self, error) -> bool:
        """Handle errors by attempting to relogin"""
        logger.error(f"Error for user {self.user_hash[4:]}**** : {error}. Attempting relogin...")

        # If currently suspended, wait until suspension expires then try once
        if self.is_suspended():
            wait_seconds = (self.suspended_until - datetime.now(self.timezone_obj)).total_seconds()
            if wait_seconds > 0:
                logger.info(f"User {self.user_hash[:4]}**** suspended. Waiting {int(wait_seconds)}s before attempting relogin.")
                await asyncio.sleep(wait_seconds)

                self.suspended_until = None
        
        for attempt in range(5):
            try:
                if attempt > 0:
                    wait_time = 5 * (2 ** attempt)
                    logger.info(f"Retry attempt {attempt+1}/5 for user {self.user_hash[:4]}**** after waiting {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                    
                # Check if server is reachable
                if not await self.check_pronote_server():
                    logger.warning(f"Pronote server unreachable for user {self.user_hash[:4]}**** (attempt {attempt+1}/5)")
                    continue
                    
                # Attempt relogin
                if await self.login():
                    return True
                    
            except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectTimeout, 
                    requests.exceptions.ConnectionError) as e:
                logger.warning(f"Connection error during relogin for user {self.user_hash[:4]}**** : {e}")
                
            except Exception as e:
                logger.critical(f"Failed relogin for user {self.user_hash[:4]}**** : {e}")
                sentry_sdk.capture_exception(e)
                
        logger.error(f"All relogin attempts failed for user {self.user_hash[:4]}****")
        return False
        
    async def check_pronote_server(self) -> bool:
        """Check if Pronote server is reachable"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.login_page_link, timeout=20) as resp:
                    return resp.status == 200
        except (aiohttp.ClientError, asyncio.TimeoutError, aiohttp.ServerTimeoutError) as e:
            logger.warning(f"Pronote server check failed for {self.user_hash[:4]}**** : {e}")
            return False
        
        except Exception as e:
            logger.error(f"Unexpected error checking Pronote server for {self.user_hash[:4]}**** : {e}")
            return False
    
    def update_from_db(self, user_data) -> None:
        """Update user with fresh data from database without reinitializing"""
        changes_made = False
        changes = []  # List to track what changed

        if user_data.get('app_token') != self.app_token:
            self.app_token = user_data.get('app_token', self.app_token)
            changes_made = True
            changes.append('app_token')
        
        if user_data.get('app_session_id') != self.app_session_id:
            self.app_session_id = user_data.get('app_session_id', self.app_session_id)
            changes_made = True
            changes.append('app_session_id')
        
        if user_data.get('user_hash') != self.user_hash:
            self.user_hash = user_data.get('user_hash', self.user_hash)
            changes_made = True
            changes.append('user_hash')

        # Update student info
        if user_data.get('student_fullname') != self.student_fullname:
            self.student_fullname = user_data.get('student_fullname')
            changes_made = True
            changes.append('student_fullname')

        if user_data.get('student_firstname') != self.student_firstname:
            self.student_firstname = user_data.get('student_firstname')
            changes_made = True
            changes.append('student_firstname')

        if user_data.get('student_class') != self.student_class:
            self.student_class = user_data.get('student_class')
            changes_made = True
            changes.append('student_class')

        # Update credentials if they've changed
        new_username = decrypt(user_data.get('student_username', ''))
        new_password = decrypt(user_data.get('student_password', ''))
        if new_username != self.username or new_password != self.password:
            self.username = new_username
            self.password = new_password
            # Force re-login on next check
            self.first_login = True
            changes_made = True
            changes.append('credentials')

        # Update connection settings
        new_login_page_link = decrypt(user_data.get('login_page_link', ''))
        if new_login_page_link != self.login_page_link:
            self.login_page_link = new_login_page_link
            # Force re-login on next check
            self.first_login = True
            changes_made = True
            changes.append('login_page_link')

        if user_data.get('uuid') != self.uuid:
            self.uuid = user_data.get('uuid', self.uuid)
            changes_made = True
            changes.append('uuid')
        
        if user_data.get('lang') != self.lang:
            self.lang = user_data.get('lang', self.lang)
            changes_made = True
            changes.append('lang')

        new_qr_code_login = bool(user_data.get('qr_code_login', 0))
        if new_qr_code_login != self.qr_code_login:
            self.qr_code_login = new_qr_code_login
            changes_made = True
            changes.append('qr_code_login')

        new_ent_used = bool(user_data.get('ent_used', 0))
        if new_ent_used != self.ent_used:
            self.ent_used = new_ent_used
            changes_made = True
            changes.append('ent_used')

        if user_data.get('notification_delay') != self.notification_delay:
            self.notification_delay = user_data.get('notification_delay', self.notification_delay)
            changes_made = True
            changes.append('notification_delay')

        if user_data.get('fcm_token') != self.fcm_token:
            self.fcm_token = user_data.get('fcm_token', self.fcm_token)
            changes_made = True
            changes.append('fcm_token')

        # Update time settings
        new_timezone = user_data.get('timezone', self.timezone)
        if new_timezone != self.timezone:
            self.timezone = new_timezone
            self.timezone_obj = pytz.timezone(self.timezone)
            changes_made = True
            changes.append('timezone')

        # Update lunch times
        for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']:
            if user_data.get(f'{day}_lunch') != self.lunch_times.get(day):
                self.lunch_times[day] = user_data.get(f'{day}_lunch', self.lunch_times.get(day))
                changes_made = True
                changes.append(f'{day}_lunch')

        # Update feature flags
        if bool(user_data.get('evening_menu', self.evening_menu)) != self.evening_menu:
            self.evening_menu = bool(user_data.get('evening_menu', self.evening_menu))
            changes_made = True
            changes.append('evening_menu')

        if bool(user_data.get('unfinished_homework_reminder', self.unfinished_homework_reminder)) != self.unfinished_homework_reminder:
            self.unfinished_homework_reminder = bool(user_data.get('unfinished_homework_reminder', self.unfinished_homework_reminder))
            changes_made = True
            changes.append('unfinished_homework_reminder')

        if bool(user_data.get('get_bag_ready_reminder', self.get_bag_ready_reminder)) != self.get_bag_ready_reminder:
            self.get_bag_ready_reminder = bool(user_data.get('get_bag_ready_reminder', self.get_bag_ready_reminder))
            changes_made = True
            changes.append('get_bag_ready_reminder')
        
        if bool(user_data.get('new_grade_notification', self.new_grade_notification)) != self.new_grade_notification:
            self.new_grade_notification = bool(user_data.get('new_grade_notification', self.new_grade_notification))
            changes_made = True
            changes.append('get_bag_ready_reminder')

        # Only log if something changed
        if changes_made:
            logger.debug(f"Updated user {self.user_hash[:4]}**** from database. Changes: {', '.join(changes)}")

    async def get_current_lesson(self) -> dict:
        """Get current lesson information"""
        try:
            today = datetime.now(self.timezone_obj).date()
            lessons = self.client.lessons(date_from=today)
            current_time = datetime.now(self.timezone_obj)
            
            for lesson in lessons:
                # Ensure lesson times are timezone-aware
                lesson_start = lesson.start
                lesson_end = lesson.end
                
                # If lesson times are naive, make them timezone-aware
                if lesson_start.tzinfo is None:
                    lesson_start = self.timezone_obj.localize(lesson_start)
                if lesson_end.tzinfo is None:
                    lesson_end = self.timezone_obj.localize(lesson_end)
                
                if lesson_start <= current_time <= lesson_end and not lesson.canceled:
                    return {
                        'name': lesson.subject.name if lesson.subject else None,
                        'room': lesson.classroom,
                        'teacher': lesson.teacher_name if hasattr(lesson, 'teacher_name') else None,
                        'start': lesson_start.strftime('%H:%M'),
                        'end': lesson_end.strftime('%H:%M')
                    }
            return {}
        except Exception as e:
            logger.error(f"Error getting current lesson for user {self.user_hash[4:]}**** : {e}")
            return {}
    
    async def get_next_lesson(self) -> dict:
        """Get next lesson information"""
        try:
            today = datetime.now(self.timezone_obj).date()
            tomorrow = today + timedelta(days=1)
            current_time = datetime.now(self.timezone_obj)
            
            # Get lessons for today and tomorrow
            lessons_today = self.client.lessons(date_from=today)
            lessons_tomorrow = self.client.lessons(date_from=tomorrow) if datetime.now(self.timezone_obj).time() > dt_time(20, 0) else []
            
            all_lessons = lessons_today + lessons_tomorrow
            
            # Find next lesson
            upcoming_lessons = []
            for lesson in all_lessons:
                if lesson.canceled:
                    continue
                    
                # Ensure lesson start time is timezone-aware
                lesson_start = lesson.start
                if lesson_start.tzinfo is None:
                    lesson_start = self.timezone_obj.localize(lesson_start)
                
                if lesson_start > current_time:
                    upcoming_lessons.append((lesson, lesson_start))
            
            if upcoming_lessons:
                # Sort by start time and get the earliest
                next_lesson, next_lesson_start = min(upcoming_lessons, key=lambda x: x[1])
                next_lesson_end = next_lesson.end
                if next_lesson_end.tzinfo is None:
                    next_lesson_end = self.timezone_obj.localize(next_lesson_end)
                
                return {
                    'name': next_lesson.subject.name if next_lesson.subject else None,
                    'room': next_lesson.classroom,
                    'teacher': next_lesson.teacher_name if hasattr(next_lesson, 'teacher_name') else None,
                    'start': next_lesson_start.strftime('%H:%M'),
                    'end': next_lesson_end.strftime('%H:%M')
                }
            return {}
        except Exception as e:
            logger.error(f"Error getting next lesson for user {self.user_hash[:4]}**** : {e}")
            return {}

    async def get_homeworks(self, count: int = 5) -> list:
        """Get a defined count of upcoming homeworks"""
        try:
            today = datetime.now(self.timezone_obj).date()
            next_week = today + timedelta(days=7)

            homeworks = self.client.homework(date_from=today, date_to=next_week)
            upcoming_homeworks = []

            for hw in homeworks:
                if hw.date is None:
                    continue
                
                #only homeworks with due dates >= today
                if hw.date >= today:
                    upcoming_homeworks.append({
                        'subject': hw.subject.name if hw.subject else None,
                        'description': hw.description,
                        'due_date': hw.date.strftime('%Y-%m-%d'),
                        'done': hw.done
                    })
            
            #Sorted by due date
            return sorted(upcoming_homeworks, key=lambda x: x['due_date'])[:count]
                
        except Exception as e:
            logger.error(f"Error getting upcoming homeworks for user {self.user_hash[:4]}**** : {e}")
            sentry_sdk.capture_exception(e)
            return []

    
    async def get_pronote_data(self, requested_fields: list) -> dict:
        """Get Pronote data based on requested fields"""
        data = {}
        
        try:
            # Check session before fetching data
            await self.check_session()
            
            if any(field.startswith('next_class_') for field in requested_fields):
                next_lesson = await self.get_next_lesson()
                data.update({
                    'next_class_name': next_lesson.get('name'),
                    'next_class_room': next_lesson.get('room'),
                    'next_class_teacher': next_lesson.get('teacher'),
                    'next_class_start': next_lesson.get('start'),
                    'next_class_end': next_lesson.get('end')
                })
            
            if any(field.startswith('current_class_') for field in requested_fields):
                current_lesson = await self.get_current_lesson()
                data.update({
                    'current_class_name': current_lesson.get('name'),
                    'current_class_room': current_lesson.get('room'),
                    'current_class_teacher': current_lesson.get('teacher'),
                    'current_class_start': current_lesson.get('start'),
                    'current_class_end': current_lesson.get('end')
                })

            if 'homeworks' in requested_fields:
                homeworks = await self.get_homeworks()
                data['homeworks'] = homeworks
                
        except Exception as e:
            logger.error(f"Error getting Pronote data for user {self.user_hash[:4]}**** : {e}")
            for field in requested_fields:
                if field.startswith(('next_class_', 'current_class_')):
                    data[field] = None
        
        return {field: data.get(field) for field in requested_fields if field in data}
