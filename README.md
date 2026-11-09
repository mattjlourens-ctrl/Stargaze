# Stargaze

**Find promising stargazing conditions near any city.**

Stargaze is a weather-aware web application that searches nearby coordinates and recommends a location and viewing time based on forecast conditions. It combines a Python/FastAPI backend with a lightweight JavaScript frontend to compare cloud cover, precipitation, wind, humidity, and an approximate measure of sky darkness.

**[Live demo](https://stargaze-ten.vercel.app)** · **[Source code](https://github.com/mattjlourens-ctrl/Stargaze)**

## Features

- **City search:** Look up a city using OpenStreetMap's Nominatim geocoding service.
- **Nearby location search:** Generate candidate coordinates within a configurable radius (12 km by default).
- **Nighttime weather analysis:** Retrieve hourly forecasts from Open-Meteo and evaluate the next available nighttime period.
- **Location ranking:** Compare candidate points using a weighted score for cloud cover, precipitation, wind, humidity, and estimated sky darkness.
- **Results visualization:** View the recommended coordinates, best-scoring hour, conditions table, nightly cloud-cover forecast, and embedded map, with a link to Google Earth.

## How it works

1. **Find the city.** The frontend converts a city name into latitude and longitude using Nominatim.
2. **Generate candidates.** The backend creates a grid of coordinates around the city, excluding points outside the search radius.
3. **Fetch forecasts.** Open-Meteo supplies hourly weather data for the candidate coordinates in a batched request.
4. **Select nighttime hours.** The backend uses the forecast's `is_day` field to select the next available continuous nighttime period.
5. **Score conditions.** Each nighttime hour receives a score based on the weather and an estimated Bortle-scale value.
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

The `/api/best-spot` response includes the search center, recommended location, distance from the city center, average nighttime score, best hour, hourly nighttime forecast, number of candidates evaluated, and search radius.

## Project structure

```text
Stargaze/
├── app.py                 # FastAPI routes, grid search, weather scoring
├── frontend/
│   ├── index.html         # Page layout and styles
│   ├── app.js              # Search and results rendering
│   └── starfield.js        # Decorative canvas starfield
├── requirements.txt       # Python application dependencies
├── .gitignore
└── README.md
```

## Current limitations

- **Approximate darkness data:** The built-in Bortle estimates do not replace a geographic light-pollution dataset.
- **Accessibility:** The search evaluates coordinate points, not verified public, reachable, or safe observation sites.
- **Weather-only simplification:** The score does not account for moon illumination, astronomical twilight, horizon obstructions, or seeing conditions.
- **Time display:** The frontend currently parses forecast timestamps in the browser; displayed times may need correction when the user's timezone differs from the searched location.
- **Map coverage:** The map displays the winning coordinate, not every evaluated candidate.

## Roadmap

- [ ] Replace placeholder Bortle estimates with geographically accurate light-pollution data, such as VIIRS-derived radiance data.
- [ ] Include moon phase and illumination in the scoring model.
- [ ] Correct timezone-aware display of recommended viewing times.
- [ ] Show candidate locations on an interactive map.
- [ ] Improve location suitability checks and error handling.
- [ ] Add automated tests for grid generation, scoring, nighttime selection, and API responses.

## Data sources

- [Open-Meteo](https://open-meteo.com/) — hourly and current weather forecasts.
- [OpenStreetMap / Nominatim](https://nominatim.org/) — city geocoding and reverse geocoding.
- [Google Maps](https://maps.google.com/) and [Google Earth](https://earth.google.com/) — location visualization.

Stargaze provides an estimated recommendation, not a guarantee of visibility or site access. Verify local conditions and access permissions before traveling to a suggested coordinate.