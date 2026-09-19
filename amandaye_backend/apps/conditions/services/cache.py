"""Per-source caching and a short cache.add lease shared by Django workers."""
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from ..aggregation import consolidate_weather
from ..normalization import unavailable_station
from .forecast import fetch_forecast, present_forecast, unavailable_forecast
from .http import ProviderError
from .weather import fetch_ecowitt, fetch_wunderground

logger = logging.getLogger("amandaye.conditions")


def cached_source(key, loader, unavailable, ttl, *, provider, station="forecast"):
    key = "conditions:v1:" + key
    value = cache.get(key)
    if value is not None:
        return value
    previous = cache.get(key + ":last_success")
    config = settings.CONDITIONS
    # Let the lease expire naturally: an expired worker never deletes a new owner's lock.
    lease_seconds = int(config["external_timeout_seconds"] * 3 + 5)
    if not cache.add(key + ":lease", uuid.uuid4().hex, lease_seconds):
        if previous:
            return {**previous, "refreshing": True, "last_known": True}
        return {**unavailable("refresh_in_progress"), "refreshing": True}
    try:
        value = loader()
        if not value.get("available"):
            raise ProviderError(value.get("error") or "station_unavailable")
        cache.set(key + ":last_success", value, max(ttl, config["fallback_cache_seconds"]))
    except Exception as exc:
        code = exc.code if isinstance(exc, ProviderError) else "provider_error"
        status = exc.status if isinstance(exc, ProviderError) else None
        # Exception text and URL can contain API keys; record only classified values.
        logger.warning("provider_failed provider=%s station=%s error=%s http_status=%s", provider, station, code, status)
        value = {**previous, "last_known": True, "error": code} if previous else unavailable(code)
    cache.set(key, value, ttl)
    return value


def _station(station_id, provider, loader):
    return cached_source(
        station_id, loader, lambda error: unavailable_station(station_id, error),
        settings.CONDITIONS["observation_cache_seconds"], provider=provider, station=station_id,
    )


def _forecast():
    config = settings.CONDITIONS
    return cached_source(
        f"forecast:{config['latitude']}:{config['longitude']}", fetch_forecast, unavailable_forecast,
        config["forecast_cache_seconds"], provider="open_meteo",
    )


def get_conditions(*, include_forecast=True):
    jobs = [
        lambda: _station("pescadores", "ecowitt", fetch_ecowitt),
        lambda: _station("yacht", "wunderground", fetch_wunderground),
    ]
    if include_forecast:
        jobs.append(_forecast)
    # Independent providers run concurrently, so timeouts do not add sequentially.
    with ThreadPoolExecutor(max_workers=len(jobs)) as executor:
        results = list(executor.map(lambda job: job(), jobs))
    now = timezone.now()
    config = settings.CONDITIONS
    weather = consolidate_weather(
        results[:2], now=now, stale_minutes=config["stale_minutes"],
        difference_thresholds=config["difference_thresholds"],
    )
    meta = {
        "generated_at": now.isoformat(), "stale_after_minutes": config["stale_minutes"],
        "forecast_stale_after_seconds": config["forecast_cache_seconds"], "refresh_interval_seconds": 300,
    }
    if not include_forecast:
        return {"stations": weather["sources"], "meta": meta}
    return {"weather": weather, "forecast": present_forecast(results[2], now=now), "meta": meta}
