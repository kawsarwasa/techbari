from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from storefront.models import ContactMessage

from .context import page_context


def _base_context():
    context = page_context("customers")
    context["active_section"] = "contact_messages"
    return context


def contact_messages(request):
    qs = ContactMessage.objects.select_related("handled_by").all()
    query = str(request.GET.get("q") or "").strip()
    status = str(request.GET.get("status") or "").strip()

    if query:
        qs = qs.filter(
            Q(name__icontains=query)
            | Q(email__icontains=query)
            | Q(phone__icontains=query)
            | Q(subject__icontains=query)
            | Q(message__icontains=query)
        )
    if status in {value for value, _ in ContactMessage.Status.choices}:
        qs = qs.filter(status=status)

    counts = {
        "total": ContactMessage.objects.count(),
        "new": ContactMessage.objects.filter(status=ContactMessage.Status.NEW).count(),
        "read": ContactMessage.objects.filter(status=ContactMessage.Status.READ).count(),
        "replied": ContactMessage.objects.filter(status=ContactMessage.Status.REPLIED).count(),
    }
    page_obj = Paginator(qs, 30).get_page(request.GET.get("page"))
    context = _base_context()
    context.update(
        contact_message_rows=page_obj.object_list,
        page_obj=page_obj,
        contact_query=query,
        contact_status=status,
        contact_status_choices=ContactMessage.Status.choices,
        contact_counts=counts,
    )
    return render(request, "backoffice/pages/contact_messages/contact_messages.html", context)


def contact_message_detail(request, message_id):
    contact_message = get_object_or_404(ContactMessage.objects.select_related("handled_by"), pk=message_id)
    context = _base_context()
    context["contact_message"] = contact_message
    return render(request, "backoffice/pages/contact_messages/contact_message_detail.html", context)


@require_POST
def contact_message_status(request, message_id):
    contact_message = get_object_or_404(ContactMessage, pk=message_id)
    status = str(request.POST.get("status") or "").strip()
    if status not in {value for value, _ in ContactMessage.Status.choices}:
        messages.error(request, "Invalid contact message status.")
        return redirect("backoffice:contact_message_detail", message_id=contact_message.pk)

    now = timezone.now()
    contact_message.status = status
    contact_message.handled_by = request.user
    if status == ContactMessage.Status.NEW:
        contact_message.first_read_at = None
        contact_message.replied_at = None
    elif status == ContactMessage.Status.READ:
        if contact_message.first_read_at is None:
            contact_message.first_read_at = now
        contact_message.replied_at = None
    else:
        if contact_message.first_read_at is None:
            contact_message.first_read_at = now
        contact_message.replied_at = now

    contact_message.save(
        update_fields=["status", "handled_by", "first_read_at", "replied_at", "updated_at"]
    )
    messages.success(request, f"Contact message marked {contact_message.get_status_display().lower()}.")
    return redirect("backoffice:contact_message_detail", message_id=contact_message.pk)
