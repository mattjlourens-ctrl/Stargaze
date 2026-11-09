"""Static Bortle-scale dataset of known dark-sky locations.

A placeholder for real light-pollution data (e.g. VIIRS radiance or a light-pollution map API).
"""
from geo import haversine

# Beyond this distance from every known spot, the sky is assumed suburban.
NEAREST_SPOT_MAX_KM = 500
DEFAULT_BORTLE = 6

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


def nearest_bortle(lat: float, lng: float) -> int:
    """Bortle scale at the given point, taken from the nearest known spot."""
    nearest = min(DARK_SKY_SPOTS, key=lambda s: haversine(lat, lng, s["lat"], s["lng"]))
    if haversine(lat, lng, nearest["lat"], nearest["lng"]) > NEAREST_SPOT_MAX_KM:
        return DEFAULT_BORTLE
    return nearest["bortle"]


def spots_near(lat: float, lon: float, radius_km: float, limit: int = 8) -> list[dict]:
    """Known dark-sky spots within radius_km, best first (darker and closer score higher)."""
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
    return results[:limit]
