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
from dotenv import set_key
import json

config = configparser.ConfigParser(comment_prefixes=";")
config.optionxform = str
script_directory = os.path.dirname(os.path.abspath(__file__))

try:
  with open("Data/config.ini", encoding='utf-8') as f:
    config.read_file(f)
  logger.info("Config file has been succesfully loaded !")
except Exception as e:
  logger.critical(f"An error has occurred while trying to open the config file: {e}\n\nClosing program...")
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

lunch_times = {day.lower(): list(map(int, time.split(':'))) for day, time in config['LunchTimes'].items()}
logger.debug(f"lunch_times have been loaded !")

timezone_str = config['Advanced'].get('timezone')
timezone = pytz.timezone(timezone_str)
logger.debug(f"timezone is: {timezone} !")

ent_used = config['Global'].get('ent_used')
logger.debug(f"ent_used loaded ! (value is {ent_used})")

qr_code_login = config['Global'].get('qr_code_login')
logger.debug(f"qr_code_login loaded ! (value is {qr_code_login})")

uuid = config['Global'].get('uuid')
logger.debug(f"uuid loaded !")

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

        current_time = datetime.datetime.now(timezone).strftime("%H:%M")

        todays_date = datetime.datetime.now(timezone).strftime("%Y-%m-%d")
        logger.debug(f"Real time: {todays_date} {current_time}")

        #fake_current_time = datetime.datetime.combine(other_day, datetime.time(9, 5)) - datetime.timedelta(minutes=0)
        #logger.debug(f"Fake time: {fake_current_time}")

        for lesson_checks in lesson_checker:
          start_time = lesson_checks.start.time()

          five_minutes_before_start = datetime.datetime.combine(today, start_time) - datetime.timedelta(minutes=5)
          five_minutes_before_start = five_minutes_before_start.strftime("%H:%M") #Comment when testing with fake time

          if current_time == five_minutes_before_start:
          #if fake_current_time.time() ==  five_minutes_before_start.time():
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
      headers = {"Priority": "5", "Title": "Prochain cours dans 5 minutes !", "Tags": "school_satchel"}

      async with aiohttp.ClientSession() as session:
        async with session.post(url, data=message.encode('utf-8'), headers=headers) as response:
          if response.status == 200:
            logger.info("The class information message has been successfully sent !")
            return response.status
          else:
            logger.error(f"A problem as occured while trying to send the class message : {response.status}")
            client.refresh()

    async def send_food_menu_notification_via_ntfy(message):
      food_tags_emojis = ["plate_with_cutlery", "fork_and_knife", "clock3"]
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
        return
      if menus:
        current_time = datetime.datetime.now(timezone).time()
        day_str = today.strftime('%A').lower()

        lunch_time = lunch_times.get(day_str)
 
        if lunch_time is not None:
          lunch_hour, lunch_minute = lunch_time

        if current_time.hour == lunch_hour and current_time.minute == lunch_minute:
          logger.debug(f"{today.strftime('%A')} {lunch_hour:02d}:{lunch_minute:02d}")
          await food_notif_send_system()
      else:
        if not menus:
          logger.debug("There is no menu defined for today !")

    async def food_notif_send_system():
      global menus

      for menu in menus:
        if menu.is_lunch:
          logger.info(f"Menu pour le {menu.date} :")
          for menu_first_meal in menu.first_meal:
            pass

          for menu_main_meal in menu.main_meal:
            pass

          for menu_side_meal in menu.side_meal:
            pass

          for menu_dessert in menu.dessert:
            pass

          if menu.other_meal:
            for other_meal in menu.other_meal:
              pass

            await send_food_menu_notification_via_ntfy(f"Au menu: {menu_first_meal.name}, {menu_main_meal.name} (ou {other_meal.name}), {menu_side_meal.name} et {menu_dessert.name} en dessert.\nBon appétit ! 😁")

          else:
            await send_food_menu_notification_via_ntfy(f"Au menu: {menu_first_meal.name}, {menu_main_meal.name}, {menu_side_meal.name} et {menu_dessert.name} en dessert.\nBon appétit ! 😁")
          logger.debug("Lunch menu sent successfully !")

    while run_main_loop is True:
      await check_internet_connexion()
      if internet_connected:
        no_internet_message = False
        await check_session(client)
        await lesson_check()
        await menu_food_check()
      else:
        if not no_internet_message:
          logger.critical("Tasks have been paused... (No Internet connexion)")
          no_internet_message = True
      await asyncio.sleep(60)
      
  else:
    logger.critical(f"An error has occured while login: {Exception}\n\nClosing program...")
    time.sleep(2)
    exit(1)

asyncio.run(pronote_main_checks_loop())