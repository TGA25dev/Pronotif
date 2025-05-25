import os
from flask_limiter import Limiter
from flask import request

limiter = Limiter(
    key_func=lambda: request.remote_addr,
    storage_uri=f"redis://{os.getenv('REDIS_HOST')}:{int(os.getenv('LIMITER_PORT'))}"
)