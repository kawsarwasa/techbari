from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import Http404, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from catalog.models import ProductVariant
from customers.models import Customer
from sales.forms import OrderPaymentUpdateForm, SalesOrderForm
from sales.models import SalesOrder
from sales.services import (
    SalesOrderError,
    delete_draft_order,
    parse_order_items,
    save_sales_order,
    transition_order,
    update_order_payment,
)
from .context import page_context


NOTICE_TEXT = {
    "order-saved": "Sales order saved successfully.",
    "order-confirmed": "Order confirmed and stock reservation verified.",
    "order-processing": "Order moved to processing.",
    "order-completed": "Order completed and reserved inventory was deducted.",
    "order-cancelled": "Order cancelled and any reserved stock was released.",
    "order-deleted": "Draft order deleted successfully.",
    "payment-updated": "Order payment status updated.",
}


def _message(exc):
    if hasattr(exc, "messages"):
        return " ".join(str(value) for value in exc.messages)
    return str(exc)


def _money(value):
    return f"৳ {Decimal(value or 0):,.2f}"


def _base_context(page_name, request):
    context = page_context(page_name)
    context["sales_database"] = True
    context["sales_notice"] = NOTICE_TEXT.get(request.GET.get("notice", ""), "")
    context["sales_error"] = request.GET.get("error", "")
    return context


def orders(request):
    context = _base_context("orders", request)
    qs = SalesOrder.objects.select_related("customer", "warehouse").prefetch_related("items")
    query = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    payment = (request.GET.get("payment") or "").strip()
    customer_id = (request.GET.get("customer") or "").strip()
    channel = (request.GET.get("channel") or "").strip()

    if query:
        qs = qs.filter(
            Q(order_number__icontains=query)
            | Q(customer__name__icontains=query)
            | Q(customer__phone__icontains=query)
            | Q(shipping_name__icontains=query)
            | Q(shipping_phone__icontains=query)
            | Q(items__sku_snapshot__icontains=query)
            | Q(items__product_snapshot__icontains=query)
        ).distinct()
    if status in {value for value, _ in SalesOrder.Status.choices}:
        qs = qs.filter(status=status)
    if payment in {value for value, _ in SalesOrder.PaymentStatus.choices}:
        qs = qs.filter(payment_status=payment)
    if channel in {value for value, _ in SalesOrder.Channel.choices}:
        qs = qs.filter(channel=channel)
    if customer_id.isdigit():
        qs = qs.filter(customer_id=int(customer_id))

    all_orders = list(SalesOrder.objects.prefetch_related("items").all())
    status_counts = {
        value: sum(1 for order in all_orders if order.status == value)
        for value, _ in SalesOrder.Status.choices
    }
    completed_value = sum(
        (order.grand_total for order in all_orders if order.status == SalesOrder.Status.COMPLETED),
        Decimal("0.00"),
    )
    due = sum(
        (
            order.outstanding_amount
            for order in all_orders
            if order.status not in {SalesOrder.Status.DRAFT, SalesOrder.Status.CANCELLED}
        ),
        Decimal("0.00"),
    )

    order_stats = [
        {
            "label": "Total Orders",
            "value": str(len(all_orders)),
            "trend": "All sales orders",
            "icon": "backoffice/components/icons/icon_13.html",
            "color": "blue",
        },
        {
            "label": "Pending",
            "value": str(status_counts.get(SalesOrder.Status.PENDING, 0)),
            "trend": "Awaiting confirmation",
            "icon": "backoffice/components/icons/icon_14.html",
            "color": "orange",
        },
        {
            "label": "Confirmed",
            "value": str(status_counts.get(SalesOrder.Status.CONFIRMED, 0)),
            "trend": "Ready to process",
            "icon": "backoffice/components/icons/icon_13.html",
            "color": "cyan",
        },
        {
            "label": "Processing",
            "value": str(status_counts.get(SalesOrder.Status.PROCESSING, 0)),
            "trend": "In progress",
            "icon": "backoffice/components/icons/icon_14.html",
            "color": "purple",
        },
        {
            "label": "Completed",
            "value": str(status_counts.get(SalesOrder.Status.COMPLETED, 0)),
            "trend": _money(completed_value),
            "icon": "backoffice/components/icons/icon_12.html",
            "color": "green",
        },
        {
            "label": "Cancelled",
            "value": str(status_counts.get(SalesOrder.Status.CANCELLED, 0)),
            "trend": _money(due) + " outstanding",
            "icon": "backoffice/components/icons/icon_1.html",
            "color": "red",
        },
    ]
    order_status_tabs = [
        {
            "value": value,
            "label": label,
            "count": status_counts.get(value, 0),
        }
        for value, label in SalesOrder.Status.choices
    ]

    context.update(
        order_rows=qs.order_by("-order_date", "-id"),
        order_query=query,
        order_status=status,
        order_payment=payment,
        order_customer=customer_id,
        order_channel=channel,
        order_status_choices=SalesOrder.Status.choices,
        order_payment_choices=SalesOrder.PaymentStatus.choices,
        order_channel_choices=SalesOrder.Channel.choices,
        order_customers=Customer.objects.filter(is_active=True).order_by("name"),
        order_stats=order_stats,
        order_status_tabs=order_status_tabs,
        order_total_count=len(all_orders),
    )
    return render(request, "backoffice/pages/orders/orders.html", context)


def _posted_item_rows(post):
    variants = post.getlist("variant_id")
    quantities = post.getlist("quantity")
    prices = post.getlist("unit_price")
    discounts = post.getlist("line_discount")
    count = max(len(variants), len(quantities), len(prices), len(discounts), 1)
    return [
        {
            "variant_id": variants[i] if i < len(variants) else "",
            "quantity": quantities[i] if i < len(quantities) else "1",
            "unit_price": prices[i] if i < len(prices) else "",
            "discount_amount": discounts[i] if i < len(discounts) else "0.00",
        }
        for i in range(count)
    ]


def order_add(request):
    order_id = request.GET.get("id") or request.POST.get("order_id")
    instance = None
    if order_id:
        instance = get_object_or_404(
            SalesOrder.objects.select_related("customer", "warehouse").prefetch_related("items__variant__product"),
            pk=order_id,
        )
        if instance.status not in {SalesOrder.Status.DRAFT, SalesOrder.Status.PENDING}:
            return redirect(reverse("backoffice:order_detail_id", args=[instance.pk]) + "?error=Only Draft or Pending orders can be edited.")
    form = SalesOrderForm(request.POST or None, instance=instance)
    error = ""
    if request.method == "POST" and form.is_valid():
        try:
            item_rows = parse_order_items(request.POST)
            order = save_sales_order(
                header_data=form.cleaned_data,
                item_rows=item_rows,
                order=instance,
                actor="Dashboard",
            )
            return redirect(reverse("backoffice:order_detail_id", args=[order.pk]) + "?notice=order-saved")
        except (SalesOrderError, ValidationError) as exc:
            error = _message(exc)
    elif request.method == "POST":
        error = "Please correct the highlighted order fields."

    if request.method == "POST":
        item_rows = _posted_item_rows(request.POST)
    elif instance:
        item_rows = [
            {
                "variant_id": str(item.variant_id),
                "quantity": str(item.quantity),
                "unit_price": str(item.unit_price),
                "discount_amount": str(item.discount_amount),
            }
            for item in instance.items.all()
        ]
    else:
        item_rows = [{"variant_id": "", "quantity": "1", "unit_price": "", "discount_amount": "0.00"}]

    context = _base_context("order_add", request)
    context.update(
        form=form,
        order_obj=instance,
        is_edit=bool(instance),
        item_rows=item_rows,
        sales_variants=ProductVariant.objects.select_related("product").filter(is_active=True, product__status="active").order_by("product__name", "sku"),
        sales_form_error=error,
    )
    return render(request, "backoffice/pages/orders/order_add.html", context)


def order_detail(request, order_id=None):
    if order_id is None:
        raw_id = request.GET.get("id")
        if not raw_id or not str(raw_id).isdigit():
            raise Http404("Order not found")
        order_id = int(raw_id)
    order = get_object_or_404(
        SalesOrder.objects.select_related("customer", "warehouse").prefetch_related("items__variant__product", "history"),
        pk=order_id,
    )
    payment_form = OrderPaymentUpdateForm(initial={"amount_paid": order.amount_paid})
    context = _base_context("order_detail", request)
    context.update(order=order, payment_form=payment_form)
    return render(request, "backoffice/pages/orders/order_detail.html", context)


def _transition(request, order_id, status, notice):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    order = get_object_or_404(SalesOrder, pk=order_id)
    try:
        transition_order(order=order, new_status=status, actor="Dashboard", note=request.POST.get("note", ""))
        return redirect(reverse("backoffice:order_detail_id", args=[order.pk]) + f"?notice={notice}")
    except (SalesOrderError, ValidationError) as exc:
        return redirect(reverse("backoffice:order_detail_id", args=[order.pk]) + "?error=" + _message(exc))


def order_confirm(request, order_id):
    return _transition(request, order_id, SalesOrder.Status.CONFIRMED, "order-confirmed")


def order_process(request, order_id):
    return _transition(request, order_id, SalesOrder.Status.PROCESSING, "order-processing")


def order_complete(request, order_id):
    return _transition(request, order_id, SalesOrder.Status.COMPLETED, "order-completed")


def order_cancel(request, order_id):
    return _transition(request, order_id, SalesOrder.Status.CANCELLED, "order-cancelled")


def order_payment(request, order_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    order = get_object_or_404(SalesOrder, pk=order_id)
    form = OrderPaymentUpdateForm(request.POST)
    if not form.is_valid():
        return redirect(reverse("backoffice:order_detail_id", args=[order.pk]) + "?error=Enter a valid paid amount.")
    try:
        update_order_payment(
            order=order,
            amount_paid=form.cleaned_data["amount_paid"],
            note=form.cleaned_data["note"],
            actor="Dashboard",
        )
        return redirect(reverse("backoffice:order_detail_id", args=[order.pk]) + "?notice=payment-updated")
    except (SalesOrderError, ValidationError) as exc:
        return redirect(reverse("backoffice:order_detail_id", args=[order.pk]) + "?error=" + _message(exc))


def order_delete(request, order_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    order = get_object_or_404(SalesOrder, pk=order_id)
    try:
        delete_draft_order(order=order)
        return redirect(reverse("backoffice:orders") + "?notice=order-deleted")
    except (SalesOrderError, ValidationError) as exc:
        return redirect(reverse("backoffice:order_detail_id", args=[order.pk]) + "?error=" + _message(exc))
