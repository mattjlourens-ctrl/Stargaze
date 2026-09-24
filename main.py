import math
from datetime import datetime, timedelta, timezone

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="StarGaze API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# ── Light pollution: static Bortle-scale dataset ──────────────────────────────
# Real data would come from a shapefile or the Light Pollution Map API.
# Each entry: (lat, lng, bortle, name, tags)
DARK_SKY_SPOTS: list[dict] = [
    {"lat": 51.178, "lng": -1.826,  "bortle": 3, "name": "Salisbury Plain",         "tags": ["open field", "flat horizon"]},
    {"lat": 54.45,  "lng": -3.08,   "bortle": 2, "name": "Lake District NP",         "tags": ["mountains", "dark sky reserve"]},
    {"lat": 36.106, "lng": -112.11, "bortle": 2, "name": "Grand Canyon South Rim",   "tags": ["dark sky park", "high altitude"]},
    {"lat": 32.27,  "lng": -110.83, "bortle": 3, "name": "Kitt Peak, Arizona",        "tags": ["observatory", "desert"]},
    {"lat": -22.95, "lng": -68.19,  "bortle": 1, "name": "Atacama Desert",            "tags": ["world class", "high altitude", "dry"]},
    {"lat": -29.05, "lng": 26.71,   "bortle": 2, "name": "Sutherland, South Africa",  "tags": ["SALT telescope", "karoo"]},
    {"lat": -32.38, "lng": 20.81,   "bortle": 2, "name": "Matjiesfontein, Karoo",     "tags": ["karoo", "semi-arid"]},
    {"lat": 28.30,  "lng": -16.51,  "bortle": 2, "name": "Teide NP, Tenerife",        "tags": ["volcano", "dark sky reserve"]},
    {"lat": 45.86,  "lng": 6.87,    "bortle": 3, "name": "Chamonix, French Alps",     "tags": ["mountains", "alpine"]},
    {"lat": 35.68,  "lng": 138.56,  "bortle": 3, "name": "Fuji Five Lakes",           "tags": ["mountain", "iconic"]},
    {"lat": 64.25,  "lng": -20.0,   "bortle": 2, "name": "Central Iceland Highlands", "tags": ["aurora", "lava fields"]},
    {"lat": -43.5,  "lng": 170.1,   "bortle": 1, "name": "Aoraki Mackenzie, NZ",      "tags": ["dark sky reserve", "southern sky"]},
    {"lat": 38.61,  "lng": -109.55, "bortle": 2, "name": "Canyonlands NP, Utah",      "tags": ["dark sky park", "canyon"]},
    {"lat": 47.86,  "lng": 13.8,    "bortle": 3, "name": "Berchtesgaden, Bavaria",    "tags": ["national park", "alpine"]},
    {"lat": -33.86, "lng": 18.86,   "bortle": 5, "name": "Stellenbosch Wine Valley",  "tags": ["wine region", "partial light"]},
]


def haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in km."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def nearest_bortle(lat: float, lng: float) -> int:
    """Return Bortle scale at the given point by finding the nearest known spot."""
    nearest = min(DARK_SKY_SPOTS, key=lambda s: haversine(lat, lng, s["lat"], s["lng"]))
    dist = haversine(lat, lng, nearest["lat"], nearest["lng"])
    # If far from any known dark spot assume suburban sky (Bortle 6)
    if dist > 500:
        return 6
    return nearest["bortle"]


def generate_grid(lat: float, lon: float, radius_km: float, spacing_km: float) -> list[tuple[float, float]]:
    """Candidate points on a square grid, clipped to a circle of radius_km around (lat, lon)."""
    steps = max(1, round(radius_km / spacing_km))
    km_per_deg_lat = 111.0
    km_per_deg_lng = 111.0 * math.cos(math.radians(lat)) or 111.0

    points = []
    for i in range(-steps, steps + 1):
        for j in range(-steps, steps + 1):
            plat = lat + (i * spacing_km) / km_per_deg_lat
            plng = lon + (j * spacing_km) / km_per_deg_lng
            if haversine(lat, lon, plat, plng) <= radius_km:
                points.append((plat, plng))
    return points


def score_conditions(cloud_cover: float, precipitation: float, wind_speed: float, humidity: float, bortle: int) -> float:
    """Higher is better for stargazing: rewards clear, dry, calm, dark skies."""
    score = 100.0
    score -= cloud_cover * 0.6
    score -= min(precipitation, 10) * 8
    score -= min(wind_speed, 40) * 0.3
    score -= max(0.0, humidity - 50) * 0.2
    score -= (bortle - 1) * 5
    return round(score, 1)


def next_night_window(entry: dict, lat: float, lng: float) -> dict | None:
    """From an hourly forecast entry, pull the next contiguous block of night (is_day == 0)
    hours starting from now, score each hour, and summarize the block. None if no night data."""
    hourly = entry.get("hourly", {})
    times = hourly.get("time", [])
    is_day = hourly.get("is_day", [])
    cloud = hourly.get("cloud_cover", [])
    precip = hourly.get("precipitation", [])
    wind = hourly.get("wind_speed_10m", [])
    humidity = hourly.get("relative_humidity_2m", [])
    if not times:
        return None

    local_now = datetime.now(timezone.utc) + timedelta(seconds=entry.get("utc_offset_seconds", 0))
    now_str = local_now.strftime("%Y-%m-%dT%H:%M")

    i = next((idx for idx, t in enumerate(times) if t >= now_str), len(times))
    while i < len(times) and is_day[i] == 1:  # skip any remaining daylight hours
        i += 1

    night_indices = []
    while i < len(times) and is_day[i] == 0:
        night_indices.append(i)
        i += 1

    if not night_indices:
        return None

    bortle = nearest_bortle(lat, lng)
    hours = []
    for idx in night_indices:
        c, p, w, h = cloud[idx], precip[idx], wind[idx], humidity[idx]
        hours.append({
            "time":          times[idx],
            "cloud_cover":   c,
            "precipitation": p,
            "wind_speed":    w,
            "humidity":      h,
            "score":         score_conditions(c, p, w, h, bortle),
        })

    return {
        "bortle_scale":    bortle,
        "avg_night_score": round(sum(h["score"] for h in hours) / len(hours), 1),
        "best_hour":       max(hours, key=lambda h: h["score"]),
        "night_forecast":  hours,
    }


# ── Weather endpoint ──────────────────────────────────────────────────────────
@app.get("/api/weather")
def get_weather(lat: float, lon: float) -> dict:
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&current=cloud_cover,precipitation,wind_speed_10m,relative_humidity_2m,visibility"
        f"&forecast_days=1"
    )
    try:
        res = requests.get(url, timeout=8)
        res.raise_for_status()
        data = res.json()["current"]
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Weather API error: {exc}") from exc

    return {
        "time":          data.get("time", ""),
        "cloud_cover":   data.get("cloud_cover", 0),
        "precipitation": data.get("precipitation", 0.0),
        "wind_speed":    data.get("wind_speed_10m", 0.0),
        "humidity":      data.get("relative_humidity_2m", 0),
        "bortle_scale":  nearest_bortle(lat, lon),
    }


# ── Best spot endpoint ────────────────────────────────────────────────────────
@app.get("/api/best-spot")
def get_best_spot(lat: float, lon: float, radius_km: float = 12) -> dict:
    spacing_km = max(2.0, radius_km / 4)
    points = generate_grid(lat, lon, radius_km=radius_km, spacing_km=spacing_km)
    if not points:
        points = [(lat, lon)]

    lat_str = ",".join(f"{p[0]:.5f}" for p in points)
    lng_str = ",".join(f"{p[1]:.5f}" for p in points)
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat_str}&longitude={lng_str}"
        f"&hourly=cloud_cover,precipitation,wind_speed_10m,relative_humidity_2m,is_day"
        f"&timezone=auto&forecast_days=2"
    )
    try:
        res = requests.get(url, timeout=15)
        res.raise_for_status()
        raw = res.json()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Weather API error: {exc}") from exc

    # Open-Meteo returns a bare object for a single coordinate, a list for multiple.
    entries = raw if isinstance(raw, list) else [raw]

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
        raise HTTPException(status_code=502, detail="No night forecast data available for this area")

    best = max(candidates, key=lambda c: c["avg_night_score"])
    return {
        "query_center":       {"lat": lat, "lng": lon},
        "best_spot":          best,
        "candidates_checked": len(candidates),
        "radius_km":          radius_km,
    }


# ── Spots endpoint ────────────────────────────────────────────────────────────
@app.get("/api/spots")
def get_spots(lat: float, lon: float, radius_km: float = 1000) -> list[dict]:
    results = []
    for s in DARK_SKY_SPOTS:
        dist = haversine(lat, lon, s["lat"], s["lng"])
        if dist <= radius_km:
            score = max(0, round(100 - s["bortle"] * 10 - (dist / radius_km) * 10))
            results.append({
                "name":        s["name"],
                "lat":         s["lat"],
                "lng":         s["lng"],
                "bortle":      s["bortle"],
                "distance_km": dist,
                "score":       score,
                "tags":        s["tags"],
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:8]


app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")