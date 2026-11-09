"""HTTP-level tests: validation, error handling, response compatibility, static files.
Run: python -m unittest discover tests  (needs requirements-dev.txt for httpx)

Open-Meteo is always mocked; no network access.
"""
import unittest
import warnings
from datetime import date, datetime, timezone
from unittest import mock

import requests

with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)  # starlette's httpx deprecation notice
    from fastapi.testclient import TestClient

import app
import scoring
import weather
from geo import generate_grid
from test_timezones import AUSTIN, LONDON, fake_entry

UTC = timezone.utc
TROMSO = (69.6492, 18.9553)
client = TestClient(app.app)


def mock_response(payload=None, status=200, json_error=False):
    response = mock.Mock()
    response.status_code = status
    if status >= 400:
        response.raise_for_status.side_effect = requests.HTTPError(f"{status} Server Error for url: {weather.OPEN_METEO_URL}?secret")
    else:
        response.raise_for_status.return_value = None
    if json_error:
        response.json.side_effect = requests.JSONDecodeError("Expecting value", "<html>", 0)
    else:
        response.json.return_value = payload
    return response


def patched(response=None, side_effect=None, now=datetime(2026, 11, 9, 12, tzinfo=UTC)):
    get = mock.patch.object(weather.requests, "get", return_value=response, side_effect=side_effect)
    return get, mock.patch.object(scoring, "utc_now", return_value=now)


def london_entries():
    points = generate_grid(*LONDON, radius_km=12, spacing_km=3)
    return [fake_entry("Europe/London", date(2026, 11, 9)) for _ in points]


class ValidationTests(unittest.TestCase):
    def test_rejects_out_of_range_and_invalid_coordinates(self):
        bad = ["lat=91&lon=0", "lat=-90.5&lon=0", "lat=0&lon=180.5", "lat=0&lon=-181",
               "lat=nan&lon=0", "lat=0&lon=inf", "lat=abc&lon=0", "lon=0", "lat=0", ""]
        for endpoint in ("/api/best-spot", "/api/weather", "/api/spots"):
            for query in bad:
                with self.subTest(endpoint=endpoint, query=query):
                    self.assertEqual(client.get(f"{endpoint}?{query}").status_code, 422)

    def test_rejects_unreasonable_radii(self):
        for endpoint, too_big in (("/api/best-spot", 101), ("/api/spots", 20001)):
            for radius in (0, -5, too_big, "nan"):
                with self.subTest(endpoint=endpoint, radius=radius):
                    self.assertEqual(client.get(f"{endpoint}?lat=0&lon=0&radius_km={radius}").status_code, 422)

    def test_boundary_coordinates_are_accepted(self):
        current = {"timezone": "UTC", "current": {"time": "2026-11-09T12:00", "cloud_cover": 0}}
        for lat, lon in ((90, 180), (-90, -180), (89.95, 179.95)):
            points = generate_grid(lat, lon, radius_km=12, spacing_km=3)
            forecasts = [fake_entry("UTC", date(2026, 11, 9)) for _ in points]
            with self.subTest(lat=lat, lon=lon):
                self.assertEqual(client.get(f"/api/spots?lat={lat}&lon={lon}").status_code, 200)
                get, now = patched(mock_response(current))
                with get, now:
                    self.assertEqual(client.get(f"/api/weather?lat={lat}&lon={lon}").status_code, 200)
                get, now = patched(mock_response(forecasts))
                with get as mocked_get, now:
                    self.assertEqual(client.get(f"/api/best-spot?lat={lat}&lon={lon}").status_code, 200)
                sent_lngs = [float(x) for x in mocked_get.call_args.kwargs["params"]["longitude"].split(",")]
                self.assertTrue(all(-180 <= x <= 180 for x in sent_lngs))

    def test_validation_happens_before_calling_open_meteo(self):
        get, now = patched(mock_response([]))
        with get as mocked_get, now:
            client.get("/api/best-spot?lat=95&lon=0")
        mocked_get.assert_not_called()


class WeatherServiceErrorTests(unittest.TestCase):
    def assert_error(self, res, status, text):
        self.assertEqual(res.status_code, status)
        detail = res.json()["detail"]
        self.assertIn(text, detail)
        self.assertNotIn("open-meteo", detail.lower())  # no URLs or exception internals
        self.assertNotIn("secret", detail)

    def test_timeout_is_504(self):
        get, now = patched(side_effect=requests.Timeout("read timed out"))
        with get, now:
            self.assert_error(client.get("/api/best-spot?lat=51.5&lon=0"), 504, "timed out")

    def test_connection_error_is_502(self):
        get, now = patched(side_effect=requests.ConnectionError("Max retries exceeded with url: ..."))
        with get, now:
            self.assert_error(client.get("/api/best-spot?lat=51.5&lon=0"), 502, "Could not reach")

    def test_http_error_is_502(self):
        get, now = patched(mock_response(status=500))
        with get, now:
            self.assert_error(client.get("/api/weather?lat=51.5&lon=0"), 502, "returned an error")

    def test_invalid_json_is_502(self):
        get, now = patched(mock_response(json_error=True))
        with get, now:
            self.assert_error(client.get("/api/best-spot?lat=51.5&lon=0"), 502, "unexpected response")

    def test_malformed_forecasts_are_502(self):
        good = london_entries()
        broken_field = [dict(e) for e in good]
        broken_field[3] = {**good[3], "hourly": {**good[3]["hourly"], "cloud_cover": [10] * 5}}
        bad_time = [dict(e) for e in good]
        bad_time[0] = {**good[0], "hourly": {**good[0]["hourly"], "time": ["not a time"] * 48}}
        cases = {
            "too few entries": good[:-1],
            "not a list or object": "oops",
            "missing hourly": [{"timezone": "Europe/London"}] * len(good),
            "misaligned field": broken_field,
            "unparseable time": bad_time,
        }
        for name, payload in cases.items():
            get, now = patched(mock_response(payload))
            with self.subTest(name), get, now:
                self.assert_error(client.get(f"/api/best-spot?lat={LONDON[0]}&lon={LONDON[1]}"), 502, "unexpected")

    def test_current_weather_without_current_block_is_502(self):
        get, now = patched(mock_response({"timezone": "UTC"}))
        with get, now:
            self.assert_error(client.get("/api/weather?lat=0&lon=0"), 502, "unexpected")

    def test_empty_forecast_is_an_error_not_no_darkness(self):
        empty = {"hourly": {"time": [], **{f: [] for f in weather.WEATHER_FIELDS}}}
        points = generate_grid(*LONDON, radius_km=12, spacing_km=3)
        get, now = patched(mock_response([empty] * len(points)))
        with get, now:
            self.assert_error(client.get(f"/api/best-spot?lat={LONDON[0]}&lon={LONDON[1]}"), 502, "no forecast data")


class ResponseCompatibilityTests(unittest.TestCase):
    def test_best_spot_over_http(self):
        get, now = patched(mock_response(london_entries()))
        with get, now:
            res = client.get(f"/api/best-spot?lat={LONDON[0]}&lon={LONDON[1]}")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(set(body), {"query_center", "timezone", "darkness_available", "message",
                                     "best_spot", "candidates_checked", "radius_km"})
        self.assertTrue(body["darkness_available"])
        self.assertEqual(body["radius_km"], 12)
        self.assertEqual(body["best_spot"]["night_forecast"][0]["time"], "2026-11-09T19:00")

    def test_no_darkness_over_http_is_200_not_an_error(self):
        points = generate_grid(*TROMSO, radius_km=12, spacing_km=3)
        entries = [fake_entry("Europe/Oslo", date(2026, 6, 20)) for _ in points]
        get, now = patched(mock_response(entries), now=datetime(2026, 6, 20, tzinfo=UTC))
        with get, now:
            res = client.get(f"/api/best-spot?lat={TROMSO[0]}&lon={TROMSO[1]}")
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.json()["darkness_available"])
        self.assertIsNone(res.json()["best_spot"])
        self.assertEqual(res.json()["message"], app.NO_DARKNESS_MESSAGE)

    def test_request_parameters_sent_to_open_meteo(self):
        get, now = patched(mock_response(london_entries()))
        with get as mocked_get, now:
            client.get(f"/api/best-spot?lat={LONDON[0]}&lon={LONDON[1]}")
        params = mocked_get.call_args.kwargs["params"]
        self.assertEqual(params["hourly"], "cloud_cover,precipitation,wind_speed_10m,relative_humidity_2m")
        self.assertEqual((params["timezone"], params["forecast_days"]), ("auto", 2))
        self.assertEqual(len(params["latitude"].split(",")), len(london_entries()))

    def test_spots_sorted_limited_and_within_radius(self):
        res = client.get("/api/spots?lat=40&lon=-100&radius_km=20000")
        spots = res.json()
        self.assertEqual(len(spots), 8)
        self.assertEqual([s["score"] for s in spots], sorted((s["score"] for s in spots), reverse=True))
        near = client.get("/api/spots?lat=51.5&lon=-0.13&radius_km=200").json()
        self.assertEqual([s["name"] for s in near], ["Salisbury Plain"])


class StaticFrontendTests(unittest.TestCase):
    def test_index_links_stylesheet_and_scripts(self):
        html = client.get("/").text
        for asset in ('href="styles.css"', 'src="starfield.js"', 'src="time-format.js"', 'src="app.js"'):
            self.assertIn(asset, html)
        self.assertNotIn("<style>", html)

    def test_assets_are_served_with_correct_types(self):
        for path, content_type in (("/styles.css", "text/css"), ("/app.js", "javascript"),
                                   ("/time-format.js", "javascript"), ("/starfield.js", "javascript")):
            with self.subTest(path=path):
                res = client.get(path)
                self.assertEqual(res.status_code, 200)
                self.assertIn(content_type, res.headers["content-type"])


if __name__ == "__main__":
    unittest.main()
