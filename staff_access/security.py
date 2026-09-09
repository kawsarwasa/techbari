import hashlib
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import AuthThrottle
from .services import get_client_ip


def _key_hash(scope, request, identity):
    ip = get_client_ip(request) or "unknown"
    normalized = " ".join(str(identity or "").strip().lower().split())[:254]
    raw = f"{scope}|{ip}|{normalized}".encode("utf-8", errors="ignore")
    return hashlib.sha256(raw).hexdigest()


def throttle_seconds_remaining(scope, request, identity):
    row = AuthThrottle.objects.filter(scope=scope, key_hash=_key_hash(scope, request, identity)).first()
    if not row or not row.locked_until:
        return 0
    seconds = int((row.locked_until - timezone.now()).total_seconds())
    return max(seconds, 0)


@transaction.atomic
def register_auth_failure(scope, request, identity):
    now = timezone.now()
    key_hash = _key_hash(scope, request, identity)
    row, _ = AuthThrottle.objects.select_for_update().get_or_create(
        scope=scope,
        key_hash=key_hash,
        defaults={"window_started_at": now},
    )
    window_seconds = int(getattr(settings, "AUTH_FAILURE_WINDOW", 900))
    failure_limit = int(getattr(settings, "AUTH_FAILURE_LIMIT", 5))
    lockout_seconds = int(getattr(settings, "AUTH_LOCKOUT_SECONDS", 900))

    if (now - row.window_started_at).total_seconds() > window_seconds:
        row.failures = 0
        row.window_started_at = now
        row.locked_until = None

    row.failures += 1
    if row.failures >= failure_limit:
        row.locked_until = now + timedelta(seconds=lockout_seconds)
    row.save(update_fields=["failures", "window_started_at", "locked_until", "updated_at"])
    return max(int((row.locked_until - now).total_seconds()), 0) if row.locked_until else 0


@transaction.atomic
def clear_auth_throttle(scope, request, identity):
    AuthThrottle.objects.filter(scope=scope, key_hash=_key_hash(scope, request, identity)).delete()
