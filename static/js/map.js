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
const featuredImage = document.getElementById('featured-image');
const featuredCaption = document.getElementById('featured-caption');
const imageGrid = document.getElementById('image-grid');

function setWeather(weather) {
  weatherTemp.textContent = weather.temperature ?? '--';
  weatherHumidity.textContent = weather.humidity ?? '--';
  weatherPressure.textContent = weather.pressure ?? '--';
  weatherWind.textContent = weather.wind_speed ?? '--';
}

function setImages(images) {
  imageGrid.innerHTML = '';
  if (!images || !images.length) {
    featuredImage.removeAttribute('src');
    featuredCaption.textContent = 'Sem imagens encontradas para este local.';
    imageGrid.innerHTML = '<p class="muted">Sem imagens encontradas para este local.</p>';
    return;
  }

  const [primaryImage, ...restImages] = images;
  featuredImage.src = primaryImage.url;
  featuredImage.alt = primaryImage.title || 'Imagem principal do local';
  featuredCaption.textContent = primaryImage.title || 'Imagem principal';

  restImages.forEach((image) => {
    const figure = document.createElement('figure');
    const link = document.createElement('a');
    link.href = image.page_url || image.url;
    link.target = '_blank';
    link.rel = 'noreferrer';
    link.innerHTML = `<img src="${image.url}" alt="${image.title || 'Imagem do local'}">`;
    const caption = document.createElement('figcaption');
    caption.textContent = image.title || 'Imagem relacionada';
    figure.appendChild(link);
    figure.appendChild(caption);
    imageGrid.appendChild(figure);
  });
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
  setImages(payload.images || []);
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