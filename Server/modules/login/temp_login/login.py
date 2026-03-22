import requests
from uuid import uuid4
import pronotepy
from urllib.parse import urlparse, urlunparse
import ipaddress

from .pronotepy_monlycee import ile_de_france
from ..geocoding.geocoder import get_timezone_from_state
from ..verify_manual_link import clean_url
import logging
import json

logger = logging.getLogger(__name__)


def _is_disallowed_host(hostname: str) -> bool:
    """Block untrusted QR URLs"""
    if not hostname:
        return True

    host = hostname.strip().lower()
    if host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".local"):
        return True

    try:
        ip = ipaddress.ip_address(host)
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast #block ip literals that are not globally routable
    
    except ValueError:
        # Not an IP literal Keep domain names allowed
        return False


def _normalize_qrcode_payload(qrcode_data):
    """Validate and normalize untrusted QR payload before passing to login module."""

    if isinstance(qrcode_data, str):

        try:
            qrcode_data = json.loads(qrcode_data)

        except json.JSONDecodeError:
            return None, {"error": "Invalid QR code data format", "error_code": "INVALID_QR_DATA"}, 400

    if not isinstance(qrcode_data, dict):
        return None, {"error": "Invalid QR code data format", "error_code": "INVALID_QR_DATA"}, 400

    required_keys = ("login", "jeton", "url")
    normalized = {}

    for key in required_keys:

        value = qrcode_data.get(key)
        if not isinstance(value, str) or not value.strip():

            return None, {"error": "Invalid QR code data format", "error_code": "INVALID_QR_DATA"}, 400
        normalized[key] = value.strip()

    try: #ensure we get hex data
        bytes.fromhex(normalized["login"])
        bytes.fromhex(normalized["jeton"])

    except ValueError:
        return None, {"error": "Invalid QR code data format", "error_code": "INVALID_QR_DATA"}, 400

    parsed_qr_url = urlparse(normalized["url"])
    if parsed_qr_url.scheme.lower() != "https" or not parsed_qr_url.netloc:
        return None, {"error": "Invalid QR code URL", "error_code": "INVALID_QR_URL"}, 400

    if _is_disallowed_host(parsed_qr_url.hostname or ""):
        return None, {"error": "Invalid QR code URL", "error_code": "INVALID_QR_URL"}, 400

    return normalized, None, None


def _normalize_login_link(link: str) -> str | None:
    """Normalize provided link to a single pronote/eleve.html path."""
    cleaned = clean_url(link)
    if not cleaned:
        return None

    parsed = urlparse(cleaned)
    path = parsed.path.rstrip("/")

    #Trim trailing /eleve if user sent a partially built link
    if path.endswith("/eleve"):
        path = path.rsplit("/", 1)[0]

    # Keep existing pronote path when present if not otherwise default
    segments = [seg for seg in path.split("/") if seg]
    if not segments or segments[-1].lower() != "pronote":
        path = "/pronote"
    else:
        path = "/" + "/".join(segments)

    return urlunparse((
        parsed.scheme,
        parsed.netloc,
        f"{path}/eleve.html",
        "",
        "",
        ""
    ))

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

def to_text(value):
    if value is None:
        return None
    
    if isinstance(value, str):
        return value
    
    elif isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="strict")
    
    else:
        return str(value)
    
def get_student_data(client: pronotepy.Client, ent_used:bool, qr_code_login:bool, uuid:str, region:str):
    student_fullname = to_text(client.info.name)
    student_class = to_text(client.info.class_name)
    login_page_link = to_text(client.pronote_url)

    user_username = to_text(client.username)
    user_password = to_text(client.password)

    try:
        timezone = get_timezone_from_state(region)
        
    except Exception as e:
        logger.error(f"An error occurred while trying to get the timezone from state: '{e}' -> (Timezone set to default)")
        timezone = "Europe/Paris"

    student_firstname = "None"

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

    normalized_link = _normalize_login_link(link)
    if not normalized_link:
        return {"error": "Invalid login page link"}, 400
    
    if isinstance(password, (bytes, bytearray)):
        password = password.decode("utf-8", errors="strict")

    if qr_code_login:
        logger.debug("Attempting QR code login")
        pin_str = str(pin).strip()

        if not pin_str.isdigit() or len(pin_str) != 4:
            return {"error": "Invalid QR PIN format", "error_code": "INVALID_QR_PIN_FORMAT"}, 400

        qrcode_data, validation_error, validation_status = _normalize_qrcode_payload(qrcode_data)
        if validation_error:
            return validation_error, validation_status

        uuid=uuid4()
        client=pronotepy.Client.qrcode_login(qrcode_data, pin_str, str(uuid))

        if client.logged_in:
            logger.debug(f"QR code login successful! {uuid} - {region}")
            return get_student_data(client, ent_used=False, qr_code_login=True, uuid=str(uuid), region=region)

        else:
            return {"error": "QR code login failed", "error_code": "QR_LOGIN_FAILED"}, 400

    is_ent_login = check_if_ent(normalized_link)
    
    if is_ent_login is None:
        return {"error": "Invalid login page link"}, 400
    
    elif is_ent_login: #login with ENT
        logger.debug("Attempting ENT login")
        
        if not region: #none or empty string
            logger.error("Region is required for ENT login but was not provided")
            return {"error": "Region is required for ENT login"}, 400
        
        if region in ["Île-de-France", "https://psn.monlycee.net"]:
            logger.debug("Using Île-de-France ENT settings")
            #specific login for Île-de-France
            client = pronotepy.Client(normalized_link, username=username, password=password, ent=ile_de_france)

            if client.logged_in:
                return get_student_data(client, ent_used=True, qr_code_login=False, uuid="00000000-0000-0000-0000-000000000000", region=region)

            else:
                logger.error("Île-de-France ENT login failed")
                return {"error": "ENT IDF login failed"}, 400
        else:
            logger.error(f"Region '{region}' is not supported yet for ENT login")
            return {"error": "Region not supported yet"}, 400
    
    elif not is_ent_login: #normal login
        logger.debug("Attempting standard Pronote login")
        client = pronotepy.Client(normalized_link, username=username, password=password)

        if client.logged_in:
            return get_student_data(client, ent_used=False, qr_code_login=False, uuid="00000000-0000-0000-0000-000000000000", region=region)

        else:
            return {"error": "Pronote login failed"}, 400