"""Temporary adapters for the two public station dashboards.

Only the shared Ecowitt read endpoints and WU server-rendered observations
are consumed. No login, embedded API keys, browser runtime or history scraping.
"""
import json
import re
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit

from django.conf import settings

from ..normalization import STATIONS, normalize_ecowitt, normalize_wunderground, unavailable_station
from ..utils import fahrenheit_to_celsius, finite_number, inches_to_mm, inhg_to_hpa, mph_to_kmh, parse_timestamp
from .http import ProviderError, public_response

ECOWITT_DEVICES_URL = "https://www.ecowitt.net/index/get_device_list"
ECOWITT_CURRENT_URL = "https://www.ecowitt.net/index/home"
ECOWITT_SHARE = "PHC0G3"


def _public(station):
    return {**station, "access_method": "public_page"}


def _decimal(value):
    """The shared dashboard formats numbers using the owner's preferences."""
    if not isinstance(value, str):
        return finite_number(value)
    value = value.strip()
    if re.fullmatch(r"[+-]?\d{1,3}(?:\.\d{3})+,\d+", value):
        value = value.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"[+-]?\d{1,3}(?:,\d{3})+\.\d+", value):
        value = value.replace(",", "")
    elif re.fullmatch(r"[+-]?\d+,\d+", value):
        value = value.replace(",", ".")
    elif not re.fullmatch(r"[+-]?\d+(?:\.\d+)?", value):
        return None
    return finite_number(value)


def _sensor_time(value, reference, offset):
    """Resolve explicit dates; never treat an undated HH:MM as today's data."""
    if not isinstance(value, str):
        return None
    absolute = parse_timestamp(value)
    if absolute is not None:
        return absolute
    if reference is None or offset is None or not -50400 <= offset <= 50400:
        return None
    local_zone = timezone(timedelta(seconds=offset))
    match = re.fullmatch(r"(Today|Yesterday) (\d{2}):(\d{2})", value)
    try:
        if match:
            day = reference.astimezone(local_zone).date()
            if match[1] == "Yesterday":
                day -= timedelta(days=1)
            return datetime(day.year, day.month, day.day, int(match[2]), int(match[3]), tzinfo=local_zone)
        # Full dated readings remain usable when a station stops reporting.
        if re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}(?::\d{2})?", value):
            return datetime.fromisoformat(value).replace(tzinfo=local_zone)
    except ValueError:
        pass
    return None


def normalize_ecowitt_page(payload, *, reference, now=None, stale_minutes=20):
    if not isinstance(payload, dict) or str(payload.get("errcode")) != "0" or not isinstance(payload.get("data"), dict):
        return _public(unavailable_station("pescadores", "invalid_response"))
    offset = finite_number(payload.get("UTC_offset"))
    data = payload["data"]
    mapping = {
        ("outdoor", "temperature"): ("temp", "tempf"),
        ("outdoor", "humidity"): ("temp", "humidity"),
        ("pressure", "relative"): ("pressure", "baromrelin"),
        ("wind", "wind_speed"): ("wind", "windspeedmph"),
        ("wind", "wind_gust"): ("wind", "windgustmph"),
        ("wind", "wind_direction"): ("wind", "winddir"),
        ("rainfall", "hourly"): ("rain", "hourlyrainin"),
        ("rainfall", "rain_rate"): ("rain", "rainratein"),
        ("rainfall_piezo", "hourly"): ("rain_piezo", "hrain_piezo"),
        ("rainfall_piezo", "rain_rate"): ("rain_piezo", "rrain_piezo"),
    }
    normalized = {}
    for (group, field), (section, key) in mapping.items():
        block = data.get(section)
        values = block.get("data") if isinstance(block, dict) else None
        node = values.get(key) if isinstance(values, dict) else None
        if not isinstance(node, dict):
            continue
        stamp = _sensor_time(node.get("time"), reference, offset)
        if stamp is None:
            continue
        normalized.setdefault(group, {})[field] = {
            "value": _decimal(node.get("value")), "unit": node.get("unit"), "time": stamp.isoformat(),
        }
    station = normalize_ecowitt({"code": 0, "data": normalized}, now=now, stale_minutes=stale_minutes)
    # Public dashboard dates have minute precision; never replace them with fetch time.
    return _public({**station, "timestamp_precision": "minute"})


def fetch_ecowitt_page():
    config = settings.CONDITIONS
    devices, _ = public_response(ECOWITT_DEVICES_URL, config["external_timeout_seconds"],
                                 form={"authorize": ECOWITT_SHARE})
    if str(devices.get("errcode")) != "0" or not isinstance(devices.get("list"), list):
        raise ProviderError("invalid_response")
    candidates = [item for item in devices["list"] if isinstance(item, dict) and str(item.get("type")) == "1"]
    # Do not silently switch station if the owner changes the shared device list.
    if len(candidates) != 1:
        raise ProviderError("station_unavailable" if not candidates else "invalid_response")
    device_id = candidates[0].get("device_id")
    if not isinstance(device_id, str) or not device_id or len(device_id) > 256:
        raise ProviderError("invalid_response")
    data, reference = public_response(ECOWITT_CURRENT_URL, config["external_timeout_seconds"],
                                     form={"authorize": ECOWITT_SHARE, "device_id": device_id})
    return normalize_ecowitt_page(data, reference=reference, stale_minutes=config["stale_minutes"])


class _WuDashboard(HTMLParser):
    TAGS = {"pws-status", "temp-widget-view", "humidity-widget-view", "wind-widget-view",
            "rain-widget-view", "pressure-widget-view"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.nodes = {}
        self.invalid = False
        self.state_parts = []
        self.reading_state = False
        self.has_state = False

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if tag == "script" and data.get("id") == "app-root-state":
            if self.has_state or data.get("type") != "application/json":
                self.invalid = True
            self.has_state = True
            self.reading_state = True
        if tag not in self.TAGS:
            return
        if data.get("data-pws-id") != "IPAYSA15" or tag in self.nodes:
            self.invalid = True
        self.nodes[tag] = data

    def handle_endtag(self, tag):
        if tag == "script":
            self.reading_state = False

    def handle_data(self, text):
        if self.reading_state:
            self.state_parts.append(text)


def _wu_observation_metrics(body):
    """Use only the target station and the explicitly named unit group."""
    observations = body.get("observations") if isinstance(body, dict) else None
    if not isinstance(observations, list):
        return body
    normalized = []
    for observation in observations:
        if not isinstance(observation, dict) or observation.get("stationID") != "IPAYSA15":
            continue
        result = dict(observation)
        if not isinstance(result.get("metric"), dict):
            imperial, si = observation.get("imperial"), observation.get("metric_si")
            if isinstance(imperial, dict):
                result["metric"] = {
                    "temp": fahrenheit_to_celsius(imperial.get("temp")),
                    "windSpeed": mph_to_kmh(imperial.get("windSpeed")),
                    "windGust": mph_to_kmh(imperial.get("windGust")),
                    "pressure": inhg_to_hpa(imperial.get("pressure")),
                    "precipRate": inches_to_mm(imperial.get("precipRate")),
                }
            elif isinstance(si, dict):
                result["metric"] = dict(si)
                for field in ("windSpeed", "windGust"):
                    value = finite_number(si.get(field))
                    result["metric"][field] = value * 3.6 if value is not None else None
        normalized.append(result)
    return {"observations": normalized}


def _wu_transfer_state(parts, *, now, stale_minutes):
    """Read Angular's embedded HTTP cache; embedded URLs are never requested."""
    def invalid_constant(_):
        raise ValueError("non_finite_json")

    try:
        state = json.loads("".join(parts), parse_constant=invalid_constant)
    except (ValueError, RecursionError):
        return unavailable_station("yacht", "invalid_response")
    if not isinstance(state, dict):
        return unavailable_station("yacht", "invalid_response")
    entries = list(state.values())
    legacy = state.get("wu-next-state-key")
    if isinstance(legacy, dict):
        entries.extend(legacy.values())
    candidates = []
    offline = False
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        url = entry.get("u", entry.get("url"))
        if not isinstance(url, str):
            continue
        try:
            parsed = urlsplit(url)
            if parsed.scheme != "https" or parsed.netloc != "api.weather.com":
                continue
            if parse_qs(parsed.query).get("stationId") != ["IPAYSA15"]:
                continue
        except ValueError:
            continue
        body = entry.get("b", entry.get("value"))
        if parsed.path == "/v2/pwsidentity" and entry.get("s", 200) == 200:
            if isinstance(body, dict) and body.get("ID") == "IPAYSA15" and body.get("isRecent") is False:
                offline = True
        if parsed.path != "/v2/pws/observations/current":
            continue  # history, forecasts and airport observations are not current PWS data
        if entry.get("s", 200) == 204:
            offline = True
        elif entry.get("s", 200) == 200:
            candidates.append(normalize_wunderground(_wu_observation_metrics(body), now=now, stale_minutes=stale_minutes))
    valid = [item for item in candidates if item["available"]]
    if valid:
        return max(valid, key=lambda item: parse_timestamp(item["timestamp"]))
    if candidates:
        return candidates[0]
    return unavailable_station("yacht", "station_offline" if offline else "invalid_response")


def _wu_timestamp(value):
    stamp = parse_timestamp(value)
    if stamp is not None:
        return stamp
    if not isinstance(value, str):
        return None
    # The current SSR template interpolates a JS Date (Date.toString()), not ISO.
    match = re.fullmatch(
        r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun) ([A-Z][a-z]{2}) (\d{2}) (\d{4}) "
        r"(\d{2}):(\d{2}):(\d{2}) GMT([+-])(\d{2})(\d{2})(?: \([^\r\n()]*\))?", value)
    if not match:
        return None
    try:
        month = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec").index(match[1]) + 1
        hours, minutes = int(match[8]), int(match[9])
        if hours > 14 or minutes > 59 or (hours == 14 and minutes):
            return None
        offset = timedelta(hours=hours, minutes=minutes) * (-1 if match[7] == "-" else 1)
        return datetime(int(match[3]), month, int(match[2]), int(match[4]), int(match[5]), int(match[6]), tzinfo=timezone(offset))
    except ValueError:
        return None


def normalize_wunderground_page(html, *, now=None, stale_minutes=20):
    page = _WuDashboard()
    page.feed(html)
    status = page.nodes.get("pws-status")
    if page.invalid:
        return _public(unavailable_station("yacht", "invalid_response"))
    if status is None:
        return _public(_wu_transfer_state(page.state_parts, now=now, stale_minutes=stale_minutes))
    if status.get("data-status") == "offline":
        return _public(unavailable_station("yacht", "station_offline"))
    if status.get("data-status") != "connected":
        return _public(unavailable_station("yacht", "station_unavailable"))
    stamp = _wu_timestamp(status.get("data-obs-time-utc"))
    if stamp is None:
        return _public(unavailable_station("yacht", "invalid_timestamp"))

    def metric(tag, field, kind):
        node = page.nodes.get(tag, {})
        if node.get("data-status") != "connected":
            return None
        value = finite_number(node.get("data-" + field))
        unit = node.get("data-unit")
        if value is None or unit not in ("m", "e", "h", "s"):
            return None
        if kind == "temperature" and unit == "e":
            return fahrenheit_to_celsius(value)
        if kind == "wind" and unit in ("e", "h"):
            # WU's website hybrid uses mph, unlike the API's metric_si group.
            return mph_to_kmh(value)
        if kind == "wind" and unit == "s":
            return value * 3.6
        if kind == "pressure" and unit == "e":
            return inhg_to_hpa(value)
        if kind == "rain" and unit == "e":
            return inches_to_mm(value)
        return value

    observation = {
        "stationID": "IPAYSA15", "obsTimeUtc": stamp.isoformat(),
        "humidity": metric("humidity-widget-view", "humidity", "humidity"),
        "winddir": metric("wind-widget-view", "wind-dir", "direction"),
        "metric": {
            "temp": metric("temp-widget-view", "temp", "temperature"),
            "windSpeed": metric("wind-widget-view", "wind-speed", "wind"),
            "windGust": metric("wind-widget-view", "wind-gust", "wind"),
            "pressure": metric("pressure-widget-view", "pressure", "pressure"),
            "precipRate": metric("rain-widget-view", "precip-rate", "rain"),
        },
    }
    return _public(normalize_wunderground({"observations": [observation]}, now=now, stale_minutes=stale_minutes))


def fetch_wunderground_page():
    config = settings.CONDITIONS
    html, _ = public_response(STATIONS["yacht"]["source_url"], config["external_timeout_seconds"])
    return normalize_wunderground_page(html, stale_minutes=config["stale_minutes"])
