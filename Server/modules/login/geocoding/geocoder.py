from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder

def geocode_city(city_name: str) -> tuple[float, float] | None:
    """
    Geocode the city name to get its latitude and longitude.
    """
    geolocator = Nominatim(user_agent="Pronotif")
    location = geolocator.geocode(city_name)
    if location:
        return location.latitude, location.longitude
    else:
        return None
    
def get_country_name(latitude: float, longitude: float) -> str | None:
    """
    Get the country name for given latitude and longitude.
    """
    geolocator = Nominatim(user_agent="Pronotif")
    location = geolocator.reverse((latitude, longitude), exactly_one=True)
    if location and location.raw.get('address', {}).get('country'):
        return location.raw['address']['country']
    else:
        return None
    
def get_timezone(latitude: str, longitude :str) -> str | None:
    """
    Get the timezone of the user's city using the geocode and set data class.
    """
    tf = TimezoneFinder()
    timezone_str = tf.timezone_at(lng=longitude, lat=latitude)
    if timezone_str:
        return timezone_str
    else:
        return None
    
def get_postal_code(latitude: float, longitude: float) -> str | None:
    """
    Get the postal code for given latitude and longitude.
    """
    geolocator = Nominatim(user_agent="Pronotif")
    location = geolocator.reverse((latitude, longitude), exactly_one=True)
    if location and location.raw.get('address', {}).get('postcode'):
        return location.raw['address']['postcode']
    else:
        return None
    
def get_region(latitude: float, longitude: float) -> str | None:
    """
    Get the administrative region for given latitude and longitude.
    """
    geolocator = Nominatim(user_agent="Pronotif")
    location = geolocator.reverse((latitude, longitude), exactly_one=True)
    if location and location.raw.get('address', {}).get('state'):
        return location.raw['address']['state']
    else:
        return None
    
def get_timezone_from_state(state_name: str) -> str | None:
    """
    Get the timezone for a given state name.
    """
    geolocator = Nominatim(user_agent="Pronotif")
    location = geolocator.geocode(state_name)
    if location:
        tf = TimezoneFinder()
        timezone_str = tf.timezone_at(lng=location.longitude, lat=location.latitude)
        return timezone_str
    else:
        return None