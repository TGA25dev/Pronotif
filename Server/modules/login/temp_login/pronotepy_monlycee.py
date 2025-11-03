import typing

import requests
from bs4 import BeautifulSoup
from functools import partial

import logging
import threading

from pronotepy import ENTLoginError

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:73.0) Gecko/20100101 Firefox/73.0"
}

MAX_RETRIES = 3  # Number of retries
RETRY_DELAY = 5  # Delay between retries in seconds

@typing.no_type_check
def _monlycee_net(
    username: str,
    password: str,
    url: str = "https://psn.monlycee.net",
    **opts: str,
) -> requests.cookies.RequestsCookieJar:
    """
    ENT for monlycee.net with the new website

    Parameters
    ----------
    username : str
        username
    password : str
        password
    url: str
        url of the ent login page

    Returns
    -------
    cookies : cookies
        returns the ent session cookies
    """
    if not url:
        raise ENTLoginError("Login URL is missing")

    if not password:
        raise ENTLoginError("Password is missing")

    if not username:
        raise ENTLoginError("Username is missing")

    logger.info(f"[ENT {url}] Logging in a user...")

    # ENT Connection
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with requests.Session() as session:
                response = session.get(url, headers=HEADERS, timeout=20)
                if response.status_code != 200:
                    raise ENTLoginError(f"Failed to fetch login page. Status code: {response.status_code}")

                html = response.text
                soup = BeautifulSoup(html, "html.parser")
                form = soup.find(id="kc-form-login")

                if form is None:
                    raise ENTLoginError("Login form is missing")

                payload = {"username": username, "password": password}
                action_url = form.get("action")

                r = session.post(action_url, data=payload, headers=HEADERS, timeout=20)
                if r.status_code != 200:
                    raise ENTLoginError(f"Login failed. Status code: {r.status_code}")

                html = r.text
                soup = BeautifulSoup(html, "html.parser")
                username_input = soup.find(id="username")

                if username_input is not None and username_input.get("aria-invalid") == "true":
                    raise ENTLoginError("Username / Password is invalid")

                logger.info(f"User logged in successfully.")
                return session.cookies

        except requests.RequestException as e:
            logger.warning(f"Attempt {attempt} failed for user {username}: {e}")
            if attempt < MAX_RETRIES:
                delay_event = threading.Event()
                delay_event.wait(RETRY_DELAY)

            else:
                raise ENTLoginError(f"Failed to connect to {url} after {MAX_RETRIES} attempts") from e

ile_de_france = partial(_monlycee_net)

