import hashlib
import re
from decimal import Decimal

from django.db import IntegrityError
from django.urls import reverse
from django.utils import timezone

from .models import IntegrationSettings, Notification, NotificationRead, OutboundMessage


def get_integration_settings():
    obj, _ = IntegrationSettings.objects.get_or_create(singleton_key=1)
    return obj


def public_tracking_config():
    config = get_integration_settings()
    return {
        "meta_pixel_enabled": bool(config.meta_pixel_enabled and config.meta_pixel_id),
        "meta_pixel_id": config.meta_pixel_id if config.meta_pixel_enabled else "",
        "ga4_enabled": bool(config.ga4_enabled and config.ga4_measurement_id),
        "ga4_measurement_id": config.ga4_measurement_id if config.ga4_enabled else "",
    }


def _notification(*, kind, severity, title, message, link="", reference_type="", reference_id="", dedupe_key=None):
    defaults = {
        "kind": kind,
        "severity": severity,
        "title": str(title)[:180],
        "message": str(message)[:500],
        "link": str(link or "")[:500],
        "reference_type": str(reference_type or "")[:50],
        "reference_id": str(reference_id or "")[:100],
    }
    if dedupe_key:
        obj, _ = Notification.objects.get_or_create(dedupe_key=str(dedupe_key)[:220], defaults=defaults)
        return obj
    return Notification.objects.create(**defaults)


def unread_notifications_for(user):
    if not getattr(user, "is_authenticated", False):
        return Notification.objects.none()
    return Notification.objects.exclude(reads__user=user)


def mark_notification_read(notification, user):
    return NotificationRead.objects.get_or_create(notification=notification, user=user)


def mark_all_notifications_read(user):
    unread_ids = list(unread_notifications_for(user).values_list("id", flat=True))
    if not unread_ids:
        return 0
    existing = set(NotificationRead.objects.filter(user=user, notification_id__in=unread_ids).values_list("notification_id", flat=True))
    rows = [NotificationRead(notification_id=pk, user=user) for pk in unread_ids if pk not in existing]
    NotificationRead.objects.bulk_create(rows, ignore_conflicts=True)
    return len(rows)


def _outbound(*, channel, event_type, idempotency_key, recipient="", subject="", body="", payload=None, reference_type="", reference_id=""):
    defaults = {
        "channel": channel,
        "event_type": event_type,
        "recipient": str(recipient or "")[:500],
        "subject": str(subject or "")[:255],
        "body": str(body or ""),
        "payload": payload or {},
        "reference_type": str(reference_type or "")[:50],
        "reference_id": str(reference_id or "")[:100],
    }
    try:
        obj, _ = OutboundMessage.objects.get_or_create(idempotency_key=str(idempotency_key)[:220], defaults=defaults)
        return obj
    except IntegrityError:
        return OutboundMessage.objects.get(idempotency_key=str(idempotency_key)[:220])


def _normalize_phone(phone):
    digits = "".join(ch for ch in str(phone or "") if ch.isdigit())
    if digits.startswith("880"):
        return "+" + digits
    if digits.startswith("01") and len(digits) == 11:
        return "+88" + digits
    return "+" + digits if digits else ""


def _sha256(value):
    text = str(value or "").strip().lower()
    return hashlib.sha256(text.encode("utf-8")).hexdigest() if text else ""


def _order_customer_channels(order, config, event_type, subject, body):
    reference_id = order.order_number
    email = str(order.shipping_email or "").strip()
    phone = _normalize_phone(order.shipping_phone)
    if config.email_enabled and email:
        _outbound(channel=OutboundMessage.Channel.EMAIL, event_type=event_type, idempotency_key=f"email:{event_type}:{reference_id}", recipient=email, subject=subject, body=body, reference_type="sales_order", reference_id=reference_id)
    if config.sms_enabled and phone and config.sms_webhook_url:
        _outbound(channel=OutboundMessage.Channel.SMS, event_type=event_type, idempotency_key=f"sms:{event_type}:{reference_id}", recipient=phone, body=body, payload={"url": config.sms_webhook_url}, reference_type="sales_order", reference_id=reference_id)
    if config.whatsapp_enabled and phone and config.whatsapp_webhook_url:
        _outbound(channel=OutboundMessage.Channel.WHATSAPP, event_type=event_type, idempotency_key=f"whatsapp:{event_type}:{reference_id}", recipient=phone, body=body, payload={"url": config.whatsapp_webhook_url}, reference_type="sales_order", reference_id=reference_id)


def _purchase_payload(order):
    items = []
    for item in order.items.all():
        items.append({
            "item_id": item.sku_snapshot,
            "item_name": item.product_snapshot,
            "item_variant": item.variant_snapshot,
            "price": float(item.unit_price),
            "quantity": int(item.quantity),
        })
    return items


def _enqueue_purchase_analytics(order, config):
    if order.channel != order.Channel.ONLINE or order.status == order.Status.DRAFT:
        return
    event_id = f"tb-purchase-{order.order_number}"
    items = _purchase_payload(order)
    if config.meta_capi_enabled and config.meta_pixel_enabled and config.meta_pixel_id:
        user_data = {}
        email_hash = _sha256(order.shipping_email)
        phone_hash = _sha256(_normalize_phone(order.shipping_phone))
        if email_hash:
            user_data["em"] = [email_hash]
        if phone_hash:
            user_data["ph"] = [phone_hash]
        payload = {
            "pixel_id": config.meta_pixel_id,
            "event": {
                "event_name": "Purchase",
                "event_time": int(timezone.now().timestamp()),
                "event_id": event_id,
                "action_source": "website",
                "user_data": user_data,
                "custom_data": {
                    "currency": "BDT",
                    "value": float(order.grand_total or Decimal("0.00")),
                    "order_id": order.order_number,
                    "contents": [{"id": row["item_id"], "quantity": row["quantity"], "item_price": row["price"]} for row in items],
                    "content_type": "product",
                },
            },
        }
        _outbound(channel=OutboundMessage.Channel.META_CAPI, event_type="purchase", idempotency_key=f"meta:purchase:{order.order_number}", payload=payload, reference_type="sales_order", reference_id=order.order_number)
    if config.ga4_server_enabled and config.ga4_enabled and config.ga4_measurement_id:
        payload = {
            "measurement_id": config.ga4_measurement_id,
            "client_id": f"{order.pk}.{int(order.created_at.timestamp()) if order.created_at else int(timezone.now().timestamp())}",
            "events": [{
                "name": "purchase",
                "params": {
                    "transaction_id": order.order_number,
                    "currency": "BDT",
                    "value": float(order.grand_total or Decimal("0.00")),
                    "shipping": float(order.shipping_charge or Decimal("0.00")),
                    "items": items,
                },
            }],
        }
        _outbound(channel=OutboundMessage.Channel.GA4, event_type="purchase", idempotency_key=f"ga4:purchase:{order.order_number}", payload=payload, reference_type="sales_order", reference_id=order.order_number)


def enqueue_order_event(order, event_type):
    config = get_integration_settings()
    event_type = str(event_type or "updated")
    link = reverse("backoffice:order_detail_id", args=[order.pk])
    label = order.get_status_display()
    severity = Notification.Severity.SUCCESS if order.status == order.Status.COMPLETED else Notification.Severity.WARNING if order.status == order.Status.CANCELLED else Notification.Severity.INFO
    if config.notify_order_events:
        _notification(kind=Notification.Kind.ORDER, severity=severity, title=f"Order {order.order_number}: {label}", message=f"{order.customer_name} · ৳ {order.grand_total:.2f}", link=link, reference_type="sales_order", reference_id=order.order_number, dedupe_key=f"order:{event_type}:{order.order_number}")
        if order.status != order.Status.DRAFT:
            body = f"TechBari order {order.order_number} is {label}. Total: ৳ {order.grand_total:.2f}."
            _order_customer_channels(order, config, f"order_{event_type}", f"TechBari order {order.order_number}", body)
    if event_type == "created":
        _enqueue_purchase_analytics(order, config)


def enqueue_payment_event(payment, event_type="completed"):
    config = get_integration_settings()
    if not config.notify_payment_events:
        return
    order = payment.sales_order
    reference = payment.transaction_no
    link = reverse("backoffice:payment_detail", args=[payment.pk])
    severity = Notification.Severity.SUCCESS if payment.status == payment.Status.COMPLETED else Notification.Severity.WARNING
    _notification(kind=Notification.Kind.PAYMENT, severity=severity, title=f"Payment {payment.get_status_display()}", message=f"{reference} · ৳ {payment.amount:.2f}" + (f" · {order.order_number}" if order else ""), link=link, reference_type="payment", reference_id=reference, dedupe_key=f"payment:{event_type}:{reference}")
    if order and payment.status == payment.Status.COMPLETED:
        body = f"Payment received for TechBari order {order.order_number}: ৳ {payment.amount:.2f}."
        _order_customer_channels(order, config, f"payment_{reference}", f"Payment received - {order.order_number}", body)


def enqueue_low_stock_event(balance):
    config = get_integration_settings()
    if not config.notify_low_stock or not balance.is_low_stock:
        return
    balance = type(balance).objects.select_related("variant__product", "warehouse").get(pk=balance.pk)
    available = balance.available_quantity
    today = timezone.localdate().isoformat()
    severity = Notification.Severity.DANGER if available == 0 else Notification.Severity.WARNING
    _notification(kind=Notification.Kind.STOCK, severity=severity, title="Out of stock" if available == 0 else "Low stock", message=f"{balance.variant.product.name} / {balance.variant.sku}: {available} available at {balance.warehouse.name}", link=reverse("backoffice:inventory_low_stock"), reference_type="inventory_balance", reference_id=str(balance.pk), dedupe_key=f"stock:{balance.pk}:{today}:{available}")
    if config.email_enabled and config.admin_email:
        _outbound(channel=OutboundMessage.Channel.EMAIL, event_type="low_stock", idempotency_key=f"email:stock:{balance.pk}:{today}:{available}", recipient=config.admin_email, subject=f"TechBari stock alert: {balance.variant.sku}", body=f"{balance.variant.product.name} / {balance.variant.sku} has {available} available at {balance.warehouse.name}.", reference_type="inventory_balance", reference_id=str(balance.pk))


def enqueue_shipping_event(shipment, event_type="updated"):
    config = get_integration_settings()
    if config.notify_shipping_events:
        severity = Notification.Severity.SUCCESS if shipment.status == shipment.Status.DELIVERED else Notification.Severity.WARNING if shipment.status in {shipment.Status.FAILED, shipment.Status.RETURNING, shipment.Status.RETURNED} else Notification.Severity.INFO
        _notification(kind=Notification.Kind.SHIPPING, severity=severity, title=f"Shipment {shipment.get_status_display()}", message=f"{shipment.shipment_no} · {shipment.order.order_number} · {shipment.courier.name}", link=reverse("backoffice:shipment_detail", args=[shipment.pk]), reference_type="shipment", reference_id=shipment.shipment_no, dedupe_key=f"shipment:{event_type}:{shipment.shipment_no}")
        if shipment.order and shipment.order.status != shipment.order.Status.DRAFT:
            body = f"TechBari shipment for order {shipment.order.order_number}: {shipment.get_status_display()}."
            if shipment.tracking_id:
                body += f" Tracking: {shipment.tracking_id}."
            _order_customer_channels(shipment.order, config, f"shipping_{event_type}_{shipment.shipment_no}", f"Shipping update - {shipment.order.order_number}", body)
    if event_type == "created" and config.courier_api_enabled and shipment.courier.api_enabled and shipment.courier.api_base_url:
        payload = {
            "shipment_id": shipment.pk,
            "shipment_no": shipment.shipment_no,
            "courier_code": shipment.courier.code,
            "api_base_url": shipment.courier.api_base_url,
            "api_create_path": shipment.courier.api_create_path,
            "token_env": shipment.courier.api_token_env or f"COURIER_API_TOKEN_{shipment.courier.code}",
            "order": {
                "order_number": shipment.order.order_number,
                "recipient_name": shipment.order.shipping_name,
                "recipient_phone": shipment.order.shipping_phone,
                "recipient_email": shipment.order.shipping_email,
                "address": shipment.order.shipping_summary,
                "cod_amount": float(shipment.cod_expected),
                "parcel_count": shipment.parcel_count,
                "weight_kg": float(shipment.weight_kg),
            },
        }
        _outbound(channel=OutboundMessage.Channel.COURIER, event_type="create_shipment", idempotency_key=f"courier:create:{shipment.shipment_no}", recipient=shipment.courier.api_base_url, payload=payload, reference_type="shipment", reference_id=shipment.shipment_no)


def enqueue_integration_failure(message, error_text):
    key = f"integration-failure:{message.pk}:{message.attempts}"
    _notification(kind=Notification.Kind.INTEGRATION, severity=Notification.Severity.DANGER, title=f"Integration delivery failed: {message.get_channel_display()}", message=str(error_text)[:500], link=reverse("backoffice:integration_settings"), reference_type="outbound_message", reference_id=str(message.pk), dedupe_key=key)
