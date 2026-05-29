const config = window.APP_CONFIG || {};

const map = L.map('map', {
  worldCopyJump: false,
  zoomControl: true,
  scrollWheelZoom: true,
  doubleClickZoom: true,
  minZoom: 2,
}).setView([10, 0], 2);

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19,
  attribution: '&copy; OpenStreetMap contributors',
  noWrap: true,
}).addTo(map);

map.zoomControl.setPosition('topright');
map.touchZoom.enable();

let marker = null;

const placeName = document.getElementById('place-name');
const placeCountry = document.getElementById('place-country');
const clickedPoint = document.getElementById('clicked-point');
const weatherTemp = document.getElementById('weather-temp');
const weatherHumidity = document.getElementById('weather-humidity');
const weatherPressure = document.getElementById('weather-pressure');
const weatherWind = document.getElementById('weather-wind');
const countryCapital = document.getElementById('country-capital');
const countryCurrency = document.getElementById('country-currency');
const countryLanguage = document.getElementById('country-language');
const countryPopulation = document.getElementById('country-population');
const countryFlag = document.getElementById('country-flag');
const countryRegion = document.getElementById('country-region');
const countryTimezone = document.getElementById('country-timezone');
const forecastList = document.getElementById('forecast-list');

function setWeather(weather) {
  const units = weather.units || {};
  const tempUnit = (units.temperature && units.temperature.symbol) || '°C';
  const humUnit = (units.humidity && units.humidity.symbol) || '%';
  const presUnit = (units.pressure && units.pressure.symbol) || 'hPa';
  const windUnit = (units.wind_speed && units.wind_speed.symbol) || 'm/s';

  const round = (v) => (typeof v === 'number' ? Math.round(v) : v ?? '--');
  weatherTemp.textContent = `${round(weather.temperature)} ${tempUnit}`;
  weatherHumidity.textContent = `${weather.humidity ?? '--'} ${humUnit}`;
  weatherPressure.textContent = `${weather.pressure ?? '--'} ${presUnit}`;
  weatherWind.textContent = `${weather.wind_speed ?? '--'} ${windUnit}`;

  forecastList.innerHTML = '';
  const items = (weather.forecast || []);
  items.forEach((day) => {
    const card = document.createElement('article');
    card.className = 'forecast-card';
    const date = new Date(`${day.date}T00:00:00`);

        const { icon, label } = mapWeatherCode(day.weather_code);
        const ftempUnit = (units.forecast_temp && units.forecast_temp.symbol) || tempUnit;
        
        // put human label in title for accessibility but do not render inline
        card.title = label || '';
        
        card.innerHTML = `
          <div class="fc-icon">${icon}</div>
          <div class="fc-body">
            <div class="fc-date"><strong>${date.toLocaleDateString('pt-BR', { weekday: 'short', day: '2-digit', month: 'short' })}</strong></div>
            <div class="fc-values">
              <div class="fc-temp">${round(day.high)}${ftempUnit} / ${round(day.low)}${ftempUnit}</div>
              <div class="fc-rain">Chuva: ${day.rain_probability ?? '--'}%</div>
            </div>
          </div>
        `;
    forecastList.appendChild(card);
  });
}

function mapWeatherCode(code) {
  // Simple mapping of Open-Meteo weather codes to emoji + label
  const map = {
    0: ['☀️', 'Céu limpo'],
    1: ['🌤️', 'Pouco nublado'],
    2: ['⛅', 'Parcialmente nublado'],
    3: ['☁️', 'Nublado'],
    45: ['🌫️', 'Nevoeiro'],
    48: ['🌫️', 'Nevoeiro gelado'],
    51: ['🌦️', 'Garoa leve'],
    53: ['🌦️', 'Garoa moderada'],
    55: ['🌧️', 'Garoa forte'],
    61: ['🌧️', 'Chuva fraca'],
    63: ['🌧️', 'Chuva'],
    65: ['🌧️', 'Chuva forte'],
    71: ['❄️', 'Neve fraca'],
    73: ['❄️', 'Neve'],
    75: ['❄️', 'Neve forte'],
    80: ['🌦️', 'Chuva (passeios)'],
    81: ['🌧️', 'Chuva (frequente)'],
    82: ['🌧️', 'Chuva intensa'],
    95: ['⛈️', 'Tempestade'],
    96: ['⛈️', 'Tempestade com granizo'],
    99: ['⛈️', 'Tempestade severa'],
  };
  const entry = map[code] || ['❓', 'Indeterminado'];
  return { icon: entry[0], label: entry[1] };
}

function formatNumber(value) {
  return value ? new Intl.NumberFormat('pt-BR').format(value) : '--';
}

function setCountry(country) {
  if (!country) return;
  countryCapital.textContent = country?.capital || '--';
  countryCurrency.textContent = (country?.currencies || []).join(', ') || '--';
  countryLanguage.textContent = (country?.languages || []).join(', ') || '--';
  countryPopulation.textContent = formatNumber(country?.population);
  countryRegion.textContent = [country?.region, country?.subregion].filter(Boolean).join(' • ') || '--';
  countryTimezone.textContent = (country?.timezones || []).join(', ') || '--';
  if (countryFlag) {
    countryFlag.src = country?.flag || '';
    countryFlag.alt = country?.name ? `Bandeira de ${country.name}` : 'Bandeira do país';
    countryFlag.style.display = country?.flag ? 'block' : 'none';
  }
}
// suggestions (datalist)
const suggestionsList = document.getElementById('place-suggestions');
let suggestionTimer = null;

function setSuggestions(items) {
  if (!suggestionsList) return;
  suggestionsList.innerHTML = '';
  (items || []).forEach((item) => {
    const option = document.createElement('option');
    option.value = item.display_name;
    suggestionsList.appendChild(option);
  });
}

async function loadSuggestions(query) {
  if (!config.suggestUrl) return;
  const url = new URL(config.suggestUrl, window.location.origin);
  url.searchParams.set('q', query);
  const response = await fetch(url, { headers: { Accept: 'application/json' } });
  if (!response.ok) return;
  const payload = await response.json();
  setSuggestions(payload.suggestions || []);
}

function updateMapPoint(lat, lon, label) {
  if (marker) {
    marker.remove();
  }
  marker = L.marker([lat, lon]).addTo(map).bindPopup(label).openPopup();
  map.flyTo([lat, lon], Math.max(map.getZoom(), 5), { duration: 0.9 });
}

function syncPlace(payload) {
  const location = payload.location;
  placeName.textContent = location.display_name || location.query || 'Lugar selecionado';
  placeCountry.textContent = location.country ? `País: ${location.country}` : '';
  clickedPoint.textContent = payload.clicked
    ? `Você clicou em: ${payload.clicked.lat.toFixed(5)}, ${payload.clicked.lon.toFixed(5)}`
    : `Coordenadas: ${location.lat.toFixed(5)}, ${location.lon.toFixed(5)}`;
  setWeather(payload.weather || {});
  setCountry(payload.country_profile || {});
  updateMapPoint(location.lat, location.lon, location.display_name || location.query);
}

async function fetchJson(url) {
  const response = await fetch(url, { headers: { 'Accept': 'application/json' } });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || 'Falha na requisição');
  }
  return payload;
}

async function loadPlace(query) {
  const url = new URL(config.searchUrl, window.location.origin);
  url.searchParams.set('q', query);
  const payload = await fetchJson(url);
  syncPlace(payload);
}

async function loadPoint(lat, lon) {
  const url = new URL(config.lookupUrl, window.location.origin);
  url.searchParams.set('lat', lat);
  url.searchParams.set('lon', lon);
  const payload = await fetchJson(url);
  syncPlace(payload);
}

document.getElementById('search-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const input = document.getElementById('place-search');
  if (!input.value.trim()) {
    return;
  }

  try {
    await loadPlace(input.value.trim());
  } catch (error) {
    placeName.textContent = 'Local não encontrado';
    clickedPoint.textContent = error.message;
  }
});

document.getElementById('place-search').addEventListener('input', () => {
  const value = document.getElementById('place-search').value.trim();
  if (suggestionTimer) {
    clearTimeout(suggestionTimer);
  }
  if (!value) {
    setSuggestions([]);
    return;
  }
  suggestionTimer = setTimeout(() => {
    loadSuggestions(value).catch(() => {});
  }, 300);
});

map.on('click', async (event) => {
  try {
    await loadPoint(event.latlng.lat, event.latlng.lng);
  } catch (error) {
    placeName.textContent = 'Ponto sem identificação';
    clickedPoint.textContent = error.message;
  }
});

loadPlace(config.initialPlace || 'Brasil').catch(() => {
  placeName.textContent = 'Use a busca para começar';
});