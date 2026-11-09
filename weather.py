"""Open-Meteo client: requests, error mapping, response validation, and local-time parsing."""
import logging
from datetime import datetime, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests

logger = logging.getLogger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
WEATHER_FIELDS = ("cloud_cover", "precipitation", "wind_speed_10m", "relative_humidity_2m")
FORECAST_DAYS = 2
FORECAST_TIMEOUT_S = 15
CURRENT_TIMEOUT_S = 8


class WeatherServiceError(Exception):
    """Open-Meteo failed or returned unusable data. `message` is safe to show to API clients;
    the underlying cause is logged, not exposed."""

    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _get_json(params: dict, timeout: float) -> object:
    try:
        res = requests.get(OPEN_METEO_URL, params=params, timeout=timeout)
        res.raise_for_status()
    except requests.Timeout as exc:
        logger.warning("Open-Meteo request timed out: %s", exc)
        raise WeatherServiceError("The weather service timed out. Please try again.", status_code=504) from exc
    except requests.HTTPError as exc:
        logger.warning("Open-Meteo returned an HTTP error: %s", exc)
        raise WeatherServiceError("The weather service returned an error. Please try again later.") from exc
    except requests.RequestException as exc:
        logger.warning("Open-Meteo request failed: %s", exc)
        raise WeatherServiceError("Could not reach the weather service. Please try again later.") from exc

    # Parsed outside the try above: requests' JSONDecodeError is also a RequestException.
    try:
        return res.json()
    except ValueError as exc:
        logger.warning("Open-Meteo returned invalid JSON: %s", exc)
        raise _unexpected_response() from exc


def _unexpected_response() -> WeatherServiceError:
    return WeatherServiceError("The weather service returned an unexpected response.")


def _validate_hourly(entry: object) -> None:
    """Every hourly field must be a list aligned with `time`; individual values may be null."""
    hourly = entry.get("hourly") if isinstance(entry, dict) else None
    times = hourly.get("time") if isinstance(hourly, dict) else None
    if not isinstance(times, list):
        raise _unexpected_response()
    for field in WEATHER_FIELDS:
        values = hourly.get(field)
        if not isinstance(values, list) or len(values) != len(times):
            raise _unexpected_response()
    try:
        for t in times:
            datetime.fromisoformat(t)
    except (TypeError, ValueError) as exc:
        raise _unexpected_response() from exc


def fetch_hourly_forecasts(points: list[tuple[float, float]]) -> list[dict]:
    """One validated hourly forecast entry per point, in the same order, from a single batched request.
    Times are the location's local wall clock (`timezone=auto`), starting at local midnight today."""
    params = {
        "latitude":      ",".join(f"{lat:.5f}" for lat, _ in points),
        "longitude":     ",".join(f"{lng:.5f}" for _, lng in points),
        "hourly":        ",".join(WEATHER_FIELDS),
        "timezone":      "auto",
        "forecast_days": FORECAST_DAYS,
    }
    raw = _get_json(params, FORECAST_TIMEOUT_S)
    # Open-Meteo returns a bare object for a single coordinate, a list for multiple.
    entries = raw if isinstance(raw, list) else [raw]
    if len(entries) != len(points):
        logger.warning("Open-Meteo returned %d entries for %d points", len(entries), len(points))
        raise _unexpected_response()
    for entry in entries:
        _validate_hourly(entry)
    return entries


def fetch_current_weather(lat: float, lon: float) -> dict:
    """Open-Meteo's current-conditions response for one point, in the location's timezone."""
    params = {
        "latitude":      lat,
        "longitude":     lon,
        "current":       ",".join(WEATHER_FIELDS),
        "timezone":      "auto",
        "forecast_days": 1,
    }
    raw = _get_json(params, CURRENT_TIMEOUT_S)
    if not isinstance(raw, dict) or not isinstance(raw.get("current"), dict):
        raise _unexpected_response()
    return raw


def location_timezone(entry: dict) -> tuple[tzinfo, str]:
    """The forecast location's timezone and its name, from Open-Meteo's `timezone=auto` response.
    Prefers the IANA zone (DST-aware); falls back to the fixed `utc_offset_seconds`."""
    name = entry.get("timezone")
    if name:
        try:
            return ZoneInfo(name), name
        except (ZoneInfoNotFoundError, ValueError):
            pass
    offset = timezone(timedelta(seconds=entry.get("utc_offset_seconds", 0)))
    return offset, offset.tzname(None)


def localize_times(times: list[str], tz: tzinfo) -> list[datetime]:
    """Attach tz to Open-Meteo's naive local wall-clock strings ("YYYY-MM-DDTHH:MM").
    A wall-clock time that repeats (DST fall-back) is the second occurrence, so it gets fold=1."""
    seen: set[datetime] = set()
    localized = []
    for t in times:
        naive = datetime.fromisoformat(t)
        localized.append(naive.replace(tzinfo=tz, fold=int(naive in seen)))
        seen.add(naive)
    return localized
