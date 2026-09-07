from decimal import Decimal
from urllib.parse import urlencode

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from shipping.forms import (
    CODSettlementForm,
    CourierProviderForm,
    ShipmentForm,
    ShipmentStatusForm,
    TrackingUpdateForm,
)
from shipping.models import CODSettlement, CourierProvider, Shipment
from shipping.services import (
    ShippingError,
    allowed_statuses,
    change_shipment_status,
    create_shipment,
    post_cod_settlement,
    update_tracking,
)

from .context import page_context


NOTICE_TEXT = {
    "shipment-created": "Shipment created successfully.",
    "shipment-status": "Shipment status updated successfully.",
    "tracking-updated": "Courier tracking information updated.",
    "courier-saved": "Courier provider saved successfully.",
    "cod-settled": "COD settlement posted and linked payment transactions were reconciled.",
}


def _message(exc):
    if hasattr(exc, "messages"):
        return " ".join(str(value) for value in exc.messages)
    return str(exc)


def _money(value):
    return f"৳ {Decimal(value or 0):,.2f}"


def _base_context(page_name, request):
    context = page_context(page_name)
    context["shipping_database"] = True
    context["shipping_notice"] = NOTICE_TEXT.get(request.GET.get("notice", ""), "")
    context["shipping_error"] = request.GET.get("error", "")
    return context


def _redirect_error(route_name, error, *args):
    url = reverse(route_name, args=args)
    return redirect(url + "?" + urlencode({"error": _message(error)}))


def shipping(request):
    context = _base_context("shipping", request)
    qs = Shipment.objects.select_related("order", "order__customer", "courier")
    query = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    courier_id = (request.GET.get("courier") or "").strip()
    cod_status = (request.GET.get("cod_status") or "").strip()
    if query:
        qs = qs.filter(
            Q(shipment_no__icontains=query)
            | Q(order__order_number__icontains=query)
            | Q(order__shipping_name__icontains=query)
            | Q(order__shipping_phone__icontains=query)
            | Q(order__customer__name__icontains=query)
            | Q(tracking_id__icontains=query)
            | Q(courier_reference__icontains=query)
        ).distinct()
    if status in {value for value, _ in Shipment.Status.choices}:
        qs = qs.filter(status=status)
    if courier_id.isdigit():
        qs = qs.filter(courier_id=int(courier_id))
    if cod_status in {value for value, _ in Shipment.CODStatus.choices}:
        qs = qs.filter(cod_status=cod_status)

    all_shipments = list(Shipment.objects.select_related("order", "courier").all())
    active = [
        shipment
        for shipment in all_shipments
        if shipment.status
        in {
            Shipment.Status.READY,
            Shipment.Status.HANDED_OVER,
            Shipment.Status.IN_TRANSIT,
            Shipment.Status.OUT_FOR_DELIVERY,
            Shipment.Status.FAILED,
            Shipment.Status.RETURNING,
        }
    ]
    delivered = [shipment for shipment in all_shipments if shipment.status == Shipment.Status.DELIVERED]
    unsettled = sum((shipment.unsettled_cod for shipment in all_shipments), Decimal("0.00"))
    context.update(
        shipment_rows=qs.order_by("-shipment_date", "-id"),
        shipping_query=query,
        shipping_status=status,
        shipping_courier=courier_id,
        shipping_cod_status=cod_status,
        shipment_status_choices=Shipment.Status.choices,
        shipment_cod_choices=Shipment.CODStatus.choices,
        shipping_couriers=CourierProvider.objects.order_by("name"),
        shipping_stats=[
            {"label": "Shipments", "value": str(len(all_shipments)), "trend": "Live", "trend_class": "up", "icon": "backoffice/components/icons/icon_13.html", "color": "blue"},
            {"label": "In Delivery Flow", "value": str(len(active)), "trend": "Operational", "trend_class": "up", "icon": "backoffice/components/icons/icon_14.html", "color": "orange"},
            {"label": "Delivered", "value": str(len(delivered)), "trend": "Completed", "trend_class": "up", "icon": "backoffice/components/icons/icon_12.html", "color": "green"},
            {"label": "COD Unsettled", "value": _money(unsettled), "trend": "Courier receivable", "trend_class": "up", "icon": "backoffice/components/icons/icon_1.html", "color": "red"},
        ],
    )
    return render(request, "backoffice/pages/shipping/shipping.html", context)


def shipment_add(request):
    initial = {}
    order_id = request.GET.get("order")
    if order_id and str(order_id).isdigit():
        initial["order"] = int(order_id)
    form = ShipmentForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            shipment = create_shipment(
                order=data["order"],
                courier=data["courier"],
                shipment_date=data.get("shipment_date"),
                expected_delivery_date=data.get("expected_delivery_date"),
                tracking_id=data.get("tracking_id", ""),
                courier_reference=data.get("courier_reference", ""),
                parcel_count=data.get("parcel_count", 1),
                weight_kg=data.get("weight_kg", 0),
                courier_fee=data.get("courier_fee"),
                cod_expected=data.get("cod_expected"),
                notes=data.get("notes", ""),
                actor="Dashboard",
            )
            return redirect(reverse("backoffice:shipment_detail", args=[shipment.pk]) + "?notice=shipment-created")
        except (ShippingError, ValidationError) as exc:
            form.add_error(None, _message(exc))
    context = _base_context("shipment_add", request)
    context.update(form=form)
    return render(request, "backoffice/pages/shipping/shipment_add.html", context)


def shipment_detail(request, shipment_id):
    shipment = get_object_or_404(
        Shipment.objects.select_related("order", "order__customer", "order__warehouse", "courier").prefetch_related(
            "events",
            "settlement_items__settlement",
            "settlement_items__payment_transaction",
        ),
        pk=shipment_id,
    )
    allowed = allowed_statuses(shipment)
    status_form = ShipmentStatusForm(allowed_statuses=allowed)
    tracking_form = TrackingUpdateForm(
        initial={
            "tracking_id": shipment.tracking_id,
            "courier_reference": shipment.courier_reference,
            "location": shipment.last_location,
        }
    )
    context = _base_context("shipping", request)
    context.update(
        shipment=shipment,
        allowed_shipping_statuses=allowed,
        status_form=status_form,
        tracking_form=tracking_form,
    )
    return render(request, "backoffice/pages/shipping/shipment_detail.html", context)


def shipment_status(request, shipment_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    shipment = get_object_or_404(Shipment, pk=shipment_id)
    form = ShipmentStatusForm(request.POST, allowed_statuses=allowed_statuses(shipment))
    if not form.is_valid():
        return _redirect_error("backoffice:shipment_detail", "Choose a valid next shipment status.", shipment.pk)
    try:
        change_shipment_status(
            shipment=shipment,
            new_status=form.cleaned_data["new_status"],
            cod_collected=form.cleaned_data.get("cod_collected"),
            location=form.cleaned_data.get("location", ""),
            failure_reason=form.cleaned_data.get("failure_reason", ""),
            note=form.cleaned_data.get("note", ""),
            actor="Dashboard",
        )
        return redirect(reverse("backoffice:shipment_detail", args=[shipment.pk]) + "?notice=shipment-status")
    except (ShippingError, ValidationError) as exc:
        return _redirect_error("backoffice:shipment_detail", exc, shipment.pk)


def shipment_tracking(request, shipment_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    shipment = get_object_or_404(Shipment, pk=shipment_id)
    form = TrackingUpdateForm(request.POST)
    if not form.is_valid():
        return _redirect_error("backoffice:shipment_detail", "Enter valid tracking information.", shipment.pk)
    try:
        update_tracking(
            shipment=shipment,
            tracking_id=form.cleaned_data.get("tracking_id", ""),
            courier_reference=form.cleaned_data.get("courier_reference", ""),
            location=form.cleaned_data.get("location", ""),
            note=form.cleaned_data.get("note", ""),
            actor="Dashboard",
        )
        return redirect(reverse("backoffice:shipment_detail", args=[shipment.pk]) + "?notice=tracking-updated")
    except (ShippingError, ValidationError) as exc:
        return _redirect_error("backoffice:shipment_detail", exc, shipment.pk)


def courier_providers(request):
    provider_id = request.GET.get("id") or request.POST.get("provider_id")
    instance = None
    if provider_id and str(provider_id).isdigit():
        instance = get_object_or_404(CourierProvider, pk=int(provider_id))
    form = CourierProviderForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        provider = form.save(commit=False)
        try:
            provider.full_clean()
            provider.save()
            return redirect(reverse("backoffice:courier_providers") + "?notice=courier-saved")
        except ValidationError as exc:
            form.add_error(None, _message(exc))
    context = _base_context("shipping", request)
    context.update(
        courier_rows=CourierProvider.objects.order_by("name"),
        courier_form=form,
        courier_edit=instance,
    )
    return render(request, "backoffice/pages/shipping/courier_providers.html", context)


def cod_settlements(request):
    context = _base_context("shipping", request)
    settlements = CODSettlement.objects.select_related("courier").prefetch_related(
        "items__shipment__order",
        "items__payment_transaction",
    )
    context.update(settlement_rows=settlements)
    return render(request, "backoffice/pages/shipping/cod_settlements.html", context)


def _eligible_cod_shipments():
    return [
        shipment
        for shipment in Shipment.objects.select_related("order", "order__customer", "courier")
        .filter(status=Shipment.Status.DELIVERED, cod_collected__gt=0)
        .order_by("courier__name", "-delivered_at", "-id")
        if shipment.unsettled_cod > Decimal("0.00") and shipment.order.outstanding_amount > Decimal("0.00")
    ]


def cod_settlement_add(request):
    form = CODSettlementForm(request.POST or None)
    eligible = _eligible_cod_shipments()
    if request.method == "POST" and form.is_valid():
        selected_ids = request.POST.getlist("shipment_id")
        shipment_amounts = {
            shipment_id: request.POST.get(f"amount_{shipment_id}", "0")
            for shipment_id in selected_ids
        }
        data = form.cleaned_data
        try:
            settlement = post_cod_settlement(
                courier=data["courier"],
                settlement_date=data.get("settlement_date"),
                payment_method=data["payment_method"],
                reference=data.get("reference", ""),
                shipment_amounts=shipment_amounts,
                courier_deduction=data.get("courier_deduction") or Decimal("0.00"),
                note=data.get("note", ""),
                actor="Dashboard",
            )
            return redirect(reverse("backoffice:cod_settlement_detail", args=[settlement.pk]) + "?notice=cod-settled")
        except (ShippingError, ValidationError) as exc:
            form.add_error(None, _message(exc))
    context = _base_context("shipping", request)
    context.update(form=form, eligible_cod_shipments=eligible)
    return render(request, "backoffice/pages/shipping/cod_settlement_add.html", context)


def cod_settlement_detail(request, settlement_id):
    settlement = get_object_or_404(
        CODSettlement.objects.select_related("courier").prefetch_related(
            "items__shipment__order",
            "items__payment_transaction",
        ),
        pk=settlement_id,
    )
    context = _base_context("shipping", request)
    context.update(settlement=settlement)
    return render(request, "backoffice/pages/shipping/cod_settlement_detail.html", context)
