// Frontend and API are served by the same FastAPI app, so use same-origin relative URLs.
const API_BASE = '';

const NO_DARKNESS_MESSAGE =
  'No astronomical darkness is expected within the available forecast period for this location.';
const GENERIC_ERROR_MESSAGE = 'Something went wrong. Please try again.';

// An error whose message is written for the user and safe to display as-is.
class SearchError extends Error {}

const cityInput = document.getElementById('city-input');
const searchBtn = document.getElementById('search-btn');
const message   = document.getElementById('message');
const results   = document.getElementById('results');

searchBtn.addEventListener('click', handleSearch);
cityInput.addEventListener('keydown', e => { if (e.key === 'Enter') handleSearch(); });

async function handleSearch() {
  const city = cityInput.value.trim();
  if (!city) return;

  searchBtn.disabled = true;
  searchBtn.textContent = 'Searching…';
  message.textContent = '';
  results.style.display = 'none';

  try {
    const geo = await geocode(city);
    if (!geo) {
      message.textContent = 'City not found. Try a different name.';
      return;
    }

    const result = await fetchBestSpot(geo.lat, geo.lng);
    if (!result.best_spot) {
      // e.g. high-latitude summer: twilight all night, so there is no viewing time to recommend.
      message.textContent = result.message || NO_DARKNESS_MESSAGE;
      return;
    }
    const spotName = await reverseGeocode(result.best_spot.lat, result.best_spot.lng);
    displayResults(geo.displayName, spotName, result);

  } catch (err) {
    message.textContent = err instanceof SearchError ? err.message : GENERIC_ERROR_MESSAGE;
  } finally {
    searchBtn.disabled = false;
    searchBtn.textContent = 'Search';
  }
}

async function geocode(city) {
  const url = `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(city)}&format=json&limit=1`;
  let data;
  try {
    const res = await fetch(url, { headers: { 'Accept-Language': 'en' } });
    if (!res.ok) throw new Error(`Nominatim ${res.status}`);
    data = await res.json();
  } catch {
    throw new SearchError('Could not reach the city search service. Please try again shortly.');
  }
  if (!Array.isArray(data) || !data.length) return null;
  return {
    lat: parseFloat(data[0].lat),
    lng: parseFloat(data[0].lon),
    displayName: data[0].display_name,
  };
}

async function fetchBestSpot(lat, lng) {
  let res;
  try {
    res = await fetch(`${API_BASE}/api/best-spot?lat=${lat}&lon=${lng}`);
  } catch {
    throw new SearchError('Could not reach the Stargaze server. Check your connection and try again.');
  }
  if (!res.ok) throw new SearchError(await apiErrorMessage(res));
  return res.json();
}

// The API's `detail` is a user-facing string for weather-service errors (502/504);
// validation errors (422) carry a list instead, so fall back to a generic message.
async function apiErrorMessage(res) {
  try {
    const body = await res.json();
    if (typeof body.detail === 'string') return body.detail;
  } catch {
    // Non-JSON error body: use the fallback below.
  }
  return 'The forecast could not be loaded. Please try again shortly.';
}

function mapsEmbedUrl(lat, lng) {
  // Keyless Google Maps embed, satellite tiles (t=k), pinned at the exact coordinate.
  return `https://maps.google.com/maps?q=${lat},${lng}&z=16&t=k&output=embed`;
}

function googleEarthUrl(lat, lng) {
  // Deep link into Google Earth Web, dropping a pin at the exact coordinate.
  const latStr = lat.toFixed(6);
  const lngStr = lng.toFixed(6);
  return `https://earth.google.com/web/search/${latStr},${lngStr}/@${latStr},${lngStr},0a,1000d,35y,0h,0t,0r`;
}

async function reverseGeocode(lat, lng) {
  try {
    const url = `https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lng}&format=json&zoom=14`;
    const res = await fetch(url, { headers: { 'Accept-Language': 'en' } });
    const data = await res.json();
    return data.display_name || `${lat.toFixed(4)}, ${lng.toFixed(4)}`;
  } catch {
    return `${lat.toFixed(4)}, ${lng.toFixed(4)}`;
  }
}

function displayResults(cityName, spotName, result) {
  const spot = result.best_spot;

  document.getElementById('location-name').textContent = `Best spot near ${cityName}`;
  document.getElementById('spot-name').textContent = spotName;
  document.getElementById('spot-coords').textContent =
    `${spot.lat.toFixed(5)}, ${spot.lng.toFixed(5)} · ${spot.distance_km} km from city center · ` +
    `${result.candidates_checked} spots checked`;

  document.getElementById('map-frame').src = mapsEmbedUrl(spot.lat, spot.lng);
  document.getElementById('earth-link').href = googleEarthUrl(spot.lat, spot.lng);

  const best = spot.best_hour;
  const tzName = result.timezone || spot.timezone;
  const tzSuffix = tzName ? ` · ${tzName} time` : '';
  document.getElementById('timestamp').textContent =
    `Best viewing time: ${formatViewingTime(best, [])}${tzSuffix}`;

  const rows = [
    {
      label: 'Cloud Cover',
      value: `${best.cloud_cover}%`,
      rating: best.cloud_cover <= 20 ? 'good'
            : best.cloud_cover <= 60 ? 'ok' : 'bad',
      text:   best.cloud_cover <= 20 ? 'Clear'
            : best.cloud_cover <= 60 ? 'Partly cloudy' : 'Overcast',
    },
    {
      label: 'Precipitation',
      value: `${best.precipitation} mm`,
      rating: best.precipitation === 0 ? 'good'
            : best.precipitation < 1    ? 'ok' : 'bad',
      text:   best.precipitation === 0 ? 'None'
            : best.precipitation < 1    ? 'Light' : 'Heavy',
    },
    {
      label: 'Wind Speed',
      value: `${best.wind_speed} km/h`,
      rating: best.wind_speed < 20 ? 'good'
            : best.wind_speed < 40  ? 'ok' : 'bad',
      text:   best.wind_speed < 20 ? 'Calm'
            : best.wind_speed < 40  ? 'Moderate' : 'Strong',
    },
    {
      label: 'Humidity',
      value: `${best.humidity}%`,
      rating: best.humidity < 60 ? 'good'
            : best.humidity < 80  ? 'ok' : 'bad',
      text:   best.humidity < 60 ? 'Low'
            : best.humidity < 80  ? 'Moderate' : 'High',
    },
    {
      label: 'Light Pollution',
      value: `Bortle ${spot.bortle_scale}`,
      rating: spot.bortle_scale <= 3 ? 'good'
            : spot.bortle_scale <= 6  ? 'ok' : 'bad',
      text:   spot.bortle_scale <= 3 ? 'Dark sky'
            : spot.bortle_scale <= 6  ? 'Suburban' : 'Urban',
    },
  ];

  document.getElementById('conditions-body').innerHTML = rows.map(r => `
    <tr>
      <td>${r.label}</td>
      <td>${r.value}</td>
      <td class="${r.rating}">${r.text}</td>
    </tr>
  `).join('');

  renderNightForecast(spot.night_forecast, tzName);

  results.style.display = 'block';
}

function renderNightForecast(nightForecast, tzName) {
  const firstAbbr = nightForecast.length ? nightForecast[0].tz_abbreviation : '';
  const tzLabel = [firstAbbr, tzName].filter(Boolean).join(', ');
  document.querySelector('.night-forecast-title').textContent =
    `Astronomically dark hours at this spot (Sun 18°+ below horizon)${tzLabel ? ` · ${tzLabel}` : ''}`;

  let prevAbbr = firstAbbr;
  document.getElementById('night-forecast').innerHTML = nightForecast.map(h => {
    // Label an hour only when the offset changes mid-night (a DST transition).
    const abbrChanged = h.tz_abbreviation && h.tz_abbreviation !== prevAbbr;
    prevAbbr = h.tz_abbreviation || prevAbbr;
    const t = formatHourTime(h, []) + (abbrChanged ? ` ${h.tz_abbreviation}` : '');
    return `
      <div class="hour-card">
        <div class="hour-time">${t}</div>
        <div class="hour-cloud">${h.cloud_cover}%</div>
      </div>
    `;
  }).join('');
}