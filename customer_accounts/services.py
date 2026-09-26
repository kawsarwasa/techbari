from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from customers.models import Customer, CustomerGroup
from sales.models import SalesOrder

from .models import CustomerAccount


@transaction.atomic
def register_customer_account(*, name, phone, email, password, previous_order_number=""):
    User = get_user_model()
    if CustomerAccount.objects.filter(customer__phone=phone).exists():
        raise ValidationError("A customer account already exists for this mobile number.")
    if User.objects.filter(username=phone).exists():
        raise ValidationError("This mobile number is already used by another login.")
    if email and CustomerAccount.objects.filter(customer__email__iexact=email).exists():
        raise ValidationError("A customer account already exists for this email address.")

    customer = Customer.objects.select_for_update().filter(phone=phone).first()
    if customer:
        if not customer.is_active:
            raise ValidationError("We couldn't securely verify this existing customer record. Please contact TechBari support to activate your online account.")

        # Existing CRM identities may expose order history, warranty and balances.
        # A phone number alone is not enough to claim that record. Require a valid
        # previous order, and when any trusted email is already on file require an
        # exact email match as a second knowledge check.
        if customer.email and customer.email.casefold() != (email or "").casefold():
            raise ValidationError("For security, use an email already linked with this customer or a previous TechBari order.")

        historical_orders = customer.sales_orders.exclude(
            status__in=[SalesOrder.Status.DRAFT, SalesOrder.Status.CANCELLED]
        )
        if not historical_orders.exists():
            raise ValidationError("We couldn't securely verify this existing customer record. Please contact TechBari support to activate your online account.")
        if not previous_order_number:
            raise ValidationError("For security, enter one previous TechBari order number to link your existing purchase history.")

        matched_order = historical_orders.filter(order_number__iexact=previous_order_number).first()
        if matched_order is None:
            raise ValidationError("The previous order number could not be verified for this mobile number.")

        known_emails = set()
        if customer.email:
            known_emails.add(customer.email.strip().casefold())
        for historical_email in historical_orders.exclude(shipping_email="").values_list("shipping_email", flat=True):
            normalized = (historical_email or "").strip().casefold()
            if normalized:
                known_emails.add(normalized)

        normalized_email = (email or "").strip().casefold()
        if known_emails and normalized_email not in known_emails:
            raise ValidationError("For security, use an email already linked with this customer or a previous TechBari order.")

        # Do not rewrite the existing CRM name/source/status during account claiming.
        # If the CRM had no email at all, a supplied email may be attached only after
        # the previous-order challenge has succeeded.
        if email and not customer.email:
            if Customer.objects.select_for_update().filter(email__iexact=email).exclude(pk=customer.pk).exists():
                raise ValidationError("This email is already linked to another customer record.")
            customer.email = email
            customer.save(update_fields=["email", "updated_at"])

        account_name = customer.name
        account_email = customer.email or email
    else:
        if email and Customer.objects.select_for_update().filter(email__iexact=email).exclude(phone=phone).exists():
            raise ValidationError("This email is already linked to another customer record.")
        group = CustomerGroup.objects.filter(code="RETAIL", is_active=True).first()
        customer = Customer.objects.create(name=name, phone=phone, email=email, group=group, source=Customer.Source.ONLINE, is_active=True)
        account_name = customer.name
        account_email = customer.email

    user = User.objects.create_user(
        username=phone,
        email=account_email,
        password=password,
        first_name=account_name[:150],
        is_staff=False,
        is_active=True,
    )
    return CustomerAccount.objects.create(user=user, customer=customer, is_active=True, link_verified_at=timezone.now())


def find_customer_account(identity):
    value = (identity or "").strip()
    if not value:
        return None
    qs = CustomerAccount.objects.select_related("user", "customer").filter(is_active=True, user__is_active=True, customer__is_active=True)
    compact = "".join(ch for ch in value if ch.isdigit())
    if compact.startswith("880"):
        compact = "0" + compact[3:]
    if len(compact) == 11 and compact.startswith("01"):
        return qs.filter(customer__phone=compact).first()
    return qs.filter(customer__email__iexact=value.lower()).first()


@transaction.atomic
def update_customer_profile(account, *, name, email, address, city, district, postal_code):
    customer = Customer.objects.select_for_update().get(pk=account.customer_id)
    if email and Customer.objects.filter(email__iexact=email).exclude(pk=customer.pk).exists():
        raise ValidationError("This email is already linked to another customer.")
    customer.name = name
    customer.email = email
    customer.address = address
    customer.city = city
    customer.district = district
    customer.postal_code = postal_code
    customer.save(update_fields=["name", "email", "address", "city", "district", "postal_code", "updated_at"])
    user = account.user
    user.first_name = name[:150]
    user.email = email
    user.save(update_fields=["first_name", "email"])
    return customer


@transaction.atomic
def save_customer_address(account, form):
    address = form.save(commit=False)
    address.account = account
    if not account.addresses.exists():
        address.is_default = True
    if address.is_default:
        account.addresses.exclude(pk=address.pk).update(is_default=False)
    address.save()
    return address


@transaction.atomic
def delete_customer_address(account, address):
    was_default = address.is_default
    address.delete()
    if was_default:
        replacement = account.addresses.order_by("-updated_at", "-id").first()
        if replacement:
            replacement.is_default = True
            replacement.save(update_fields=["is_default", "updated_at"])
