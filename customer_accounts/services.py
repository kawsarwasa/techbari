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
        if customer.email and customer.email.casefold() != (email or "").casefold():
            raise ValidationError("For security, use the email already linked with this mobile number.")
        historical_orders = customer.sales_orders.exclude(status__in=[SalesOrder.Status.DRAFT, SalesOrder.Status.CANCELLED])
        if historical_orders.exists():
            if not previous_order_number:
                raise ValidationError("For security, enter one previous TechBari order number to link your existing purchase history.")
            if not historical_orders.filter(order_number__iexact=previous_order_number).exists():
                raise ValidationError("The previous order number could not be verified for this mobile number.")
        elif customer.opening_due and customer.opening_due > 0:
            # A pre-existing CRM balance is sensitive business history. Without a prior
            # SalesOrder challenge or a verified OTP channel, do not let self-registration
            # claim that record merely by knowing its phone number.
            raise ValidationError("This existing customer record has a balance. Contact TechBari support to activate online account access securely.")
    else:
        if email and Customer.objects.select_for_update().filter(email__iexact=email).exclude(phone=phone).exists():
            raise ValidationError("This email is already linked to another customer record.")
        group = CustomerGroup.objects.filter(code="RETAIL", is_active=True).first()
        customer = Customer.objects.create(name=name, phone=phone, email=email, group=group, source=Customer.Source.ONLINE, is_active=True)

    changed = []
    for field, value in {"name": name, "source": Customer.Source.ONLINE, "is_active": True}.items():
        if getattr(customer, field) != value:
            setattr(customer, field, value)
            changed.append(field)
    if email and customer.email != email:
        customer.email = email
        changed.append("email")
    if changed:
        changed.append("updated_at")
        customer.save(update_fields=changed)

    user = User.objects.create_user(username=phone, email=email, password=password, first_name=name[:150], is_staff=False, is_active=True)
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
