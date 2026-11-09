"""Stargaze API: FastAPI app, routes, and the static frontend. Vercel serves the `app` object."""
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from dark_sky import nearest_bortle, spots_near
from geo import generate_grid, haversine
from scoring import next_night_window
from weather import WeatherServiceError, fetch_current_weather, fetch_hourly_forecasts, location_timezone

FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"

DEFAULT_SEARCH_RADIUS_KM = 12
MAX_SEARCH_RADIUS_KM = 100
MIN_GRID_SPACING_KM = 2.0
DEFAULT_SPOTS_RADIUS_KM = 1000
MAX_SPOTS_RADIUS_KM = 20_000  # about half of Earth's circumference

NO_DARKNESS_MESSAGE = "No astronomical darkness is expected within the available forecast period for this location."

Latitude = Annotated[float, Query(ge=-90, le=90, description="Latitude in degrees")]
Longitude = Annotated[float, Query(ge=-180, le=180, description="Longitude in degrees")]

app = FastAPI(title="StarGaze API")


@app.exception_handler(WeatherServiceError)
def weather_service_error(_request: Request, exc: WeatherServiceError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


# ── Weather endpoint ──────────────────────────────────────────────────────────
@app.get("/api/weather")
def get_weather(lat: Latitude, lon: Longitude) -> dict:
    raw = fetch_current_weather(lat, lon)
    data = raw["current"]
    return {
        "time":          data.get("time", ""),
        "timezone":      location_timezone(raw)[1],
        "cloud_cover":   data.get("cloud_cover", 0),
        "precipitation": data.get("precipitation", 0.0),
        "wind_speed":    data.get("wind_speed_10m", 0.0),
        "humidity":      data.get("relative_humidity_2m", 0),
        "bortle_scale":  nearest_bortle(lat, lon),
    }


# ── Best spot endpoint ────────────────────────────────────────────────────────
@app.get("/api/best-spot")
def get_best_spot(
    lat: Latitude,
    lon: Longitude,
    radius_km: Annotated[float, Query(gt=0, le=MAX_SEARCH_RADIUS_KM)] = DEFAULT_SEARCH_RADIUS_KM,
) -> dict:
    spacing_km = max(MIN_GRID_SPACING_KM, radius_km / 4)
    points = generate_grid(lat, lon, radius_km=radius_km, spacing_km=spacing_km) or [(lat, lon)]
    entries = fetch_hourly_forecasts(points)

    candidates = []
    for (plat, plng), entry in zip(points, entries):
        night = next_night_window(entry, plat, plng)
        if night is None:
            continue
        candidates.append({
            "lat":         plat,
            "lng":         plng,
            "distance_km": round(haversine(lat, lon, plat, plng), 2),
            **night,
        })

    if not candidates:
        forecasts = [e for e in entries if e["hourly"]["time"]]
        if not forecasts:
            raise WeatherServiceError("The weather service returned no forecast data for this area.")
        # Forecast exists but never reaches astronomical darkness (e.g. high-latitude summer).
        return {
            "query_center":       {"lat": lat, "lng": lon},
            "timezone":           location_timezone(forecasts[0])[1],
            "darkness_available": False,
            "message":            NO_DARKNESS_MESSAGE,
            "best_spot":          None,
            "candidates_checked": len(forecasts),
            "radius_km":          radius_km,
        }

    best = max(candidates, key=lambda c: c["avg_night_score"])
    return {
        "query_center":       {"lat": lat, "lng": lon},
        "timezone":           best["timezone"],
        "darkness_available": True,
        "message":            None,
        "best_spot":          best,
        "candidates_checked": len(candidates),
        "radius_km":          radius_km,
    }


# ── Spots endpoint ────────────────────────────────────────────────────────────
@app.get("/api/spots")
def get_spots(
    lat: Latitude,
    lon: Longitude,
    radius_km: Annotated[float, Query(gt=0, le=MAX_SPOTS_RADIUS_KM)] = DEFAULT_SPOTS_RADIUS_KM,
) -> list[dict]:
    return spots_near(lat, lon, radius_km)


# Mounted last so the /api/* routes above take precedence. html=True serves index.html at "/".
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
