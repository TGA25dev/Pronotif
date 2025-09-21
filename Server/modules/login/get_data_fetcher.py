import logging
import json
from typing import Optional, Dict, Any

from .geocoding.geocoder import (
    geocode_city,
    get_timezone,
    get_country_name,
    get_postal_code,
    get_region,
)
from .schools.search_schools import search_school_from_coords

logger = logging.getLogger(__name__)

def get_city_coords(raw_city_name: str) -> Optional[Dict[str, Any]]:
    """
    Resolve a raw city name into enriched geographic metadata.
    Returns dict or None if not found.
    """
    if not raw_city_name or not raw_city_name.strip():
        logger.warning("Empty city name supplied")
        return None

    try:
        geocoded_city_coords = geocode_city(raw_city_name)
    except Exception as e:
        logger.error(f"City geocoding failed for '{raw_city_name}': {e}")
        return None

    if not geocoded_city_coords or len(geocoded_city_coords) < 2:
        logger.info(f"Unknown city: {raw_city_name}")
        return None

    lat, lon = geocoded_city_coords[0], geocoded_city_coords[1]

    try:
        return {
            "latitude": lat,
            "longitude": lon,
            "postal_code": get_postal_code(lat, lon),
            "country": get_country_name(lat, lon),
            "region": get_region(lat, lon),
            "timezone": get_timezone(lat, lon)
        }
    except Exception as e:
        logger.error(f"Failed enriching geocode data for '{raw_city_name}': {e}")
        return None


def get_schools_from_city(
    city_name: Optional[str],
    coords: bool,
    lat: Optional[float],
    lon: Optional[float]
) -> Optional[Dict[str, Any]]:
    """
    Retrieve schools for a given city (by name) or provided coordinates.
    Returns dict with schools + region/country/timezone or None.
    """
    city_coords: Optional[Dict[str, Any]] = None

    if coords:
        if lat is None or lon is None:
            logger.warning("Coordinates mode selected but lat/lon missing")
            return None
        try:
            city_coords = {
                "latitude": lat,
                "longitude": lon,
                "postal_code": get_postal_code(lat, lon),
                "country": get_country_name(lat, lon),
                "region": get_region(lat, lon),
                "timezone": get_timezone(lat, lon)
            }
        except Exception as e:
            logger.error(f"Reverse geo enrichment failed ({lat},{lon}): {e}")
            return None
    else:
        if not city_name:
            logger.warning("Neither city name nor coordinates provided")
            return None
        
        city_coords = get_city_coords(city_name)
        if not city_coords:
            return None

    #Check if the school is international
    is_international_school = False

    if city_coords and "country" in city_coords:

        country = city_coords.get("country")
        if country and country.lower() != "france":

            is_international_school = True
            logger.info(f"International school detected in: {country}")

    latitude = city_coords["latitude"]
    longitude = city_coords["longitude"]
    postal_code = city_coords.get("postal_code")

    city_schools = []

    if is_international_school == False: #If school is in France, search for schools (API doesnt support other countries)
        try:
            schools_raw = search_school_from_coords(str(latitude), str(longitude))
        except Exception as e:
            logger.error(f"School search failed {e}")
            return None

        try:
            if isinstance(schools_raw, str):
                schools = json.loads(schools_raw)
            else:
                schools = schools_raw

        except (TypeError, json.JSONDecodeError) as e:
            logger.error(f"Failed parsing school search result: {e}")
            return None

        if not isinstance(schools, list):
            logger.warning("Unexpected school search result structure")
            return None

        if postal_code:
            city_schools = [s for s in schools if s.get("cp") == postal_code]
        else:
            city_schools = schools  #fallback

    return {
        "schools": city_schools,
        "region": city_coords["region"],
        "country": city_coords["country"],
        "timezone": city_coords["timezone"],
        "is_international": is_international_school
    }