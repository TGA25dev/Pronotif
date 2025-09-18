from flask_limiter import Limiter
from flask import request

from modules.secrets.secrets_manager import get_secret

limiter = Limiter(
    key_func=lambda: request.remote_addr,
    storage_uri=f"redis://default:{get_secret('REDIS_PASSWORD')}@{get_secret('REDIS_HOST')}:{int(get_secret('LIMITER_PORT'))}/{int(get_secret('REDIS_DB', 0))}"
)