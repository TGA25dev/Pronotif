import logging
from geopy.geocoders import Nominatim
import sys
import os
import requests

current_dir = os.path.dirname(os.path.abspath(__file__))
server_dir = os.path.abspath(os.path.join(current_dir, "../../../"))
sys.path.append(server_dir)

from modules.secrets.secrets_manager import get_secret

logger = logging.getLogger(__name__)
geolocator = Nominatim(user_agent="Pronotif")
timeouts = [5, 10, 20]

GEONAMES_USERNAME = get_secret("GEONAMES_USERNAME")

def geocode_city(city_name: str) -> tuple[float, float] | None:
    """
    Geocode the city name to get its latitude and longitude.
    Retries with increasing timeouts on network errors.
    """
    
    for attempt, timeout in enumerate(timeouts, 1):
        try:
            location = geolocator.geocode(city_name, timeout=timeout)
            if location:
                return location.latitude, location.longitude
            else:
                logger.warning(f"geocode_city: No location found for after {attempt} attempts")
                return None
        except Exception as e:
            logger.warning(f"geocode_city: Attempt {attempt} failed due to: {e}")
            continue
    logger.warning(f"geocode_city: Failed to geocode after {len(timeouts)} attempts")
    return None

def get_country_name(latitude: float, longitude: float) -> str | None:
    """
    Get the country name for given latitude and longitude.
    Retries with increasing timeouts on network errors.
    """
    for attempt, timeout in enumerate(timeouts, 1):
        try:
            location = geolocator.reverse((latitude, longitude), exactly_one=True, timeout=timeout)
            if location and location.raw.get('address', {}).get('country'):
                return location.raw['address']['country']
            else:
                logger.warning(f"get_country_name: No country found after {attempt} attempts")
                return None
        except Exception as e:
            logger.warning(f"get_country_name: Attempt {attempt} failed due to: {e}")
            continue
    logger.warning(f"get_country_name: Failed after {len(timeouts)} attempts.")
    return None

def get_timezone(latitude: float, longitude: float) -> str | None:
    """
    Get the timezone for given latitude and longitude using GeoNames.
    Retries with increasing timeouts on network errors.
    """
    for attempt, timeout in enumerate(timeouts, 1):
        try:
            response = requests.get(
                "https://secure.geonames.org/timezoneJSON",
                params={
                    "lat": latitude,
                    "lng": longitude,
                    "username": GEONAMES_USERNAME,
                },
                timeout=timeout,
            )
            response.raise_for_status()
            data = response.json()

            timezone_id = data.get("timezoneId")
            if timezone_id:
                return timezone_id

            logger.warning(
                f"get_timezone: No timezone found after {attempt} attempts"
            )
            return None
        
        except Exception as e:
            logger.warning(
                f"get_timezone: Attempt {attempt} failed due to: {e}"
            )
            continue

    logger.warning(
        f"get_timezone: Failed after {len(timeouts)} attempts"
    )
    return None

def get_postal_code(latitude: float, longitude: float) -> str | None:
    """
    Get the postal code for given latitude and longitude.
    Retries with increasing timeouts on network errors.
    """
    for attempt, timeout in enumerate(timeouts, 1):
        try:
            location = geolocator.reverse((latitude, longitude), exactly_one=True, timeout=timeout)
            if location and location.raw.get('address', {}).get('postcode'):
                return location.raw['address']['postcode']
            else:
                logger.warning(f"get_postal_code: No postal code found after {attempt} attempts")
                return None
        except Exception as e:
            logger.warning(f"get_postal_code: Attempt {attempt} failed due to: {e}")
            continue
    logger.warning(f"get_postal_code: Failed after {len(timeouts)} attempts ")
    return None

def get_region(latitude: float, longitude: float) -> str | None:
    """
    Get the administrative region for given latitude and longitude.
    Retries with increasing timeouts on network errors.
    """
    for attempt, timeout in enumerate(timeouts, 1):
        try:
            location = geolocator.reverse((latitude, longitude), exactly_one=True, timeout=timeout, zoom=8)
            if location and location.raw.get('address', {}).get('state'):
                return location.raw['address']['state']
            else:
                logger.warning(f"get_region: No region found at attempt {attempt}, retrying…")
                continue
        except Exception as e:
            logger.warning(f"get_region: Attempt {attempt} failed due to: {e}")
            continue
    logger.warning(f"get_region: Failed after {len(timeouts)} attempts")
    return None

def get_timezone_from_state(state_name: str) -> str | None:
    """
    Get the timezone for a given state name.
    Retries with increasing timeouts on network errors.
    """
    static_timezones = {
        "Île-de-France": "Europe/Paris",
        "Ile-de-France": "Europe/Paris",
        "https://psn.monlycee.net": "Europe/Paris",
    }
    if state_name in static_timezones:
        return static_timezones[state_name]

    for attempt, timeout in enumerate(timeouts):
        try:
            location = geolocator.geocode(state_name, timeout=timeout)
            if not location:
                logger.warning(
                    f"get_timezone_from_state: No location found after {attempt} attempts"
                )
                return None

            return get_timezone(
                location.latitude,
                location.longitude,
            )
        
        except Exception as e:
            logger.warning(
                f"get_timezone_from_state: Attempt {attempt} failed due to: {e}"
            )
            continue

    logger.warning(
        f"get_timezone_from_state: Failed after {len(timeouts)} attempts"
    )
    return None