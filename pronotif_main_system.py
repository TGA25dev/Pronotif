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
import configparser
import time
import sys
import traceback
from loguru import logger
import sentry_sdk
from dotenv import set_key
import json

config = configparser.ConfigParser(comment_prefixes=";")
config.optionxform = str
script_directory = os.path.dirname(os.path.abspath(__file__))
version = "v0.5"

sentry_sdk.init("https://8c5e5e92f5e18135e5c89280db44a056@o4508253449224192.ingest.de.sentry.io/4508253458726992", 
                enable_tracing=True,
                traces_sample_rate=1.0,
                environment="development",
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

# Adding custom colors and format to the logger
logger.remove()  # Remove any existing handlers
logger.add(sys.stdout, level="DEBUG")  # Log to console
logger.add("notif_system_logs.log", level="DEBUG", rotation="500 MB")  # Log to file with rotation

# Global exception handler
def handle_exception(exc_type, exc_value, exc_traceback):
  if issubclass(exc_type, KeyboardInterrupt):
    sys.__excepthook__(exc_type, exc_value, exc_traceback)
    return
  logger.critical(
    f"Uncaught exception: {exc_value}\n"
    f"Traceback: {''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))}"
  )
  sentry_sdk.capture_exception(exc_type, exc_value, exc_traceback)

sys.excepthook = handle_exception

internet_connected = None
async def check_internet_connexion():
  url = "http://www.google.com"
  timeout = 5
  global internet_connected
  try:
    requests.get(url, timeout=timeout)
    internet_connected = True
  except requests.ConnectionError:
    internet_connected = False

first_login = True    
async def check_session(client):

  global first_login #Don't get session status for 1st check
  if first_login:
    first_login = False
    pass

  else:
    if client.session_check() is True: #Set to False for testing purposes, real is True
      logger.error("Session has expired !")

      if qr_code_login == "True":
        try:
          os.environ.pop('Password', None)  # Clear memory cache of the password variable

          dotenv.load_dotenv("Data/pronote_password.env")
          secured_password = os.getenv("Password")
          logger.debug("Pronote password has been reloaded !")

          client = pronotepy.Client.token_login(login_page_link, username=secured_username, password=secured_password, uuid=uuid) #As refreshing is not available for QR Code login, create a new session
          if client.logged_in:
            logger.info("A new session has been created !")
            set_key(f"{script_directory}/Data/pronote_password.env", 'Password', client.password)

        except Exception as e:
          logger.error(f"An error happened during session creation: {e}\nClosing program...")
          sentry_sdk.capture_exception(e)
          sys.exit(1)

      else:
        client.refresh()
        logger.info("Session has been refreshed !")
    else:
      if qr_code_login != "True":
        client.refresh()

async def pronote_main_checks_loop():
  await check_internet_connexion()
  if internet_connected is False:
    logger.critical("No Internet connexion !\n\nProgram will close in 2 seconds...")
    time.sleep(2)
    exit(1)
  
  logger.debug(internet_connected)
  now = datetime.datetime.now(timezone)
  # Calculate the time to the next full minute
  next_minute = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
  wait_time = (next_minute - now).total_seconds()
  logger.warning(f"Waiting for {round(wait_time, 1)} seconds until system start...")
  await asyncio.sleep(wait_time)
  logger.debug(f"System started ! ({datetime.datetime.now(timezone).strftime('%H:%M:%S')})")

  global client

  if qr_code_login == "True":
    client = pronotepy.Client.token_login(login_page_link, username=secured_username, password=secured_password, uuid=uuid)
  else:
    client = pronotepy.Client(login_page_link, username=secured_username, password=secured_password)

  if client.logged_in:
    nom_utilisateur = client.info.name
    logger.info(f"Logged in as {nom_utilisateur} !")

    if qr_code_login == "True":
      set_key(f"{script_directory}/Data/pronote_password.env", 'Password', client.password) # Update the password in the .env file for future connexions
      logger.debug(f"New token password generated !")

    async def lesson_check():
      global class_check_print_flag

      today = datetime.date.today()
      #other_day = today + datetime.timedelta(days=3)
      lesson_checker = client.lessons(date_from=today)  # CHANGE TO FAKE OR REAL !!

      if not lesson_checker:
        if not class_check_print_flag:
          logger.info("There is probably no class today !")
      elif lesson_checker:
        current_time = datetime.datetime.now(timezone).strftime("%H:%M")

        todays_date = datetime.datetime.now(timezone).strftime("%Y-%m-%d")
        logger.debug(f"Real time: {todays_date} {current_time}")

        #fake_current_time = datetime.datetime.combine(other_day, datetime.time(9, 5)) - datetime.timedelta(minutes=0)
        #logger.debug(f"Fake time: {fake_current_time}")

        for lesson_checks in lesson_checker:
          start_time = lesson_checks.start.time()

          time_before_start = datetime.datetime.combine(today, start_time) - datetime.timedelta(minutes=int(notification_delay))
          time_before_start = time_before_start.strftime("%H:%M") #Comment when testing with fake time

          if current_time == time_before_start:
          #if fake_current_time.time() ==  time_before_start.time():
            global subject
            subject = lesson_checks.subject.name

            room_name = lesson_checks.classroom
            class_start_time = lesson_checks.start.strftime("%H:%M")
            canceled = lesson_checks.canceled

            # Load JSON data from files
            with open('Data/emoji_cours_names.json', 'r', encoding='utf-8') as file1, open('Data/subject_names_format.json', 'r', encoding='utf-8') as file2:
              emojis = json.load(file1)
              subjects = json.load(file2)

            global lower_cap_subject_name
            lower_cap_subject_name = subject[0].capitalize() + subject[1:].lower()

            # Normalize function to simplify comparison
            def normalize(text):
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
              det = "de"  # default determinant if not found

            # Find matching emoji
            found_emoji_list = ['📝']  # Default emoji if no match is found
            for short_name, emoji_list in normalized_emojis.items():
              if short_name in normalized_subject_key:
                found_emoji_list = emoji_list
                break

            # Randomly choose an emoji from the matched emoji list
            chosen_emoji = random.choice(found_emoji_list)

            if det == "de":
              extra_space = " "
            else:
              extra_space = ""

            async def send_class_canceled_message_via_ntfy(message):
              topic = topic_name
              url = f"https://ntfy.sh/{topic}"
              headers = {"Priority": "5", "Title": "Cours annulé !", "Tags": f"date"}

              async with aiohttp.ClientSession() as session:
                async with session.post(url, data=message.encode('utf-8'), headers=headers) as response:
                  if response.status == 200:
                    logger.info("The canceled class information message has been successfully sent !")
                    return response.status
                  else:
                    logger.error(f"A problem as occured while trying to send the class message : {response.status}")
                    client.refresh()

            if canceled:
              await send_class_canceled_message_via_ntfy(f"Le cours {det}{extra_space}{name} initialement prévu à {class_start_time} est annulé !")

            elif not canceled:
              class_time_message = f"Le cours {det}{extra_space}{name} se fera en salle {room_name} et commencera à {class_start_time}. {chosen_emoji}"
              logger.debug(class_time_message)
              await send_class_info_notification_via_ntfy(class_time_message)

    async def send_class_info_notification_via_ntfy(message):
      topic = topic_name
      url = f"https://ntfy.sh/{topic}"
      s = "" if notification_delay == "1" else "s"
      headers = {"Priority": "5", "Title": f"Prochain cours dans {notification_delay} minute{s} !", "Tags": "school_satchel"}

      async with aiohttp.ClientSession() as session:
        async with session.post(url, data=message.encode('utf-8'), headers=headers) as response:
          if response.status == 200:
            logger.info("The class information message has been successfully sent !")
            return response.status
          else:
            logger.error(f"A problem as occured while trying to send the class message : {response.status}")
            client.refresh()

    async def send_food_menu_notification_via_ntfy(message, dinner_time):
      food_tags_emojis = ["plate_with_cutlery", "fork_and_knife", "clock7" if dinner_time else "clock3"]
      food_tags_random_emojis = random.choice(food_tags_emojis)

      topic = topic_name
      url = f"https://ntfy.sh/{topic}"
      headers = {"Priority": "4", "Title": "C'est l'heure de manger !", "Tags": f"{food_tags_random_emojis}"}
      async with aiohttp.ClientSession() as session:
        async with session.post(url, data=message.encode('utf-8'), headers=headers) as response:
          if response.status == 200:
            return response.status
          else:
            logger.error(f"A problem as occured while trying to send the menu message : {response.status}")
            client.refresh()

    async def menu_food_check():
      today = datetime.date.today()
      global menus
      try:
        menus = client.menus(date_from=today)
      except Exception as e:
        logger.error(f"Error fetching menus: {e}")
        sentry_sdk.capture_exception(e)
        return
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
          logger.info("There is no menu defined for today !")

    async def food_notif_send_system():
        def format_menu(menu_items):
            def extract_relevant_item(item_string):
                # Handle both string and list inputs
                if isinstance(item_string, str):
                    items = [elem.strip() for elem in item_string.split(',')]
                elif isinstance(item_string, list):
                    items = [str(elem).strip() for elem in item_string]
                else:
                    items = []

                # Heuristique pour déterminer le plat principal
                def is_main_dish(item):
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

            def get_menu_items(items):
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

    async def send_reminder_notification_via_ntfy(message, reminder_type):
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
            logger.info("Reminder message sent successfully!")
            return response.status
          else:
            logger.error(f"Error sending Reminder message: {response.status}")

    async def check_reminder_notifications():
        global reminder_type
        global reminder_message
        global current_time
        current_time = datetime.datetime.now(timezone).time()

        # Convert tomorrow to date object for homework check
        tomorrow_date = (datetime.datetime.now(timezone) + datetime.timedelta(days=1)).date()
        
        class_checker = client.lessons(date_from=tomorrow_date)

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
            logger.debug(tomorrow_date)
            
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

    while run_main_loop is True:
      await check_internet_connexion()
      if internet_connected:
        no_internet_message = False
        await check_session(client)
        await lesson_check()
        await menu_food_check()
        await check_reminder_notifications()
      else:
        if not no_internet_message:
          logger.critical("Tasks have been paused... (No Internet connexion)")
          no_internet_message = True
      await asyncio.sleep(60)
      
  else:
    logger.critical(f"An error has occured while login: {Exception}\n\nClosing program...")
    sentry_sdk.capture_exception(Exception)
    time.sleep(2)
    exit(1)

asyncio.run(pronote_main_checks_loop())