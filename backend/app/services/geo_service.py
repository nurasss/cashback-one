"""Geocoding and 2GIS coordinate resolution service for business stores.

Supports:
1. 2GIS Organization/Firm URLs:
   - Official 2GIS Places API (if twogis_api_key configured).
   - Async HTML metadata parsing (og:image beautyshare center coordinates) without key.
2. 2GIS short share URLs (go.2gis.com/...) with safe async redirect resolution (strict domain whitelist).
3. Fallback to textual store address when link cannot resolve a definitive entity point.
4. Viewport center (?m=lon,lat) is NOT mistaken for store entity location.
5. Scoped address geocoding via 2GIS Geocoder API (if key configured) or OSM Nominatim (Kazakhstan scope).
6. SSRF protection, strict overall deadline (4.0s), response body streaming limit (128 KB), rate limiting (Nominatim <= 1 rps),
   and in-memory TTL caching.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import re
import socket
import time
import urllib.parse
from collections.abc import Callable
from typing import Any

import httpx

from app.core.config import Settings
from app.schemas.admin_content import (
    StoreCoordinateCandidate,
    StoreResolveCoordinatesResponse,
)

logger = logging.getLogger(__name__)

ALLOWED_2GIS_DOMAINS = frozenset({
    "go.2gis.com",
    "2gis.kz",
    "2gis.ru",
    "2gis.com",
    "2gis.uz",
    "2gis.by",
    "2gis.kg",
    "2gis.ae",
})

ALLOWED_2GIS_API_DOMAINS = frozenset({
    "catalog.api.2gis.com",
    "api.2gis.com",
})

ALLOWED_NOMINATIM_DOMAINS = frozenset({
    "nominatim.openstreetmap.org",
})

# Patterns for 2GIS entities and metadata
RE_2GIS_FIRM_ID = re.compile(
    r"/(?:firm|geo)/(\d{6,25})", re.IGNORECASE
)
RE_2GIS_POINTS_PARAM = re.compile(
    r"[?&]points=([0-9.]+)(?:%2C|,)([0-9.]+)", re.IGNORECASE
)
RE_2GIS_OG_IMAGE_CENTER = re.compile(
    r"beautyshare\.2gis\.ru/api/v1/image\?[^\"]*center=([0-9.]+)(?:%2C|,)([0-9.]+)",
    re.IGNORECASE,
)
RE_2GIS_OG_TITLE = re.compile(
    r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
RE_2GIS_IMAGE_DESC = re.compile(
    r"desc=([^&\"'<>]+)",
    re.IGNORECASE,
)

MAX_RESPONSE_BYTES = 128 * 1024  # 128 KB
HTTP_TIMEOUT = httpx.Timeout(4.0, connect=2.0)

# Nominatim rate limiter (policy: max 1 request per second)
_nominatim_lock = asyncio.Lock()
_last_nominatim_request_time: float = 0.0
_NOMINATIM_MIN_INTERVAL = 1.05  # seconds

# In-memory TTL cache (query -> (timestamp, response))
_cache_lock = asyncio.Lock()
_geocode_cache: dict[str, tuple[float, StoreResolveCoordinatesResponse]] = {}
_CACHE_TTL = 600.0  # 10 minutes
_CACHE_MAX_SIZE = 256


def is_safe_ip(ip_str: str) -> bool:
    """Validate that IP address is not private, loopback, or reserved."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return not (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        )
    except ValueError:
        return False


def is_safe_external_host_sync(hostname: str) -> bool:
    """Synchronous DNS resolution and IP safety check."""
    if not hostname:
        return False
    # If already a valid IP string
    try:
        ip = ipaddress.ip_address(hostname)
        return is_safe_ip(str(ip))
    except ValueError:
        pass

    try:
        addrinfo = socket.getaddrinfo(hostname, None)
        if not addrinfo:
            return False
        for _, _, _, _, sockaddr in addrinfo:
            ip_str = sockaddr[0]
            if not is_safe_ip(ip_str):
                return False
        return True
    except (socket.gaierror, ValueError, OSError):
        return False


async def is_safe_external_host(hostname: str) -> bool:
    """Non-blocking DNS check on worker thread."""
    return await asyncio.to_thread(is_safe_external_host_sync, hostname)


def is_allowed_2gis_host(hostname: str) -> bool:
    """Check if host belongs to allowed 2GIS web domain list."""
    if not hostname:
        return False
    h = hostname.lower()
    if h in ALLOWED_2GIS_DOMAINS:
        return True
    return any(h.endswith(f".{d}") for d in ALLOWED_2GIS_DOMAINS)


def is_allowed_2gis_api_host(hostname: str) -> bool:
    """Check if host belongs to allowed 2GIS API domain list."""
    if not hostname:
        return False
    h = hostname.lower()
    return h in ALLOWED_2GIS_API_DOMAINS or any(h.endswith(f".{d}") for d in ALLOWED_2GIS_API_DOMAINS)


def is_allowed_nominatim_host(hostname: str) -> bool:
    """Check if host belongs to allowed OSM Nominatim domain list."""
    if not hostname:
        return False
    return hostname.lower() in ALLOWED_NOMINATIM_DOMAINS


def normalize_coordinate_pair(val1: float, val2: float) -> tuple[float, float] | None:
    """Determine latitude and longitude from coordinate pair.

    In Kazakhstan:
    Latitude: ~40.0 .. 56.0 N.
    Longitude: ~46.0 .. 88.0 E.
    2GIS standard parameter order is: (lon, lat).
    """
    # Check 2GIS order (val1 = lon, val2 = lat)
    if -90.0 <= val2 <= 90.0 and -180.0 <= val1 <= 180.0:
        if 40.0 <= val2 <= 56.0 and 46.0 <= val1 <= 88.0:
            return round(val2, 6), round(val1, 6)
        if 40.0 <= val1 <= 56.0 and 46.0 <= val2 <= 88.0:
            return round(val1, 6), round(val2, 6)
        # Default fallback
        return round(val2, 6), round(val1, 6)

    # Check swapped order (val1 = lat, val2 = lon)
    if -90.0 <= val1 <= 90.0 and -180.0 <= val2 <= 180.0:
        return round(val1, 6), round(val2, 6)

    return None


async def safe_stream_request(
    url: str,
    *,
    allowed_host_checker: Callable[[str], bool],
    headers: dict[str, str] | None = None,
    method: str = "GET",
    max_redirects: int = 3,
    max_bytes: int = MAX_RESPONSE_BYTES,
    overall_timeout: float = 4.0,
    raise_on_overflow: bool = False,
) -> tuple[int, bytes, httpx.Headers, str]:
    """Execute an HTTP request with end-to-end safety guarantees.

    Guarantees:
    - Overall deadline enforced across all DNS queries, connects, redirects, and streaming.
    - HTTPS only (scheme must be 'https').
    - Every redirect destination is validated BEFORE following (HTTPS, allowed host, public IP).
    - Response body is streamed with strict byte limit (never buffer > max_bytes).
    - If raise_on_overflow is True and response exceeds max_bytes, raises ValueError.
    - SSRF protection: private/loopback/link-local/multicast/reserved IPs rejected.
    """
    current_url = url
    async with asyncio.timeout(overall_timeout):
        async with httpx.AsyncClient(
            follow_redirects=False,
            timeout=httpx.Timeout(overall_timeout, connect=2.0),
        ) as client:
            for redirect_idx in range(max_redirects + 1):
                parsed = urllib.parse.urlparse(current_url)
                if parsed.scheme.lower() != "https":
                    raise ValueError(
                        f"Запрещён небезопасный протокол '{parsed.scheme}'. Разрешён только HTTPS."
                    )

                hostname = (parsed.hostname or "").lower()
                if not hostname or not allowed_host_checker(hostname):
                    raise ValueError(f"Недопустимый домен '{hostname}'.")

                if not await is_safe_external_host(hostname):
                    raise ValueError(f"Хост '{hostname}' разрешается в недопустимый или приватный IP-адрес.")

                # Reject anti-bot / captcha challenge domains
                if "captcha" in hostname:
                    raise ValueError("Обнаружен домен проверки капчи. Автоматический обход запрещён.")

                req_method = method if redirect_idx == 0 else "GET"
                async with client.stream(req_method, current_url, headers=headers) as resp:
                    if resp.status_code in (301, 302, 303, 307, 308):
                        if redirect_idx >= max_redirects:
                            raise ValueError(f"Превышен лимит редиректов ({max_redirects}).")
                        loc = resp.headers.get("Location")
                        if not loc:
                            raise ValueError("Пустой заголовок Location при редиректе.")
                        current_url = urllib.parse.urljoin(current_url, loc)
                        continue

                    # Stream response body without adding exceeding portion
                    body_chunks: list[bytes] = []
                    total_bytes = 0
                    overflow = False

                    async for chunk in resp.aiter_bytes():
                        remaining = max_bytes - total_bytes
                        if remaining <= 0:
                            overflow = True
                            break
                        if len(chunk) > remaining:
                            overflow = True
                            body_chunks.append(chunk[:remaining])
                            total_bytes += remaining
                            break
                        body_chunks.append(chunk)
                        total_bytes += len(chunk)

                    if overflow and raise_on_overflow:
                        raise ValueError(f"Размер ответа превысил допустимый лимит {max_bytes} байт.")

                    return resp.status_code, b"".join(body_chunks), resp.headers, current_url

            raise ValueError("Превышено максимальное число редиректов.")


async def resolve_short_2gis_link(url: str, timeout: float = 4.0) -> str:
    """Follow redirects for 2GIS short URLs safely within the allowed domain whitelist."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme.lower() != "https":
        raise ValueError("Разрешены только HTTPS ссылки.")
    hostname = (parsed.hostname or "").lower()
    if not is_allowed_2gis_host(hostname):
        raise ValueError(
            f"Недопустимый домен '{hostname}'. Разрешены только ссылки 2ГИС (go.2gis.com, 2gis.kz)."
        )

    _status_code, _body, _headers, final_url = await safe_stream_request(
        url,
        allowed_host_checker=is_allowed_2gis_host,
        headers={"User-Agent": "CashbackOne-Admin/1.0 (Store Coordinate Resolver)"},
        max_redirects=3,
        max_bytes=1024,
        overall_timeout=timeout,
        raise_on_overflow=False,
    )
    return final_url


async def fetch_2gis_firm_point(url: str, timeout: float = 4.0) -> tuple[float, float, str] | None:
    """Fetch public HTML of 2GIS organization page and extract pin coordinates from metadata.

    Note: Coordinates from og:image metadata represent public preview coordinates.
    They must be confirmed by the store manager on the map before saving.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ru-RU,ru;q=0.9",
    }
    try:
        status_code, body, _headers, _final_url = await safe_stream_request(
            url,
            allowed_host_checker=is_allowed_2gis_host,
            headers=headers,
            max_redirects=3,
            max_bytes=MAX_RESPONSE_BYTES,
            overall_timeout=timeout,
            raise_on_overflow=False,
        )
        if status_code != 200:
            return None

        html = body.decode("utf-8", errors="ignore")

        # Match og:image beautyshare center parameter
        match = RE_2GIS_OG_IMAGE_CENTER.search(html)
        if match:
            lon_val = float(match.group(1))
            lat_val = float(match.group(2))
            coords = normalize_coordinate_pair(lon_val, lat_val)
            if coords:
                lat, lon = coords
                # Extract title and address
                title = ""
                title_m = RE_2GIS_OG_TITLE.search(html)
                if title_m:
                    raw_title = title_m.group(1)
                    title = raw_title.split(" — 2ГИС")[0].split(" на карте")[0].strip()

                desc = ""
                desc_m = RE_2GIS_IMAGE_DESC.search(html)
                if desc_m:
                    desc = urllib.parse.unquote(desc_m.group(1).replace("<br />", ", ")).strip()

                resolved_name = desc or title or "Точка организации 2ГИС (по данным превью)"
                return lat, lon, resolved_name

    except (httpx.HTTPError, TimeoutError, OSError, ValueError) as exc:
        logger.warning("Failed to fetch 2GIS firm page HTML for %s: %s", url, exc)

    return None


async def query_2gis_places_api(
    firm_id: str, api_key: str, timeout: float = 4.0
) -> tuple[float, float, str] | None:
    """Fetch point coordinates for a 2GIS firm ID using official Places API."""
    params = urllib.parse.urlencode({
        "id": firm_id,
        "fields": "items.point,items.name,items.address_name",
        "key": api_key,
    })
    url = f"https://catalog.api.2gis.com/3.0/items/byid?{params}"
    try:
        status_code, body, _headers, _final_url = await safe_stream_request(
            url,
            allowed_host_checker=is_allowed_2gis_api_host,
            headers={"User-Agent": "CashbackOne-Admin/1.0"},
            max_redirects=0,
            max_bytes=MAX_RESPONSE_BYTES,
            overall_timeout=timeout,
            raise_on_overflow=True,
        )
        if status_code == 200:
            data = json.loads(body.decode("utf-8"))
            items = data.get("result", {}).get("items", [])
            if items:
                item = items[0]
                pt = item.get("point")
                if pt and "lat" in pt and "lon" in pt:
                    name = item.get("name") or item.get("address_name") or f"2GIS ID {firm_id}"
                    return float(pt["lat"]), float(pt["lon"]), name
    except (httpx.HTTPError, TimeoutError, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        logger.warning("2GIS Places API query failed for firm %s: %s", firm_id, exc)
    return None


async def query_2gis_geocoder_api(
    query: str, api_key: str, timeout: float = 4.0
) -> list[dict[str, Any]]:
    """Geocode an address using official 2GIS Geocoder API."""
    params = urllib.parse.urlencode({
        "q": query,
        "fields": "items.point,items.full_name",
        "key": api_key,
    })
    url = f"https://catalog.api.2gis.com/3.0/items/geocode?{params}"
    try:
        status_code, body, _headers, _final_url = await safe_stream_request(
            url,
            allowed_host_checker=is_allowed_2gis_api_host,
            headers={"User-Agent": "CashbackOne-Admin/1.0"},
            max_redirects=0,
            max_bytes=MAX_RESPONSE_BYTES,
            overall_timeout=timeout,
            raise_on_overflow=True,
        )
        if status_code == 200:
            data = json.loads(body.decode("utf-8"))
            items = data.get("result", {}).get("items", [])
            results = []
            for it in items:
                pt = it.get("point")
                if pt and "lat" in pt and "lon" in pt:
                    results.append({
                        "display_name": it.get("full_name") or it.get("name") or query,
                        "lat": float(pt["lat"]),
                        "lon": float(pt["lon"]),
                    })
            return results
    except (httpx.HTTPError, TimeoutError, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        logger.warning("2GIS Geocoder API failed for '%s': %s", query, exc)
    return []


async def query_nominatim(query: str, timeout: float = 4.0) -> list[dict[str, Any]]:
    """Geocode an address using OpenStreetMap Nominatim scoped to Kazakhstan with rate limiting."""
    global _last_nominatim_request_time

    params = urllib.parse.urlencode({
        "q": query,
        "format": "json",
        "countrycodes": "kz",
        "addressdetails": "1",
        "limit": "5",
    })
    url = f"https://nominatim.openstreetmap.org/search?{params}"
    headers = {"User-Agent": "CashbackOneStoreGeocoder/1.0 (loyalty-admin@poscenter.kz)"}

    # Respect Nominatim rate limit: maximum 1 request per second
    async with _nominatim_lock:
        now = time.monotonic()
        elapsed = now - _last_nominatim_request_time
        if elapsed < _NOMINATIM_MIN_INTERVAL:
            await asyncio.sleep(_NOMINATIM_MIN_INTERVAL - elapsed)
        _last_nominatim_request_time = time.monotonic()

        try:
            status_code, body, _headers, _final_url = await safe_stream_request(
                url,
                allowed_host_checker=is_allowed_nominatim_host,
                headers=headers,
                max_redirects=2,
                max_bytes=MAX_RESPONSE_BYTES,
                overall_timeout=timeout,
                raise_on_overflow=True,
            )
            if status_code == 200:
                data = json.loads(body.decode("utf-8"))
                if isinstance(data, list):
                    return data
        except (httpx.HTTPError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
            logger.warning("Nominatim geocoding failed for query '%s': %s", query, exc)

    return []


def format_candidate_address(item: dict[str, Any], query: str) -> str:
    """Format an informative address string including city and street."""
    raw_display = item.get("display_name") or query
    addr = item.get("address", {})
    if isinstance(addr, dict):
        city = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("state")
        road = addr.get("road") or addr.get("street")
        house = addr.get("house_number")
        if city and road:
            suffix = f", {house}" if house else ""
            return f"{city}, {road}{suffix} ({raw_display})"
    return raw_display


async def _get_cached_response(cache_key: str) -> StoreResolveCoordinatesResponse | None:
    async with _cache_lock:
        if cache_key in _geocode_cache:
            ts, resp = _geocode_cache[cache_key]
            if time.time() - ts < _CACHE_TTL:
                return resp
            del _geocode_cache[cache_key]
    return None


async def _set_cached_response(cache_key: str, resp: StoreResolveCoordinatesResponse) -> None:
    async with _cache_lock:
        if len(_geocode_cache) >= _CACHE_MAX_SIZE:
            # Purge oldest entry
            oldest_key = min(_geocode_cache.keys(), key=lambda k: _geocode_cache[k][0])
            del _geocode_cache[oldest_key]
        _geocode_cache[cache_key] = (time.time(), resp)


async def geocode_text_address(
    clean_address: str, settings: Settings
) -> StoreResolveCoordinatesResponse:
    """Geocode a textual address via 2GIS Geocoder (if key available) or Nominatim."""
    twogis_key = getattr(settings, "twogis_api_key", None)
    if twogis_key:
        items = await query_2gis_geocoder_api(clean_address, twogis_key)
    else:
        items = await query_nominatim(clean_address)

    if not items:
        return StoreResolveCoordinatesResponse(
            status="not_found",
            message=(
                f"По адресу '{clean_address}' в Казахстане ничего не найдено. "
                "Уточните город и улицу или проверьте правильность написания."
            ),
        )

    if len(items) == 1:
        it = items[0]
        try:
            lat = round(float(it["lat"]), 6)
            lon = round(float(it["lon"]), 6)
            addr = format_candidate_address(it, clean_address)
            return StoreResolveCoordinatesResponse(
                status="found",
                latitude=lat,
                longitude=lon,
                resolved_address=addr,
                message="Адрес найден через геокодер. Проверьте положение точки на карте перед сохранением.",
            )
        except (ValueError, KeyError):
            pass

    # Multiple candidates -> ambiguous
    candidates: list[StoreCoordinateCandidate] = []
    for it in items[:5]:
        try:
            c_lat = round(float(it["lat"]), 6)
            c_lon = round(float(it["lon"]), 6)
            c_addr = format_candidate_address(it, clean_address)
            candidates.append(
                StoreCoordinateCandidate(
                    address=c_addr,
                    latitude=c_lat,
                    longitude=c_lon,
                )
            )
        except (ValueError, KeyError):
            continue

    if candidates:
        return StoreResolveCoordinatesResponse(
            status="ambiguous",
            message="Найдено несколько похожих адресов. Выберите подходящий вариант:",
            candidates=candidates,
        )

    return StoreResolveCoordinatesResponse(
        status="not_found",
        message="Не удалось разобрать координаты найденных объектов.",
    )


async def resolve_store_coordinates(
    query: str | None = None,
    url: str | None = None,
    address: str | None = None,
    settings: Settings = None,
) -> StoreResolveCoordinatesResponse:
    """Resolve coordinates from 2GIS URL or textual address with intelligent fallback.

    Rules:
    - If URL is an organization/firm card (/firm/<id>), resolves the exact entity location
      (via Places API or og:image metadata). Viewport center (?m=) is NEVER used as firm position.
    - If URL cannot be definitively resolved to a point, falls back to geocoding `address` if provided.
    - Textual addresses with multiple matches return `ambiguous` with candidate options.
    - Caches successful and ambiguous results in memory.
    """
    if settings is None:
        settings = Settings()

    # Determine candidate URL and candidate Address
    cand_url = (url or "").strip()
    cand_addr = (address or "").strip()

    raw_query = (query or "").strip()
    if raw_query:
        if raw_query.startswith(("http://", "https://", "go.2gis.com/", "2gis.")):
            if not cand_url:
                cand_url = raw_query
        else:
            if not cand_addr:
                cand_addr = raw_query

    if not cand_url and not cand_addr:
        return StoreResolveCoordinatesResponse(
            status="error",
            message="Поисковый запрос пуст. Введите адрес или вставьте ссылку 2ГИС.",
        )

    # Check in-memory cache
    cache_key = f"url:{cand_url}|addr:{cand_addr.lower()}"
    cached = await _get_cached_response(cache_key)
    if cached is not None:
        return cached

    # Step 1: If URL is provided, attempt 2GIS entity resolution
    if cand_url:
        full_url = cand_url
        if not full_url.startswith(("http://", "https://")):
            full_url = f"https://{full_url}"
        elif full_url.startswith("http://"):
            full_url = f"https://{full_url[7:]}"

        try:
            parsed = urllib.parse.urlparse(full_url)
            hostname = (parsed.hostname or "").lower()
            if not is_allowed_2gis_host(hostname):
                if cand_addr:
                    # Non-2GIS domain: fallback to geocoding address directly
                    resp = await geocode_text_address(cand_addr, settings)
                    await _set_cached_response(cache_key, resp)
                    return resp
                return StoreResolveCoordinatesResponse(
                    status="error",
                    message=(
                        f"Домен '{hostname}' не поддерживается. "
                        "Поддерживаются ссылки 2ГИС (go.2gis.com, 2gis.kz, 2gis.ru). "
                        "Для других сервисов укажите адрес текстом."
                    ),
                )
        except (ValueError, TypeError):
            if cand_addr:
                resp = await geocode_text_address(cand_addr, settings)
                await _set_cached_response(cache_key, resp)
                return resp
            return StoreResolveCoordinatesResponse(
                status="error",
                message="Некорректный формат URL-ссылки.",
            )

        # 1. Unshorten link if needed
        resolved_url = full_url
        if (parsed.hostname or "").lower() == "go.2gis.com":
            try:
                resolved_url = await resolve_short_2gis_link(full_url)
            except ValueError as val_err:
                if cand_addr:
                    resp = await geocode_text_address(cand_addr, settings)
                    await _set_cached_response(cache_key, resp)
                    return resp
                return StoreResolveCoordinatesResponse(
                    status="error",
                    message=str(val_err),
                )
            except (httpx.HTTPError, TimeoutError, OSError) as exc:
                logger.warning("Short link resolve failed: %s", exc)

        # 2. Check if firm ID or geo ID is in URL
        firm_match = RE_2GIS_FIRM_ID.search(resolved_url)
        if firm_match:
            firm_id = firm_match.group(1)
            twogis_key = getattr(settings, "twogis_api_key", None)
            if twogis_key:
                api_res = await query_2gis_places_api(firm_id, twogis_key)
                if api_res:
                    lat, lon, name = api_res
                    resp = StoreResolveCoordinatesResponse(
                        status="found",
                        latitude=lat,
                        longitude=lon,
                        resolved_address=name,
                        message="Точка определена через официальный Places API 2ГИС.",
                    )
                    await _set_cached_response(cache_key, resp)
                    return resp

            # If no API key or Places API empty: fetch firm page HTML to read server-rendered pin
            html_res = await fetch_2gis_firm_point(resolved_url)
            if html_res:
                lat, lon, name = html_res
                resp = StoreResolveCoordinatesResponse(
                    status="found",
                    latitude=lat,
                    longitude=lon,
                    resolved_address=name,
                    message=(
                        "Точка извлечена из публичных метаданных 2ГИС. "
                        "Пожалуйста, проверьте соответствие организации и положение на карте перед сохранением."
                    ),
                )
                await _set_cached_response(cache_key, resp)
                return resp

            # If 2GIS page could not yield point: fallback to address if present
            if cand_addr:
                resp = await geocode_text_address(cand_addr, settings)
                await _set_cached_response(cache_key, resp)
                return resp

            return StoreResolveCoordinatesResponse(
                status="not_found",
                message=(
                    f"Ссылка 2ГИС ведёт на организацию (ID: {firm_id}), "
                    "но не удалось получить точные координаты точки на карте. "
                    "Пожалуйста, введите адрес магазина текстом для точного поиска."
                ),
            )

        # 3. Check for explicit marker pin parameter (e.g. ?points=lon,lat)
        points_match = RE_2GIS_POINTS_PARAM.search(resolved_url)
        if points_match:
            try:
                p_lon = float(points_match.group(1))
                p_lat = float(points_match.group(2))
                coords = normalize_coordinate_pair(p_lon, p_lat)
                if coords:
                    lat, lon = coords
                    resp = StoreResolveCoordinatesResponse(
                        status="found",
                        latitude=lat,
                        longitude=lon,
                        resolved_address="Точка из метки 2ГИС",
                        message="Точка извлечена из параметров метки 2ГИС. Проверьте положение на карте.",
                    )
                    await _set_cached_response(cache_key, resp)
                    return resp
            except (ValueError, IndexError):
                pass

        # 4. Viewport center (?m=lon,lat) without firm entity is NOT store location.
        # Fall back to address if provided.
        if cand_addr:
            resp = await geocode_text_address(cand_addr, settings)
            await _set_cached_response(cache_key, resp)
            return resp

        return StoreResolveCoordinatesResponse(
            status="not_found",
            message=(
                "Указанная ссылка 2ГИС содержит только общий центр просмотра карты, а не конкретный магазин. "
                "Пожалуйста, введите адрес магазина в поле адреса или скопируйте ссылку на карточку организации."
            ),
        )

    # Step 2: Pure textual address geocoding
    resp = await geocode_text_address(cand_addr, settings)
    await _set_cached_response(cache_key, resp)
    return resp
