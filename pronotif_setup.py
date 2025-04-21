import customtkinter as ctk
from customtkinter import *
from CTkMessagebox import CTkMessagebox
from CTkToolTip import *
from hPyT import *
import tkinter as tk
import qrcode
import io
import pyglet
from pathlib import Path
import pronotepy
import requests
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
import time
import pytz
import datetime
from dotenv import set_key
import re
import sys
import json
import os
import webbrowser
import configparser
import base64
from win11toast import notify
import traceback
import random
from loguru import logger
import sentry_sdk
from PIL import Image, ImageGrab, ImageTk
from ctypes import windll
from pyzbar.pyzbar import decode
from uuid import uuid4
import cv2


# Create a ConfigParser object
config = configparser.ConfigParser()

default_font_style = "Fixel Text Medium", 16
default_font_name = "Fixel Text Medium"

default_title_font = ("Fixel Display Bold", 28)

default_messagebox_font = ("Fixel Text Medium", 18)
default_items_font = ("Fixel Text Regular", 17)
default_text_font = ("Fixel Text Medium", 17)
default_config_step_font = ("Fixel Text Medium", 16)
default_subtitle_font = ("Fixel Text Medium", 15)
default_conditions_font = ("Fixel Text Medium", 13)

geolocator = Nominatim(user_agent="Geocoder")

script_directory = os.path.dirname(os.path.abspath(__file__))

cancel_icon_path = f"{script_directory}/Icons/Messagebox UI/cancel_icon.png"
ok_icon_path = f"{script_directory}/Icons/Messagebox UI/ok_icon.png"
question_icon_path = f"{script_directory}/Icons/Messagebox UI/question_icon.png"
warning_icon_path = f"{script_directory}/Icons/Messagebox UI/warning_icon.png"
info_icon_path = f"{script_directory}/Icons/Messagebox UI/info_icon.png"

github_repo_name = "TGA25dev/Pronotif"
version = "v0.8"

sentry_sdk.init("https://8c5e5e92f5e18135e5c89280db44a056@o4508253449224192.ingest.de.sentry.io/4508253458726992", 
                enable_tracing=True,
                traces_sample_rate=1.0,
                environment="production",
                release=version,
                server_name="User-Machine")

local_paths = {
    "ico": os.path.join(script_directory, "pronote_butterfly.ico"),
    "ent_data": os.path.join(script_directory, "Data", "ent_data.json"),
    "env_p": os.path.join(script_directory, "Data", "pronote_password.env"),
    "env_u": os.path.join(script_directory, "Data", "pronote_username.env")
}

github_paths = {
    "ico": "pronote_butterfly.ico",
    "ent_data": "Data/ent_data.json",
    "env_p": "Data/pronote_password.env",
    "env_u": "Data/pronote_username.env"
}

# Adding custom colors and format to the logger
logger.remove()  # Remove any existing handlers

# Add logging to the console (only if a console exists)
if hasattr(sys, "stdout") and sys.stdout is not None:
    logger.add(sys.stdout, level="DEBUG")

# Add logging to a file with rotation
logger.add("setup_wizard_logs.log", level="DEBUG", rotation="500 MB")

# Global exception handler
def handle_exception(exc_type:str, exc_value:str, exc_traceback:str) -> None:
  """
  Handle uncaught exceptions log them and send them to Sentry.
  """
  if issubclass(exc_type, KeyboardInterrupt):
      # Handle KeyboardInterrupt gracefully
      sys.__excepthook__(exc_type, exc_value, exc_traceback)
      return

  # Send exception to Sentry
  sentry_sdk.capture_exception((exc_type, exc_value, exc_traceback))

  logger.critical(
      f"Uncaught exception: {exc_value}\n"
      f"Traceback: {''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))}"
  )

# Set the global exception handler
sys.excepthook = handle_exception

class SystemData: #System related data (needed for the system to work but not saved or sent to the server.)
    def __init__(self):
      self.true_city_name = None
      self.departement_code = None
      self.region_name = None
      self.country_name = None
      self.school_type = None
      self.automatic_school_timezone = None
      self.qrcode_data = None
      self.scan_qr_code_method = None
      self.international_use = None

system_data = SystemData()      
       
class ConfigData:
    def __init__(self):
        #Main data
        self.pronote_url = None
        self.student_fullname = None
        self.student_firstname = None
        self.student_class_name = None
        self.user_password = None
        self.user_username = None
        self.ent_connexion = None
        self.notification_delay = None
        self.uuid = None
        self.qr_code_login = None

        #Lunch times
        self.lunch_times = {
            "Monday": None,
            "Tuesday": None,
            "Wednesday": None,
            "Thursday": None,
            "Friday": None,
        }
        self.evening_menu = None

        #Advanced
        self.selected_timezone = None
        self.unfinished_homework_reminder = None
        self.get_bag_ready_reminder = None

config_data = ConfigData()

#wanted file type can be : ico, ent_data, pronote_password or pronote_username

def check_important_file_existence(wanted_file_type:str) -> None:
  """
  Check if the file exists in the local directory. If not, download it from the GitHub repo or create it.
  """

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

def get_timezone(true_city_geocode:Nominatim) -> None:
  """
  Get the timezone of the user's city using the geocode and set data class.
  """
  tf = TimezoneFinder()
  timezone_str = tf.timezone_at(lng=true_city_geocode.longitude, lat=true_city_geocode.latitude)
  system_data.automatic_school_timezone = pytz.timezone(timezone_str)

def app_final_closing():
  """
  Close the application after the setup has been completed.
  """

  root.config(cursor="watch")
  final_app_close_button.configure(state="disabled", text_color="grey")
  logger.debug("Setup has been fully completed ! Application will now close....")
  logger.info("Made with ❤️ by the Pronot'if Team.")
  time.sleep(1.5)
  sys.exit(0)

def show_config_data_qr_code():
  """
  Show the QR code containing the configuration data
  """

  #Get a session id
  response = None
  try:
    response = requests.post("https://api.pronotif.tech/v1/setup/session")
    if response.status_code == 200:
      session_id = response.json()["session_id"]
      token = response.json()["token"]
      logger.debug(f"New session created with ID: {session_id}")
    else:
      logger.error(f"Failed to create session. Status code: {response.status_code}")
      sentry_sdk.capture_exception(Exception(f"Failed to create session. Status code: {response.status_code}"))
      session_id = None

  except Exception as e:
    logger.error(f"Failed to create session. Error: {e}")

    if "getaddrinfo failed" not in str(e):
      sentry_sdk.capture_exception(e)

    session_id = None

  if session_id is None:
    if response and (response.text or response.status_code is not None):
      box = CTkMessagebox(title=f"{response.status_code}: {response.text}", font=default_messagebox_font, message="Une erreur est survenue !\nVerifiez que vous êtes connecté à Internet.", icon=warning_icon_path, option_1="Annuler", option_2="Réessayer", master=root, width=400, height=180, corner_radius=25, sound=True)
    else:
      box = CTkMessagebox(title=f"Erreur !", font=default_messagebox_font, message="Une erreur est survenue !\nVerifiez que vous êtes connecté à Internet.", icon=warning_icon_path, option_1="Annuler", option_2="Réessayer", master=root, width=400, height=180, corner_radius=25, sound=True)
    box.info._text_label.configure(wraplength=450)

    response = box.get()
    if response == "Réessayer":
      show_config_data_qr_code()

  elif session_id:  
    logger.success(session_id)
    # Prepare QR data
    qr_config_data = {
      "session_id": str(session_id),
      "token": str(token),
      "login_page_link": str(config_data.pronote_url),
      "student_username": str(config_data.user_username),
      "student_password": str(config_data.user_password),
      "student_fullname": str(config_data.student_fullname),
      "student_firstname": str(config_data.student_firstname),
      "student_class": str(config_data.student_class_name),
      "ent_used": "1" if config_data.ent_connexion else "0",
      "qr_code_login": "1" if config_data.qr_code_login else "0",
      "uuid": str(config_data.uuid),
      "timezone": str(config_data.selected_timezone),
      "notification_delay": str(config_data.notification_delay),
      "lunch_times": str(config_data.lunch_times),
      "evening_menu": "1" if config_data.evening_menu else "0",
      "unfinished_homework_reminder": "1" if config_data.unfinished_homework_reminder else "0",
      "get_bag_ready_reminder": "1" if config_data.get_bag_ready_reminder else "0"
    }
    qr_config_data_json = json.dumps(qr_config_data)

    download_page_qr_img_label.place_forget()
    final_2nd_step.place_forget()
    show_config_qr_code_button.place_forget()
    close_button.place_forget()
    
    main_text.configure(text="Voici votre QR Code de configuration,\nscannez le dans l'application mobile.", font=default_config_step_font)
    main_text.place(relx=0.3, rely=0.4, anchor="center")

    warning_text_label = ctk.CTkLabel(master=root, text="Ne partagez jamais ce QR Code,\nil contient des informations sensibles !", font=(default_font_name, 13, "underline"))
    warning_text_label.place(relx=0.3, rely=0.5, anchor="center")

    global final_app_close_button
    final_app_close_button = ctk.CTkButton(master=root, text="Terminer", font=default_items_font, command=app_final_closing, corner_radius=10, width=200, height=45)
    final_app_close_button.place(relx=0.31, rely=0.7, anchor="center")
    
    # Create a QR code object
    config_data_qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,  
        border=4,
    )
    config_data_qr.add_data(qr_config_data_json)
    config_data_qr.make(fit=True)

    # Convert QR code to image
    img_bytes = io.BytesIO()
    config_data_qr.make_image(fill_color="black", back_color="white").save(img_bytes, format="PNG")
    img_bytes.seek(0)
    pil_img = Image.open(img_bytes)

    # Convert the PIL image to a CTkImage
    img_tk = CTkImage(light_image=pil_img, size=(250, 250))

    # Place QR code on the right
    config_qr_label = ctk.CTkLabel(master=root, image=img_tk, text="")
    config_qr_label.image = img_tk
    config_qr_label.place(relx=0.75, rely=0.5, anchor="center")

   

def final_step():
  """
  Show the final step of the setup wizard.
  """

  logger.info("All steps have been succesfully completed !")
  tabview.pack_forget()

  main_text.configure(text="1. Scannez ce QR Code depuis votre smartphone\npour installer l'application mobile !", font=default_config_step_font)
  main_text.place(relx=0.5, rely=0.15, anchor="center")

  global download_page_qr
  download_page_qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=1)
  download_page_qr.add_data("https://pronotif.tech/download?step2")
  download_page_qr.make(fit=True)

  img_bytes = io.BytesIO()
  download_page_qr.make_image(fill_color="black", back_color="white").save(img_bytes, format="PNG")
  img_bytes.seek(0)
  pil_img = Image.open(img_bytes)

  # Convert the PIL image to a CTkImage
  download_page_qr_img_tk = CTkImage(light_image=pil_img, size=(150, 150))

  # Place QR code
  global download_page_qr_img_label
  download_page_qr_img_label = ctk.CTkLabel(master=root, image=download_page_qr_img_tk, text="")
  download_page_qr_img_label.image = download_page_qr_img_tk
  download_page_qr_img_label.place(relx=0.5, rely=0.45, anchor="center")

  global final_2nd_step
  final_2nd_step = ctk.CTkLabel(master=root, text="2. Ensuite, suivez les instructions dans l'application.", font=default_config_step_font)
  final_2nd_step.place(relx=0.5, rely=0.73, anchor="center")

  global show_config_qr_code_button
  show_config_qr_code_button = ctk.CTkButton(master=root, text="Afficher le QR Code de configuratin", font=default_items_font, command=show_config_data_qr_code, corner_radius=10, width=350, height=45)
  show_config_qr_code_button.place(relx=0.5, rely=0.85, anchor="center")

  show_config_data_qr_code_tooltip = CTkToolTip(show_config_qr_code_button, message="Ne cliquez pas ici avant d'avoir installé l'application !", delay=0, alpha=0.8, wraplength=450, justify="center", font=default_subtitle_font)	

steps = ['config_tab1_approved', 'config_tab2_approved', 'config_tab3_approved']

for step in steps:
    if step not in globals():
        globals()[step] = False

def config_steps():
  """
  Show the configuration steps for the setup wizard.
  """

  mid_canvas.place_forget()

  if school_name_text is not None: # If the label exists
    school_name_text.place_forget()


  class VerticalTabView(ctk.CTkFrame):
      def __init__(self, master, **kwargs):
          if "height" in kwargs:
              del kwargs["height"]
          if "width" in kwargs:
              del kwargs["width"]
              
          super().__init__(master, **kwargs)
          
          self.tab_frame = ctk.CTkFrame(self, width=250, fg_color=("#e0e0e0", "#2b2b2b"))
          self.tab_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
          
          # Add title
          self.settings_label = ctk.CTkLabel(self.tab_frame, text="Paramètres", 
                                            font=("Fixel Display Bold", 22),
                                            anchor="center")
          self.settings_label.pack(pady=(25, 30), padx=5)
          
          self.content_frame = ctk.CTkFrame(self)
          self.content_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
          
          self.grid_columnconfigure(1, weight=4)
          self.grid_rowconfigure(0, weight=1)

          self.SELECTED_COLOR = "#3a86ff"
          self.NORMAL_COLOR = ("#d0d0d0", "#3b3b3b") #Default colors
          self.HOVER_COLOR = ("#c0c0c0", "#4b4b4b")
          
          #Frame creation
          self.buttons_container = ctk.CTkFrame(self.tab_frame, fg_color="transparent")
          self.buttons_container.pack(fill="both", expand=True, padx=5, pady=5)
          
          self.tabs = {}
          self.buttons = {}
          self.current_tab = None
      
      def add(self, name:str) -> ctk.CTkFrame:
          """
          Add a new tab with the given name.
          """

          tab = ctk.CTkFrame(self.content_frame, corner_radius=10)
          self.tabs[name] = tab
          
          btn = ctk.CTkButton(
              self.buttons_container, 
              text=name,
              command=lambda n=name: self.set(n),
              corner_radius=8,
              height=65,
              width=230,
              anchor="w",
              font=default_items_font,
              fg_color=self.NORMAL_COLOR,
              text_color=("#000000", "#ffffff"),
              hover_color=self.HOVER_COLOR,
          )

          btn.pack(fill="x", pady=(0, 12), padx=5)
          self.buttons[name] = btn
          
          return tab
          
      def set(self, name:str) -> None:
          """
          Set the currently visible tab to the one with the given name.
          """

          # Hide all tabs first
          for tab_name, tab in self.tabs.items():
              tab.place_forget()
              if tab_name != name: 
                  self.buttons[tab_name].configure(
                      fg_color=self.NORMAL_COLOR,
                      text_color=("#000000", "#ffffff")
                  )
          
          # Show the selected tab
          if name in self.tabs:
              self.tabs[name].place(relx=0, rely=0, relwidth=1, relheight=1)
              # Change color of selected button
              self.buttons[name].configure(
                  fg_color=self.SELECTED_COLOR,
                  hover_color=self.SELECTED_COLOR,
                  text_color=("#FFFFFF", "#FFFFFF")
              )
              self.current_tab = name

      def tab(self, name):
          """
          Get the tab with the given name.
          """

          if name in self.tabs:
              return self.tabs[name]
          else:
              raise ValueError(f"Tab {name} does not exist")
              
      def get_next_tab(self, current_tab_name):
          """
          Get the next tab name based on the current tab
          """

          tab_names = list(self.tabs.keys())
          try:
              current_index = tab_names.index(current_tab_name)
              if current_index < len(tab_names) - 1:
                  return tab_names[current_index + 1]
          except ValueError:
              pass
          return None
          
  global tabview
  tabview = VerticalTabView(master=root)
  tabview.pack(padx=20, pady=(20, 60), fill="both", expand=True)

  tabview.add("1. Notifications")
  tabview.add("2. Repas")
  tabview.add("3. Avancé")

  tabview.set("1. Notifications")  # set currently visible tab
  close_button.tkraise()
  author_name_label.tkraise()

  #TAB 2 LUNCH TIMES
         
  if not menus_found:
    config_tab_step2_text = ctk.CTkLabel(master=tabview.tab("2. Repas"), text="Votre établissement ne semble pas être compatible\navec de cette fonctionalité de Pronot'if pour le moment !\n\nPassez cette étape.", font=default_config_step_font)
    config_tab_step2_text.place(relx=0.5, rely=0.5, anchor="center")

    # Add a next button to navigate to the next tab
    next_button = ctk.CTkButton(
        master=tabview.tab("2. Repas"), 
        font=default_items_font,
        text="Suivant", 
        command=lambda: tabview.set("3. Avancé"), 
        corner_radius=10, 
        width=200, 
        height=40
    )
    next_button.place(relx=0.5, rely=0.8, anchor="center")

    globals()['config_tab2_approved'] = True

  # Handling the case when a menu is found
  else:
    config_tab_step2_text = ctk.CTkLabel(master=tabview.tab("2. Repas"), text="Déplacez le curseur bleu pour définir vos horaires\nde déjeuner.", font=default_config_step_font)
    config_tab_step2_text.place(relx=0.5, rely=0.15, anchor="center")

    def evening_switch_toogle():
        """
        Toggle the evening menu switch.
        """

        if evening_switch_var.get() == "True":
            evening_menu_switch.configure(text="Diner (oui)", progress_color="light green")
        else:
            evening_menu_switch.configure(text="Diner (non)", progress_color="grey")
        
        # Auto-save evening menu preference
        config_data.evening_menu = evening_switch_var.get()
        logger.debug(f"Evening menu option has been set to {config_data.evening_menu}")

    evening_switch_var = ctk.StringVar(value="False") # Set the switch to be disabled by default
    evening_menu_switch = ctk.CTkSwitch(master=tabview.tab("2. Repas"), switch_width=50, switch_height=20, button_color="white", progress_color="grey", variable=evening_switch_var, font=default_subtitle_font, text="Diner (non)", onvalue="True", offvalue="False", command=evening_switch_toogle)
    evening_menu_switch.place(relx=0.8, rely=0.47, anchor="center")

    evening_menu_tooltip = CTkToolTip(evening_menu_switch, message="Si l'option est activée, une notification avec le\nmenu du soir est envoyée vers 19h.", delay=0.2, alpha=0.8, wraplength=450, justify="center", font=default_subtitle_font)

    # Create labels and Scale widgets for each day
    days = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi"]
    labels = {}
    scales = {}
    lunch_times = {}
    global current_day_index
    current_day_index = 0  # Initialize current_day_index here

    def time_to_minutes(time: str) -> int:
        """
        Convert time in HH:MM format to minutes since 00:00.
        """

        hours, minutes = map(int, time.split(":"))
        return hours * 60 + minutes

    def minutes_to_time(minutes: int) -> str:
        """
        Convert minutes since 00:00 to time in HH:MM format.
        """

        hours = minutes // 60
        minutes = minutes % 60
        return f"{hours:02d}:{minutes:02d}"

    def submit_lunch_time():
        """
        Submit the selected lunch time and move to the next day.
        """

        global current_day_index
        global day
        day = days[current_day_index]
        selected_minutes = int(scales[day].get())
        lunch_times[day] = minutes_to_time(selected_minutes)

        french_to_english = {
            'Lundi': 'Monday',
            'Mardi': 'Tuesday',
            'Mercredi': 'Wednesday',
            'Jeudi': 'Thursday',
            'Vendredi': 'Friday'
        }
        
        # Assign to ConfigData class
        config_data.lunch_times[french_to_english[day]] = lunch_times[day]

        if current_day_index < len(days) - 1:
            # Hide the current day and move to the next day
            labels[day].place_forget()
            scales[day].place_forget()
            current_day_index += 1
            next_day = days[current_day_index]
            labels[next_day].place(relx=0.2, rely=0.35)
            scales[next_day].place(relx=0.3, rely=0.55, anchor="center")
        else:
            # Final submission
            scales[day].configure(state="disabled", progress_color="grey")
            label.configure(text_color="grey")
            
            # Display success message
            config_tab_step2_text.configure(text="Vos paramètres ont étés enregistrés !")
            
            submit_button.configure(text="Suivant", command=lambda: tabview.set("3. Avancé"))
            
            logger.debug(f"Lunch times submitted !")

            globals()['config_tab2_approved'] = True

    # Define the time range for lunch times (from 10:30 to 14:30 in 5-minute intervals)
    start_time = time_to_minutes("10:30")
    end_time = time_to_minutes("14:30")
    increment = 5  # 5 minutes increment

    for day in days:
        label = ctk.CTkLabel(master=tabview.tab("2. Repas"), text=f"{day} 12h30", font=default_subtitle_font)
        labels[day] = label

        scale = ctk.CTkSlider(master=tabview.tab("2. Repas"), from_=start_time, to=end_time, number_of_steps=(end_time - start_time) // increment)
        scales[day] = scale

        # Add a label to show the selected time
        def update_label(value, scale=scale, label=label, day=day) -> None:
            """
            Update the label with the selected time.
            """
        
            time = minutes_to_time(int(float(value)))
            label.configure(text=f"{day}: {time}h")

        scale.configure(command=lambda value, scale=scale, label=label, day=day: update_label(value, scale, label, day))

        # Show the Scale for the first day only
        labels[days[current_day_index]].place(relx=0.2, rely=0.35)
        scales[days[current_day_index]].place(relx=0.3, rely=0.55, anchor="center")

        submit_button_icon = ctk.CTkImage(light_image=Image.open(f"{script_directory}/Icons/Global UI/save_meal_def.png").resize((24, 24)))

        # Create the submit button
        submit_button = ctk.CTkButton(master=tabview.tab("2. Repas"),font=default_items_font , text="Suivant", image=submit_button_icon, compound="right", command=submit_lunch_time, corner_radius=10, width=200, height=40)
        submit_button.place(relx=0.5, rely=0.8, anchor="center")

  #TAB 1 NOTIFICATIONS
  
  def unfinished_homework_reminder_switch_toogle():
    """
    Toggle the unfinished homework reminder switch.
    """

    if unfinished_homework_reminder_switch_var.get() == "True":
      unfinished_homework_reminder_switch.configure(progress_color="light green")
    else:
      unfinished_homework_reminder_switch.configure(progress_color="grey")
      
    # Auto-save the setting
    config_data.unfinished_homework_reminder = unfinished_homework_reminder_switch_var.get()
    logger.debug(f"Unfinished homework reminder set to {config_data.unfinished_homework_reminder}")
    
    # Mark first tab as completed if both settings are configured
    if config_data.unfinished_homework_reminder is not None and config_data.get_bag_ready_reminder is not None:
      globals()['config_tab1_approved'] = True
      

  def get_bag_ready_reminder_toogle():
    """
    Toggle the get bag ready reminder
    """

    if get_bag_ready_reminder_switch_var.get() == "True":
      get_bag_ready_reminder_switch.configure(progress_color="light green")
    else:
      get_bag_ready_reminder_switch.configure(progress_color="grey")
      
    # Auto-save the setting
    config_data.get_bag_ready_reminder = get_bag_ready_reminder_switch_var.get()
    logger.debug(f"Get bag ready reminder set to {config_data.get_bag_ready_reminder}")
    
    # Mark first tab as completed if both settings are configured
    if config_data.unfinished_homework_reminder is not None and config_data.get_bag_ready_reminder is not None:
      globals()['config_tab1_approved'] = True
      
                     
  # Header section
  header_frame = ctk.CTkFrame(master=tabview.tab("1. Notifications"), fg_color="transparent")
  header_frame.place(relx=0.5, rely=0.13, anchor="center", relwidth=0.9)
  
  header_title = ctk.CTkLabel(master=header_frame, text="Rappels et Notifications", 
                          font=("Fixel Display Bold", 20))
  header_title.pack(anchor="w")

  # Settings container frame
  settings_container = ctk.CTkFrame(master=tabview.tab("1. Notifications"), fg_color="transparent")
  settings_container.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.9, relheight=0.6)
  
  # Create a function to make cards consistent
  def create_setting_card(container, title, description, var, toggle_command):
      card = ctk.CTkFrame(master=container, corner_radius=15)
      card.pack(fill="x", pady=10, ipady=5)
      
      # Main content frame
      content = ctk.CTkFrame(master=card, fg_color="transparent")
      content.pack(fill="both", expand=True, padx=20, pady=10)
      
      content.grid_columnconfigure(0, weight=8)  # Text column
      content.grid_columnconfigure(1, weight=1)  # Switch column
      content.grid_rowconfigure(1, minsize=40)  # Set minimum height for description row
      
      # Title and description
      title_label = ctk.CTkLabel(master=content, text=title, 
                           font=("Fixel Text Medium", 16))
      title_label.grid(row=0, column=0, sticky="w", pady=(0, 5))
      

      desc_label = ctk.CTkLabel(
          master=content, 
          text=description, 
          font=("Fixel Text Regular", 13),
          text_color=("gray50", "gray70"),
          wraplength=240,
          anchor="w",      # Left alignment 
          justify="left"   # Left-aligned text
      )
      desc_label.grid(row=1, column=0, sticky="nw", pady=(0, 5))
      
      # Switch
      switch = ctk.CTkSwitch(
          master=content,
          switch_width=50, 
          switch_height=25, 
          button_color="#ffffff", 
          progress_color="#3a86ff",
          button_hover_color="#f0f0f0",
          variable=var, 
          text="", 
          onvalue="True", 
          offvalue="False", 
          command=toggle_command
      )
      switch.grid(row=0, column=1, rowspan=2, sticky="e", padx=(10, 5))
      
      return switch
    
  #Homework reminder card
  unfinished_homework_reminder_switch_var = ctk.StringVar(value="False")
  unfinished_homework_reminder_switch = create_setting_card(
      settings_container,
      "Devoirs non faits",
      "Recevez un rappel vers 18h pour terminer vos devoirs non faits.",
      unfinished_homework_reminder_switch_var,
      unfinished_homework_reminder_switch_toogle
  )
  config_data.unfinished_homework_reminder = False #Default value
  
  #bag reminder card
  get_bag_ready_reminder_switch_var = ctk.StringVar(value="False")
  get_bag_ready_reminder_switch = create_setting_card(
      settings_container,
      "Faire son sac",
      "Recevez un rappel vers 19h30 pour préparer votre sac pour le lendemain.",
      get_bag_ready_reminder_switch_var,
      get_bag_ready_reminder_toogle
  )
  config_data.get_bag_ready_reminder = False #Default value
  
  next_button = ctk.CTkButton(
      master=tabview.tab("1. Notifications"), 
      font=default_items_font,
      text="Suivant", 
      command=lambda: tabview.set("2. Repas"), 
      corner_radius=10, 
      width=200, 
      height=40
  )
  next_button.place(relx=0.5, rely=0.88, anchor="center")

  #TAB 3 ADVANCED

  def switch_toggled():
      """Switch toggle handler for timezone selection mode
      """
      if switch_var.get() == "off":
          switch.configure(text="Manuel")
          combo_menu.place(relx=0.5, rely=0.45, anchor="center")
      else:
          switch.configure(text="Automatique")
          combo_menu.place_forget()
          
      # Auto-save the timezone selection
      if switch_var.get() == "off":
          selected_option = combo_menu.get()
          if selected_option:
              if selected_option == "UTC":
                  config_data.selected_timezone = "UTC"
              else:
                  sign = selected_option[3]
                  offset = selected_option[4:]

                  # Invert the sign for the Etc/GMT format
                  if sign == '+':
                      etc_gmt_offset = f"-{offset}"
                  elif sign == '-':
                      etc_gmt_offset = f"+{offset}"

                  config_data.selected_timezone = f"Etc/GMT{etc_gmt_offset}"
                  logger.debug(f"New timezone has been selected: {config_data.selected_timezone}")
      else:
          config_data.selected_timezone = system_data.automatic_school_timezone
          logger.debug("Default timezone has been selected!")

  def notification_delay_changed(new_value):
      """Handle notification delay change
      """
      # Extract just the number from the string
      delay = int(new_value.split()[0])
      config_data.notification_delay = delay
      logger.debug(f"Notification delay set to {delay} minutes")
  
  # Header section
  advanced_header_frame = ctk.CTkFrame(master=tabview.tab("3. Avancé"), fg_color="transparent")
  advanced_header_frame.place(relx=0.5, rely=0.05, anchor="center", relwidth=0.9)
  
  advanced_header_title = ctk.CTkLabel(master=advanced_header_frame, text="Paramètres avancés", 
                          font=("Fixel Display Bold", 20))
  advanced_header_title.pack(anchor="w")

  # Settings container frame
  advanced_settings_container = ctk.CTkFrame(master=tabview.tab("3. Avancé"), fg_color="transparent")
  advanced_settings_container.place(relx=0.5, rely=0.45, anchor="center", relwidth=0.9, relheight=0.8)
  
  # Create a function to make cards consistent
  def create_advanced_card(container, title, content_setup_func):
      card = ctk.CTkFrame(master=container, corner_radius=15)
      card.pack(fill="x", pady=10, ipady=10)
      
      # Card content frame
      content = ctk.CTkFrame(master=card, fg_color="transparent")
      content.pack(fill="both", expand=True, padx=20, pady=15)
      
      # Set title
      card_title = ctk.CTkLabel(master=content, text=title, font=("Fixel Text Medium", 16))
      card_title.pack(anchor="w", pady=(0, 10))
      
      content_setup_func(content)
      
      return card
  
  # Function to set up timezone card content
  def setup_timezone_content(content):
      # Switch for automatic/manual timezone
      global switch, switch_var, combo_menu
      switch_var = ctk.StringVar(value="on")  # Default to automatic
      switch = ctk.CTkSwitch(master=content, 
                          font=("Fixel Text Regular", 13),
                          switch_width=50, 
                          switch_height=25,
                          button_color="#ffffff",
                          progress_color="#3a86ff", 
                          text="Automatique", 
                          variable=switch_var, 
                          onvalue="on", 
                          offvalue="off", 
                          command=switch_toggled)
      switch.pack(anchor="w", pady=(0, 10))
      
      # Timezone dropdown (initially hidden)
      options = ["UTC", "UTC+1", "UTC+2", "UTC+3", "UTC+4", "UTC+5", "UTC+6", "UTC+7", "UTC+8", 
                "UTC+9", "UTC+10", "UTC+11", "UTC+12", "UTC-1", "UTC-2", "UTC-3", "UTC-4", 
                "UTC-5", "UTC-6", "UTC-7", "UTC-8", "UTC-9", "UTC-10", "UTC-11", "UTC-12"]
      combo_menu = ctk.CTkComboBox(master=content, 
                                font=("Fixel Text Regular", 13),
                                values=options, 
                                state="readonly",
                                width=200,
                                height=35)
      # Initially hidden, will be shown when manual mode is selected
      
      # Auto-set timezone to automatic
      config_data.selected_timezone = system_data.automatic_school_timezone
      #logger.debug("Default timezone has been selected automatically")
  
  # Function to set up notification delay card content
  def setup_delay_content(content):
      global notification_delay_menu
      # Description text
      desc = ctk.CTkLabel(master=content, 
                        text="Combien de temps à l'avance souhaitez-vous être notifié ?", 
                        font=("Fixel Text Regular", 13),
                        text_color=("gray50", "gray70"),
                        wraplength=300,
                        justify="left")
      desc.pack(anchor="w", pady=(0, 15))
      
      # Dropdown for notification delay
      notification_delays = ["1 minute", "3 minutes", "5 minutes", "10 minutes"]
      notification_delay_var = ctk.StringVar(value=notification_delays[2])  # Default to 5 minutes
      
      notification_delay_menu = ctk.CTkOptionMenu(
          master=content,
          font=("Fixel Text Regular", 13),
          values=notification_delays, 
          variable=notification_delay_var, 
          command=notification_delay_changed,
          width=200,
          height=40,
          button_color="#3a86ff",
          button_hover_color="#2d6ed3", 
          dropdown_fg_color="#ffffff",
          dropdown_hover_color="#f0f0f0",
          dropdown_text_color="#000000",
          text_color=("#ffffff", "#ffffff"),
          fg_color="#3a86ff",
          state="readonly"
      )
      notification_delay_menu.pack(anchor="w")
      
      # Auto-set the default notification delay (5 minutes)
      config_data.notification_delay = 5
      #logger.debug("Default notification delay set to 5 minutes")
  
  # Create the cards
  timezone_card = create_advanced_card(advanced_settings_container, "Fuseau horaire", setup_timezone_content)
  delay_card = create_advanced_card(advanced_settings_container, "Délai avant envoi des notifications", setup_delay_content)
  
  # Finish button at the bottom of the tab
  finish_button = ctk.CTkButton(master=tabview.tab("3. Avancé"), 
                           font=default_items_font,
                           text="Terminer", 
                           command=final_step, 
                           corner_radius=10, 
                           width=200, 
                           height=40,
                           state="normal")
  finish_button.place(relx=0.5, rely=0.88, anchor="center")

def save_credentials():
    """
    Save the username and password.
    """

    username = username_entry.get()
    password = password_entry.get()


    if not username or not password:
     logger.error("Missing Entrys")
     box = CTkMessagebox(title="Erreur !", font=default_messagebox_font, message="Vous devez renseigner un mot de passe et un identifiant...", icon=warning_icon_path, option_1="Réessayer",master=root, width=400, height=180, corner_radius=25,sound=True)
     box.info._text_label.configure(wraplength=450)

    else: 
      root.config(cursor="watch")

      try:

        client = pronotepy.Client(config_data.pronote_url, username=username, password=password)

        config_data.qr_code_login = False  
            
        if client.logged_in:
          
          config_data.student_fullname = client.info.name
          config_data.student_class_name = client.info.class_name

          logger.info(f'Logged in as {config_data.student_fullname}')

          config_data.user_username = username
          config_data.user_password = password

          names = config_data.student_fullname.strip().split() if config_data.student_fullname.strip() else []
          config_data.student_firstname = names[1] if len(names) > 1 else None

          current_hour = datetime.datetime.now().hour
          greeting = "Bonjour" if 6 <= current_hour < 18 else "Bonsoir"

          box = CTkMessagebox(title="Connexion réussie !", font=default_messagebox_font, message=f"{greeting} {config_data.student_firstname} !\nPrenez quelques instants pour personaliser Pronot'if.", icon=ok_icon_path, option_1="Parfait", master=root, width=580, height=180, corner_radius=25,sound=True)
          box.info._text_label.configure(wraplength=450)

          # Get today's date
          today = datetime.date.today()

          # Automatically determine the start date (30 days before today)
          days_back = 30  # Number of days to go back
          start_date = today - datetime.timedelta(days=days_back)

          # Generate a list of weekdays (excluding Saturdays and Sundays) between start_date and today
          weekdays = []
          current_date = start_date
          while current_date <= today:
              if current_date.weekday() < 5:  # Monday to Friday (0=Monday, 4=Friday)
                  weekdays.append(current_date)
              current_date += datetime.timedelta(days=1)

          # Randomly choose some days from the weekdays list
          fallback_dates = random.sample(weekdays, k=7)  # Choose 7 random dates
          global menus

          dates_to_check = [today] + fallback_dates #

          global menus_found
          menus_found = False
          for date in dates_to_check: 
            try:
              menus = client.menus(date_from=date)
              if menus:  # If a menu is found, break out of the loop
                menus_found = True # Set the flag to True
                break
            except KeyError:
              menus_found = False # If no menu is found, set the flag to False

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

          password_eye_button.place_forget()

          if country_and_city_label is not None: # If the label exists
            country_and_city_label.place_forget()

          config_steps()

      except (pronotepy.CryptoError, pronotepy.ENTLoginError):
         logger.warning("Wrong credentials !")
         box = CTkMessagebox(title="Erreur !", font=default_messagebox_font, message="Vos identifiants de connexion semblent incorrects...", icon=warning_icon_path, option_1="Réessayer",master=root, width=470, height=180, corner_radius=25,sound=True)
         box.info._text_label.configure(wraplength=450)
         password_entry.delete(0, 'end')
         root.config(cursor="arrow")   


      except Exception as e:
         current_month = datetime.datetime.now().month
         if current_month == 7 or current_month == 8:
           
           logger.critical(f"Unknown error ! Month is {current_month}, perhaps service closure due to summer break ?\n{e}")
           box = CTkMessagebox(title="Erreur !", font=default_messagebox_font, message="Une erreur inconnue est survenue...\n(Peut-être la fermeture estivale de Pronote ?)", icon=cancel_icon_path, option_1="Ok",master=root, width=400, height=180, corner_radius=25,sound=True)

         else:
            logger.critical(f"Unknown error ! Detail below :\n{e}")
            box = CTkMessagebox(title="Erreur !", font=default_messagebox_font, message="Une erreur inconnue est survenue...\nVeuillez réessayer plus tard.", icon=cancel_icon_path, option_1="Ok",master=root, width=400, height=180, corner_radius=25,sound=True)
            sentry_sdk.capture_exception(e)

         box.info._text_label.configure(wraplength=450) 
         root.config(cursor="arrow")


def qr_code_login_process():
    """
    Process the QR code login.
    """

    pin=enter_pin_entry.get()
    uuid=uuid4()

    try:
        client=pronotepy.Client.qrcode_login(system_data.qrcode_data, pin, str(uuid))

        config_data.uuid = client.uuid
        config_data.pronote_url = client.pronote_url

        if client.logged_in:
         config_data.qr_code_login = True

         box = CTkMessagebox(title="Succès !", font=default_messagebox_font, message="Connexion effectuée !", icon=ok_icon_path, option_1="Parfait", master=root, width=400, height=180, corner_radius=25,sound=True)
         box.info._text_label.configure(wraplength=450)

         # Get today's date
         today = datetime.date.today()

         # Automatically determine the start date (e.g., 30 days before today)
         days_back = 30  # Number of days to go back
         start_date = today - datetime.timedelta(days=days_back)

         # Generate a list of weekdays (excluding Saturdays and Sundays) between start_date and today
         weekdays = []
         current_date = start_date
         while current_date <= today:
              if current_date.weekday() < 5:  # Monday to Friday (0=Monday, 4=Friday)
                  weekdays.append(current_date)
              current_date += datetime.timedelta(days=1)

         # Randomly choose some days from the weekdays list
         fallback_dates = random.sample(weekdays, k=7)  # Choose 7 random dates
         global menus

         dates_to_check = [today] + fallback_dates #

         global menus_found
         menus_found = False
         for date in dates_to_check: 
          try:
           menus = client.menus(date_from=date)
           if menus:  # If a menu is found, break out of the loop
            menus_found = True # Set the flag to True
            break
          except KeyError:
            menus_found = False # If no menu is found, set the flag to False
         
         config_data.student_fullname = client.info.name
         config_data.student_class_name = client.info.class_name

         logger.info(f'Logged in as {config_data.student_fullname}')

         # Enregistrer le nom d'utilisateur et le mot de passe dans deux fichiers .env différents
         set_key(f"{script_directory}/Data/pronote_username.env", 'User', client.username)
         config_data.user_username = client.username
         set_key(f"{script_directory}/Data/pronote_password.env", 'Password', client.password)
         config_data.user_password = client.password

         if config_data.student_fullname:
          # Split the name into words
          words = config_data.student_fullname.strip().split()
            
          # Find the first word that is not in ALL CAPS and not a hyphen
          for word in words:
            if not word.isupper() and word != "-":
              config_data.student_firstname = word
              break
            else:

             config_data.student_firstname = None
          else:
            config_data.student_firstname = None

         root.config(cursor="arrow")

         # Effacer les champs après enregistrement
         enter_pin_entry.place_forget()
         enter_pin_button.place_forget()

         title_label.configure(text="")
         main_text.configure(text= "")

         config_steps()

    except Exception as e:
        # Vérifie si le message d'erreur indique un problème de déchiffrement lié à un QR code expiré
        if "Decryption failed while trying to un pad" in str(e) and "qr code has expired" in str(e):
          box = CTkMessagebox(title="Erreur !", font=default_messagebox_font, message="Le QR code a expiré !\nVeuillez en générer un nouveau sur Pronote.", icon=warning_icon_path, option_1="Réessayer",master=root, width=400, height=180, corner_radius=25,sound=True)
          box.info._text_label.configure(wraplength=450)
          logger.error("QR Code has expired !")

        elif "invalid confirmation code" in str(e):
          box = CTkMessagebox(title="Erreur !", font=default_messagebox_font, message="Le code de confirmation est incorrect !", icon=warning_icon_path, option_1="Réessayer",master=root, width=400, height=180, corner_radius=25,sound=True)
          box.info._text_label.configure(wraplength=450)
          logger.error("Invalid confirmation code !")

        else:
          box = CTkMessagebox(title="Erreur !", font=default_messagebox_font, message="Une erreur inconnue est survenue...\nVeuillez réessayer plus tard.", icon=cancel_icon_path, option_1="Ok",master=root, width=400, height=180, corner_radius=25,sound=True)
          box.info._text_label.configure(wraplength=450)
          logger.error(f"Can not login with QR code: {str(e)}")
          sentry_sdk.capture_exception(e)

def ask_qr_code_pin():
   """
   Ask the user to enter the PIN code for the QR code login.
   """

   root.deiconify()  # Restore the main window
   main_text.configure(text="Entrez le code PIN défini\nsur Pronote.", font=default_text_font)

   if system_data.scan_qr_code_method == "file":
    file_qr_code_button.place_forget()
    under_button_text.place_forget()

   elif system_data.scan_qr_code_method == "screen":
    on_screen_qr_code_button.place_forget()
    camera_qr_code_button.place_forget()
    file_qr_code_button.place_forget()

   global enter_pin_entry
   enter_pin_entry = ctk.CTkEntry(root, width=250, height=40, font=default_text_font, placeholder_text="1234")
   enter_pin_entry.place(relx=0.75, rely=0.45, anchor="center")

   global enter_pin_button
   enter_pin_button = ctk.CTkButton(root, text="Valider", font=default_items_font, command=qr_code_login_process, corner_radius=10, width=200, height=40)
   enter_pin_button.place(relx=0.75, rely=0.6, anchor="center")
   

def analyse_qr_code(screenshot: Image) -> None:
    """
    Analyse the QR code from the screenshot
    """

    decoded_objects = decode(screenshot) #Decode the QR Code
    
    #print(decoded_objects)
    try:
        system_data.qrcode_data=json.loads(decoded_objects[0].data.decode("utf-8")) #Get the data from the QR Code
  
        file_qr_code_button.configure(state='disabled')
        ask_qr_code_pin()

    except Exception as e:
        logger.error(f"Can not decode QR code: {str(e)}")
        box = CTkMessagebox(title="Erreur !", font=default_messagebox_font, message="Le QR Code scanné ne semble pas être valide...", icon=warning_icon_path, option_1="Réessayer",master=root, width=400, height=180, corner_radius=25,sound=True)
        box.info._text_label.configure(wraplength=450)

        root.deiconify()  # Restore the main window
        root.lift()  # Bring main window to top

def process_coords(start_x:float, start_y:float, end_x:float, end_y:float) -> None:
    """
    Process the coordinates of the screenshot.
    """

    overlay.destroy()
    # Ensure coordinates are ordered correctly
    left = min(start_x, end_x)
    top = min(start_y, end_y)
    right = max(start_x, end_x)
    bottom = max(start_y, end_y)
    screenshot = ImageGrab.grab(bbox=(left, top, right, bottom))
    logger.info("Screenshot has been processed !")
    analyse_qr_code(screenshot)

class DragRectangle:
    def __init__(self, canvas: tk.Canvas):
        """
        Initialize the DragRectangle class.
        """

        self.canvas = canvas
        self.start_x = None
        self.start_y = None
        self.rect = None

    def start_drag(self, event: tk.Event):
        """
        Start the drag.
        """

        self.start_x = event.x
        self.start_y = event.y

        global start_x
        global start_y
        start_x = self.start_x
        start_y = self.start_y
        #print(f"Starting coordinates: ({self.start_x}, {self.start_y})")
        self.rect = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x, self.start_y,
            outline="#FF0000", width=4
        )

    def drag(self, event:tk.Event):
        """
        Drag the rectangle.
        """

        if self.rect:
            self.canvas.coords(
                self.rect,
                self.start_x, self.start_y,
                event.x, event.y
            )

    def stop_drag(self, event:tk.Event):
        """
        Stop
        """

        if self.rect:
            end_x, end_y = event.x, event.y
            #print(f"Start: {start_x}, {start_y} End: {end_x}, {end_y}")
            process_coords(start_x, start_y, end_x, end_y)

def create_overlay():
    """
    Create the overlay for the QR code scanning.
    """

    global overlay
    overlay = ctk.CTkToplevel(root)
    overlay.overrideredirect(True)  # Remove title bar
    overlay.attributes('-alpha', 0.3)  # Set transparency to slightly transparent
    overlay.state('zoomed')
    overlay.attributes('-topmost', True)
    overlay.config(cursor="crosshair")
    overlay.lift()

    canvas = tk.Canvas(overlay, highlightthickness=0)
    canvas.pack(fill='both', expand=True)
    
    drag_rect = DragRectangle(canvas)
    canvas.bind('<Button-1>', drag_rect.start_drag)
    canvas.bind('<B1-Motion>', drag_rect.drag)

    canvas.bind('<ButtonRelease-1>', drag_rect.stop_drag)
    overlay.focus_force()  # Force focus on overlay

    def on_overlay_close():
        """
        Close the overlay.
        """

        overlay.destroy()
        on_screen_qr_code_button.configure(state='normal')

    overlay.bind('<space>', lambda _: on_overlay_close())

    return overlay     

def scan_qr_code(scan_qr_code_method:str) -> None:
   """
    Scan the QR code depending the chosen methond.
    """
   
   system_data.scan_qr_code_method = scan_qr_code_method

   if scan_qr_code_method == "file": #If the user wants to scan a QR Code from a file
      on_screen_qr_code_button.place_forget()
      camera_qr_code_button.place_forget()

      def import_qr_code_image():
        """
        Import the QR code from an image image.
        """

        filename = filedialog.askopenfilename(parent=root, filetypes=[("Images", "*.png"), ("Images", "*.jpg"), ("Images", "*.jpeg"), ("Images", "*.svg"), ("Images", "*.webp")], title="Selectionnez le fichier contenant votre QR Code", initialdir="/downloads")
        if filename:

          screenshot = Image.open(filename)
          analyse_qr_code(screenshot)

        else:
          logger.warning("No file selected")
          file_qr_code_button.configure(state='normal')
      

      main_text.configure(text="Importez l'image\nde votre QR Code", font=default_text_font)
      global file_qr_code_button
      file_qr_code_button.configure(text="Charger un fichier", command=import_qr_code_image, width=250, height=45)
      file_qr_code_button.place(relx=0.75, rely=0.4, anchor="center")

      global under_button_text
      under_button_text = ctk.CTkLabel(root, text="Formats supportés : PNG, JPG, JPEG, SVG, WEBP", font=default_subtitle_font)
      under_button_text.place(relx=0.75, rely=0.5 , anchor="center")   

   elif scan_qr_code_method == "screen":
      logger.debug("Scan on screen method chosen !")
      root.iconify() # Minimize the main window
      create_overlay()

   elif scan_qr_code_method == "camera":
      logger.debug("Scan with camera method chosen !")

      on_screen_qr_code_button.place_forget()
      file_qr_code_button.place_forget()
      camera_qr_code_button.place_forget()

      main_text.configure(text="Placez votre QR Code\ndans le carrée vert", font=default_text_font)
      # Create camera frame
      camera_frame = ctk.CTkFrame(root, width=400, height=300)
      camera_frame.place(relx=0.74, rely=0.5, anchor="center")
      
      camera_label = tk.Label(camera_frame)
      camera_label.pack()

      # Start video capture
      cap = cv2.VideoCapture(0)
      
      def update_frame():
          """
          Update the camera frame.
          """

          nonlocal cap, camera_frame
          try:
              ret, frame = cap.read()
              if ret:
                  frame = cv2.flip(frame, 1) # Flip the frame horizontally
                  frame = cv2.resize(frame, (400, 300)) # Resize the frame

                  # Draw green square in center
                  h, w = frame.shape[:2]
                  center_x, center_y = w//2, h//2
                  square_size = 240
                  cv2.rectangle(frame, 
                              (center_x-square_size//2, center_y-square_size//2),
                              (center_x+square_size//2, center_y+square_size//2),
                              (0,255,0), 3)
                  
                  # Convert frame for display
                  frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                  img = Image.fromarray(frame_rgb)
                  imgtk = ImageTk.PhotoImage(image=img)
                  camera_label.imgtk = imgtk
                  camera_label.configure(image=imgtk)
                  
                  # Scan QR code in green square region
                  qr_region = frame[center_y-square_size//2:center_y+square_size//2,
                                  center_x-square_size//2:center_x+square_size//2]
                  decoded = decode(qr_region)
                  if decoded:
                      try:
                          decoded_data = decoded[0].data.decode("utf-8")
                          qrcode_data = json.loads(decoded_data)
                          cap.release()
                          camera_frame.destroy()
                          system_data.qrcode_data = qrcode_data
                          ask_qr_code_pin()
                          return
                      except json.JSONDecodeError:
                          logger.error("Invalid QR code format")

                          box = CTkMessagebox(title="Erreur !", font=default_messagebox_font, message="Le QR Code scanné ne semble pas être valide...", icon=warning_icon_path, option_1="Réessayer",master=root, width=400, height=180, corner_radius=25,sound=True)
                          box.info._text_label.configure(wraplength=450)
                      
                  root.after(10, update_frame)
              else:
                  cap.release()
                  camera_frame.destroy()
          except Exception as e:
              logger.critical(f"Camera error: {str(e)}")
              cap.release()
              camera_frame.destroy()
              sentry_sdk.capture_exception(e)
      
      update_frame()

def qr_code_login():
  """
  QR Code login method.
  """

  logger.debug("User has chosen QR Code login method !")
  title_label.configure(text="Etape 4/4")
  main_text.configure(text="Choissisez comment\nscanner votre QR Code", font=default_text_font)
  main_text.place(rely=0.45)

  global school_name_text
  school_name_text = ctk.CTkLabel(root, text="")
  school_name_text.place(relx=0.23, rely=0.65, anchor="center")
  
  login_with_credentials_button.place_forget()
  login_with_qr_button.place_forget()

  on_screen_qr_code_image = ctk.CTkImage(light_image=Image.open(f"{script_directory}/Icons/Global UI/select_on_screen_def.png").resize((24, 24)))
  file_qr_code_image = ctk.CTkImage(light_image=Image.open(f"{script_directory}/Icons/Global UI/open_folder_def.png").resize((24, 24)))
  camera_qr_code_image = ctk.CTkImage(light_image=Image.open(f"{script_directory}/Icons/Global UI/camera_def.png").resize((24, 24)))

  #Create 3 buttons for 3 methods
  global on_screen_qr_code_button
  on_screen_qr_code_button = ctk.CTkButton(root, text="Scanner depuis l'écran", font=default_items_font, command=lambda: scan_qr_code("screen"), image=on_screen_qr_code_image, compound="left", width=250, height=45)
  on_screen_qr_code_button.place(relx=0.75, rely=0.3, anchor="center")

  global camera_qr_code_button
  camera_qr_code_button = ctk.CTkButton(root, text="Scanner avec la caméra", font=default_items_font, command=lambda: scan_qr_code("camera"), image=camera_qr_code_image, compound="left", width=250, height=45)
  camera_qr_code_button.place(relx=0.75, rely=0.45, anchor="center")

  global file_qr_code_button
  file_qr_code_button = ctk.CTkButton(root, text="Importer une image", font=default_items_font, command=lambda: scan_qr_code("file"), image=file_qr_code_image, compound="left", width=250, height=45)
  file_qr_code_button.place(relx=0.75, rely=0.6, anchor="center")
   
def select_login_method(choice: str):
   """
   Select the login method.
   """

   root.config(cursor="arrow")
   choice_menu.place_forget()
   title_label.configure(text="Etape 3/4")
   main_text.configure(text="Choisissez votre méthode\nde connexion à Pronote.", font=default_text_font)

   def adjust_text_size(event=None):
    """
    Adjust the text size based on the length of the text.
    """

    global school_name_text
    school_name_text = ctk.CTkLabel(root, text=f"{choice}", font=default_subtitle_font)
    school_name_text.place(relx=0.25, rely=0.45, anchor="center")

    # Bind the label to the adjust_text_size function
    school_name_text.bind("<Configure>", adjust_text_size)

    # Get the current text of the label
    text = school_name_text.cget("text")
    # Calculate the length of the text
    text_length = len(text)
    # Adjust font size based on text length
    font_size = max(12, 14 - text_length // 12)
    # Update the font size of the label
    school_name_text.configure(font=(default_font_name, font_size))

   #Load the images
   qr_code_login_image = ctk.CTkImage(light_image=Image.open(f"{script_directory}/Icons/Global UI/qr_code_def.png").resize((24, 24)))
   credentials_login_image = ctk.CTkImage(light_image=Image.open(f"{script_directory}/Icons/Global UI/credentials_def.png").resize((24, 24)))
   disabled_credentials_login_image = ctk.CTkImage(light_image=Image.open(f"{script_directory}/Icons/Global UI/credentials_disabled.png").resize((24, 24)))

   #Create 2 buttons for two login methods
   global login_with_qr_button
   login_with_qr_button = ctk.CTkButton(root, text="Avec le QR Code", font=default_items_font, image=qr_code_login_image, compound="left", command=qr_code_login, width=250, height=45)
   login_with_qr_button.place(relx=0.75, rely=0.35, anchor="center")

   global login_with_credentials_button
   login_with_credentials_button = ctk.CTkButton(root, text="Avec vos Identifiants", font=default_items_font, image=credentials_login_image, compound="left", command=lambda: login_step(choice), width=250, height=45)
   login_with_credentials_button.place(relx=0.75, rely=0.5, anchor="center")

   if config_data.ent_connexion == True: #If the school uses ENT connexion disable the credentials login button
     login_with_credentials_button.configure(state="disabled", text_color="grey", image=disabled_credentials_login_image)
     credentials_login_disabled_tooltip = CTkToolTip(login_with_credentials_button, message="La connexion via ENT n'est plus supportée par Pronot'if.\nVeuillez utiliser le QR Code.\n\nPlus d'infos dans la documentation.", delay=0.3, alpha=0.8, wraplength=450, justify="center", font=default_subtitle_font)

def check_pronote_use(choice: str) -> None:
  """
  Check if the school uses Pronote by making a request to the instance.
  """

  pronote_use = True
  pronote_use_msg = None
  try:
    response = requests.get(config_data.pronote_url, allow_redirects=False)

  except requests.exceptions.ConnectionError:
    pronote_use = False
    pronote_use_msg = "DNS Error"

  except Exception as e:
    pronote_use_msg = str(e)
    pronote_use = False

    # Handle any other unexpected errors  
  if pronote_use and not pronote_use_msg and response.status_code == 200:
    logger.info(f"{choice} ({system_data.true_city_name}) uses Pronote !")

    config_data.ent_connexion = False
    select_login_method(choice)

  else:
    if pronote_use_msg == "DNS Error":
      logger.warning(f"{choice} ({system_data.true_city_name}) doesn't seem to use Pronote... See below\nWebsite {config_data.pronote_url} does not exists. {pronote_use_msg}")
      box = CTkMessagebox(title="Aucun résultat", font=default_messagebox_font, message="Votre établissement ne semble pas utiliser Pronote.", icon=warning_icon_path, option_1="Ok",master=root, width=400, height=180, corner_radius=25,sound=True)
      box.info._text_label.configure(wraplength=450)
      root.config(cursor="arrow")

    elif response != 202 and not pronote_use_msg:
       logger.debug(f"{choice} ({system_data.true_city_name}) uses Pronote (ENT Conexion) !")
       config_data.ent_connexion = True
       select_login_method(choice)

    else:
      logger.critical(response)
      logger.critical(f"Unknown error for {config_data.pronote_url}\nError detail : {pronote_use_msg}")
      box = CTkMessagebox(title="Erreur", font=default_messagebox_font, message="Une erreur inconnue est survenue.\nMerci de réessayer plus tard.", icon=cancel_icon_path, option_1="Ok",master=root, width=400, height=180, corner_radius=25,sound=True)
      box.info._text_label.configure(wraplength=450)

def login_step(choice:str) -> None:
  """
  Login step.
  """

  pronote_url = config_data.pronote_url
    
  # Handle any other unexpected errors
  if config_data.ent_connexion is False or config_data.ent_connexion is None:
    
    if system_data.international_use:
       manual_pronote_url_entry.place_forget()
       maunual_pronote_url_button.place_forget()
       country_and_city_label.place_forget()
    else:   
     choice_menu.place_forget()
     login_with_qr_button.place_forget()
     login_with_credentials_button.place_forget()
     
    root.config(cursor="arrow")
    
    title_label.configure(text="Etape 3/4")
    main_text.configure(text=f"Connectez vous à Pronote\nà l'aide de vos identifiants.", font=default_text_font)
    main_text.place(relx=0.25, rely=0.45, anchor="center") #Reposition the text to the initial position (but rely changed to 0.45)

    def adjust_text_size(event=None) -> None:
      """
      Adjust the text size based on the length of the text.
      """

      # Get the current text of the label
      text = school_name_text.cget("text")
      # Calculate the length of the text
      text_length = len(text)
      # Adjust font size based on text length
      font_size = max(10, 12 - text_length // 10)  # Adjust the formula as needed
      # Update the font size of the label
      school_name_text.configure(font=(default_font_name, font_size))

    global password_visible
    password_visible = None
    # Function to toggle the password visibility
    def toggle_password(event=None) -> None:
          """
          Toggle the password visibility.
          """
    
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
    closed_eye_image = ctk.CTkImage(light_image=Image.open(f"{script_directory}/Icons/Global UI/closed_eye_light.png").resize((24, 24)), dark_image=Image.open(f"{script_directory}/Icons/Global UI/closed_eye_dark.png").resize((24, 24)))
    open_eye_image = ctk.CTkImage(light_image=Image.open(f"{script_directory}/Icons/Global UI/open_eye_light.png").resize((24, 24)), dark_image=Image.open(f"{script_directory}/Icons/Global UI/open_eye_dark.png").resize((24, 24)))
      
    global school_name_text
    school_name_text = ctk.CTkLabel(root, text=f"{choice}", font=default_subtitle_font)
    school_name_text.place(relx=0.23, rely=0.65, anchor="center")

    # Bind the label to the adjust_text_size function
    school_name_text.bind("<Configure>", adjust_text_size)

    # Création des labels
    global username_label
    username_label = ctk.CTkLabel(root, text="Identifiant", font=default_subtitle_font)
    username_label.place(relx=0.75, rely=0.25, anchor="center")

    global password_label
    password_label = ctk.CTkLabel(root, text="Mot de passe", font=default_subtitle_font)
    password_label.place(relx=0.75, rely=0.45, anchor="center")

    # Création des champs de saisie
    global username_entry
    username_entry = ctk.CTkEntry(root, width=300, height=45, placeholder_text="Nom d'utilisateur", font=default_subtitle_font)
    username_entry.place(relx=0.75, rely=0.35, anchor="center")

    global password_entry
    password_entry = ctk.CTkEntry(root, width=300, height=45, show="*", placeholder_text="Mot de passe", font=default_subtitle_font)
    password_entry.place(relx=0.75, rely=0.55, anchor="center")
    password_entry.bind("<Return>", lambda event: save_credentials())

    # Bouton pour afficher/masquer le mot de passe avec événements de clic
    global password_eye_button
    password_eye_button = ctk.CTkButton(root,width=1, height=10 ,image=closed_eye_image, text="", fg_color=["#f9f9fa", "#343638"], bg_color=["#f9f9fa", "#343638"], hover_color=["#f9f9fa", "#343638"], corner_radius=10)
    password_eye_button.place(relx=0.92, rely=0.55, anchor="center")

    # Bind left mouse button click to toggle password visibility
    password_eye_button.bind("<Button-1>", toggle_password)
                      
    # Create the save button with the lock icon
    global save_button
    save_button = ctk.CTkButton(root, text="Connexion", font=default_items_font, command=save_credentials, corner_radius=10, width=250, height=45)
    save_button.place(relx=0.75, rely=0.7, anchor="center")

def process_manual_login_url():
  """
  Process the manual login URL.
  """

  manual_login_url = manual_pronote_url_entry.get()

  # Define the patterns for the two URL formats
  manual_login_url_patter1 = r'^https://[a-zA-Z0-9.-]+\.index-education\.net$'
  manual_login_url_patter2 = r'^[a-zA-Z0-9.-]+\.index-education\.net$'

  # Check if the URL matches one of the patterns
  if re.match(manual_login_url_patter1, manual_login_url): #If the URL matches the first pattern
        
        global manual_pronote_url
        manual_pronote_url = manual_login_url + "/pronote/eleve.html" #Add the pronote part to the URL
        config_data.pronote_url = manual_pronote_url #Save the URL in the config_data object
        
        system_data.international_use = True
        login_step(choice="") #Call the login_step function with the manual URL

  elif re.match(manual_login_url_patter2, manual_login_url): #If the URL matches the second pattern
        manual_pronote_url = "https://" + manual_login_url + "/pronote/eleve.html" #Add the pronote part to the URL
        config_data.pronote_url = manual_pronote_url #Save the URL in the config_data object

        system_data.international_use = True
        login_step(choice="") #Call the login_step function with the manual URL

  else:
    logger.error("Given URL string is not well formated...")
    box = CTkMessagebox(title="Erreur !", font=default_messagebox_font, width=450, height=180, corner_radius=25, message="L'URL que vous avez entrée n'est pas correcte.\n\nVeuillez vérifier le format et réessayer.", icon=warning_icon_path, option_1="Réessayer", master=root, sound=True)
    box.info._text_label.configure(wraplength=500)
    

def search_school():
    """
    Search for the school by making a request to the 'Education Nationale' API.
    """

    root.config(cursor="watch")

    city = city_entry.get()

    try:
     true_city_geocode = geolocator.geocode(city)
    except:
      box = CTkMessagebox(title="Erreur !", font=default_messagebox_font, message="Une erreur inconnue est survenue...", icon=warning_icon_path, option_1="Réessayer",master=root, width=400, height=180, corner_radius=25,sound=True)
      box.info._text_label.configure(wraplength=450)
      root.config(cursor="arrow")
      sentry_sdk.capture_exception(e)
    
    if not true_city_geocode:
       logger.error("Unknow city !")
       box = CTkMessagebox(title="Erreur !", font=default_messagebox_font, message="Cette ville ne semble pas exister...", icon=warning_icon_path, option_1="Réessayer", master=root, width=400, height=180, corner_radius=25, sound=True)
       box.info._text_label.configure(wraplength=450)
       root.config(cursor="arrow")

       city_entry.delete(0, "end")

    elif true_city_geocode:
     system_data.true_city_name = true_city_geocode.raw["name"]
     
     display_name = true_city_geocode.raw["display_name"]
     # Split the display name by comma
     display_name_parts = display_name.split(", ")
     # Get the last part which should be the country name
     system_data.country_name = display_name_parts[-1]
     logger.debug(system_data.country_name)

     if system_data.country_name != "France":
      search_button.configure(state="disabled", text_color="grey")
      root.config(cursor="arrow")

      get_timezone(true_city_geocode)

      search_button.place_forget()
      city_entry.place_forget()
      tos_label.place_forget()
      mid_canvas.configure(height=400)
      internet_status_label.place(relx=0.75, rely=0.85, anchor="center")

      title_label.configure(text="Etape 2/4")
      
      main_text.configure(text="Etablissement à l'étranger ?\n\nRenseignez manuellement votre url\nde connexion Pronote.", justify="center", anchor="w", font=default_config_step_font)
      main_text.place(relx=0.25, rely=0.4, anchor="center")
 
      global country_and_city_label
      country_and_city_label = ctk.CTkLabel(master=root, text=f"{system_data.true_city_name}, {system_data.country_name}", font=(default_font_name, 13, "underline"), justify="center", anchor="center")
      country_and_city_label.place(relx=0.23, rely=0.55, anchor="center")

      global manual_pronote_url_entry
      manual_pronote_url_entry = ctk.CTkEntry(master=root, font=(default_font_name, 13), width=350, height=45, placeholder_text="https://xxxxxxxx.index-education.net")
      manual_pronote_url_entry.place(relx=0.75, rely=0.45, anchor="center")
      manual_pronote_url_entry.bind("<Return>", lambda event: process_manual_login_url())

      global maunual_pronote_url_button
      maunual_pronote_url_button = ctk.CTkButton(master=root, text="Valider", font=default_items_font , command=process_manual_login_url, corner_radius=10, width=250, height=45)
      maunual_pronote_url_button.place(relx=0.75, rely=0.6, anchor="center")

     else:
      city_entry.delete(0, "end")
      if ("Marseille" in system_data.true_city_name) and "Arrondissement" not in system_data.true_city_name:  
       box = CTkMessagebox(title="Info", font=default_messagebox_font, message=f"Pour Marseille merci de spécifier l'arrondissement en entier !\nExemple : Marseille 1er Arrondissement, Marseille 2e Arrondissement,", icon=info_icon_path, option_1="Réessayer",master=root, width=400, height=180, corner_radius=25,sound=True)
       box.info._text_label.configure(wraplength=450)
       root.config(cursor="arrow")

      elif ("Paris" in system_data.true_city_name or "Lyon" in system_data.true_city_name) and "Arrondissement" not in system_data.true_city_name:
       box = CTkMessagebox(title="Info", font=default_messagebox_font, message=f"Pour {system_data.true_city_name} merci de spécifier l'arrondissement !\nExemple : {system_data.true_city_name} 19e, {system_data.true_city_name} 20e, {system_data.true_city_name} 1er", icon=info_icon_path, option_1="Réessayer",master=root, width=400, height=180, corner_radius=25,sound=True)
       box.info._text_label.configure(wraplength=450)
       root.config(cursor="arrow")

      else:
       search_button.configure(state="disabled", text_color="grey")
       if "Arrondissement" in system_data.true_city_name:
         # Define the pattern to match
         pattern = r'(\d+e)\s+(Arrondissement)' or r'(\d+er)\s+(Arrondissement)'

         # Replace the matched pattern with a space between the number and "Arrondissement"
         system_data.true_city_name = re.sub(pattern, r'\1  \2', system_data.true_city_name)

       url = "https://data.education.gouv.fr/api/explore/v2.1/catalog/datasets/fr-en-adresse-et-geolocalisation-etablissements-premier-et-second-degre/records"

       # Define query parameters
       limit = 30
       params = {
          "limit": 30,
          "refine": [
              f"libelle_commune:{system_data.true_city_name}",
              "nature_uai_libe:COLLEGE",
              "nature_uai_libe:LYCEE D ENSEIGNEMENT GENERAL",
              "nature_uai_libe:LYCEE ENSEIGNT GENERAL ET TECHNOLOGIQUE",
              "nature_uai_libe:LYCEE POLYVALENT",
              "nature_uai_libe:LYCEE PROFESSIONNEL"
              "nature_uai_libe:LYCEE CLIMATIQUE"
              "nature_uai_libe:LYCEE EXPERIMENTAL"
              "nature_uai_libe:LYCEE ENS GENERAL TECHNO PROF AGRICOLE"
          ]
        }

       try:
        # Make the GET request with SSL verification disabled
        try:
            response = requests.get(url, params=params, verify=True)
        except requests.exceptions.SSLError:
            logger.error("Unable to verify SSL certificate !")
            box = CTkMessagebox(title="Erreur réseau !", font=default_messagebox_font, message="Une erreur SSL est survenue et une connexion sécurisée ne peut être établie.", icon=cancel_icon_path, option_1="D'accord", master=root, width=400, height=180, corner_radius=25, sound=True)
            box.info._text_label.configure(wraplength=450)
            response = box.get()
            if response == "D'accord":
              root.config(cursor="arrow")
              search_button.configure(state="normal", text_color="white")
              return []
             
        # Check if the request was successful (status code 200)
        if response.status_code == 200:
          # Parse the JSON response
          data = response.json()

          results_number = data["total_count"]

          if results_number == 0:
           logger.error("No results for the city !")
           box = CTkMessagebox(title="Aucun résultat", font=default_messagebox_font, message="Il ne semble pas y avoir de collèges ou lycées pris en charge dans cette ville...", icon=warning_icon_path, option_1="Réessayer",master=root, width=400, height=180, corner_radius=25,sound=True)
           box.info._text_label.configure(wraplength=450)

           root.config(cursor="arrow")
           search_button.configure(state="normal")

          else: 
           results_count = data["total_count"]

           appellation_officielle_values = []
           for record in data['results']:
              appellation_officielle = record['appellation_officielle']
              if appellation_officielle is None: # If the school name is None
                school_adress = record['adresse_uai']
                logger.info(f"Unnamed school ! ({school_adress})")

              else:
                appellation_officielle_values.append(appellation_officielle)  # Add the school name to the list

           logger.info(f"{results_count} results have been returned for {system_data.true_city_name} ! (limit is {limit})")  

           def optionmenu_callback(choice: str) -> None:
            """
            Callback function for the OptionMenu.
            """
 
            root.config(cursor="watch")
            
            url = "https://data.education.gouv.fr/api/explore/v2.1/catalog/datasets/fr-en-adresse-et-geolocalisation-etablissements-premier-et-second-degre/records"

            # Define query parameters
            params = {
            "limit": 10,
            "refine": [
               f"appellation_officielle:{choice}",
               f"libelle_commune:{system_data.true_city_name}",

             ]
           }

            # Make the GET request
            response = requests.get(url, params=params)

            # Check if the request was successful (status code 200)
            if response.status_code == 200:
             # Parse the JSON response
             data = response.json()

             uai_number = data["results"][0]["numero_uai"]

             system_data.departement_code = data["results"][0]["code_departement"]
             system_data.region_name = data["results"][0]["libelle_region"]
             system_data.school_type = data["results"][0]["nature_uai_libe"]

             config_data.pronote_url = f"https://{uai_number}.index-education.net/pronote/eleve.html"

             global country_and_city_label
             country_and_city_label = None

             get_timezone(true_city_geocode)
             check_pronote_use(choice)

           tos_label.place_forget()
           mid_canvas.configure(height=400)
           internet_status_label.place(relx=0.75, rely=0.85, anchor="center")

           title_label.configure(text="Etape 2/4")
           main_text.configure(text="Selectionnez \nvotre établissement.")

           # Create a StringVar to store the selected option
           default_choice_menu_var = ctk.StringVar(value="Selectionnez votre établissement")

           # Create the OptionMenu with dynamic width
           global choice_menu
           choice_menu = ctk.CTkOptionMenu(root, font=default_items_font , width=350, height=45, dynamic_resizing=False, values=appellation_officielle_values, variable=default_choice_menu_var, command=optionmenu_callback)
           choice_menu.place(relx=0.75, rely=0.4, anchor="center")

           search_button.place_forget()
           city_entry.place_forget()

           root.config(cursor="arrow")

        else:
          # If the request was not successful, print an error message
          logger.error("Error:", response.status_code)
          return []
       
       except Exception as e:
        logger.error(f"An error occurred while trying to search for the city !\n{e}")
        box = CTkMessagebox(title="Erreur !", font=default_messagebox_font, message="Une erreur inconnue est survenue...", icon=warning_icon_path, option_1="Réessayer",master=root, width=400, height=180, corner_radius=25,sound=True)
        box.info._text_label.configure(wraplength=450)
        sentry_sdk.capture_exception(e)
        root.config(cursor="arrow")
        search_button.configure(state="normal")
         

# Create the main window
windll.shcore.SetProcessDpiAwareness(1)
root = ctk.CTk()
root.geometry("750x500")
root.resizable(False, False)
root.title(f"Pronot'if Setup {version}")
root.option_add("*Font", default_font_style)

pyglet.options['win32_gdi_font'] = True # Use GDI font rendering
fonts_dir = Path(__file__).parent / 'Fonts' # Create path to fonts directory

for font_file in fonts_dir.glob('*.otf'): # Load all .otf fonts from the directory
    pyglet.font.add_file(str(font_file))

check_important_file_existence(wanted_file_type="ico")


root.iconbitmap(f"{script_directory}/pronote_butterfly.ico")

ctk.set_appearance_mode("System")

title_bar_color.set(root, "#16a376")
window_frame.center(root)

def close_app():
  """
  Close the application (triggered on both close buttons)."""
  box = CTkMessagebox(title="Fermer ?", font=default_messagebox_font, message="Annuler la configuration ?\nL'ensemble de vos données sera supprimé...", icon=question_icon_path, option_1="Annuler", option_2="Fermer",cancel_button=None ,cancel_button_color="light grey", justify="center", master=root, width=400, height=180, corner_radius=25,sound=True)
  box.info._text_label.configure(wraplength=450)


  response = box.get()

  if response == "Fermer":
    logger.debug("Window is closing removing data...")

    # List of file paths to delete
    files_to_delete = [
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
        sentry_sdk.capture_exception(e)

    logger.debug(f"{deleted_files_count} files out of 2 deleted")

    time.sleep(0.1)
    root.destroy()
    logger.info("Window has been closed !")
    sys.exit(0)
    
  elif response == "Annuler":
    pass

def check_internet() -> bool:
    """
    Check if the computer is connected to the internet.
    """

    url = "http://www.google.com"
    timeout = 5
    try:
        response = requests.get(url, timeout=timeout)
        return True
    except requests.ConnectionError:
        return False

previously_connected = False

def update_internet_label_state():
    """
    Update the internet status label.
    """

    global previously_connected

    currently_connected = check_internet()
    
    if currently_connected and not previously_connected:
        def change_text():
            """
            Change the text of the label.
            """

            internet_status_label.configure(text="De retour en ligne...", text_color="green")
            root.after(2000, clear_text)  # Wait 2 seconds before clearing the text

        def clear_text():
            """
            Clear the text of the label.
            """

            internet_status_label.configure(text="")
        
        change_text()  # Call the change_text function to update the label and start the timer
        search_button.configure(state="normal")
        
    elif not currently_connected:
        internet_status_label.configure(text="Pas de connexion à Internet !", text_color="#ed3f28")
        search_button.configure(state="disabled")
    
    previously_connected = currently_connected  # Update the previous state
        

    root.after(1000, update_internet_label_state)

def on_label_click(event:tk.Event) -> None:
    """
    Open the Pronot'if website when the label is clicked (that's a secret...)
    """
    global click_count
    click_count += 1
    if click_count == 8:
       webbrowser.open_new_tab("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
       logger.critical("Easter egg discovered !")

click_count = 0

def check_if_first_time():
  """
  Check if it's the first time the user is using Pronot'if (txt file existence).
  """

  first_use_file = os.path.exists(f"{script_directory}/first_use.txt")

  if first_use_file:
    logger.info("Initial Startup !")
    box = CTkMessagebox(title="Premiere fois ici ?", font=default_messagebox_font, message=f"On dirait que vous n'avez jamais utilisé Pronot'if...\n\nLisez la documentation pour mieux comprendre comment vous en servir.", icon=info_icon_path, option_1="D'accord", cancel_button=None ,cancel_button_color="light grey", justify="center", master=root, width=450, height=180, corner_radius=25)
    box.info._text_label.configure(wraplength=450)
    webbrowser.open_new_tab("https://docs.pronotif.tech")
    os.remove(f"{script_directory}/first_use.txt")

  else:
    logger.info("Not first startup...")


#Create name label
global author_name_label
author_name_label = ctk.CTkLabel(root, text="Pronot'if Team | ©2025", font=default_subtitle_font, bg_color="transparent")
author_name_label.place(relx=0.87, rely=0.96, anchor="center")
author_name_label.bind("<Button-1>", on_label_click)

# Create a Canvas widget to draw the line

mid_canvas = ctk.CTkCanvas(root, width=3, height=400, background= "white", highlightthickness=0)
mid_canvas.place(relx=0.5, rely=0.48, anchor="center")

# Functions to open links in the default web browser
def open_tos(event:tk.Event) -> None:
    """
    Open the Terms of Service link in the default web browser.
    """

    webbrowser.open("https://safety.pronotif.tech/docs/terms-of-service")

def open_privacy(event:tk.Event) -> None:
    """
    Open the Privacy Policy link in the default web browser.
    """

    webbrowser.open("https://safety.pronotif.tech/docs/politique-de-confidentialite")

# Create a Text widget
tos_label = ctk.CTkTextbox(root, height=20, width=900, fg_color="transparent", bg_color="transparent", font=default_conditions_font, wrap="word")
tos_label.place(relx=0.78, rely=0.85, anchor="center")

# Insert normal text and the link text
tos_label.insert("end", "En continuant vous acceptez les ")
tos_label.insert("end", "conditions", "link_tos")
tos_label.insert("end", " et la ")
tos_label.insert("end", "politique de confidentialité", "link_privacy")
tos_label.insert("end", ".")

# Configure tags for the link parts (make them blue and underline)
tos_label.tag_config("link_tos", foreground="blue", underline=1)
tos_label.tag_config("link_privacy", foreground="blue", underline=1)

# Bind the tags to open links when clicked
tos_label.tag_bind("link_tos", "<Button-1>", open_tos)
tos_label.tag_bind("link_privacy", "<Button-1>", open_privacy)

# Change cursor on hover over the links
tos_label.tag_bind("link_tos", "<Enter>", lambda e: tos_label.configure(cursor="hand2"))  # Hand cursor on hover
tos_label.tag_bind("link_tos", "<Leave>", lambda e: tos_label.configure(cursor="xterm"))  # Reset to default

tos_label.tag_bind("link_privacy", "<Enter>", lambda e: tos_label.configure(cursor="hand2"))  # Hand cursor on hover
tos_label.tag_bind("link_privacy", "<Leave>", lambda e: tos_label.configure(cursor="xterm"))  # Reset to default

# Disable editing of the text widget (making it like a label)
tos_label.configure(state="disabled")

# Create a title label
title_label = ctk.CTkLabel(root, text="Etape 1/4", font=default_title_font)
title_label.place(relx=0.5, rely=0.1, anchor="center")

# Create main text label
main_text = ctk.CTkLabel(root, text="Recherchez ici la ville\n  de votre établissement.", font=default_text_font)
main_text.place(relx=0.25, rely=0.40, anchor="center")

# Create city entry widget
city_entry = ctk.CTkEntry(root, width=300, height=45, font=default_text_font)
city_entry.place(relx=0.75, rely=0.35, anchor="center")
city_entry.bind("<Return>", lambda event: search_school())

search_icon = ctk.CTkImage(light_image=Image.open(f"{script_directory}/Icons/Global UI/search_def.png").resize((48, 48)))

# Create search button
global search_button
search_button = ctk.CTkButton(root, text="Chercher",font=default_items_font, command=search_school, image=search_icon, compound="right", corner_radius=10, width=250, height=45) 
search_button.place(relx=0.75, rely=0.5, anchor="center")

#Create internet status label
internet_status_label = ctk.CTkLabel(root, text="Checking connection...", font=default_subtitle_font)
internet_status_label.place(relx=0.75, rely=0.65, anchor="center")

#Create close button
close_button = ctk.CTkButton(root, text="Fermer", font=default_items_font, command=close_app, width=150, height=40, corner_radius=10, fg_color="#FF6347", hover_color="#FF4500")
close_button.place(relx=0.01, rely=0.98, anchor="sw")

root.protocol("WM_DELETE_WINDOW", close_app)

check_if_first_time()
update_internet_label_state()

#Start main loop
root.mainloop()