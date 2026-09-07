from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction

from catalog.models import Product, ProductVariant
from customers.models import Customer
from inventory.models import InventoryBalance, Warehouse

from .models import SalesOrder
from .services import SalesOrderError, delete_draft_order, save_sales_order, transition_order, update_order_payment


class POSError(ValidationError):
    pass


def _decimal(value, label):
    try:
        return Decimal(str(value if value not in (None, "") else "0"))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise POSError(f"Invalid {label}.") from exc


def _customer(customer_id):
    if not customer_id:
        return None
    try:
        customer_id = int(customer_id)
    except (TypeError, ValueError) as exc:
        raise POSError("Select a valid customer.") from exc
    customer = Customer.objects.filter(pk=customer_id, is_active=True).first()
    if not customer:
        raise POSError("Selected customer is not available.")
    return customer


def _warehouse(warehouse_id):
    try:
        warehouse_id = int(warehouse_id)
    except (TypeError, ValueError) as exc:
        raise POSError("Select a valid warehouse.") from exc
    warehouse = Warehouse.objects.filter(pk=warehouse_id, is_active=True).first()
    if not warehouse:
        raise POSError("Selected warehouse is not available.")
    return warehouse


def _price(variant):
    return variant.price_override if variant.price_override is not None else variant.product.current_price


def build_pos_item_rows(*, items, warehouse):
    if not isinstance(items, list) or not items:
        raise POSError("Add at least one product to the POS cart.")
    merged = {}
    for index, raw in enumerate(items, start=1):
        if not isinstance(raw, dict):
            raise POSError(f"Invalid POS cart row {index}.")
        try:
            variant_id = int(raw.get("variant_id"))
            quantity = int(raw.get("qty"))
        except (TypeError, ValueError) as exc:
            raise POSError(f"Invalid SKU or quantity on POS row {index}.") from exc
        if quantity <= 0 or quantity > 999:
            raise POSError("POS quantity must be between 1 and 999.")
        merged[variant_id] = merged.get(variant_id, 0) + quantity

    variants = {
        variant.pk: variant
        for variant in ProductVariant.objects.select_related("product", "product__category", "product__brand").filter(
            pk__in=merged,
            is_active=True,
            product__status=Product.Status.ACTIVE,
            product__category__is_active=True,
            product__brand__is_active=True,
        )
    }
    if len(variants) != len(merged):
        raise POSError("One or more POS SKUs are inactive or unavailable.")

    balances = {
        row.variant_id: row
        for row in InventoryBalance.objects.filter(warehouse=warehouse, variant_id__in=merged)
    }
    rows = []
    for variant_id, quantity in merged.items():
        variant = variants[variant_id]
        balance = balances.get(variant_id)
        available = balance.available_quantity if balance else 0
        if quantity > available:
            raise POSError(
                f"Not enough stock for {variant.sku} in {warehouse.name}. Available: {available}."
            )
        rows.append(
            {
                "variant": variant,
                "quantity": quantity,
                "unit_price": _price(variant),
                "discount_amount": Decimal("0.00"),
            }
        )
    return rows


def _header(*, customer, warehouse, discount_amount, note, status):
    walk_in_name = customer.name if customer else "Walk-in Customer"
    walk_in_phone = customer.phone if customer else "POS-WALK-IN"
    return {
        "customer": customer,
        "warehouse": warehouse,
        "channel": SalesOrder.Channel.POS,
        "status": status,
        "shipping_name": walk_in_name,
        "shipping_phone": walk_in_phone,
        "shipping_email": customer.email if customer else "",
        "shipping_address": customer.address if customer else "POS counter sale",
        "shipping_city": customer.city if customer else "",
        "shipping_district": customer.district if customer else "",
        "shipping_postal_code": customer.postal_code if customer else "",
        "discount_amount": discount_amount,
        "shipping_charge": Decimal("0.00"),
        "amount_paid": Decimal("0.00"),
        "notes": note or "POS counter sale",
    }


def _validate_discount(item_rows, discount_amount):
    subtotal = sum((row["unit_price"] * row["quantity"] for row in item_rows), Decimal("0.00"))
    if discount_amount < 0:
        raise POSError("Discount cannot be negative.")
    if discount_amount > subtotal:
        raise POSError("Discount cannot exceed POS subtotal.")
    return subtotal


def _held_order(order_id):
    if not order_id:
        return None
    try:
        order_id = int(order_id)
    except (TypeError, ValueError) as exc:
        raise POSError("Invalid held order.") from exc
    order = SalesOrder.objects.filter(pk=order_id, channel=SalesOrder.Channel.POS).first()
    if not order or order.status != SalesOrder.Status.DRAFT:
        raise POSError("Held POS order is no longer available.")
    return order


@transaction.atomic
def hold_pos_order(*, warehouse_id, customer_id=None, items=None, discount_amount=0, note="", order_id=None, actor="POS"):
    warehouse = _warehouse(warehouse_id)
    customer = _customer(customer_id)
    item_rows = build_pos_item_rows(items=items, warehouse=warehouse)
    discount_amount = _decimal(discount_amount, "discount")
    _validate_discount(item_rows, discount_amount)
    order = _held_order(order_id)
    try:
        order = save_sales_order(
            header_data=_header(
                customer=customer,
                warehouse=warehouse,
                discount_amount=discount_amount,
                note=note,
                status=SalesOrder.Status.DRAFT,
            ),
            item_rows=item_rows,
            order=order,
            actor=actor,
        )
    except SalesOrderError as exc:
        raise POSError(exc.messages if hasattr(exc, "messages") else str(exc)) from exc
    order.payment_method = ""
    order.payment_reference = ""
    order.tendered_amount = Decimal("0.00")
    order.change_amount = Decimal("0.00")
    order.save(update_fields=["payment_method", "payment_reference", "tendered_amount", "change_amount", "updated_at"])
    return order


@transaction.atomic
def complete_pos_sale(
    *,
    warehouse_id,
    customer_id=None,
    items=None,
    discount_amount=0,
    note="",
    payment_method="cash",
    payment_reference="",
    tendered_amount=None,
    order_id=None,
    actor="POS",
):
    warehouse = _warehouse(warehouse_id)
    customer = _customer(customer_id)
    item_rows = build_pos_item_rows(items=items, warehouse=warehouse)
    discount_amount = _decimal(discount_amount, "discount")
    _validate_discount(item_rows, discount_amount)
    order = _held_order(order_id)
    try:
        order = save_sales_order(
            header_data=_header(
                customer=customer,
                warehouse=warehouse,
                discount_amount=discount_amount,
                note=note,
                status=SalesOrder.Status.PENDING,
            ),
            item_rows=item_rows,
            order=order,
            actor=actor,
        )
    except SalesOrderError as exc:
        raise POSError(exc.messages if hasattr(exc, "messages") else str(exc)) from exc

    method = str(payment_method or "cash").lower()
    valid_methods = {choice for choice, _ in SalesOrder.PaymentMethod.choices}
    if method not in valid_methods:
        raise POSError("Select a valid POS payment method.")
    reference = str(payment_reference or "").strip()
    if method != SalesOrder.PaymentMethod.CASH and not reference:
        raise POSError("Payment reference is required for Card, bKash or Nagad POS sales.")

    tendered = _decimal(order.grand_total if tendered_amount in (None, "") else tendered_amount, "tendered amount")
    if tendered < order.grand_total:
        raise POSError(f"Tendered amount cannot be below the sale total ({order.grand_total}).")
    if method != SalesOrder.PaymentMethod.CASH and tendered != order.grand_total:
        raise POSError("Non-cash POS payment must match the sale total exactly.")

    order.payment_method = method
    order.payment_reference = reference
    order.tendered_amount = tendered
    order.change_amount = tendered - order.grand_total if method == SalesOrder.PaymentMethod.CASH else Decimal("0.00")
    order.save(update_fields=["payment_method", "payment_reference", "tendered_amount", "change_amount", "updated_at"])

    try:
        order = update_order_payment(
            order=order,
            amount_paid=order.grand_total,
            actor=actor,
            note=f"POS payment captured via {order.get_payment_method_display()}.",
        )
        order = transition_order(order=order, new_status=SalesOrder.Status.CONFIRMED, actor=actor, note="POS sale confirmed.")
        order = transition_order(order=order, new_status=SalesOrder.Status.COMPLETED, actor=actor, note="POS sale completed at counter.")
    except SalesOrderError as exc:
        raise POSError(exc.messages if hasattr(exc, "messages") else str(exc)) from exc
    return SalesOrder.objects.select_related("customer", "warehouse").prefetch_related("items").get(pk=order.pk)


@transaction.atomic
def discard_pos_hold(*, order_id):
    order = _held_order(order_id)
    try:
        delete_draft_order(order=order)
    except SalesOrderError as exc:
        raise POSError(exc.messages if hasattr(exc, "messages") else str(exc)) from exc
