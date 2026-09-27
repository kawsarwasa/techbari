import base64
import hashlib
import hmac
import io
import secrets
import time
from urllib.parse import quote, urlencode

import qrcode
import qrcode.image.svg
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac

from .models import StaffMFADevice


TOTP_STEP_SECONDS = 30
TOTP_DIGITS = 6
RECOVERY_CODE_COUNT = 10


def _fernet():
    configured = str(getattr(settings, "STAFF_MFA_ENCRYPTION_KEY", "") or "").strip()
    if configured:
        try:
            return Fernet(configured.encode("ascii"))
        except (ValueError, TypeError) as exc:
            raise ValueError("STAFF_MFA_ENCRYPTION_KEY is invalid.") from exc

    # Development fallback only. Production preflight requires a dedicated key
    # so rotating DJANGO_SECRET_KEY does not destroy enrolled TOTP devices.
    material = hashlib.sha256(
        (settings.SECRET_KEY + "|techbari-staff-mfa-v1").encode("utf-8")
    ).digest()
    return Fernet(base64.urlsafe_b64encode(material))


def encrypt_secret(secret):
    return _fernet().encrypt(secret.encode("ascii")).decode("ascii")


def decrypt_secret(device):
    try:
        return _fernet().decrypt(device.encrypted_secret.encode("ascii")).decode("ascii")
    except (InvalidToken, ValueError, TypeError) as exc:
        raise ValueError("Stored MFA secret could not be decrypted.") from exc


def generate_secret():
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def get_or_create_mfa_device(user):
    device, _created = StaffMFADevice.objects.get_or_create(
        user=user,
        defaults={"encrypted_secret": encrypt_secret(generate_secret())},
    )
    return device


def mfa_enabled(user):
    if not getattr(user, "is_authenticated", False):
        return False
    return StaffMFADevice.objects.filter(user=user, is_enabled=True).exists()


def _decode_secret(secret):
    padded = secret + "=" * ((8 - len(secret) % 8) % 8)
    return base64.b32decode(padded, casefold=True)


def _totp_for_counter(secret, counter):
    digest = hmac.new(
        _decode_secret(secret),
        int(counter).to_bytes(8, "big"),
        hashlib.sha1,
    ).digest()
    offset = digest[-1] & 0x0F
    binary = int.from_bytes(digest[offset : offset + 4], "big") & 0x7FFFFFFF
    return str(binary % (10 ** TOTP_DIGITS)).zfill(TOTP_DIGITS)


def current_totp_code(secret, *, for_time=None):
    now = int(time.time() if for_time is None else for_time)
    return _totp_for_counter(secret, now // TOTP_STEP_SECONDS)


def _matching_counter(secret, code, *, for_time=None, window=1):
    normalized = "".join(ch for ch in str(code or "") if ch.isdigit())
    if len(normalized) != TOTP_DIGITS:
        return None
    now = int(time.time() if for_time is None else for_time)
    current = now // TOTP_STEP_SECONDS
    for offset in range(-int(window), int(window) + 1):
        candidate = current + offset
        if candidate >= 0 and hmac.compare_digest(
            _totp_for_counter(secret, candidate),
            normalized,
        ):
            return candidate
    return None


def _normalize_recovery_code(value):
    return "".join(ch for ch in str(value or "").upper() if ch.isalnum())


def _recovery_digest(value):
    hmac_secret = (
        str(getattr(settings, "STAFF_MFA_ENCRYPTION_KEY", "") or "").strip()
        or settings.SECRET_KEY
    )
    return salted_hmac(
        "techbari.staff-mfa-recovery.v1",
        _normalize_recovery_code(value),
        secret=hmac_secret,
        algorithm="sha256",
    ).hexdigest()


def generate_recovery_codes(count=RECOVERY_CODE_COUNT):
    codes = []
    for _ in range(int(count)):
        raw = secrets.token_hex(5).upper()
        codes.append(f"{raw[:5]}-{raw[5:]}")
    return codes


@transaction.atomic
def enable_mfa(user, code):
    device = StaffMFADevice.objects.select_for_update().filter(user=user).first()
    if device is None or device.is_enabled:
        return None
    secret = decrypt_secret(device)
    counter = _matching_counter(secret, code)
    if counter is None:
        return None
    recovery_codes = generate_recovery_codes()
    device.is_enabled = True
    device.last_counter = counter
    device.recovery_code_hashes = [_recovery_digest(value) for value in recovery_codes]
    device.enabled_at = timezone.now()
    device.save(
        update_fields=[
            "is_enabled",
            "last_counter",
            "recovery_code_hashes",
            "enabled_at",
            "updated_at",
        ]
    )
    return recovery_codes


@transaction.atomic
def verify_mfa_code(user, code):
    device = StaffMFADevice.objects.select_for_update().filter(
        user=user,
        is_enabled=True,
    ).first()
    if device is None:
        return False, ""

    secret = decrypt_secret(device)
    counter = _matching_counter(secret, code)
    if counter is not None:
        if counter <= int(device.last_counter):
            return False, ""
        device.last_counter = counter
        device.save(update_fields=["last_counter", "updated_at"])
        return True, "totp"

    digest = _recovery_digest(code)
    hashes = list(device.recovery_code_hashes or [])
    for index, stored in enumerate(hashes):
        if constant_time_compare(str(stored), digest):
            hashes.pop(index)
            device.recovery_code_hashes = hashes
            device.save(update_fields=["recovery_code_hashes", "updated_at"])
            return True, "recovery"
    return False, ""


def provisioning_uri(user, device):
    secret = decrypt_secret(device)
    issuer = str(getattr(settings, "STAFF_MFA_ISSUER", "TechBari") or "TechBari")
    account = user.get_username()
    label = quote(f"{issuer}:{account}", safe="")
    query = urlencode(
        {
            "secret": secret,
            "issuer": issuer,
            "algorithm": "SHA1",
            "digits": TOTP_DIGITS,
            "period": TOTP_STEP_SECONDS,
        }
    )
    return f"otpauth://totp/{label}?{query}"


def qr_svg_bytes(user, device):
    image = qrcode.make(
        provisioning_uri(user, device),
        image_factory=qrcode.image.svg.SvgPathImage,
        box_size=6,
        border=2,
    )
    buffer = io.BytesIO()
    image.save(buffer)
    return buffer.getvalue()


@transaction.atomic
def reset_mfa(user):
    return StaffMFADevice.objects.filter(user=user).delete()[0]
