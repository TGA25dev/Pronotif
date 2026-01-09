from flask import Flask, jsonify, render_template, send_from_directory, abort
import logging
from datetime import timedelta
import redis
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

sys.path.append('/var/www/pronotif.tech/html/Pronotif/Server')

from modules.secrets.secrets_manager import get_secret # type: ignore

from modules.ratelimit.ratelimiter import limiter # type: ignore

app = Flask(__name__, 
            template_folder='.',
            static_folder='.',
            static_url_path='')

redis_connection = redis.Redis(
    host=get_secret('REDIS_HOST'),
    port=int(get_secret('REDIS_PORT')),
    db=int(get_secret('REDIS_DB')),
    password=get_secret('REDIS_PASSWORD')
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
cors_origins = [origin.strip() for origin in get_secret('CORS_ORIGINS', '').split(',')]
cors_methods = [method.strip() for method in get_secret('CORS_METHODS', '').split(',')]
cors_headers = [header.strip() for header in get_secret('CORS_HEADERS', '').split(',')]
cors_credentials = get_secret('CORS_CREDENTIALS', 'False')

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
    host=get_secret('REDIS_HOST'),
    port=int(get_secret('REDIS_PORT')),
    db=int(get_secret('REDIS_DB')),
    password=get_secret('REDIS_PASSWORD')
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

app.secret_key = get_secret('FLASK_KEY')
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

@app.route('/fonts_manager.css', methods=['GET'])
def website_serve_fonts_manager():
    return send_from_directory("/", "fonts_manager.css")

@app.route('/<filename>')
def website_serve_seo_files(filename):
    if filename not in ['robots.txt', 'sitemap.xml', 'favicon.ico']:
        abort(404)
    return send_from_directory('.', filename)

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

# Serve static files
@app.route('/assets/<path:filename>')
def website_serve_assets_file(filename):
    website_assets_path = os.path.join(app.root_path, 'website/assets', filename)
    if os.path.isfile(website_assets_path):
        return send_from_directory('website/assets', filename)
    
    #fall back to shared assets folder
    shared_assets_path = os.path.join(app.root_path, 'assets', filename)
    if os.path.isfile(shared_assets_path):
        return send_from_directory('assets', filename)
    
    abort(404)

@app.route('/pwa/splash/<path:filename>')
def pwa_serve_splash_file(filename):
    return send_from_directory('pwa/splash', filename)

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

if __name__ == '__main__':    
    # Start the Flask app
    app.run(host=get_secret('HOST'), port=get_secret('WEBSITE_PORT'))
