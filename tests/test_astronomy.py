"""Astronomical-darkness selection. Run: python -m unittest discover tests

Reference elevations and dusk/dawn times come from PyEphem (VSOP87, an independent method from
the NOAA equations in solar.py); a 20,000-sample comparison over 2020–2035 agreed within 0.02°.
"""
import unittest
from datetime import date, datetime, timezone
from unittest import mock
from zoneinfo import ZoneInfo

from fastapi import HTTPException

import app
from solar import ASTRONOMICAL_DARKNESS_DEG, is_astronomically_dark, solar_elevation
from test_timezones import AUSTIN, LONDON, TOKYO, fake_entry, window

UTC = timezone.utc
SYDNEY = (-33.8688, 151.2093)
SUTHERLAND = (-32.38, 20.81)
TROMSO = (69.6492, 18.9553)
OSLO = (59.9139, 10.7522)


class SolarElevationTests(unittest.TestCase):
    def test_matches_reference_elevations(self):
        cases = [  # (lat, lng, instant, PyEphem elevation)
            (*LONDON, datetime(2026, 11, 9, 17, tzinfo=UTC), -6.57),
            (*LONDON, datetime(2026, 11, 9, 22, tzinfo=UTC), -49.82),
            (*SUTHERLAND, datetime(2026, 6, 21, 21, tzinfo=UTC), -66.51),
            (0.0, 0.0, datetime(2026, 3, 20, 12, 7, tzinfo=UTC), 89.88),
        ]
        for lat, lng, when, expected in cases:
            with self.subTest(lat=lat, when=when):
                self.assertAlmostEqual(solar_elevation(lat, lng, when), expected, delta=0.05)

    def test_same_instant_in_any_timezone_gives_same_elevation(self):
        instant = datetime(2026, 11, 9, 22, tzinfo=UTC)
        for zone in ("Asia/Tokyo", "America/Chicago", "Australia/Sydney"):
            self.assertEqual(solar_elevation(*LONDON, instant.astimezone(ZoneInfo(zone))),
                             solar_elevation(*LONDON, instant))

    def test_threshold_is_inclusive_at_minus_18(self):
        self.assertEqual(ASTRONOMICAL_DARKNESS_DEG, -18.0)
        with mock.patch("solar.solar_elevation", return_value=-18.0):
            self.assertTrue(is_astronomically_dark(0, 0, datetime(2026, 1, 1, tzinfo=UTC)))
        with mock.patch("solar.solar_elevation", return_value=-17.99):
            self.assertFalse(is_astronomically_dark(0, 0, datetime(2026, 1, 1, tzinfo=UTC)))


class LondonNovemberTests(unittest.TestCase):
    """Sunset 16:20 GMT, but astronomical darkness only from 18:15 GMT to 05:14 GMT."""

    def setUp(self):
        self.entry = fake_entry("Europe/London", date(2026, 11, 9))

    def test_5pm_twilight_does_not_qualify(self):
        five_pm = datetime(2026, 11, 9, 17, tzinfo=ZoneInfo("Europe/London"))
        self.assertLess(solar_elevation(*LONDON, five_pm), 0)  # the Sun has set...
        self.assertGreater(solar_elevation(*LONDON, five_pm), -18)  # ...but it is still twilight
        night = window(self.entry, datetime(2026, 11, 9, 16, 30, tzinfo=UTC), LONDON)
        times = [h["time"] for h in night["night_forecast"]]
        self.assertNotIn("2026-11-09T17:00", times)
        self.assertNotIn("2026-11-09T18:00", times)  # 18:00 is still 2° short of -18
        self.assertEqual(times[0], "2026-11-09T19:00")
        self.assertEqual(times[-1], "2026-11-10T05:00")
        for h in night["night_forecast"]:
            self.assertLessEqual(h["sun_elevation"], -18)

    def test_later_hour_qualifies_and_earlier_hours_are_excluded(self):
        night = window(self.entry, datetime(2026, 11, 9, 22, 30, tzinfo=UTC), LONDON)
        times = [h["time"] for h in night["night_forecast"]]
        self.assertEqual(times[0], "2026-11-09T23:00")  # 19:00–22:00 have already passed
        self.assertEqual(night["best_hour"]["tz_abbreviation"], "GMT")


class OtherCityTests(unittest.TestCase):
    def test_austin_november(self):
        night = window(fake_entry("America/Chicago", date(2026, 11, 9)), datetime(2026, 11, 9, 18, tzinfo=UTC), AUSTIN)
        times = [h["time"] for h in night["night_forecast"]]
        self.assertEqual((times[0], times[-1], len(times)), ("2026-11-09T19:00", "2026-11-10T05:00", 11))

    def test_austin_across_us_fall_back(self):
        # 2026-11-01 02:00 CDT → 01:00 CST. Darkness 20:05 CDT → 05:24 CST.
        entry = fake_entry("America/Chicago", date(2026, 10, 31))
        night = window(entry, datetime(2026, 10, 31, 18, tzinfo=UTC), AUSTIN)
        hours = night["night_forecast"]
        self.assertEqual(hours[0]["time_iso"], "2026-10-31T21:00-05:00")
        self.assertEqual(hours[-1]["time_iso"], "2026-11-01T05:00-06:00")
        self.assertEqual([h["tz_abbreviation"] for h in hours].count("CDT"), 5)
        self.assertEqual(len(hours), 10)

    def test_tokyo_dark_hours_in_jst(self):
        # Darkness 18:05 JST → 04:45 JST (Nov 10–11).
        night = window(fake_entry("Asia/Tokyo", date(2026, 11, 10)), datetime(2026, 11, 10, 3, tzinfo=UTC), TOKYO)
        hours = night["night_forecast"]
        self.assertEqual(hours[0]["time_iso"], "2026-11-10T19:00+09:00")
        self.assertEqual(hours[-1]["time_iso"], "2026-11-11T04:00+09:00")
        self.assertTrue(all(h["tz_abbreviation"] == "JST" for h in hours))

    def test_southern_hemisphere_summer_sydney(self):
        # Short southern-summer night on AEDT: darkness 21:04 → 04:13 AEDT.
        night = window(fake_entry("Australia/Sydney", date(2026, 11, 9)), datetime(2026, 11, 9, 3, tzinfo=UTC), SYDNEY)
        times = [h["time"] for h in night["night_forecast"]]
        self.assertEqual(times, ["2026-11-09T22:00", "2026-11-09T23:00", "2026-11-10T00:00", "2026-11-10T01:00",
                                 "2026-11-10T02:00", "2026-11-10T03:00", "2026-11-10T04:00"])
        self.assertEqual(night["best_hour"]["tz_abbreviation"], "AEDT")

    def test_southern_hemisphere_winter_has_long_night(self):
        # Sutherland, South Africa in June: much longer dark window than Sydney in November.
        night = window(fake_entry("Africa/Johannesburg", date(2026, 6, 21)),
                       datetime(2026, 6, 21, 10, tzinfo=UTC), SUTHERLAND)
        self.assertGreaterEqual(len(night["night_forecast"]), 10)


class NoDarknessTests(unittest.TestCase):
    def test_tromso_midnight_sun(self):
        entry = fake_entry("Europe/Oslo", date(2026, 6, 20))
        self.assertIsNone(window(entry, datetime(2026, 6, 20, 0, tzinfo=UTC), TROMSO))

    def test_oslo_summer_sunset_without_darkness(self):
        # The Sun sets in Oslo, but only dips to about -6.6° — never astronomically dark.
        entry = fake_entry("Europe/Oslo", date(2026, 6, 20))
        self.assertIsNone(window(entry, datetime(2026, 6, 20, 0, tzinfo=UTC), OSLO))


class BestSpotEndpointTests(unittest.TestCase):
    def _call(self, center, entries, now):
        response = mock.Mock()
        response.json.return_value = entries
        response.raise_for_status.return_value = None
        with mock.patch.object(app.requests, "get", return_value=response) as get, \
                mock.patch.object(app, "utc_now", return_value=now):
            return app.get_best_spot(*center), get.call_args.args[0]

    def test_no_darkness_returns_structured_result(self):
        points = app.generate_grid(*TROMSO, radius_km=12, spacing_km=3)
        entries = [fake_entry("Europe/Oslo", date(2026, 6, 20)) for _ in points]
        result, url = self._call(TROMSO, entries, datetime(2026, 6, 20, 0, tzinfo=UTC))
        self.assertEqual(result, {
            "query_center": {"lat": TROMSO[0], "lng": TROMSO[1]},
            "timezone": "Europe/Oslo",
            "darkness_available": False,
            "message": app.NO_DARKNESS_MESSAGE,
            "best_spot": None,
            "candidates_checked": len(points),
            "radius_km": 12,
        })
        self.assertNotIn("is_day", url)

    def test_missing_forecast_data_is_still_an_upstream_error(self):
        with self.assertRaises(HTTPException) as ctx:
            self._call(LONDON, [{"hourly": {}}], datetime(2026, 11, 9, tzinfo=UTC))
        self.assertEqual(ctx.exception.status_code, 502)

    def test_ranking_picks_clearest_candidate_with_unchanged_scores(self):
        points = app.generate_grid(*LONDON, radius_km=12, spacing_km=3)
        clouds = [(i * 7) % 90 + 5 for i in range(len(points))]  # distinct per candidate
        entries = [fake_entry("Europe/London", date(2026, 11, 9), cloud=c) for c in clouds]
        result, _ = self._call(LONDON, entries, datetime(2026, 11, 9, 12, tzinfo=UTC))

        best = result["best_spot"]
        clearest = points[clouds.index(min(clouds))]
        self.assertEqual((best["lat"], best["lng"]), clearest)
        for h in best["night_forecast"]:
            self.assertEqual(h["score"], app.score_conditions(min(clouds), 0.0, 5.0, 60, best["bortle_scale"]))
        self.assertEqual(best["best_hour"]["time"], "2026-11-09T19:00")  # ties → first dark hour


if __name__ == "__main__":
    unittest.main()
