"""Offline service tests: all upstream requests use synthetic fixtures or mocks."""
import copy
import socket
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone as dt_timezone
from threading import Event
from unittest.mock import MagicMock, Mock, patch
from urllib.error import HTTPError, URLError
from urllib.request import Request

from django.conf import settings
from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from .normalization import normalize_ecowitt, normalize_wunderground, unavailable_station
from .services import cache as source_cache
from .services import forecast, http, weather


NOW = datetime(2026, 9, 15, 12, 30, tzinfo=dt_timezone.utc)
MIDNIGHT = datetime(2026, 9, 15, 3, tzinfo=dt_timezone.utc)
SECRET = "synthetic-do-not-log-provider-secret"


def ecowitt_payload(stamp=NOW):
    def node(value, unit):
        return {"value": str(value), "unit": unit, "time": str(int(stamp.timestamp()))}

    return {"code": 0, "data": {
        "outdoor": {"temperature": node(18, "°C"), "humidity": node(70, "%")},
        "wind": {"wind_speed": node(12, "km/h"), "wind_gust": node(20, "km/h"),
                 "wind_direction": node(350, "°")},
        "pressure": {"relative": node(1015, "hPa")},
        "rainfall": {"hourly": node(0, "mm"), "rain_rate": node(0, "mm/h")},
    }}


def wunderground_payload(stamp=NOW):
    return {"observations": [{
        "stationID": "IPAYSA15", "epoch": int(stamp.timestamp()),
        "obsTimeUtc": stamp.isoformat(), "humidity": 74, "winddir": 10,
        "metric": {"temp": 20, "windSpeed": 16, "windGust": 24,
                   "pressure": 1017, "precipRate": 0, "precipTotal": 6},
    }]}


def forecast_payload():
    """Two local calendar days; Unix instants retain their real UTC meaning."""
    return {
        "timezone": "America/Montevideo", "utc_offset_seconds": -10800,
        "hourly_units": {
            "time": "unixtime", "temperature_2m": "°C", "relative_humidity_2m": "%",
            "precipitation": "mm", "precipitation_probability": "%", "wind_speed_10m": "km/h",
            "wind_gusts_10m": "km/h", "wind_direction_10m": "°", "weather_code": "wmo code",
        },
        "daily_units": {
            "time": "unixtime", "temperature_2m_min": "°C", "temperature_2m_max": "°C",
            "wind_speed_10m_max": "km/h", "wind_gusts_10m_max": "km/h",
            "precipitation_probability_max": "%", "precipitation_sum": "mm", "weather_code": "wmo code",
        },
        "hourly": {
            "time": [int((MIDNIGHT + timedelta(hours=i)).timestamp()) for i in range(48)],
            "temperature_2m": [18] * 48,
            "relative_humidity_2m": [70] * 48,
            "precipitation": [0] * 48,
            "precipitation_probability": [20] * 48,
            "wind_speed_10m": [10 + i % 24 for i in range(48)],
            "wind_gusts_10m": [40] * 48,
            "wind_direction_10m": [90] * 48,
            "weather_code": [2] * 48,
        },
        "daily": {
            "time": [int(MIDNIGHT.timestamp()), int((MIDNIGHT + timedelta(days=1)).timestamp())],
            "temperature_2m_min": [10, 12], "temperature_2m_max": [24, 26],
            "wind_speed_10m_max": [33, 33], "wind_gusts_10m_max": [40, 40],
            "precipitation_probability_max": [20, 30], "precipitation_sum": [0, 2],
            "weather_code": [2, 3],
        },
    }


class ConditionsServiceCase(SimpleTestCase):
    def setUp(self):
        super().setUp()
        self.config = copy.deepcopy(settings.CONDITIONS)
        self.config.update(ecowitt_application_key="", ecowitt_api_key="", ecowitt_mac="",
                           wunderground_api_key="", external_timeout_seconds=5,
                           observation_cache_seconds=300, forecast_cache_seconds=900,
                           fallback_cache_seconds=3600, stale_minutes=20)
        self.overrides = override_settings(CONDITIONS=self.config, CACHES={
            "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                        "LOCATION": "conditions-services-tests"},
        })
        self.overrides.enable()
        self.addCleanup(self.overrides.disable)
        cache.clear()
        self.addCleanup(cache.clear)

    @contextmanager
    def providers(self, *, ecowitt_error=None, wunderground_error=None):
        with patch.object(source_cache, "fetch_ecowitt", return_value=normalize_ecowitt(
            ecowitt_payload(), now=NOW), side_effect=ecowitt_error) as ecowitt, patch.object(
                source_cache, "fetch_wunderground", return_value=normalize_wunderground(
                    wunderground_payload(), now=NOW), side_effect=wunderground_error) as wunderground, patch.object(
                        source_cache, "fetch_forecast", return_value=forecast.normalize_forecast(
                            forecast_payload(), now=NOW)) as prediction:
            yield ecowitt, wunderground, prediction


class WeatherAdapterTests(ConditionsServiceCase):
    def test_missing_credentials_never_open_upstream_connection(self):
        with patch.object(weather, "get_json") as request:
            for loader in (weather.fetch_ecowitt, weather.fetch_wunderground):
                with self.subTest(loader=loader.__name__), self.assertRaises(http.ProviderError) as raised:
                    loader()
                self.assertEqual(raised.exception.code, "not_configured")
            request.assert_not_called()

    def test_ecowitt_uses_official_endpoint_real_config_and_metric_parameters(self):
        self.config.update(ecowitt_application_key="synthetic-app", ecowitt_api_key=SECRET,
                           ecowitt_mac="AA:BB:CC:DD:EE:FF")
        with patch.object(weather, "get_json", return_value=ecowitt_payload()) as request:
            result = weather.fetch_ecowitt()
        url, params, timeout = request.call_args.args
        self.assertEqual(url, "https://api.ecowitt.net/api/v3/device/real_time")
        self.assertEqual(params["application_key"], "synthetic-app")
        self.assertEqual(params["api_key"], SECRET)
        self.assertEqual(params["mac"], "AA:BB:CC:DD:EE:FF")
        self.assertEqual({name: params[name] for name in (
            "temp_unitid", "pressure_unitid", "wind_speed_unitid", "rainfall_unitid")},
            {"temp_unitid": 1, "pressure_unitid": 3, "wind_speed_unitid": 7, "rainfall_unitid": 12})
        self.assertEqual(timeout, 5)
        self.assertEqual(result["temperature_c"], 18)
        self.assertEqual(result["wind_speed_kmh"], 12)
        self.assertNotIn(SECRET, repr(result))

    def test_wunderground_uses_station_id_and_does_not_invent_hourly_rain(self):
        self.config["wunderground_api_key"] = SECRET
        with patch.object(weather, "get_json", return_value=wunderground_payload()) as request:
            result = weather.fetch_wunderground()
        request.assert_called_once_with("https://api.weather.com/v2/pws/observations/current", {
            "stationId": "IPAYSA15", "format": "json", "units": "m",
            "numericPrecision": "decimal", "apiKey": SECRET,
        }, 5)
        self.assertEqual(result["temperature_c"], 20)
        self.assertEqual(result["wind_gust_kmh"], 24)
        self.assertEqual(result["rain_rate_mmh"], 0)
        self.assertIsNone(result["rain_1h_mm"])
        self.assertNotIn(SECRET, repr(result))


class HttpTransportTests(SimpleTestCase):
    URL = "https://api.weather.com/v2/pws/observations/current"

    def response(self, body):
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = body
        opener = MagicMock()
        opener.open.return_value = response
        return opener, response

    def test_encodes_query_sets_json_header_and_honors_timeout(self):
        opener, _ = self.response(b'{"observations": []}')
        with patch.object(http, "build_opener", return_value=opener) as builder:
            result = http.get_json(self.URL, {"apiKey": "synthetic space+key"}, 3)
        self.assertEqual(result, {"observations": []})
        self.assertIsInstance(builder.call_args.args[0], http.NoRedirect)
        request = opener.open.call_args.args[0]
        self.assertIn("apiKey=synthetic+space%2Bkey", request.full_url)
        self.assertEqual(request.get_header("Accept"), "application/json")
        self.assertEqual(opener.open.call_args.kwargs["timeout"], 3)

    def test_upstream_network_failures_are_classified_without_secret_text(self):
        failures = [
            (HTTPError(self.URL + "?apiKey=" + SECRET, 401, SECRET, {}, None), "http_error", 401),
            (HTTPError(self.URL + "?apiKey=" + SECRET, 503, SECRET, {}, None), "http_error", 503),
            (URLError(socket.gaierror(SECRET)), "connection_error", None),
            (URLError(socket.timeout(SECRET)), "timeout", None),
            (TimeoutError(SECRET), "timeout", None),
            (OSError(SECRET), "connection_error", None),
        ]
        for error, code, status in failures:
            with self.subTest(code=code, status=status), patch.object(http, "build_opener") as builder:
                builder.return_value.open.side_effect = error
                with self.assertRaises(http.ProviderError) as raised:
                    http.get_json(self.URL, {"apiKey": SECRET}, 5)
                self.assertEqual(raised.exception.code, code)
                self.assertEqual(raised.exception.status, status)
                self.assertNotIn(SECRET, str(raised.exception))

    def test_invalid_json_nonfinite_and_nonobjects_are_rejected(self):
        for body in (b"not-json", b"[]", b"null", b'{"value": NaN}',
                     b'{"value": Infinity}', b'{"value": -Infinity}', b"\xff"):
            with self.subTest(body=body):
                opener, _ = self.response(body)
                with patch.object(http, "build_opener", return_value=opener):
                    with self.assertRaises(http.ProviderError) as raised:
                        http.get_json(self.URL, {}, 5)
                self.assertEqual(raised.exception.code, "invalid_response")

    def test_response_size_is_bounded(self):
        opener, response = self.response(b"x" * 21)
        with patch.object(http, "MAX_RESPONSE_BYTES", 20), patch.object(http, "build_opener", return_value=opener):
            with self.assertRaises(http.ProviderError) as raised:
                http.get_json(self.URL, {}, 5)
        self.assertEqual(raised.exception.code, "invalid_response")
        response.read.assert_called_once_with(21)

    def test_redirects_cannot_forward_credentials_to_another_host(self):
        handler = http.NoRedirect()
        request = Request(self.URL + "?apiKey=" + SECRET)
        self.assertIsNone(handler.redirect_request(request, None, 302, "Found", {},
                                                  "https://different.invalid/collect"))
        with patch.object(http, "build_opener") as builder:
            builder.return_value.open.side_effect = HTTPError(self.URL, 302, "Found", {}, None)
            with self.assertRaises(http.ProviderError) as raised:
                http.get_json(self.URL, {"apiKey": SECRET}, 5)
        self.assertEqual(raised.exception.status, 302)


class ForecastServiceTests(ConditionsServiceCase):
    def test_unix_timestamp_conversion_and_local_daily_summary(self):
        raw = forecast.normalize_forecast(forecast_payload(), now=NOW)
        self.assertEqual(raw["hourly"][0]["timestamp"], "2026-09-15T00:00:00-03:00")
        self.assertEqual(raw["days"][0]["date"], "2026-09-15")
        self.assertEqual(raw["days"][1]["date"], "2026-09-16")
        result = forecast.present_forecast(raw, now=NOW)
        self.assertEqual(len(result["hourly"]), 12)
        self.assertEqual(result["hourly"][0]["timestamp"], "2026-09-15T10:00:00-03:00")
        self.assertEqual(result["daily"]["wind_speed_min_kmh"], 10)
        self.assertEqual(result["daily"]["temperature_min_c"], 10)
        self.assertEqual(result["daily"]["temperature_max_c"], 24)
        self.assertEqual(result["hourly"][0]["wind_direction_cardinal"], "E")
        self.assertNotIn("days", result)

    def test_midnight_cache_hit_selects_new_day_and_retains_fetch_timestamp(self):
        raw = forecast.normalize_forecast(forecast_payload(), now=NOW)
        tomorrow = MIDNIGHT + timedelta(days=1, minutes=1)
        result = forecast.present_forecast(raw, now=tomorrow)
        self.assertEqual(result["daily"]["date"], "2026-09-16")
        self.assertEqual(result["daily"]["temperature_min_c"], 12)
        self.assertEqual(result["fetched_at"], NOW.isoformat())
        self.assertTrue(result["stale"])
        self.assertTrue(result["hourly"][0]["timestamp"].startswith("2026-09-16T01:00"))
        self.assertEqual(raw["hourly"][0]["timestamp"], "2026-09-15T00:00:00-03:00")

    def test_missing_invalid_values_remain_null_without_losing_valid_prediction(self):
        payload = forecast_payload()
        payload["hourly"]["temperature_2m"][0] = True
        payload["hourly"]["precipitation"][0] = -1
        payload["hourly"]["wind_gusts_10m"][0] = float("nan")
        payload["hourly"].pop("relative_humidity_2m")
        payload["daily"]["temperature_2m_min"] = []
        result = forecast.normalize_forecast(payload, now=NOW)
        first = result["hourly"][0]
        for field in ("temperature_c", "precipitation_mm", "wind_gust_kmh", "humidity_pct"):
            self.assertIsNone(first[field])
        self.assertEqual(first["wind_speed_kmh"], 10)
        self.assertIsNone(result["days"][0]["temperature_min_c"])

    def test_malformed_or_empty_forecast_is_unavailable(self):
        for payload in ({}, {"hourly": [], "daily": {}},
                        {"hourly": {"time": []}, "daily": {"time": []}}):
            with self.subTest(payload=payload), self.assertRaises(http.ProviderError) as raised:
                forecast.normalize_forecast(payload, now=NOW)
            self.assertEqual(raised.exception.code, "invalid_response")
        expired = forecast.present_forecast(forecast.normalize_forecast(forecast_payload(), now=NOW),
                                            now=MIDNIGHT + timedelta(days=3))
        self.assertFalse(expired["available"])
        self.assertEqual(expired["hourly"], [])

    def test_undocumented_units_cannot_be_labeled_as_metric_predictions(self):
        wrong_units = [
            ("hourly_units", "temperature_2m", "°F"),
            ("hourly_units", "wind_speed_10m", "mp/h"),
            ("hourly_units", "time", "iso8601"),
            ("daily_units", "precipitation_sum", "inch"),
            ("daily_units", "time", None),
        ]
        for group, field, wrong in wrong_units:
            payload = forecast_payload()
            payload[group][field] = wrong
            with self.subTest(group=group, field=field), self.assertRaises(http.ProviderError) as raised:
                forecast.normalize_forecast(payload, now=NOW)
            self.assertEqual(raised.exception.code, "invalid_response")
        payload = forecast_payload()
        payload.pop("hourly_units")
        with self.assertRaises(http.ProviderError):
            forecast.normalize_forecast(payload, now=NOW)

    def test_request_uses_documented_hourly_fields_metric_units_and_unix_time(self):
        with patch.object(forecast, "get_json", return_value=forecast_payload()) as request, patch.object(
                forecast.timezone, "now", return_value=NOW):
            result = forecast.fetch_forecast()
        url, params, timeout = request.call_args.args
        self.assertEqual(url, "https://api.open-meteo.com/v1/forecast")
        self.assertEqual(set(params["hourly"].split(",")), {
            "temperature_2m", "relative_humidity_2m", "precipitation", "precipitation_probability",
            "wind_speed_10m", "wind_gusts_10m", "wind_direction_10m", "weather_code",
        })
        self.assertEqual(params["timeformat"], "unixtime")
        self.assertEqual(params["timezone"], "America/Montevideo")
        self.assertEqual(params["temperature_unit"], "celsius")
        self.assertEqual(params["wind_speed_unit"], "kmh")
        self.assertEqual(params["precipitation_unit"], "mm")
        self.assertEqual(params["forecast_days"], 2)
        self.assertEqual(timeout, 5)
        self.assertTrue(result["available"])
        self.assertEqual(result["fetched_at"], NOW.isoformat())


class ConditionsCacheAndApiTests(ConditionsServiceCase):
    def test_public_endpoints_share_observations_and_do_not_cache_response_age(self):
        with self.providers() as loaders, patch.object(source_cache.timezone, "now", return_value=NOW):
            full = self.client.get("/api/conditions/")
            stations = self.client.get("/api/conditions/stations/")
            repeated = self.client.get("/api/conditions/")
        self.assertEqual(full.status_code, 200)
        self.assertEqual(stations.status_code, 200)
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(full["Cache-Control"], "no-store")
        self.assertEqual(stations.json()["stations"], full.json()["weather"]["sources"])
        self.assertNotIn("forecast", stations.json())
        self.assertEqual(full.json()["weather"]["current"]["stations_available"], 2)
        self.assertTrue(full.json()["forecast"]["available"])
        for loader in loaders:
            loader.assert_called_once()

    def test_each_station_failure_is_isolated_from_other_station_and_forecast(self):
        for failed in ("ecowitt", "wunderground"):
            cache.clear()
            kwargs = {failed + "_error": http.ProviderError("timeout")}
            with self.subTest(failed=failed), self.providers(**kwargs), patch.object(
                    source_cache.timezone, "now", return_value=NOW), self.assertLogs("amandaye.conditions"):
                result = source_cache.get_conditions()
            self.assertEqual(result["weather"]["current"]["stations_available"], 1)
            self.assertTrue(result["forecast"]["available"])
            failed_source = next(source for source in result["weather"]["sources"]
                                 if source["provider"] == failed)
            self.assertFalse(failed_source["available"])
            self.assertEqual(failed_source["error"], "timeout")

    def test_both_stations_unavailable_still_returns_forecast_and_http_200(self):
        with self.providers(ecowitt_error=http.ProviderError("not_configured"),
                            wunderground_error=http.ProviderError("http_error", 503)), patch.object(
                source_cache.timezone, "now", return_value=NOW), self.assertLogs("amandaye.conditions"):
            response = self.client.get("/api/conditions/")
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertFalse(result["weather"]["current"]["available"])
        self.assertEqual(result["weather"]["current"]["stations_available"], 0)
        self.assertTrue(result["forecast"]["available"])

    def test_age_and_stale_recalculated_on_cached_observations(self):
        with self.providers() as loaders:
            with patch.object(source_cache.timezone, "now", return_value=NOW):
                fresh = source_cache.get_conditions(include_forecast=False)
            with patch.object(source_cache.timezone, "now", return_value=NOW + timedelta(minutes=21)):
                old = source_cache.get_conditions(include_forecast=False)
        self.assertEqual(fresh["stations"][0]["age_minutes"], 0)
        self.assertFalse(fresh["stations"][0]["stale"])
        self.assertEqual(old["stations"][0]["age_minutes"], 21)
        self.assertTrue(old["stations"][0]["stale"])
        self.assertEqual(old["stations"][0]["timestamp"], fresh["stations"][0]["timestamp"])
        loaders[0].assert_called_once()
        loaders[1].assert_called_once()
        loaders[2].assert_not_called()

    def test_expired_cache_loads_again_and_preserves_last_success_on_error(self):
        value = normalize_ecowitt(ecowitt_payload(), now=NOW)
        loader = Mock(side_effect=[value, http.ProviderError("timeout")])
        initial_clock = time.time()
        with patch("django.core.cache.backends.locmem.time.time", return_value=initial_clock):
            first = source_cache.cached_source("fallback-test", loader,
                lambda error: unavailable_station("pescadores", error), 300, provider="ecowitt")
        with patch("django.core.cache.backends.locmem.time.time", return_value=initial_clock + 301), self.assertLogs(
                "amandaye.conditions"):
            fallback = source_cache.cached_source("fallback-test", loader,
                lambda error: unavailable_station("pescadores", error), 300, provider="ecowitt")
        self.assertEqual(loader.call_count, 2)
        self.assertTrue(fallback["last_known"])
        self.assertEqual(fallback["error"], "timeout")
        self.assertEqual(fallback["timestamp"], first["timestamp"])
        self.assertEqual(fallback["field_timestamps"], first["field_timestamps"])
        self.assertNotIn("last_known", first)

    def test_cold_cache_concurrent_requests_do_not_duplicate_upstream_fetch(self):
        entered, release = Event(), Event()
        value = normalize_ecowitt(ecowitt_payload(), now=NOW)

        def blocking_loader():
            entered.set()
            if not release.wait(5):
                raise TimeoutError("test did not release loader")
            return value

        loader = Mock(side_effect=blocking_loader)

        def load():
            return source_cache.cached_source("concurrency-test", loader,
                lambda error: unavailable_station("pescadores", error), 300, provider="ecowitt")

        with ThreadPoolExecutor(max_workers=1) as executor:
            first = executor.submit(load)
            try:
                self.assertTrue(entered.wait(5), "first request did not enter loader")
                competing = load()
                self.assertFalse(competing["available"])
                self.assertEqual(competing["error"], "refresh_in_progress")
                self.assertTrue(competing["refreshing"])
                loader.assert_called_once()
            finally:
                release.set()
            self.assertTrue(first.result(timeout=5)["available"])
        self.assertTrue(load()["available"])
        loader.assert_called_once()

    def test_logging_and_response_exclude_raw_exception_secret(self):
        failures = [http.ProviderError("http_error", 403), RuntimeError("apiKey=" + SECRET)]
        for index, error in enumerate(failures):
            with self.subTest(error=type(error).__name__), self.assertLogs("amandaye.conditions") as logs:
                result = source_cache.cached_source("secret-test-" + str(index), Mock(side_effect=error),
                    lambda code: unavailable_station("yacht", code), 300,
                    provider="wunderground", station="yacht")
            self.assertNotIn(SECRET, " ".join(logs.output))
            self.assertNotIn(SECRET, repr(result))
            self.assertIn("provider=wunderground", logs.output[0])
            self.assertIn("station=yacht", logs.output[0])
            if index == 0:
                self.assertIn("http_status=403", logs.output[0])
            else:
                self.assertEqual(result["error"], "provider_error")
