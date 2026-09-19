"""Combine local observations, keeping forecast data outside this layer."""

from .normalization import DEFAULT_STALE_MINUTES, FIELD_NAMES, refresh_station_age
from .utils import degrees_to_cardinal, parse_timestamp, vector_mean_direction


DEFAULT_DIFFERENCE_THRESHOLDS = {
    "wind_difference_kmh": 10,
    "gust_difference_kmh": 15,
    "temperature_difference_c": 3,
    "pressure_difference_hpa": 5,
}
COMPARISON_FIELDS = {
    "wind_difference_kmh": "wind_speed_kmh",
    "gust_difference_kmh": "wind_gust_kmh",
    "temperature_difference_c": "temperature_c",
    "pressure_difference_hpa": "pressure_hpa",
}


def _values(stations, field):
    return [station[field] for station in stations if station.get(field) is not None]


def _average(values):
    return round(sum(values) / len(values), 2) if values else None


def _maximum(values):
    return max(values) if values else None


def consolidate_wind_speed(speeds):
    """Initial policy: arithmetic mean of valid speeds from selected stations."""
    return _average(speeds)


def _rain_detected(stations):
    """Positive rate OR last-hour accumulation indicates measured rain.

    False requires every used station to report a known zero rain quantity.
    Unknown stations do not turn absence of evidence into a dry condition.
    """
    observations = []
    for station in stations:
        values = _values([station], "rain_1h_mm") + _values([station], "rain_rate_mmh")
        observations.append(any(value > 0 for value in values) if values else None)
    if any(value is True for value in observations):
        return True
    if observations and all(value is False for value in observations):
        return False
    return None


def _compare(stations, thresholds):
    comparison = {name: None for name in COMPARISON_FIELDS}
    comparison.update(significant=False, differing_fields=[], station_ids=[station["id"] for station in stations])
    for name, field in COMPARISON_FIELDS.items():
        values = _values(stations, field)
        if len(values) < 2:
            continue
        difference = round(max(values) - min(values), 2)
        comparison[name] = difference
        if difference > thresholds[name]:
            comparison["differing_fields"].append(name)
    comparison["significant"] = bool(comparison["differing_fields"])
    return comparison


def consolidate_weather(stations, *, now=None, stale_minutes=DEFAULT_STALE_MINUTES, difference_thresholds=None):
    """Prefer fresh stations; use old observations only when none are fresh.

    Each field uses known values from the selected stations. Gust, last-hour
    rain and rain rate use maxima; their different dimensions stay separate.
    """
    sources = [refresh_station_age(station, now=now, stale_minutes=stale_minutes) for station in stations]
    available = [station for station in sources if station.get("available")]
    fresh = [station for station in available if not station["stale"]]
    selected = fresh or available
    thresholds = {**DEFAULT_DIFFERENCE_THRESHOLDS, **(difference_thresholds or {})}
    current = {
        **{field: None for field in FIELD_NAMES},
        "wind_direction_cardinal": None,
        "wind_direction_ambiguous": False,
        "rain_detected": None,
        "available": bool(selected),
        "stations_available": len(selected),
        "station_ids": [station["id"] for station in selected],
        "timestamp": None,
        "age_minutes": None,
        "stale": not bool(fresh),
        "fallback": "stale_observations" if selected and not fresh else None,
        "last_known": any(station.get("last_known", False) for station in selected),
        "refreshing": any(station.get("refreshing", False) for station in selected),
    }
    if selected:
        for field in ("temperature_c", "humidity_pct", "pressure_hpa"):
            current[field] = _average(_values(selected, field))
        current["wind_speed_kmh"] = consolidate_wind_speed(_values(selected, "wind_speed_kmh"))
        for field in ("wind_gust_kmh", "rain_1h_mm", "rain_rate_mmh"):
            current[field] = _maximum(_values(selected, field))
        directions = _values(selected, "wind_direction_deg")
        current["wind_direction_deg"] = vector_mean_direction(directions)
        current["wind_direction_ambiguous"] = len(directions) >= 2 and current["wind_direction_deg"] is None
        current["wind_direction_cardinal"] = degrees_to_cardinal(current["wind_direction_deg"])
        current["rain_detected"] = _rain_detected(selected)
        oldest = min(selected, key=lambda station: parse_timestamp(station["timestamp"]))
        current["timestamp"] = oldest["timestamp"]
        current["age_minutes"] = oldest["age_minutes"]
    return {"current": current, "sources": sources, "comparison": _compare(fresh, thresholds)}
