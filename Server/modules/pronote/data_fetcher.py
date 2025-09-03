import os
import sentry_sdk
from datetime import datetime
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from modules.pronote.users import PronotifUser
from modules.pronote.notification_system import _existing_users, user_update_lock

async def fetch_pronote_data(user_hash, data_type):
    """
    Fetch specific data from Pronote for an already authenticated user.
    
    Args:
        user_hash (str): The hash of the user to fetch data for.
        data_type (str): The type of data to fetch (e.g., 'lessons', 'menus', etc.).
    
    Returns:
        dict: The requested data or an error message.
    """
    try:
        # Check if user is already authenticated in the notification system
        async with user_update_lock:
            if user_hash not in _existing_users:
                return {"error": "User not found or not authenticated"}
            
            user = _existing_users[user_hash]
            
            if not user.client or not user.client.logged_in:
                return {"error": "User not logged in"}
        
        # Fetch the requested data using the existing authenticated client
        if data_type == "lessons":
            today = datetime.now(user.timezone_obj).date()
            lessons = user.client.lessons(date_from=today)
            return {"lessons": [lesson.to_dict() for lesson in lessons]}
        
        elif data_type == "menus":
            today = datetime.now(user.timezone_obj).date()
            menus = user.client.menus(date_from=today, date_to=today)
            return {"menus": [menu.to_dict() for menu in menus]}
        
        else:
            return {"error": f"Unsupported data type: {data_type}"}
    
    except Exception as e:
        sentry_sdk.capture_exception(e)
        return {"error": f"An error occurred: {str(e)}"}