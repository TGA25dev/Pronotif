import typing

import requests
from bs4 import BeautifulSoup
from functools import partial

import logging

from pronotepy import ENTLoginError

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:73.0) Gecko/20100101 Firefox/73.0"
}

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
    with requests.Session() as session:
        response = session.get(url, headers=HEADERS)

        soup = BeautifulSoup(response.text, "html.parser")
        form = soup.find(id="kc-form-login")

        if form is None:
            raise ENTLoginError("Login form is missing")

        payload = {"username": username, "password": password}

        r = session.post(form.get("action"), data=payload, headers=HEADERS)

        soup = BeautifulSoup(r.text, "html.parser")
        username_input = soup.find(id="username")
        if username_input is not None and username_input.get("aria-invalid") == "true":
            raise ENTLoginError("Username / Password is invalid")

        return session.cookies

ile_de_france = partial(_monlycee_net)

