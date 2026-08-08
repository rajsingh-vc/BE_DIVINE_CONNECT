import json
from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings


class QRDecryptionError(Exception):
    """Generic verification failure: malformed payload, missing fields, or
    an unrecognized user_type. Maps to 'QR Verification Failed'."""


class QRInvalidError(QRDecryptionError):
    """Signature check failed — tampered, corrupted, or not a QR this
    system issued. Maps to 'Invalid QR'."""


class QRExpiredError(QRDecryptionError):
    """Signature is valid but the token is older than max_age_seconds.
    Maps to 'QR Expired'."""


def get_fernet() -> MultiFernet:
    """MultiFernet encrypts with the first key, decrypts with any key in the
    list — lets you rotate QR_ENCRYPTION_KEY without invalidating QR codes
    already printed/cached on devices (old key goes in _PREVIOUS during the
    rotation window)."""
    keys = [Fernet(settings.QR_ENCRYPTION_KEY)]
    prev = getattr(settings, "QR_ENCRYPTION_KEY_PREVIOUS", None)
    if prev:
        keys.append(Fernet(prev))
    return MultiFernet(keys)


REQUIRED_DEVOTEE_FIELDS = {"user_type", "devotee_id", "timestamp", "action_type"}
REQUIRED_VOLUNTEER_FIELDS = {"user_type", "volunteer_id", "role", "generated_at"}


def encrypt_payload(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return get_fernet().encrypt(raw).decode("utf-8")


def _decrypt_raw(encrypted_data: str, *, max_age_seconds: int | None) -> bytes:
    """Two-step decrypt so 'tampered' and 'expired' produce distinct errors,
    even though Fernet's own ttl-decrypt raises InvalidToken for both:

    1. Decrypt with no ttl — this only checks the HMAC signature. If this
       fails, the token itself is bad (wrong key, corrupted, or tampered).
    2. If step 1 succeeds but max_age_seconds was given, decrypt again with
       ttl enforced. Since the signature is already known-good, a failure
       here can only be due to the embedded timestamp being too old.
    """
    fernet = get_fernet()
    try:
        raw = fernet.decrypt(encrypted_data.encode("utf-8"))
    except InvalidToken:
        raise QRInvalidError("QR signature invalid or tampered.")

    if max_age_seconds is not None:
        try:
            fernet.decrypt(encrypted_data.encode("utf-8"), ttl=max_age_seconds)
        except InvalidToken:
            raise QRExpiredError("QR token has expired.")

    return raw


def decrypt_payload(encrypted_data: str, *, max_age_seconds: int | None = None) -> dict:
    if not encrypted_data or not isinstance(encrypted_data, str):
        raise QRInvalidError("Missing or invalid encrypted_data.")

    raw = _decrypt_raw(encrypted_data, max_age_seconds=max_age_seconds)

    try:
        payload = json.loads(raw)
    except (ValueError, TypeError):
        raise QRDecryptionError("QR payload is not valid JSON.")

    if not isinstance(payload, dict) or "user_type" not in payload:
        raise QRDecryptionError("QR payload missing user_type.")

    if payload["user_type"] == "devotee":
        missing = REQUIRED_DEVOTEE_FIELDS - payload.keys()
    elif payload["user_type"] == "volunteer":
        missing = REQUIRED_VOLUNTEER_FIELDS - payload.keys()
    else:
        raise QRDecryptionError(f"Unknown user_type: {payload['user_type']!r}")
    if missing:
        raise QRDecryptionError(f"QR payload missing required fields: {sorted(missing)}")

    return payload