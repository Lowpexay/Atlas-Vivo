from __future__ import annotations

import base64
import mimetypes
from functools import lru_cache
from urllib.parse import quote_plus

import requests

USER_AGENT = 'projeto-geografia/1.0 (contato-local)'
SCENIC_KEYWORDS = (
    'landscape', 'skyline', 'travel', 'tourism', 'nature', 'beach', 'mountain',
    'landmark', 'view', 'panorama', 'architecture', 'cityscape', 'scenery', 'photo',
)
REJECT_KEYWORDS = (
    'news', 'report', 'article', 'press', 'breaking', 'tweet', 'twitter', 'facebook',
    'instagram', 'blog', 'video', 'podcast', 'opinion', 'interview', 'daily', 'update',
)


def _safe_json_get(url: str, *, params: dict, headers: dict | None = None):
    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError):
        return None


def _nominatim_get(params: dict[str, str]):
    endpoint = 'https://nominatim.openstreetmap.org/search' if 'q' in params else 'https://nominatim.openstreetmap.org/reverse'
    return _safe_json_get(
        endpoint,
        params={**params, 'format': 'jsonv2', 'addressdetails': 1, 'limit': 1, 'accept-language': 'en'},
        headers={'User-Agent': USER_AGENT},
    )


def geocode_place(query: str) -> dict | None:
    results = _nominatim_get({'q': query})
    if not results:
        return None

    item = results[0]
    return {
        'query': query,
        'display_name': item.get('display_name', query),
        'country': item.get('address', {}).get('country') or item.get('display_name', query),
        'lat': float(item['lat']),
        'lon': float(item['lon']),
        'raw': item,
    }


def reverse_geocode(lat: str, lon: str) -> dict | None:
    data = _nominatim_get({'lat': lat, 'lon': lon})
    if not data:
        return None

    address = data.get('address', {})
    query = address.get('country') or data.get('display_name', f'{lat}, {lon}')
    return {
        'query': query,
        'display_name': data.get('display_name', query),
        'country': address.get('country') or query,
        'lat': float(data['lat']),
        'lon': float(data['lon']),
        'raw': data,
    }


def _unique_terms(terms: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered_terms: list[str] = []
    for term in terms:
        normalized = ' '.join(term.split()).strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered_terms.append(normalized)
    return ordered_terms


def _image_search_terms(location: dict) -> list[str]:
    raw = location.get('raw', {}) or {}
    address = raw.get('address', {}) or {}
    query = (location.get('query') or '').strip()
    display_name = (location.get('display_name') or query).strip()
    country = (address.get('country') or location.get('country') or '').strip()
    city = (
        address.get('city')
        or address.get('town')
        or address.get('village')
        or address.get('municipality')
        or address.get('county')
        or ''
    ).strip()
    region = (address.get('state') or address.get('region') or '').strip()
    country_level = bool(country) and not city and not region

    if country_level:
        return _unique_terms([
            f'{country} landscape',
            f'{country} travel',
            f'{country} tourism',
            f'{country} landmark',
            f'{country} view',
            display_name,
            query,
        ])

    return _unique_terms([
        f'{display_name} skyline',
        f'{display_name} landmark',
        f'{display_name} travel',
        f'{display_name} architecture',
        display_name,
        query,
        city,
        region,
        country,
        f'{country} travel' if country else '',
        f'{country} landscape' if country else '',
        f'{country} tourism' if country else '',
        f'{query} travel',
    ])


def _image_score(title: str, term: str) -> int:
    normalized_title = title.lower()
    normalized_term = term.lower()
    score = 0

    for keyword in SCENIC_KEYWORDS:
        if keyword in normalized_title:
            score += 4

    for keyword in REJECT_KEYWORDS:
        if keyword in normalized_title:
            score -= 12

    hashtag_count = normalized_title.count('#')
    mention_count = normalized_title.count('@')
    if hashtag_count >= 3:
        score -= 6
    if hashtag_count >= 6:
        score -= 8
    if mention_count >= 1:
        score -= 4

    if normalized_term and normalized_term in normalized_title:
        score += 3

    if any(word in normalized_title for word in ('photo', 'landscape', 'skyline', 'view', 'travel')):
        score += 3

    return score


def weather_for_location(lat: float, lon: float) -> dict:
    # Request current weather + daily forecast (7 days) from Open-Meteo
    payload = _safe_json_get(
        'https://api.open-meteo.com/v1/forecast',
        params={
            'latitude': lat,
            'longitude': lon,
            'timezone': 'auto',
            'current_weather': True,
            'daily': 'temperature_2m_max,temperature_2m_min,precipitation_probability_max,weathercode',
            'hourly': 'relativehumidity_2m,pressure_msl',
            'forecast_days': 7,
        },
    )

    current = (payload or {}).get('current_weather') or {}
    daily = (payload or {}).get('daily') or {}
    hourly = (payload or {}).get('hourly') or {}

    # try to pick humidity/pressure from hourly arrays at the current time
    humidity = None
    pressure = None
    try:
        current_time = current.get('time')
        times = hourly.get('time') or []
        if current_time and times:
            # match exact time index if present, otherwise fall back to nearest
            try:
                idx = times.index(current_time)
            except ValueError:
                # find nearest by absolute difference
                from datetime import datetime
                fmt = '%Y-%m-%dT%H:%M' if len(times[0]) == 16 else '%Y-%m-%dT%H:%M:%S'
                try:
                    ct = datetime.fromisoformat(current_time)
                    nearest = min(range(len(times)), key=lambda i: abs((datetime.fromisoformat(times[i]) - ct).total_seconds()))
                    idx = nearest
                except Exception:
                    idx = None
            if idx is not None:
                rh = hourly.get('relativehumidity_2m') or []
                prs = hourly.get('pressure_msl') or []
                if idx < len(rh):
                    humidity = rh[idx]
                if idx < len(prs):
                    pressure = prs[idx]
    except Exception:
        humidity = None
        pressure = None

    forecast = []
    times = daily.get('time') or []
    highs = daily.get('temperature_2m_max') or []
    lows = daily.get('temperature_2m_min') or []
    rain_probs = daily.get('precipitation_probability_max') or []
    codes = daily.get('weathercode') or []

    for i, dt in enumerate(times[:7]):
        forecast.append({
            'date': dt,
            'high': highs[i] if i < len(highs) else None,
            'low': lows[i] if i < len(lows) else None,
            'rain_probability': rain_probs[i] if i < len(rain_probs) else None,
            'weather_code': codes[i] if i < len(codes) else None,
        })

    # extract units from payload if available
    daily_units = (payload or {}).get('daily_units') or {}
    hourly_units = (payload or {}).get('hourly_units') or {}

    def _unit_name(sym: str | None) -> str:
        if not sym:
            return ''
        sym = sym.strip()
        names = {
            '°C': 'Celsius',
            '°F': 'Fahrenheit',
            '%': 'Percent',
            'hPa': 'hPa',
            'm/s': 'm/s',
        }
        return names.get(sym, sym)

    temp_sym = hourly_units.get('temperature_2m') or daily_units.get('temperature_2m_max') or '°C'
    hum_sym = hourly_units.get('relativehumidity_2m') or '%'
    pres_sym = hourly_units.get('pressure_msl') or 'hPa'
    wind_sym = hourly_units.get('windspeed_10m') or hourly_units.get('wind_speed_10m') or 'm/s'

    units = {
        'temperature': {'symbol': temp_sym, 'name': _unit_name(temp_sym)},
        'humidity': {'symbol': hum_sym, 'name': _unit_name(hum_sym)},
        'pressure': {'symbol': pres_sym, 'name': _unit_name(pres_sym)},
        'wind_speed': {'symbol': wind_sym, 'name': _unit_name(wind_sym)},
        'forecast_temp': {'symbol': daily_units.get('temperature_2m_max') or temp_sym, 'name': _unit_name(daily_units.get('temperature_2m_max') or temp_sym)},
    }

    return {
        'temperature': current.get('temperature'),
        'humidity': humidity,
        'pressure': pressure,
        'wind_speed': current.get('windspeed'),
        'units': units,
        'reference_time': current.get('time'),
        'forecast': forecast,
    }


def _unsplash_result(term: str, title: str | None = None) -> dict:
    slug = quote_plus(term)
    return {
        'title': title or term,
        'url': f'https://source.unsplash.com/featured/800x600/?{slug}',
        'page_url': f'https://unsplash.com/s/photos/{slug}',
    }


def _image_response_source(url: str) -> dict | None:
    try:
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        mime_type = response.headers.get('content-type', '').split(';', 1)[0].strip()
        if not mime_type:
            mime_type = mimetypes.guess_type(url)[0] or 'image/jpeg'
        encoded = base64.b64encode(response.content).decode('ascii')
        return {
            'src': f'data:{mime_type};base64,{encoded}',
            'mime_type': mime_type,
        }
    except requests.RequestException:
        return None


@lru_cache(maxsize=128)
def _materialize_image(url: str) -> dict | None:
    return _image_response_source(url)


def image_results(location: dict) -> list[dict]:
    terms = _image_search_terms(location)
    raw = location.get('raw', {}) or {}
    address = raw.get('address', {}) or {}
    city = (
        address.get('city')
        or address.get('town')
        or address.get('village')
        or address.get('municipality')
        or address.get('county')
        or ''
    ).strip()
    region = (address.get('state') or address.get('region') or '').strip()
    country = (address.get('country') or location.get('country') or '').strip()
    country_level = bool(country) and not city and not region

    candidates: list[dict] = []

    if not country_level:
        for term in terms:
            payload = _safe_json_get(
                'https://en.wikipedia.org/w/api.php',
                params={
                    'action': 'query',
                    'generator': 'search',
                    'gsrsearch': term,
                    'gsrlimit': 5,
                    'prop': 'pageimages|info',
                    'inprop': 'url',
                    'pithumbsize': 600,
                    'format': 'json',
                },
            )
            pages = (payload or {}).get('query', {}).get('pages', {})
            for page in pages.values():
                thumb = page.get('thumbnail', {})
                if not thumb.get('source'):
                    continue

                title = page.get('title') or term
                score = _image_score(title, term)
                if score < 0:
                    continue

                candidates.append({
                    'title': title,
                    'url': thumb['source'],
                    'page_url': page.get('fullurl'),
                    'score': score,
                })

                if len(candidates) >= 8:
                    break
            if len(candidates) >= 8:
                break

    for term in terms:
        payload = _safe_json_get(
            'https://api.openverse.org/v1/images/',
            params={
                'q': term,
                'license_type': 'all',
                'mature': 'false',
                'page_size': 20,
            },
        )
        for item in (payload or {}).get('results', []):
            thumbnail = item.get('thumbnail') or item.get('url')
            if not thumbnail:
                continue

            title = item.get('title') or term
            score = _image_score(title, term)
            source_url = (item.get('url') or '').lower()
            if any(domain in source_url for domain in ('unsplash.com', 'wikimedia.org', 'pexels.com', 'flickr.com')):
                score += 2
            if score < 0:
                continue

            candidates.append({
                'title': title,
                'url': thumbnail,
                'page_url': item.get('foreign_landing_url') or item.get('url'),
                'score': score,
            })

            if len(candidates) >= 16:
                break
        if len(candidates) >= 16:
            break

    candidates.sort(key=lambda item: item['score'], reverse=True)

    if not candidates:
        query_term = terms[0] if terms else location.get('query', '')
        fallback = _unsplash_result(query_term, location.get('display_name') or location.get('query', 'Lugar'))
        fallback['score'] = 0
        candidates.append(fallback)

    finalized: list[dict] = []
    for image in candidates[:4]:
        materialized = _materialize_image(image['url'])
        if materialized:
            finalized.append({
                'title': image.get('title'),
                'url': materialized['src'],
                'page_url': image.get('page_url'),
            })

    if not finalized:
        fallback = _unsplash_result(location.get('query', 'Lugar'), location.get('display_name') or location.get('query', 'Lugar'))
        materialized = _materialize_image(fallback['url'])
        if materialized:
            finalized.append({
                'title': fallback.get('title'),
                'url': materialized['src'],
                'page_url': fallback.get('page_url'),
            })

    return finalized[:4]


def place_suggestions(query: str, limit: int = 5) -> list[dict]:
    try:
        response = requests.get(
            'https://nominatim.openstreetmap.org/search',
            params={'q': query, 'format': 'jsonv2', 'addressdetails': 1, 'limit': limit, 'accept-language': 'pt'},
            headers={'User-Agent': USER_AGENT},
            timeout=10,
        )
        response.raise_for_status()
        items = response.json() or []
        results = []
        for item in items:
            results.append({
                'display_name': item.get('display_name'),
                'lat': float(item.get('lat')) if item.get('lat') else None,
                'lon': float(item.get('lon')) if item.get('lon') else None,
                'raw': item,
            })
        return results
    except requests.RequestException:
        return []


def country_profile_for_location(location: dict) -> dict | None:
    raw = (location.get('raw') or {})
    address = raw.get('address', {}) or {}
    country_code = (address.get('country_code') or '').upper()
    country_name = address.get('country') or location.get('country') or ''

    session = requests.Session()
    session.headers.update({'User-Agent': USER_AGENT})

    try:
        if country_code:
            url = f'https://restcountries.com/v3.1/alpha/{country_code}'
            resp = session.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json() or []
            item = data[0] if isinstance(data, list) and data else (data if isinstance(data, dict) else None)
        else:
            url = f'https://restcountries.com/v3.1/name/{quote_plus(country_name)}'
            resp = session.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json() or []
            item = data[0] if data else None

        if not item:
            return None

        # Parse currencies and languages
        currencies = []
        for code, cur in (item.get('currencies') or {}).items():
            name = cur.get('name')
            if name:
                currencies.append(name)

        languages = list((item.get('languages') or {}).values())

        flag = ''
        if item.get('flags'):
            flag = item['flags'].get('png') or item['flags'].get('svg') or ''

        return {
            'name': item.get('name', {}).get('common') or country_name,
            'official_name': item.get('name', {}).get('official') if item.get('name') else None,
            'capital': (item.get('capital') or [None])[0],
            'region': item.get('region'),
            'subregion': item.get('subregion'),
            'population': item.get('population'),
            'area': item.get('area'),
            'currencies': currencies,
            'languages': languages,
            'flag': flag,
            'map': (item.get('maps') or {}).get('googleMaps') or (item.get('maps') or {}).get('openStreetMaps'),
            'timezones': item.get('timezones') or [],
            'continents': item.get('continents') or [],
        }
    except requests.RequestException:
        return None