"""Unit and integration tests for geo_service and store coordinate resolution."""

import asyncio
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from httpx import AsyncClient

from app.core.config import Settings
from app.services.geo_service import (
    MAX_RESPONSE_BYTES,
    _geocode_cache,
    fetch_2gis_firm_point,
    is_allowed_2gis_api_host,
    is_allowed_2gis_host,
    is_allowed_nominatim_host,
    is_safe_external_host,
    is_safe_ip,
    normalize_coordinate_pair,
    query_2gis_geocoder_api,
    query_2gis_places_api,
    query_nominatim,
    resolve_store_coordinates,
    safe_stream_request,
)


def test_normalize_coordinate_pair():
    # 2GIS standard: lon=76.889709, lat=43.238949
    res = normalize_coordinate_pair(76.889709, 43.238949)
    assert res == (43.238949, 76.889709)

    # Inverted order
    res_inv = normalize_coordinate_pair(43.238949, 76.889709)
    assert res_inv == (43.238949, 76.889709)

    # Out of range
    assert normalize_coordinate_pair(100.0, 200.0) is None
    assert normalize_coordinate_pair(-200.0, 50.0) is None
    assert normalize_coordinate_pair(95.0, 95.0) is None


def test_is_safe_ip():
    assert is_safe_ip("127.0.0.1") is False
    assert is_safe_ip("10.0.0.1") is False
    assert is_safe_ip("192.168.1.1") is False
    assert is_safe_ip("169.254.169.254") is False
    assert is_safe_ip("::1") is False
    assert is_safe_ip("8.8.8.8") is True


@pytest.mark.asyncio
async def test_is_safe_external_host():
    assert await is_safe_external_host("127.0.0.1") is False
    assert await is_safe_external_host("localhost") is False
    assert await is_safe_external_host("2gis.kz") is True


def test_is_allowed_2gis_host():
    assert is_allowed_2gis_host("2gis.kz") is True
    assert is_allowed_2gis_host("go.2gis.com") is True
    assert is_allowed_2gis_host("sub.2gis.ru") is True
    assert is_allowed_2gis_host("google.com") is False
    assert is_allowed_2gis_host("evil-2gis.com.attacker.com") is False


@pytest.mark.asyncio
async def test_resolve_2gis_firm_via_html_metadata():
    settings = Settings(admin_jwt_signing_key="a" * 32)
    _geocode_cache.clear()

    # Mock fetch_2gis_firm_point returning parsed og:image coordinates for firm
    with patch(
        "app.services.geo_service.fetch_2gis_firm_point",
        new_callable=AsyncMock,
        return_value=(51.1512, 71.457674, "КеремЕт, супермаркет"),
    ):
        res = await resolve_store_coordinates(
            url="https://2gis.kz/astana/firm/70000001103172202?m=70.0%2C50.0%2F16",
            settings=settings,
        )
        assert res.status == "found"
        assert res.latitude == 51.1512
        assert res.longitude == 71.457674
        assert "КеремЕт" in (res.resolved_address or "")


@pytest.mark.asyncio
async def test_resolve_fallback_to_address_when_url_fails():
    settings = Settings(admin_jwt_signing_key="a" * 32)
    _geocode_cache.clear()

    # Firm page cannot be resolved, but address is provided
    with patch("app.services.geo_service.fetch_2gis_firm_point", new_callable=AsyncMock, return_value=None):
        mock_nominatim = [
            {
                "display_name": "проспект Тауелсиздик, 4, Астана",
                "lat": "51.151037",
                "lon": "71.457883",
                "address": {"city": "Астана", "road": "проспект Тауелсиздик", "house_number": "4"},
            }
        ]
        with patch("app.services.geo_service.query_nominatim", new_callable=AsyncMock, return_value=mock_nominatim):
            res = await resolve_store_coordinates(
                url="https://2gis.kz/astana/firm/99999999999",
                address="Астана, проспект Тауелсиздик, 4",
                settings=settings,
            )
            assert res.status == "found"
            assert res.latitude == 51.151037
            assert res.longitude == 71.457883
            assert "Тауелсиздик" in (res.resolved_address or "")


@pytest.mark.asyncio
async def test_viewport_center_not_mistaken_for_store_location():
    settings = Settings(admin_jwt_signing_key="a" * 32)
    _geocode_cache.clear()

    # Viewport center without firm and without address -> returns informative error
    res = await resolve_store_coordinates(
        url="https://2gis.kz/almaty?m=76.889709%2C43.238949%2F16",
        settings=settings,
    )
    assert res.status == "not_found"
    assert "центр просмотра карты" in (res.message or "")


@pytest.mark.asyncio
async def test_resolve_2gis_url_forbidden_domain_with_fallback():
    settings = Settings(admin_jwt_signing_key="a" * 32)
    _geocode_cache.clear()

    # With fallback address
    mock_nom = [
        {
            "display_name": "ул. Достык, 1, Астана",
            "lat": "51.130000",
            "lon": "71.420000",
        }
    ]
    with patch("app.services.geo_service.query_nominatim", new_callable=AsyncMock, return_value=mock_nom):
        res = await resolve_store_coordinates(
            url="https://evil-site.com/firm/123",
            address="ул. Достык, 1",
            settings=settings,
        )
        assert res.status == "found"
        assert res.latitude == 51.130000

    # Without address
    _geocode_cache.clear()
    res_err = await resolve_store_coordinates(
        url="https://evil-site.com/firm/123",
        settings=settings,
    )
    assert res_err.status == "error"
    assert "evil-site.com" in (res_err.message or "")


@pytest.mark.asyncio
async def test_resolve_2gis_short_link_success():
    settings = Settings(admin_jwt_signing_key="a" * 32)
    _geocode_cache.clear()

    with (
        patch(
            "app.services.geo_service.resolve_short_2gis_link",
            new_callable=AsyncMock,
            return_value="https://2gis.kz/almaty/firm/70000001018042456",
        ),
        patch(
            "app.services.geo_service.fetch_2gis_firm_point",
            new_callable=AsyncMock,
            return_value=(43.238949, 76.889709, "Магазин 2ГИС"),
        ),
    ):
        res = await resolve_store_coordinates("https://go.2gis.com/somerandomcode", settings=settings)
        assert res.status == "found"
        assert res.latitude == 43.238949
        assert res.longitude == 76.889709


@pytest.mark.asyncio
async def test_resolve_address_ambiguous():
    settings = Settings(admin_jwt_signing_key="a" * 32)
    _geocode_cache.clear()

    mock_results = [
        {
            "display_name": "10, Абай даңғылы, Алмалы ауданы, Алматы",
            "lat": "43.240123",
            "lon": "76.920456",
            "address": {"city": "Алматы", "road": "Абай даңғылы", "house_number": "10"},
        },
        {
            "display_name": "10, Абай көшесі, Есіл ауданы, Астана",
            "lat": "51.150123",
            "lon": "71.430456",
            "address": {"city": "Астана", "road": "Абай көшесі", "house_number": "10"},
        },
    ]

    with patch("app.services.geo_service.query_nominatim", new_callable=AsyncMock, return_value=mock_results):
        res = await resolve_store_coordinates("Абая 10", settings=settings)
        assert res.status == "ambiguous"
        assert len(res.candidates) == 2
        assert res.candidates[0].latitude == 43.240123
        assert res.candidates[0].longitude == 76.920456
        assert "Алматы" in res.candidates[0].address
        assert res.candidates[1].latitude == 51.150123
        assert "Астана" in res.candidates[1].address


@pytest.mark.asyncio
async def test_resolve_address_caching():
    settings = Settings(admin_jwt_signing_key="a" * 32)
    _geocode_cache.clear()

    mock_result = [
        {
            "display_name": "42, Достық даңғылы, Медеу ауданы, Алматы",
            "lat": "43.251062",
            "lon": "76.956437",
        }
    ]

    nom_mock = AsyncMock(return_value=mock_result)
    with patch("app.services.geo_service.query_nominatim", nom_mock):
        res1 = await resolve_store_coordinates("Алматы, Достык 42", settings=settings)
        assert res1.status == "found"
        assert nom_mock.call_count == 1

        # Second call must hit in-memory cache and NOT call query_nominatim again
        res2 = await resolve_store_coordinates("Алматы, Достык 42", settings=settings)
        assert res2.status == "found"
        assert nom_mock.call_count == 1


from tests.test_admin_mutations import (
    auth_headers,
    make_admin,
    make_business,
    mutation_client,  # noqa: F401
)
from tests.test_customer_app import business_with_card, customer


@pytest.mark.asyncio
async def test_admin_resolve_coordinates_endpoint_authorized(
    db_session, mutation_client: AsyncClient,  # noqa: F811
):
    biz = await make_business(db_session, "Geo Test Biz")
    manager = await make_admin(db_session, "business_manager", biz.id, "geo-manager")
    headers = await auth_headers(db_session, manager)
    await db_session.commit()

    with patch(
        "app.services.geo_service.query_nominatim",
        new_callable=AsyncMock,
        return_value=[
            {
                "display_name": "Астана, Достык 5",
                "lat": "51.13245",
                "lon": "71.46821",
            }
        ],
    ):
        resp = await mutation_client.post(
            f"/admin/businesses/{biz.id}/stores/resolve-coordinates",
            json={"query": "Астана, Достык 5"},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "found"
        assert data["latitude"] == 51.13245
        assert data["longitude"] == 71.46821


@pytest.mark.asyncio
async def test_store_resolve_save_and_app_content_etag_chain(
    db_session,
    client: AsyncClient,
    mutation_client: AsyncClient,  # noqa: F811
):
    cust_user, cust_auth = await customer(db_session, "+77015550101")
    biz, _card = await business_with_card(db_session, cust_user, "Shop")
    manager = await make_admin(db_session, "business_manager", biz.id, "geo-chain-manager")
    mgr_headers = await auth_headers(db_session, manager)
    await db_session.commit()

    # 1. Resolve coordinates via API
    with patch(
        "app.services.geo_service.fetch_2gis_firm_point",
        new_callable=AsyncMock,
        return_value=(43.238949, 76.889709, "Супермаркет КеремЕт"),
    ):
        resolve_resp = await mutation_client.post(
            f"/admin/businesses/{biz.id}/stores/resolve-coordinates",
            json={"url": "https://2gis.kz/almaty/firm/70000001018042456"},
            headers=mgr_headers,
        )
        assert resolve_resp.status_code == 200
        res_data = resolve_resp.json()
        assert res_data["status"] == "found"
        assert res_data["latitude"] == 43.238949
        assert res_data["longitude"] == 76.889709

    # 2. Create store using resolved coordinates
    store_create_resp = await mutation_client.post(
        f"/admin/businesses/{biz.id}/stores",
        json={
            "title_ru": "Супермаркет КеремЕт",
            "title_kk": "КеремЕт супермаркеті",
            "address_ru": "ул. Достык, 5",
            "address_kk": "Достық к-сі, 5",
            "map_url": "https://2gis.kz/almaty/firm/70000001018042456",
            "latitude": res_data["latitude"],
            "longitude": res_data["longitude"],
            "is_active": True,
        },
        headers=mgr_headers,
    )
    assert store_create_resp.status_code == 201
    store_obj = store_create_resp.json()
    store_id = store_obj["id"]

    # 3. Customer requests /me/app-content and verifies coordinates & initial ETag
    content1 = await client.get(f"/me/app-content?business_id={biz.id}", headers=cust_auth)
    assert content1.status_code == 200
    etag1 = content1.headers.get("ETag")
    assert etag1 is not None
    data1 = content1.json()
    assert len(data1["stores"]) == 1
    assert data1["stores"][0]["latitude"] == 43.238949
    assert data1["stores"][0]["longitude"] == 76.889709

    # 4. If-None-Match with etag1 returns 304 Not Modified
    content304 = await client.get(
        f"/me/app-content?business_id={biz.id}",
        headers={**cust_auth, "If-None-Match": etag1},
    )
    assert content304.status_code == 304

    # 5. Manager updates store coordinates
    store_patch_resp = await mutation_client.patch(
        f"/admin/businesses/{biz.id}/stores/{store_id}",
        json={
            "latitude": 51.13245,
            "longitude": 71.46821,
        },
        headers=mgr_headers,
    )
    assert store_patch_resp.status_code == 200

    # 6. Customer requests /me/app-content and verifies updated coordinates and new ETag
    content2 = await client.get(f"/me/app-content?business_id={biz.id}", headers=cust_auth)
    assert content2.status_code == 200
    etag2 = content2.headers.get("ETag")
    assert etag2 is not None
    assert etag2 != etag1, "ETag must change after store coordinates are modified"
    data2 = content2.json()
    assert data2["stores"][0]["latitude"] == 51.13245
    assert data2["stores"][0]["longitude"] == 71.46821


class MockStreamResponse:
    def __init__(
        self,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
        chunks: list[bytes] | None = None,
        delay: float = 0.0,
    ):
        self.status_code = status_code
        self.headers = httpx.Headers(headers or {})
        self.chunks = chunks or []
        self.delay = delay

    async def aiter_bytes(self):
        if self.delay > 0:
            await asyncio.sleep(self.delay)
        for chunk in self.chunks:
            yield chunk

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class MockAsyncClient:
    def __init__(self, responses: list[MockStreamResponse] | None = None, default_resp: MockStreamResponse | None = None):
        self.responses = list(responses or [])
        self.default_resp = default_resp or MockStreamResponse(200, chunks=[b"ok"])
        self.requested_urls: list[str] = []

    def stream(self, method: str, url: str, headers: dict | None = None):
        self.requested_urls.append(url)
        if self.responses:
            return self.responses.pop(0)
        return self.default_resp

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.mark.asyncio
async def test_safe_stream_redirect_validations():
    # 1. Reject non-HTTPS redirect (http://)
    client_http = MockAsyncClient([
        MockStreamResponse(302, headers={"Location": "http://2gis.kz/insecure"}),
    ])
    with patch("app.services.geo_service.httpx.AsyncClient", return_value=client_http), pytest.raises(
        ValueError, match="Разрешён только HTTPS"
    ):
        await safe_stream_request(
            "https://go.2gis.com/short1",
            allowed_host_checker=is_allowed_2gis_host,
        )

    # 2. Reject redirect to disallowed domain (evil.com)
    client_domain = MockAsyncClient([
        MockStreamResponse(302, headers={"Location": "https://evil-site.com/steal"}),
    ])
    with patch("app.services.geo_service.httpx.AsyncClient", return_value=client_domain), pytest.raises(
        ValueError, match="Недопустимый домен 'evil-site.com'"
    ):
        await safe_stream_request(
            "https://go.2gis.com/short2",
            allowed_host_checker=is_allowed_2gis_host,
        )

    # 3. Reject redirect resolving to private IP (SSRF protection / DNS rebinding)
    client_ip = MockAsyncClient([
        MockStreamResponse(302, headers={"Location": "https://2gis.kz/admin"}),
    ])
    with (
        patch("app.services.geo_service.httpx.AsyncClient", return_value=client_ip),
        patch("app.services.geo_service.is_safe_external_host", new_callable=AsyncMock, return_value=False),
        pytest.raises(ValueError, match="приватный IP-адрес"),
    ):
        await safe_stream_request(
            "https://go.2gis.com/short3",
            allowed_host_checker=is_allowed_2gis_host,
        )

    # 4. Reject redirect to captcha domain
    client_captcha = MockAsyncClient([
        MockStreamResponse(302, headers={"Location": "https://captcha.2gis.ru/form?return_url=xyz"}),
    ])
    with patch("app.services.geo_service.httpx.AsyncClient", return_value=client_captcha), pytest.raises(
        ValueError, match="Обнаружен домен проверки капчи"
    ):
        await safe_stream_request(
            "https://go.2gis.com/short4",
            allowed_host_checker=is_allowed_2gis_host,
        )

    # 5. Reject redirect loop / exceeding max redirects
    client_loop = MockAsyncClient([
        MockStreamResponse(302, headers={"Location": "https://go.2gis.com/r1"}),
        MockStreamResponse(302, headers={"Location": "https://go.2gis.com/r2"}),
        MockStreamResponse(302, headers={"Location": "https://go.2gis.com/r3"}),
        MockStreamResponse(302, headers={"Location": "https://go.2gis.com/r4"}),
    ])
    with patch("app.services.geo_service.httpx.AsyncClient", return_value=client_loop), pytest.raises(
        ValueError, match="Превышен лимит редиректов"
    ):
        await safe_stream_request(
            "https://go.2gis.com/start",
            allowed_host_checker=is_allowed_2gis_host,
            max_redirects=3,
        )


@pytest.mark.asyncio
async def test_safe_stream_oversized_response_protection():
    huge_chunk = b"X" * (200 * 1024)  # 200 KB

    # 1. raise_on_overflow=True raises ValueError and does not buffer excess bytes
    client_overflow = MockAsyncClient([
        MockStreamResponse(200, chunks=[huge_chunk]),
    ])
    with patch("app.services.geo_service.httpx.AsyncClient", return_value=client_overflow), pytest.raises(
        ValueError, match="Размер ответа превысил допустимый лимит"
    ):
        await safe_stream_request(
            "https://catalog.api.2gis.com/3.0/items/byid?id=123",
            allowed_host_checker=is_allowed_2gis_api_host,
            raise_on_overflow=True,
            max_bytes=MAX_RESPONSE_BYTES,
        )

    # 2. raise_on_overflow=False truncates body strictly to MAX_RESPONSE_BYTES (128 KB)
    client_trunc = MockAsyncClient([
        MockStreamResponse(200, chunks=[b"A" * 100000, b"B" * 100000]),
    ])
    with patch("app.services.geo_service.httpx.AsyncClient", return_value=client_trunc):
        code, body, _, _ = await safe_stream_request(
            "https://2gis.kz/almaty/firm/123",
            allowed_host_checker=is_allowed_2gis_host,
            raise_on_overflow=False,
            max_bytes=MAX_RESPONSE_BYTES,
        )
        assert code == 200
        assert len(body) == MAX_RESPONSE_BYTES
        assert body.startswith(b"A" * 100000)
        assert body[100000:] == b"B" * (MAX_RESPONSE_BYTES - 100000)


@pytest.mark.asyncio
async def test_providers_oversized_response_handling():
    huge_data = b"Y" * (250 * 1024)

    # 1. fetch_2gis_firm_point: safe streaming cap prevents memory exhaustion
    mock_client1 = MockAsyncClient([
        MockStreamResponse(200, chunks=[huge_data]),
    ])
    with patch("app.services.geo_service.httpx.AsyncClient", return_value=mock_client1):
        res_firm = await fetch_2gis_firm_point("https://2gis.kz/almaty/firm/70000001018042456")
        assert res_firm is None

    # 2. query_2gis_places_api: returns None when response overflows
    mock_client2 = MockAsyncClient([
        MockStreamResponse(200, chunks=[huge_data]),
    ])
    with patch("app.services.geo_service.httpx.AsyncClient", return_value=mock_client2):
        res_places = await query_2gis_places_api("70000001018042456", "test-key")
        assert res_places is None

    # 3. query_2gis_geocoder_api: returns [] when response overflows
    mock_client3 = MockAsyncClient([
        MockStreamResponse(200, chunks=[huge_data]),
    ])
    with patch("app.services.geo_service.httpx.AsyncClient", return_value=mock_client3):
        res_geo = await query_2gis_geocoder_api("Абая 10", "test-key")
        assert res_geo == []

    # 4. query_nominatim: returns [] when response overflows
    mock_client4 = MockAsyncClient([
        MockStreamResponse(200, chunks=[huge_data]),
    ])
    with patch("app.services.geo_service.httpx.AsyncClient", return_value=mock_client4):
        res_nom = await query_nominatim("Абая 10")
        assert res_nom == []


@pytest.mark.asyncio
async def test_safe_stream_overall_timeout_deadline():
    # Simulated slow stream that takes 0.2s when overall_timeout is 0.05s
    slow_client = MockAsyncClient([
        MockStreamResponse(200, chunks=[b"data"], delay=0.2),
    ])
    with patch("app.services.geo_service.httpx.AsyncClient", return_value=slow_client), pytest.raises(
        TimeoutError
    ):
        await safe_stream_request(
            "https://nominatim.openstreetmap.org/search?q=test",
            allowed_host_checker=is_allowed_nominatim_host,
            overall_timeout=0.05,
        )
