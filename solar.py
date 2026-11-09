"""Solar elevation from the NOAA solar-position equations (after Meeus, "Astronomical Algorithms").

Accurate to roughly 0.01° in elevation for dates within a few centuries of 2000 — far finer than
the 18° astronomical-darkness threshold requires. Atmospheric refraction is ignored; it is
negligible well below the horizon.
"""
import math
from datetime import datetime, timezone
from functools import lru_cache

ASTRONOMICAL_DARKNESS_DEG = -18.0


@lru_cache(maxsize=4096)
def _sun_position(unix_seconds: int) -> tuple[float, float]:
    """Solar declination (degrees) and equation of time (minutes) at a UTC instant.
    Location-independent, so cached and shared across all candidate coordinates."""
    julian_century = (unix_seconds / 86400 + 2440587.5 - 2451545.0) / 36525
    t = julian_century

    mean_long = (280.46646 + t * (36000.76983 + t * 0.0003032)) % 360
    mean_anom = 357.52911 + t * (35999.05029 - 0.0001537 * t)
    eccent = 0.016708634 - t * (0.000042037 + 0.0000001267 * t)
    m = math.radians(mean_anom)
    center = (math.sin(m) * (1.914602 - t * (0.004817 + 0.000014 * t))
              + math.sin(2 * m) * (0.019993 - 0.000101 * t)
              + math.sin(3 * m) * 0.000289)
    omega = math.radians(125.04 - 1934.136 * t)
    apparent_long = mean_long + center - 0.00569 - 0.00478 * math.sin(omega)

    mean_obliq = 23 + (26 + (21.448 - t * (46.815 + t * (0.00059 - t * 0.001813))) / 60) / 60
    obliq = math.radians(mean_obliq + 0.00256 * math.cos(omega))
    declination = math.degrees(math.asin(math.sin(obliq) * math.sin(math.radians(apparent_long))))

    y = math.tan(obliq / 2) ** 2
    l0 = math.radians(mean_long)
    eq_time = 4 * math.degrees(
        y * math.sin(2 * l0)
        - 2 * eccent * math.sin(m)
        + 4 * eccent * y * math.sin(m) * math.cos(2 * l0)
        - 0.5 * y * y * math.sin(4 * l0)
        - 1.25 * eccent * eccent * math.sin(2 * m)
    )
    return declination, eq_time


def solar_elevation(lat: float, lng: float, when: datetime) -> float:
    """Elevation of the Sun's center above the horizon, in degrees, at an aware datetime."""
    unix_seconds = int(when.astimezone(timezone.utc).timestamp())
    declination, eq_time = _sun_position(unix_seconds)

    minutes_utc = (unix_seconds % 86400) / 60
    true_solar_minutes = (minutes_utc + eq_time + 4 * lng) % 1440
    hour_angle = math.radians(true_solar_minutes / 4 - 180)

    lat_r, decl_r = math.radians(lat), math.radians(declination)
    cos_zenith = math.sin(lat_r) * math.sin(decl_r) + math.cos(lat_r) * math.cos(decl_r) * math.cos(hour_angle)
    return 90 - math.degrees(math.acos(max(-1.0, min(1.0, cos_zenith))))


def is_astronomically_dark(lat: float, lng: float, when: datetime) -> bool:
    """True when the Sun's center is at least 18° below the horizon."""
    return solar_elevation(lat, lng, when) <= ASTRONOMICAL_DARKNESS_DEG
