# Stargaze

**Find promising stargazing conditions near any city.**

Stargaze is a weather-aware web application that searches nearby coordinates and recommends a location and viewing time based on forecast conditions. It combines a Python/FastAPI backend with a lightweight JavaScript frontend to compare cloud cover, precipitation, wind, humidity, and an approximate measure of sky darkness.

**[Live demo](https://stargaze-ten.vercel.app)** · **[Source code](https://github.com/mattjlourens-ctrl/Stargaze)**

## Features

- **City search:** Look up a city using OpenStreetMap's Nominatim geocoding service.
- **Nearby location search:** Generate candidate coordinates within a configurable radius (12 km by default).
- **Astronomical-darkness analysis:** Retrieve hourly forecasts from Open-Meteo and evaluate the next period when the Sun is at least 18° below the horizon, so twilight hours are never recommended.
- **Location ranking:** Compare candidate points using a weighted score for cloud cover, precipitation, wind, humidity, and estimated sky darkness.
- **Results visualization:** View the recommended coordinates, best-scoring hour, conditions table, nightly cloud-cover forecast, and embedded map, with a link to Google Earth.

## How it works

1. **Find the city.** The frontend converts a city name into latitude and longitude using Nominatim.
2. **Generate candidates.** The backend creates a grid of coordinates around the city, excluding points outside the search radius.
3. **Fetch forecasts.** Open-Meteo supplies hourly weather data for the candidate coordinates in a batched request.
4. **Select dark hours.** For each candidate, the backend computes the Sun's elevation at every upcoming forecast hour and selects the next continuous run of astronomically dark hours (see [Astronomical darkness](#astronomical-darkness)).
5. **Score conditions.** Each dark hour receives a score based on the weather and an estimated Bortle-scale value.
6. **Recommend a location.** Candidates are ranked by their average score across the selected nighttime period. The highest-scoring candidate is returned with its best individual hour.
7. **Display results.** The frontend renders the recommendation, weather details, hourly cloud-cover values, and map.

### Scoring model

The backend calculates an hourly score using:

```text
score = 100
      - 0.6 × cloud_cover (%)
      - 8 × min(precipitation (mm), 10)
      - 0.3 × min(wind_speed (km/h), 40)
      - 0.2 × max(humidity (%) - 50, 0)
      - 5 × (estimated_bortle - 1)
```

Higher scores indicate more favorable conditions under this heuristic. A candidate's overall ranking is based on the **average** score of its nighttime hours, rather than only its best hour. The weights are project-defined heuristics, not a scientifically validated observability index.

> **Light-pollution limitation:** The current Bortle estimate uses the nearest entry in a small hardcoded dataset of dark-sky locations. When a candidate is more than 500 km from every entry, the backend assumes Bortle 6. This is a placeholder, **not** a reliable light-pollution measurement for arbitrary coordinates.

### Astronomical darkness

**Definition.** The sky is *astronomically dark* when the Sun's center is at least **18° below the horizon**. Between sunset and that point, the sky passes through civil (0° to −6°), nautical (−6° to −12°), and astronomical (−12° to −18°) twilight, and residual sunlight still washes out faint objects. In London in November, for example, the Sun sets around 16:20 but the sky isn't astronomically dark until about 18:15.

**Solar elevation.** `solar.py` computes the Sun's elevation locally using the NOAA solar-position equations, which are based on Meeus's *Astronomical Algorithms*. Each forecast hour's timezone-aware local time is converted to an absolute UTC instant before the calculation. Compared with PyEphem across 20,000 random locations and times from 2020 to 2035, the results agreed within 0.02°. Refraction is ignored because it is negligible this far below the horizon. The Sun's declination and equation of time depend only on the instant, so they are cached and shared by every candidate in a search. The calculation needs no network calls, and a full 45-candidate search adds only a few milliseconds.

**Eligible hours.** Starting from the current time, the backend skips every forecast hour where the Sun is above −18°, including daylight and all three twilight stages. It then takes the following continuous run of hours at or below −18°. Elevation is evaluated at each forecast timestamp (the top of the hour). Windows that cross midnight or a DST change are handled because each hour is a distinct UTC instant. Open-Meteo's sunset-based `is_day` field is no longer used. Darkness is an eligibility rule, not a scoring factor: the scoring weights below apply unchanged to the eligible hours. Each hour in the response includes its `sun_elevation` in degrees.

**Locations without darkness.** At high latitudes in summer, for example Oslo or Tromsø in June, the Sun never reaches −18°. If none of the candidates has a dark hour in the forecast, `/api/best-spot` returns HTTP 200 with `"darkness_available": false`, `"best_spot": null`, and a `message`. It never falls back to twilight hours. The frontend shows: *"No astronomical darkness is expected within the available forecast period for this location."* Successful responses include `"darkness_available": true` and `"message": null`. HTTP 502 is still reserved for missing or failed forecast data.

### Timezones

All forecast times are shown in the **searched location's** local time, not the visitor's. Searching Tokyo from Texas shows Japan Standard Time and Tokyo's calendar date.

- **Determining the timezone:** Forecasts are requested from Open-Meteo with `timezone=auto`, which resolves each coordinate to an IANA zone such as `America/Chicago` or `Asia/Tokyo`. The backend loads that zone with Python's `zoneinfo`. If the zone is missing or unknown, it falls back to Open-Meteo's fixed `utc_offset_seconds`.
- **Selecting the nighttime window:** The current moment is compared against each forecast hour as an absolute UTC instant, so neither the server's nor the visitor's timezone affects the result. This handles locations that are already on a different calendar day, windows that cross midnight, and DST changes during the night. When clocks fall back, the repeated hour is kept as two distinct hours with different offsets.
- **Displaying times:** The frontend never passes offset-less timestamps to `new Date()`, which would interpret them in the visitor's timezone. It formats the local wall-clock fields directly and labels them with the abbreviation the backend computed for each hour, for example `Tue, Nov 10, 3:00 AM JST · Asia/Tokyo time`. If the abbreviation changes mid-night because of a DST transition, the hourly forecast labels the affected hour.

**Timestamp format.** Each hour in `night_forecast` (and `best_hour`) contains:

| Field | Example | Meaning |
| --- | --- | --- |
| `time` | `2026-11-09T21:00` | Local wall-clock time at the location (unchanged from earlier versions) |
| `time_iso` | `2026-11-09T21:00-06:00` | The same moment as ISO 8601 with its UTC offset |
| `tz_abbreviation` | `CST` | Timezone abbreviation in effect for that hour |
| `sun_elevation` | `-24.3` | Sun's elevation in degrees at that hour (always ≤ −18) |

The response also includes the location's IANA zone as `timezone`, both at the top level and on `best_spot`.

## Tech stack

| Layer | Technologies |
| --- | --- |
| Backend | Python, FastAPI, Requests |
| Frontend | JavaScript, HTML, CSS, Canvas |
| Forecast data | Open-Meteo API |
| Geocoding | OpenStreetMap Nominatim |
| Maps | Google Maps embed, Google Earth link |

## Getting started

### Prerequisites

- Python 3.10 or newer
- Internet access for geocoding, weather forecasts, and map features

### Run locally

1. Clone the repository and enter the project directory:

   ```bash
   git clone https://github.com/mattjlourens-ctrl/Stargaze.git
   cd Stargaze
   ```

2. Create and activate a virtual environment:

   **macOS / Linux**

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

   **Windows (PowerShell)**

   ```powershell
   py -m venv .venv
   .venv\Scripts\Activate.ps1
   ```

3. Install the application dependencies and Uvicorn server:

   ```bash
   python -m pip install -r requirements.txt uvicorn
   ```

4. Start the FastAPI application from the repository root:

   ```bash
   uvicorn app:app --reload
   ```

5. Open **http://127.0.0.1:8000** in a browser. Enter a city and select **Search**.

FastAPI serves the frontend and API from the same local server. No separate frontend development server is required. Interactive API documentation is available at **http://127.0.0.1:8000/docs**.

## API endpoints

| Endpoint | Purpose | Parameters |
| --- | --- | --- |
| `GET /api/best-spot` | Rank nearby forecast locations and return the recommended spot | `lat`, `lon`, optional `radius_km` (default: `12`) |
| `GET /api/weather` | Retrieve current weather and estimated Bortle value for one coordinate | `lat`, `lon` |
| `GET /api/spots` | List up to eight nearby entries from the built-in dark-sky dataset | `lat`, `lon`, optional `radius_km` (default: `1000`) |

For example:

```text
http://127.0.0.1:8000/api/best-spot?lat=30.2672&lon=-97.7431
```

The `/api/best-spot` response includes the search center, the location's IANA timezone, whether astronomical darkness is available (`darkness_available`, plus a `message` when it is not), recommended location, distance from the city center, average nighttime score, best hour, hourly nighttime forecast, number of candidates evaluated, and search radius. `/api/weather` returns its `time` in the location's local time, along with `timezone`. See [Timezones](#timezones) for the timestamp format.

## Running tests

Tests use synthetic forecasts and need no network access:

```bash
python -m unittest discover tests        # backend: solar elevation, dark-hour selection, timezones, API shape
node --test tests/time-format.test.js    # frontend: time formatting (Node 18+)
```

## Project structure

```text
Stargaze/
├── app.py                 # FastAPI routes, grid search, weather scoring
├── solar.py               # Solar elevation and astronomical-darkness check
├── frontend/
│   ├── index.html         # Page layout and styles
│   ├── app.js              # Search and results rendering
│   ├── time-format.js      # Formats forecast times in the searched location's timezone
│   └── starfield.js        # Decorative canvas starfield
├── tests/                 # Backend (unittest) and frontend (node:test) tests
├── requirements.txt       # Python application dependencies
├── .gitignore
└── README.md
```

## Current limitations

- **Approximate darkness data:** The built-in Bortle estimates do not replace a geographic light-pollution dataset.
- **Accessibility:** The search evaluates coordinate points, not verified public, reachable, or safe observation sites.
- **Weather-only simplification:** Twilight is excluded, but the score does not account for moon illumination, horizon obstructions, or seeing conditions. A bright Moon can still wash out an astronomically dark sky.
- **Hourly resolution:** Darkness is checked at each forecast hour, so a dark period is reported to the hour. If darkness begins at 18:15, the first eligible hour is 19:00. A dark period shorter than an hour that doesn't include a full hour mark may be missed.
- **Forecast horizon:** Forecasts cover today and tomorrow in the location's local time (`forecast_days=2`). Late on the second day, the next dark window may be cut off at the end of the forecast. "No astronomical darkness" means none within this period, not none at all.
- **No terrain or altitude model:** Elevation is calculated for a sea-level horizon and doesn't account for mountains or the observer's altitude.
- **Timezone of the winning spot:** Times use the timezone of the recommended coordinate. Near a timezone border, a candidate up to 12 km away can fall in a different zone from the searched city. The label always names the zone actually used.
- **Abbreviations:** Some zones have no common abbreviation, and the label then shows a numeric offset such as `-03`. Daylight saving rules come from the `tzdata` package and are only as current as the installed version.
- **Map coverage:** The map displays the winning coordinate, not every evaluated candidate.

## Roadmap

- [ ] Replace placeholder Bortle estimates with geographically accurate light-pollution data, such as VIIRS-derived radiance data.
- [ ] Include moon phase and illumination in the scoring model.
- [x] Correct timezone-aware display of recommended viewing times.
- [ ] Show candidate locations on an interactive map.
- [ ] Improve location suitability checks and error handling.
- [x] Recommend only astronomically dark hours (Sun ≥ 18° below the horizon).
- [ ] Expand automated tests: dark-hour selection, timezones, spot ranking, and API responses are covered; grid generation is not yet.

## Data sources

- [Open-Meteo](https://open-meteo.com/) — hourly and current weather forecasts.
- [OpenStreetMap / Nominatim](https://nominatim.org/) — city geocoding and reverse geocoding.
- [Google Maps](https://maps.google.com/) and [Google Earth](https://earth.google.com/) — location visualization.

Stargaze provides an estimated recommendation, not a guarantee of visibility or site access. Verify local conditions and access permissions before traveling to a suggested coordinate.