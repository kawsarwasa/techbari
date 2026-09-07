from decimal import Decimal
from urllib.parse import urlencode

from django.core.exceptions import ValidationError
from django.db.models import Q, Sum
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from payments.forms import PaymentCaptureForm, PaymentMethodConfigForm, PaymentRefundForm, ReconciliationForm
from payments.models import PaymentMethodConfig, PaymentTransaction
from payments.services import (
    PaymentError,
    capture_sales_payment,
    reconcile_payment,
    refundable_amount,
    refund_sales_payment,
    reverse_sales_payment,
)
from sales.models import SalesOrder

from .context import page_context


ZERO = Decimal("0.00")
NOTICE_TEXT = {
    "payment-recorded": "Payment transaction recorded successfully.",
    "payment-refunded": "Refund transaction recorded successfully.",
    "payment-reversed": "Payment was reversed successfully.",
    "payment-reconciled": "Reconciliation status updated.",
    "method-saved": "Payment method configuration updated.",
}


def _message(exc):
    if hasattr(exc, "messages"):
        return " ".join(str(value) for value in exc.messages)
    return str(exc)


def _redirect_with(route_name, *, args=None, notice="", error=""):
    url = reverse(route_name, args=args or [])
    params = {}
    if notice:
        params["notice"] = notice
    if error:
        params["error"] = error
    return redirect(url + ("?" + urlencode(params) if params else ""))


def _base_context(page_name, request):
    context = page_context(page_name)
    context["payment_database"] = True
    context["payment_notice"] = NOTICE_TEXT.get(request.GET.get("notice", ""), "")
    context["payment_error"] = request.GET.get("error", "")
    return context


def payments(request):
    context = _base_context("payments", request)
    qs = PaymentTransaction.objects.select_related(
        "sales_order",
        "sales_order__customer",
        "purchase_payment",
        "purchase_payment__supplier",
        "purchase_payment__purchase",
        "parent_transaction",
    )
    query = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    method = (request.GET.get("method") or "").strip()
    kind = (request.GET.get("kind") or "").strip()
    reconciliation = (request.GET.get("reconciliation") or "").strip()
    if query:
        qs = qs.filter(
            Q(transaction_no__icontains=query)
            | Q(provider_reference__icontains=query)
            | Q(external_id__icontains=query)
            | Q(sales_order__order_number__icontains=query)
            | Q(sales_order__customer__name__icontains=query)
            | Q(purchase_payment__payment_no__icontains=query)
            | Q(purchase_payment__purchase__po_number__icontains=query)
            | Q(purchase_payment__supplier__name__icontains=query)
        )
    if status in {value for value, _ in PaymentTransaction.Status.choices}:
        qs = qs.filter(status=status)
    if method in {value for value, _ in PaymentMethodConfig.Method.choices}:
        qs = qs.filter(method=method)
    if kind in {value for value, _ in PaymentTransaction.Kind.choices}:
        qs = qs.filter(kind=kind)
    if reconciliation in {value for value, _ in PaymentTransaction.ReconciliationStatus.choices}:
        qs = qs.filter(reconciliation_status=reconciliation)

    all_qs = PaymentTransaction.objects.all()
    received = all_qs.filter(
        direction=PaymentTransaction.Direction.IN,
        status__in=[PaymentTransaction.Status.COMPLETED, PaymentTransaction.Status.REVERSED],
    ).aggregate(total=Sum("amount"))["total"] or ZERO
    paid_out = all_qs.filter(
        direction=PaymentTransaction.Direction.OUT,
        status=PaymentTransaction.Status.COMPLETED,
    ).aggregate(total=Sum("amount"))["total"] or ZERO
    unreconciled = all_qs.filter(
        reconciliation_status=PaymentTransaction.ReconciliationStatus.UNRECONCILED,
        status__in=[PaymentTransaction.Status.COMPLETED, PaymentTransaction.Status.REVERSED],
    ).count()
    pending = all_qs.filter(status=PaymentTransaction.Status.PENDING).count()

    context.update(
        payment_rows=qs.order_by("-transaction_date", "-id"),
        payment_query=query,
        payment_status=status,
        payment_method=method,
        payment_kind=kind,
        payment_reconciliation=reconciliation,
        payment_status_choices=PaymentTransaction.Status.choices,
        payment_method_choices=PaymentMethodConfig.Method.choices,
        payment_kind_choices=PaymentTransaction.Kind.choices,
        payment_reconciliation_choices=PaymentTransaction.ReconciliationStatus.choices,
        payment_stats=[
            {"label": "Money In", "value": f"৳ {received:,.2f}", "trend": "Completed", "trend_class": "up", "icon": "backoffice/components/icons/icon_1.html", "color": "green"},
            {"label": "Money Out", "value": f"৳ {paid_out:,.2f}", "trend": "Refunds + suppliers", "trend_class": "up", "icon": "backoffice/components/icons/icon_2.html", "color": "red"},
            {"label": "Net Cash Flow", "value": f"৳ {(received - paid_out):,.2f}", "trend": "Payment ledger", "trend_class": "up", "icon": "backoffice/components/icons/icon_12.html", "color": "blue"},
            {"label": "Needs Review", "value": str(unreconciled), "trend": f"{pending} pending", "trend_class": "up", "icon": "backoffice/components/icons/icon_14.html", "color": "orange"},
        ],
    )
    return render(request, "backoffice/pages/payments/payments.html", context)


def payment_add(request):
    order = None
    order_id = request.GET.get("order") or request.POST.get("order_id")
    if order_id and str(order_id).isdigit():
        order = SalesOrder.objects.filter(pk=int(order_id)).first()
    form = PaymentCaptureForm(request.POST or None, order=order)
    error = ""
    if request.method == "POST" and form.is_valid():
        try:
            payment = capture_sales_payment(
                order=form.cleaned_data["sales_order"],
                amount=form.cleaned_data["amount"],
                method=form.cleaned_data["method"],
                reference=form.cleaned_data["reference"],
                note=form.cleaned_data["note"],
                transaction_date=form.cleaned_data.get("transaction_date"),
                actor="Dashboard",
                channel="dashboard",
            )
            return _redirect_with("backoffice:payment_detail", args=[payment.pk], notice="payment-recorded")
        except (PaymentError, ValidationError) as exc:
            error = _message(exc)
    elif request.method == "POST":
        error = "Please correct the highlighted payment fields."

    context = _base_context("payment_add", request)
    context.update(payment_form=form, selected_order=order, payment_form_error=error)
    return render(request, "backoffice/pages/payments/payment_add.html", context)


def payment_detail(request, payment_id):
    payment = get_object_or_404(
        PaymentTransaction.objects.select_related(
            "sales_order",
            "sales_order__customer",
            "purchase_payment",
            "purchase_payment__purchase",
            "purchase_payment__supplier",
            "parent_transaction",
        ).prefetch_related("events", "child_transactions"),
        pk=payment_id,
    )
    context = _base_context("payments", request)
    context.update(
        payment=payment,
        refundable=refundable_amount(payment),
        refund_form=PaymentRefundForm(initial={"amount": refundable_amount(payment)}),
        reconciliation_form=ReconciliationForm(initial={"reconciliation_status": payment.reconciliation_status}),
    )
    return render(request, "backoffice/pages/payments/payment_detail.html", context)


def payment_refund(request, payment_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    payment = get_object_or_404(PaymentTransaction, pk=payment_id)
    form = PaymentRefundForm(request.POST)
    if not form.is_valid():
        return _redirect_with("backoffice:payment_detail", args=[payment.pk], error="Enter a valid refund amount.")
    try:
        refund_sales_payment(
            payment=payment,
            amount=form.cleaned_data["amount"],
            reference=form.cleaned_data["reference"],
            note=form.cleaned_data["note"],
            actor="Dashboard",
        )
        return _redirect_with("backoffice:payment_detail", args=[payment.pk], notice="payment-refunded")
    except (PaymentError, ValidationError) as exc:
        return _redirect_with("backoffice:payment_detail", args=[payment.pk], error=_message(exc))


def payment_reverse(request, payment_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    payment = get_object_or_404(PaymentTransaction, pk=payment_id)
    try:
        reverse_sales_payment(
            payment=payment,
            reference=request.POST.get("reference", ""),
            note=request.POST.get("note", ""),
            actor="Dashboard",
        )
        return _redirect_with("backoffice:payment_detail", args=[payment.pk], notice="payment-reversed")
    except (PaymentError, ValidationError) as exc:
        return _redirect_with("backoffice:payment_detail", args=[payment.pk], error=_message(exc))


def payment_reconcile(request, payment_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    payment = get_object_or_404(PaymentTransaction, pk=payment_id)
    form = ReconciliationForm(request.POST)
    if not form.is_valid():
        return _redirect_with("backoffice:payment_detail", args=[payment.pk], error="Choose a valid reconciliation status.")
    try:
        reconcile_payment(
            payment=payment,
            status=form.cleaned_data["reconciliation_status"],
            note=form.cleaned_data["note"],
            actor="Dashboard",
        )
        return _redirect_with("backoffice:payment_detail", args=[payment.pk], notice="payment-reconciled")
    except (PaymentError, ValidationError) as exc:
        return _redirect_with("backoffice:payment_detail", args=[payment.pk], error=_message(exc))


def payment_methods(request):
    context = _base_context("payments", request)
    method_id = request.POST.get("method_id") if request.method == "POST" else None
    if request.method == "POST":
        config = get_object_or_404(PaymentMethodConfig, pk=method_id)
        form = PaymentMethodConfigForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            return _redirect_with("backoffice:payment_methods", notice="method-saved")
        context["payment_error"] = "Please correct the payment method settings."
    context["payment_methods"] = PaymentMethodConfig.objects.all()
    return render(request, "backoffice/pages/payments/payment_methods.html", context)
