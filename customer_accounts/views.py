from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from catalog.models import Product
from sales.models import SalesOrder
from serial_tracking.models import SerializedUnit
from storefront.context import catalog_context
from storefront.forms import normalize_bd_phone

from .decorators import customer_account_required
from .forms import CustomerLoginForm, CustomerProfileForm, CustomerRegistrationForm, SavedAddressForm, TrackOrderForm, WarrantyLookupForm
from .models import CustomerAccount, SavedAddress, WishlistItem
from .services import delete_customer_address, find_customer_account, register_customer_account, save_customer_address, update_customer_profile


def _safe_next(request, default):
    target = request.POST.get("next") or request.GET.get("next") or ""
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return target
    return default


def _auth_context(request, *, mode, login_form=None, register_form=None):
    context = catalog_context()
    context.update(
        auth_mode=mode,
        login_form=login_form or CustomerLoginForm(),
        register_form=register_form or CustomerRegistrationForm(),
        next_url=request.POST.get("next") or request.GET.get("next") or "",
    )
    return context


def login_view(request):
    existing = CustomerAccount.objects.filter(user_id=request.user.pk, is_active=True, customer__is_active=True).first() if request.user.is_authenticated else None
    if existing:
        return redirect("customer_accounts:dashboard")
    form = CustomerLoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        account = find_customer_account(form.cleaned_data["identity"])
        user = None
        if account:
            user = authenticate(request, username=account.user.username, password=form.cleaned_data["password"])
        if user and account and not user.is_staff:
            login(request, user)
            if not form.cleaned_data.get("remember"):
                request.session.set_expiry(0)
            account.last_login_at = timezone.now()
            account.save(update_fields=["last_login_at", "updated_at"])
            return redirect(_safe_next(request, reverse("customer_accounts:dashboard")))
        form.add_error(None, "Invalid email/phone or password.")
    return render(request, "storefront/pages/login.html", _auth_context(request, mode="login", login_form=form))


def register_view(request):
    existing = CustomerAccount.objects.filter(user_id=request.user.pk, is_active=True, customer__is_active=True).first() if request.user.is_authenticated else None
    if existing:
        return redirect("customer_accounts:dashboard")
    form = CustomerRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            account = register_customer_account(
                name=form.cleaned_data["name"],
                phone=form.cleaned_data["phone"],
                email=form.cleaned_data["email"],
                password=form.cleaned_data["password1"],
                previous_order_number=form.cleaned_data.get("previous_order_number", ""),
            )
        except ValidationError as exc:
            form.add_error(None, " ".join(getattr(exc, "messages", [str(exc)])))
        else:
            user = authenticate(request, username=account.user.username, password=form.cleaned_data["password1"])
            if user:
                login(request, user)
            messages.success(request, "Your TechBari account is ready.")
            return redirect(_safe_next(request, reverse("customer_accounts:dashboard")))
    return render(request, "storefront/pages/login.html", _auth_context(request, mode="register", register_form=form))


@require_POST
def logout_view(request):
    logout(request)
    return redirect("storefront:home")


@customer_account_required
def dashboard(request):
    account = request.customer_account
    order_qs = SalesOrder.objects.filter(customer=account.customer).exclude(status=SalesOrder.Status.DRAFT).select_related("warehouse")
    active_orders = order_qs.exclude(status__in=[SalesOrder.Status.CANCELLED, SalesOrder.Status.COMPLETED])
    context = catalog_context()
    context.update(
        account=account,
        recent_orders=order_qs[:5],
        total_orders=order_qs.count(),
        active_order_count=active_orders.count(),
        total_spent=sum((order.payable_total for order in order_qs.filter(status=SalesOrder.Status.COMPLETED)), Decimal("0.00")),
        due_balance=account.customer.due_balance,
        wishlist_count=account.wishlist_items.count(),
        address_count=account.addresses.count(),
        account_active="dashboard",
    )
    return render(request, "customer_accounts/dashboard.html", context)


@customer_account_required
def orders(request):
    account = request.customer_account
    qs = SalesOrder.objects.filter(customer=account.customer).exclude(status=SalesOrder.Status.DRAFT).prefetch_related("items")
    status = (request.GET.get("status") or "").strip()
    valid_statuses = {value for value, _label in SalesOrder.Status.choices}
    if status in valid_statuses:
        qs = qs.filter(status=status)
    context = catalog_context()
    context.update(account=account, orders=qs, selected_status=status, status_choices=SalesOrder.Status.choices, account_active="orders")
    return render(request, "customer_accounts/orders.html", context)


@customer_account_required
def order_detail(request, order_number):
    account = request.customer_account
    order = get_object_or_404(
        SalesOrder.objects.filter(customer=account.customer).exclude(status=SalesOrder.Status.DRAFT).select_related("warehouse", "shipment__courier").prefetch_related("items__variant__product", "history", "shipment__events"),
        order_number=order_number,
    )
    context = catalog_context()
    context.update(account=account, order=order, account_active="orders")
    return render(request, "customer_accounts/order_detail.html", context)


@customer_account_required
def profile(request):
    account = request.customer_account
    customer = account.customer
    initial = {"name": customer.name, "email": customer.email, "address": customer.address, "city": customer.city, "district": customer.district, "postal_code": customer.postal_code}
    form = CustomerProfileForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            update_customer_profile(account, **form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, " ".join(getattr(exc, "messages", [str(exc)])))
        else:
            messages.success(request, "Profile updated.")
            return redirect("customer_accounts:profile")
    context = catalog_context()
    context.update(account=account, profile_form=form, account_active="profile")
    return render(request, "customer_accounts/profile.html", context)


@customer_account_required
def addresses(request):
    account = request.customer_account
    context = catalog_context()
    context.update(account=account, addresses=account.addresses.all(), account_active="addresses")
    return render(request, "customer_accounts/addresses.html", context)


@customer_account_required
def address_add(request):
    account = request.customer_account
    form = SavedAddressForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        save_customer_address(account, form)
        messages.success(request, "Address saved.")
        return redirect("customer_accounts:addresses")
    context = catalog_context()
    context.update(account=account, address_form=form, address_title="Add Address", account_active="addresses")
    return render(request, "customer_accounts/address_form.html", context)


@customer_account_required
def address_edit(request, pk):
    account = request.customer_account
    address = get_object_or_404(SavedAddress, pk=pk, account=account)
    form = SavedAddressForm(request.POST or None, instance=address)
    if request.method == "POST" and form.is_valid():
        save_customer_address(account, form)
        messages.success(request, "Address updated.")
        return redirect("customer_accounts:addresses")
    context = catalog_context()
    context.update(account=account, address_form=form, address_title="Edit Address", address_obj=address, account_active="addresses")
    return render(request, "customer_accounts/address_form.html", context)


@require_POST
@customer_account_required
def address_delete(request, pk):
    account = request.customer_account
    address = get_object_or_404(SavedAddress, pk=pk, account=account)
    delete_customer_address(account, address)
    messages.success(request, "Address removed.")
    return redirect("customer_accounts:addresses")


@customer_account_required
def password_change(request):
    account = request.customer_account
    form = PasswordChangeForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        messages.success(request, "Password changed successfully.")
        return redirect("customer_accounts:password_change")
    context = catalog_context()
    context.update(account=account, password_form=form, account_active="password")
    return render(request, "customer_accounts/password_change.html", context)


@customer_account_required
def warranty_lookup(request):
    account = request.customer_account
    form = WarrantyLookupForm(request.GET or None)
    unit = None
    if form.is_valid():
        identifier = form.cleaned_data["identifier"]
        order_numbers = list(SalesOrder.objects.filter(customer=account.customer).values_list("order_number", flat=True))
        scope = Q(customer_reference__in=[account.customer.customer_no, account.customer.phone])
        if order_numbers:
            scope |= Q(sales_reference__in=order_numbers)
        unit = SerializedUnit.objects.select_related("variant__product", "warehouse").prefetch_related("warranty_claims").filter(Q(serial_number__iexact=identifier) | Q(imei1=identifier) | Q(imei2=identifier)).filter(scope).first()
        if not unit:
            form.add_error("identifier", "No Serial/IMEI linked to your TechBari purchases was found.")
    context = catalog_context()
    context.update(account=account, warranty_form=form, warranty_unit=unit, account_active="warranty")
    return render(request, "customer_accounts/warranty.html", context)


@customer_account_required
def wishlist_view(request):
    account = request.customer_account
    ids = list(account.wishlist_items.values_list("product_id", flat=True))
    context = catalog_context()
    product_map = {row["pk"]: row for row in context["catalog"]}
    context.update(
        account=account,
        wishlist_products=[product_map[pk] for pk in ids if pk in product_map],
        recommended_products=[row for row in context["catalog"] if row["pk"] not in ids][:6],
    )
    return render(request, "storefront/pages/wishlist.html", context)


@require_POST
@customer_account_required
def wishlist_toggle(request, product_id):
    account = request.customer_account
    product = get_object_or_404(Product, public_id=product_id, status=Product.Status.ACTIVE, category__is_active=True, brand__is_active=True)
    item = WishlistItem.objects.filter(account=account, product=product).first()
    if item:
        item.delete()
    else:
        WishlistItem.objects.create(account=account, product=product)
    target = request.POST.get("next") or reverse("storefront:wishlist")
    if not url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        target = reverse("storefront:wishlist")
    return redirect(target)


def track_order_view(request):
    form = TrackOrderForm(request.POST or None)
    order = None
    if request.method == "POST" and form.is_valid():
        candidate = SalesOrder.objects.select_related("customer", "shipment__courier").prefetch_related("history", "shipment__events").filter(order_number__iexact=form.cleaned_data["order_number"]).first()
        if candidate:
            order_phone = normalize_bd_phone(candidate.customer_phone or candidate.shipping_phone)
            if order_phone == form.cleaned_data["phone"]:
                order = candidate
        if not order:
            form.add_error(None, "Order not found. Check the order number and phone number.")
    context = catalog_context()
    context.update(track_form=form, tracked_order=order)
    return render(request, "storefront/pages/track_order.html", context)
