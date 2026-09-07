from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from catalog.models import ProductVariant
from purchasing.forms import (
    PurchaseOrderForm,
    PurchasePaymentForm,
    PurchaseReceiptHeaderForm,
    PurchaseReturnHeaderForm,
    SupplierForm,
)
from purchasing.models import PurchaseOrder, Supplier
from purchasing.services import (
    PurchasingError,
    cancel_purchase,
    delete_draft_purchase,
    delete_supplier,
    parse_purchase_items,
    parse_serial_lines,
    pay_purchase,
    receive_purchase,
    return_purchase,
    save_purchase_order,
)
from serial_tracking.models import SerializedUnit
from .context import page_context


NOTICE_TEXT = {
    "supplier-saved": "Supplier saved successfully.",
    "supplier-deleted": "Supplier deleted successfully.",
    "purchase-saved": "Purchase order saved successfully.",
    "purchase-deleted": "Draft purchase deleted successfully.",
    "purchase-cancelled": "Purchase order cancelled successfully.",
    "stock-received": "Purchase stock received successfully.",
    "payment-saved": "Supplier payment recorded successfully.",
    "return-posted": "Purchase return posted successfully.",
}


def _message(exc):
    if hasattr(exc, "messages"):
        return " ".join(str(value) for value in exc.messages)
    return str(exc)


def _money(value):
    return f"৳ {Decimal(value or 0):,.2f}"


def _base_context(page_name, request):
    context = page_context(page_name)
    context["purchase_database"] = True
    context["purchase_notice"] = NOTICE_TEXT.get(request.GET.get("notice", ""), "")
    context["purchase_error"] = request.GET.get("error", "")
    return context


def suppliers(request):
    context = _base_context("suppliers", request)
    qs = Supplier.objects.all().order_by("name", "code")
    query = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    if query:
        qs = qs.filter(
            Q(code__icontains=query)
            | Q(name__icontains=query)
            | Q(contact_person__icontains=query)
            | Q(phone__icontains=query)
            | Q(email__icontains=query)
        )
    if status == "active":
        qs = qs.filter(is_active=True)
    elif status == "inactive":
        qs = qs.filter(is_active=False)

    all_suppliers = list(Supplier.objects.all())
    active_count = sum(1 for supplier in all_suppliers if supplier.is_active)
    total_due = sum((supplier.outstanding_balance for supplier in all_suppliers), Decimal("0.00"))
    total_purchase = sum((supplier.total_purchases for supplier in all_suppliers), Decimal("0.00"))
    context.update(
        supplier_rows=qs,
        supplier_query=query,
        supplier_status=status,
        supplier_stats=[
            {"label": "Total Suppliers", "value": str(len(all_suppliers)), "trend": "Live", "trend_class": "up", "icon": "backoffice/components/icons/icon_2.html", "color": "blue"},
            {"label": "Active Suppliers", "value": str(active_count), "trend": "Live", "trend_class": "up", "icon": "backoffice/components/icons/icon_7.html", "color": "green"},
            {"label": "Outstanding", "value": _money(total_due), "trend": "Live", "trend_class": "up", "icon": "backoffice/components/icons/icon_1.html", "color": "red"},
            {"label": "Purchase Value", "value": _money(total_purchase), "trend": "Live", "trend_class": "up", "icon": "backoffice/components/icons/icon_13.html", "color": "purple"},
        ],
    )
    return render(request, "backoffice/pages/suppliers/suppliers.html", context)


def supplier_add(request):
    supplier_id = request.GET.get("id") or request.POST.get("supplier_id")
    instance = get_object_or_404(Supplier, pk=supplier_id) if supplier_id else None
    form = SupplierForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        supplier = form.save()
        return redirect(reverse("backoffice:supplier_add") + f"?id={supplier.pk}&notice=supplier-saved")
    context = _base_context("supplier_add", request)
    context.update(form=form, supplier_obj=instance, is_edit=bool(instance))
    return render(request, "backoffice/pages/suppliers/supplier_add.html", context)


def supplier_delete(request, supplier_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    supplier = get_object_or_404(Supplier, pk=supplier_id)
    try:
        delete_supplier(supplier=supplier)
        return redirect(reverse("backoffice:suppliers") + "?notice=supplier-deleted")
    except PurchasingError as exc:
        return redirect(reverse("backoffice:suppliers") + "?error=" + _message(exc))


def _posted_item_rows(post):
    variants = post.getlist("variant_id")
    quantities = post.getlist("ordered_quantity")
    costs = post.getlist("unit_cost")
    discounts = post.getlist("line_discount")
    count = max(len(variants), len(quantities), len(costs), len(discounts), 1)
    rows = []
    for index in range(count):
        rows.append({
            "variant_id": variants[index] if index < len(variants) else "",
            "ordered_quantity": quantities[index] if index < len(quantities) else "",
            "unit_cost": costs[index] if index < len(costs) else "",
            "discount_amount": discounts[index] if index < len(discounts) else "0.00",
        })
    return rows


def purchases(request):
    context = _base_context("purchases", request)
    qs = PurchaseOrder.objects.select_related("supplier", "warehouse").prefetch_related("items", "payments", "returns").all()
    query = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    supplier_id = (request.GET.get("supplier") or "").strip()
    if query:
        qs = qs.filter(
            Q(po_number__icontains=query)
            | Q(supplier__name__icontains=query)
            | Q(supplier_invoice_no__icontains=query)
            | Q(items__variant__sku__icontains=query)
            | Q(items__variant__product__name__icontains=query)
        ).distinct()
    if status in {value for value, _ in PurchaseOrder.Status.choices}:
        qs = qs.filter(status=status)
    if supplier_id.isdigit():
        qs = qs.filter(supplier_id=int(supplier_id))

    all_orders = list(PurchaseOrder.objects.select_related("supplier").prefetch_related("items", "payments", "returns"))
    total_value = sum((purchase.grand_total for purchase in all_orders if purchase.status != PurchaseOrder.Status.CANCELLED), Decimal("0.00"))
    total_due = sum((purchase.outstanding_amount for purchase in all_orders if purchase.status not in {PurchaseOrder.Status.DRAFT, PurchaseOrder.Status.CANCELLED}), Decimal("0.00"))
    pending_receive = sum(1 for purchase in all_orders if purchase.status in {PurchaseOrder.Status.ORDERED, PurchaseOrder.Status.PARTIALLY_RECEIVED})
    received = sum(1 for purchase in all_orders if purchase.status == PurchaseOrder.Status.RECEIVED)
    context.update(
        purchase_rows=qs,
        purchase_query=query,
        purchase_status=status,
        purchase_supplier=supplier_id,
        purchase_status_choices=PurchaseOrder.Status.choices,
        purchase_suppliers=Supplier.objects.filter(is_active=True).order_by("name"),
        purchase_stats=[
            {"label": "Purchase Orders", "value": str(len(all_orders)), "trend": "Live", "trend_class": "up", "icon": "backoffice/components/icons/icon_13.html", "color": "blue"},
            {"label": "Pending Receipt", "value": str(pending_receive), "trend": "Live", "trend_class": "up", "icon": "backoffice/components/icons/icon_14.html", "color": "orange"},
            {"label": "Received", "value": str(received), "trend": "Live", "trend_class": "up", "icon": "backoffice/components/icons/icon_12.html", "color": "green"},
            {"label": "Supplier Due", "value": _money(total_due), "trend": _money(total_value), "trend_class": "up", "icon": "backoffice/components/icons/icon_1.html", "color": "red"},
        ],
    )
    return render(request, "backoffice/pages/purchases/purchases.html", context)


def purchase_add(request):
    purchase_id = request.GET.get("id") or request.POST.get("purchase_id")
    instance = get_object_or_404(
        PurchaseOrder.objects.select_related("supplier", "warehouse").prefetch_related("items", "receipts", "payments", "returns"),
        pk=purchase_id,
    ) if purchase_id else None
    form = PurchaseOrderForm(request.POST or None, instance=instance)
    error = ""
    if request.method == "POST" and form.is_valid():
        try:
            item_rows = parse_purchase_items(request.POST)
            purchase = save_purchase_order(
                header_data=form.cleaned_data,
                item_rows=item_rows,
                purchase=instance,
                actor="Dashboard",
            )
            return redirect(reverse("backoffice:purchase_detail", args=[purchase.pk]) + "?notice=purchase-saved")
        except (PurchasingError, ValidationError) as exc:
            error = _message(exc)
    elif request.method == "POST":
        error = "Please correct the highlighted purchase fields."

    if request.method == "POST":
        item_rows = _posted_item_rows(request.POST)
    elif instance:
        item_rows = [
            {
                "variant_id": str(item.variant_id),
                "ordered_quantity": str(item.ordered_quantity),
                "unit_cost": str(item.unit_cost),
                "discount_amount": str(item.discount_amount),
            }
            for item in instance.items.all()
        ]
    else:
        item_rows = [{"variant_id": "", "ordered_quantity": "1", "unit_cost": "0.00", "discount_amount": "0.00"}]

    context = _base_context("purchase_add", request)
    context.update(
        form=form,
        purchase_obj=instance,
        is_edit=bool(instance),
        item_rows=item_rows,
        purchase_variants=ProductVariant.objects.select_related("product").filter(is_active=True).order_by("product__name", "sku"),
        purchase_form_error=error,
    )
    return render(request, "backoffice/pages/purchases/purchase_add.html", context)


def purchase_detail(request, purchase_id):
    purchase = get_object_or_404(
        PurchaseOrder.objects.select_related("supplier", "warehouse").prefetch_related(
            "items__variant__product", "receipts__items", "payments", "returns__items__purchase_item__variant"
        ),
        pk=purchase_id,
    )
    context = _base_context("purchases", request)
    context.update(purchase=purchase)
    return render(request, "backoffice/pages/purchases/purchase_detail.html", context)


def purchase_receive(request, purchase_id):
    purchase = get_object_or_404(
        PurchaseOrder.objects.select_related("supplier", "warehouse").prefetch_related("items__variant__product"),
        pk=purchase_id,
    )
    form = PurchaseReceiptHeaderForm(request.POST or None)
    error = ""
    if request.method == "POST" and form.is_valid():
        try:
            quantities = {item.pk: request.POST.get(f"receive_{item.pk}", "0") for item in purchase.items.all()}
            serial_payloads = {item.pk: parse_serial_lines(request.POST.get(f"serials_{item.pk}", "")) for item in purchase.items.all()}
            receive_purchase(
                purchase=purchase,
                received_date=form.cleaned_data["received_date"],
                quantities=quantities,
                serial_payloads=serial_payloads,
                supplier_challan_no=form.cleaned_data["supplier_challan_no"],
                note=form.cleaned_data["note"],
                actor="Dashboard",
            )
            return redirect(reverse("backoffice:purchase_detail", args=[purchase.pk]) + "?notice=stock-received")
        except (PurchasingError, ValidationError) as exc:
            error = _message(exc)
    context = _base_context("purchases", request)
    context.update(purchase=purchase, form=form, purchase_form_error=error)
    return render(request, "backoffice/pages/purchases/purchase_receive.html", context)


def purchase_payment(request, purchase_id):
    purchase = get_object_or_404(PurchaseOrder.objects.select_related("supplier", "warehouse").prefetch_related("items", "payments", "returns"), pk=purchase_id)
    form = PurchasePaymentForm(request.POST or None, purchase=purchase)
    error = ""
    if request.method == "POST" and form.is_valid():
        try:
            pay_purchase(purchase=purchase, actor="Dashboard", **form.cleaned_data)
            return redirect(reverse("backoffice:purchase_detail", args=[purchase.pk]) + "?notice=payment-saved")
        except (PurchasingError, ValidationError) as exc:
            error = _message(exc)
    context = _base_context("purchases", request)
    context.update(purchase=purchase, form=form, purchase_form_error=error)
    return render(request, "backoffice/pages/purchases/purchase_payment.html", context)


def purchase_return(request, purchase_id):
    purchase = get_object_or_404(
        PurchaseOrder.objects.select_related("supplier", "warehouse").prefetch_related("items__variant__product"),
        pk=purchase_id,
    )
    form = PurchaseReturnHeaderForm(request.POST or None)
    error = ""
    serial_options = {}
    for item in purchase.items.all():
        serial_options[item.pk] = SerializedUnit.objects.filter(
            variant=item.variant,
            warehouse=purchase.warehouse,
            purchase_reference=purchase.po_number,
            status__in=[SerializedUnit.Status.AVAILABLE, SerializedUnit.Status.RETURNED],
        ).order_by("serial_number", "imei1", "id")
    if request.method == "POST" and form.is_valid():
        try:
            quantities = {item.pk: request.POST.get(f"return_{item.pk}", "0") for item in purchase.items.all()}
            serial_unit_ids = {item.pk: request.POST.getlist(f"serial_unit_{item.pk}") for item in purchase.items.all()}
            return_purchase(
                purchase=purchase,
                return_date=form.cleaned_data["return_date"],
                quantities=quantities,
                serial_unit_ids=serial_unit_ids,
                reason=form.cleaned_data["reason"],
                note=form.cleaned_data["note"],
                actor="Dashboard",
            )
            return redirect(reverse("backoffice:purchase_detail", args=[purchase.pk]) + "?notice=return-posted")
        except (PurchasingError, ValidationError) as exc:
            error = _message(exc)
    item_panels = [{"item": item, "serial_units": serial_options[item.pk]} for item in purchase.items.all()]
    context = _base_context("purchases", request)
    context.update(purchase=purchase, form=form, item_panels=item_panels, purchase_form_error=error)
    return render(request, "backoffice/pages/purchases/purchase_return.html", context)


def purchase_cancel(request, purchase_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    purchase = get_object_or_404(PurchaseOrder, pk=purchase_id)
    try:
        cancel_purchase(purchase=purchase, actor="Dashboard")
        return redirect(reverse("backoffice:purchase_detail", args=[purchase.pk]) + "?notice=purchase-cancelled")
    except PurchasingError as exc:
        return redirect(reverse("backoffice:purchase_detail", args=[purchase.pk]) + "?error=" + _message(exc))


def purchase_delete(request, purchase_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    purchase = get_object_or_404(PurchaseOrder, pk=purchase_id)
    try:
        delete_draft_purchase(purchase=purchase)
        return redirect(reverse("backoffice:purchases") + "?notice=purchase-deleted")
    except PurchasingError as exc:
        return redirect(reverse("backoffice:purchase_detail", args=[purchase.pk]) + "?error=" + _message(exc))
