import mysql.connector
from modules.messaging.firebase import send_notification_to_device
from modules.secrets.secrets_manager import get_secret
from modules.sentry.sentry_config import get_logger_enabled_sentry

sentry_sdk, sentry_logger, logger = get_logger_enabled_sentry()

def send_notification_to_all_devices(title, body):
    """Send a notification to all active registered devices"""
    try:
        
        #Whitelisted table names
        allowed_tables = {get_secret('DB_STUDENT_TABLE_NAME')}
        table = get_secret('DB_STUDENT_TABLE_NAME')
        if table not in allowed_tables:
            raise ValueError("Invalid table name")
        
        connection = mysql.connector.connect(
            host=get_secret('DB_HOST'),
            user=get_secret('DB_USER'),
            password=get_secret('DB_PASSWORD'),
            database=get_secret('DB_NAME')
        )
        cursor = connection.cursor()
        
        table = get_secret('DB_STUDENT_TABLE_NAME')
        cursor.execute(f"""
            SELECT fcm_token FROM {table}
            WHERE fcm_token IS NOT NULL 
            AND is_active = TRUE
        """)
        
        tokens = [row[0] for row in cursor.fetchall()]
        cursor.close()
        connection.close()
        
        successful = 0
        failed = 0
        
        for token in tokens:
            result = send_notification_to_device(token, title, body)

            if result.get("status") == "success":
                successful += 1

            else:
                failed += 1
        
        logger.info(f"Broadcast sent: {successful}/{len(tokens)} successful")
        return {"successful": successful, "failed": failed, "total": len(tokens)}
    
    except Exception as e:
        logger.error(f"Broadcast error: {e}")
        sentry_sdk.capture_exception(e)
        return {"error": str(e)}


def send_notification_to_user(user_hash, title, body):
    """Send a notification to a specific user by their user_hash"""

    try:
        connection = mysql.connector.connect(
            host=get_secret('DB_HOST'),
            user=get_secret('DB_USER'),
            password=get_secret('DB_PASSWORD'),
            database=get_secret('DB_NAME')
        )

        cursor = connection.cursor(dictionary=True)
        
        table = get_secret('DB_STUDENT_TABLE_NAME')
        cursor.execute(f"""
            SELECT fcm_token FROM {table}
            WHERE user_hash = %s
            AND fcm_token IS NOT NULL 
            AND is_active = TRUE
        """, (user_hash,))
        
        result = cursor.fetchone()
        cursor.close()
        connection.close()
        
        if not result:

            logger.warning(f"No active FCM token found for user_hash: {user_hash}")
            return {"status": "not_found", "message": "User not found or no active FCM token"}
        
        fcm_token = result['fcm_token']
        notification_result = send_notification_to_device(fcm_token, title, body)
        
        if notification_result.get("status") == "success":
            logger.info(f"Notification sent successfully to user {user_hash}")
            return {"status": "success", "message": "Notification sent"}
        
        else:
            logger.error(f"Failed to send notification to user {user_hash}: {notification_result}")
            return {"status": "failed", "message": notification_result.get("error", "Unknown error")}
    
    except Exception as e:

        logger.error(f"Error sending notification to user {user_hash}: {e}")
        sentry_sdk.capture_exception(e)
        return {"status": "error", "message": str(e)}
