"""Great-circle distance and the candidate search grid."""
import math

EARTH_RADIUS_KM = 6371.0
KM_PER_DEG_LAT = 111.0


def haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in km."""
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    return EARTH_RADIUS_KM * 2 * math.asin(math.sqrt(a))


def normalize_longitude(lng: float) -> float:
    """Wrap an out-of-range longitude into [-180, 180). In-range values are returned untouched,
    so ordinary grids are bit-for-bit identical to their unwrapped form."""
    if -180 <= lng <= 180:
        return lng
    return (lng + 180) % 360 - 180


def generate_grid(lat: float, lon: float, radius_km: float, spacing_km: float) -> list[tuple[float, float]]:
    """Candidate points on a square grid, clipped to a circle of radius_km around (lat, lon).

    Longitudes wrap across the antimeridian and points past a pole are dropped, so every point
    is a valid coordinate for the weather API."""
    steps = max(1, round(radius_km / spacing_km))
    km_per_deg_lng = KM_PER_DEG_LAT * math.cos(math.radians(lat)) or KM_PER_DEG_LAT

    points = []
    for i in range(-steps, steps + 1):
        for j in range(-steps, steps + 1):
            plat = lat + (i * spacing_km) / KM_PER_DEG_LAT
            if abs(plat) > 90:
                continue
            plng = normalize_longitude(lon + (j * spacing_km) / km_per_deg_lng)
            if haversine(lat, lon, plat, plng) <= radius_km:
                points.append((plat, plng))
    return points
