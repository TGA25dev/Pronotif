import requests

def search_school_from_coords(latitude: str, longitude: str):
    """
    Search for the school by making a request to the 'Education Nationale' API using latitude and longitude.
    """

    url = "https://www.index-education.com/swie/geoloc.php"
    headers = {"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"}
    payload = f'data={{"nomFonction":"geoLoc","lat":"{latitude}","long":"{longitude}"}}'

    response = requests.post(url, data=payload, headers=headers)

    if response.ok:
        return response.text  # JSON of PRONOTE instances
    else:
        return response.status_code, response.text