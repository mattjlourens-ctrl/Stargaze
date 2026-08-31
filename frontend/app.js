const API_BASE = 'http://localhost:8000';

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
    const spotName = await reverseGeocode(result.best_spot.lat, result.best_spot.lng);
    displayResults(geo.displayName, spotName, result);

  } catch (err) {
    message.textContent = 'Error fetching data. Make sure the backend is running.';
  } finally {
    searchBtn.disabled = false;
    searchBtn.textContent = 'Search';
  }
}

async function geocode(city) {
  const url = `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(city)}&format=json&limit=1`;
  const res = await fetch(url, { headers: { 'Accept-Language': 'en' } });
  const data = await res.json();
  if (!data.length) return null;
  return {
    lat: parseFloat(data[0].lat),
    lng: parseFloat(data[0].lon),
    displayName: data[0].display_name,
  };
}

async function fetchBestSpot(lat, lng) {
  const res = await fetch(`${API_BASE}/api/best-spot?lat=${lat}&lon=${lng}`);
  if (!res.ok) throw new Error('Best-spot fetch failed');
  return res.json();
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
  const weather = result.best_spot;

  document.getElementById('location-name').textContent = `Best spot near ${cityName}`;
  document.getElementById('spot-name').textContent = spotName;
  document.getElementById('spot-coords').textContent =
    `${weather.lat.toFixed(5)}, ${weather.lng.toFixed(5)} · ${weather.distance_km} km from city center · ` +
    `${result.candidates_checked} spots checked`;

  document.getElementById('map-frame').src = mapsEmbedUrl(weather.lat, weather.lng);
  document.getElementById('earth-link').href = googleEarthUrl(weather.lat, weather.lng);

  const best = weather.best_hour;
  const bestTime = best.time
    ? new Date(best.time).toLocaleString([], { weekday: 'short', hour: 'numeric', minute: '2-digit' })
    : '—';
  document.getElementById('timestamp').textContent = `Best time tonight: ${bestTime}`;

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
      value: `Bortle ${weather.bortle_scale}`,
      rating: weather.bortle_scale <= 3 ? 'good'
            : weather.bortle_scale <= 6  ? 'ok' : 'bad',
      text:   weather.bortle_scale <= 3 ? 'Dark sky'
            : weather.bortle_scale <= 6  ? 'Suburban' : 'Urban',
    },
  ];

  document.getElementById('conditions-body').innerHTML = rows.map(r => `
    <tr>
      <td>${r.label}</td>
      <td>${r.value}</td>
      <td class="${r.rating}">${r.text}</td>
    </tr>
  `).join('');

  renderNightForecast(weather.night_forecast);

  results.style.display = 'block';
}

function renderNightForecast(nightForecast) {
  document.getElementById('night-forecast').innerHTML = nightForecast.map(h => {
    const t = h.time ? new Date(h.time).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }) : '—';
    return `
      <div class="hour-card">
        <div class="hour-time">${t}</div>
        <div class="hour-cloud">${h.cloud_cover}%</div>
      </div>
    `;
  }).join('');
}