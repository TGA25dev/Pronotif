import pronotepy
import datetime
from datetime import timedelta
import dotenv
import os
import random
import asyncio
import pytz
import aiohttp
import requests
from requests.adapters import TimeoutSauce
import configparser
import time
import sys
import traceback
from loguru import logger
import sentry_sdk
from dotenv import set_key
import json

# Configure default timeouts for requests
class DefaultTimeout(TimeoutSauce):
    def __init__(self, *args, **kwargs):
        if kwargs['connect'] is None:
            kwargs['connect'] = 10  # 10 seconds connection timeout
        if kwargs['read'] is None:
            kwargs['read'] = 15  # 15 seconds read timeout
        super(DefaultTimeout, self).__init__(*args, **kwargs)

requests.adapters.TimeoutSauce = DefaultTimeout

config = configparser.ConfigParser(comment_prefixes=";")
config.optionxform = str
script_directory = os.path.dirname(os.path.abspath(__file__))
version = "v0.8.1"

sentry_sdk.init("https://8c5e5e92f5e18135e5c89280db44a056@o4508253449224192.ingest.de.sentry.io/4508253458726992", 
                enable_tracing=True,
                traces_sample_rate=1.0,
                environment="production",
                release=version,
                server_name="Server")

try:
  with open("Data/config.ini", encoding='utf-8') as f:
    config.read_file(f)
  logger.info("Config file has been succesfully loaded !")
except Exception as e:
  logger.critical(f"An error has occurred while trying to open the config file: {e}\n\nClosing program...")
  sentry_sdk.capture_exception(e)
  time.sleep(2)
  sys.exit(1)

dotenv.load_dotenv("Data/pronote_username.env")
secured_username = os.getenv("User")
logger.debug("Pronote username has been loaded.")

dotenv.load_dotenv("Data/pronote_password.env")
secured_password = os.getenv("Password")
logger.debug("Pronote password has been loaded.")

login_page_link = config['Global'].get('login_page_link')
logger.debug(f"login_page_link is: {login_page_link} !")

topic_name = config['Global'].get('topic_name')
logger.debug(f"topic_name is: {topic_name} !")

notification_delay = config['Global'].get('notification_delay')
logger.debug(f"notification_delay is: {notification_delay} !")

lunch_times = {day.lower(): list(map(int, time.split(':'))) for day, time in config['LunchTimes'].items() if ':' in time}  # Include only entries that look like time
logger.debug(f"lunch_times have been loaded !")

evening_menu = config["LunchTimes"].get("evening_menu")
logger.debug(f"evening_menu is: {evening_menu} !")

timezone_str = config['Advanced'].get('timezone')
timezone = pytz.timezone(timezone_str)
logger.debug(f"timezone is: {timezone} !")

ent_used = config['Global'].get('ent_used')
logger.debug(f"ent_used loaded ! (value is {ent_used})")

qr_code_login = config['Global'].get('qr_code_login')
logger.debug(f"qr_code_login loaded ! (value is {qr_code_login})")

uuid = config['Global'].get('uuid')
logger.debug(f"uuid loaded !")

unfinished_homework_reminder = config['Advanced'].get('unfinished_homework_reminder')
logger.debug(f"unfinished_homework_reminder loaded ! (value is {unfinished_homework_reminder})")

get_bag_ready_reminder = config['Advanced'].get('get_bag_ready_reminder')
logger.debug(f"get_bag_ready_reminder loaded ! (value is {get_bag_ready_reminder})")

run_main_loop = True
printed_message = False

class_check_print_flag = False
menu_check_print_flag = False

max_retries = 5
retry_delay = 3

logger.remove()  # Remove any existing handlers
logger.add(sys.stdout, level="DEBUG")  # Log to console
logger.add("notif_system_logs.log", level="DEBUG", rotation="500 MB")  # Log to file with rotation

# Add these variables at the top with other global variables
class_message_printed_today = False
menu_message_printed_today = False
last_check_date = None

# Add after imports
import random

# Global exception handler
def handle_exception(exc_type:str, exc_value:str, exc_traceback:str) -> None:
  """
  Handle uncaught exceptions send them to sentry and log them to the logger
  """

  if issubclass(exc_type, KeyboardInterrupt):
    sys.__excepthook__(exc_type, exc_value, exc_traceback)
    return
  logger.critical(
    f"Uncaught exception: {exc_value}\n"
    f"Traceback: {''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))}"
  )
  sentry_sdk.capture_exception(exc_value)

sys.excepthook = handle_exception

async def handle_error_with_relogin(e) -> bool:
    """
    Handle errors by attempting to relogin and return True if successful, False otherwise
    """

    logger.error(f"Critical error occurred: {e}\nAttempting to relogin...")
    global client
    
    # Backoff for connection issues
    for attempt in range(5):  # Try 5 times
        try:
            # Delay between retries with exponential backoff
            if attempt > 0:
                wait_time = 5 * (2 ** attempt)  # 5, 10, 20s
                logger.info(f"Retry attempt {attempt+1}/5 after waiting {wait_time} seconds...")
                await asyncio.sleep(wait_time)
            
            # Check if server is even reachable before attempting relogin
            if not await check_pronote_server():
                logger.warning(f"Pronote server is unreachable (attempt {attempt+1}/5). Waiting before retry...")
                continue
                
            # Attempt to relogin
            if qr_code_login == "True":
                client = pronotepy.Client.token_login(login_page_link, username=secured_username, 
                                                     password=secured_password, uuid=uuid)
            else:
                client = pronotepy.Client(login_page_link, username=secured_username, 
                                         password=secured_password)

            if client.logged_in:
                logger.success("Successfully logged back in!")
                if qr_code_login == "True":
                    set_key(f"{script_directory}/Data/pronote_password.env", 'Password', client.password)
                return True
            
            logger.error("Failed to log back in!")
        
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectTimeout, 
                requests.exceptions.ConnectionError) as conn_error:
            logger.warning(f"Connection error during relogin attempt {attempt+1}/3: {conn_error}")
        
        except Exception as relogin_error:
            logger.critical(f"Failed to relogin (attempt {attempt+1}/3): {relogin_error}")
            sentry_sdk.capture_exception(relogin_error)
    
    #All attempts failed
    logger.error("All relogin attempts failed")
    sentry_sdk.capture_message("All relogin attempts failed", level="error")
    return False

async def check_internet_connexion() -> bool:
  """
  Check if the internet connexion is available
  """

  url = "http://www.google.com"
  timeout = 5
  try:
    requests.get(url, timeout=timeout)
    return True
  except requests.ConnectionError:
    return False

first_login = True    
async def check_session(client:pronotepy.Client) -> None:
    """
    Check if the session has expired and refresh it if necessary
    """

    global first_login
    if first_login: # Skip session check on first login
        first_login = False 
        return
    try:
        if client.session_check(): #Returns True if session has expired
            logger.warning("Session has expired!")

            if qr_code_login == "True":
                os.environ.pop('Password', None)
                dotenv.load_dotenv("Data/pronote_password.env")
                secured_password = os.getenv("Password")

                client = pronotepy.Client.token_login(login_page_link, username=secured_username, password=secured_password, uuid=uuid)

                if client.logged_in:
                    logger.success("A new session has been created!")
                    set_key(f"{script_directory}/Data/pronote_password.env", 'Password', client.password)
            else:
                client.refresh()
                logger.success("Session has been refreshed!")

    except Exception as e:
        logger.error(f"Session check failed: {e}")
        await handle_error_with_relogin(e)

async def retry_with_backoff(func, *args, max_attempts=5) -> None:
    """
    Retry a function with exponential backoff
    """

    timeout_incident_id = None
    
    for attempt in range(max_attempts):
        try:
            result = await func(*args)
            
            # If previously reported a timeout and now succeeded, mark it as resolved
            if timeout_incident_id:
                with sentry_sdk.new_scope() as scope:
                    scope.set_tag("status", "resolved")
                    sentry_sdk.capture_message(
                        f"Timeout resolved for {func.__name__} after {attempt} retries",
                        level="info"
                    )
                logger.success(f"Function {func.__name__} recovered after {attempt} retries")
            # Only log success if it's not the first attempt
            elif attempt > 0:
                logger.success(f"Function {func.__name__} succeeded after {attempt} retries")
            
            return result
            
        except (requests.exceptions.ReadTimeout, 
                requests.exceptions.ConnectTimeout, 
                requests.exceptions.ConnectionError) as e:
            
            wait_time = retry_delay * (2 ** attempt)
            
            # On first timeout, create an incident in Sentry
            if attempt == 0:
                with sentry_sdk.new_scope() as scope:
                    scope.set_tag("error_type", "timeout")
                    scope.set_tag("function", func.__name__)
                    scope.set_tag("status", "ongoing")
                    timeout_incident_id = sentry_sdk.capture_message(
                        f"Timeout occurred in {func.__name__}",
                        level="error"
                    )
            
            if attempt == max_attempts - 1:
                # Update the incident to show all retries failed
                with sentry_sdk.new_scope() as scope:
                    scope.set_tag("error_type", "timeout")
                    scope.set_tag("function", func.__name__)
                    scope.set_tag("status", "failed")
                    scope.set_tag("total_retries", str(max_attempts))
                    sentry_sdk.capture_message(
                        f"All retry attempts failed for {func.__name__}",
                        level="error"
                    )
                    
                if func.__name__ == 'fetch_lessons':
                    return []
                elif func.__name__ == 'fetch_menus':
                    return []
                else:
                    return None
            
            logger.warning(f"Network error: {e}. Retrying in {wait_time} seconds... (Attempt {attempt + 1}/{max_attempts})")
            await asyncio.sleep(wait_time)

        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}")
            sentry_sdk.capture_exception(e)
            if not await handle_error_with_relogin(e):
                return [] if func.__name__ in ['fetch_lessons', 'fetch_menus'] else None
            raise
        
async def check_pronote_server() -> bool:
  """
  Sends a HEAD request to check if the server is reachable.
  """
  try:
      response = requests.get(login_page_link, timeout=10, stream=True)
      if response.status_code == 200:
          #logger.debug("Pronote server is reachable.")
          return True
      else:
          if response.status_code < 500:
             #logger.error(f"Pronote instance seems to be down ! (status code: {response.status_code}, link: {login_page_link})")
             sentry_sdk.capture_message("Pronote instance seems to be down !", level="error")

      return False
  
  except requests.ConnectionError:
      logger.error("Connection error while checking Pronote server.")
      return False

async def pronote_main_checks_loop():
  """
  Main loop for checking lessons, menus, and reminders
  """

  try:
    await check_internet_connexion()
    if await check_internet_connexion() is False:
      logger.critical("No Internet connexion !\n\nProgram will close in 2 seconds...")
      time.sleep(2)
      sys.exit(1)
    
    logger.debug(await check_internet_connexion())
    now = datetime.datetime.now(timezone)
    # Calculate the time to the next full minute
    next_minute = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
    wait_time = (next_minute - now).total_seconds()

    logger.info(f"Waiting for {round(wait_time, 1)} seconds until system start...")
    #await asyncio.sleep(wait_time)
    logger.debug(f"System started ! ({datetime.datetime.now(timezone).strftime('%H:%M:%S')})")

    global client

    if qr_code_login == "True":
      client = pronotepy.Client.token_login(login_page_link, username=secured_username, password=secured_password, uuid=uuid)
    else:
      client = pronotepy.Client(login_page_link, username=secured_username, password=secured_password)

    if client.logged_in:
      logger.success(f"Succesfully logged in !")

      if qr_code_login == "True":
        set_key(f"{script_directory}/Data/pronote_password.env", 'Password', client.password) # Update the password in the .env file for future connexions
        logger.debug(f"New token password generated !")

      async def lesson_check() :
        """
        Check for upcoming lessons and send notifications
        """

        try:
          global class_check_print_flag
          global class_message_printed_today
          global last_check_date

          today = datetime.date.today()
          
          # Reset the flag if it's a new day
          if last_check_date != today:
              class_message_printed_today = False
              last_check_date = today

          today = datetime.date.today()
          #other_day = today + datetime.timedelta(days=3)  # For testing purposes
          
          async def fetch_lessons() -> list:
            """
            Fetch lessons from the server
            """

            return client.lessons(date_from=today)

          try:
            lesson_checker = await retry_with_backoff(fetch_lessons)

          except Exception as e:
            logger.error(f"Failed to fetch lessons after all retries: {e}")
            sentry_sdk.capture_exception(e)
            lesson_checker = []

          if not lesson_checker:
            if not class_message_printed_today:
              logger.info("There is probably no class today !")
              class_message_printed_today = True

          elif lesson_checker:
            current_time = datetime.datetime.now(timezone).strftime("%H:%M")

            todays_date = datetime.datetime.now(timezone).strftime("%Y-%m-%d")
            logger.debug(f"Real time: {todays_date} {current_time}")

            #fake_current_time = datetime.datetime.combine(other_day, datetime.time(11, 10)) - datetime.timedelta(minutes=0)
            #logger.debug(f"Fake time: {fake_current_time}")

            # Group all lessons by their start time
            lessons_by_time = {}
            for lesson in lesson_checker:
                start_time = lesson.start.strftime("%H:%M")

                if (start_time not in lessons_by_time):
                    lessons_by_time[start_time] = []
                lessons_by_time[start_time].append(lesson)

            # Process each time slot only once
            for start_time, lessons in lessons_by_time.items():
                lesson_start = datetime.datetime.strptime(start_time, "%H:%M").time()
                time_before_start = (datetime.datetime.combine(today, lesson_start) - datetime.timedelta(minutes=int(notification_delay))).time()

                #if fake_current_time.time() == time_before_start:
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
                    with open('Data/emoji_cours_names.json', 'r', encoding='utf-8') as emojis_data, open('Data/subject_names_format.json', 'r', encoding='utf-8') as subjects_data:
                      emojis = json.load(emojis_data)
                      subjects = json.load(subjects_data)

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

                    async def send_class_canceled_message_via_ntfy(message:str) -> int:
                      """
                      Send a message to the notification system when a class is canceled
                      """

                      try:
                        topic = topic_name
                        url = f"https://ntfy.sh/{topic}"
                        headers = {"Priority": "5", "Title": "Cours annulé !", "Tags": f"date"}

                        async with aiohttp.ClientSession() as session:
                          async with session.post(url, data=message.encode('utf-8'), headers=headers) as response:
                            if response.status == 200:
                              logger.success("The canceled class information message has been successfully sent !")
                              return response.status
                            
                      except Exception as e:
                        logger.error(f"Error sending notification: {e}")
                        if not await handle_error_with_relogin(e):
                            sys.exit(1)      

                    if canceled:
                      await send_class_canceled_message_via_ntfy(f"Le cours {det}{extra_space}{name} initialement prévu à {class_start_time} est annulé !")

                    elif not canceled:
                      if room_name is None:
                        class_time_message = f"Le cours {det}{extra_space}{name} commencera à {class_start_time}. {chosen_emoji}"

                      else:  
                        class_time_message = f"Le cours {det}{extra_space}{name} se fera en salle {room_name} et commencera à {class_start_time}. {chosen_emoji}"

                      logger.debug(class_time_message)
                      await send_class_info_notification_via_ntfy(class_time_message)

                    # Break after processing the matching time slot
                    break
        except Exception as e:
            logger.error(f"Error in lesson check: {e}")
            await handle_error_with_relogin(e)

      async def send_class_info_notification_via_ntfy(message:str) -> int:
        """
        Send a message to the notification system with the class information
        """
        
        try:
          topic = topic_name
          url = f"https://ntfy.sh/{topic}"
          s = "" if notification_delay == "1" else "s"
          headers = {"Priority": "5", "Title": f"Prochain cours dans {notification_delay} minute{s} !", "Tags": "bell"}

          async with aiohttp.ClientSession() as session:
            async with session.post(url, data=message.encode('utf-8'), headers=headers) as response:
              if response.status == 200:
                logger.success("The class information message has been successfully sent !")
                return response.status
                
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
            if not await handle_error_with_relogin(e):
                sys.exit(1)

      async def menu_food_check():
        """
        Check for upcoming menus and send notifications
        """

        try:
          global menu_message_printed_today
          global last_check_date

          today = datetime.date.today()
          
          # Reset the flag if it's a new day
          if last_check_date != today:
              menu_message_printed_today = False
              last_check_date = today

          today = datetime.date.today()
          global menus
      
          async def fetch_menus() -> list:
            """
            Fetch menus from the server
            """

            return client.menus(date_from=today)

          try:
            menus = await retry_with_backoff(fetch_menus)

          except Exception as e:
            logger.error(f"Failed to fetch menus after all retries: {e}")
            sentry_sdk.capture_exception(e)
            menus = []

          if menus:
            current_time = datetime.datetime.now(timezone).time()
            day_str = today.strftime('%A').lower()

            lunch_time = lunch_times.get(day_str)
    
            if lunch_time is not None:
              lunch_hour, lunch_minute = lunch_time

            global dinner_time
            dinner_time = None

            if current_time.hour == lunch_hour and current_time.minute == lunch_minute:
              logger.info(f"Lunch time ! ({today.strftime('%A')} {lunch_hour:02d}:{lunch_minute:02d})")
              dinner_time = False
              await food_notif_send_system()

            elif current_time.hour == 18 and current_time.minute == 55 and evening_menu == "True":
              logger.info(f"Diner time ! ({today.strftime('%A')} 18:55)")
              dinner_time = True
              await food_notif_send_system()
          else:
            if not menus:
              if not menu_message_printed_today:
                logger.info("There is no menu defined for today !")
                menu_message_printed_today = True

        except Exception as e:
            logger.error(f"Error in menu check: {e}")
            await handle_error_with_relogin(e)

      async def food_notif_send_system() -> None:
          """
          Send food menu notifications
          """
          def format_menu(menu_items:pronotepy.Menu) -> dict:
              """
              Format the menu items for notification
              """
              def extract_relevant_item(item_string:list) -> str: #(parameter could alose be str)
                  """
                  Extract the relevant item from a string or list of items
                  """
                  # Handle both string and list inputs
                  if isinstance(item_string, str):
                      items = [elem.strip() for elem in item_string.split(',')]
                  elif isinstance(item_string, list):
                      items = [str(elem).strip() for elem in item_string]
                  else:
                      items = []

                  # Heuristique pour déterminer le plat principal
                  def is_main_dish(item:str) -> bool:
                      """
                      Determine if an item is a main dish
                      """

                      # Exclure les éléments contenant certains mots-clés ou étant très courts
                      if len(item.split()) <= 2:  # Généralement, les plats principaux ont peu de mots
                          return True
                      if "de" in item.lower():  # Éviter les phrases avec des "de"
                          return False
                      return True

                  # Filtrer pour garder uniquement les plats principaux
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

                  # Si aucun plat principal n'est détecté, renvoyer tout pour éviter des pertes de données
                  return ', '.join(main_dishes) if main_dishes else ', '.join(items)

              def get_menu_items(items:pronotepy.Menu.Food) -> str:
                  """
                  Get the menu items for a category
                  """

                  if not items:
                      return ''
                  # Appliquer l'extraction aux chaînes de chaque catégorie
                  return extract_relevant_item(items)

              return {
                  'first_meal': get_menu_items(menu_items.first_meal),
                  'main_meal': get_menu_items(menu_items.main_meal),
                  'side_meal': get_menu_items(menu_items.side_meal),
                  'dessert': get_menu_items(menu_items.dessert),
              }

          for menu in menus:
              if dinner_time is False and menu.is_lunch:
                  # Formatter les items du menu
                  menu_items = format_menu(menu)

                  if all(menu_items.values()):  # Vérifie que toutes les catégories sont présentes
                      menu_text = (
                          f"Au menu: {menu_items['first_meal']}, "
                          f"{menu_items['main_meal']}, "
                          f"{menu_items['side_meal']} "
                          f"et {menu_items['dessert']} en dessert.\n"
                          "Bon appétit ! 😁"
                      )

                      await send_food_menu_notification_via_ntfy(menu_text, dinner_time)
                      logger.info(menu_text)
                  else:
                      logger.warning(f"Incomplete lunch menu for {menu.date}. Skipping notification.")

              elif dinner_time is True and menu.is_dinner:
                  # Formatter les items du menu
                  menu_items = format_menu(menu)

                  if all(menu_items.values()):  # Vérifie que toutes les catégories sont présentes
                      menu_text = (
                          f"Au menu: {menu_items['first_meal']}, "
                          f"{menu_items['main_meal']}, "
                          f"{menu_items['side_meal']} "
                          f"et {menu_items['dessert']} en dessert.\n"
                          "Bonne soirée ! 🌙"
                      )

                      await send_food_menu_notification_via_ntfy(menu_text, dinner_time)
                      logger.info(menu_text)

                  else:
                      logger.warning(f"Incomplete dinner menu for {menu.date}. Skipping notification.")

      async def send_food_menu_notification_via_ntfy(message:str, dinner_time:bool) -> int:
        """
        Send a message to the notification system with the food menu
        """

        try:
          food_tags_emojis = ["plate_with_cutlery", "fork_and_knife", "clock7" if dinner_time else "clock3"]
          food_tags_random_emojis = random.choice(food_tags_emojis)

          topic = topic_name
          url = f"https://ntfy.sh/{topic}"
          headers = {"Priority": "4", "Title": "C'est l'heure de manger !", "Tags": f"{food_tags_random_emojis}"}
          async with aiohttp.ClientSession() as session:
            async with session.post(url, data=message.encode('utf-8'), headers=headers) as response:
              if response.status == 200:
                return response.status

        except Exception as e:
          logger.error(f"Error sending notification: {e}")
          if not await handle_error_with_relogin(e):
              sys.exit(1)     

      async def send_reminder_notification_via_ntfy(message:str, reminder_type:str) -> int:
        """
        Send a message to the notification system with the reminder
        """

        try:
          topic = topic_name
          url = f"https://ntfy.sh/{topic}"

          if reminder_type == "bag":
              reminder_notification_title = "N'oubliez pas !"
              reminder_notification_tag = "school_satchel"

          elif reminder_type == "homework":
              if not_finished_homeworks_count == 0: # No homeworks left
                reminder_notification_title = "Reposez vous bien !" 
                
              elif not_finished_homeworks_count > 1: # Multiple homeworks left (plural)
                reminder_notification_title = "Devoirs non faits !"

              elif not_finished_homeworks_count == 1: # One homework (singular)
                reminder_notification_title = "Devoir non fait !"  

              reminder_notification_tag = "memo"  
          else:
            reminder_notification_title = ""  # Default title
            reminder_notification_tag = ""  # Default tag

          headers = {"Priority": "4", "Title": reminder_notification_title, "Tags": reminder_notification_tag}
          async with aiohttp.ClientSession() as session:
            async with session.post(url, data=message.encode('utf-8'), headers=headers) as response:
              if response.status == 200:
                logger.success("Reminder message sent successfully!")
                return response.status

        except Exception as e:
            logger.error(f"Error sending notification: {e}")
            if not await handle_error_with_relogin(e):
                sys.exit(1)

      async def check_reminder_notifications() -> None:
        """
        Check for reminders and send notifications
        """
        
        try:
          global reminder_type
          global reminder_message
          global current_time
          current_time = datetime.datetime.now(timezone).time()

          # Convert tomorrow to date object for homework check
          tomorrow_date = (datetime.datetime.now(timezone) + datetime.timedelta(days=1)).date()
                  
          for attempt in range(max_retries):
              try:
                class_checker = client.lessons(date_from=tomorrow_date)
                break

              except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError) as e:
                if attempt < max_retries - 1:
                  logger.warning(f"Connection timeout during lesson check (attempt {attempt + 1}/{max_retries}). Retrying in {retry_delay} seconds...")
                  await asyncio.sleep(retry_delay * (2 ** attempt))

                else:
                  logger.error(f"Failed to check lessons after {max_retries} attempts")
                  sentry_sdk.capture_exception(e)
                  class_checker = []  # List is empty for fallback

              except Exception as e:
                logger.error(f"Unexpected error checking lessons: {e}")
                if not await handle_error_with_relogin(e):
                    sys.exit(1)

                class_checker = []
                break

          if class_checker:
              class_tomorrow = True
          else:
              class_tomorrow = False

          if current_time.hour == 19 and current_time.minute == 35 and get_bag_ready_reminder == "True" and class_tomorrow:
              reminder_message = "Il est temps de préparer votre sac pour demain !"
              reminder_type = "bag"

              await send_reminder_notification_via_ntfy(reminder_message, reminder_type)
              logger.info(reminder_message)

          if current_time.hour == 18 and current_time.minute == 15 and unfinished_homework_reminder == "True" and class_tomorrow:
              homeworks = client.homework(tomorrow_date, tomorrow_date)
              reminder_type = "homework"

              # Initialize variables
              global not_finished_homeworks_count
              not_finished_homeworks_count = 0

              global defined_homework_for_tomorrow
              defined_homework_for_tomorrow = False

              if not homeworks:
                  # Handle case where no homework is found
                  not_finished_homeworks_count = 0
                  defined_homework_for_tomorrow = False
                  logger.warning("No homeworks found for tomorrow !")
              else:
                  # Process each homework
                  
                  for homework in homeworks:
                      
                      defined_homework_for_tomorrow = True
                      if not homework.done:
                          not_finished_homeworks_count += 1
                  
                  # Set reminder message based on homework completion status
                  if not_finished_homeworks_count == 0:
                      reminder_message = "Vous avez fini tous vos devoirs pour demain, vous pouvez souffler ! 😮‍💨"
                  else:
                    if not_finished_homeworks_count > 1:
                      reminder_message = f"Il vous reste {not_finished_homeworks_count} devoirs à terminer pour demain."

                    elif not_finished_homeworks_count == 1:
                      reminder_message = "Il vous reste 1 devoir à terminer pour demain."  
      
                  # Send the reminder notification
                  await send_reminder_notification_via_ntfy(reminder_message, reminder_type)
                  logger.info(reminder_message)

        except Exception as e:
            logger.error(f"Error in reminder check: {e}")
            await handle_error_with_relogin(e)

      no_internet_message = None
      instance_not_reachable_message = None
      while run_main_loop is True:
        start_time = time.time() 
        await check_internet_connexion()

        if await check_internet_connexion() and await check_pronote_server():
          no_internet_message = False
          instance_not_reachable_message = False
          await check_session(client)
          await asyncio.gather(lesson_check(), menu_food_check(), check_reminder_notifications())

        else:
          if not no_internet_message or not instance_not_reachable_message:
            logger.warning("Tasks have been paused... (No Internet connexion or Pronote server unreachable)")
            no_internet_message = True
            instance_not_reachable_message = True

        await asyncio.sleep(60 - ((time.time() - start_time) % 60))
        
    else:
      logger.critical(f"An error has occured while login: {e}\n\nClosing program...")
      sentry_sdk.capture_exception(e)
      time.sleep(2)
      exit(1)

  except Exception as e:
    logger.critical(f"Critical error in main loop: {e}")
    if not await handle_error_with_relogin(e):
        sys.exit(1)
    return

asyncio.run(pronote_main_checks_loop())