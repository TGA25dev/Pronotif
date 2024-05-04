import pronotepy
import datetime
import dotenv
import os
import random
import discord
from discord.ext import commands
import asyncio
import pytz
import aiohttp
import configparser
import time
import sys

config = configparser.ConfigParser(comment_prefixes=";")
config.optionxform = str

try:
    with open("dev_config.ini", encoding='utf-8') as f:
        config.read_file(f)
    print("Config file has been succesfully loaded !")
except Exception as e:
    print(f"An error has occurred while trying to open the config file: {e}")
    time.sleep(2)
    print("Closing program...")
    sys.exit(1)

dotenv.load_dotenv("Token/Templates/pronote_password.env")
secured_password = os.getenv("Password")

dotenv.load_dotenv("Token/Templates/pronote_user.env")
secured_username = os.getenv("User")

dotenv.load_dotenv("Token/Templates/pronote_bot_token.env")
token = os.getenv("Token")


login_page_link = config['Global'].get('login_page_link')
topic_name = config['Global'].get('topic_name')

lunch_times = {day.lower(): map(int, time.split(':')) for day, time in config['LunchTimes'].items()}

bot_prefix = config['Advanced'].get('bot_prefix')

timezone_str = config['Advanced'].get('timezone')
timezone = pytz.timezone(timezone_str)



bot = commands.Bot(command_prefix={bot_prefix}, intents=discord.Intents.all())

run_main_loop = True
printed_message = False

class_check_print_flag = False
menu_check_print_flag = False


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} ({bot.user.id})")
    print('------')
    print("Waiting 60s")
    await asyncio.sleep(60)
    asyncio.create_task(pronote_main_checks_loop())


@bot.command(name="test")
async def send_test_command(ctx):
    url = f"https://ntfy.sh/{topic_name}"
    headers = {"Priority": "5", "Title": "Test", "Tags": "test_tag"}
    message ="Ceci est un message de test..."

    async with aiohttp.ClientSession() as session:

        async with session.request("POST",url,data=message.encode("utf-8"),headers=headers) as response:
            if response.status == 200:
                print("The test message has been successfully sent!")
                await ctx.message.add_reaction("✉️")
            else:
                await ctx.message.add_reaction("❌")
                print(f"Failed to send test message. Status code: {response.status}")

@bot.command(name="moyenne")
async def send_average_command(ctx):
    periods = client.current_period
    average = float(periods.overall_average)

    if average < 10:
       message_title = "Persévère!"
       support_message = "📚"
       tag_emoji = "muscle"

    elif average > 10 and  average <= 12:
       message_title = "Continue comme ça."
       support_message = "Bien joué! 📝"
       tag_emoji = "smiley"

    elif average > 12 and average <= 14:
       message_title = "Super!"
       support_message = "Tu progresses ! 📚"
       tag_emoji = "star2"

    elif average > 14 and average <= 16:
       message_title = "Excellent!"
       support_message = "Tu es sur la bonne voie ! 📝"
       tag_emoji = "rocket"

    elif average > 16:
       message_title = "Félicitations!"
       support_message = "Tu es un exemple à suivre ! 🌟"
       tag_emoji = "tada"

    url = f"https://ntfy.sh/{topic_name}"
    headers = {"Priority": "5", "Title": f"{message_title}", "Tags": f"{tag_emoji}"}    

    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=f"Ta moyenne générale est de {average}/20.\n{support_message}".encode("utf-8"), headers=headers) as response:
            if response.status == 200:
                await ctx.message.add_reaction("✉️")
                print("The average message has been successfully sent!")

            else:
                print(f"Failed to send average message.")
                await ctx.message.add_reaction("❌")
                client.refresh()

async def pronote_main_checks_loop():
     global client
     client = pronotepy.Client(login_page_link,
                              username=secured_username,
                              password=secured_password)

     if client.logged_in:
        nom_utilisateur = client.info.name
        print(f'Logged in as {nom_utilisateur}')


        async def lesson_check():
            global class_check_print_flag
            
            today = datetime.date.today()
            #other_day = today + datetime.timedelta(days=3)
            lesson_checker = client.lessons(date_from=today) #CHANGE TO FAKE OR REAL !!

            if not lesson_checker:
                if not class_check_print_flag:
                 print("There is probably no class today !")
                 class_check_print_flag = True

            elif lesson_checker:
                has_printed = False
                   
                current_time = datetime.datetime.now(timezone).strftime("%H:%M")
                
                todays_date = datetime.datetime.now(timezone).strftime("%Y-%m-%d")
                print(f"Real time: {todays_date} {current_time}")

                #fake_current_time = datetime.datetime.combine(other_day, datetime.time(13, 55)) - datetime.timedelta(minutes=0)
                #print(f"Fake time: {fake_current_time}")

                for lesson_checks in lesson_checker:
                    start_time = lesson_checks.start.time()

                    five_minutes_before_start = datetime.datetime.combine(today, start_time) - datetime.timedelta(minutes=5)
                    five_minutes_before_start = five_minutes_before_start.strftime("%H:%M") #Useless if testing with fake time
                    
                    if current_time == five_minutes_before_start:                        
                    #if fake_current_time.time() ==  five_minutes_before_start.time():

                        global subject
                        subject = lesson_checks.subject.name
                        
                        room_name = lesson_checks.classroom
                        class_start_time = lesson_checks.start.strftime("%H:%M")
                        canceled = lesson_checks.canceled

                        global lower_cap_subject_name
                        lower_cap_subject_name = subject[0].capitalize() + subject[1:].lower()

                        # Define preprocessed_subject_emojis dictionary
                        preprocessed_subject_emojis = {}

                        # Iterate over the items in the SubjectEmojis section
                        for subject, emojis_str in config['SubjectEmojis'].items():
                         # Preprocess the subject string to have the first letter capitalized and the rest lowercase
                         preprocessed_subject = subject[0].capitalize() + subject[1:].lower()
                         # Store the preprocessed subject string and emojis in the new dictionary
                         preprocessed_subject_emojis[preprocessed_subject] = emojis_str

                        # Access the subject emojis from the preprocessed dictionary

                        subject_emojis = {}

                        for subject, emojis_str in preprocessed_subject_emojis.items():
                         emojis = emojis_str.split(', ')  # Split the emoji string into a list
                         subject_emojis[subject] = emojis


                        if canceled:
                            pass
                            print(f"Class {lower_cap_subject_name} at {class_start_time}, was canceled !\nNot sending any message...")
                            client.refresh()

                        elif not canceled:

                            if lower_cap_subject_name in subject_emojis:
                             random_subject_emojis = random.choice(subject_emojis[lower_cap_subject_name])
                            else:
                             print(f"No emojis found for subject: {lower_cap_subject_name}")
                             random_subject_emojis = "" 
                            
                            class_time_message = f"Le cours de {lower_cap_subject_name} se fera en salle {room_name} et commencera à {class_start_time}. {random_subject_emojis}"
                            print(class_time_message)
                            await send_class_info_notification_via_ntfy(class_time_message)

                    else:
                     pass
                               

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
                "ENS. MORAL & CIVIQUE": ["handshake", "speech_balloon", "balance_scale", "ballot_box", "brain"]
            }

            # Select emojis based on subject

            all_low_cap_subject_name = lower_cap_subject_name.lower() # Convert subject to lowercase for case-insensitive matching

            emojis = []
           
            if "anglais" in all_low_cap_subject_name:
             emojis = subject_emojis.get("ANGLAIS LV1", [])

            elif "eco" in all_low_cap_subject_name or "sociale" in subject:
             emojis = subject_emojis.get("SC. ECONO.& SOCIALES", [])

            elif "mathematiques" in all_low_cap_subject_name:
             emojis = subject_emojis.get("MATHEMATIQUES", [])

            elif "sport" in all_low_cap_subject_name:
             emojis = subject_emojis.get("ED.PHYSIQUE & SPORT.", [])

            elif "histoire" in all_low_cap_subject_name:
             emojis = subject_emojis.get("HISTOIRE-GEOGRAPHIE", [])

            elif "allemand" in all_low_cap_subject_name:
             emojis = subject_emojis.get("ALLEMAND LV2", [])

            elif any(word in all_low_cap_subject_name for word in ["informatique", "numerique", "numérique", "techno"]):
             emojis = subject_emojis.get("SC.NUMERIQ.TECHNOL.", [])

            elif "terre" in all_low_cap_subject_name:
             emojis = subject_emojis.get("SCIENCES VIE & TERRE", [])

            elif any(word in all_low_cap_subject_name for word in ["physique", "chimie"]):
             emojis = subject_emojis.get("PHYSIQUE-CHIMIE", [])

            elif any(word in all_low_cap_subject_name for word in ["moral", "civique"]):
             emojis = subject_emojis.get("ENS. MORAL & CIVIQUE", [])

            else:
              emojis = []

            class_tags_random_emojis = random.choice(emojis)

                
            topic = topic_name 
            url = f"https://ntfy.sh/{topic}"
            headers = {"Priority": "5", "Title": "Prochain cours dans 5 minutes !", "Tags": f"{class_tags_random_emojis}"}

            async with aiohttp.ClientSession() as session:
             async with session.post(url, data=message.encode('utf-8'), headers=headers) as response:
              if response.status == 200:
               print("The class information message has been successfully sent !")

               return response.status
              else:
                 print(f"A problem as occured while trying to send the class message : {response.status}")
                 client.refresh()

        async def send_food_menu_notification_via_ntfy(message):
         food_tags_emojis = ["plate_with_cutlery", "fork_and_knife", "clock3"]
         food_tags_random_emojis = random.choice(food_tags_emojis)

         topic = topic_name # replace with your topic
         url = f"https://ntfy.sh/{topic}"
         headers = {"Priority": "4", "Title": "C'est l'heure de manger !", "Tags": f"{food_tags_random_emojis}"}
         async with aiohttp.ClientSession() as session:
          async with session.post(url, data=message.encode('utf-8'), headers=headers) as response:
            if response.status == 200:

             return response.status
            else:
                 print(f"A problem as occured while trying to send the menu message : {response.status}")
                 client.refresh()

        async def menu_food_check():
         today = datetime.date.today()
         #other_day = today + datetime.timedelta(days=3)
         global menus
         try:
          menus = client.menus(date_from=today)
         except Exception as e:
          print(f"Error fetching menus: {e}")
          return
                   
         current_time = datetime.datetime.now(timezone).time()

         day_str = today.strftime('%A').lower()
         lunch_time = lunch_times.get(day_str)
         if lunch_time is not None:
          lunch_hour, lunch_minute = lunch_time
          if current_time.hour == lunch_hour and current_time.minute == lunch_minute:
           print(f"{today.strftime('%A')} {lunch_hour:02d}:{lunch_minute:02d}")

           await food_notif_send_system()
  

         elif not menus:
            print("There is no menu defined for today !")
         

        async def food_notif_send_system():
            global menus
            
            for menu in menus:
             if menu.is_lunch:
              print(f"Menu pour le {menu.date}:")

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
                print(f"C'est l'heure de manger !\nAu menu: {menu_first_meal.name}, {menu_main_meal.name} (ou {other_meal.name}), {menu_side_meal.name} et {menu_dessert.name} en dessert.\nBon appétit ! 😁")
              else:
                await send_food_menu_notification_via_ntfy(f"Au menu: {menu_first_meal.name}, {menu_main_meal.name}, {menu_side_meal.name} et {menu_dessert.name} en dessert.\nBon appétit ! 😁")
                print(f"C'est l'heure de manger !\nAu menu: {menu_first_meal.name}, {menu_main_meal.name}, {menu_side_meal.name} et {menu_dessert.name} en dessert.\nBon appétit ! 😁")

        while run_main_loop is True:
         await lesson_check()
         await menu_food_check()
         client.refresh()
         await asyncio.sleep(60)
        
     else:
      print("LOGIN ERROR !!")
      print(Exception)
      exit(1)

      
    
bot.run(token)
