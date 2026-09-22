"""Prefer official station APIs; optional temporary public dashboard adapters."""
from django.conf import settings

from ..normalization import normalize_ecowitt, normalize_wunderground
from .http import ProviderError, get_json
from .scraping import fetch_ecowitt_page, fetch_wunderground_page

ECOWITT_URL = "https://api.ecowitt.net/api/v3/device/real_time"
WUNDERGROUND_URL = "https://api.weather.com/v2/pws/observations/current"


def station_access_method(station_id):
    config = settings.CONDITIONS
    mode = config.get("station_mode", "api")
    if mode != "auto":
        return mode
    keys = ("ecowitt_application_key", "ecowitt_api_key", "ecowitt_mac") if station_id == "pescadores" else ("wunderground_api_key",)
    return "api" if all(config.get(key) for key in keys) else "public_page"


def fetch_ecowitt():
    config = settings.CONDITIONS
    if station_access_method("pescadores") == "public_page":
        return fetch_ecowitt_page()
    if not all(config[key] for key in ("ecowitt_application_key", "ecowitt_api_key", "ecowitt_mac")):
        raise ProviderError("not_configured")
    data = get_json(ECOWITT_URL, {
        "application_key": config["ecowitt_application_key"],
        "api_key": config["ecowitt_api_key"], "mac": config["ecowitt_mac"],
        "call_back": "outdoor,wind,pressure,rainfall,rainfall_piezo",
        "temp_unitid": 1, "pressure_unitid": 3, "wind_speed_unitid": 7, "rainfall_unitid": 12,
    }, config["external_timeout_seconds"])
    return {**normalize_ecowitt(data, stale_minutes=config["stale_minutes"]), "access_method": "api"}


def fetch_wunderground():
    config = settings.CONDITIONS
    if station_access_method("yacht") == "public_page":
        return fetch_wunderground_page()
    if not config["wunderground_api_key"]:
        raise ProviderError("not_configured")
    data = get_json(WUNDERGROUND_URL, {
        "stationId": "IPAYSA15", "format": "json", "units": "m",
        "numericPrecision": "decimal", "apiKey": config["wunderground_api_key"],
    }, config["external_timeout_seconds"])
    return {**normalize_wunderground(data, stale_minutes=config["stale_minutes"]), "access_method": "api"}
