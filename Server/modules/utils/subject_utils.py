import os
import json
import unicodedata
import random
from modules.sentry.sentry_config import sentry_sdk, logger

SUBJECT_DATA = {}
EMOJI_DATA = {}

def _load_data():
    global SUBJECT_DATA, EMOJI_DATA
    try:
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data'))
        
        color_path = os.path.join(base_path, 'subject_names_format.json')
        if os.path.exists(color_path):
            with open(color_path, 'r', encoding='utf-8') as f:
                SUBJECT_DATA = json.load(f)
                logger.debug(f"Loaded {len(SUBJECT_DATA)} subjects from color mapping")
                
        emoji_path = os.path.join(base_path, 'emoji_cours_names.json')
        if os.path.exists(emoji_path):
            with open(emoji_path, 'r', encoding='utf-8') as f:
                EMOJI_DATA = json.load(f)
                logger.debug(f"Loaded emojis from emoji mapping")
    except Exception as e:
        logger.error(f"Failed to load subject data: {e}")
        sentry_sdk.capture_exception(e)

_load_data()

def normalize_subject_name(name: str) -> str:
    """
    Normalize a subject name by removing accents and converting to lowercase
    """

    if not name:
        return ""
    
    return "".join([c for c in unicodedata.normalize('NFKD', name) 
            if not unicodedata.category(c).startswith('M')]).lower()

def get_subject_clean_name(raw_name: str) -> str:
    """
    Get the clean name for a subject from its raw name
        (returns raw if not found)
    """
    if not raw_name:
        return ""
    
    normalized = normalize_subject_name(raw_name) #normalize it
    
    if normalized in SUBJECT_DATA:
        return SUBJECT_DATA[normalized].get('name', raw_name)
    
    return raw_name

def get_subject_emoji(name: str) -> str:
    """
    Get an emoji for a subject based on its name
    """
    if not name:
        return EMOJI_DATA.get('default', '📝') #default match
        
    normalized = normalize_subject_name(name)
    
    #Check for keywords
    for key in EMOJI_DATA:
        if key != 'default' and key.lower() in normalized:
            emojis = EMOJI_DATA[key]
            return random.choice(emojis) if isinstance(emojis, list) else emojis
            
    return EMOJI_DATA.get('default', '📝')

def get_subject_color(name: str) -> str:
    """
    Get the color for a subject based on its name
    """
    if not name:
        return "#E0C195" #default color
        
    normalized = normalize_subject_name(name)
    if normalized in SUBJECT_DATA:
        return SUBJECT_DATA[normalized].get('color', "#E0C195")
        
    return "#E0C195"
