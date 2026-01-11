# SPDX-License-Identifier: AGPL-3.0-only
# Portions of this file are adapted from Pawnote.js:
# - cleanURL: https://github.com/LiterateInk/Pawnote.js/blob/46535542c0b50afe8af565d719956076eb13ae57/src/api/helpers/clean-url.ts
# - instance: https://github.com/LiterateInk/Pawnote.js/blob/46535542c0b50afe8af565d719956076eb13ae57/src/api/instance.ts
# Original authors: LiterateInk contributors (GPL-3.0)
# Translated and modified for this project by TGA25dev, 2025. Licensed under AGPL-3.0.

from urllib.parse import urlparse, urlunparse
import requests
import re
from typing import Optional, Dict

ALLOWED_SCHEMES = {"https", "http"}
BLOCKED_HOST_PATTERNS = (
    r"^localhost$",
    r"^127\.\d+\.\d+\.\d+$",
    r"^0\.0\.0\.0$",
    r"^10\.\d+\.\d+\.\d+$",
    r"^192\.168\.\d+\.\d+$",
    r"^172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+$"
)

APP_ID = "0D264427-EEFC-4810-A9E9-346942A862A4"
INFO_ENDPOINT = f"pronote/infoMobileApp.json?id={APP_ID}"

def _host_blocked(host: str) -> bool:
    h = host.split(":")[0].lower()
    for p in BLOCKED_HOST_PATTERNS:
        if re.match(p, h):
            return True
    return False

def clean_url(url: str) -> Optional[str]:
    if not url:
        return None
    parsed = urlparse(url.strip())
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        return None
    if not parsed.netloc or _host_blocked(parsed.netloc):
        return None

    #keep the path as-is but remove .html if present
    path = parsed.path
    if path.endswith('.html'):
        path = path.rsplit('/', 1)[0]
    
    #Ensure path doesn't end with slash for consistency
    if path.endswith('/'):
        path = path.rstrip('/')
    
    return urlunparse((
        parsed.scheme.lower(),
        parsed.netloc,
        path,
        "", "", ""
    ))

def test_url(instance_url: str) -> Dict[str, Optional[str]]:
    cleaned = clean_url(instance_url)
    if not cleaned:
        return {"success": False, "region": None, "nom_etab": None, "error": "invalid_url"}

    info_url = f"{cleaned}/{INFO_ENDPOINT}"
    try:
        resp = requests.get(
            info_url,
            timeout=5,
            allow_redirects=False,
            headers={"Accept": "application/json"}
        )
    except requests.Timeout:
        return {"success": False, "region": None, "nom_etab": None, "error": "timeout"}
    except requests.RequestException:
        return {"success": False, "region": None, "nom_etab": None, "error": "network_error"}

    if resp.status_code != 200:
        return {"success": False, "region": None, "nom_etab": None, "error": f"http_{resp.status_code}"}

    try:
        data = resp.json()
    except ValueError:
        return {"success": False, "region": None, "nom_etab": None, "error": "invalid_json"}

    region_url = None
    nom_etab = None
    if isinstance(data, dict):
        region_url = data.get("collectivite", {}).get("urlCollectivite")
        nom_etab = data.get("nomEtab")

    return {"success": True, "region": region_url, "nom_etab": nom_etab, "error": None}

def verify(manual_pronote_link: str) -> Dict[str, Optional[str]]:
    res = test_url(manual_pronote_link)
    if res["success"]:
        return {
            "isValid": True,
            "region": res["region"],
            "nomEtab": res["nom_etab"]
        }
    return {
        "isValid": False,
        "error": res.get("error")
    }