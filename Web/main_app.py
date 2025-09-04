from flask import Flask, jsonify, render_template, send_from_directory, abort
import logging
from datetime import timedelta
import redis
from dotenv import load_dotenv
import os
import re
from flask_cors import CORS
from flask_talisman import Talisman
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_session import Session
from redis import Redis
from datetime import datetime
from jinja2 import TemplateNotFound
import sys


server_env_path = '/var/www/pronotif.tech/html/Pronotif/Server/.env'
load_dotenv(server_env_path)

sys.path.append('/var/www/pronotif.tech/html/Pronotif/Server')
from modules.ratelimit.ratelimiter import limiter # type: ignore

app = Flask(__name__, 
            template_folder='.',
            static_folder='.',
            static_url_path='')

redis_connection = redis.Redis(
    host=os.getenv('REDIS_HOST'),
    port=int(os.getenv('REDIS_PORT')),
    db=int(os.getenv('REDIS_DB')),
    password=os.getenv('REDIS_PASSWORD')
)

initialized = False

# Initialize limiter
limiter.init_app(app)

app.wsgi_app = ProxyFix(
    app.wsgi_app,
    x_for=2,       # Number of proxies setting X-Forwarded-For
    x_proto=1,     # Number of proxies setting X-Forwarded-Proto
    x_host=1,      # Number of proxies setting X-Forwarded-Host
    x_port=0,      # Number of proxies setting X-Forwarded-Port
    x_prefix=0     # Number of proxies setting X-Forwarded-Prefix
)
# Parse CORS settings
cors_origins = [origin.strip() for origin in os.getenv('CORS_ORIGINS', '').split(',')]
cors_methods = [method.strip() for method in os.getenv('CORS_METHODS', '').split(',')]
cors_headers = [header.strip() for header in os.getenv('CORS_HEADERS', '').split(',')]
cors_credentials = os.getenv('CORS_CREDENTIALS', 'False')

if not cors_origins or not cors_methods or not cors_headers:
    raise RuntimeError("CORS_ORIGINS, CORS_METHODS, and CORS_HEADERS environment variables must be set.")

CORS(app, 
     resources={r"/*": {
         "origins": cors_origins,
         "methods": cors_methods,
         "allow_headers": cors_headers,
         "supports_credentials": cors_credentials
     }}
)

Talisman(app,
    force_https=True,
    strict_transport_security=True,
    session_cookie_secure=True,
    session_cookie_http_only=True,
    content_security_policy=False
)

app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_KEY_PREFIX'] = 'session:'
app.config['SESSION_REDIS'] = Redis(
    host=os.getenv('REDIS_HOST'),
    port=int(os.getenv('REDIS_PORT')),
    db=int(os.getenv('REDIS_DB')),
    password=os.getenv('REDIS_PASSWORD')
)

Session(app)

# Setup logging
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

file_handler = logging.FileHandler('main_app.log')
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

app.secret_key = os.getenv('FLASK_KEY')
app.config['SESSION_COOKIE_SAMESITE'] = 'Strict'
app.config['SESSION_COOKIE_SECURE'] = True  #HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)

@app.errorhandler(500)
def internal_error(error):
    logger.critical(f"Internal Server Error: {error}")
    return jsonify({'error': 'An internal error occurred'}), 500

@app.errorhandler(429)
def ratelimit_error(error):    
    logger.warning(f"Rate limit exceeded: {error}")

    return jsonify({
        'error': 'Rate limit exceeded, please try again later.',
    }), 429

#TODO: Add custom 404 page

#@app.errorhandler(404)
#def page_not_found(error):
    #logger.warning(f"Page not found: {error}")
    #if request.accept_mimetypes.accept_html:
        #return render_template('404.html'), 404
    #otherwise it returns JSON
    #return jsonify({'error': 'Page not found'}), 404


#MAIN Root
@app.route('/', methods=['GET'])
@limiter.limit("50 per minute")
def website_index():
    cache_buster = datetime.now().strftime("%Y%m%d%H%M%S")
    return render_template('website/index.html', cache_buster=cache_buster)

@app.route('/<filename>', methods=['GET'])
@limiter.limit("50 per minute")
def website_index2(filename):
    #only allow alphanumeric, hyphens, and underscores
    if not re.match(r'^[a-zA-Z0-9_-]+$', filename):
        logger.warning(f"Invalid filename attempted: {filename}")
        abort(404)
    
    allowed_pages = ['support', 'download']
    if filename not in allowed_pages:
        abort(404)
    
    cache_buster = datetime.now().strftime("%Y%m%d%H%M%S")
    
    try:
        return render_template(f'website/{filename}.html', cache_buster=cache_buster)
    except TemplateNotFound:
        logger.warning(f"Template not found: website/{filename}.html")
        abort(404)

# Serve static files
@app.route('/langs/<filename>')
def website_serve_language_file(filename):
    return send_from_directory('website/langs', filename)

@app.route('/styles/<filename>')
def website_serve_style_file(filename):
    return send_from_directory('website/styles', filename)

@app.route('/scripts/<filename>')
def website_serve_script_file(filename):
    return send_from_directory('website/scripts', filename)

@app.route('/sw.js')
def website_serve_sw_file():
    return send_from_directory("website/", "sw.js")

@app.route('/manifest.json')
def website_serve_manifest_file():
    return send_from_directory("website/", "manifest.json")

#PWA Root

@app.route('/pwa/index.htm', methods=['GET'])
@limiter.limit("50 per minute")
def pwa_index():
    cache_buster = datetime.now().strftime("%Y%m%d%H%M%S")
    return render_template('pwa/index.htm', cache_buster=cache_buster)

# Serve static files
@app.route('/pwa/styles/<filename>')
def pwa_serve_style_file(filename):
    return send_from_directory('pwa/styles', filename)

@app.route('/pwa/scripts/<filename>')
def pwa_serve_script_file(filename):
    return send_from_directory('pwa/scripts', filename)

@app.route('/pwa/sw.js')
def pwa_serve_manifest_file():
    return send_from_directory("pwa/", "sw.js")

#Global Fonts Handler
@app.route('/fonts/<path:filename>')
def serve_font(filename):
    if not filename.lower().endswith(('.ttf')):
        abort(404)
    
    #prevent directory traversal
    if '..' in filename or '/' in filename:
        abort(404)
        
    fonts_dir = os.path.join(os.path.dirname(__file__), 'fonts')
    full_path = os.path.join(fonts_dir, filename)

    if not os.path.isfile(full_path):
        logger.warning(f"Font not found: {full_path}")
        return jsonify({'error': 'Font not found'}), 404
    
    return send_from_directory(fonts_dir, filename)

if __name__ == '__main__':    
    # Start the Flask app
    app.run(host=os.getenv('HOST'), port=os.getenv('WEBSITE_PORT'))
