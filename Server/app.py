from flask import Flask, request, jsonify
import mysql.connector
from mysql.connector import pooling
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import logging
from datetime import datetime
import redis
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Setup logging
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

file_handler = logging.FileHandler('app.log')
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# MySQL Connection Pool
connection_pool = pooling.MySQLConnectionPool(
    pool_name=os.getenv('DB_POOL_NAME'),
    pool_size=int(os.getenv('DB_POOL_SIZE')),
    pool_reset_session=os.getenv('DB_POOL_RESET_SESSION'),
    host=os.getenv('DB_HOST'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    database=os.getenv('DB_NAME')
)

authcode = os.getenv('AUTHCODE')

# Flask-Limiter and Redis Configuration
redis_connection = redis.Redis(
    host=os.getenv('REDIS_HOST'),
    port=int(os.getenv('REDIS_PORT')),
    db=int(os.getenv('REDIS_DB'))
)

limiter = Limiter(
    get_remote_address,
    app=app,
    storage_uri=f"redis://{os.getenv('REDIS_HOST')}:{int(os.getenv('LIMITER_PORT'))}"
)


@app.errorhandler(500)
def internal_error(error):
    logger.critical(f"Internal Server Error: {error}")
    return jsonify({'error': 'An internal error occurred'}), 500


@app.errorhandler(429)
def ratelimit_error(error):
    logger.warning(f"Rate limit exceeded: {error}")
    return jsonify({'error': 'Rate limit exceeded'}), 429


@app.errorhandler(404)
def page_not_found(error):
    logger.warning(f"Page not found: {error}")
    return jsonify({'error': 'Page not found'}), 404

# API Endpoints

@app.route('/ping', methods=['GET'])
@limiter.limit("10 per minute")
def test_endpoint():
    client_ip = request.remote_addr
    logger.info(f"{client_ip} Pong !")
    return jsonify({"message": "Pong !"}), 200

# Use Redis to store the state instead of a dictionary
def get_state():
    state = redis_connection.get('visibility_state')
    return bool(state and state.decode('utf-8') == 'True')

def set_state(enabled):
    redis_connection.set('visibility_state', str(enabled))

@app.route('/emc', methods=['GET'])
def toggle_visibility():
    if 'enable' in request.args:
        set_state(True)
        logger.info("Visibility state enabled")
        return jsonify({"status": "enabled"}), 200
    
    elif 'disable' in request.args:
        set_state(False)
        logger.info("Visibility state disabled")
        return jsonify({"status": "disabled"}), 200
    else:
        return jsonify({"error": "Invalid action"}), 400

@app.route('/state', methods=['GET'])
def get_visibility_state():
    return jsonify({"enabled": get_state()}), 200

#App Endpoints


if __name__ == '__main__':
    app.run(host=os.getenv('HOST'), port=os.getenv('MAIN_PORT'))
