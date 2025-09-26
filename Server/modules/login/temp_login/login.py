import requests
from uuid import uuid4
import pronotepy

from .pronotepy_monlycee import ile_de_france
from ..geocoding.geocoder import get_timezone_from_state
import logging

logger = logging.getLogger(__name__)

def check_if_ent(link: str) ->bool:
    """
    Check if the provided link is an ENT link.
    """

    response = requests.get(link, allow_redirects=False, timeout=15)

    if response.status_code == 302: #ENT redirection
       return True
    
    elif response.status_code == 200: #Direct Pronote page
        return False
    
    else:
        return None
    
def get_student_data(client: pronotepy.Client, ent_used:bool, qr_code_login:bool, uuid:str, region:str):
    student_fullname = client.info.name
    student_class = client.info.class_name
    login_page_link = client.pronote_url

    user_username = client.username
    user_password = client.password

    try:
        timezone = get_timezone_from_state(region)
        
    except Exception as e:
        logger.error(f"An error occurred while trying to get the timezone from state: '{e}' -> (Timezone set to default)")
        timezone = "Europe/Paris"

    if student_fullname:
        # Split the name into words
        words = student_fullname.strip().split()
        
        # Find the first word that is not in ALL CAPS and not a hyphen
        for word in words:
            if not word.isupper() and word != "-":

                student_firstname = word
                break

            else:
                student_firstname = "None"

    return {
        "student_fullname": student_fullname,
        "student_firstname": student_firstname,
        "student_class": student_class,
        "login_page_link": login_page_link,
        "student_username": user_username,
        "student_password": user_password,
        "ent_used": ent_used,
        "qr_code_login": qr_code_login,
        "uuid": uuid,
        "timezone": timezone
    }

    
def global_pronote_login(link: str, username:str, password:str, qr_code_login:bool, qrcode_data:dict ,pin:int, region:str):

    if not link.endswith("/eleve.html"):
        link = f"{link}/eleve.html"

    is_ent_login = check_if_ent(link)

    qr_code_login = bool(qr_code_login)

    if qr_code_login and pin and qrcode_data:

        uuid=uuid4()
        client=pronotepy.Client.qrcode_login(qrcode_data, pin, str(uuid))

        if client.logged_in:
            return get_student_data(client, ent_used=False, qr_code_login=True, uuid=str(uuid), region=region)

        else:
            return {"error": "QR code login failed"}, 400
    
    elif is_ent_login: #login with ENT
        logger.debug("Attempting ENT login")
        
        if is_ent_login is None:
            return {"error": "Invalid login page link"}, 400
        
        if region is None or region == "":
            return {"error": "Region is required for ENT login"}, 400
    
        if region!="Île-de-France" and region!="https://psn.monlycee.net":
            return {"error": "Region not supported yet"}, 400
        
        if region=="Île-de-France" or region=="https://psn.monlycee.net":
            logger.debug("Using Île-de-France ENT settings")
            #specific login for Île-de-France
            client = pronotepy.Client(link, username=username, password=password, ent=ile_de_france)

            if client.logged_in:
                return get_student_data(client, ent_used=True, qr_code_login=False, uuid="00000000-0000-0000-0000-000000000000", region=region)

            else:
                return {"error": "ENT login failed"}, 400
    
    elif not is_ent_login: #normal login
        logger.debug("Attempting standard Pronote login")
        client = pronotepy.Client(link, username=username, password=password)

        if client.logged_in:
            return get_student_data(client, ent_used=False, qr_code_login=False, uuid="00000000-0000-0000-0000-000000000000", region=region)

        else:
            return {"error": "Pronote login failed"}, 400