"""Open-Meteo forecast, deliberately independent from measured observations."""
import math
from datetime import datetime, timezone as dt_timezone
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

from ..utils import degrees_to_cardinal
from .http import ProviderError, get_json

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
LOCAL_TIMEZONE = ZoneInfo("America/Montevideo")
HOURLY = {
    "temperature_c": ("temperature_2m", -100, 70),
    "humidity_pct": ("relative_humidity_2m", 0, 100),
    "precipitation_mm": ("precipitation", 0, 2000),
    "precipitation_probability_pct": ("precipitation_probability", 0, 100),
    "wind_speed_kmh": ("wind_speed_10m", 0, 500),
    "wind_gust_kmh": ("wind_gusts_10m", 0, 500),
    "wind_direction_deg": ("wind_direction_10m", 0, 360),
    "weather_code": ("weather_code", 0, 99),
}
DAILY = {
    "temperature_min_c": ("temperature_2m_min", -100, 70),
    "temperature_max_c": ("temperature_2m_max", -100, 70),
    "wind_speed_max_kmh": ("wind_speed_10m_max", 0, 500),
    "wind_gust_max_kmh": ("wind_gusts_10m_max", 0, 500),
    "precipitation_probability_max_pct": ("precipitation_probability_max", 0, 100),
    "precipitation_sum_mm": ("precipitation_sum", 0, 2000),
    "weather_code": ("weather_code", 0, 99),
}
EXPECTED_UNITS = {
    "temperature_c": "°C", "temperature_min_c": "°C", "temperature_max_c": "°C",
    "humidity_pct": "%", "precipitation_mm": "mm", "precipitation_sum_mm": "mm",
    "precipitation_probability_pct": "%", "precipitation_probability_max_pct": "%",
    "wind_speed_kmh": "km/h", "wind_gust_kmh": "km/h", "wind_speed_max_kmh": "km/h",
    "wind_gust_max_kmh": "km/h", "wind_direction_deg": "°", "weather_code": "wmo code",
}


def _number(value, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        return None
    return value if math.isfinite(value) and minimum <= value <= maximum else None


def _value(series, spec, index):
    name, minimum, maximum = spec
    values = series.get(name)
    if not isinstance(values, list) or index >= len(values):
        return None
    return _number(values[index], minimum, maximum)


def _timestamp(value):
    if _number(value, 0, 4102444800) is None:
        return None
    return datetime.fromtimestamp(value, dt_timezone.utc).astimezone(LOCAL_TIMEZONE)


def unavailable_forecast(error="forecast_unavailable"):
    return {
        "provider": "open_meteo", "source_url": "https://open-meteo.com/",
        "available": False, "error": error, "fetched_at": None,
        "age_minutes": None, "stale": True, "hourly": [], "daily": None,
    }


def normalize_forecast(payload, *, now=None):
    now = now or timezone.now()
    result = unavailable_forecast()
    if not isinstance(payload, dict):
        raise ProviderError("invalid_response")
    hourly, daily = payload.get("hourly"), payload.get("daily")
    if not isinstance(hourly, dict) or not isinstance(daily, dict):
        raise ProviderError("invalid_response")
    times, dates = hourly.get("time"), daily.get("time")
    if not isinstance(times, list) or not isinstance(dates, list):
        raise ProviderError("invalid_response")
    for group, fields in (("hourly", HOURLY), ("daily", DAILY)):
        units = payload.get(group + "_units")
        if not isinstance(units, dict) or units.get("time") != "unixtime":
            raise ProviderError("invalid_response")
        for name, spec in fields.items():
            if spec[0] in payload[group] and units.get(spec[0]) != EXPECTED_UNITS[name]:
                raise ProviderError("invalid_response")
    hours = []
    for index, raw_time in enumerate(times[:192]):
        stamp = _timestamp(raw_time)
        if stamp is None:
            continue
        row = {key: _value(hourly, spec, index) for key, spec in HOURLY.items()}
        if not any(value is not None for value in row.values()):
            continue
        row.update(timestamp=stamp.isoformat(), wind_direction_cardinal=degrees_to_cardinal(row["wind_direction_deg"]))
        hours.append(row)
    days = []
    for index, raw_time in enumerate(dates[:7]):
        stamp = _timestamp(raw_time)
        if stamp is None:
            continue
        date = stamp.date().isoformat()
        row = {key: _value(daily, spec, index) for key, spec in DAILY.items()}
        speeds = [hour["wind_speed_kmh"] for hour in hours if hour["timestamp"][:10] == date and hour["wind_speed_kmh"] is not None]
        # Minimum is derived only from real hourly predictions for that calendar day.
        row.update(date=date, wind_speed_min_kmh=min(speeds) if speeds else None)
        days.append(row)
    if not hours:
        raise ProviderError("invalid_response")
    result.update(available=True, error=None, fetched_at=now.isoformat(), age_minutes=0, stale=False, hourly=hours, days=days)
    return result


def present_forecast(forecast, *, now=None):
    """Select upcoming hours/today at response time, including after midnight/cache hits."""
    now = now or timezone.now()
    result = dict(forecast)
    days = result.pop("days", [])
    result["daily"] = next((day for day in days if day["date"] == now.astimezone(LOCAL_TIMEZONE).date().isoformat()), None)
    result["hourly"] = [hour for hour in forecast.get("hourly", []) if datetime.fromisoformat(hour["timestamp"]) >= now][:12]
    if forecast.get("fetched_at"):
        age_seconds = max(0, (now - datetime.fromisoformat(forecast["fetched_at"])).total_seconds())
        result["age_minutes"] = round(age_seconds / 60, 1)
        result["stale"] = age_seconds > settings.CONDITIONS["forecast_cache_seconds"] or bool(result.get("last_known"))
    if not result["hourly"]:
        result["available"] = False
    return result


def fetch_forecast():
    config = settings.CONDITIONS
    data = get_json(OPEN_METEO_URL, {
        "latitude": config["latitude"], "longitude": config["longitude"],
        "hourly": ",".join(spec[0] for spec in HOURLY.values()),
        "daily": ",".join(spec[0] for spec in DAILY.values()),
        "forecast_days": 2, "timezone": "America/Montevideo", "timeformat": "unixtime",
        "temperature_unit": "celsius", "wind_speed_unit": "kmh", "precipitation_unit": "mm",
    }, config["external_timeout_seconds"])
    return normalize_forecast(data)
