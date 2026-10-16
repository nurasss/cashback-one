"""Apple Wallet / Google Wallet loyalty passes.

A pass carries the card's static barcode as a QR code, so the cashier can scan it from the
phone's wallet just like the plastic card. The QR inside the app stays dynamic (qr_tokens).
Balance and level are not printed on the pass: a pass is not refreshed on every purchase,
so the app remains the place to see them.

Apple passes are downloaded through a short-lived signed link (no auth header is needed, so
the app can hand the link to Safari, which shows "Add to Apple Wallet"). Google passes are
added through a signed "Save to Google Wallet" JWT link.
"""
import base64
import hashlib
import hmac
import io
import json
import struct
import uuid
import zipfile
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

import jwt
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.serialization import pkcs7

from app.core.config import settings
from app.core.time import utcnow
from app.models.entities import Business, Card

ASSETS = Path(__file__).resolve().parent.parent / "assets" / "wallet"
APPLE_IMAGES = ("icon.png", "icon@2x.png", "icon@3x.png", "logo.png", "logo@2x.png")
GOOGLE_LOGO = "google-logo.png"
LINK_PREFIX = "W1"
_MAC_BYTES = 10
_PAYLOAD_BYTES = 20
BRAND_RGB = "rgb(238, 29, 62)"
BRAND_HEX = "#EE1D3E"


def apple_enabled() -> bool:
    configured = all((
        settings.wallet_public_base_url, settings.apple_pass_type_id, settings.apple_team_id,
        settings.apple_pass_cert_file, settings.apple_pass_key_file, settings.apple_wwdr_cert_file,
    ))
    return configured and all(
        Path(p).is_file()
        for p in (settings.apple_pass_cert_file, settings.apple_pass_key_file, settings.apple_wwdr_cert_file)
    )


def google_enabled() -> bool:
    configured = all((
        settings.wallet_public_base_url, settings.google_wallet_issuer_id, settings.google_wallet_service_account_file,
    ))
    return configured and Path(settings.google_wallet_service_account_file).is_file()


# --- Signed download links (Apple) ----------------------------------------------------------


def _link_key() -> bytes:
    return hmac.new(settings.jwt_signing_key.encode("utf-8"), b"cashback-one/wallet-link/v1", hashlib.sha256).digest()


def _link_mac(payload: bytes) -> bytes:
    return hmac.new(_link_key(), LINK_PREFIX.encode() + payload, hashlib.sha256).digest()[:_MAC_BYTES]


def issue_link_token(card_id: uuid.UUID, now: datetime | None = None) -> tuple[str, datetime]:
    expires_at = ((now or utcnow()) + timedelta(seconds=settings.wallet_link_ttl_seconds)).replace(microsecond=0)
    payload = card_id.bytes + struct.pack(">I", int(expires_at.timestamp()))
    raw = payload + _link_mac(payload)
    return LINK_PREFIX + base64.b32encode(raw).decode("ascii").rstrip("="), expires_at


def verify_link_token(token: str, now: datetime | None = None) -> uuid.UUID | None:
    value = token.strip().upper()
    if not value.startswith(LINK_PREFIX) or len(value) > 64:
        return None
    body = value[len(LINK_PREFIX):]
    try:
        raw = base64.b32decode(body + "=" * (-len(body) % 8))
    except ValueError:
        return None
    if len(raw) != _PAYLOAD_BYTES + _MAC_BYTES:
        return None
    payload, mac = raw[:_PAYLOAD_BYTES], raw[_PAYLOAD_BYTES:]
    if not hmac.compare_digest(mac, _link_mac(payload)):
        return None
    (expires_unix,) = struct.unpack(">I", payload[16:])
    if datetime.fromtimestamp(expires_unix, tz=UTC) <= (now or utcnow()):
        return None
    return uuid.UUID(bytes=payload[:16])


def apple_link(card_id: uuid.UUID) -> tuple[str, datetime]:
    token, expires_at = issue_link_token(card_id)
    return f"{settings.wallet_public_base_url}/wallet/apple/{token}.pkpass", expires_at


# --- Apple Wallet (.pkpass) -----------------------------------------------------------------


def apple_pass_json(card: Card, business: Business) -> dict[str, Any]:
    barcode = {"format": "PKBarcodeFormatQR", "message": card.barcode, "messageEncoding": "iso-8859-1", "altText": card.barcode}
    return {
        "formatVersion": 1,
        "passTypeIdentifier": settings.apple_pass_type_id,
        "teamIdentifier": settings.apple_team_id,
        "serialNumber": str(card.id),
        "organizationName": settings.wallet_organization_name,
        "description": f"Бонусная карта {business.name}",
        "logoText": business.name,
        "foregroundColor": "rgb(255, 255, 255)",
        "labelColor": "rgb(255, 222, 227)",
        "backgroundColor": BRAND_RGB,
        "barcodes": [barcode],
        "barcode": barcode,
        "sharingProhibited": True,
        "storeCard": {
            "primaryFields": [{"key": "program", "label": "Бонусная карта", "value": business.name}],
            "secondaryFields": [{"key": "number", "label": "Номер карты", "value": card.barcode}],
            "backFields": [
                {"key": "balance", "label": "Баланс и статус", "value": "Смотрите в приложении Cashback One."},
                {"key": "redeem", "label": "Списание баллов", "value": "Списание подтверждается кодом, который приходит вам в WhatsApp."},
            ],
        },
    }


@lru_cache(maxsize=2)
def _load_apple_signer(cert_file: str, key_file: str, wwdr_file: str, key_password: str) -> tuple[x509.Certificate, Any, x509.Certificate]:
    cert = x509.load_pem_x509_certificate(Path(cert_file).read_bytes())
    password = key_password.encode() if key_password else None
    key = serialization.load_pem_private_key(Path(key_file).read_bytes(), password=password)
    wwdr = x509.load_pem_x509_certificate(Path(wwdr_file).read_bytes())
    return cert, key, wwdr


def _apple_signer() -> tuple[x509.Certificate, Any, x509.Certificate]:
    return _load_apple_signer(
        settings.apple_pass_cert_file,
        settings.apple_pass_key_file,
        settings.apple_wwdr_cert_file,
        settings.apple_pass_key_password,
    )


_apple_signer.cache_clear = _load_apple_signer.cache_clear  # type: ignore[attr-defined]


def build_apple_pass(card: Card, business: Business) -> bytes:
    files: dict[str, bytes] = {"pass.json": json.dumps(apple_pass_json(card, business), ensure_ascii=False).encode("utf-8")}
    for name in APPLE_IMAGES:
        files[name] = (ASSETS / name).read_bytes()
    manifest = json.dumps({name: hashlib.sha1(data).hexdigest() for name, data in files.items()}).encode()
    cert, key, wwdr = _apple_signer()
    signature = (
        pkcs7.PKCS7SignatureBuilder()
        .set_data(manifest)
        .add_signer(cert, key, hashes.SHA256())
        .add_certificate(wwdr)
        .sign(serialization.Encoding.DER, [pkcs7.PKCS7Options.DetachedSignature, pkcs7.PKCS7Options.Binary])
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
        archive.writestr("manifest.json", manifest)
        archive.writestr("signature", signature)
    return buffer.getvalue()


# --- Google Wallet (Save link) --------------------------------------------------------------


@lru_cache(maxsize=2)
def _load_google_account(sa_file: str) -> dict[str, str]:
    data: dict[str, str] = json.loads(Path(sa_file).read_text())
    return data


def _google_account() -> dict[str, str]:
    return _load_google_account(settings.google_wallet_service_account_file)


_google_account.cache_clear = _load_google_account.cache_clear  # type: ignore[attr-defined]


def google_ids(card: Card, business: Business) -> tuple[str, str]:
    issuer = settings.google_wallet_issuer_id
    return f"{issuer}.cashback_{business.id.hex}", f"{issuer}.card_{card.id.hex}"


def google_payload(card: Card, business: Business) -> dict[str, Any]:
    class_id, object_id = google_ids(card, business)
    logo = business.logo_url if (business.logo_url or "").startswith("https://") else f"{settings.wallet_public_base_url}/wallet/assets/{GOOGLE_LOGO}"
    return {
        "loyaltyClasses": [{
            "id": class_id,
            "issuerName": settings.wallet_organization_name,
            "programName": business.name,
            "programLogo": {"sourceUri": {"uri": logo}},
            "hexBackgroundColor": BRAND_HEX,
            "reviewStatus": "UNDER_REVIEW",
        }],
        "loyaltyObjects": [{
            "id": object_id,
            "classId": class_id,
            "state": "ACTIVE",
            "accountId": card.barcode,
            "accountName": card.full_name or card.barcode,
            "barcode": {"type": "QR_CODE", "value": card.barcode, "alternateText": card.barcode},
            "textModulesData": [{"id": "balance", "header": "Баланс и статус", "body": "Смотрите в приложении Cashback One."}],
        }],
    }


def google_save_url(card: Card, business: Business) -> str:
    account = _google_account()
    claims = {
        "iss": account["client_email"],
        "aud": "google",
        "typ": "savetowallet",
        "iat": int(utcnow().timestamp()),
        "origins": [],
        "payload": google_payload(card, business),
    }
    token = jwt.encode(claims, account["private_key"], algorithm="RS256")
    return f"https://pay.google.com/gp/v/save/{token}"
