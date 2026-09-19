"""Small, provider-independent helpers for weather measurements."""

import math
from datetime import datetime, timezone


CARDINAL_DIRECTIONS = (
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
)


def finite_number(value):
    """Return a finite float, rejecting booleans and missing/provider sentinels."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _convert(value, multiplier, offset=0):
    number = finite_number(value)
    return None if number is None else number * multiplier + offset


def mph_to_kmh(value):
    return _convert(value, 1.609344)


def knots_to_kmh(value):
    return _convert(value, 1.852)


def fahrenheit_to_celsius(value):
    number = finite_number(value)
    return None if number is None else (number - 32) * 5 / 9


def inhg_to_hpa(value):
    return _convert(value, 33.8638866667)


def inches_to_mm(value):
    return _convert(value, 25.4)


def degrees_to_cardinal(value):
    degrees = finite_number(value)
    if degrees is None or not 0 <= degrees <= 360:
        return None
    return CARDINAL_DIRECTIONS[int((degrees % 360 + 11.25) // 22.5) % 16]


def vector_mean_direction(directions, ambiguity_threshold=0.1):
    """Mean unit vectors; a near-zero resultant has no meaningful direction.

    Directions describe where wind comes FROM. They are not weighted by speed.
    The default threshold makes opposing and almost opposing directions null.
    """
    values = [finite_number(value) for value in directions]
    values = [value for value in values if value is not None and 0 <= value <= 360]
    if not values:
        return None
    east = sum(math.sin(math.radians(value)) for value in values) / len(values)
    north = sum(math.cos(math.radians(value)) for value in values) / len(values)
    if math.hypot(east, north) <= ambiguity_threshold:
        return None
    return round(math.degrees(math.atan2(east, north)) % 360, 1) % 360


def parse_timestamp(value):
    """Accept Unix seconds or ISO 8601 with an explicit timezone, never local time."""
    if isinstance(value, datetime):
        return value if value.utcoffset() is not None else None
    if isinstance(value, bool) or value is None:
        return None
    number = finite_number(value)
    if number is not None:
        try:
            return datetime.fromtimestamp(number, tz=timezone.utc)
        except (ValueError, OverflowError, OSError):
            return None
    if not isinstance(value, str):
        return None
    try:
        timestamp = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    return timestamp if timestamp.utcoffset() is not None else None
