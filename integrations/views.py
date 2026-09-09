import hashlib
import hmac
import json
import os

from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from shipping.models import CourierProvider, Shipment
from shipping.services import ShippingError, change_shipment_status, update_tracking

from .models import CourierWebhookReceipt


STATUS_ALIASES = {
    "ready": Shipment.Status.READY,
    "handed_over": Shipment.Status.HANDED_OVER,
    "in_transit": Shipment.Status.IN_TRANSIT,
    "out_for_delivery": Shipment.Status.OUT_FOR_DELIVERY,
    "delivered": Shipment.Status.DELIVERED,
    "failed": Shipment.Status.FAILED,
    "returning": Shipment.Status.RETURNING,
    "returned": Shipment.Status.RETURNED,
    "cancelled": Shipment.Status.CANCELLED,
}


def _secret_for(provider):
    return str(os.getenv(f"COURIER_{provider.code}_WEBHOOK_SECRET", "") or os.getenv("COURIER_WEBHOOK_SECRET", "") or "").strip()


def _signed_payload(request, body):
    if not getattr(settings, "COURIER_WEBHOOK_REQUIRE_TIMESTAMP", not settings.DEBUG):
        return body, ""
    timestamp = str(request.headers.get("X-TechBari-Timestamp", "")).strip()
    try:
        sent_at = int(timestamp)
    except (TypeError, ValueError):
        return None, None
    skew = abs(int(timezone.now().timestamp()) - sent_at)
    if skew > int(getattr(settings, "COURIER_WEBHOOK_MAX_SKEW_SECONDS", 300)):
        return None, None
    return timestamp.encode("ascii") + b"." + body, timestamp


@csrf_exempt
@require_POST
def courier_webhook(request, code):
    max_bytes = int(getattr(settings, "COURIER_WEBHOOK_MAX_BYTES", 64 * 1024))
    try:
        content_length = int(request.META.get("CONTENT_LENGTH") or 0)
    except (TypeError, ValueError):
        content_length = 0
    if content_length > max_bytes:
        return JsonResponse({"ok": False, "error": "Webhook payload is too large."}, status=413)

    provider = CourierProvider.objects.filter(code__iexact=code, is_active=True, api_enabled=True).first()
    if provider is None:
        return JsonResponse({"ok": False, "error": "Courier integration not found."}, status=404)
    secret = _secret_for(provider)
    if not secret:
        return JsonResponse({"ok": False, "error": "Courier webhook is not configured."}, status=503)

    body = request.body
    if len(body) > max_bytes:
        return JsonResponse({"ok": False, "error": "Webhook payload is too large."}, status=413)
    signing_payload, timestamp = _signed_payload(request, body)
    if signing_payload is None:
        return JsonResponse({"ok": False, "error": "Missing or stale webhook timestamp."}, status=401)

    supplied = str(request.headers.get("X-TechBari-Signature", "")).strip()
    if supplied.lower().startswith("sha256="):
        supplied = supplied.split("=", 1)[1]
    expected = hmac.new(secret.encode("utf-8"), signing_payload, hashlib.sha256).hexdigest()
    if not supplied or not hmac.compare_digest(supplied, expected):
        return JsonResponse({"ok": False, "error": "Invalid signature."}, status=401)

    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"ok": False, "error": "Invalid JSON."}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"ok": False, "error": "Webhook payload must be a JSON object."}, status=400)

    tracking_id = str(payload.get("tracking_id") or payload.get("tracking_code") or "").strip()
    reference = str(payload.get("reference") or payload.get("consignment_id") or "").strip()
    if not tracking_id and not reference:
        return JsonResponse({"ok": False, "error": "tracking_id or reference is required."}, status=400)

    digest = hashlib.sha256(provider.code.upper().encode("utf-8") + b"|" + signing_payload).hexdigest()
    with transaction.atomic():
        receipt, created = CourierWebhookReceipt.objects.get_or_create(
            digest=digest,
            defaults={"provider_code": provider.code},
        )
        if not created:
            return JsonResponse({"ok": True, "duplicate": True})

        qs = Shipment.objects.select_related("courier", "order").filter(courier=provider)
        shipment = qs.filter(tracking_id=tracking_id).first() if tracking_id else None
        if shipment is None and reference:
            shipment = qs.filter(courier_reference=reference).first()
        if shipment is None:
            transaction.set_rollback(True)
            return JsonResponse({"ok": False, "error": "Shipment not found."}, status=404)

        status = STATUS_ALIASES.get(str(payload.get("status") or "").strip().lower())
        location = str(payload.get("location") or "").strip()[:180]
        note = str(payload.get("note") or "Courier webhook update.").strip()[:500]
        failure_reason = str(payload.get("failure_reason") or "").strip()[:500]
        try:
            if tracking_id != shipment.tracking_id or (reference and reference != shipment.courier_reference) or (location and not status):
                shipment = update_tracking(
                    shipment=shipment,
                    tracking_id=tracking_id or shipment.tracking_id,
                    courier_reference=reference or shipment.courier_reference,
                    location=location,
                    note=note,
                    actor=f"Courier:{provider.code}",
                )
            if status and status != shipment.status:
                shipment = change_shipment_status(
                    shipment=shipment,
                    new_status=status,
                    cod_collected=payload.get("cod_collected"),
                    location=location,
                    failure_reason=failure_reason,
                    note=note,
                    actor=f"Courier:{provider.code}",
                )
        except ShippingError as exc:
            transaction.set_rollback(True)
            return JsonResponse({"ok": False, "error": " ".join(getattr(exc, "messages", [str(exc)]))}, status=409)
        receipt.processed_at = timezone.now()
        receipt.save(update_fields=["processed_at"])

    return JsonResponse({"ok": True, "shipment": shipment.shipment_no, "status": shipment.status, "tracking_id": shipment.tracking_id})
