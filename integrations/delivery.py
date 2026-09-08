import json
import os
from datetime import timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from .models import OutboundMessage
from .services import enqueue_integration_failure, get_integration_settings


class DeliveryError(Exception):
    pass


def _secret(name):
    return str(os.getenv(name, "") or "").strip()


def _safe_error(exc):
    if isinstance(exc, HTTPError):
        return f"HTTP {exc.code}: {exc.reason}"[:1000]
    if isinstance(exc, URLError):
        return f"Network error: {exc.reason}"[:1000]
    text = str(exc)
    for env_name in ("META_CAPI_ACCESS_TOKEN", "GA4_API_SECRET", "SMS_API_TOKEN", "WHATSAPP_API_TOKEN", "COURIER_API_TOKEN"):
        value = _secret(env_name)
        if value:
            text = text.replace(value, "***")
    return text[:1000]


def _http_json(url, payload, *, token="", timeout=12, headers=None):
    request_headers = {"Content-Type": "application/json", "Accept": "application/json", **(headers or {})}
    if token:
        request_headers["Authorization"] = f"Bearer {token}"
    request = Request(url, data=json.dumps(payload, separators=(",", ":")).encode("utf-8"), headers=request_headers, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            if response.status < 200 or response.status >= 300:
                raise DeliveryError(f"HTTP {response.status}")
            if not raw.strip():
                return {}
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {"raw": raw[:1000]}
    except (HTTPError, URLError, TimeoutError) as exc:
        raise DeliveryError(_safe_error(exc)) from exc


def _deliver_email(message):
    if not message.recipient:
        raise DeliveryError("Email recipient is missing.")
    send_mail(message.subject or "TechBari notification", message.body, settings.DEFAULT_FROM_EMAIL, [message.recipient], fail_silently=False)


def _deliver_webhook(message, *, token_env):
    url = str(message.payload.get("url") or "").strip()
    if not url:
        raise DeliveryError("Webhook URL is not configured.")
    token = _secret(token_env)
    _http_json(url, {"to": message.recipient, "message": message.body, "event_type": message.event_type, "reference": message.reference_id}, token=token)


def _deliver_meta(message):
    config = get_integration_settings()
    token = _secret("META_CAPI_ACCESS_TOKEN")
    pixel_id = str(message.payload.get("pixel_id") or config.meta_pixel_id or "").strip()
    if not token or not pixel_id:
        raise DeliveryError("Meta CAPI token or Pixel ID is not configured.")
    version = _secret("META_GRAPH_API_VERSION").strip("/")
    base = str(os.getenv("META_CAPI_BASE_URL", "https://graph.facebook.com") or "https://graph.facebook.com").rstrip("/")
    path = f"/{version}/{pixel_id}/events" if version else f"/{pixel_id}/events"
    url = base + path + "?" + urlencode({"access_token": token})
    _http_json(url, {"data": [message.payload["event"]]})


def _deliver_ga4(message):
    config = get_integration_settings()
    secret = _secret("GA4_API_SECRET")
    measurement_id = str(message.payload.get("measurement_id") or config.ga4_measurement_id or "").strip()
    if not secret or not measurement_id:
        raise DeliveryError("GA4 API secret or Measurement ID is not configured.")
    endpoint = str(os.getenv("GA4_MEASUREMENT_PROTOCOL_URL", "https://www.google-analytics.com/mp/collect") or "").strip()
    url = endpoint + "?" + urlencode({"measurement_id": measurement_id, "api_secret": secret})
    body = {"client_id": message.payload.get("client_id"), "events": message.payload.get("events", [])}
    _http_json(url, body)


def _deliver_courier(message):
    from shipping.models import Shipment
    from shipping.services import update_tracking

    payload = message.payload or {}
    shipment = Shipment.objects.select_related("courier", "order").get(pk=payload["shipment_id"])
    base = str(payload.get("api_base_url") or shipment.courier.api_base_url or "").strip()
    if not base:
        raise DeliveryError("Courier API base URL is not configured.")
    path = str(payload.get("api_create_path") or shipment.courier.api_create_path or "/shipments")
    url = urljoin(base.rstrip("/") + "/", path.lstrip("/"))
    token_env = str(payload.get("token_env") or shipment.courier.api_token_env or f"COURIER_API_TOKEN_{shipment.courier.code}")
    token = _secret(token_env) or _secret("COURIER_API_TOKEN")
    response = _http_json(url, {"shipment_no": shipment.shipment_no, **(payload.get("order") or {})}, token=token, headers={"X-TechBari-Courier": shipment.courier.code})
    tracking_id = str(response.get("tracking_id") or response.get("tracking_code") or "").strip()
    courier_reference = str(response.get("reference") or response.get("consignment_id") or "").strip()
    if tracking_id or courier_reference:
        update_tracking(shipment=shipment, tracking_id=tracking_id or shipment.tracking_id, courier_reference=courier_reference or shipment.courier_reference, note="Courier API booking response.", actor="Integration")


def deliver_message(message):
    if message.channel == OutboundMessage.Channel.EMAIL:
        return _deliver_email(message)
    if message.channel == OutboundMessage.Channel.SMS:
        return _deliver_webhook(message, token_env="SMS_API_TOKEN")
    if message.channel == OutboundMessage.Channel.WHATSAPP:
        return _deliver_webhook(message, token_env="WHATSAPP_API_TOKEN")
    if message.channel == OutboundMessage.Channel.META_CAPI:
        return _deliver_meta(message)
    if message.channel == OutboundMessage.Channel.GA4:
        return _deliver_ga4(message)
    if message.channel == OutboundMessage.Channel.COURIER:
        return _deliver_courier(message)
    raise DeliveryError("Unsupported integration channel.")


def process_outbound(*, limit=100, max_attempts=5):
    limit = max(1, min(int(limit or 100), 500))
    now = timezone.now()
    ids = list(
        OutboundMessage.objects.filter(status__in=[OutboundMessage.Status.PENDING, OutboundMessage.Status.FAILED], attempts__lt=max_attempts, available_at__lte=now)
        .order_by("available_at", "id")
        .values_list("id", flat=True)[:limit]
    )
    summary = {"sent": 0, "failed": 0, "skipped": 0}
    for pk in ids:
        with transaction.atomic():
            message = OutboundMessage.objects.select_for_update().get(pk=pk)
            if message.status == OutboundMessage.Status.SENT or message.attempts >= max_attempts or message.available_at > timezone.now():
                summary["skipped"] += 1
                continue
            message.attempts += 1
            message.last_attempt_at = timezone.now()
            try:
                deliver_message(message)
            except Exception as exc:
                error_text = _safe_error(exc)
                message.status = OutboundMessage.Status.FAILED
                message.last_error = error_text
                delay = min(60 * (2 ** max(message.attempts - 1, 0)), 3600)
                message.available_at = timezone.now() + timedelta(seconds=delay)
                message.save(update_fields=["attempts", "last_attempt_at", "status", "last_error", "available_at", "updated_at"])
                enqueue_integration_failure(message, error_text)
                summary["failed"] += 1
            else:
                message.status = OutboundMessage.Status.SENT
                message.sent_at = timezone.now()
                message.last_error = ""
                message.save(update_fields=["attempts", "last_attempt_at", "status", "sent_at", "last_error", "updated_at"])
                summary["sent"] += 1
    return summary
