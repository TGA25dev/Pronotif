from infisical_sdk import InfisicalSDKClient
import os
from pathlib import Path
from dotenv import load_dotenv
from pathlib import Path

infisical_client = InfisicalSDKClient(host="https://eu.infisical.com")

script_dir = Path(__file__).parent.absolute()
env_path = (script_dir / "../..").resolve() / ".env"

# Load environment variables
load_dotenv(env_path)

infisical_client.auth.universal_auth.login(
  str(os.getenv("CLIENT_ID")),
  str(os.getenv("CLIENT_SECRET")),
)


def get_secret(name, default=None, cast=None, required=False):
    """
    Get a secret from Infisical and optionally cast it.
    """
    secret_obj = infisical_client.secrets.get_secret_by_name(
        name,
        environment_slug=os.getenv("ENV_SLUG"),
        secret_path=os.getenv("SECRET_PATH"),
        project_id=os.getenv("PROJECT_ID"),
        project_slug=os.getenv("PROJECT_SLUG")
    )

    # Extract the actual value
    val = secret_obj.secretValue if secret_obj else None

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