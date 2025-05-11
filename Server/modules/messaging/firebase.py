import firebase_admin
from firebase_admin import messaging, credentials
from dotenv import load_dotenv
import os

load_dotenv()

script_dir = os.path.dirname(os.path.abspath(__file__))
cred_path = os.path.join(script_dir, os.getenv('FB_CREDENTIALS_PATH'))

if not os.path.exists(cred_path):
    raise FileNotFoundError(f"Firebase credentials file not found at: {cred_path}")
try: 
    cred = credentials.Certificate(cred_path)
    default_app = firebase_admin.initialize_app(cred) # Initialize Firebase
    print("Firebase Initialized Successfully, user: ", default_app.name)

except Exception as e:
    raise RuntimeError(f"Failed to initialize Firebase: {e}")

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
            )
        )

        # Send a message to the device
        response = messaging.send(message)
        return response
    
    except messaging.FirebaseError as e:
        # Firebase-specific errors
        print(f"Firebase error: {e}")
        return None
    
    except Exception as e:
        #Other exceptions
        print(f"Error sending notification: {e}")
        return None