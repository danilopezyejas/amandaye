"""Synthetic fixtures mirror the public dashboard contracts inspected 2026-09-21."""
import json
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from .config import environment_settings
from .services import http, scraping, weather
from .services import cache as source_cache
from .test_services import ConditionsServiceCase, ecowitt_payload, wunderground_payload

NOW = datetime(2026, 9, 21, 14, 5, tzinfo=timezone.utc)


def ecowitt_page(time="Today 11:03"):
    def node(value, unit):
        return {"value": value, "unit": unit, "time": time}
    return {"errcode": "0", "UTC_offset": "-10800", "timespan": 120, "data": {
        "temp": {"data": {"tempf": node("16,8", "℃"), "humidity": node("46", "%"),
                          "max_daily_tempf": node("35,0", "℃")}},
        "wind": {"data": {"windspeedmph": node("24,5", "km/h"), "windgustmph": node("38,9", "km/h"),
                          "winddir": node("183", "º"), "max_daily_windgustmph": node("90,0", "km/h")}},
        "pressure": {"data": {"baromrelin": node("1.009,3", "hPa")}},
        "rain_piezo": {"data": {"hrain_piezo": node("0,0", "mm"), "rrain_piezo": node("0,2", "mm/hr"),
                                "drain_piezo": node("10,0", "mm")}},
    }}


def wu_page(*, unit="m", stamp="Mon Sep 21 2026 14:03:00 GMT+0000 (Coordinated Universal Time)",
            status="connected", station_id="IPAYSA15"):
    def widget(tag, **data):
        attrs = {"pws-id": station_id, "status": status, "unit": unit, **data}
        text = " ".join(f'data-{key.replace("_", "-")}="{value}"' for key, value in attrs.items())
        return f"<{tag} {text}></{tag}>"
    return (
        widget("pws-status", obs_time_utc=stamp)
        + widget("temp-widget-view", temp=20)
        + widget("humidity-widget-view", humidity=70)
        + widget("wind-widget-view", wind_speed=10, wind_gust=15, wind_dir=350)
        + widget("pressure-widget-view", pressure=1010)
        + widget("rain-widget-view", precip_rate=0.2, precip_total=12)
        + '<pws-history-table data-pws-id="IPAYSA15">Historical temperature 99</pws-history-table>'
    )


class PublicParsingTests(SimpleTestCase):
    def ecowitt(self, payload=None, *, reference=NOW, now=NOW):
        return scraping.normalize_ecowitt_page(payload if payload is not None else ecowitt_page(), reference=reference, now=now)

    def wu(self, html=None):
        return scraping.normalize_wunderground_page(wu_page() if html is None else html, now=NOW)

    def test_ecowitt_decimal_comma_units_and_sensor_dates(self):
        station = self.ecowitt()
        self.assertTrue(station["available"])
        self.assertFalse(station["stale"])
        self.assertEqual(station["age_minutes"], 2)
        self.assertEqual(station["temperature_c"], 16.8)
        self.assertEqual(station["pressure_hpa"], 1009.3)
        self.assertEqual(station["wind_speed_kmh"], 24.5)
        self.assertEqual(station["wind_gust_kmh"], 38.9)
        self.assertEqual(station["wind_direction_cardinal"], "S")
        self.assertEqual(station["rain_1h_mm"], 0)
        self.assertEqual(station["rain_rate_mmh"], 0.2)
        self.assertTrue(station["rain_detected"])
        self.assertEqual(station["timestamp_precision"], "minute")
        self.assertEqual(station["access_method"], "public_page")

    def test_ecowitt_timestamps_use_response_date_not_fetch_date(self):
        yesterday = NOW - timedelta(days=1)
        station = self.ecowitt(reference=yesterday)
        self.assertEqual(station["age_minutes"], 1442)
        self.assertTrue(station["stale"])
        midnight = datetime(2026, 9, 22, 3, 1, tzinfo=timezone.utc)
        station = self.ecowitt(ecowitt_page("Yesterday 23:58"), reference=midnight, now=midnight)
        self.assertEqual(station["age_minutes"], 3)

    def test_ecowitt_oldest_sensor_keeps_its_original_date(self):
        payload = ecowitt_page()
        payload["data"]["wind"]["data"]["windgustmph"]["time"] = "2026-09-20 11:03"
        station = self.ecowitt(payload)
        self.assertEqual(station["age_minutes"], 1442)
        self.assertTrue(station["stale"])
        self.assertNotEqual(station["field_timestamps"]["wind_gust_kmh"], station["field_timestamps"]["temperature_c"])

    def test_ecowitt_rejects_missing_ambiguous_or_future_dates(self):
        for value in ("", "11:03", "21/09 11:03", "Today 25:00", "Today 12:00"):
            with self.subTest(value=value):
                self.assertFalse(self.ecowitt(ecowitt_page(value))["available"])
        self.assertFalse(self.ecowitt(reference=None)["available"])
        payload = ecowitt_page()
        payload["UTC_offset"] = "invalid"
        self.assertFalse(self.ecowitt(payload)["available"])

    def test_ecowitt_bad_fields_do_not_hide_valid_sensors_or_invent_rain(self):
        payload = ecowitt_page()
        payload["data"]["temp"]["data"]["tempf"]["value"] = "NaN"
        payload["data"]["wind"]["data"]["windspeedmph"]["unit"] = "unknown"
        payload["data"]["rain_piezo"]["data"].pop("hrain_piezo")
        station = self.ecowitt(payload)
        self.assertTrue(station["available"])
        self.assertIsNone(station["temperature_c"])
        self.assertIsNone(station["wind_speed_kmh"])
        self.assertIsNone(station["rain_1h_mm"])
        self.assertEqual(station["rain_rate_mmh"], 0.2)

    def test_ecowitt_malformed_payloads_are_unavailable(self):
        for payload in ({}, [], {"errcode": "1", "data": {}}, {"errcode": "0", "data": []},
                        {"errcode": "0", "data": {"temp": {"data": []}}}):
            with self.subTest(payload=payload):
                self.assertFalse(self.ecowitt(payload)["available"])

    def test_ecowitt_alternative_number_formats_and_imperial_units(self):
        payload = ecowitt_page()
        payload["data"]["pressure"]["data"]["baromrelin"]["value"] = "1,009.3"
        payload["data"]["temp"]["data"]["tempf"].update(value="68.0", unit="℉")
        self.assertEqual(self.ecowitt(payload)["temperature_c"], 20)
        self.assertEqual(self.ecowitt(payload)["pressure_hpa"], 1009.3)

    def test_wu_metric_page_uses_explicit_js_date_without_reading_history(self):
        station = self.wu()
        self.assertTrue(station["available"])
        self.assertEqual(station["temperature_c"], 20)
        self.assertEqual(station["wind_gust_kmh"], 15)
        self.assertEqual(station["age_minutes"], 2)
        self.assertEqual(station["rain_rate_mmh"], 0.2)
        self.assertIsNone(station["rain_1h_mm"])
        self.assertEqual(station["access_method"], "public_page")

    def test_wu_imperial_hybrid_and_si_conversion(self):
        html = wu_page(unit="e").replace('data-temp="20"', 'data-temp="68"').replace('data-pressure="1010"', 'data-pressure="29.92"')
        station = self.wu(html)
        self.assertEqual(station["temperature_c"], 20)
        self.assertEqual(station["wind_speed_kmh"], 16.09)
        self.assertAlmostEqual(station["pressure_hpa"], 1013.21, places=2)
        self.assertEqual(station["rain_rate_mmh"], 5.08)
        hybrid = self.wu(wu_page(unit="h"))
        self.assertEqual(hybrid["temperature_c"], 20)
        self.assertEqual(hybrid["wind_speed_kmh"], 16.09)
        self.assertEqual(hybrid["rain_rate_mmh"], 0.2)
        self.assertEqual(self.wu(wu_page(unit="s"))["wind_speed_kmh"], 36)

    def test_wu_offline_and_disconnected_never_use_historical_or_placeholder_values(self):
        for status, error in (("offline", "station_offline"), ("disconnected", "station_unavailable")):
            station = self.wu(wu_page(status=status, stamp="undefined"))
            self.assertFalse(station["available"])
            self.assertEqual(station["error"], error)
            self.assertIsNone(station["temperature_c"])

    def test_wu_accepts_explicit_offsets_but_rejects_ambiguous_and_future_times(self):
        for stamp in ("2026-09-21T11:03:00-03:00", "Mon Sep 21 2026 11:03:00 GMT-0300 (Uruguay Standard Time)"):
            self.assertEqual(self.wu(wu_page(stamp=stamp))["age_minutes"], 2)
        for stamp in ("undefined", "2026-09-21 11:03", "Mon Sep 21 2026 11:03:00", "2026-09-22T14:03:00Z"):
            self.assertFalse(self.wu(wu_page(stamp=stamp))["available"])
        self.assertTrue(self.wu(wu_page(stamp="2026-09-20T14:03:00Z"))["stale"])

    def test_wu_rejects_wrong_station_duplicates_or_changed_layout(self):
        for html in (wu_page(station_id="OTHER"), wu_page() + wu_page(), "<html>Access denied</html>",
                     '<script>{"observations":[{"temp":99}]}</script>'):
            station = self.wu(html)
            self.assertFalse(station["available"])
            self.assertEqual(station["error"], "invalid_response")

    def test_wu_unknown_units_and_invalid_measurements_stay_null(self):
        self.assertFalse(self.wu(wu_page(unit="unexpected"))["available"])
        station = self.wu(wu_page().replace('data-temp="20"', 'data-temp="NaN"').replace('data-humidity="70"', 'data-humidity="999"'))
        self.assertTrue(station["available"])
        self.assertIsNone(station["temperature_c"])
        self.assertIsNone(station["humidity_pct"])

    def transfer_page(self, entries):
        return '<script id="app-root-state" type="application/json">' + json.dumps(entries) + '</script>'

    def test_wu_angular_current_embedded_cache_is_read_without_exposing_keys(self):
        url = "https://api.weather.com/v2/pws/observations/current?stationId=IPAYSA15&apiKey=synthetic-key"
        body = wunderground_payload(NOW - timedelta(minutes=2))
        for state in ({"123": {"u": url, "s": 200, "b": body}},
                      {"wu-next-state-key": {"hash": {"url": url, "value": body}}}):
            result = self.wu(self.transfer_page(state))
            self.assertTrue(result["available"])
            self.assertEqual(result["age_minutes"], 2)
            self.assertEqual(result["temperature_c"], 20)
            self.assertNotIn("synthetic-key", repr(result))
            self.assertIsNone(result["rain_1h_mm"])

    def test_wu_angular_offline_identity_never_uses_history(self):
        state = {
            "identity": {"u": "https://api.weather.com/v2/pwsidentity?stationId=IPAYSA15", "s": 200,
                         "b": {"ID": "IPAYSA15", "isRecent": False, "lastUpdateTime": NOW.isoformat()}},
            "history": {"u": "https://api.weather.com/v2/pws/observations/all/1day?stationId=IPAYSA15", "s": 200,
                        "b": wunderground_payload(NOW)},
        }
        result = self.wu(self.transfer_page(state))
        self.assertFalse(result["available"])
        self.assertEqual(result["error"], "station_offline")
        self.assertIsNone(result["timestamp"])
        state.pop("identity")
        self.assertFalse(self.wu(self.transfer_page(state))["available"])

    def test_wu_angular_ignores_unrelated_station_and_untrusted_endpoints(self):
        for url in ("https://api.weather.com/v2/pws/observations/current?stationId=OTHER",
                    "https://unrelated.invalid/v2/pws/observations/current?stationId=IPAYSA15",
                    "https://api.weather.com/v2/pws/observations/all/1day?stationId=IPAYSA15"):
            result = self.wu(self.transfer_page({"123": {"u": url, "s": 200, "b": wunderground_payload(NOW)}}))
            self.assertFalse(result["available"])

    def test_wu_angular_converts_explicit_imperial_and_si_groups(self):
        url = "https://api.weather.com/v2/pws/observations/current?stationId=IPAYSA15"
        body = wunderground_payload(NOW)
        observation = body["observations"][0]
        observation.pop("metric")
        observation["imperial"] = {"temp": 68, "windSpeed": 10, "windGust": 20, "pressure": 29.92, "precipRate": 0.1}
        result = self.wu(self.transfer_page({"123": {"u": url, "s": 200, "b": body}}))
        self.assertEqual(result["temperature_c"], 20)
        self.assertEqual(result["wind_speed_kmh"], 16.09)
        self.assertEqual(result["rain_rate_mmh"], 2.54)
        observation.pop("imperial")
        observation["metric_si"] = {"temp": 20, "windSpeed": 10}
        self.assertEqual(self.wu(self.transfer_page({"123": {"u": url, "s": 200, "b": body}}))["wind_speed_kmh"], 36)

    def test_wu_angular_rejects_malformed_or_duplicated_state(self):
        for html in (self.transfer_page({}) * 2,
                     '<script id="app-root-state" type="application/json">not json</script>',
                     '<script id="app-root-state" type="application/json">{"bad":NaN}</script>'):
            self.assertEqual(self.wu(html)["error"], "invalid_response")


class PublicAdapterTests(ConditionsServiceCase):
    def test_ecowitt_discovers_id_from_public_share_instead_of_hardcoding_it(self):
        devices = {"errcode": "0", "list": [{"type": "1", "device_id": "synthetic-device"}]}
        with patch.object(scraping, "public_response", side_effect=[(devices, NOW), (ecowitt_page(), NOW)]) as request:
            station = scraping.fetch_ecowitt_page()
        self.assertTrue(station["available"])
        self.assertEqual(request.call_args_list[0].kwargs["form"], {"authorize": "PHC0G3"})
        self.assertEqual(request.call_args_list[1].kwargs["form"], {"authorize": "PHC0G3", "device_id": "synthetic-device"})
        self.assertNotIn("synthetic-device", repr(station))

    def test_ecowitt_shared_link_revoked_or_ambiguous_devices_do_not_select_a_station(self):
        for devices in ({"errcode": "1"}, {"errcode": "0", "list": []},
                        {"errcode": "0", "list": [{"type": "1", "device_id": "a"}] * 2}):
            with patch.object(scraping, "public_response", return_value=(devices, NOW)) as request:
                with self.assertRaises(http.ProviderError):
                    scraping.fetch_ecowitt_page()
                request.assert_called_once()

    def test_auto_uses_public_pages_until_credentials_are_complete(self):
        self.config["station_mode"] = "auto"
        with patch.object(weather, "fetch_ecowitt_page", return_value={"available": True}) as eco, patch.object(
                weather, "fetch_wunderground_page", return_value={"available": True}) as wu, patch.object(weather, "get_json") as api:
            weather.fetch_ecowitt()
            weather.fetch_wunderground()
            eco.assert_called_once()
            wu.assert_called_once()
            api.assert_not_called()

    def test_auto_prefers_api_and_never_hides_api_failure_with_scraping(self):
        self.config.update(station_mode="auto", ecowitt_application_key="synthetic", ecowitt_api_key="synthetic",
                           ecowitt_mac="AA:BB:CC:DD:EE:FF", wunderground_api_key="synthetic")
        with patch.object(weather, "get_json", side_effect=[ecowitt_payload(), wunderground_payload()]), patch.object(
                weather, "fetch_ecowitt_page") as eco, patch.object(weather, "fetch_wunderground_page") as wu:
            self.assertEqual(weather.fetch_ecowitt()["access_method"], "api")
            self.assertEqual(weather.fetch_wunderground()["access_method"], "api")
            eco.assert_not_called()
            wu.assert_not_called()
        with patch.object(weather, "get_json", side_effect=http.ProviderError("http_error", 403)), patch.object(
                weather, "fetch_wunderground_page") as public:
            with self.assertRaises(http.ProviderError):
                weather.fetch_wunderground()
            public.assert_not_called()

    def test_explicit_modes_and_cache_do_not_mix_api_with_scraped_values(self):
        self.config.update(station_mode="public_page", wunderground_api_key="synthetic")
        with patch.object(weather, "fetch_wunderground_page", return_value={"available": True}) as public:
            weather.fetch_wunderground()
            public.assert_called_once()
        loader = MagicMock(return_value={"available": True, "access_method": "public_page"})
        source_cache._station("yacht", "wunderground", loader)
        self.config["station_mode"] = "api"
        loader.return_value = {"available": True, "access_method": "api"}
        self.assertEqual(source_cache._station("yacht", "wunderground", loader)["access_method"], "api")
        self.assertEqual(loader.call_count, 2)

    def test_wu_reads_only_public_page_without_query_keys(self):
        with patch.object(scraping, "public_response", return_value=(wu_page(status="offline"), NOW)) as request:
            station = scraping.fetch_wunderground_page()
        request.assert_called_once_with("https://www.wunderground.com/dashboard/pws/IPAYSA15", 5)
        self.assertEqual(station["error"], "station_offline")


class PublicTransportTests(SimpleTestCase):
    URL = scraping.ECOWITT_CURRENT_URL

    def response(self, body=b'{"errcode":"0"}', date="Mon, 21 Sep 2026 14:05:00 GMT"):
        opener = MagicMock()
        response = opener.open.return_value.__enter__.return_value
        response.read.return_value = body
        response.headers = {"Date": date}
        return opener, response

    def test_form_encoding_timeout_date_and_no_cookie_or_credentials(self):
        opener, response = self.response()
        with patch.object(http, "build_opener", return_value=opener):
            data, reference = http.public_response(self.URL, 5, form={"authorize": "public link", "device_id": "a+b"})
        request = opener.open.call_args.args[0]
        self.assertEqual(parse_qs(request.data.decode()), {"authorize": ["public link"], "device_id": ["a+b"]})
        self.assertEqual(request.get_method(), "POST")
        self.assertFalse(request.has_header("Cookie"))
        self.assertEqual(reference, NOW)
        self.assertEqual(opener.open.call_args.kwargs["timeout"], 5)

    def test_public_html_does_not_execute_inline_scripts(self):
        body = b'<script>throw new Error("never run")</script>'
        opener, _ = self.response(body)
        with patch.object(http, "build_opener", return_value=opener):
            result, _ = http.public_response(self.URL, 5)
        self.assertEqual(result, body.decode())
        self.assertEqual(opener.open.call_args.args[0].get_method(), "GET")

    def test_public_transport_bounds_and_invalid_json(self):
        for body in (b"[]", b"null", b"NaN", b"not JSON", b"\xff"):
            opener, _ = self.response(body)
            with patch.object(http, "build_opener", return_value=opener), self.assertRaises(http.ProviderError):
                http.public_response(self.URL, 5, form={})
        opener, _ = self.response(b"x" * 21)
        with patch.object(http, "MAX_PAGE_BYTES", 20), patch.object(http, "build_opener", return_value=opener), self.assertRaises(http.ProviderError):
            http.public_response(self.URL, 5)

    def test_redirect_http_errors_timeout_and_dns_are_classified(self):
        for failure, expected in ((HTTPError(self.URL, 302, "redirect", {}, None), "http_error"),
                                  (HTTPError(self.URL, 429, "limit", {}, None), "http_error"),
                                  (TimeoutError(), "timeout"), (URLError("dns"), "connection_error")):
            with patch.object(http, "build_opener") as builder:
                builder.return_value.open.side_effect = failure
                with self.assertRaises(http.ProviderError) as raised:
                    http.public_response(self.URL, 5)
                self.assertEqual(raised.exception.code, expected)
                self.assertIsInstance(builder.call_args.args[0], http.NoRedirect)

    def test_invalid_http_date_is_not_replaced_with_fetch_time(self):
        opener, _ = self.response(date="not a date")
        with patch.object(http, "build_opener", return_value=opener):
            _, reference = http.public_response(self.URL, 5, form={})
        self.assertIsNone(reference)

    def test_invalid_mode_fails_configuration(self):
        with patch.dict(os.environ, {"CONDITIONS_STATION_MODE": "typo"}), self.assertRaises(ImproperlyConfigured):
            environment_settings()
