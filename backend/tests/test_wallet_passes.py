import hashlib
import io
import json
import logging
import subprocess
import uuid
import zipfile
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import jwt
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs7
from cryptography.x509.oid import NameOID
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.time import utcnow
from app.models.entities import UserCard
from app.services import wallet_passes
from tests.test_customer_app import business_with_card, customer


def _generate_test_certs(tmp_path: Path) -> dict[str, str]:
    """Generates test RSA keys and certificates for Apple Wallet pass signing."""
    # CA / WWDR cert
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_name = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "Apple Worldwide Developer Relations CA")]
    )
    now = datetime.now(UTC)
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(1)
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(ca_key, hashes.SHA256())
    )

    # Pass signer cert (signed by WWDR CA)
    signer_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    signer_name = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "Pass Type ID: pass.kz.cashbackone.card")]
    )
    signer_cert = (
        x509.CertificateBuilder()
        .subject_name(signer_name)
        .issuer_name(ca_name)
        .public_key(signer_key.public_key())
        .serial_number(2)
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=365))
        .sign(ca_key, hashes.SHA256())
    )

    wwdr_path = tmp_path / "wwdr.pem"
    cert_path = tmp_path / "pass_cert.pem"
    key_path = tmp_path / "pass_key.pem"

    wwdr_path.write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))
    cert_path.write_bytes(signer_cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        signer_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )

    return {
        "apple_wwdr_cert_file": str(wwdr_path),
        "apple_pass_cert_file": str(cert_path),
        "apple_pass_key_file": str(key_path),
    }


def _generate_test_google_sa(tmp_path: Path) -> tuple[rsa.RSAPrivateKey, str]:
    """Generates an RSA private key and Google Service Account JSON."""
    sa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = sa_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    sa_file = tmp_path / "google_sa.json"
    sa_data = {
        "client_email": "test-wallet-sa@cashback-one.iam.gserviceaccount.com",
        "private_key": pem,
    }
    sa_file.write_text(json.dumps(sa_data))
    return sa_key, str(sa_file)


# --- Availability tests ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_wallet_availability_disabled_without_settings(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, headers = await customer(db_session, "+77011000001")
    wallet_passes._apple_signer.cache_clear()
    wallet_passes._google_account.cache_clear()

    res = await client.get("/me/wallet", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data == {"apple": False, "google": False}


@pytest.mark.asyncio
async def test_wallet_availability_enabled_with_settings(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _, headers = await customer(db_session, "+77011000002")
    certs = _generate_test_certs(tmp_path)
    _, sa_path = _generate_test_google_sa(tmp_path)

    monkeypatch.setattr(settings, "wallet_public_base_url", "https://api.test.kz")
    monkeypatch.setattr(settings, "apple_pass_type_id", "pass.kz.cashbackone.card")
    monkeypatch.setattr(settings, "apple_team_id", "TEAM123456")
    monkeypatch.setattr(settings, "apple_pass_cert_file", certs["apple_pass_cert_file"])
    monkeypatch.setattr(settings, "apple_pass_key_file", certs["apple_pass_key_file"])
    monkeypatch.setattr(settings, "apple_wwdr_cert_file", certs["apple_wwdr_cert_file"])
    monkeypatch.setattr(settings, "apple_pass_key_password", "")
    monkeypatch.setattr(settings, "google_wallet_issuer_id", "3388000000022")
    monkeypatch.setattr(settings, "google_wallet_service_account_file", sa_path)

    wallet_passes._apple_signer.cache_clear()
    wallet_passes._google_account.cache_clear()

    res = await client.get("/me/wallet", headers=headers)
    assert res.status_code == 200
    assert res.json() == {"apple": True, "google": True}


def test_wallet_startup_warnings_when_files_unreadable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    non_existent_cert = str(tmp_path / "missing_cert.pem")
    unreadable_key = tmp_path / "unreadable_key.pem"
    unreadable_key.write_text("dummy key")
    try:
        unreadable_key.chmod(0o000)
    except OSError:
        pass

    monkeypatch.setattr(settings, "wallet_public_base_url", "https://api.test.kz")
    monkeypatch.setattr(settings, "apple_pass_type_id", "pass.kz.cashbackone.card")
    monkeypatch.setattr(settings, "apple_team_id", "TEAM123456")
    monkeypatch.setattr(settings, "apple_pass_cert_file", non_existent_cert)
    monkeypatch.setattr(settings, "apple_pass_key_file", str(unreadable_key))
    monkeypatch.setattr(settings, "apple_wwdr_cert_file", "")
    monkeypatch.setattr(settings, "google_wallet_issuer_id", "3388000000022")
    monkeypatch.setattr(
        settings, "google_wallet_service_account_file", str(tmp_path / "missing_sa.json")
    )

    with caplog.at_level(logging.WARNING):
        warnings = wallet_passes.check_wallet_files_at_startup(force=True)

    assert len(warnings) >= 3
    assert any("apple_pass_cert_file" in w and "is not readable" in w for w in warnings)
    assert any("apple_pass_key_file" in w and "is not readable" in w for w in warnings)
    assert any("apple_wwdr_cert_file" in w and "not set" in w for w in warnings)
    assert any(
        "google_wallet_service_account_file" in w and "is not readable" in w for w in warnings
    )

    assert not wallet_passes.apple_enabled()
    assert not wallet_passes.google_enabled()

    # Second run without force does not produce duplicate warnings (runs once)
    caplog.clear()
    dup_warnings = wallet_passes.check_wallet_files_at_startup(force=False)
    assert len(dup_warnings) == 0
    assert len(caplog.records) == 0


# --- Token and Link tests -------------------------------------------------------------------


def test_w1_token_roundtrip_tampering_and_expiry() -> None:
    card_id = uuid.uuid4()
    now = utcnow()

    token, expires_at = wallet_passes.issue_link_token(card_id, now=now)
    assert token.startswith("W1")
    assert expires_at > now

    # Valid verification
    verified = wallet_passes.verify_link_token(token, now=now)
    assert verified == card_id

    # Expiry verification
    past_expiry = wallet_passes.verify_link_token(token, now=expires_at + timedelta(seconds=1))
    assert past_expiry is None

    # Tampering: change characters
    corrupted = token[:-2] + ("A" if token[-1] != "A" else "B")
    assert wallet_passes.verify_link_token(corrupted, now=now) is None

    # Invalid prefix or too short
    assert wallet_passes.verify_link_token("X1abc", now=now) is None
    assert wallet_passes.verify_link_token("W1short", now=now) is None


@pytest.mark.asyncio
async def test_card_wallet_link_errors(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    user1, headers1 = await customer(db_session, "+77011000003")
    _user2, headers2 = await customer(db_session, "+77011000004")
    _, card = await business_with_card(db_session, user1, barcode="0123456789010")

    # Card not owned -> 404
    res = await client.post(
        f"/me/cards/{card.id}/wallet", json={"platform": "apple"}, headers=headers2
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "CARD_NOT_FOUND"

    # Hidden card -> 404
    user_card = (
        await db_session.execute(
            select(UserCard).where(UserCard.user_id == user1.id, UserCard.card_id == card.id)
        )
    ).scalar_one()
    user_card.hidden_at = utcnow()
    await db_session.commit()
    res = await client.post(
        f"/me/cards/{card.id}/wallet", json={"platform": "apple"}, headers=headers1
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "CARD_NOT_FOUND"
    user_card.hidden_at = None
    await db_session.commit()

    # Wallet unconfigured -> 503
    monkeypatch.setattr(settings, "apple_pass_type_id", "")
    monkeypatch.setattr(settings, "google_wallet_issuer_id", "")
    res = await client.post(
        f"/me/cards/{card.id}/wallet", json={"platform": "apple"}, headers=headers1
    )
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "WALLET_UNAVAILABLE"

    res = await client.post(
        f"/me/cards/{card.id}/wallet", json={"platform": "google"}, headers=headers1
    )
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "WALLET_UNAVAILABLE"

    # Blocked card -> 409
    card.is_blocked = True
    await db_session.commit()
    res = await client.post(
        f"/me/cards/{card.id}/wallet", json={"platform": "apple"}, headers=headers1
    )
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "CARD_BLOCKED"


# --- Apple Wallet (.pkpass) end-to-end -------------------------------------------------------


@pytest.mark.asyncio
async def test_apple_pass_generation_download_and_signature(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    user, headers = await customer(db_session, "+77011000005")
    _, card = await business_with_card(
        db_session, user, name="POSCENTER Маркет", barcode="2000000000012"
    )
    card.balance = Decimal("15000.50")
    await db_session.commit()

    certs = _generate_test_certs(tmp_path)
    monkeypatch.setattr(settings, "wallet_public_base_url", "https://api.cashback-qr.poscenter.kz")
    monkeypatch.setattr(settings, "apple_pass_type_id", "pass.kz.cashbackone.card")
    monkeypatch.setattr(settings, "apple_team_id", "TEAM123456")
    monkeypatch.setattr(settings, "apple_pass_cert_file", certs["apple_pass_cert_file"])
    monkeypatch.setattr(settings, "apple_pass_key_file", certs["apple_pass_key_file"])
    monkeypatch.setattr(settings, "apple_wwdr_cert_file", certs["apple_wwdr_cert_file"])
    monkeypatch.setattr(settings, "apple_pass_key_password", "")
    wallet_passes._apple_signer.cache_clear()

    # 1. Request Apple Wallet link
    res = await client.post(
        f"/me/cards/{card.id}/wallet", json={"platform": "apple"}, headers=headers
    )
    assert res.status_code == 200
    data = res.json()
    assert "url" in data
    assert data["expires_at"] is not None
    download_url = data["url"]
    assert download_url.startswith("https://api.cashback-qr.poscenter.kz/wallet/apple/W1")
    assert download_url.endswith(".pkpass")

    # 2. Extract path and fetch without authentication header (Safari behavior)
    path = download_url.replace("https://api.cashback-qr.poscenter.kz", "")
    pass_res = await client.get(path)
    assert pass_res.status_code == 200
    assert pass_res.headers["content-type"] == "application/vnd.apple.pkpass"
    assert pass_res.headers["cache-control"] == "no-store"
    assert 'filename="card.pkpass"' in pass_res.headers["content-disposition"]

    # 3. Verify .pkpass ZIP structure and manifest hashes
    zip_bytes = pass_res.content
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        namelist = zf.namelist()
        assert "pass.json" in namelist
        assert "manifest.json" in namelist
        assert "signature" in namelist
        for img in wallet_passes.APPLE_IMAGES:
            assert img in namelist

        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        # Check manifest matches SHA1 of every file except manifest and signature
        for name in namelist:
            if name in ("manifest.json", "signature"):
                continue
            assert name in manifest
            expected_sha1 = hashlib.sha1(zf.read(name)).hexdigest()
            assert manifest[name] == expected_sha1

        # Check pass.json semantics: barcode matches, no dynamic QR token, balance not exposed
        pass_data = json.loads(zf.read("pass.json").decode("utf-8"))
        assert pass_data["formatVersion"] == 1
        assert pass_data["passTypeIdentifier"] == "pass.kz.cashbackone.card"
        assert pass_data["serialNumber"] == str(card.id)
        assert pass_data["barcodes"][0]["message"] == "2000000000012"
        assert pass_data["barcode"]["message"] == "2000000000012"
        assert pass_data["storeCard"]["secondaryFields"][0]["value"] == "2000000000012"

        # Ensure no C1 dynamic token or numeric balance is printed
        pass_json_str = zf.read("pass.json").decode("utf-8")
        assert "15000.50" not in pass_json_str
        assert "C1" not in pass_json_str
        # Verify backFields informative note
        back_values = [bf["value"] for bf in pass_data["storeCard"]["backFields"]]
        assert any("Смотрите в приложении Cashback One" in v for v in back_values)
        assert any("WhatsApp" in v for v in back_values)

        # 4. Verify signature contains certificates
        sig = zf.read("signature")
        loaded_certs = pkcs7.load_der_pkcs7_certificates(sig)
        assert len(loaded_certs) >= 2  # signer cert + WWDR cert

        # Verify signature cryptographically with OpenSSL and the test CA
        sig_file = tmp_path / "sig.der"
        manifest_file = tmp_path / "manifest.json"
        tampered_manifest_file = tmp_path / "tampered_manifest.json"
        sig_file.write_bytes(sig)
        manifest_file.write_bytes(zf.read("manifest.json"))
        tampered_manifest_file.write_bytes(b'{"corrupted": true}')

        openssl_check = subprocess.run(  # noqa: ASYNC221
            [
                "openssl",
                "smime",
                "-verify",
                "-inform",
                "DER",
                "-binary",
                "-content",
                str(manifest_file),
                "-CAfile",
                certs["apple_wwdr_cert_file"],
                "-in",
                str(sig_file),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert openssl_check.returncode == 0, f"OpenSSL smime verify failed: {openssl_check.stderr}"
        assert "Verification successful" in openssl_check.stderr

        # Ensure cryptographic check rejects tampered content
        tampered_check = subprocess.run(  # noqa: ASYNC221
            [
                "openssl",
                "smime",
                "-verify",
                "-inform",
                "DER",
                "-binary",
                "-content",
                str(tampered_manifest_file),
                "-CAfile",
                certs["apple_wwdr_cert_file"],
                "-in",
                str(sig_file),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert tampered_check.returncode != 0


@pytest.mark.asyncio
async def test_apple_pass_download_invalid_token(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 1. Unconfigured Apple Wallet -> 503
    monkeypatch.setattr(wallet_passes, "apple_enabled", lambda: False)
    res = await client.get("/wallet/apple/W1invalidtoken.pkpass")
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "WALLET_UNAVAILABLE"

    # 2. Corrupt / invalid token -> 404
    monkeypatch.setattr(wallet_passes, "apple_enabled", lambda: True)
    res = await client.get("/wallet/apple/W1invalidtoken.pkpass")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "WALLET_LINK_INVALID"

    # 3. Valid token for blocked card -> 404
    user, _ = await customer(db_session, "+77011000007")
    biz, card = await business_with_card(db_session, user, barcode="0123456789999")
    card.is_blocked = True
    await db_session.commit()
    token, _ = wallet_passes.issue_link_token(card.id)
    res = await client.get(f"/wallet/apple/{token}.pkpass")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "WALLET_LINK_INVALID"

    # 4. Valid token for inactive business -> 404
    card.is_blocked = False
    biz.status = "inactive"
    await db_session.commit()
    res = await client.get(f"/wallet/apple/{token}.pkpass")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "WALLET_LINK_INVALID"


# --- Google Wallet Save URL -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_google_save_url_payload_and_jwt(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    user, headers = await customer(db_session, "+77011000006")
    biz, card = await business_with_card(
        db_session, user, name="POSCENTER Супермаркет", barcode="9990000000001"
    )

    sa_key, sa_path = _generate_test_google_sa(tmp_path)
    monkeypatch.setattr(settings, "wallet_public_base_url", "https://api.cashback-qr.poscenter.kz")
    monkeypatch.setattr(settings, "google_wallet_issuer_id", "3388000000022")
    monkeypatch.setattr(settings, "google_wallet_service_account_file", sa_path)
    monkeypatch.setattr(settings, "wallet_organization_name", "POSCENTER ONE")
    wallet_passes._google_account.cache_clear()

    res = await client.post(
        f"/me/cards/{card.id}/wallet", json={"platform": "google"}, headers=headers
    )
    assert res.status_code == 200
    data = res.json()
    assert data["expires_at"] is None
    url = data["url"]
    assert url.startswith("https://pay.google.com/gp/v/save/")

    token = url.replace("https://pay.google.com/gp/v/save/", "")
    decoded = jwt.decode(token, sa_key.public_key(), algorithms=["RS256"], audience="google")
    assert decoded["iss"] == "test-wallet-sa@cashback-one.iam.gserviceaccount.com"
    assert decoded["aud"] == "google"
    assert decoded["typ"] == "savetowallet"

    payload = decoded["payload"]
    loyalty_class = payload["loyaltyClasses"][0]
    assert loyalty_class["id"] == f"3388000000022.cashback_{biz.id.hex}"
    assert loyalty_class["issuerName"] == "POSCENTER ONE"
    assert loyalty_class["programName"] == "POSCENTER Супермаркет"

    loyalty_obj = payload["loyaltyObjects"][0]
    assert loyalty_obj["id"] == f"3388000000022.card_{card.id.hex}"
    assert loyalty_obj["classId"] == loyalty_class["id"]
    assert loyalty_obj["state"] == "ACTIVE"
    assert loyalty_obj["barcode"]["type"] == "QR_CODE"
    assert loyalty_obj["barcode"]["value"] == "9990000000001"
    assert loyalty_obj["textModulesData"][0]["header"] == "Баланс и статус"


# --- Google Wallet Logo Endpoint ------------------------------------------------------------


@pytest.mark.asyncio
async def test_google_wallet_logo_endpoint(client: AsyncClient) -> None:
    res = await client.get("/wallet/assets/google-logo.png")
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/png"
    assert res.headers["cache-control"] == "public, max-age=86400"
    # PNG signature: 89 50 4E 47 0D 0A 1A 0A
    assert res.content.startswith(b"\x89PNG\r\n\x1a\n")
