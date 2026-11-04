from infisical_sdk import InfisicalSDKClient
import os
import re
import time
import threading
from pathlib import Path
from dotenv import load_dotenv

infisical_client = InfisicalSDKClient(host="https://eu.infisical.com")

script_dir = Path(__file__).parent.absolute()
env_path = (script_dir / "../..").resolve() / ".env"

# Load environment variables
load_dotenv(env_path)

infisical_client.auth.universal_auth.login(
  str(os.getenv("CLIENT_ID")),
  str(os.getenv("CLIENT_SECRET")),
)

_secret_cache = {}
_secret_cache_lock = threading.Lock()


def _extract_retry_delay(error_message):
    match = re.search(r"try again in\s+(\d+)\s+seconds", str(error_message), re.IGNORECASE)
    if match:
        return max(1, int(match.group(1)))
    return None


def _get_secret_from_infisical(name):
    environment_slug = os.getenv("ENV_SLUG")
    secret_path = os.getenv("SECRET_PATH")
    project_id = os.getenv("PROJECT_ID")
    project_slug = os.getenv("PROJECT_SLUG")

    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            secret_obj = infisical_client.secrets.get_secret_by_name(
                name,
                environment_slug=environment_slug,
                secret_path=secret_path,
                project_id=project_id,
                project_slug=project_slug
            )
            return secret_obj.secretValue if secret_obj else None

        except Exception as error:
            error_message = str(error)
            is_rate_limited = "status: 429" in error_message.lower() or "rate limit exceeded" in error_message.lower()

            if not is_rate_limited or attempt == max_attempts - 1:
                raise

            retry_delay = _extract_retry_delay(error_message) or (2 ** attempt)
            time.sleep(retry_delay)


def get_secret(name, default=None, cast=None, required=False):
    """
    Get a secret from Infisical and optionally cast it.
    """
    with _secret_cache_lock:
        if name in _secret_cache:
            val = _secret_cache[name]
        else:
            val = os.getenv(name)
            if val is None or val == "":
                val = _get_secret_from_infisical(name)
            _secret_cache[name] = val

    if val is None or val == "":
        if required:
            raise ValueError(f"Missing required secret: {name}")
        return default

    if cast is bool:
        return str(val).lower() in ("1", "true", "yes", "on")
    
    if cast:
        try:
            return cast(val)
        except Exception:
            raise

    return val