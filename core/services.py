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
    payload = _safe_json_get(
        'https://api.open-meteo.com/v1/forecast',
        params={
            'latitude': lat,
            'longitude': lon,
            'current': 'temperature_2m,relative_humidity_2m,pressure_msl,wind_speed_10m',
            'timezone': 'auto',
        },
    )
    current = (payload or {}).get('current', {})
    return {
        'temperature': current.get('temperature_2m'),
        'humidity': current.get('relative_humidity_2m'),
        'pressure': current.get('pressure_msl'),
        'wind_speed': current.get('wind_speed_10m'),
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