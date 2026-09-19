"""Pure weather logic: synthetic provider responses, no database or Internet."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone

from django.test import SimpleTestCase

from .aggregation import consolidate_weather, consolidate_wind_speed
from .normalization import (
    normalize_ecowitt,
    normalize_wunderground,
    refresh_station_age,
    unavailable_station,
)
from .utils import (
    degrees_to_cardinal,
    fahrenheit_to_celsius,
    finite_number,
    inches_to_mm,
    inhg_to_hpa,
    knots_to_kmh,
    mph_to_kmh,
    parse_timestamp,
    vector_mean_direction,
)


NOW = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)


def ecowitt_payload(age=4):
    timestamp = str(int((NOW - timedelta(minutes=age)).timestamp()))

    def reading(value, unit):
        return {"time": timestamp, "unit": unit, "value": str(value)}

    return {
        "code": 0,
        "msg": "success",
        "time": str(int(NOW.timestamp())),
        "data": {
            "outdoor": {"temperature": reading(20, "℃"), "humidity": reading(70, "%")},
            "wind": {
                "wind_speed": reading(10, "km/h"),
                "wind_gust": reading(24, "km/h"),
                "wind_direction": reading(350, "º"),
            },
            "pressure": {"relative": reading(1010, "hPa"), "absolute": reading(1000, "hPa")},
            "rainfall": {"hourly": reading(0, "mm"), "rain_rate": reading(0, "mm/h")},
        },
    }


def wunderground_payload(age=3):
    timestamp = NOW - timedelta(minutes=age)
    return {"observations": [{
        "stationID": "IPAYSA15",
        "epoch": int(timestamp.timestamp()),
        "obsTimeUtc": timestamp.isoformat().replace("+00:00", "Z"),
        "humidity": 80,
        "winddir": 10,
        "metric": {"temp": 22, "windSpeed": 20, "windGust": 32, "pressure": 1014, "precipRate": 0, "precipTotal": 12},
    }]}


class WeatherUnitsTests(SimpleTestCase):
    def test_mph_conversion(self):
        self.assertAlmostEqual(mph_to_kmh(10), 16.09344)

    def test_knots_conversion(self):
        self.assertAlmostEqual(knots_to_kmh(10), 18.52)

    def test_fahrenheit_conversion(self):
        self.assertEqual(fahrenheit_to_celsius(32), 0)
        self.assertEqual(fahrenheit_to_celsius(68), 20)
        self.assertEqual(fahrenheit_to_celsius(-40), -40)

    def test_pressure_conversion(self):
        self.assertAlmostEqual(inhg_to_hpa(29.92), 1013.2075, places=3)

    def test_rain_conversion(self):
        self.assertEqual(inches_to_mm(1), 25.4)

    def test_missing_and_invalid_numbers_do_not_become_zero(self):
        for value in (None, "", "--", True, False, float("inf"), float("nan"), {}, []):
            with self.subTest(value=value):
                self.assertIsNone(finite_number(value))
                self.assertIsNone(mph_to_kmh(value))
                self.assertIsNone(fahrenheit_to_celsius(value))
        self.assertEqual(finite_number("0"), 0)

    def test_all_cardinal_points_and_north_wrap(self):
        points = ("N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW")
        for index, point in enumerate(points):
            with self.subTest(point=point):
                self.assertEqual(degrees_to_cardinal(index * 22.5), point)
        self.assertEqual(degrees_to_cardinal(360), "N")
        self.assertEqual(degrees_to_cardinal(348.75), "N")
        for value in (None, -1, 361, "garbage"):
            self.assertIsNone(degrees_to_cardinal(value))

    def test_vector_mean_crosses_north(self):
        self.assertEqual(vector_mean_direction([350, 10]), 0)

    def test_vector_mean_opposing_or_nearly_opposing_is_ambiguous(self):
        self.assertIsNone(vector_mean_direction([0, 180]))
        self.assertIsNone(vector_mean_direction([0, 175]))
        self.assertIsNone(vector_mean_direction([None, float("nan")]))
        self.assertEqual(vector_mean_direction([90, 180]), 135)

    def test_timestamp_requires_explicit_timezone_or_unix_seconds(self):
        self.assertEqual(parse_timestamp(NOW.timestamp()), NOW)
        self.assertEqual(parse_timestamp("2026-09-15T09:00:00-03:00"), NOW)
        for value in (None, True, "2026-09-15T12:00:00", "yesterday", 1e100):
            self.assertIsNone(parse_timestamp(value))


class StationNormalizationTests(SimpleTestCase):
    def test_ecowitt_metric_measurements_and_sensor_timestamp(self):
        station = normalize_ecowitt(ecowitt_payload(), now=NOW)
        self.assertTrue(station["available"])
        self.assertFalse(station["stale"])
        self.assertEqual(station["id"], "pescadores")
        self.assertEqual(station["temperature_c"], 20)
        self.assertEqual(station["humidity_pct"], 70)
        self.assertEqual(station["pressure_hpa"], 1010)
        self.assertEqual(station["wind_speed_kmh"], 10)
        self.assertEqual(station["wind_gust_kmh"], 24)
        self.assertEqual(station["wind_direction_cardinal"], "N")
        self.assertEqual(station["rain_1h_mm"], 0)
        self.assertEqual(station["rain_rate_mmh"], 0)
        self.assertFalse(station["rain_detected"])
        self.assertEqual(station["age_minutes"], 4)
        self.assertEqual(parse_timestamp(station["timestamp"]), NOW - timedelta(minutes=4))

    def test_ecowitt_converts_documented_imperial_units(self):
        payload = ecowitt_payload()
        changes = (
            ("outdoor", "temperature", "ºF", "68"),
            ("wind", "wind_speed", "mph", "10"),
            ("wind", "wind_gust", "knots", "20"),
            ("pressure", "relative", "inHg", "29.92"),
            ("rainfall", "hourly", "in", "0.1"),
            ("rainfall", "rain_rate", "in/hr", "0.2"),
        )
        for group, field, unit, value in changes:
            payload["data"][group][field].update(unit=unit, value=value)
        station = normalize_ecowitt(payload, now=NOW)
        self.assertEqual(station["temperature_c"], 20)
        self.assertEqual(station["wind_speed_kmh"], 16.09)
        self.assertEqual(station["wind_gust_kmh"], 37.04)
        self.assertEqual(station["pressure_hpa"], 1013.21)
        self.assertEqual(station["rain_1h_mm"], 2.54)
        self.assertEqual(station["rain_rate_mmh"], 5.08)
        self.assertTrue(station["rain_detected"])

    def test_ecowitt_missing_or_unknown_unit_stays_null(self):
        payload = ecowitt_payload()
        del payload["data"]["outdoor"]["temperature"]["unit"]
        payload["data"]["wind"]["wind_speed"]["unit"] = "surprise"
        station = normalize_ecowitt(payload, now=NOW)
        self.assertIsNone(station["temperature_c"])
        self.assertIsNone(station["wind_speed_kmh"])
        self.assertTrue(station["available"])

    def test_ecowitt_does_not_substitute_absolute_pressure(self):
        payload = ecowitt_payload()
        del payload["data"]["pressure"]["relative"]
        self.assertIsNone(normalize_ecowitt(payload, now=NOW)["pressure_hpa"])

    def test_ecowitt_piezo_rain_fallback(self):
        payload = ecowitt_payload()
        payload["data"]["rainfall_piezo"] = payload["data"].pop("rainfall")
        payload["data"]["rainfall_piezo"]["hourly"]["value"] = "1.8"
        self.assertEqual(normalize_ecowitt(payload, now=NOW)["rain_1h_mm"], 1.8)

    def test_ecowitt_missing_field_is_null(self):
        payload = ecowitt_payload()
        del payload["data"]["rainfall"]
        station = normalize_ecowitt(payload, now=NOW)
        self.assertIsNone(station["rain_1h_mm"])
        self.assertIsNone(station["rain_rate_mmh"])
        self.assertIsNone(station["rain_detected"])

    def test_ecowitt_uses_oldest_actual_sensor_time_and_preserves_each_time(self):
        payload = ecowitt_payload()
        payload["data"]["wind"]["wind_speed"]["time"] = str(int((NOW - timedelta(minutes=37)).timestamp()))
        station = normalize_ecowitt(payload, now=NOW)
        self.assertTrue(station["stale"])
        self.assertEqual(station["age_minutes"], 37)
        self.assertEqual(parse_timestamp(station["field_timestamps"]["temperature_c"]), NOW - timedelta(minutes=4))
        self.assertEqual(parse_timestamp(station["field_timestamps"]["wind_speed_kmh"]), NOW - timedelta(minutes=37))

    def test_ecowitt_request_time_cannot_replace_missing_observation_time(self):
        payload = ecowitt_payload()
        for block in payload["data"].values():
            for node in block.values():
                node.pop("time")
        station = normalize_ecowitt(payload, now=NOW)
        self.assertFalse(station["available"])
        self.assertIsNone(station["timestamp"])
        self.assertIsNone(station["temperature_c"])

    def test_ecowitt_bad_values_are_not_exposed_or_averaged(self):
        payload = ecowitt_payload()
        payload["data"]["outdoor"]["temperature"]["value"] = "NaN"
        payload["data"]["outdoor"]["humidity"]["value"] = 105
        payload["data"]["wind"]["wind_speed"]["value"] = -10
        payload["data"]["rainfall"]["hourly"]["value"] = True
        station = normalize_ecowitt(payload, now=NOW)
        for field in ("temperature_c", "humidity_pct", "wind_speed_kmh", "rain_1h_mm"):
            self.assertIsNone(station[field])

    def test_wunderground_metric_and_rate_are_independent_of_daily_rain(self):
        payload = wunderground_payload()
        payload["observations"][0]["metric"]["precipRate"] = 1.4
        station = normalize_wunderground(payload, now=NOW)
        self.assertTrue(station["available"])
        self.assertEqual(station["temperature_c"], 22)
        self.assertEqual(station["humidity_pct"], 80)
        self.assertEqual(station["wind_speed_kmh"], 20)
        self.assertEqual(station["pressure_hpa"], 1014)
        self.assertEqual(station["wind_direction_deg"], 10)
        self.assertEqual(station["rain_rate_mmh"], 1.4)
        self.assertIsNone(station["rain_1h_mm"])
        self.assertTrue(station["rain_detected"])
        self.assertEqual(station["age_minutes"], 3)

    def test_wunderground_missing_numeric_fields_stay_null(self):
        payload = wunderground_payload()
        payload["observations"][0]["metric"] = {"windSpeed": 0}
        station = normalize_wunderground(payload, now=NOW)
        self.assertEqual(station["wind_speed_kmh"], 0)
        self.assertIsNone(station["temperature_c"])
        self.assertIsNone(station["wind_gust_kmh"])
        self.assertIsNone(station["rain_detected"])

    def test_wunderground_rejects_wrong_or_missing_station_id(self):
        for station_id in ("OTHER123", None):
            payload = wunderground_payload()
            payload["observations"][0]["stationID"] = station_id
            self.assertFalse(normalize_wunderground(payload, now=NOW)["available"])

    def test_wunderground_accepts_either_documented_timestamp(self):
        for field in ("epoch", "obsTimeUtc"):
            payload = wunderground_payload()
            del payload["observations"][0][field]
            self.assertEqual(normalize_wunderground(payload, now=NOW)["age_minutes"], 3)

    def test_wunderground_rejects_inconsistent_or_malformed_time(self):
        for value in ("not a date", "2026-09-14T00:00:00Z", "2026-09-15T12:20:00Z"):
            payload = wunderground_payload()
            payload["observations"][0]["obsTimeUtc"] = value
            station = normalize_wunderground(payload, now=NOW)
            self.assertFalse(station["available"])
            self.assertEqual(station["error"], "invalid_timestamp")

    def test_offline_and_invalid_payloads_never_raise(self):
        cases = (
            (normalize_ecowitt, None),
            (normalize_ecowitt, []),
            (normalize_ecowitt, {"code": 0, "data": {}}),
            (normalize_ecowitt, {"code": 0, "data": {"wind": []}}),
            (normalize_ecowitt, {"code": -1, "msg": "private provider message"}),
            (normalize_wunderground, {"observations": []}),
            (normalize_wunderground, {"observations": [None]}),
            (normalize_wunderground, None),
        )
        for normalizer, payload in cases:
            with self.subTest(normalizer=normalizer.__name__, payload=payload):
                station = normalizer(payload, now=NOW)
                self.assertFalse(station["available"])
                self.assertIsNone(station["wind_speed_kmh"])
                self.assertNotIn("private", station["error"])

    def test_stale_boundary_and_configurable_threshold(self):
        self.assertFalse(normalize_ecowitt(ecowitt_payload(age=20), now=NOW)["stale"])
        self.assertTrue(normalize_ecowitt(ecowitt_payload(age=20.1), now=NOW)["stale"])
        self.assertFalse(normalize_ecowitt(ecowitt_payload(age=25), now=NOW, stale_minutes=30)["stale"])

    def test_age_updates_without_mutating_cached_reading(self):
        station = normalize_ecowitt(ecowitt_payload(), now=NOW)
        before = deepcopy(station)
        aged = refresh_station_age(station, now=NOW + timedelta(minutes=20))
        self.assertEqual(station, before)
        self.assertEqual(aged["timestamp"], before["timestamp"])
        self.assertEqual(aged["age_minutes"], 24)
        self.assertTrue(aged["stale"])

    def test_timestamps_in_future_do_not_appear_fresh(self):
        for normalizer, fixture in ((normalize_ecowitt, ecowitt_payload), (normalize_wunderground, wunderground_payload)):
            self.assertFalse(normalizer(fixture(age=-10), now=NOW)["available"])


class WeatherAggregationTests(SimpleTestCase):
    def setUp(self):
        self.pescadores = normalize_ecowitt(ecowitt_payload(), now=NOW)
        self.yacht = normalize_wunderground(wunderground_payload(), now=NOW)

    def test_two_fresh_stations_consolidate_each_variable(self):
        result = consolidate_weather([self.pescadores, self.yacht], now=NOW)
        current = result["current"]
        self.assertEqual(current["temperature_c"], 21)
        self.assertEqual(current["humidity_pct"], 75)
        self.assertEqual(current["pressure_hpa"], 1012)
        self.assertEqual(current["wind_speed_kmh"], 15)
        self.assertEqual(current["wind_gust_kmh"], 32)
        self.assertEqual(current["wind_direction_deg"], 0)
        self.assertEqual(current["wind_direction_cardinal"], "N")
        self.assertEqual(current["stations_available"], 2)
        self.assertEqual(current["station_ids"], ["pescadores", "yacht"])
        self.assertEqual(current["age_minutes"], 4)
        self.assertEqual(current["timestamp"], self.pescadores["timestamp"])
        self.assertTrue(current["available"])
        self.assertFalse(current["stale"])
        self.assertIsNone(current["fallback"])

    def test_wind_speed_policy_is_independent(self):
        self.assertEqual(consolidate_wind_speed([10, 20]), 15)
        self.assertIsNone(consolidate_wind_speed([]))

    def test_one_station_failure_preserves_other_and_all_sources(self):
        offline = unavailable_station("yacht")
        result = consolidate_weather([self.pescadores, offline], now=NOW)
        self.assertEqual(result["current"]["stations_available"], 1)
        self.assertEqual(result["current"]["wind_speed_kmh"], 10)
        self.assertEqual(len(result["sources"]), 2)
        self.assertFalse(result["sources"][1]["available"])
        self.assertIsNone(result["comparison"]["temperature_difference_c"])

    def test_both_stations_failed_gives_null_observations(self):
        result = consolidate_weather([unavailable_station("pescadores"), unavailable_station("yacht")], now=NOW)
        self.assertFalse(result["current"]["available"])
        self.assertEqual(result["current"]["stations_available"], 0)
        for field in ("wind_speed_kmh", "temperature_c", "rain_1h_mm", "rain_detected", "timestamp"):
            self.assertIsNone(result["current"][field])
        self.assertFalse(result["comparison"]["significant"])

    def test_stale_station_excluded_when_other_is_fresh_even_for_missing_fields(self):
        old = normalize_ecowitt(ecowitt_payload(age=37), now=NOW)
        self.yacht["wind_gust_kmh"] = None
        result = consolidate_weather([old, self.yacht], now=NOW)
        self.assertEqual(result["current"]["stations_available"], 1)
        self.assertEqual(result["current"]["station_ids"], ["yacht"])
        self.assertEqual(result["current"]["temperature_c"], 22)
        self.assertIsNone(result["current"]["wind_gust_kmh"])
        self.assertIsNone(result["comparison"]["wind_difference_kmh"])
        self.assertTrue(result["sources"][0]["stale"])

    def test_only_stale_station_is_explicit_fallback(self):
        old = normalize_ecowitt(ecowitt_payload(age=37), now=NOW)
        current = consolidate_weather([old, unavailable_station("yacht")], now=NOW)["current"]
        self.assertTrue(current["available"])
        self.assertTrue(current["stale"])
        self.assertEqual(current["fallback"], "stale_observations")
        self.assertEqual(current["age_minutes"], 37)
        self.assertEqual(current["wind_speed_kmh"], 10)

    def test_cached_station_age_is_rechecked_before_selection(self):
        result = consolidate_weather([self.pescadores, self.yacht], now=NOW + timedelta(minutes=21))
        self.assertTrue(result["current"]["stale"])
        self.assertEqual(result["current"]["age_minutes"], 25)
        self.assertEqual(result["current"]["fallback"], "stale_observations")

    def test_last_known_and_refreshing_are_exposed_before_stale_threshold(self):
        self.pescadores.update(last_known=True, refreshing=True, error="provider_timeout")
        current = consolidate_weather([self.pescadores, self.yacht], now=NOW)["current"]
        self.assertTrue(current["last_known"])
        self.assertTrue(current["refreshing"])
        self.assertFalse(current["stale"])
        self.assertEqual(current["timestamp"], self.pescadores["timestamp"])

    def test_unknown_values_are_not_zero_in_average(self):
        self.yacht["temperature_c"] = None
        self.yacht["pressure_hpa"] = None
        current = consolidate_weather([self.pescadores, self.yacht], now=NOW)["current"]
        self.assertEqual(current["temperature_c"], 20)
        self.assertEqual(current["pressure_hpa"], 1010)

    def test_near_opposing_winds_have_no_consolidated_direction(self):
        self.pescadores["wind_direction_deg"] = 0
        self.yacht["wind_direction_deg"] = 175
        current = consolidate_weather([self.pescadores, self.yacht], now=NOW)["current"]
        self.assertIsNone(current["wind_direction_deg"])
        self.assertIsNone(current["wind_direction_cardinal"])
        self.assertTrue(current["wind_direction_ambiguous"])

    def test_rain_maximum_and_rate_stay_separate(self):
        self.pescadores["rain_1h_mm"] = 2.5
        self.yacht["rain_rate_mmh"] = 5
        current = consolidate_weather([self.pescadores, self.yacht], now=NOW)["current"]
        self.assertEqual(current["rain_1h_mm"], 2.5)
        self.assertEqual(current["rain_rate_mmh"], 5)
        self.assertTrue(current["rain_detected"])

    def test_dry_condition_requires_known_rain_from_each_station(self):
        current = consolidate_weather([self.pescadores, self.yacht], now=NOW)["current"]
        self.assertFalse(current["rain_detected"])
        self.yacht["rain_rate_mmh"] = None
        self.assertIsNone(consolidate_weather([self.pescadores, self.yacht], now=NOW)["current"]["rain_detected"])
        self.pescadores["rain_1h_mm"] = 0.2
        self.assertTrue(consolidate_weather([self.pescadores, self.yacht], now=NOW)["current"]["rain_detected"])

    def test_comparison_has_differences_and_configurable_thresholds(self):
        result = consolidate_weather([self.pescadores, self.yacht], now=NOW)
        self.assertEqual(result["comparison"]["wind_difference_kmh"], 10)
        self.assertEqual(result["comparison"]["gust_difference_kmh"], 8)
        self.assertEqual(result["comparison"]["temperature_difference_c"], 2)
        self.assertEqual(result["comparison"]["pressure_difference_hpa"], 4)
        self.assertFalse(result["comparison"]["significant"])
        result = consolidate_weather([self.pescadores, self.yacht], now=NOW, difference_thresholds={"wind_difference_kmh": 5})
        self.assertTrue(result["comparison"]["significant"])
        self.assertEqual(result["comparison"]["differing_fields"], ["wind_difference_kmh"])
