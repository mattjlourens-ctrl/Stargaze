"""Viewing-window selection (astronomical darkness) and weather scoring."""
from datetime import datetime, timezone

from dark_sky import nearest_bortle
from solar import ASTRONOMICAL_DARKNESS_DEG, solar_elevation
from weather import WEATHER_FIELDS, localize_times, location_timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def score_conditions(cloud_cover: float, precipitation: float, wind_speed: float, humidity: float, bortle: int) -> float:
    """Higher is better for stargazing: rewards clear, dry, calm, dark skies."""
    score = 100.0
    score -= cloud_cover * 0.6
    score -= min(precipitation, 10) * 8
    score -= min(wind_speed, 40) * 0.3
    score -= max(0.0, humidity - 50) * 0.2
    score -= (bortle - 1) * 5
    return round(score, 1)


def next_night_window(entry: dict, lat: float, lng: float, now: datetime | None = None) -> dict | None:
    """From an hourly forecast entry, pull the next contiguous block of astronomically dark hours
    (Sun's center at or below -18°) starting from now, score each hour, and summarize the block.
    None if no such hour remains in the forecast — twilight hours are never substituted.

    `now` is an aware datetime (defaults to the current time); it is compared as an absolute
    instant, so the server's own timezone never affects which hours are selected.
    Dark hours with a missing (null) weather value are left unscored rather than guessed."""
    hourly = entry.get("hourly", {})
    times = hourly.get("time", [])
    if not times:
        return None
    cloud, precip, wind, humidity = (hourly[field] for field in WEATHER_FIELDS)

    tz, tz_name = location_timezone(entry)
    local_times = localize_times(times, tz)
    # Compare in UTC: aware datetimes sharing a tzinfo compare by wall clock, ignoring fold.
    now_utc = (now or utc_now()).astimezone(timezone.utc).replace(second=0, microsecond=0)

    # Elevations are computed lazily: only from now until the end of the first dark block.
    elevations: dict[int, float] = {}

    def is_dark(idx: int) -> bool:
        if idx not in elevations:
            elevations[idx] = solar_elevation(lat, lng, local_times[idx])
        return elevations[idx] <= ASTRONOMICAL_DARKNESS_DEG

    i = next((idx for idx, dt in enumerate(local_times) if dt.astimezone(timezone.utc) >= now_utc), len(times))
    while i < len(times) and not is_dark(i):  # skip daylight and civil/nautical/astronomical twilight
        i += 1

    night_indices = []
    while i < len(times) and is_dark(i):
        night_indices.append(i)
        i += 1

    if not night_indices:
        return None

    bortle = nearest_bortle(lat, lng)
    hours = []
    for idx in night_indices:
        c, p, w, h = cloud[idx], precip[idx], wind[idx], humidity[idx]
        if None in (c, p, w, h):
            continue
        local_dt = local_times[idx]
        hours.append({
            "time":            times[idx],  # location's local wall clock, "YYYY-MM-DDTHH:MM"
            "time_iso":        local_dt.isoformat(timespec="minutes"),  # same instant with UTC offset
            "tz_abbreviation": local_dt.tzname(),
            "sun_elevation":   round(elevations[idx], 1),
            "cloud_cover":   c,
            "precipitation": p,
            "wind_speed":    w,
            "humidity":      h,
            "score":         score_conditions(c, p, w, h, bortle),
        })

    if not hours:
        return None

    return {
        "timezone":        tz_name,
        "bortle_scale":    bortle,
        "avg_night_score": round(sum(h["score"] for h in hours) / len(hours), 1),
        "best_hour":       max(hours, key=lambda h: h["score"]),
        "night_forecast":  hours,
    }
