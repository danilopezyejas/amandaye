"""Translate station responses into our metric, explicitly nullable contract.

    Rain rate (mm/h) and the measured last-hour accumulation (mm) are different
    quantities. Neither the daily accumulation nor a rate fills rain_1h_mm.
"""

from datetime import datetime, timedelta, timezone

from .utils import (
    degrees_to_cardinal,
    fahrenheit_to_celsius,
    finite_number,
    inches_to_mm,
    inhg_to_hpa,
    knots_to_kmh,
    mph_to_kmh,
    parse_timestamp,
)


DEFAULT_STALE_MINUTES = 20
FUTURE_TOLERANCE_SECONDS = 300
STATIONS = {
    "pescadores": {
        "id": "pescadores",
        "name": "Club de Pescadores",
        "provider": "ecowitt",
        "location": "Paysandú, Uruguay",
        "source_url": "https://www.ecowitt.net/home/share?authorize=PHC0G3",
    },
    "yacht": {
        "id": "yacht",
        "name": "Yacht Club Paysandú",
        "provider": "wunderground",
        "location": "Paysandú, Uruguay",
        "source_url": "https://www.wunderground.com/dashboard/pws/IPAYSA15",
    },
}

# Broad physical bounds reject malformed/sentinel values without guessing data.
FIELD_LIMITS = {
    "temperature_c": (-100, 70),
    "humidity_pct": (0, 100),
    "pressure_hpa": (300, 1200),
    "wind_speed_kmh": (0, 500),
    "wind_gust_kmh": (0, 500),
    "wind_direction_deg": (0, 360),
    "rain_1h_mm": (0, 1000),
    "rain_rate_mmh": (0, 2000),
}
FIELD_NAMES = tuple(FIELD_LIMITS)


def validate_measurement(field, value):
    number = finite_number(value)
    minimum, maximum = FIELD_LIMITS[field]
    if number is None or not minimum <= number <= maximum:
        return None
    if field == "wind_direction_deg":
        return round(number % 360, 1) % 360
    return round(number, 2)


def _now(now):
    return now if now is not None else datetime.now(timezone.utc)


def _valid_timestamp(value, now):
    timestamp = parse_timestamp(value)
    if timestamp is None or timestamp > now + timedelta(seconds=FUTURE_TOLERANCE_SECONDS):
        return None
    return timestamp


def _empty_station(station_id):
    return {
        **STATIONS[station_id],
        **{field: None for field in FIELD_NAMES},
        "wind_direction_cardinal": None,
        "rain_detected": None,
        "timestamp": None,
        "field_timestamps": {},
        "age_minutes": None,
        "stale": True,
        "available": False,
        "error": None,
    }


def unavailable_station(station_id, error="station_unavailable"):
    station = _empty_station(station_id)
    station["error"] = error
    return station


def refresh_station_age(station, *, now=None, stale_minutes=DEFAULT_STALE_MINUTES):
    """Return a copy so cached source timestamps keep aging on every API read."""
    result = dict(station)
    timestamp = _valid_timestamp(result.get("timestamp"), _now(now))
    if timestamp is None:
        result.update(age_minutes=None, stale=True, available=False)
        if result.get("error") is None:
            result["error"] = "invalid_timestamp"
        return result
    age = max(0, (_now(now) - timestamp).total_seconds() / 60)
    result.update(age_minutes=round(age, 1), stale=age > stale_minutes)
    return result


def _finish_station(station, *, now, stale_minutes):
    station["wind_direction_cardinal"] = degrees_to_cardinal(station["wind_direction_deg"])
    rain_values = [station[field] for field in ("rain_1h_mm", "rain_rate_mmh") if station[field] is not None]
    station["rain_detected"] = any(value > 0 for value in rain_values) if rain_values else None
    station["available"] = any(station[field] is not None for field in FIELD_NAMES)
    if not station["available"]:
        station["error"] = "station_unavailable"
    return refresh_station_age(station, now=now, stale_minutes=stale_minutes)


def _ecowitt_value(field, node):
    """Interpret the documented unit label, including default imperial responses."""
    if not isinstance(node, dict) or not isinstance(node.get("unit"), str):
        return None
    number = finite_number(node.get("value"))
    if number is None:
        return None
    unit = node["unit"].strip().lower().replace("º", "°").replace("℃", "°c").replace("℉", "°f")
    if field == "temperature_c":
        value = number if unit in ("°c", "c") else fahrenheit_to_celsius(number) if unit in ("°f", "f") else None
    elif field == "humidity_pct":
        value = number if unit == "%" else None
    elif field == "pressure_hpa":
        value = number if unit in ("hpa", "mb", "mbar") else inhg_to_hpa(number) if unit == "inhg" else None
    elif field in ("wind_speed_kmh", "wind_gust_kmh"):
        if unit in ("km/h", "kmh", "kph"):
            value = number
        elif unit == "mph":
            value = mph_to_kmh(number)
        elif unit in ("knots", "knot", "kt", "kn"):
            value = knots_to_kmh(number)
        elif unit == "m/s":
            value = number * 3.6
        else:
            value = None
    elif field == "wind_direction_deg":
        value = number if unit in ("°", "deg", "degree", "degrees") else None
    elif field == "rain_1h_mm":
        value = number if unit == "mm" else inches_to_mm(number) if unit in ("in", "inch") else None
    else:
        # Ecowitt can label the rain_rate unit as mm, though its quantity is mm/h.
        value = number if unit in ("mm", "mm/h", "mm/hr") else inches_to_mm(number) if unit in ("in", "in/h", "in/hr", "inch/hr") else None
    return validate_measurement(field, value)


def normalize_ecowitt(payload, *, now=None, stale_minutes=DEFAULT_STALE_MINUTES):
    now = _now(now)
    if not isinstance(payload, dict) or payload.get("code") != 0 or not isinstance(payload.get("data"), dict):
        return unavailable_station("pescadores", "invalid_response")
    data = payload["data"]
    if not data:
        return unavailable_station("pescadores")
    station = _empty_station("pescadores")
    paths = {
        "temperature_c": ("outdoor", "temperature"),
        "humidity_pct": ("outdoor", "humidity"),
        "pressure_hpa": ("pressure", "relative"),
        "wind_speed_kmh": ("wind", "wind_speed"),
        "wind_gust_kmh": ("wind", "wind_gust"),
        "wind_direction_deg": ("wind", "wind_direction"),
        "rain_1h_mm": ("rainfall", "hourly"),
        "rain_rate_mmh": ("rainfall", "rain_rate"),
    }
    timestamps = []
    for field, (group, name) in paths.items():
        block = data.get(group)
        node = block.get(name) if isinstance(block, dict) else None
        value = _ecowitt_value(field, node)
        timestamp = _valid_timestamp(node.get("time"), now) if isinstance(node, dict) else None
        if group == "rainfall" and (value is None or timestamp is None):
            block = data.get("rainfall_piezo")
            node = block.get(name) if isinstance(block, dict) else None
            value = _ecowitt_value(field, node)
            timestamp = _valid_timestamp(node.get("time"), now) if isinstance(node, dict) else None
        # An undated sensor value cannot be described as a current observation.
        if value is not None and timestamp is not None:
            station[field] = value
            station["field_timestamps"][field] = timestamp.isoformat()
            timestamps.append(timestamp)
    if timestamps:
        # Never relabel the older measurements with the newest sensor's time.
        station["timestamp"] = min(timestamps).isoformat()
    return _finish_station(station, now=now, stale_minutes=stale_minutes)


def normalize_wunderground(payload, *, now=None, stale_minutes=DEFAULT_STALE_MINUTES):
    now = _now(now)
    observations = payload.get("observations") if isinstance(payload, dict) else None
    if not isinstance(observations, list):
        return unavailable_station("yacht", "invalid_response")
    if not observations:
        return unavailable_station("yacht")
    observation = next((item for item in observations if isinstance(item, dict) and item.get("stationID") == "IPAYSA15"), None)
    if observation is None:
        return unavailable_station("yacht", "invalid_response")
    epoch = _valid_timestamp(observation.get("epoch"), now)
    utc = _valid_timestamp(observation.get("obsTimeUtc"), now)
    if epoch is not None and utc is not None and abs((epoch - utc).total_seconds()) > 60:
        return unavailable_station("yacht", "invalid_timestamp")
    # A supplied but corrupt time cannot be hidden by the other timestamp.
    if (observation.get("epoch") is not None and epoch is None) or (observation.get("obsTimeUtc") is not None and utc is None):
        return unavailable_station("yacht", "invalid_timestamp")
    timestamp = utc or epoch
    if timestamp is None:
        return unavailable_station("yacht", "invalid_timestamp")
    metrics = observation.get("metric")
    if not isinstance(metrics, dict):
        return unavailable_station("yacht", "invalid_response")
    station = _empty_station("yacht")
    station["timestamp"] = timestamp.isoformat()
    values = {
        "temperature_c": metrics.get("temp"),
        "humidity_pct": observation.get("humidity"),
        "pressure_hpa": metrics.get("pressure"),
        "wind_speed_kmh": metrics.get("windSpeed"),
        "wind_gust_kmh": metrics.get("windGust"),
        "wind_direction_deg": observation.get("winddir"),
        "rain_rate_mmh": metrics.get("precipRate"),
        # precipTotal is a daily accumulation, not precipitation in the last hour.
        "rain_1h_mm": None,
    }
    for field, value in values.items():
        station[field] = validate_measurement(field, value)
        if station[field] is not None:
            station["field_timestamps"][field] = timestamp.isoformat()
    return _finish_station(station, now=now, stale_minutes=stale_minutes)
