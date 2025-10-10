# SPDX-License-Identifier: AGPL-3.0-only
# This file is adapted from Pawnote.js:
# - geolocation https://github.com/LiterateInk/Pawnote.js/blob/f2da3df464be324ceb9aeb8d8ce3b983e55664d7/src/api/geolocation.ts#L12
# Original authors: LiterateInk contributors (GPL-3.0)
# Translated and modified for this project by TGA25dev, 2025. Licensed under AGPL-3.0.

import requests

def search_school_from_coords(latitude: str, longitude: str):
    """
    Search for the school by making a request to the 'Education Nationale' API using latitude and longitude.
    """

    url = "https://www.index-education.com/swie/geoloc.php"
    headers = {"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"}
    payload = f'data={{"nomFonction":"geoLoc","lat":"{latitude}","long":"{longitude}"}}'

    response = requests.post(url, data=payload, headers=headers, timeout=15)

    if response.ok:
        return response.text  # JSON of PRONOTE instances
    else:
        return response.status_code, response.text