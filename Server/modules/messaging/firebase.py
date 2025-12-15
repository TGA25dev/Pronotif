import firebase_admin
from firebase_admin import messaging, credentials
from firebase_admin.exceptions import FirebaseError
import os
import requests

from modules.secrets.secrets_manager import get_secret
from modules.sentry.sentry_config import get_logger_enabled_sentry

sentry_sdk, sentry_logger, logger = get_logger_enabled_sentry()

script_dir = os.path.dirname(os.path.abspath(__file__))
cred_path = os.path.join(script_dir, get_secret('FB_CREDENTIALS_PATH'))

if not os.path.exists(cred_path):
    raise FileNotFoundError(f"Firebase credentials file not found at: {cred_path}")
try: 
    cred = credentials.Certificate(cred_path)
    default_app = firebase_admin.initialize_app(cred) # Initialize Firebase
    logger.info("Firebase Initialized Successfully, user: ", default_app.name)

except Exception as e:
    raise RuntimeError(f"Failed to initialize Firebase: {e}")

def invalid_token(token):
    """
    Mark a Firebase token as invalid in the database
    """
    try:
        api_key = get_secret('INTERNAL_API_KEY')
        api_url = f"https://api.pronotif.tech/v1/internal/invalid_token"
        
        headers = {
            'Content-Type': 'application/json',
            'X-Internal-Auth': api_key
        }
        
        payload = {
            'fcm_token': token
        }
        
        response = requests.post(api_url, json=payload, headers=headers, timeout=5)
        
        if response.status_code == 200:
            logger.info(f"Successfully marked token as invalid: {token[:10]}...")
            return True
        else:
            logger.error(f"Failed to mark token as invalid. Status: {response.status_code} \nResponse: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error marking token as invalid: {e}")
        sentry_sdk.capture_exception(e)
        return False

def send_notification_to_device(registration_token, title, body):
    """
    Send a notification to a specific device using Firebase Cloud Messaging (FCM).
    """
    try:
        #Message payload.
        message = messaging.Message(
            token=registration_token, #FCM token of the device
            notification=messaging.Notification(
                title=title, #Title
                body=body, #Body (content)
            ),

            android=messaging.AndroidConfig(
                priority="high",
                ttl=86400,  #24 hours
                ),

            apns=messaging.APNSConfig(
                headers={
                    "apns-priority": "10",
                }
            ),
        )

        # Send a message to the device
        response = messaging.send(message)
        return response
    
    except FirebaseError as e:
        #Handle Firebase-specific errors
        if "Requested entity was not found" in str(e):
            logger.warning(f"Invalid FCM token: {registration_token[:10]}... : Token is no longer valid")
            invalid_token(registration_token) #Mark token as invalid

        else:
            logger.error(f"Firebase error: {e}")
        return None
    except Exception as e:
        #Other exceptions
        logger.error(f"Error sending notification: {e}")
        return None