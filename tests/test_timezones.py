"""Timezone handling for forecast windows. Run: python -m unittest discover tests

No network: Open-Meteo responses are synthesized the way the real API builds them with
`timezone=auto` — consecutive UTC hours rendered as the location's naive local wall clock.
Night hours are selected by astronomical darkness at the real city coordinates; expected
windows were cross-checked against PyEphem (see test_astronomy.py).
"""
import unittest
from datetime import date, datetime, timedelta, timezone
from unittest import mock
from zoneinfo import ZoneInfo

import app

UTC = timezone.utc

AUSTIN = (30.2672, -97.7431)
TOKYO = (35.6762, 139.6503)
LONDON = (51.5072, -0.1276)


def fake_entry(tz_name: str | None, start: date, hours: int = 48, offset_seconds: int = 0,
               cloud: float = 10) -> dict:
    """An Open-Meteo hourly entry starting at local midnight of `start`."""
    tz = ZoneInfo(tz_name) if tz_name else timezone(timedelta(seconds=offset_seconds))
    t = datetime(start.year, start.month, start.day, tzinfo=tz).astimezone(UTC)
    times = []
    for _ in range(hours):
        times.append(t.astimezone(tz).strftime("%Y-%m-%dT%H:%M"))
        t += timedelta(hours=1)
    entry = {
        "utc_offset_seconds": int(datetime(start.year, start.month, start.day, 12, tzinfo=tz)
                                  .utcoffset().total_seconds()),
        "hourly": {
            "time": times,
            "cloud_cover": [cloud] * hours,
            "precipitation": [0.0] * hours,
            "wind_speed_10m": [5.0] * hours,
            "relative_humidity_2m": [60] * hours,
        },
    }
    if tz_name:
        entry["timezone"] = tz_name
    return entry


def window(entry: dict, now: datetime, coords: tuple[float, float]) -> dict | None:
    return app.next_night_window(entry, coords[0], coords[1], now=now)


class AustinTests(unittest.TestCase):
    def setUp(self):
        self.entry = fake_entry("America/Chicago", date(2026, 11, 9))

    def test_window_uses_central_time(self):
        # 14:30 CST; astronomical darkness 18:59 CST → 05:30 CST.
        night = window(self.entry, datetime(2026, 11, 9, 20, 30, tzinfo=UTC), AUSTIN)
        self.assertEqual(night["timezone"], "America/Chicago")
        first = night["night_forecast"][0]
        self.assertEqual(first["time"], "2026-11-09T19:00")
        self.assertEqual(first["time_iso"], "2026-11-09T19:00-06:00")
        self.assertEqual(first["tz_abbreviation"], "CST")

    def test_result_independent_of_callers_timezone(self):
        # The same instant expressed in Tokyo, London, or UTC must select the same window.
        instant = datetime(2026, 11, 9, 20, 30, tzinfo=UTC)
        expected = window(self.entry, instant, AUSTIN)
        for zone in ("Asia/Tokyo", "Europe/London", "Pacific/Kiritimati", "America/Los_Angeles"):
            with self.subTest(zone=zone):
                self.assertEqual(window(self.entry, instant.astimezone(ZoneInfo(zone)), AUSTIN), expected)

    def test_partially_elapsed_hour_is_skipped_like_before(self):
        # 22:30 CST → the 22:00 hour has mostly passed; window starts at 23:00 (unchanged behavior).
        night = window(self.entry, datetime(2026, 11, 10, 4, 30, tzinfo=UTC), AUSTIN)
        self.assertEqual(night["night_forecast"][0]["time"], "2026-11-09T23:00")
        # Seconds past the hour are ignored, so 22:00:30 still includes the 22:00 hour.
        night = window(self.entry, datetime(2026, 11, 10, 4, 0, 30, tzinfo=UTC), AUSTIN)
        self.assertEqual(night["night_forecast"][0]["time"], "2026-11-09T22:00")


class TokyoFromUnitedStatesTests(unittest.TestCase):
    def test_destination_already_on_next_calendar_day(self):
        # 10:00 CST on Nov 9 in Texas is 01:00 JST on Nov 10 in Tokyo — mid-darkness there
        # (dark until 04:44 JST).
        now = datetime(2026, 11, 9, 10, 0, tzinfo=ZoneInfo("America/Chicago"))
        entry = fake_entry("Asia/Tokyo", date(2026, 11, 10))
        night = window(entry, now, TOKYO)
        hours = night["night_forecast"]
        self.assertEqual(night["timezone"], "Asia/Tokyo")
        self.assertEqual(hours[0]["time"], "2026-11-10T01:00")
        self.assertEqual(hours[0]["time_iso"], "2026-11-10T01:00+09:00")
        self.assertEqual(hours[0]["tz_abbreviation"], "JST")
        self.assertEqual(hours[-1]["time"], "2026-11-10T04:00")

    def test_daytime_in_tokyo_waits_for_tokyo_darkness(self):
        # 18:00 CST Nov 9 = 09:00 JST Nov 10 (daylight) → darkness from 18:05 JST, so 19:00 first.
        now = datetime(2026, 11, 9, 18, 0, tzinfo=ZoneInfo("America/Chicago"))
        night = window(fake_entry("Asia/Tokyo", date(2026, 11, 10)), now, TOKYO)
        self.assertEqual(night["night_forecast"][0]["time"], "2026-11-10T19:00")


class LondonTests(unittest.TestCase):
    def test_standard_time_is_gmt(self):
        night = window(fake_entry("Europe/London", date(2026, 1, 15)), datetime(2026, 1, 15, 12, tzinfo=UTC), LONDON)
        first = night["night_forecast"][0]
        self.assertTrue(first["time_iso"].endswith("+00:00"))
        self.assertEqual(first["tz_abbreviation"], "GMT")

    def test_daylight_saving_time_is_bst(self):
        # Mid-July London never reaches -18°; use mid-September when it does, still on BST.
        night = window(fake_entry("Europe/London", date(2026, 9, 15)), datetime(2026, 9, 15, 12, tzinfo=UTC), LONDON)
        first = night["night_forecast"][0]
        self.assertTrue(first["time_iso"].endswith("+01:00"))
        self.assertEqual(first["tz_abbreviation"], "BST")

    def test_fall_back_night_has_two_distinct_one_oclock_hours(self):
        # Clocks go back 02:00 BST → 01:00 GMT on 2026-10-25; 01:00 occurs twice.
        # Darkness: 19:40 BST → 04:49 GMT.
        night = window(fake_entry("Europe/London", date(2026, 10, 24)), datetime(2026, 10, 24, 12, tzinfo=UTC), LONDON)
        hours = night["night_forecast"]
        ones = [h for h in hours if h["time"] == "2026-10-25T01:00"]
        self.assertEqual([h["time_iso"] for h in ones], ["2026-10-25T01:00+01:00", "2026-10-25T01:00+00:00"])
        self.assertEqual([h["tz_abbreviation"] for h in ones], ["BST", "GMT"])
        self.assertEqual(hours[0]["time_iso"], "2026-10-24T20:00+01:00")
        self.assertEqual(hours[-1]["time_iso"], "2026-10-25T04:00+00:00")
        self.assertEqual(len(hours), 10)  # 20:00–04:00 with one extra hour

    def test_spring_forward_night_skips_one_oclock(self):
        # Clocks go forward 01:00 GMT → 02:00 BST on 2026-03-29. Darkness: 20:23 GMT → 04:46 BST.
        night = window(fake_entry("Europe/London", date(2026, 3, 28)), datetime(2026, 3, 28, 12, tzinfo=UTC), LONDON)
        hours = night["night_forecast"]
        times = [h["time"] for h in hours]
        self.assertNotIn("2026-03-29T01:00", times)
        self.assertEqual(times, ["2026-03-28T21:00", "2026-03-28T22:00", "2026-03-28T23:00", "2026-03-29T00:00",
                                 "2026-03-29T02:00", "2026-03-29T03:00", "2026-03-29T04:00"])
        self.assertEqual(hours[0]["tz_abbreviation"], "GMT")
        self.assertEqual(hours[-1]["tz_abbreviation"], "BST")


class MidnightCrossingTests(unittest.TestCase):
    def test_window_spans_midnight_into_next_date(self):
        night = window(fake_entry("America/Chicago", date(2026, 11, 9)), datetime(2026, 11, 9, 18, tzinfo=UTC), AUSTIN)
        times = [h["time"] for h in night["night_forecast"]]
        self.assertEqual(times[0], "2026-11-09T19:00")
        self.assertIn("2026-11-09T23:00", times)
        self.assertIn("2026-11-10T00:00", times)
        self.assertEqual(times[-1], "2026-11-10T05:00")
        self.assertEqual(len(times), 11)
        # Every time_iso is a valid, strictly increasing instant.
        instants = [datetime.fromisoformat(h["time_iso"]) for h in night["night_forecast"]]
        self.assertEqual(instants, sorted(set(instants)))


class TimezoneFallbackTests(unittest.TestCase):
    def test_missing_iana_zone_falls_back_to_fixed_offset(self):
        entry = fake_entry(None, date(2026, 11, 9), offset_seconds=-6 * 3600)
        night = window(entry, datetime(2026, 11, 9, 20, tzinfo=UTC), AUSTIN)
        self.assertEqual(night["timezone"], "UTC-06:00")
        self.assertEqual(night["night_forecast"][0]["time_iso"], "2026-11-09T19:00-06:00")

    def test_unknown_iana_zone_falls_back_to_fixed_offset(self):
        entry = fake_entry("Asia/Tokyo", date(2026, 11, 10))
        entry["timezone"] = "Not/AZone"
        entry["utc_offset_seconds"] = 9 * 3600
        night = window(entry, datetime(2026, 11, 10, 9, tzinfo=UTC), TOKYO)  # 18:00 JST
        self.assertEqual(night["timezone"], "UTC+09:00")
        self.assertEqual(night["night_forecast"][0]["time_iso"], "2026-11-10T19:00+09:00")


class ApiCompatibilityTests(unittest.TestCase):
    """Endpoints called with Open-Meteo mocked; checks existing fields, scoring, and timezone fields."""

    def _mock_get(self, payload):
        response = mock.Mock()
        response.json.return_value = payload
        response.raise_for_status.return_value = None
        return mock.patch.object(app.requests, "get", return_value=response)

    def test_best_spot_response_shape_and_scoring(self):
        points = app.generate_grid(*AUSTIN, radius_km=12, spacing_km=3)
        entries = [fake_entry("America/Chicago", date(2026, 11, 9)) for _ in points]

        with self._mock_get(entries) as get, \
                mock.patch.object(app, "utc_now", return_value=datetime(2026, 11, 9, 18, tzinfo=UTC)):
            result = app.get_best_spot(*AUSTIN)

        url = get.call_args.args[0]
        self.assertIn("timezone=auto", url)
        self.assertIn("forecast_days=2", url)

        self.assertEqual(set(result), {"query_center", "timezone", "darkness_available", "message",
                                       "best_spot", "candidates_checked", "radius_km"})
        self.assertEqual(result["timezone"], "America/Chicago")
        self.assertTrue(result["darkness_available"])
        self.assertIsNone(result["message"])
        self.assertEqual(result["candidates_checked"], len(points))
        best = result["best_spot"]
        for key in ("lat", "lng", "distance_km", "timezone", "bortle_scale",
                    "avg_night_score", "best_hour", "night_forecast"):
            self.assertIn(key, best)
        for key in ("time", "time_iso", "tz_abbreviation", "sun_elevation", "cloud_cover",
                    "precipitation", "wind_speed", "humidity", "score"):
            self.assertIn(key, best["best_hour"])

        # Scoring weights unchanged: Bortle 6 (no nearby dark spot), cloud 10, wind 5, humidity 60.
        expected = 100 - 10 * 0.6 - 0 - 5 * 0.3 - (60 - 50) * 0.2 - (6 - 1) * 5
        self.assertEqual(best["bortle_scale"], 6)
        self.assertEqual(best["best_hour"]["score"], round(expected, 1))
        self.assertEqual(best["avg_night_score"], round(expected, 1))

    def test_weather_requests_local_timezone(self):
        payload = {
            "timezone": "Asia/Tokyo", "utc_offset_seconds": 32400,
            "current": {"time": "2026-11-10T01:00", "cloud_cover": 5, "precipitation": 0.0,
                        "wind_speed_10m": 3.0, "relative_humidity_2m": 40},
        }
        with self._mock_get(payload) as get:
            result = app.get_weather(35.68, 139.69)
        self.assertIn("timezone=auto", get.call_args.args[0])
        self.assertEqual(result["time"], "2026-11-10T01:00")
        self.assertEqual(result["timezone"], "Asia/Tokyo")
        self.assertEqual(result["cloud_cover"], 5)


if __name__ == "__main__":
    unittest.main()
