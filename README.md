# Stargazing Spot Finder

A tool for finding the best nearby spots for stargazing — scoring real-world
locations on sky darkness, weather, and moon phase so you know what's
actually worth the drive tonight.

## What it does

Given a region, the pipeline pulls candidate outdoor locations, checks how
dark the sky actually gets at each one, and layers in near-term conditions
(cloud cover, moon phase) to rank which spots are worth visiting on a given
night. The goal is finding good stargazing, full stop — camping is just one
reason someone might end up at one of these spots.

## How it works

The scoring pipeline has three logical steps:

1. **Find candidate locations** — query the Overpass API (OpenStreetMap) for
   outdoor points in a region (currently campsite tags, used as a reliable
   proxy for real, accessible locations), cached locally to avoid re-hitting
   the API.
2. **Score sky darkness** — sample VIIRS satellite radiance data at each
   site's coordinates and convert it into a Bortle-like darkness score. This
   is precomputed, since darkness barely changes day to day.
3. **Layer in live conditions** — pull hourly cloud cover for the 9pm–3am
   window from Open-Meteo, and compute moon phase locally. These run fresh
   per request, since they're time-sensitive.

A composite score combines all three into a ranked list of spots.

## Tech stack

- **Language:** Python
- **Data/science:** `numpy`, `h5py`, `rasterio`, `geopandas`, `cartopy`,
  `astropy`, `skyfield`
- **Frontend:** `streamlit`, `folium` (+ `streamlit-folium` for map embeds)
- **HTTP:** `requests`

```bash
pip install numpy h5py rasterio geopandas cartopy astropy skyfield streamlit folium streamlit-folium requests
```

> **Note:** `rasterio`, `geopandas`, and `cartopy` depend on GDAL/GEOS at the
> OS
