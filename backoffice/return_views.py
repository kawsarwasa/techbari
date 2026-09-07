from decimal import Decimal
from urllib.parse import urlencode

from django.core.exceptions import ValidationError
from django.db.models import Q, Sum
from django.http import Http404, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from inventory.models import Warehouse
from returns.forms import SalesReturnForm
from returns.models import SalesReturn, SalesReturnItem, SalesReturnRefund
from returns.services import (
    ReturnError,
    approve_sales_return,
    available_return_credit,
    available_return_quantity,
    cancel_sales_return,
    complete_sales_return,
    create_sales_return,
    receive_sales_return,
    reject_sales_return,
)
from sales.models import SalesOrder
from serial_tracking.models import SerializedUnit

from .context import page_context


NOTICE_TEXT = {
    "return-created": "Return request created successfully.",
    "return-approved": "Return approved.",
    "return-received": "Return marked received and ready for inspection/completion.",
    "return-completed": "Return completed; inventory, order credit and any cash refund were posted atomically.",
    "return-rejected": "Return rejected. No inventory or payment was changed.",
    "return-cancelled": "Return cancelled. No inventory or payment was changed.",
}


def _error_text(exc):
    if hasattr(exc, "messages"):
        return " ".join(str(value) for value in exc.messages)
    return str(exc)


def _redirect_detail(sales_return, *, notice="", error=""):
    url = reverse("backoffice:return_detail", args=[sales_return.pk])
    params = {}
    if notice:
        params["notice"] = notice
    if error:
        params["error"] = error
    return redirect(url + (("?" + urlencode(params)) if params else ""))


def _base_context(page_name, request):
    context = page_context(page_name)
    context["returns_database"] = True
    context["returns_notice"] = NOTICE_TEXT.get(request.GET.get("notice", ""), "")
    context["returns_error"] = request.GET.get("error", "")
    return context


def returns(request):
    context = _base_context("returns", request)
    qs = SalesReturn.objects.select_related("order", "order__customer", "warehouse").prefetch_related("items", "refunds")
    query = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    source = (request.GET.get("source") or "").strip()
    if query:
        qs = qs.filter(
            Q(return_no__icontains=query)
            | Q(order__order_number__icontains=query)
            | Q(order__customer__name__icontains=query)
            | Q(order__shipping_name__icontains=query)
            | Q(order__shipping_phone__icontains=query)
            | Q(items__sku_snapshot__icontains=query)
            | Q(items__product_snapshot__icontains=query)
        ).distinct()
    if status in {value for value, _ in SalesReturn.Status.choices}:
        qs = qs.filter(status=status)
    if source in {value for value, _ in SalesReturn.Source.choices}:
        qs = qs.filter(source=source)

    total = SalesReturn.objects.count()
    open_count = SalesReturn.objects.filter(
        status__in=[SalesReturn.Status.REQUESTED, SalesReturn.Status.APPROVED, SalesReturn.Status.RECEIVED]
    ).count()
    completed = SalesReturn.objects.filter(status=SalesReturn.Status.COMPLETED).count()
    refunded = SalesReturnRefund.objects.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    context.update(
        return_rows=qs.order_by("-requested_date", "-id"),
        return_query=query,
        return_status=status,
        return_source=source,
        return_status_choices=SalesReturn.Status.choices,
        return_source_choices=SalesReturn.Source.choices,
        return_stats=[
            {"label": "Returns", "value": str(total), "trend": "Database", "trend_class": "up", "icon": "backoffice/components/icons/icon_13.html", "color": "blue"},
            {"label": "Open", "value": str(open_count), "trend": "Needs action", "trend_class": "up", "icon": "backoffice/components/icons/icon_14.html", "color": "orange"},
            {"label": "Completed", "value": str(completed), "trend": "Processed", "trend_class": "up", "icon": "backoffice/components/icons/icon_12.html", "color": "green"},
            {"label": "Cash Refunded", "value": f"৳ {refunded:,.2f}", "trend": "Payment ledger", "trend_class": "up", "icon": "backoffice/components/icons/icon_1.html", "color": "red"},
        ],
    )
    return render(request, "backoffice/pages/returns/returns.html", context)


def _selected_order(request):
    raw = request.POST.get("order") if request.method == "POST" else request.GET.get("order")
    if not raw or not str(raw).isdigit():
        return None
    return (
        SalesOrder.objects.select_related("customer", "warehouse")
        .prefetch_related("items__variant__product")
        .filter(pk=int(raw), status=SalesOrder.Status.COMPLETED)
        .first()
    )


def _return_item_rows(order, request):
    if not order:
        return []
    rows = []
    sold_items = list(order.items.select_related("variant", "variant__product").filter(issued_quantity__gt=0).order_by("id"))
    for item in sold_items:
        remaining_qty = available_return_quantity(item)
        if remaining_qty <= 0:
            continue
        remaining_credit = available_return_credit(item)
        serials = list(
            SerializedUnit.objects.filter(variant=item.variant, status=SerializedUnit.Status.SOLD)
            .filter(Q(sales_reference=order.order_number) | Q(sales_reference=""))
            .order_by("serial_number", "imei1", "id")
        )
        prefix = str(item.pk)
        rows.append(
            {
                "item": item,
                "remaining_quantity": remaining_qty,
                "remaining_credit": remaining_credit,
                "serials": serials,
                "checked": request.POST.get(f"include_{prefix}") == "1" if request.method == "POST" else False,
                "posted_quantity": request.POST.get(f"quantity_{prefix}", "1"),
                "posted_refund": request.POST.get(f"refund_amount_{prefix}", str(remaining_credit)),
                "posted_condition": request.POST.get(f"condition_{prefix}", SalesReturnItem.Condition.GOOD),
                "posted_disposition": request.POST.get(f"disposition_{prefix}", SalesReturnItem.Disposition.RESTOCK),
                "posted_serial": request.POST.get(f"serialized_unit_{prefix}", ""),
                "posted_note": request.POST.get(f"item_note_{prefix}", ""),
            }
        )
    return rows


def _posted_rows(order, request):
    rows = []
    for item in order.items.filter(issued_quantity__gt=0).order_by("id"):
        prefix = str(item.pk)
        if request.POST.get(f"include_{prefix}") != "1":
            continue
        rows.append(
            {
                "order_item_id": item.pk,
                "quantity": request.POST.get(f"quantity_{prefix}"),
                "refund_amount": request.POST.get(f"refund_amount_{prefix}"),
                "condition": request.POST.get(f"condition_{prefix}"),
                "disposition": request.POST.get(f"disposition_{prefix}"),
                "serialized_unit_id": request.POST.get(f"serialized_unit_{prefix}"),
                "note": request.POST.get(f"item_note_{prefix}"),
            }
        )
    return rows


def return_add(request):
    selected_order = _selected_order(request)
    initial = {}
    if selected_order:
        initial["order"] = selected_order
        initial["warehouse"] = selected_order.warehouse
        try:
            if selected_order.shipment.status == "returned":
                initial["source"] = SalesReturn.Source.COURIER_RETURN
                initial["reason_category"] = SalesReturn.Reason.COURIER_RETURN
                initial["source_reference"] = selected_order.shipment.shipment_no
        except Exception:
            pass
    if "source" not in initial:
        initial["source"] = SalesReturn.Source.POS if selected_order and selected_order.channel == SalesOrder.Channel.POS else SalesReturn.Source.CUSTOMER
    initial.setdefault("resolution", SalesReturn.Resolution.REFUND)

    form = SalesReturnForm(request.POST or None, initial=initial)
    error = ""
    if request.method == "POST" and form.is_valid():
        order = form.cleaned_data["order"]
        try:
            sales_return = create_sales_return(
                order=order,
                warehouse=form.cleaned_data["warehouse"],
                source=form.cleaned_data["source"],
                resolution=form.cleaned_data["resolution"],
                reason_category=form.cleaned_data["reason_category"],
                requested_date=form.cleaned_data["requested_date"],
                source_reference=form.cleaned_data["source_reference"],
                refund_reference=form.cleaned_data["refund_reference"],
                customer_note=form.cleaned_data["customer_note"],
                internal_note=form.cleaned_data["internal_note"],
                item_rows=_posted_rows(order, request),
                actor="Dashboard",
            )
            return _redirect_detail(sales_return, notice="return-created")
        except (ReturnError, ValidationError) as exc:
            error = _error_text(exc)
            selected_order = order
    elif request.method == "POST":
        error = "Please correct the highlighted return fields."

    context = _base_context("return_add", request)
    context.update(
        form=form,
        selected_order=selected_order,
        return_item_rows=_return_item_rows(selected_order, request),
        return_form_error=error,
        condition_choices=SalesReturnItem.Condition.choices,
        disposition_choices=SalesReturnItem.Disposition.choices,
    )
    return render(request, "backoffice/pages/returns/return_add.html", context)


def return_detail(request, return_id):
    sales_return = get_object_or_404(
        SalesReturn.objects.select_related("order", "order__customer", "warehouse")
        .prefetch_related(
            "items__variant",
            "items__serialized_unit",
            "events",
            "refunds__source_payment",
            "refunds__refund_transaction",
        ),
        pk=return_id,
    )
    context = _base_context("returns", request)
    context.update(sales_return=sales_return)
    return render(request, "backoffice/pages/returns/return_detail.html", context)


def _action(request, return_id, action, notice):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    sales_return = get_object_or_404(SalesReturn, pk=return_id)
    note = (request.POST.get("note") or "").strip()
    try:
        action(sales_return=sales_return, note=note, actor="Dashboard")
        sales_return.refresh_from_db()
        return _redirect_detail(sales_return, notice=notice)
    except (ReturnError, ValidationError) as exc:
        return _redirect_detail(sales_return, error=_error_text(exc))


def return_approve(request, return_id):
    return _action(request, return_id, approve_sales_return, "return-approved")


def return_receive(request, return_id):
    return _action(request, return_id, receive_sales_return, "return-received")


def return_complete(request, return_id):
    return _action(request, return_id, complete_sales_return, "return-completed")


def return_reject(request, return_id):
    return _action(request, return_id, reject_sales_return, "return-rejected")


def return_cancel(request, return_id):
    return _action(request, return_id, cancel_sales_return, "return-cancelled")
