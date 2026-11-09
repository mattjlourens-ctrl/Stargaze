# Stargaze

**Find promising stargazing conditions near any city.**

Stargaze is a weather-aware web application that searches nearby coordinates and recommends a location and viewing time based on forecast conditions. It uses a Python/FastAPI backend and a lightweight JavaScript frontend. Candidate hours are limited to astronomical darkness, and candidates are ranked by cloud cover, precipitation, wind, humidity, and an approximate measure of sky darkness.

**[Live demo](https://stargaze-ten.vercel.app)** · **[Source code](https://github.com/mattjlourens-ctrl/Stargaze)**

## Features

- **City search:** Look up a city using OpenStreetMap's Nominatim geocoding service.
- **Nearby location search:** Evaluate a grid of candidate coordinates within a configurable radius (12 km by default).
- **Astronomical-darkness filtering:** Recommend only hours when the Sun is at least 18° below the horizon. Twilight is never treated as darkness.
- **Location ranking:** Compare candidates using a weighted score for cloud cover, precipitation, wind, humidity, and estimated sky darkness.
- **Local time display:** Show every time in the searched location's timezone, with correct dates and daylight saving time, wherever the visitor is.
- **Results visualization:** View the recommended coordinates, best-scoring hour, conditions table, hourly cloud-cover forecast, and embedded map, with a link to Google Earth.

## How it works

1. **Find the city.** The frontend converts a city name into latitude and longitude using Nominatim.
2. **Generate candidates.** The backend lays a square grid around the city and keeps only points within the search radius. Longitudes wrap across the date line, and points beyond a pole are dropped.
3. **Fetch forecasts.** Open-Meteo supplies hourly weather for all candidates in one batched request. Times are in each location's local timezone.
4. **Select dark hours.** For each candidate, the backend calculates the Sun's elevation at each upcoming hour and selects the next continuous run of astronomically dark hours.
5. **Score conditions.** Each dark hour receives a weather score.
6. **Recommend a location.** Candidates are ranked by their **average** score across their dark window. The best candidate is returned along with its highest-scoring hour.
7. **Display results.** The frontend renders the recommendation, weather details, hourly cloud cover, and map.

### Astronomical darkness

The sky is *astronomically dark* when the Sun's center is at least **18° below the horizon**. Between sunset and that point, the sky passes through civil (0° to −6°), nautical (−6° to −12°), and astronomical (−12° to −18°) twilight, and residual sunlight still washes out faint objects. In London in November, for example, the Sun sets around 16:20 but the sky isn't astronomically dark until about 18:15.

- **Solar elevation.** `solar.py` uses the NOAA solar-position equations, which are based on Meeus's *Astronomical Algorithms*, and works from each hour's absolute UTC instant. Compared with PyEphem across 20,000 random locations and times from 2020 to 2035, the results agreed within 0.02°. The calculation runs locally and is cached per instant, so a full search adds only a few milliseconds and no network calls.
- **Eligible hours.** Starting from the current time, the backend skips every hour where the Sun is above −18°, then takes the following continuous run of hours at or below −18°. Elevation is evaluated at each forecast timestamp (the top of the hour). Darkness determines eligibility only; it does not change the score.
- **No darkness available.** At high latitudes in summer, for example Oslo or Tromsø in June, the Sun never reaches −18°. In that case `/api/best-spot` returns HTTP 200 with `"darkness_available": false`, `"best_spot": null`, and a `message`, and the frontend displays that message. It never falls back to twilight hours.

### Scoring model

Each dark hour is scored with:

```text
score = 100
      - 0.6 × cloud_cover (%)
      - 8 × min(precipitation (mm), 10)
      - 0.3 × min(wind_speed (km/h), 40)
      - 0.2 × max(humidity (%) - 50, 0)
      - 5 × (estimated_bortle - 1)
```

Higher scores indicate more favorable conditions. The weights are project-defined heuristics, not a scientifically validated observability index. Hours with a missing (`null`) forecast value are left out rather than guessed.

The Bortle value comes from the nearest entry in a small built-in dataset of dark-sky locations. A candidate more than 500 km from every entry is assumed to be Bortle 6. This is a placeholder, **not** a reliable light-pollution measurement for arbitrary coordinates.

### Timezones

Times are always shown in the **searched location's** local time. Searching Tokyo from Texas shows Japan Standard Time and Tokyo's calendar date.

- Open-Meteo is called with `timezone=auto`, which resolves each coordinate to an IANA zone such as `America/Chicago`. The backend loads that zone with Python's `zoneinfo`; if the zone is missing or unknown, it falls back to Open-Meteo's fixed UTC offset.
- The current moment is compared with each forecast hour as an absolute UTC instant, so neither the server's nor the visitor's timezone affects the selection. This covers locations already on another calendar day, windows that cross midnight, and DST changes during the night. When clocks fall back, the repeated hour is kept as two distinct hours with different offsets.
- The frontend never passes offset-less timestamps to `new Date()`. It formats the local wall-clock fields directly and labels them with the abbreviation in effect for each hour, for example `Tue, Nov 10, 3:00 AM JST · Asia/Tokyo time`.

## Tech stack

| Layer | Technologies |
| --- | --- |
| Backend | Python, FastAPI, Requests, `zoneinfo` + `tzdata` |
| Frontend | Vanilla JavaScript, HTML, CSS, Canvas |
| Forecast data | Open-Meteo API |
| Geocoding | OpenStreetMap Nominatim |
| Maps | Google Maps embed, Google Earth link |
| Hosting | Vercel (FastAPI serves both the API and the static frontend) |

## Getting started

### Prerequisites

- Python 3.10 or newer
- Node.js 18 or newer (only for the frontend tests)
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

3. Install the dependencies. `requirements-dev.txt` adds the local server and test client to the production `requirements.txt`:

   ```bash
   python -m pip install -r requirements-dev.txt
   ```

4. Start the app from the repository root:

   ```bash
   uvicorn app:app --reload
   ```

5. Open **http://127.0.0.1:8000** and search for a city. Interactive API documentation is at **http://127.0.0.1:8000/docs**.

`tzdata` is a production dependency because Windows has no system timezone database for `zoneinfo`. On Linux, including Vercel, it is a harmless fallback.

## Development

| Command | Purpose |
| --- | --- |
| `uvicorn app:app --reload` | Run the app locally with auto-reload |
| `python -m unittest discover tests` | Backend tests: API validation and errors, grid, scoring, solar elevation, darkness, timezones |
| `node --test tests/time-format.test.js` | Frontend tests: time formatting in the location's timezone |

All tests use synthetic forecasts and mocked HTTP calls; they need no network access and don't depend on the current date.

## API endpoints

| Endpoint | Purpose | Parameters |
| --- | --- | --- |
| `GET /api/best-spot` | Rank nearby candidates and return the recommended spot and dark viewing window | `lat` (−90…90), `lon` (−180…180), optional `radius_km` (0 < r ≤ 100, default `12`) |
| `GET /api/weather` | Current weather and estimated Bortle value for one coordinate | `lat`, `lon` |
| `GET /api/spots` | Up to eight nearby entries from the built-in dark-sky dataset | `lat`, `lon`, optional `radius_km` (0 < r ≤ 20,000, default `1000`) |

Example: `http://127.0.0.1:8000/api/best-spot?lat=30.2672&lon=-97.7431`

**`/api/best-spot` response.** It contains `query_center`, `timezone` (IANA), `darkness_available`, `message` (`null` unless darkness is unavailable), `best_spot`, `candidates_checked`, and `radius_km`. `best_spot` holds the coordinates, `distance_km`, `timezone`, `bortle_scale`, `avg_night_score`, `best_hour`, and `night_forecast`. Each hour has these fields:

| Field | Example | Meaning |
| --- | --- | --- |
| `time` | `2026-11-09T21:00` | Local wall-clock time at the location |
| `time_iso` | `2026-11-09T21:00-06:00` | The same moment as ISO 8601 with its UTC offset |
| `tz_abbreviation` | `CST` | Timezone abbreviation in effect for that hour |
| `sun_elevation` | `-24.3` | Sun's elevation in degrees (always ≤ −18) |
| `cloud_cover`, `precipitation`, `wind_speed`, `humidity` | `10`, `0.0`, `5.0`, `60` | Forecast values (%, mm, km/h, %) |
| `score` | `65.5` | Hourly score from the formula above |

**Errors.**

| Status | Meaning |
| --- | --- |
| `422` | Invalid, missing, or out-of-range parameters |
| `502` | Open-Meteo is unreachable, returned an error, or returned malformed data |
| `504` | Open-Meteo timed out |

Error bodies have the form `{"detail": "..."}`, with a message that is safe to show users. Internal details are logged on the server, not returned. A location without astronomical darkness is a normal `200` response, not an error.

## Project structure

```text
Stargaze/
├── app.py                 # FastAPI app: routes, parameter validation, error responses, static files
├── weather.py             # Open-Meteo client: requests, error mapping, response validation, local times
├── scoring.py             # Dark-window selection and the weather-scoring formula
├── solar.py               # Solar elevation and the astronomical-darkness threshold
├── geo.py                 # Great-circle distance and the candidate grid
├── dark_sky.py            # Built-in Bortle dataset and nearby dark-sky spots
├── frontend/
│   ├── index.html         # Page markup
│   ├── styles.css         # Page styles
│   ├── app.js             # Search, API calls, and results rendering
│   ├── time-format.js     # Formats times in the searched location's timezone
│   └── starfield.js       # Decorative canvas starfield
├── tests/                 # unittest (backend) and node:test (frontend) suites
├── requirements.txt       # Production dependencies (installed by Vercel)
├── requirements-dev.txt   # Adds uvicorn and the test client for local development
└── README.md
```

## Limitations

- **Approximate light pollution:** The built-in Bortle estimates do not replace a geographic light-pollution dataset.
- **Site suitability:** The search evaluates coordinates, not verified public, reachable, or safe observation sites.
- **Moon and terrain:** The score ignores moon illumination, horizon obstructions, observer altitude, and seeing conditions. A bright Moon can wash out an astronomically dark sky.
- **Hourly resolution:** Darkness is checked on the hour. If darkness begins at 18:15, the first eligible hour is 19:00, and a dark period shorter than an hour may be missed.
- **Forecast horizon:** Forecasts cover today and tomorrow in local time. Late on the second day, the next dark window may be cut off. "No astronomical darkness" means none within this period.
- **Timezone of the winning spot:** Times use the recommended coordinate's timezone. Near a timezone border, this can differ from the searched city's timezone, and the label always names the zone actually used.
- **Timezone abbreviations:** Some zones have no common abbreviation and show a numeric offset such as `-03`. DST rules are only as current as the installed `tzdata`.
- **Map coverage:** The map shows the winning coordinate, not every evaluated candidate.

## Roadmap

- [ ] Replace placeholder Bortle estimates with geographically accurate light-pollution data, such as VIIRS-derived radiance.
- [ ] Include moon phase and illumination in the scoring model.
- [ ] Show evaluated candidates on an interactive map.
- [ ] Check location suitability (public access, terrain, horizon).

## Data sources

- [Open-Meteo](https://open-meteo.com/) — hourly and current weather forecasts.
- [OpenStreetMap / Nominatim](https://nominatim.org/) — city geocoding and reverse geocoding.
- [Google Maps](https://maps.google.com/) and [Google Earth](https://earth.google.com/) — location visualization.

Stargaze provides an estimated recommendation, not a guarantee of visibility or site access. Verify local conditions and access permissions before traveling to a suggested coordinate.
