# Stargazing Spot Finder

Given a city, finds the best nearby spot and time tonight for stargazing by
combining live weather forecasts with a light-pollution estimate.

## What it does

Enter a city, and the backend checks a grid of nearby candidate points,
pulls tonight's weather forecast for all of them, and returns whichever one
has the best combination of clear skies, low wind, low humidity, and dark
enough conditions — along with the best hour to go out tonight.

## How it works

1. **Geocode** the city name to coordinates (Nominatim / OpenStreetMap).
2. **Generate candidates** — build a grid of points around that location out
   to a configurable radius.
3. **Score each candidate** — query Open-Meteo's hourly forecast for every
   candidate point in one batched request, isolate the next night-time
   window (skipping daylight hours), and score each hour with a weighted
   formula: cloud cover, precipitation, wind speed, humidity, and darkness.
4. **Estimate light pollution** — currently done via nearest-neighbor lookup
   against a small hardcoded list of well-known dark-sky locations
   worldwide, falling back to a flat "suburban sky" estimate anywhere far
   from one of them. This is a placeholder — see Roadmap.
5. **Return the best spot** — the candidate with the highest average
   night score, plus its full hour-by-hour forecast.
6. **Display it** — the frontend shows a conditions table, a map centered
   on the spot, and an hour-by-hour cloud cover strip for the night.

## Tech stack

- **Backend:** Python, FastAPI, `requests`
- **Frontend:** vanilla JavaScript, HTML/CSS
- **Data:** Open-Meteo (weather forecasts), Nominatim/OpenStreetMap
  (geocoding), Google Maps embed (map visualization, no API key required)

```bash
pip install fastapi uvicorn requests
uvicorn main:app --reload
```

Then open `http://localhost:8000` in a browser.

## Roadmap

- Replace the hardcoded dark-sky location list with real geographic
  light-pollution data (e.g. VIIRS satellite radiance), so darkness
  scoring is accurate anywhere, not just near famous sites.
- Add moon phase into the scoring formula.
- Swap the static map embed for an interactive map showing all candidate
  points, not just the winner.
- Deploy the backend so the frontend isn't tied to `localhost:8000`.
