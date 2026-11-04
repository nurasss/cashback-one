"""Comprehensive tests for Push Notification infrastructure (Task A, 2026-11-04).

Covers:
1. FCM HTTP v1 Sender (OAuth2 JWT RS256, caching, request payload format, error parsing).
2. Push Service (has_active_device, send_to_user with active/disabled/failing devices).
3. Customer API endpoints (PUT /me/push-token, DELETE /me/push-token, validation, rate limits, ownership transfer).
"""
import json
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError
from app.core.security import create_access_token, hash_refresh_token
from app.core.time import utcnow
from app.models.entities import AuthSession, Device, User
from app.services.push_sender import (
    DisabledPushSender,
    FakePushSender,
    FcmPushSender,
    LogPushSender,
    PushResult,
    PushStatus,
)
from app.services.push_service import has_active_device, send_to_user


def _generate_test_service_account_file(tmp_path: Path) -> Path:
    """Generate a valid Google Service Account JSON file with a real 2048-bit RSA key."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    sa_dict = {
        "type": "service_account",
        "project_id": "test-firebase-project",
        "private_key_id": "test-key-id-12345",
        "private_key": pem,
        "client_email": "firebase-adminsdk@test-firebase-project.iam.gserviceaccount.com",
        "client_id": "1234567890",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
    sa_file = tmp_path / "firebase-service-account.json"
    sa_file.write_text(json.dumps(sa_dict), encoding="utf-8")
    return sa_file


async def _create_test_customer(
    db: AsyncSession, phone: str = "+77011112233"
) -> tuple[User, dict[str, str]]:
    user = User(phone=phone, language="ru")
    db.add(user)
    await db.flush()
    auth = AuthSession(
        user_id=user.id,
        device_id="phone-device-1",
        refresh_token_hash=hash_refresh_token(f"rfr_{uuid.uuid4()}"),
        expires_at=utcnow() + timedelta(days=14),
    )
    db.add(auth)
    await db.commit()
    token = create_access_token(user_id=user.id, session_id=auth.id)
    return user, {"Authorization": f"Bearer {token}"}


# ==============================================================================
# 1. FCM Sender Unit Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_fcm_sender_configuration_and_validation(tmp_path: Path) -> None:
    sa_file = _generate_test_service_account_file(tmp_path)

    # Empty project id
    with pytest.raises(ValueError, match="FCM_PROJECT_ID is required"):
        FcmPushSender(project_id="", service_account_file=str(sa_file))

    # Missing file
    with pytest.raises(ValueError, match="FCM service account file not found"):
        FcmPushSender(project_id="my-proj", service_account_file=str(tmp_path / "nonexistent.json"))

    # Invalid JSON file
    bad_json_file = tmp_path / "bad.json"
    bad_json_file.write_text("not json content", encoding="utf-8")
    with pytest.raises(ValueError, match="Failed to parse FCM service account JSON"):
        FcmPushSender(project_id="my-proj", service_account_file=str(bad_json_file))

    # Missing client_email or private_key
    missing_key_file = tmp_path / "missing_key.json"
    missing_key_file.write_text(json.dumps({"client_email": "x@y.com"}), encoding="utf-8")
    with pytest.raises(ValueError, match="missing client_email or private_key"):
        FcmPushSender(project_id="my-proj", service_account_file=str(missing_key_file))


@pytest.mark.asyncio
async def test_fcm_sender_oauth2_jwt_flow_and_message_delivery(tmp_path: Path) -> None:
    sa_file = _generate_test_service_account_file(tmp_path)

    token_requests: list[httpx.Request] = []
    fcm_requests: list[httpx.Request] = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token":
            token_requests.append(request)
            return httpx.Response(
                200,
                json={"access_token": "ya29.test_oauth_access_token", "expires_in": 3600},
            )
        if "/messages:send" in request.url.path:
            fcm_requests.append(request)
            return httpx.Response(
                200,
                json={"name": "projects/test-firebase-project/messages/msg_001"},
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(mock_handler)
    sender = FcmPushSender(
        project_id="test-firebase-project",
        service_account_file=str(sa_file),
        transport=transport,
    )

    # First send: requests OAuth2 token, then sends message
    result = await sender.send(
        token="device_fcm_token_123",
        title="Тестовый заголовок",
        body="Тестовое сообщение",
        data={"code": "1234", "purpose": "redemption"},
    )
    assert result.status == PushStatus.DELIVERED
    assert len(token_requests) == 1
    assert len(fcm_requests) == 1

    # Verify OAuth2 token request
    token_req = token_requests[0]
    req_body = token_req.read().decode("utf-8")
    assert "grant_type=urn%3Aietf%3Aparams%3Aoauth%3Agrant-type%3Ajwt-bearer" in req_body
    assert "assertion=" in req_body

    # Verify FCM HTTP v1 request payload
    fcm_req = fcm_requests[0]
    assert fcm_req.url.path == "/v1/projects/test-firebase-project/messages:send"
    assert fcm_req.headers["Authorization"] == "Bearer ya29.test_oauth_access_token"
    payload = json.loads(fcm_req.read())
    msg = payload["message"]
    assert msg["token"] == "device_fcm_token_123"
    assert msg["notification"]["title"] == "Тестовый заголовок"
    assert msg["notification"]["body"] == "Тестовое сообщение"
    assert msg["data"] == {"code": "1234", "purpose": "redemption"}
    assert msg["android"]["priority"] == "HIGH"
    assert msg["android"]["notification"]["channel_id"] == "default"

    # Second send: should use CACHED OAuth2 token without requesting /token again
    result2 = await sender.send(
        token="device_fcm_token_456",
        title="Второе",
        body="Тело",
    )
    assert result2.status == PushStatus.DELIVERED
    assert len(token_requests) == 1  # No additional token request
    assert len(fcm_requests) == 2


@pytest.mark.asyncio
async def test_fcm_sender_error_parsing(tmp_path: Path) -> None:
    sa_file = _generate_test_service_account_file(tmp_path)
    current_fcm_response: tuple[int, dict[str, Any]] = (200, {})

    def mock_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token":
            return httpx.Response(200, json={"access_token": "token_xyz", "expires_in": 3600})
        status, body = current_fcm_response
        return httpx.Response(status, json=body)

    transport = httpx.MockTransport(mock_handler)
    sender = FcmPushSender(
        project_id="test-firebase-project",
        service_account_file=str(sa_file),
        transport=transport,
    )

    # 1. UNREGISTERED error (token invalid/expired)
    current_fcm_response = (
        404,
        {
            "error": {
                "code": 404,
                "message": "Requested entity was not found.",
                "status": "NOT_FOUND",
                "details": [
                    {
                        "@type": "type.googleapis.com/google.firebase.fcm.v1.FcmError",
                        "errorCode": "UNREGISTERED",
                    }
                ],
            }
        },
    )
    res = await sender.send(token="unregistered_token", title="T", body="B")
    assert res.status == PushStatus.INVALID_TOKEN
    assert res.error_details == "UNREGISTERED"

    # 2. INVALID_ARGUMENT error for token
    current_fcm_response = (
        400,
        {
            "error": {
                "code": 400,
                "message": "The registration token is not a valid FCM registration token",
                "status": "INVALID_ARGUMENT",
                "details": [
                    {
                        "@type": "type.googleapis.com/google.firebase.fcm.v1.FcmError",
                        "errorCode": "INVALID_ARGUMENT",
                    }
                ],
            }
        },
    )
    res = await sender.send(token="malformed_token", title="T", body="B")
    assert res.status == PushStatus.INVALID_TOKEN
    assert res.error_details == "INVALID_ARGUMENT_TOKEN"

    # 3. INVALID_ARGUMENT error for non-token payload -> REJECTED (must NOT disable device)
    current_fcm_response = (
        400,
        {
            "error": {
                "code": 400,
                "message": "Payload size exceeds maximum allowed limit",
                "status": "INVALID_ARGUMENT",
                "details": [
                    {
                        "@type": "type.googleapis.com/google.firebase.fcm.v1.FcmError",
                        "errorCode": "INVALID_ARGUMENT",
                    }
                ],
            }
        },
    )
    res = await sender.send(token="valid_token_oversized_body", title="T", body="B")
    assert res.status == PushStatus.REJECTED
    assert res.error_details == "INVALID_ARGUMENT_PAYLOAD"

    # 4. NOT_FOUND without UNREGISTERED -> TEMPORARY_ERROR (must NOT disable device)
    current_fcm_response = (
        404,
        {
            "error": {
                "code": 404,
                "message": "Project not found or endpoint URL invalid",
                "status": "NOT_FOUND",
            }
        },
    )
    res = await sender.send(token="valid_token_wrong_project", title="T", body="B")
    assert res.status == PushStatus.TEMPORARY_ERROR
    assert res.error_details == "HTTP_404_NOT_FOUND"

    # 5. Rate limited (429) -> TEMPORARY_ERROR
    current_fcm_response = (429, {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED"}})
    res = await sender.send(token="t", title="T", body="B")
    assert res.status == PushStatus.TEMPORARY_ERROR

    # 6. Server error (500) -> TEMPORARY_ERROR
    current_fcm_response = (500, {"error": {"code": 500, "status": "INTERNAL"}})
    res = await sender.send(token="t", title="T", body="B")
    assert res.status == PushStatus.TEMPORARY_ERROR


@pytest.mark.asyncio
async def test_disabled_and_log_and_fake_push_senders() -> None:
    disabled = DisabledPushSender()
    assert disabled.disabled is True
    with pytest.raises(AppError) as exc_info:
        await disabled.send(token="t", title="T", body="B")
    assert exc_info.value.code == "PUSH_NOT_CONFIGURED"

    log_sender = LogPushSender()
    assert log_sender.disabled is False
    res_log = await log_sender.send(token="fcm_token_123456", title="Title", body="Body", data={"k": "v"})
    assert res_log.status == PushStatus.DELIVERED

    fake_sender = FakePushSender()
    assert fake_sender.disabled is False
    res_fake = await fake_sender.send(token="token1", title="T1", body="B1", data={"a": "b"})
    assert res_fake.status == PushStatus.DELIVERED
    assert len(fake_sender.sent_messages) == 1
    assert fake_sender.sent_messages[0].token == "token1"

    # Test simulated next result
    fake_sender.next_result = PushResult(status=PushStatus.INVALID_TOKEN, error_details="SIMULATED")
    res_sim = await fake_sender.send(token="token2", title="T2", body="B2")
    assert res_sim.status == PushStatus.INVALID_TOKEN
    assert res_sim.error_details == "SIMULATED"


# ==============================================================================
# 2. Push Service Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_push_service_has_active_device_and_send_to_user(db_session: AsyncSession) -> None:
    user, _ = await _create_test_customer(db_session, phone="+77023334455")

    # Initially has no active devices
    assert await has_active_device(db_session, user.id) is False

    # Add active device
    dev1 = Device(
        user_id=user.id,
        push_token="user_device_token_1",
        platform="android",
        app_id="kz.cashbackone.mobile",
        last_seen_at=utcnow(),
        disabled_at=None,
    )
    db_session.add(dev1)
    await db_session.commit()

    assert await has_active_device(db_session, user.id) is True

    # Disable device
    dev1.disabled_at = utcnow()
    await db_session.commit()

    assert await has_active_device(db_session, user.id) is False

    # Re-enable and add a second device
    dev1.disabled_at = None
    dev2 = Device(
        user_id=user.id,
        push_token="user_device_token_2",
        platform="android",
        app_id="kz.cashbackone.mobile",
        last_seen_at=utcnow(),
        disabled_at=None,
    )
    db_session.add(dev2)
    await db_session.commit()

    # Send to user with 2 active devices
    fake_sender = FakePushSender()
    delivered = await send_to_user(
        db_session,
        sender=fake_sender,
        user_id=user.id,
        title="Уведомление",
        body="Код списания: 4421",
        data={"code": "4421"},
    )
    assert delivered == 2
    assert len(fake_sender.sent_messages) == 2

    # Test invalid token handling: dev1 returns INVALID_TOKEN, dev2 delivers
    fake_sender.clear()
    fake_sender.results_by_token["user_device_token_1"] = PushResult(
        status=PushStatus.INVALID_TOKEN, error_details="UNREGISTERED"
    )
    delivered = await send_to_user(
        db_session,
        sender=fake_sender,
        user_id=user.id,
        title="Повтор",
        body="Текст",
    )
    assert delivered == 1

    # Verify dev1 is now marked disabled_at in the database
    await db_session.refresh(dev1)
    await db_session.refresh(dev2)
    assert dev1.disabled_at is not None
    assert dev2.disabled_at is None

    # Test temporary error handling: dev2 returns TEMPORARY_ERROR
    fake_sender.clear()
    fake_sender.results_by_token["user_device_token_2"] = PushResult(
        status=PushStatus.TEMPORARY_ERROR, error_details="HTTP_500"
    )
    delivered = await send_to_user(
        db_session,
        sender=fake_sender,
        user_id=user.id,
        title="Тест временного сбоя",
        body="Текст",
    )
    assert delivered == 0
    await db_session.refresh(dev2)
    # Temporary error must NOT disable dev2
    assert dev2.disabled_at is None

    # Test non-token REJECTED handling: dev2 returns REJECTED
    fake_sender.clear()
    fake_sender.results_by_token["user_device_token_2"] = PushResult(
        status=PushStatus.REJECTED, error_details="INVALID_ARGUMENT_PAYLOAD"
    )
    delivered = await send_to_user(
        db_session,
        sender=fake_sender,
        user_id=user.id,
        title="Тест ошибки payload",
        body="Текст",
    )
    assert delivered == 0
    await db_session.refresh(dev2)
    # REJECTED must NOT disable dev2
    assert dev2.disabled_at is None


# ==============================================================================
# 3. Customer API Tests (PUT/DELETE /me/push-token)
# ==============================================================================


@pytest.mark.asyncio
async def test_put_push_token_lifecycle_and_ownership_transfer(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    user1, auth_headers1 = await _create_test_customer(db_session, phone="+77031112233")
    user2, auth_headers2 = await _create_test_customer(db_session, phone="+77032223344")

    # 1. Register push token for user1
    resp = await client.put(
        "/me/push-token",
        headers=auth_headers1,
        json={
            "token": "fcm_token_alice_phone_12345",
            "platform": "android",
            "app_id": "kz.cashbackone.mobile",
        },
    )
    assert resp.status_code == 204

    # Verify DB record
    stmt = select(Device).where(Device.push_token == "fcm_token_alice_phone_12345")
    dev = await db_session.scalar(stmt)
    assert dev is not None
    assert dev.user_id == user1.id
    assert dev.platform == "android"
    assert dev.app_id == "kz.cashbackone.mobile"
    assert dev.disabled_at is None
    first_seen = dev.last_seen_at

    # 2. Re-register same token by user1 (updates last_seen_at)
    resp = await client.put(
        "/me/push-token",
        headers=auth_headers1,
        json={
            "token": "fcm_token_alice_phone_12345",
            "platform": "android",
            "app_id": "kz.cashbackone.mobile",
        },
    )
    assert resp.status_code == 204
    await db_session.refresh(dev)
    assert dev.user_id == user1.id
    assert dev.last_seen_at >= first_seen

    # 3. Ownership transfer: user2 registers the same token (e.g. phone transferred to new account)
    resp = await client.put(
        "/me/push-token",
        headers=auth_headers2,
        json={
            "token": "fcm_token_alice_phone_12345",
            "platform": "android",
            "app_id": "kz.client_shop.app",
        },
    )
    assert resp.status_code == 204
    await db_session.refresh(dev)
    # The record should now belong to user2
    assert dev.user_id == user2.id
    assert dev.app_id == "kz.client_shop.app"
    assert dev.disabled_at is None


@pytest.mark.asyncio
async def test_delete_push_token_behavior(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    _user1, auth_headers1 = await _create_test_customer(db_session, phone="+77041112233")
    _user2, auth_headers2 = await _create_test_customer(db_session, phone="+77042223344")

    # Register token for user1
    resp = await client.put(
        "/me/push-token",
        headers=auth_headers1,
        json={
            "token": "delete_test_token_999",
            "platform": "android",
            "app_id": "kz.cashbackone.mobile",
        },
    )
    assert resp.status_code == 204

    stmt = select(Device).where(Device.push_token == "delete_test_token_999")
    dev = await db_session.scalar(stmt)
    assert dev is not None
    assert dev.disabled_at is None

    # User2 attempts to delete User1's token -> must NOT disable User1's device, but still returns 204
    resp = await client.request(
        "DELETE",
        "/me/push-token",
        headers=auth_headers2,
        json={"token": "delete_test_token_999"},
    )
    assert resp.status_code == 204
    await db_session.refresh(dev)
    assert dev.disabled_at is None

    # Deleting non-existent token returns 204
    resp = await client.request(
        "DELETE",
        "/me/push-token",
        headers=auth_headers1,
        json={"token": "non_existent_token_abc"},
    )
    assert resp.status_code == 204

    # User1 deletes own token -> marks disabled_at
    resp = await client.request(
        "DELETE",
        "/me/push-token",
        headers=auth_headers1,
        json={"token": "delete_test_token_999"},
    )
    assert resp.status_code == 204
    await db_session.refresh(dev)
    assert dev.disabled_at is not None

    # Re-registering by User1 un-disables it
    resp = await client.put(
        "/me/push-token",
        headers=auth_headers1,
        json={
            "token": "delete_test_token_999",
            "platform": "android",
            "app_id": "kz.cashbackone.mobile",
        },
    )
    assert resp.status_code == 204
    await db_session.refresh(dev)
    assert dev.disabled_at is None


@pytest.mark.asyncio
async def test_push_token_field_validations(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    _, auth_headers = await _create_test_customer(db_session, phone="+77051112233")

    # 1. Platform must be android only
    resp = await client.put(
        "/me/push-token",
        headers=auth_headers,
        json={"token": "valid_token", "platform": "ios", "app_id": "kz.cashbackone.mobile"},
    )
    assert resp.status_code == 422

    # 2. Token must not contain whitespace
    resp = await client.put(
        "/me/push-token",
        headers=auth_headers,
        json={"token": "token with space", "platform": "android", "app_id": "kz.cashbackone.mobile"},
    )
    assert resp.status_code == 422

    # 3. App ID must match Android package format
    bad_app_ids = ["bad_package_no_dots", "123.starts_with_number", "kz..double_dot", "kz.has-dash.app"]
    for bad_id in bad_app_ids:
        resp = await client.put(
            "/me/push-token",
            headers=auth_headers,
            json={"token": "valid_token", "platform": "android", "app_id": bad_id},
        )
        assert resp.status_code == 422, f"Expected 422 for app_id={bad_id}"

    # Valid Android package IDs
    good_app_ids = ["kz.cashbackone.mobile", "com.example.app", "org.poscenter.loyalty_client_1"]
    for good_id in good_app_ids:
        resp = await client.put(
            "/me/push-token",
            headers=auth_headers,
            json={"token": f"token_{good_id}", "platform": "android", "app_id": good_id},
        )
        assert resp.status_code == 204

    # Token length boundary: 1024 characters succeeds, 1025 fails with 422
    token_1024 = "x" * 1024
    resp = await client.put(
        "/me/push-token",
        headers=auth_headers,
        json={"token": token_1024, "platform": "android", "app_id": "kz.cashbackone.mobile"},
    )
    assert resp.status_code == 204

    token_1025 = "x" * 1025
    resp = await client.put(
        "/me/push-token",
        headers=auth_headers,
        json={"token": token_1025, "platform": "android", "app_id": "kz.cashbackone.mobile"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_concurrent_push_token_registration_race(
    client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that concurrent/duplicate registration of same token handles race without 500."""
    _user1, auth_headers1 = await _create_test_customer(db_session, phone="+77071112233")
    user2, auth_headers2 = await _create_test_customer(db_session, phone="+77072223344")
    user2_id = user2.id

    shared_token = "concurrent_race_token_xyz"

    resp1 = await client.put(
        "/me/push-token",
        headers=auth_headers1,
        json={"token": shared_token, "platform": "android", "app_id": "kz.user1.app"},
    )
    assert resp1.status_code == 204

    # Simulate race condition: during user2's request, the initial device lookup
    # returns None (as if two requests raced and both saw no record).
    # This forces execution into the `else:` branch, where session.add() + commit()
    # triggers IntegrityError on the unique index because user1 already inserted the token.
    # The except IntegrityError branch must rollback and update the record without 500.
    real_scalar = AsyncSession.scalar
    first_device_lookup = True

    async def mock_scalar(self, statement, *args, **kwargs):
        nonlocal first_device_lookup
        if first_device_lookup:
            get_froms = getattr(statement, "get_final_froms", None)
            froms = get_froms() if callable(get_froms) else getattr(statement, "froms", ())
            table_names = [getattr(f, "name", "") for f in froms]
            if "devices" in table_names:
                first_device_lookup = False
                return None
        return await real_scalar(self, statement, *args, **kwargs)

    monkeypatch.setattr(AsyncSession, "scalar", mock_scalar)

    resp2 = await client.put(
        "/me/push-token",
        headers=auth_headers2,
        json={"token": shared_token, "platform": "android", "app_id": "kz.user2.app"},
    )
    assert resp2.status_code == 204

    devices = (
        await db_session.scalars(select(Device).where(Device.push_token == shared_token))
    ).all()
    assert len(devices) == 1
    assert devices[0].user_id == user2_id
    assert devices[0].app_id == "kz.user2.app"


@pytest.mark.asyncio
async def test_push_token_rate_limiting(
    client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, auth_headers = await _create_test_customer(db_session, phone="+77061112233")
    monkeypatch.setattr(settings, "push_token_user_limit", 3)

    for i in range(3):
        resp = await client.put(
            "/me/push-token",
            headers=auth_headers,
            json={"token": f"rate_token_{i}", "platform": "android", "app_id": "kz.cashbackone.mobile"},
        )
        assert resp.status_code == 204

    # 4th attempt should be blocked with 429
    resp = await client.put(
        "/me/push-token",
        headers=auth_headers,
        json={"token": "rate_token_blocked", "platform": "android", "app_id": "kz.cashbackone.mobile"},
    )
    assert resp.status_code == 429
    data = resp.json()
    assert data["error"]["code"] == "RATE_LIMIT_EXCEEDED"
