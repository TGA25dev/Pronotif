import logging
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder

logger = logging.getLogger(__name__)
geolocator = Nominatim(user_agent="Pronotif")
timeouts = [5, 10, 20]

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

def get_timezone(latitude: str, longitude: str) -> str | None:
    """
    Get the timezone of the user's city using the geocode and set data class.
    This function is local and does not require network retries.
    """
    try:
        tf = TimezoneFinder()
        timezone_str = tf.timezone_at(lng=longitude, lat=latitude)
        if timezone_str:
            return timezone_str
        else:
            logger.warning(f"get_timezone: No timezone found.")
            return None
    except Exception as e:
        logger.warning(f"get_timezone: Error: {e}")
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

    retries = 0
    for timeout in timeouts:
        try:
            location = geolocator.geocode(state_name, timeout=timeout)
            if location:
                tf = TimezoneFinder()
                timezone_str = tf.timezone_at(lng=location.longitude, lat=location.latitude)

                if retries > 0:
                    logger.warning(f"get_timezone_from_state: succeeded after {retries} retries")
                return timezone_str
            else:

                logger.warning(f"get_timezone_from_state: No location found after {retries+1} attempts")
                return None
            
        except Exception as e:
            retries += 1
            logger.warning(f"get_timezone_from_state: retry {retries} due to error: {e}")
            continue
        
    logger.warning(f"get_timezone_from_state: failed after {retries} retries")
    return None