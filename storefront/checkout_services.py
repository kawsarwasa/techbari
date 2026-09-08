from decimal import Decimal
from urllib.parse import urlencode

from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from catalog.models import Product, ProductVariant
from customers.models import Customer, CustomerGroup
from inventory.services import get_default_warehouse
from promotions.services import PromotionError, apply_flash_sale_prices, coupon_discount_for_rows, record_campaign_conversion, redeem_coupon
from sales.models import SalesOrder, make_order_number
from sales.services import SalesOrderError, save_sales_order
from store_settings.services import get_store_settings, shipping_charge_for_subtotal
from .forms import CHECKOUT_SIGNING_SALT


class CheckoutError(ValidationError):
    pass


def create_checkout_token():
    for _ in range(10):
        order_number = make_order_number()
        if not SalesOrder.objects.filter(order_number=order_number).exists():
            return signing.dumps({"order_number": order_number}, salt=CHECKOUT_SIGNING_SALT)
    raise CheckoutError("Could not initialize checkout. Please refresh and try again.")


def success_token(order):
    return signing.dumps({"order_number": order.order_number}, salt=CHECKOUT_SIGNING_SALT)


def verify_success_token(order_number, token):
    try:
        payload = signing.loads(token or "", salt=CHECKOUT_SIGNING_SALT, max_age=86400 * 7)
    except signing.BadSignature as exc:
        raise CheckoutError("Invalid order confirmation link.") from exc
    if not isinstance(payload, dict) or payload.get("order_number") != order_number:
        raise CheckoutError("Invalid order confirmation link.")
    return True


def checkout_success_url(order):
    base = reverse("storefront:checkout_success", kwargs={"order_number": order.order_number})
    return f"{base}?{urlencode({'token': success_token(order)})}"


def _resolve_order_lines(cart_payload):
    ids = [row["variant_id"] for row in cart_payload]
    variants = {variant.pk: variant for variant in ProductVariant.objects.select_related("product", "product__category", "product__brand").filter(pk__in=ids)}
    rows = []
    for line in cart_payload:
        variant = variants.get(line["variant_id"])
        if not variant:
            raise CheckoutError("One of the selected products is no longer available.")
        product = variant.product
        if not variant.is_active or product.status != Product.Status.ACTIVE or not product.category.is_active or not product.brand.is_active:
            raise CheckoutError(f"{product.name} / {variant.name} is no longer available.")
        unit_price = variant.price_override if variant.price_override is not None else product.current_price
        rows.append({"variant": variant, "quantity": int(line["qty"]), "unit_price": Decimal(unit_price), "discount_amount": Decimal("0.00")})
    if len(rows) != len(cart_payload):
        raise CheckoutError("Your cart changed while checking out. Please refresh and try again.")
    return apply_flash_sale_prices(rows)


def _customer_for_checkout(data):
    phone = data["phone"]
    customer = Customer.objects.select_for_update().filter(phone=phone).first()
    email = data.get("email") or ""
    if email:
        email_owner = Customer.objects.filter(email__iexact=email).exclude(phone=phone).first()
        if email_owner:
            raise CheckoutError("This email is already linked to another customer account. Use the phone number linked to that account or leave email blank.")
    address_bits = [data.get("address"), data.get("upazila"), data.get("district"), data.get("division")]
    latest_address = ", ".join(str(bit).strip() for bit in address_bits if str(bit or "").strip())
    if data.get("landmark"):
        latest_address += f" (Landmark: {data['landmark'].strip()})"
    if customer:
        changed = []
        updates = {"name": data["full_name"], "email": email, "source": Customer.Source.ONLINE, "address": latest_address, "city": data.get("upazila") or "", "district": data.get("district") or "", "is_active": True}
        for field, value in updates.items():
            if getattr(customer, field) != value:
                setattr(customer, field, value); changed.append(field)
        if changed:
            changed.append("updated_at"); customer.save(update_fields=changed)
        return customer
    group = CustomerGroup.objects.filter(code="RETAIL", is_active=True).first()
    return Customer.objects.create(name=data["full_name"], phone=phone, email=email, group=group, source=Customer.Source.ONLINE, address=latest_address, city=data.get("upazila") or "", district=data.get("district") or "", is_active=True)


def _order_notes(data, campaign_attribution=None):
    delivery = "Inside Dhaka" if data["delivery_option"] == "inside" else "Outside Dhaka"
    parts = ["Storefront Checkout", "Payment: Cash on Delivery", f"Delivery: {delivery}", f"Division: {data['division']}"]
    if data.get("landmark"): parts.append(f"Landmark: {data['landmark'].strip()}")
    if data.get("coupon_code"): parts.append(f"Coupon: {data['coupon_code']}")
    if campaign_attribution and campaign_attribution.get("campaign"):
        parts.append(f"Campaign: {campaign_attribution['campaign'].code}")
    if data.get("order_note"): parts.append(f"Customer note: {data['order_note'].strip()}")
    return " | ".join(parts)


@transaction.atomic
def place_checkout_order(cleaned_data, *, campaign_attribution=None):
    token_data = cleaned_data["checkout_token"]
    order_number = token_data["order_number"]
    existing = SalesOrder.objects.select_related("customer", "warehouse").filter(order_number=order_number, channel=SalesOrder.Channel.ONLINE).first()
    if existing:
        return existing, False
    rows = _resolve_order_lines(cleaned_data["cart_payload"])
    try:
        coupon, discount = coupon_discount_for_rows(cleaned_data.get("coupon_code") or "", rows, lock=True)
    except PromotionError as exc:
        raise CheckoutError(" ".join(str(value) for value in getattr(exc, "messages", [str(exc)]))) from exc

    store = get_store_settings()
    merchandise_subtotal = sum((Decimal(row["unit_price"]) * int(row["quantity"]) for row in rows), Decimal("0.00"))
    shipping = shipping_charge_for_subtotal(merchandise_subtotal, cleaned_data["delivery_option"], store=store)
    if shipping is None:
        raise CheckoutError("Select a valid delivery option.")
    if cleaned_data.get("payment_method") != "cod":
        raise CheckoutError("Only Cash on Delivery is available in this phase.")
    if not store.cod_enabled:
        raise CheckoutError("Cash on Delivery is currently disabled by the store.")

    customer = _customer_for_checkout(cleaned_data)
    warehouse = get_default_warehouse()
    shipping_address = cleaned_data["address"].strip()
    if cleaned_data.get("landmark"): shipping_address += f" (Landmark: {cleaned_data['landmark'].strip()})"
    header = {"order_number": order_number, "customer": customer, "warehouse": warehouse, "channel": SalesOrder.Channel.ONLINE, "status": SalesOrder.Status.PENDING, "order_date": timezone.localdate(), "shipping_name": cleaned_data["full_name"], "shipping_phone": cleaned_data["phone"], "shipping_email": cleaned_data.get("email") or "", "shipping_address": shipping_address, "shipping_city": cleaned_data.get("upazila") or "", "shipping_district": cleaned_data.get("district") or "", "shipping_postal_code": "", "discount_amount": discount, "shipping_charge": shipping, "amount_paid": Decimal("0.00"), "notes": _order_notes(cleaned_data, campaign_attribution)}
    try:
        order = save_sales_order(header_data=header, item_rows=rows, actor="Storefront Checkout")
        redeem_coupon(coupon=coupon, order=order, discount_amount=discount)
        record_campaign_conversion(order=order, attribution=campaign_attribution, coupon=coupon)
    except (SalesOrderError, PromotionError) as exc:
        raise CheckoutError(" ".join(str(value) for value in getattr(exc, "messages", [str(exc)]))) from exc
    return order, True
