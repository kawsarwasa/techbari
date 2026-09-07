from decimal import Decimal

from django.db.models import Q
from django.http import Http404, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from customers.forms import CustomerForm, CustomerGroupForm
from customers.models import Customer, CustomerGroup
from customers.services import CustomerError, delete_customer, delete_customer_group
from .context import page_context


NOTICE_TEXT = {
    "customer-saved": "Customer saved successfully.",
    "customer-deleted": "Customer deleted successfully.",
    "group-saved": "Customer group saved successfully.",
    "group-deleted": "Customer group deleted successfully.",
}


def _message(exc):
    if hasattr(exc, "messages"):
        return " ".join(str(value) for value in exc.messages)
    return str(exc)


def _money(value):
    return f"৳ {Decimal(value or 0):,.2f}"


def _base_context(page_name, request):
    context = page_context(page_name)
    context["crm_database"] = True
    context["crm_notice"] = NOTICE_TEXT.get(request.GET.get("notice", ""), "")
    context["crm_error"] = request.GET.get("error", "")
    return context


def customers(request):
    context = _base_context("customers", request)
    qs = Customer.objects.select_related("group").all()
    query = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    group_id = (request.GET.get("group") or "").strip()
    source = (request.GET.get("source") or "").strip()
    if query:
        qs = qs.filter(
            Q(customer_no__icontains=query)
            | Q(name__icontains=query)
            | Q(phone__icontains=query)
            | Q(email__icontains=query)
        )
    if status == "active":
        qs = qs.filter(is_active=True)
    elif status == "inactive":
        qs = qs.filter(is_active=False)
    if group_id.isdigit():
        qs = qs.filter(group_id=int(group_id))
    if source in {value for value, _ in Customer.Source.choices}:
        qs = qs.filter(source=source)

    all_customers = list(Customer.objects.select_related("group").all())
    active_count = sum(1 for customer in all_customers if customer.is_active)
    repeat_count = sum(1 for customer in all_customers if customer.repeat_customer)
    total_due = sum((customer.due_balance for customer in all_customers), Decimal("0.00"))
    total_spent = sum((customer.total_spent for customer in all_customers), Decimal("0.00"))
    context.update(
        customer_rows=qs,
        customer_query=query,
        customer_status=status,
        customer_group=group_id,
        customer_source=source,
        customer_groups=CustomerGroup.objects.filter(is_active=True).order_by("name"),
        customer_source_choices=Customer.Source.choices,
        customer_stats=[
            {"label": "Total Customers", "value": str(len(all_customers)), "trend": "Live CRM", "trend_class": "up", "icon": "backoffice/components/icons/icon_2.html", "color": "blue"},
            {"label": "Active", "value": str(active_count), "trend": "Live", "trend_class": "up", "icon": "backoffice/components/icons/icon_7.html", "color": "green"},
            {"label": "Repeat Customers", "value": str(repeat_count), "trend": "2+ completed", "trend_class": "up", "icon": "backoffice/components/icons/icon_12.html", "color": "purple"},
            {"label": "Customer Due", "value": _money(total_due), "trend": _money(total_spent), "trend_class": "up", "icon": "backoffice/components/icons/icon_1.html", "color": "red"},
        ],
    )
    return render(request, "backoffice/pages/customers/customers.html", context)


def customer_add(request):
    customer_id = request.GET.get("id") or request.POST.get("customer_id")
    instance = get_object_or_404(Customer, pk=customer_id) if customer_id else None
    form = CustomerForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        customer = form.save()
        return redirect(reverse("backoffice:customer_detail_id", args=[customer.pk]) + "?notice=customer-saved")
    context = _base_context("customer_add", request)
    context.update(form=form, customer_obj=instance, is_edit=bool(instance))
    return render(request, "backoffice/pages/customers/customer_add.html", context)


def customer_detail(request, customer_id=None):
    if customer_id is None:
        raw_id = request.GET.get("id")
        if not raw_id or not str(raw_id).isdigit():
            raise Http404("Customer not found")
        customer_id = int(raw_id)
    customer = get_object_or_404(Customer.objects.select_related("group"), pk=customer_id)
    orders = customer.sales_orders.select_related("warehouse").prefetch_related("items").order_by("-order_date", "-id")[:25]
    context = _base_context("customer_detail", request)
    context.update(customer=customer, customer_orders=orders)
    return render(request, "backoffice/pages/customers/customer_detail.html", context)


def customer_delete(request, customer_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    customer = get_object_or_404(Customer, pk=customer_id)
    try:
        delete_customer(customer=customer)
        return redirect(reverse("backoffice:customers") + "?notice=customer-deleted")
    except CustomerError as exc:
        return redirect(reverse("backoffice:customers") + "?error=" + _message(exc))


def customer_groups(request):
    group_id = request.GET.get("id") or request.POST.get("group_id")
    instance = get_object_or_404(CustomerGroup, pk=group_id) if group_id else None
    form = CustomerGroupForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        group = form.save()
        return redirect(reverse("backoffice:customer_groups") + f"?id={group.pk}&notice=group-saved")
    context = _base_context("customers", request)
    context.update(
        group_form=form,
        group_obj=instance,
        customer_group_rows=CustomerGroup.objects.all().order_by("name"),
    )
    return render(request, "backoffice/pages/customers/customer_groups.html", context)


def customer_group_delete(request, group_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    group = get_object_or_404(CustomerGroup, pk=group_id)
    try:
        delete_customer_group(group=group)
        return redirect(reverse("backoffice:customer_groups") + "?notice=group-deleted")
    except CustomerError as exc:
        return redirect(reverse("backoffice:customer_groups") + "?error=" + _message(exc))
