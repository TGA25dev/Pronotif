import customtkinter as ctk
from customtkinter import *
from CTkMessagebox import CTkMessagebox
import pronotepy
import requests
from geopy.geocoders import Nominatim
from dotenv import set_key
import re
import sys
import time
import json
from hPyT import *
import importlib
import os
import webbrowser
import configparser
import base64
from win11toast import notify
import shutil
import subprocess
import winsound
import datetime
import traceback
from loguru import logger
from notifiers.logging import NotificationHandler
from PIL import Image

# Create a ConfigParser object
config = configparser.ConfigParser()

default_title_font = "Roboto", 17, "bold"
default_subtitle_font = "Roboto", 12 
default_text_font = "Roboto", 13
default_credit_font = "Roboto", 10

geolocator = Nominatim(user_agent="Geocoder")

script_directory = os.path.dirname(os.path.abspath(__file__))

config_file_path = f"{script_directory}/Data/config.ini"
config_file_name = "config.ini"

cancel_icon_path = f"{script_directory}/Icons/Messagebox UI/cancel_icon.png"
ok_icon_path = f"{script_directory}/Icons/Messagebox UI/ok_icon.png"
question_icon_path = f"{script_directory}/Icons/Messagebox UI/question_icon.png"
warning_icon_path = f"{script_directory}/Icons/Messagebox UI/warning_icon.png"
info_icon_path = f"{script_directory}/Icons/Messagebox UI/info_icon.png"

github_repo_name = "TGA25dev/Pronote-Class-Notifier"

local_paths = {
    "config": os.path.join(script_directory, "Data", "config.ini"),
    "ico": os.path.join(script_directory, "pronote_butterfly.ico"),
    "ent_data": os.path.join(script_directory, "Data", "ent_data.json"),
    "env_p": os.path.join(script_directory, "Data", "pronote_password.env"),
    "env_u": os.path.join(script_directory, "Data", "pronote_username.env")
}

github_paths = {
    "config": "Data/config.ini",
    "ico": "pronote_butterfly.ico",
    "ent_data": "Data/ent_data.json",
    "env_p": "Data/pronote_password.env",
    "env_u": "Data/pronote_username.env"
}

# Adding custom colors and format to the logger
logger.remove()  # Remove any existing handlers
logger.add(sys.stdout, level="DEBUG")  # Log to console
logger.add("setup_wizard_logs.log", level="DEBUG", rotation="500 MB")  # Log to file with rotation

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

#wanted file type can be : ico, config, ent_data, pronote_password or pronote_username

def check_important_file_existence(wanted_file_type):
  github_file_path = None
  file_path = None

  file_path = local_paths.get(wanted_file_type)
  github_file_path = github_paths.get(wanted_file_type)

  # Check if the file exists
  while not os.path.isfile(file_path):
    if github_file_path is not None:
     logger.critical(f"File ({wanted_file_type}) does not exist. Downloading from the GitHub repo...")

     notify('Fichier manquant !', 'Un fichier nécéssaire au fonctionement du logiciel semble avoir été supprimé !\n\nTéléchargement en cours...', icon="https://i.postimg.cc/FRKD3Jgc/warning.png")

     # Construct the API URL
     api_url = f"https://api.github.com/repos/{github_repo_name}/contents/{github_file_path}"

     # Send a GET request to the API URL
     response = requests.get(api_url)

     # If the request was successful, get the download URL
     if response.status_code == 200:
        # The content is in the 'content' key of the JSON response
        content = response.json()['content']
        # Decode the content from Base64
        content = base64.b64decode(content)

        # Write the content to the file
        with open(file_path, 'wb') as f:
            f.write(content)
            logger.info(f"File ({wanted_file_type}) has been saved succesfully !")
            notify("Téléchargement terminé !","Merci d'avoir patienté ! 🚀", icon="https://i.postimg.cc/PJWpqSpM/ok-icon.png")
          
     else:
        logger.critical(f"Failed to download file ({wanted_file_type}). Status code: {response.status_code}")

    else:
      # Create empty .env file for env_u or env_p if they don't exist
      with open(file_path, 'w') as f:
        if wanted_file_type == "env_p":
          f.write("Password=")
        elif wanted_file_type == "env_u":
          f.write("User=")
        
        logger.info(f"File ({wanted_file_type}) has been created successfully!")
        notify("Téléchargement terminé !","Merci d'avoir patienté ! 🚀", icon="https://i.postimg.cc/PJWpqSpM/ok-icon.png")   

  else:
    logger.debug(f"File ({wanted_file_type}) exists. No action taken.")


countdown_seconds = 20  # Define the countdown_seconds variable outside the function

def update_countdown():
    global countdown_seconds  # Declare that you're using the global variable

    if countdown_seconds > 0:
        closing_countdown_label.configure(text=f"Fermeture dans {countdown_seconds}s...")
        countdown_seconds -= 1
        root.after(1000, update_countdown)  # Schedule the update_countdown function to run after 1 second
    else:
        root.destroy()  # Close the window or take any other action when the countdown reaches 0

def find_export_dir():  
  box = CTkMessagebox(title="Ziper le dossier ?", message=f"Souhaitez-vous ziper le dossier du bot pour alléger son poid ?", icon=question_icon_path, option_1="Oui", option_2="Non",cancel_button=None ,cancel_button_color="light grey", justify="center", master=root, width=350, height=10, corner_radius=20)
  box.info._text_label.configure(wraplength=450)

  response = box.get()

  if response == "Non":
    subprocess.Popen(f'explorer {os.path.realpath(f"{script_directory}/Bot Files")}')

  else:
    logger.debug("Ziping folder...")

    shutil.make_archive(f"{script_directory}/Bot Files", 'zip', f"{script_directory}/Bot Files")
    
    logger.debug("Folder has been ziped succesfully !")
    shutil.rmtree(f"{script_directory}/Bot Files")
    subprocess.Popen(f'explorer {os.path.realpath(f"{script_directory}")}')
    
  find_dir_button.configure(state="disabled", text_color="grey")

  global closing_countdown_label
  closing_countdown_label = CTkLabel(root, text="Fermeture...")
  closing_countdown_label.place(relx=0.2, rely=0.95, anchor="center")

  close_button.place_forget()

  winsound.PlaySound("SystemExclamation", winsound.SND_ALIAS)
  window_flash.flash(root, 5, 500)

  # Start the countdown

  update_countdown()


def final_step():
  logger.debug("All steps have been succesfully completed !")
  tabview.pack_forget()

  main_text.place(relx=0.5, rely=0.3, anchor="center")
  main_text.configure(text="Vous avez terminé la configuration de Pronote Class Notifier !\n\nCliquez sur le boutton ci-dessous pour trouver le dossier\nde votre bot.")

  global find_dir_button
  find_dir_button = CTkButton(root, text="Trouver", command=find_export_dir)
  find_dir_button.place(relx=0.5, rely=0.65, anchor="center")

  bot_files_folder = os.path.exists(f"{script_directory}/Bot Files")
  bot_files_zip_folder = os.path.isfile(f"{script_directory}/Bot Files.zip")
 
  if bot_files_folder:
    shutil.rmtree(f"{script_directory}/Bot Files")

  elif bot_files_zip_folder:
    os.remove(f"{script_directory}/Bot Files.zip")

  os.mkdir(f"{script_directory}/Bot Files")
  os.mkdir(f"{script_directory}/Bot Files/Data")

  shutil.copy(f"{script_directory}/requirements.txt", f"{script_directory}/Bot Files/requirements.txt")
  shutil.copy(f"{script_directory}/pronote_main_code.py", f"{script_directory}/Bot Files/pronote_main_code.py")
  shutil.copy(f"{script_directory}/Data/{config_file_name}", f"{script_directory}/Bot Files/Data/{config_file_name}")
  shutil.copy(f"{script_directory}/Data/ent_data.json", f"{script_directory}/Bot Files/Data/ent_data.json")
  shutil.copy(f"{script_directory}/Data/pronote_password.env", f"{script_directory}/Bot Files/Data/pronote_password.env")
  shutil.copy(f"{script_directory}/Data/pronote_username.env", f"{script_directory}/Bot Files/Data/pronote_username.env")


steps = ['config_tab1_approved', 'config_tab2_approved', 'config_tab3_approved', 'config_tab4_approved']

for step in steps:
    if step not in globals():
        globals()[step] = False

# Function to check if all steps are completed
def check_all_steps_completed():    
    if all(globals().get(step, False) for step in steps):
        final_step()

def get_ntfy_topic():
  ntfy_entered_topic_name = ntfy_topic_name_entry.get()
 
  box = CTkMessagebox(title="Valider ?", message=f"Est-ce bien le nom de votre topic ?\n{ntfy_entered_topic_name}", icon=question_icon_path, option_1="Oui", option_2="Annuler",cancel_button=None ,cancel_button_color="light grey", justify="center", master=root, width=350, height=10, corner_radius=20)
  box.info._text_label.configure(wraplength=450)

  response = box.get()

  if response == "Oui":
    defined_ntfy_topic_name = ntfy_entered_topic_name
    logger.debug(f"ntfy topic name has been defined on: {defined_ntfy_topic_name}")

    ntfy_topic_name_button.configure(state="disabled")
    ntfy_topic_name_entry.configure(state="disabled", text_color="grey")
    config_tab_step1_text.configure(text="Parfait !\nVous pouvez passer au deuxième onglet.")

    check_important_file_existence(wanted_file_type="config") 

    # Read the INI file with the appropriate encoding
    with open(config_file_path, 'r', encoding='utf-8') as configfile:
     config.read_file(configfile)

    # Modify a key in the INI file
     config['Global']['topic_name'] = defined_ntfy_topic_name

    # Write the changes back to the INI file
    with open(config_file_path, 'w', encoding='utf-8') as configfile:
     config.write(configfile)

    globals()['config_tab1_approved'] = True
    check_all_steps_completed() 


  elif response == "Annuler":
    pass

def config_steps():
  mid_canvas.place_forget()
  school_name_text.place_forget()

  check_important_file_existence(wanted_file_type="config")

  # Read the INI file with the appropriate encoding
  with open(config_file_path, 'r', encoding='utf-8') as configfile:
    config.read_file(configfile)

  # Modify a key in the INI file
  config['Global']['student_fullname'] = nom_utilisateur
  config['Global']['student_firstname'] = user_first_name
  config['Global']['student_class'] = student_class_name


  # Write the changes back to the INI file
  with open(config_file_path, 'w', encoding='utf-8') as configfile:
    config.write(configfile)

  global tabview
  tabview = ctk.CTkTabview(master=root, height=195, width=450)
  tabview.pack(padx=20, pady=0)

  tabview.add("1. ntfy")
  tabview.add("2. Repas")
  tabview.add("3. Emojis")
  tabview.add("4. Avancé")

  tabview.set("1. ntfy")  # set currently visible tab
  close_button.tkraise()
  author_name_label.tkraise()

  global config_tab_step1_text
  config_tab_step1_text = ctk.CTkLabel(master=tabview.tab("1. ntfy"), text= f"Bonjour {user_first_name} !\nEnregistrez ici le nom de votre topic ntfy.")
  config_tab_step1_text.place(relx=0.5, rely=0.2, anchor="center")

  global ntfy_topic_name_entry
  ntfy_topic_name_entry = ctk.CTkEntry(master=tabview.tab("1. ntfy"), width=200)  
  ntfy_topic_name_entry.place(relx=0.5, rely=0.5, anchor="center")
  ntfy_topic_name_entry.bind("<Return>", lambda event: get_ntfy_topic())

  # Function to enable the button if entry is not empty
  def enable_button(event):
    if ntfy_topic_name_entry.get() and ntfy_topic_name_entry.get() != "mon-topic-ntfy":
        ntfy_topic_name_button.configure(state="normal", text_color="white")
    else:
        ntfy_topic_name_button.configure(state="disabled", text_color="grey")

  
  ntfy_topic_name_entry.insert(0, "mon-topic-ntfy")
  ntfy_topic_name_entry.bind("<FocusIn>", lambda event: ntfy_topic_name_entry.delete(0, ctk.END) if ntfy_topic_name_entry.get() == "mon-topic-ntfy" else None)
  ntfy_topic_name_entry.bind("<FocusOut>", lambda event: ntfy_topic_name_entry.insert(0, "mon-topic-ntfy") if not ntfy_topic_name_entry.get() else None)
  ntfy_topic_name_entry.bind("<KeyRelease>", enable_button)

  global ntfy_topic_name_button
  ntfy_topic_name_button = ctk.CTkButton(master=tabview.tab("1. ntfy"), text="Valider",command=get_ntfy_topic, state="disabled", text_color="grey")
  ntfy_topic_name_button.place(relx=0.5, rely=0.75, anchor="center")

  #TAB 2 LUNCH TIMES
         
  if not menus_found:
    config_tab_step2_text = ctk.CTkLabel(master=tabview.tab("2. Repas"), text="Votre établissement ne semble pas avoir défini\nle menu de la cantine dans Pronote...\n\nPassez cette étape.")
    config_tab_step2_text.place(relx=0.5, rely=0.5, anchor="center")

    globals()['config_tab2_approved'] = True
    check_all_steps_completed() 

  # Handling the case when a menu is found
  else:
    config_tab_step2_text = ctk.CTkLabel(master=tabview.tab("2. Repas"), text="Déplacez le curseur bleu pour définir vos horaires\nde déjeuner.")
    config_tab_step2_text.place(relx=0.5, rely=0.15, anchor="center")

    # Create labels and Scale widgets for each day
    days = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi"]
    labels = {}
    scales = {}
    lunch_times = {}
    global current_day_index
    current_day_index = 0  # Initialize current_day_index here

    def time_to_minutes(time):
        """Convert time in HH:MM format to minutes since 00:00."""
        hours, minutes = map(int, time.split(":"))
        return hours * 60 + minutes

    def minutes_to_time(minutes):
        """Convert minutes since 00:00 to time in HH:MM format."""
        hours = minutes // 60
        minutes = minutes % 60
        return f"{hours:02d}:{minutes:02d}"

    def submit_lunch_time():
        global current_day_index
        global day
        day = days[current_day_index]
        selected_minutes = int(scales[day].get())
        lunch_times[day] = minutes_to_time(selected_minutes)

        if current_day_index < len(days) - 1:
            # Hide the current day and move to the next day
            labels[day].place_forget()
            scales[day].place_forget()
            current_day_index += 1
            next_day = days[current_day_index]
            labels[next_day].place(relx=0.35, rely=0.3)
            scales[next_day].place(relx=0.5, rely=0.5, anchor="center")
        else:
            # Final submission
            scales[day].configure(state="disabled", progress_color="grey")
            submit_button.configure(state="disabled", text_color="grey")
            label.place_forget()
            config_tab_step2_text.configure(text="Vos paramètres ont étés enregistrés !\nPassez à la prochaine étape.")
            logger.debug(f"Lunch times submitted:\n{lunch_times}")

            french_to_english = {
                'lundi': 'Monday',
                'mardi': 'Tuesday',
                'mercredi': 'Wednesday',
                'jeudi': 'Thursday',
                'vendredi': 'Friday'
            }

            check_important_file_existence(wanted_file_type="config")

            # Read the INI file with the appropriate encoding
            with open(config_file_path, 'r', encoding='utf-8') as configfile:
                config.read_file(configfile)

            for french_day, time in lunch_times.items():
                english_day = french_to_english.get(french_day.lower())  # Translate French day to English
                if english_day:
                    config['LunchTimes'][english_day] = time

            # Write the changes back to the INI file
            with open(config_file_path, 'w', encoding='utf-8') as configfile:
                config.write(configfile)

            globals()['config_tab2_approved'] = True
            check_all_steps_completed()

    # Define the time range for lunch times (e.g., from 10:30 to 14:30 in 5-minute intervals)
    start_time = time_to_minutes("10:30")
    end_time = time_to_minutes("14:30")
    increment = 5  # 5 minutes increment

    for day in days:
        label = ctk.CTkLabel(master=tabview.tab("2. Repas"), text=f"{day} 12h30 (par défaut)")
        labels[day] = label

        scale = ctk.CTkSlider(master=tabview.tab("2. Repas"), from_=start_time, to=end_time, number_of_steps=(end_time - start_time) // increment)
        scales[day] = scale

        # Add a label to show the selected time
        def update_label(value, scale=scale, label=label, day=day):
            time = minutes_to_time(int(float(value)))
            label.configure(text=f"{day}: {time}h")

        scale.configure(command=lambda value, scale=scale, label=label, day=day: update_label(value, scale, label, day))

        # Show the Scale for the first day only
        labels[days[current_day_index]].place(relx=0.35, rely=0.3)
        scales[days[current_day_index]].place(relx=0.5, rely=0.5, anchor="center")

        # Create the submit button
        submit_button = ctk.CTkButton(master=tabview.tab("2. Repas"), text="Enregistrer", command=submit_lunch_time)
        submit_button.place(relx=0.5, rely=0.8, anchor="center")
  #TAB 3 EMOJIS

  config_tab_step3_text = ctk.CTkLabel(master=tabview.tab("3. Emojis"), text="La configuration des emojis arrivera dans une\nprochaine version.\n\n(Vous pouvez toujours le faire manuellement dans le\nfichier de configuration)")
  config_tab_step3_text.place(relx=0.5, rely=0.5, anchor="center")

  globals()['config_tab3_approved'] = True
  check_all_steps_completed()

  #TAB 4 ADVANCED

  def set_config_file_advanced():
    save_button.configure(state="disabled", text_color="grey")
    switch.configure(state="disabled", text_color="grey", button_color="grey")
    combo_menu.configure(state="disabled", button_color="grey")

    check_important_file_existence(wanted_file_type="config")
    config_tab_step4_text.configure(text="Votre fuseau horaire à bien été enregistré !") 
   
    # Read the INI file with the appropriate encoding
    with open(config_file_path, 'r', encoding='utf-8') as configfile:
     config.read_file(configfile)

    # Modify a key in the INI file
    config['Advanced']['timezone'] = selected_timezone

    # Write the changes back to the INI file
    with open(config_file_path, 'w', encoding='utf-8') as configfile:
     config.write(configfile)

    globals()['config_tab4_approved'] = True
    check_all_steps_completed()

    

  def switch_toggled():
    if switch_var.get() == "on":
        combo_menu.place_forget()
    else:
        combo_menu.place(relx=0.5, rely=0.55, anchor="center")

  def save_selection():
    global selected_timezone
    if switch_var.get() == "off":
        selected_option = combo_menu.get()
        if selected_option == "":
         logger.error("Value cannot be None !")
         box = CTkMessagebox(title="Erreur !", message="Vous devez choisir une valeur du menu avant de valider !", icon=warning_icon_path, option_1="Réessayer",master=root, width=350, height=10, corner_radius=20,sound=True)
         box.info._text_label.configure(wraplength=450)

        else:
          if selected_option == "UTC":
           selected_timezone = "UTC"
          else: 
           sign = selected_option[3]
           offset = selected_option[4:]

           # Invert the sign for the Etc/GMT format
           if sign == '+':
            etc_gmt_offset = f"-{offset}"
           elif sign == '-':
            etc_gmt_offset = f"+{offset}"
    
           selected_timezone = f"Etc/GMT{etc_gmt_offset}"
           logger.debug(f"New timezone has been selected : {selected_timezone}")
          set_config_file_advanced()
    else:
        
        selected_timezone = "Europe/Paris"
        logger.debug("Default timezone has been selected !")
        set_config_file_advanced()

  config_tab_step4_text = ctk.CTkLabel(master=tabview.tab("4. Avancé"), text="Au besoin changez le fuseau horaire utilisé.")
  config_tab_step4_text.place(relx=0.5, rely=0.15, anchor="center")

  # Add a switch (CTkSwitch)
  switch_var = ctk.StringVar(value="on")  # Set the switch to be enabled by default
  switch = ctk.CTkSwitch(master=tabview.tab("4. Avancé"), text="France (par défaut)", variable=switch_var, onvalue="on", offvalue="off", command=switch_toggled)
  switch.place(relx=0.5, rely=0.35, anchor="center")

  # Add a combobox
  options = ["UTC", "UTC+1", "UTC+2", "UTC+3", "UTC+4", "UTC+5", "UTC+6", "UTC+7", "UTC+8", "UTC+9", "UTC+10", "UTC+11", "UTC+12", "UTC-1", "UTC-2", "UTC-3", "UTC-4", "UTC-5", "UTC-6", "UTC-7", "UTC-8", "UTC-9", "UTC-10", "UTC-11", "UTC-12", "UTC-13", "UTC-14"]
  combo_menu = ctk.CTkComboBox(master=tabview.tab("4. Avancé"), values=options, state="readonly")
  combo_menu.place_forget()  # Initially hidden

  # Add a save button
  save_button = ctk.CTkButton(master=tabview.tab("4. Avancé"), text="Valider", command=save_selection)
  save_button.place(relx=0.5, rely=0.8, anchor="center")



def save_credentials():
    username = username_entry.get()
    password = password_entry.get()


    if not username or not password:
     logger.error("Missing Entrys")
     box = CTkMessagebox(title="Erreur !", message="Vous devez renseigner un mot de passe et un identifiant...", icon=warning_icon_path, option_1="Réessayer",master=root, width=350, height=10, corner_radius=20,sound=True)
     box.info._text_label.configure(wraplength=450)

    else: 
      root.config(cursor="watch")

      try:
       check_important_file_existence(wanted_file_type="config") 
      
       # Read the INI file with the appropriate encoding
       with open(config_file_path, 'r', encoding='utf-8') as configfile:
        config.read_file(configfile)

        if ent_connexion:
         
         module = importlib.import_module("pronotepy.ent")
         used_ent = getattr(module, used_ent_name, None)

         client = pronotepy.Client(pronote_url, username=username, password=password, ent=used_ent)

         # Modify a key in the INI file
         config['Global']['ent_used'] = "True"
         config['Global']['ent_name'] = used_ent_name
        else:
         client = pronotepy.Client(pronote_url, username=username, password=password)

         # Modify a key in the INI file
         config['Global']['ent_used'] = "False"
         config['Global']['ent_name'] = "None"

        # Write the changes back to the INI file
        with open(config_file_path, 'w', encoding='utf-8') as configfile:
         config.write(configfile)
           
        if client.logged_in:
         box = CTkMessagebox(title="Succès !", message="Connexion effectuée !", icon=ok_icon_path, option_1="Parfait", master=root, width=300, height=10, corner_radius=20,sound=True)
         box.info._text_label.configure(wraplength=450)

        
         today = datetime.date.today()
         fallback_dates = [
          datetime.date(2024, 4, 26),
          datetime.date(2024, 4, 27),
          datetime.date(2024, 4, 29),
          datetime.date(2024, 5, 29),
          datetime.date(2024, 5, 30),
          datetime.date(2024, 5, 31)
         ]
         global menus

         dates_to_check = [today] + fallback_dates

         global menus_found
         menus_found = False
         for date in dates_to_check:
          try:
           menus = client.menus(date_from=date)
           if menus:  # If a menu is found, break out of the loop
            menus_found = True
            break
          except KeyError:
            menus_found = False 
         
          
         global nom_utilisateur
         global student_class_name

         nom_utilisateur = client.info.name
         student_class_name = client.info.class_name

         logger.info(f'Logged in as {nom_utilisateur}')

         # Enregistrer le nom d'utilisateur et le mot de passe dans deux fichiers .env différents
         set_key(f"{script_directory}/Data/pronote_username.env", 'User', username)
         set_key(f"{script_directory}/Data/pronote_password.env", 'Password', password)

         global user_first_name
         user_first_name = nom_utilisateur.split()[-1] if nom_utilisateur.strip() else None

         root.config(cursor="arrow")

         # Effacer les champs après enregistrement
         username_entry.delete(0, 'end')
         password_entry.delete(0, 'end')

         username_label.place_forget()
         username_entry.place_forget()

         password_entry.place_forget()
         password_label.place_forget()

         save_button.place_forget()

         title_label.configure(text="")
         main_text.configure(text= "")

         config_steps()

      except (pronotepy.CryptoError, pronotepy.ENTLoginError):
         logger.warning("Wrong credentials !")
         box = CTkMessagebox(title="Erreur !", message="Vos identifiants de connexion semblent incorrects...", icon=warning_icon_path, option_1="Réessayer",master=root, width=300, height=10, corner_radius=20,sound=True)
         box.info._text_label.configure(wraplength=450)
         password_entry.delete(0, 'end')
         root.config(cursor="arrow")   


      except Exception as e:
         current_month = datetime.datetime.now().month
         if current_month == 7 or current_month == 8:
           
           logger.critical(f"Unknown error ! Month is {current_month}, perhaps service closure due to summer break ?\n{e}")
           box = CTkMessagebox(title="Erreur !", message="Une erreur inconnue est survenue...\n(Peut-être la fermeture estivale de Pronote ?)", icon=cancel_icon_path, option_1="Ok",master=root, width=400, height=10, corner_radius=20,sound=True)

         else:
            logger.critical(f"Unknown error ! Detail below :\n{e}")
            box = CTkMessagebox(title="Erreur !", message="Une erreur inconnue est survenue...\nVeuillez réessayer plus tard.", icon=cancel_icon_path, option_1="Ok",master=root, width=300, height=10, corner_radius=20,sound=True)

         box.info._text_label.configure(wraplength=450) 
         root.config(cursor="arrow")



def search_school():
    root.config(cursor="watch")

    city = city_entry.get()

    try:
     true_city_geocode = geolocator.geocode(city)
    except:
      box = CTkMessagebox(title="Erreur !", message="Une erreur inconnue est survenue...", icon=warning_icon_path, option_1="Réessayer",master=root, width=300, height=10, corner_radius=20,sound=True)
      box.info._text_label.configure(wraplength=450)
      root.config(cursor="arrow")
    
    if not true_city_geocode:
       logger.error("Unknow city !")
       box = CTkMessagebox(title="Erreur !", message="Cette ville ne semble pas exister...", icon=warning_icon_path, option_1="Réessayer",master=root, width=300, height=10, corner_radius=20,sound=True)
       box.info._text_label.configure(wraplength=450)
       root.config(cursor="arrow")

       city_entry.delete(0, "end")

    elif true_city_geocode:
     true_city_name = true_city_geocode.raw["name"]
     
     display_name = true_city_geocode.raw["display_name"]
     # Split the display name by comma
     display_name_parts = display_name.split(", ")
     # Get the last part which should be the country name
     country_name = display_name_parts[-1]
     logger.debug(country_name)

     if country_name != "France":
      city_entry.delete(0, "end")
      box = CTkMessagebox(title="Info", message=f"Pour le moment Pronote Class Notifier ne peut être utilisé que dans un établissement situé en France !", icon=info_icon_path, option_1="Ok",master=root, width=350, height=10, corner_radius=20,sound=True)
      box.info._text_label.configure(wraplength=450)
      root.config(cursor="arrow")

     else:
      city_entry.delete(0, "end")
      if ("Marseille" in true_city_name) and "Arrondissement" not in true_city_name:  
       box = CTkMessagebox(title="Info", message=f"Pour Marseille merci de spécifier l'arrondissement en entier !\nExemple : Marseille 1er Arrondissement, Marseille 2e Arrondissement,", icon=info_icon_path, option_1="Réessayer",master=root, width=350, height=15, corner_radius=20,sound=True)
       box.info._text_label.configure(wraplength=450)
       root.config(cursor="arrow")

      elif ("Paris" in true_city_name or "Lyon" in true_city_name) and "Arrondissement" not in true_city_name:
       box = CTkMessagebox(title="Info", message=f"Pour {true_city_name} merci de spécifier l'arrondissement !\nExemple : {true_city_name} 19e, {true_city_name} 20e, {true_city_name} 1er", icon=info_icon_path, option_1="Réessayer",master=root, width=350, height=10, corner_radius=20,sound=True)
       box.info._text_label.configure(wraplength=450)
       root.config(cursor="arrow")

      else:
       search_button.configure(state="disabled", text_color="grey")
       if "Arrondissement" in true_city_name:
         # Define the pattern to match
         pattern = r'(\d+e)\s+(Arrondissement)' or r'(\d+er)\s+(Arrondissement)'

         # Replace the matched pattern with a space between the number and "Arrondissement"
         true_city_name = re.sub(pattern, r'\1  \2', true_city_name)

       url = "https://data.education.gouv.fr/api/explore/v2.1/catalog/datasets/fr-en-adresse-et-geolocalisation-etablissements-premier-et-second-degre/records"

       # Define query parameters
       limit = 30
       params = {
          "limit": 30,
          "refine": [
              f"libelle_commune:{true_city_name}",
              "nature_uai_libe:COLLEGE",
              "nature_uai_libe:LYCEE ENSEIGNT GENERAL ET TECHNOLOGIQUE",
              "nature_uai_libe:LYCEE POLYVALENT",
              "nature_uai_libe:LYCEE PROFESSIONNEL"
              "nature_uai_libe:LYCEE CLIMATIQUE"
              "nature_uai_libe:LYCEE EXPERIMENTAL"
              "nature_uai_libe:LYCEE ENS GENERAL TECHNO PROF AGRICOLE"
          ]
        }

       # Make the GET request
       response = requests.get(url, params=params)

       # Check if the request was successful (status code 200)
       if response.status_code == 200:
          # Parse the JSON response
          data = response.json()

          results_number = data["total_count"]

          if results_number == 0:
           logger.error("No results for the city !")
           box = CTkMessagebox(title="Aucun résultat", message="Il ne semble pas y avoir de collèges ou lycées pris en charge dans cette ville...", icon=warning_icon_path, option_1="Réessayer",master=root, width=350, height=10, corner_radius=20,sound=True)
           box.info._text_label.configure(wraplength=450)

          else: 
           results_count = data["total_count"]

           appellation_officielle_values = []
           for record in data['results']:
              appellation_officielle = record['appellation_officielle']
              appellation_officielle_values.append(appellation_officielle)

           logger.info(f"{results_count} results have been returned for {true_city_name} ! (limit is {limit})")  


           def optionmenu_callback(choice):

            root.config(cursor="watch")
            
            url = "https://data.education.gouv.fr/api/explore/v2.1/catalog/datasets/fr-en-adresse-et-geolocalisation-etablissements-premier-et-second-degre/records"

            # Define query parameters
            params = {
            "limit": 10,
            "refine": [
               f"appellation_officielle:{choice}",
               f"libelle_commune:{true_city_name}",

             ]
           }

            # Make the GET request
            response = requests.get(url, params=params)

            # Check if the request was successful (status code 200)
            if response.status_code == 200:
             # Parse the JSON response
             data = response.json()

             uai_number = data["results"][0]["numero_uai"]

             global departement_code
             global region_name
             global school_type

             departement_code = data["results"][0]["code_departement"]
             region_name = data["results"][0]["libelle_region"]
             school_type = data["results"][0]["nature_uai_libe"]

             global pronote_url
             pronote_url = f"https://{uai_number}.index-education.net/pronote/eleve.html"
       
             check_important_file_existence(wanted_file_type="config")

             # Read the INI file with the appropriate encoding
             with open(config_file_path, 'r', encoding='utf-8') as configfile:
              config.read_file(configfile)

             config["Global"]["login_page_link"] = pronote_url

             # Write the changes back to the INI file
             with open(config_file_path, 'w', encoding='utf-8') as configfile:
              config.write(configfile) 

             pronote_use = True
             pronote_use_msg = None
             try:
             
              response = requests.get(pronote_url, allow_redirects=False)

             except requests.exceptions.ConnectionError:
               pronote_use = False
               pronote_use_msg = "DNS Error"


             except Exception as e:

              pronote_use_msg = str(e)

              pronote_use = False

             # Handle any other unexpected errors  
             if pronote_use and not pronote_use_msg and response.status_code == 200:
               logger.info(f"{choice} ({true_city_name}) uses Pronote !")

               global used_ent_name
               used_ent_name = None

               global ent_connexion
               ent_connexion = False

               choice_menu.place_forget()
               root.config(cursor="arrow")
               
               
             
               title_label.configure(text="Etape 3/4")
               main_text.configure(text=f"Connectez vous à Pronote\nà l'aide de vos identifiants.")

               def adjust_text_size(event=None):
                # Get the current text of the label
                text = school_name_text.cget("text")
                # Calculate the length of the text
                text_length = len(text)
                # Adjust font size based on text length
                font_size = max(10, 12 - text_length // 10)  # Adjust the formula as needed
                # Update the font size of the label
                school_name_text.configure(font=("Roboto", font_size))

               global password_visible
               password_visible = None
               # Function to toggle the password visibility
               def toggle_password(event=None):
                    global password_visible
                    if password_visible:
                        logger.debug("Password has been hidden !") # Debugging line
                        password_entry.configure(show="*")  # Hide password
                        password_eye_button.configure(image=closed_eye_image)  # Change the eye icon to closed
                        
                        password_visible = False
                    else:
                        logger.debug("Password is being shown !")  # Debugging line
                        password_entry.configure(show="")  # Show password
                        password_eye_button.configure(image=open_eye_image)  # Change the eye icon to open
                        password_visible = True

               # Load the images for the eye icons (ensure correct paths to your image files)
               closed_eye_image = ctk.CTkImage(light_image=Image.open("Icons/Global UI/closed_eye_light.png").resize((24, 24)), dark_image=Image.open("Icons/Global UI/closed_eye_dark.png").resize((24, 24)))
               open_eye_image = ctk.CTkImage(light_image=Image.open("Icons/Global UI/open_eye_light.png").resize((24, 24)), dark_image=Image.open("Icons/Global UI/open_eye_dark.png").resize((24, 24)))
                
               global school_name_text
               school_name_text = ctk.CTkLabel(root, text=f"{choice}", font=(default_subtitle_font))
               school_name_text.place(relx=0.23, rely=0.65, anchor="center")

               # Bind the label to the adjust_text_size function
               school_name_text.bind("<Configure>", adjust_text_size)

               # Création des labels
               global username_label
               username_label = ctk.CTkLabel(root, text="Identifiant", font=(default_subtitle_font))
               username_label.place(relx=0.71, rely=0.23, anchor="center")

               global password_label
               password_label = ctk.CTkLabel(root, text="Mot de passe", font=(default_subtitle_font))
               password_label.place(relx=0.71, rely=0.52, anchor="center")

               # Création des champs de saisie
               global username_entry
               username_entry = ctk.CTkEntry(root, width=150, placeholder_text="Nom d'utilisateur")
               username_entry.place(relx=0.71, rely=0.35, anchor="center")

               global password_entry
               password_entry = ctk.CTkEntry(root, width=150, height=35, show="*", placeholder_text="Mot de passe")
               password_entry.place(relx=0.71, rely=0.65, anchor="center")
               password_entry.bind("<Return>", lambda event: save_credentials())

               # Bouton pour afficher/masquer le mot de passe avec événements de clic
               global password_eye_button
               password_eye_button = ctk.CTkButton(root,width=1, height=10 ,image=closed_eye_image, text="", fg_color=["#f9f9fa", "#343638"], bg_color=["#f9f9fa", "#343638"], hover_color=["#f9f9fa", "#343638"])
               password_eye_button.place(relx=0.85, rely=0.65, anchor="center")

               # Bind left mouse button click to toggle password visibility
               password_eye_button.bind("<Button-1>", toggle_password)
                                
               # Create the save button with the lock icon
               global save_button
               save_button = ctk.CTkButton(root, text="Connexion", command=save_credentials)
               save_button.place(relx=0.71, rely=0.83, anchor="center")

             else:

               if pronote_use_msg == "DNS Error":
                 logger.warning(f"{choice} ({true_city_name}) doesn't seem to use Pronote... See below\nWebsite {pronote_url} does not exists. {pronote_use_msg}")
                 box = CTkMessagebox(title="Aucun résultat", message="Votre établissement ne semble pas utiliser Pronote.", icon=warning_icon_path, option_1="Ok",master=root, width=350, height=10, corner_radius=20,sound=True)
                 box.info._text_label.configure(wraplength=450)
                 root.config(cursor="arrow")

               elif response != 202 and not pronote_use_msg:

                api_response = { 
                 "region": f"{region_name}",
                 "departement": f"{departement_code}",
                 "type": f"{school_type}"
                }

                check_important_file_existence(wanted_file_type="ent_data")

                # Load the JSON file
                with open(f"{script_directory}/Data/ent_data.json", 'r') as file:
                 data = json.load(file)

                # Count the number of correspondences between the API response and each option except variable_name
                correspondence_counts = {}
                for option_key, option_value in data.items():
                 # Count correspondences for all options except variable_name
                 count = sum(api_response[arg] == option_value[arg] for arg in api_response.keys())

                 # Check if any of the departments match
                 option_departements = option_value["departement"]
                 if isinstance(option_departements, list):

                  departement_count = any(dept in api_response["departement"] for dept in option_departements)

                 else:
                  # Split the department string into individual codes
                  option_departements = option_departements.split(", ")
                  # Check if any of the individual departments match
                  departement_count = any(dept in api_response["departement"] for dept in option_departements)

                 type_match_lycee = False
                 if api_response["type"].startswith("LYCEE") and option_value["type"] == "LYCEE":
                  type_match_lycee = True

                 type_match_clg = False
                 if api_response["type"].startswith("COLLEGE"):
                  type_match_clg = True 

                 correspondence_counts[option_key] = count + departement_count + type_match_lycee + type_match_clg

                # Choose the option with the highest correspondence
                chosen_option = max(correspondence_counts, key=correspondence_counts.get)

                # Print the chosen option key and its associated variable_name
                
                used_ent_name = data[chosen_option]["variable_name"]

                # ENT Connexion

                logger.debug(f"{choice} ({true_city_name}) uses Pronote (ENT Conexion: {used_ent_name}) !")

                ent_connexion = True

                choice_menu.place_forget()
                root.config(cursor="arrow")

                title_label.configure(text="Etape 3/4")
                main_text.configure(text=f"Connectez vous à Pronote\nà l'aide de vos identifiants.")

                def adjust_text_size(event=None):
                 # Get the current text of the label
                 text = school_name_text.cget("text")
                 # Calculate the length of the text
                 text_length = len(text)
                 # Adjust font size based on text length
                 font_size = max(10, 12 - text_length // 10)  # Adjust the formula as needed
                 # Update the font size of the label
                 school_name_text.configure(font=("Roboto", font_size))
                
               
                school_name_text = ctk.CTkLabel(root, text=f"{choice}", font=(default_subtitle_font))
                school_name_text.place(relx=0.23, rely=0.65, anchor="center")

                # Bind the label to the adjust_text_size function
                school_name_text.bind("<Configure>", adjust_text_size)

                # Création des labels
                username_label = ctk.CTkLabel(root, text="Identifiant", font=(default_subtitle_font)) #CHANGE ALL FONTS TO ROBOTO (BOLD)
                username_label.place(relx=0.75, rely=0.23, anchor="center")

                password_label = ctk.CTkLabel(root, text="Mot de passe", font=(default_subtitle_font))
                password_label.place(relx=0.75, rely=0.53, anchor="center")

                # Création des champs de saisie
                username_entry = ctk.CTkEntry(root, width=150)
                username_entry.place(relx=0.75, rely=0.35, anchor="center")

                password_entry = ctk.CTkEntry(root, width=150, show="*")
                password_entry.place(relx=0.75, rely=0.65, anchor="center")

                # Création du bouton d'enregistrement
                save_button = ctk.CTkButton(root, text="Connexion", command=save_credentials)
                save_button.place(relx=0.75, rely=0.83, anchor="center")

                 
               else:
                logger.critical(response)
                logger.critical(f"Unknown error for {pronote_url}\nError detail : {pronote_use_msg}")
                box = CTkMessagebox(title="Erreur", message="Une erreur inconnue est survenue.\nMerci de réessayer plus tard.", icon=cancel_icon_path, option_1="Ok",master=root, width=350, height=10, corner_radius=20,sound=True)
                box.info._text_label.configure(wraplength=450)

           title_label.configure(text="Etape 2/4")
           main_text.configure(text="Selectionnez \nvotre établissement.")

           # Create a StringVar to store the selected option
           default_choice_menu_var = ctk.StringVar(value="Selectionnez votre établissement")

           # Create the OptionMenu with dynamic width
           choice_menu = ctk.CTkOptionMenu(root, width=175, dynamic_resizing=False, values=appellation_officielle_values, variable=default_choice_menu_var, command=optionmenu_callback)
           choice_menu.place(relx=0.75, rely=0.4, anchor="center")

           search_button.place_forget()
           city_entry.place_forget()

           root.config(cursor="arrow")

       else:
          # If the request was not successful, print an error message
          logger.error("Error:", response.status_code)
          return []

# Create the main window
root = ctk.CTk()
root.geometry("400x200")
root.resizable(False, False)
root.title("Configuration Pronote Class Notifier")

#wanted file type can be : ico, config, ent_data, pronote_password or pronote_username

check_important_file_existence(wanted_file_type="ico")


root.iconbitmap(f"{script_directory}/pronote_butterfly.ico")

ctk.set_appearance_mode("System")

title_bar_color.set(root, "#16a376")
window_frame.center(root)

def close_app():
  box = CTkMessagebox(title="Fermer ?", message="Annuler la configuration ?\nL'ensemble de vos données sera supprimé...", icon=question_icon_path, option_1="Annuler", option_2="Fermer",cancel_button=None ,cancel_button_color="light grey", justify="center", master=root, width=350, height=10, corner_radius=20,sound=True)
  box.info._text_label.configure(wraplength=450)


  response = box.get()

  if response == "Fermer":
    logger.debug("Window is closing removing data...")

    # List of file paths to delete
    files_to_delete = [
     os.path.join(script_directory, "Data", "config.ini"),
     os.path.join(script_directory, "Data", "pronote_password.env"),
     os.path.join(script_directory, "Data", "pronote_username.env")
    ]
    deleted_files_count = 0

    # Attempt to delete each file
    for file_path in files_to_delete:
     try:
        os.remove(file_path)
        deleted_files_count += 1
     except FileNotFoundError:
        logger.error(f"File {file_path} not found.")
     except PermissionError:
        logger.warning(f"Permission denied to delete {file_path}.")
     except Exception as e:
        logger.critical(f"An error occurred while trying to delete {file_path}: {e}")

    logger.debug(f"{deleted_files_count} files out of 3 deleted")

    time.sleep(0.1)
    root.destroy()
    logger.info("Window has been closed !")
    sys.exit(0)
    
  elif response == "Annuler":
    pass

def check_internet():
    """Check if the computer is connected to the internet."""
    url = "http://www.google.com"
    timeout = 5
    try:
        response = requests.get(url, timeout=timeout)
        return True
    except requests.ConnectionError:
        return False

previously_connected = False

def update_internet_label_state():
    global previously_connected

    currently_connected = check_internet()
    
    if currently_connected and not previously_connected:
        def change_text():
            internet_status_label.configure(text="De retour en ligne...", text_color="green")
            root.after(2000, clear_text)  # Wait 2 seconds before clearing the text

        def clear_text():
            internet_status_label.configure(text="")
        
        change_text()  # Call the change_text function to update the label and start the timer
        search_button.configure(state="normal")
        
    elif not currently_connected:
        internet_status_label.configure(text="Pas de connexion à Internet !", text_color="#ed3f28")
        search_button.configure(state="disabled")
    
    previously_connected = currently_connected  # Update the previous state
        

    root.after(1000, update_internet_label_state)

def on_label_click(event):
    global click_count
    click_count += 1
    if click_count == 8:
       webbrowser.open_new_tab("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
       logger.critical("Easter egg discovered !")

click_count = 0

def check_if_first_time():
  first_use_file = os.path.exists(f"{script_directory}/first_use.txt")

  if first_use_file:
    logger.info("Initial Startup !")
    box = CTkMessagebox(title="Premiere fois ici ?", message=f"On dirait que vous n'avez jamais utilisé Pronote Class Notifier...\n\nLisez la documentation pour mieux comprendre comment vous en servir.", icon=info_icon_path, option_1="D'accord", cancel_button=None ,cancel_button_color="light grey", justify="center", master=root, width=450, height=10, corner_radius=20)
    box.info._text_label.configure(wraplength=450)
    webbrowser.open_new_tab("https://github.com/TGA25dev/Pronote-Class-Notifier/wiki/Accueil")
    os.remove(f"{script_directory}/first_use.txt")

  else:
    logger.info("Not first startup...")


# Create a title label
title_label = ctk.CTkLabel(root, text="Etape 1/4", font=(default_title_font))
title_label.place(relx=0.5, rely=0.1, anchor="center")

#Create name label
global author_name_label
author_name_label = ctk.CTkLabel(root, text="TGA25dev | ©2024", font=(default_credit_font), bg_color="transparent")
author_name_label.place(relx=0.77, rely=0.89)
author_name_label.bind("<Button-1>", on_label_click)

# Create a Canvas widget to draw the line

mid_canvas = ctk.CTkCanvas(root, width=2, height=190, background= "white", highlightthickness=0)
mid_canvas.place(relx=0.5, rely=0.55, anchor="center")

# Create main text label
main_text = ctk.CTkLabel(root, text="Recherchez ici la ville\n  de votre établissement.", font=(default_text_font))
main_text.place(relx=0.23, rely=0.45, anchor="center")

# Create city entry widget
city_entry = ctk.CTkEntry(root, width=150)
city_entry.place(relx=0.75, rely=0.4, anchor="center")
city_entry.bind("<Return>", lambda event: search_school())

# Create search button
global search_button
search_button = ctk.CTkButton(root, text="Chercher", command=search_school) 
search_button.place(relx=0.75, rely=0.6, anchor="center")

#Create internet status label
internet_status_label = ctk.CTkLabel(root, text="Checking connection...")
internet_status_label.place(relx=0.75, rely=0.8, anchor="center")

#Create close button
close_button = ctk.CTkButton(root, text="Fermer",command=close_app, width=15, hover_color="red")
close_button.place(relx=0.01, rely=0.98, anchor="sw")

root.protocol("WM_DELETE_WINDOW", close_app)

check_if_first_time()
update_internet_label_state()

#Start main loop
root.mainloop()
