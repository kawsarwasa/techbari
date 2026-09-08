import hashlib
import hmac
import json
import os

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from shipping.models import CourierProvider, Shipment
from shipping.services import ShippingError, change_shipment_status, update_tracking


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
    env_name = provider.api_webhook_secret_env or f"COURIER_WEBHOOK_SECRET_{provider.code}"
    return str(os.getenv(env_name, "") or os.getenv("COURIER_WEBHOOK_SECRET", "") or "").strip()


@csrf_exempt
@require_POST
def courier_webhook(request, code):
    provider = CourierProvider.objects.filter(code__iexact=code, is_active=True, api_enabled=True).first()
    if provider is None:
        return JsonResponse({"ok": False, "error": "Courier integration not found."}, status=404)
    secret = _secret_for(provider)
    if not secret:
        return JsonResponse({"ok": False, "error": "Courier webhook is not configured."}, status=503)
    supplied = str(request.headers.get("X-TechBari-Signature", "")).strip()
    if supplied.lower().startswith("sha256="):
        supplied = supplied.split("=", 1)[1]
    expected = hmac.new(secret.encode("utf-8"), request.body, hashlib.sha256).hexdigest()
    if not supplied or not hmac.compare_digest(supplied, expected):
        return JsonResponse({"ok": False, "error": "Invalid signature."}, status=401)
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"ok": False, "error": "Invalid JSON."}, status=400)
    tracking_id = str(payload.get("tracking_id") or payload.get("tracking_code") or "").strip()
    reference = str(payload.get("reference") or payload.get("consignment_id") or "").strip()
    if not tracking_id and not reference:
        return JsonResponse({"ok": False, "error": "tracking_id or reference is required."}, status=400)
    qs = Shipment.objects.select_related("courier", "order").filter(courier=provider)
    shipment = qs.filter(tracking_id=tracking_id).first() if tracking_id else None
    if shipment is None and reference:
        shipment = qs.filter(courier_reference=reference).first()
    if shipment is None:
        return JsonResponse({"ok": False, "error": "Shipment not found."}, status=404)
    status = STATUS_ALIASES.get(str(payload.get("status") or "").strip().lower())
    location = str(payload.get("location") or "").strip()
    note = str(payload.get("note") or "Courier webhook update.").strip()
    try:
        if tracking_id != shipment.tracking_id or (reference and reference != shipment.courier_reference) or (location and not status):
            shipment = update_tracking(shipment=shipment, tracking_id=tracking_id or shipment.tracking_id, courier_reference=reference or shipment.courier_reference, location=location, note=note, actor=f"Courier:{provider.code}")
        if status and status != shipment.status:
            shipment = change_shipment_status(shipment=shipment, new_status=status, cod_collected=payload.get("cod_collected"), location=location, failure_reason=payload.get("failure_reason") or "", note=note, actor=f"Courier:{provider.code}")
    except ShippingError as exc:
        return JsonResponse({"ok": False, "error": " ".join(getattr(exc, "messages", [str(exc)]))}, status=409)
    return JsonResponse({"ok": True, "shipment": shipment.shipment_no, "status": shipment.status, "tracking_id": shipment.tracking_id})
