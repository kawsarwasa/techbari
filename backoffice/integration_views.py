from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Exists, OuterRef
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from integrations.delivery import process_outbound
from integrations.forms import IntegrationSettingsForm
from integrations.models import Notification, NotificationRead, OutboundMessage
from integrations.services import get_integration_settings, mark_all_notifications_read, mark_notification_read
from shipping.models import CourierProvider


def notifications(request):
    qs = Notification.objects.annotate(
        is_read_for_user=Exists(NotificationRead.objects.filter(notification_id=OuterRef("pk"), user=request.user))
    )
    kind = str(request.GET.get("kind") or "").strip()
    state = str(request.GET.get("state") or "").strip()
    if kind in {value for value, _ in Notification.Kind.choices}:
        qs = qs.filter(kind=kind)
    if state == "unread":
        qs = qs.filter(is_read_for_user=False)
    elif state == "read":
        qs = qs.filter(is_read_for_user=True)
    page_obj = Paginator(qs, 30).get_page(request.GET.get("page"))
    return render(request, "backoffice/pages/notifications/notifications.html", {
        "notifications": page_obj.object_list,
        "page_obj": page_obj,
        "notification_kinds": Notification.Kind.choices,
        "selected_kind": kind,
        "selected_state": state,
    })


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
            return redirect("backoffice:integration_settings")
    else:
        form = IntegrationSettingsForm(instance=config)
    recent = OutboundMessage.objects.order_by("-created_at")[:40]
    couriers = CourierProvider.objects.filter(api_enabled=True).order_by("name")
    return render(request, "backoffice/pages/settings/integrations.html", {
        "form": form,
        "integration_settings": config,
        "recent_deliveries": recent,
        "api_couriers": couriers,
    })


@require_POST
def integration_retry(request, message_id):
    outbound = get_object_or_404(OutboundMessage, pk=message_id)
    if outbound.status != OutboundMessage.Status.SENT:
        outbound.status = OutboundMessage.Status.PENDING
        outbound.available_at = timezone.now()
        outbound.last_error = ""
        outbound.save(update_fields=["status", "available_at", "last_error", "updated_at"])
        messages.success(request, "Delivery queued for retry.")
    return redirect("backoffice:integration_settings")


@require_POST
def integration_process(request):
    result = process_outbound(limit=20)
    messages.success(request, f"Processed integrations: {result['sent']} sent, {result['failed']} failed, {result['skipped']} skipped.")
    return redirect("backoffice:integration_settings")
