"""Official station APIs; credentials never leave this backend adapter."""
from django.conf import settings

from ..normalization import normalize_ecowitt, normalize_wunderground
from .http import ProviderError, get_json

ECOWITT_URL = "https://api.ecowitt.net/api/v3/device/real_time"
WUNDERGROUND_URL = "https://api.weather.com/v2/pws/observations/current"


def fetch_ecowitt():
    config = settings.CONDITIONS
    if not all(config[key] for key in ("ecowitt_application_key", "ecowitt_api_key", "ecowitt_mac")):
        raise ProviderError("not_configured")
    data = get_json(ECOWITT_URL, {
        "application_key": config["ecowitt_application_key"],
        "api_key": config["ecowitt_api_key"], "mac": config["ecowitt_mac"],
        "call_back": "outdoor,wind,pressure,rainfall,rainfall_piezo",
        "temp_unitid": 1, "pressure_unitid": 3, "wind_speed_unitid": 7, "rainfall_unitid": 12,
    }, config["external_timeout_seconds"])
    return normalize_ecowitt(data, stale_minutes=config["stale_minutes"])


def fetch_wunderground():
    config = settings.CONDITIONS
    if not config["wunderground_api_key"]:
        raise ProviderError("not_configured")
    data = get_json(WUNDERGROUND_URL, {
        "stationId": "IPAYSA15", "format": "json", "units": "m",
        "numericPrecision": "decimal", "apiKey": config["wunderground_api_key"],
    }, config["external_timeout_seconds"])
    return normalize_wunderground(data, stale_minutes=config["stale_minutes"])
