from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Exists, OuterRef
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from integrations.delivery import process_outbound
from integrations.forms import IntegrationSettingsForm
from integrations.models import Notification, NotificationRead, OutboundMessage
from integrations.services import get_integration_settings, mark_all_notifications_read, mark_notification_read
from payments.models import PaymentTransaction
from sales.models import SalesOrder
from shipping.models import CourierProvider, Shipment


_TRACKED_NOTIFICATION_TARGETS = {"sales_order", "payment", "shipment"}


def _notification_target_exists(notification):
    reference_type = str(notification.reference_type or "").strip()
    reference_id = str(notification.reference_id or "").strip()
    if reference_type not in _TRACKED_NOTIFICATION_TARGETS:
        return True
    if not reference_id:
        return False
    if reference_type == "sales_order":
        return SalesOrder.objects.filter(order_number=reference_id).exists()
    if reference_type == "payment":
        return PaymentTransaction.objects.filter(transaction_no=reference_id).exists()
    return Shipment.objects.filter(shipment_no=reference_id).exists()


def _mark_notification_target_availability(notifications):
    rows = list(notifications)
    references = {target: set() for target in _TRACKED_NOTIFICATION_TARGETS}
    for notification in rows:
        reference_type = str(notification.reference_type or "").strip()
        reference_id = str(notification.reference_id or "").strip()
        if reference_type in references and reference_id:
            references[reference_type].add(reference_id)

    available = {
        "sales_order": set(SalesOrder.objects.filter(order_number__in=references["sales_order"]).values_list("order_number", flat=True)),
        "payment": set(PaymentTransaction.objects.filter(transaction_no__in=references["payment"]).values_list("transaction_no", flat=True)),
        "shipment": set(Shipment.objects.filter(shipment_no__in=references["shipment"]).values_list("shipment_no", flat=True)),
    }
    for notification in rows:
        reference_type = str(notification.reference_type or "").strip()
        reference_id = str(notification.reference_id or "").strip()
        notification.target_available = reference_type not in _TRACKED_NOTIFICATION_TARGETS or (
            bool(reference_id) and reference_id in available[reference_type]
        )
    return rows


def notifications(request):
    qs = Notification.objects.annotate(is_read_for_user=Exists(NotificationRead.objects.filter(notification_id=OuterRef("pk"), user=request.user)))
    kind = str(request.GET.get("kind") or "").strip()
    state = str(request.GET.get("state") or "").strip()
    if kind in {value for value, _ in Notification.Kind.choices}:
        qs = qs.filter(kind=kind)
    if state == "unread":
        qs = qs.filter(is_read_for_user=False)
    elif state == "read":
        qs = qs.filter(is_read_for_user=True)
    page_obj = Paginator(qs, 30).get_page(request.GET.get("page"))
    notification_rows = _mark_notification_target_availability(page_obj.object_list)
    return render(request, "backoffice/pages/notifications/notifications.html", {"notifications": notification_rows, "page_obj": page_obj, "notification_kinds": Notification.Kind.choices, "selected_kind": kind, "selected_state": state})


def notification_open(request, notification_id):
    notification = get_object_or_404(Notification, pk=notification_id)
    link = str(notification.link or "").strip()
    if not link or not _notification_target_exists(notification):
        messages.warning(request, "This notification points to a record that is no longer available.")
        return redirect("backoffice:notifications")
    if not url_has_allowed_host_and_scheme(link, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        messages.warning(request, "This notification link is not available.")
        return redirect("backoffice:notifications")
    return redirect(link)


@require_POST
def notification_read(request, notification_id):
    notification = get_object_or_404(Notification, pk=notification_id)
    mark_notification_read(notification, request.user)
    next_url = str(request.POST.get("next") or reverse("backoffice:notifications"))
    return redirect(next_url if next_url.startswith("/") else reverse("backoffice:notifications"))


@require_POST
def notifications_read_all(request):
    count = mark_all_notifications_read(request.user)
    messages.success(request, f"Marked {count} notification(s) as read.")
    return redirect("backoffice:notifications")


def integration_settings(request):
    config = get_integration_settings()
    if request.method == "POST":
        form = IntegrationSettingsForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, "Notification and integration settings saved.")
            return redirect("integration_admin:integration_settings")
    else:
        form = IntegrationSettingsForm(instance=config)
    return render(request, "backoffice/pages/settings/integrations.html", {"form": form, "integration_settings": config, "recent_deliveries": OutboundMessage.objects.order_by("-created_at")[:40], "api_couriers": CourierProvider.objects.filter(api_enabled=True).order_by("name")})


@require_POST
def integration_retry(request, message_id):
    outbound = get_object_or_404(OutboundMessage, pk=message_id)
    if outbound.status != OutboundMessage.Status.SENT:
        outbound.status = OutboundMessage.Status.PENDING
        outbound.available_at = timezone.now()
        outbound.last_error = ""
        outbound.save(update_fields=["status", "available_at", "last_error", "updated_at"])
        messages.success(request, "Delivery queued for retry.")
    return redirect("integration_admin:integration_settings")


@require_POST
def integration_process(request):
    result = process_outbound(limit=20)
    messages.success(request, f"Processed integrations: {result['sent']} sent, {result['failed']} failed, {result['skipped']} skipped.")
    return redirect("integration_admin:integration_settings")
