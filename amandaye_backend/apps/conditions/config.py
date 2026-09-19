"""Environment defaults in one place; override settings.CONDITIONS in tests."""
import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured


def environment_settings():
    def number(name, default, minimum=1, maximum=86400):
        try:
            value = float(os.environ.get(name, default))
            if not minimum <= value <= maximum:
                raise ValueError
            return value
        except ValueError:
            raise ImproperlyConfigured(f"Invalid {name}.") from None

    def credential(name):
        filename = os.environ.get(f"{name}_FILE")
        return (Path(filename).read_text(encoding="utf-8") if filename else os.environ.get(name, "")).strip()

    return {
        "ecowitt_application_key": credential("ECOWITT_APPLICATION_KEY"),
        "ecowitt_api_key": credential("ECOWITT_API_KEY"),
        "ecowitt_mac": os.environ.get("ECOWITT_MAC", "").strip(),
        "wunderground_api_key": credential("WUNDERGROUND_API_KEY"),
        "stale_minutes": number("CONDITIONS_STALE_MINUTES", 20, maximum=1440),
        "observation_cache_seconds": int(number("CONDITIONS_OBSERVATION_CACHE_SECONDS", 300)),
        "forecast_cache_seconds": int(number("CONDITIONS_FORECAST_CACHE_SECONDS", 900)),
        "fallback_cache_seconds": int(number("CONDITIONS_FALLBACK_CACHE_SECONDS", 3600)),
        "external_timeout_seconds": number("CONDITIONS_EXTERNAL_TIMEOUT_SECONDS", 5, maximum=15),
        "latitude": number("CONDITIONS_LATITUDE", -32.3027, -90, 90),
        "longitude": number("CONDITIONS_LONGITUDE", -58.0904, -180, 180),
        "difference_thresholds": {
            "wind_difference_kmh": number("CONDITIONS_WIND_DIFFERENCE_KMH", 10, 0, 500),
            "gust_difference_kmh": number("CONDITIONS_GUST_DIFFERENCE_KMH", 15, 0, 500),
            "temperature_difference_c": number("CONDITIONS_TEMPERATURE_DIFFERENCE_C", 3, 0, 100),
            "pressure_difference_hpa": number("CONDITIONS_PRESSURE_DIFFERENCE_HPA", 5, 0, 500),
        },
    }
