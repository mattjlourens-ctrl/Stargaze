"""Distance, grid generation, weather scoring, and incomplete forecast data.
Run: python -m unittest discover tests
"""
import math
import unittest
from datetime import date, datetime, timezone

from dark_sky import DEFAULT_BORTLE, nearest_bortle
from geo import generate_grid, haversine, normalize_longitude
from scoring import next_night_window, score_conditions
from test_timezones import LONDON, fake_entry

UTC = timezone.utc


class HaversineTests(unittest.TestCase):
    def test_known_distances(self):
        self.assertEqual(haversine(10, 20, 10, 20), 0)
        self.assertAlmostEqual(haversine(51.5072, -0.1276, 48.8566, 2.3522), 343.6, delta=0.5)  # London–Paris
        self.assertAlmostEqual(haversine(0, 0, 0, 180), math.pi * 6371, delta=0.01)  # antipodes
        self.assertAlmostEqual(haversine(0, 179.9, 0, -179.9), 22.24, delta=0.01)  # across the date line

    def test_symmetric(self):
        self.assertEqual(haversine(30, -97, -33, 151), haversine(-33, 151, 30, -97))


class GridTests(unittest.TestCase):
    def test_default_search_grid(self):
        lat, lon = LONDON
        points = generate_grid(lat, lon, radius_km=12, spacing_km=3)
        self.assertEqual(len(points), 45)  # 9×9 square clipped to the circle
        self.assertIn((lat, lon), points)
        self.assertTrue(all(haversine(lat, lon, *p) <= 12 for p in points))

    def test_ordinary_grid_is_unchanged_by_wrapping(self):
        # Same arithmetic as before the date-line fix, for a location far from both edges.
        lat, lon, radius, spacing = 30.2672, -97.7431, 12, 3
        km_lng = 111.0 * math.cos(math.radians(lat))
        expected = [(lat + i * spacing / 111.0, lon + j * spacing / km_lng)
                    for i in range(-4, 5) for j in range(-4, 5)]
        expected = [p for p in expected if haversine(lat, lon, *p) <= radius]
        self.assertEqual(generate_grid(lat, lon, radius, spacing), expected)

    def test_grid_across_the_date_line_stays_in_range(self):
        # Regression: points used to exceed 180°, which Open-Meteo rejects for the whole batch.
        for lon in (179.95, -179.95, 180, -180):
            points = generate_grid(-16.8, lon, radius_km=12, spacing_km=3)
            with self.subTest(lon=lon):
                self.assertEqual(len(points), 45)
                self.assertTrue(all(-180 <= p[1] <= 180 for p in points))
                self.assertTrue(all(haversine(-16.8, lon, *p) <= 12 for p in points))

    def test_grid_near_the_poles_stays_in_range(self):
        # Regression: points used to exceed ±90° latitude.
        for lat in (89.95, -89.95, 90, -90):
            points = generate_grid(lat, 10, radius_km=12, spacing_km=3)
            with self.subTest(lat=lat):
                self.assertTrue(points)
                self.assertTrue(all(-90 <= p[0] <= 90 and -180 <= p[1] <= 180 for p in points))
                self.assertTrue(all(haversine(lat, 10, *p) <= 12 for p in points))

    def test_normalize_longitude(self):
        self.assertEqual(normalize_longitude(-97.7431), -97.7431)
        self.assertEqual(normalize_longitude(180), 180)
        self.assertAlmostEqual(normalize_longitude(180.5), -179.5)
        self.assertAlmostEqual(normalize_longitude(-180.5), 179.5)
        self.assertAlmostEqual(normalize_longitude(540), -180)


class ScoringTests(unittest.TestCase):
    def test_perfect_conditions(self):
        self.assertEqual(score_conditions(0, 0, 0, 50, 1), 100.0)

    def test_weights(self):
        self.assertEqual(score_conditions(50, 0, 0, 50, 1), 70.0)    # 0.6 per % cloud
        self.assertEqual(score_conditions(0, 2, 0, 50, 1), 84.0)     # 8 per mm rain
        self.assertEqual(score_conditions(0, 0, 10, 50, 1), 97.0)    # 0.3 per km/h wind
        self.assertEqual(score_conditions(0, 0, 0, 80, 1), 94.0)     # 0.2 per % humidity above 50
        self.assertEqual(score_conditions(0, 0, 0, 50, 4), 85.0)     # 5 per Bortle step

    def test_caps_and_floors(self):
        self.assertEqual(score_conditions(0, 50, 0, 50, 1), score_conditions(0, 10, 0, 50, 1))  # rain capped at 10
        self.assertEqual(score_conditions(0, 0, 90, 50, 1), score_conditions(0, 0, 40, 50, 1))  # wind capped at 40
        self.assertEqual(score_conditions(0, 0, 0, 20, 1), 100.0)  # dry air is not rewarded

    def test_worst_case_and_rounding(self):
        self.assertEqual(score_conditions(100, 10, 40, 100, 9), -102.0)  # 100 - 60 - 80 - 12 - 10 - 40
        self.assertEqual(score_conditions(33, 0.3, 7, 61, 3), 63.5)      # 100 - 19.8 - 2.4 - 2.1 - 2.2 - 10


class BortleTests(unittest.TestCase):
    def test_nearest_known_spot_or_default(self):
        self.assertEqual(nearest_bortle(-22.95, -68.19), 1)  # Atacama itself
        self.assertEqual(nearest_bortle(*LONDON), 3)  # Salisbury Plain, ~130 km
        self.assertEqual(nearest_bortle(30.2672, -97.7431), DEFAULT_BORTLE)  # Austin: nothing within 500 km


class IncompleteForecastTests(unittest.TestCase):
    def test_null_values_are_skipped_not_crashed_on(self):
        # Regression: a null hourly value used to raise TypeError (HTTP 500).
        entry = fake_entry("Europe/London", date(2026, 11, 9))
        entry["hourly"]["cloud_cover"][20] = None  # 20:00, inside the dark window
        night = next_night_window(entry, *LONDON, now=datetime(2026, 11, 9, 12, tzinfo=UTC))
        times = [h["time"] for h in night["night_forecast"]]
        self.assertNotIn("2026-11-09T20:00", times)
        self.assertEqual(times[0], "2026-11-09T19:00")
        self.assertEqual(len(times), 10)

    def test_window_with_only_null_values_has_no_scorable_hours(self):
        entry = fake_entry("Europe/London", date(2026, 11, 9))
        entry["hourly"]["relative_humidity_2m"] = [None] * 48
        self.assertIsNone(next_night_window(entry, *LONDON, now=datetime(2026, 11, 9, 12, tzinfo=UTC)))


if __name__ == "__main__":
    unittest.main()
