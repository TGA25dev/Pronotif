import pronotepy
import datetime
from datetime import timedelta
import dotenv
import os
import random
import asyncio
import pytz
import aiohttp
import configparser
import time
import sys
import traceback
from loguru import logger
import importlib
import json

config = configparser.ConfigParser(comment_prefixes=";")
config.optionxform = str

try:
  with open("Data/config.ini", encoding='utf-8') as f:
    config.read_file(f)
  logger.info("Config file has been succesfully loaded !")
except Exception as e:
  logger.critical(f"An error has occurred while trying to open the config file: {e}\n\nClosing program...")
  time.sleep(2)
  sys.exit(1)

dotenv.load_dotenv("Data/pronote_user.env")
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
logger.debug(f"timezone is: {timezone}")

ent_used = config['Global'].get('ent_used')
logger.debug(f"ent_used loaded ! (value is {ent_used})")

ent_name = config['Global'].get('ent_name')
if ent_name is None:
  logger.debug(f"ent_name is set to None...")
else:
  logger.debug(f"ent_name has been loaded !")

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

async def pronote_main_checks_loop():
  now = datetime.datetime.now(timezone)
  # Calculate the time to the next full minute
  next_minute = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
  wait_time = (next_minute - now).total_seconds()
  logger.warning(f"Waiting for {round(wait_time, 1)} seconds until system start...")
  await asyncio.sleep(wait_time)
  logger.debug(f"System started ! ({datetime.datetime.now(timezone).strftime('%H:%M:%S')})")

  global client

  if ent_used == "True":
    module = importlib.import_module("pronotepy.ent")
    used_ent = getattr(module, ent_name, None)
    client = pronotepy.Client(login_page_link, username=secured_username, password=secured_password, ent=used_ent)
  else:
    client = pronotepy.Client(login_page_link, username=secured_username, password=secured_password)

  if client.logged_in:
    nom_utilisateur = client.info.name
    logger.info(f"Logged in as {nom_utilisateur} !")

    async def lesson_check():
      global class_check_print_flag

      today = datetime.date.today()
      #other_day = today + datetime.timedelta(days=3)
      lesson_checker = client.lessons(date_from=today)  # CHANGE TO FAKE OR REAL !!

      if not lesson_checker:
        if not class_check_print_flag:
          logger.info("There is probably no class today !")
          class_check_print_flag = True

      elif lesson_checker:
        has_printed = False

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
      subject_emojis = {
        "ANGLAIS LV1": ["earth_africa", "books", "pencil2", "gb", "mortar_board", " us"],
        "ANGLAIS LV SECTION": ["earth_africa", "books", "pencil2", "gb", "mortar_board", " us"],
        "SC. ECONO.& SOCIALES": ["chart_with_upwards_trend", "briefcase", "globe_with_meridians", "busts_in_silhouette", "moneybag"],
        "MATHEMATIQUES": ["heavy_plus_sign", "heavy_minus_sign", "heavy_multiplication_x", "heavy_division_sign", "triangular_ruler"],
        "FRANCAIS": ["memo", "book", "fr", "performing_arts", "mag"],
        "ED.PHYSIQUE & SPORT.": ["soccer", "basketball", "weight_lifting_man", "swimmer", "bicyclist"],
        "HISTOIRE-GEOGRAPHIE": ["earth_africa", "scroll", "world_map", "classical_building", "mantelpiece_clock"],
        "ALLEMAND LV2": ["de", "books", "speaking_head", "de", "at"],
        "SC.NUMERIQ.TECHNOL.": ["computer", "wrench", "rocket", "robot", "globe_with_meridians "],
        "SCIENCES VIE & TERRE": ["seedling", "microscope", "dna", "ocean", "microbe", "earth_africa"],
        "PHYSIQUE-CHIMIE": ["atom_symbol", "test_tube", "alembic", "fire", "bulb", "straight_ruler"],
        "ENS. MORAL & CIVIQUE": ["handshake", "speech_balloon", "balance_scale", "ballot_box", "brain"],
        "CANTINE": ["plate_with_cutlery", "fork_and_knife", "sandwich", "cup_with_straw", "cookie"],
        "ART PLASTIQUE": ["art", "paintbrush", "framed_picture", "scissors", "jigsaw"],
      }

      # Select emojis based on subject
      all_low_cap_subject_name = lower_cap_subject_name.lower()  # Convert subject to lowercase for case-insensitive matching

      emojis = []

      if any(word in all_low_cap_subject_name for word in ["anglais", "amc"]):
        emojis = subject_emojis.get("ANGLAIS LV1", [])

      elif any(word in all_low_cap_subject_name for word in ["eco", "sociale", "économie", "economie"]):
        emojis = subject_emojis.get("SC. ECONO.& SOCIALES", [])

      elif any(word in all_low_cap_subject_name for word in ["math", "mathématiques", "mathematiques"]):
        emojis = subject_emojis.get("MATHEMATIQUES", [])

      elif any(word in all_low_cap_subject_name for word in ["sport", "sportive", "eps"]):
        emojis = subject_emojis.get("ED.PHYSIQUE & SPORT.", [])

      elif any(word in all_low_cap_subject_name for word in ["histoire", "géo", "geo", "géographie"]):
        emojis = subject_emojis.get("HISTOIRE-GEOGRAPHIE", [])

      elif any(word in all_low_cap_subject_name for word in ["allemand"]):
        emojis = subject_emojis.get("ALLEMAND LV2", [])

      elif any(word in all_low_cap_subject_name for word in ["informatique", "numerique", "numérique", "techno", "nsi"]):
        emojis = subject_emojis.get("SC.NUMERIQ.TECHNOL.", [])

      elif any(word in all_low_cap_subject_name for word in ["svt", "terre", "biologie"]):
        emojis = subject_emojis.get("SCIENCES VIE & TERRE", [])

      elif any(word in all_low_cap_subject_name for word in ["physique", "chimie", "sciences", "scientifique"]):
        emojis = subject_emojis.get("PHYSIQUE-CHIMIE", [])

      elif any(word in all_low_cap_subject_name for word in ["moral", "civique", "emc"]):
        emojis = subject_emojis.get("ENS. MORAL & CIVIQUE", [])

      elif any(word in all_low_cap_subject_name for word in ["art", "plastique"]):
        emojis = subject_emojis.get("ART PLASTIQUE", [])

      elif any(word in all_low_cap_subject_name for word in ["cantine", "repas", "diner", "dejeuner"]):
        emojis = subject_emojis.get("CANTINE", [])

      elif any(word in all_low_cap_subject_name for word in ["français", "francais", "philo", "humanisme"]):
        emojis = subject_emojis.get("FRANCAIS", [])

      if emojis:
        class_tags_random_emojis = random.choice(emojis)
      else:
        emojis = [""]
        logger.warning(f"No tag emojis found for subject : {all_low_cap_subject_name}")

      topic = topic_name
      url = f"https://ntfy.sh/{topic}"
      headers = {"Priority": "5", "Title": "Prochain cours dans 5 minutes !", "Tags": f"{class_tags_random_emojis}"}

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
      await lesson_check()
      await menu_food_check()
      client.refresh()
      await asyncio.sleep(60)

  else:
    logger.critical(f"An error has occured while login: {Exception}\n\nClosing program...")
    time.sleep(2)
    exit(1)

asyncio.run(pronote_main_checks_loop())