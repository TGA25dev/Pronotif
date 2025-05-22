import firebase_admin
from firebase_admin import messaging, credentials
from dotenv import load_dotenv
import os
import sentry_sdk

ignore_errors = [KeyboardInterrupt]
sentry_sdk.init(
    "https://8c5e5e92f5e18135e5c89280db44a056@o4508253449224192.ingest.de.sentry.io/4508253458726992", 
    enable_tracing=True,
    traces_sample_rate=1.0,
    environment="production",
    release="v0.9",
    server_name="Server",
    ignore_errors=ignore_errors,
     _experiments={
        "enable_logs": True,
    },

)

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