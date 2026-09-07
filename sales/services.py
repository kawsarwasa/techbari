from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction

from catalog.models import ProductVariant
from inventory.services import (
    InventoryError,
    issue_reserved_stock,
    release_reserved_stock,
    reserve_stock,
)

from .models import SalesOrder, SalesOrderHistory, SalesOrderItem, make_order_number


class SalesOrderError(ValidationError):
    pass


EDITABLE_STATUSES = {SalesOrder.Status.DRAFT, SalesOrder.Status.PENDING}
RESERVED_STATUSES = {SalesOrder.Status.PENDING, SalesOrder.Status.CONFIRMED, SalesOrder.Status.PROCESSING}


def _decimal(value, field_name):
    try:
        return Decimal(str(value or "0"))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise SalesOrderError(f"Invalid {field_name}.") from exc


def parse_order_items(post):
    variant_ids = post.getlist("variant_id")
    quantities = post.getlist("quantity")
    prices = post.getlist("unit_price")
    discounts = post.getlist("line_discount")
    row_count = max(len(variant_ids), len(quantities), len(prices), len(discounts), 0)
    rows = []
    seen = set()
    for index in range(row_count):
        variant_id = variant_ids[index].strip() if index < len(variant_ids) else ""
        quantity_raw = quantities[index].strip() if index < len(quantities) else ""
        price_raw = prices[index].strip() if index < len(prices) else ""
        discount_raw = discounts[index].strip() if index < len(discounts) else "0"
        if not variant_id and not quantity_raw and not price_raw:
            continue
        if not variant_id.isdigit():
            raise SalesOrderError(f"Select a valid SKU on order line {index + 1}.")
        variant = ProductVariant.objects.select_related("product").filter(pk=int(variant_id), is_active=True).first()
        if not variant:
            raise SalesOrderError(f"Order line {index + 1} uses an unavailable SKU.")
        if variant.pk in seen:
            raise SalesOrderError(f"SKU {variant.sku} appears more than once. Combine duplicate rows.")
        seen.add(variant.pk)
        try:
            quantity = int(quantity_raw)
        except (TypeError, ValueError) as exc:
            raise SalesOrderError(f"Invalid quantity on order line {index + 1}.") from exc
        if quantity <= 0:
            raise SalesOrderError("Order quantity must be greater than zero.")
        default_price = variant.price_override if variant.price_override is not None else variant.product.current_price
        unit_price = _decimal(price_raw if price_raw != "" else default_price, "unit price")
        discount_amount = _decimal(discount_raw, "line discount")
        if unit_price < 0 or discount_amount < 0:
            raise SalesOrderError("Price and discount cannot be negative.")
        if discount_amount > unit_price * quantity:
            raise SalesOrderError(f"Line discount cannot exceed the line value for {variant.sku}.")
        rows.append(
            {
                "variant": variant,
                "quantity": quantity,
                "unit_price": unit_price,
                "discount_amount": discount_amount,
            }
        )
    if not rows:
        raise SalesOrderError("Add at least one order item.")
    return rows


def _history(order, event, *, previous_status="", new_status="", note="", actor=""):
    return SalesOrderHistory.objects.create(
        order=order,
        event=event,
        previous_status=previous_status or "",
        new_status=new_status or "",
        note=note,
        actor=actor,
    )


def _derive_payment_status(order):
    paid = order.amount_paid or Decimal("0.00")
    target = order.payable_total
    if target <= 0 and (order.return_credit_amount or Decimal("0.00")) > 0:
        return SalesOrder.PaymentStatus.REFUNDED
    if paid <= 0:
        return SalesOrder.PaymentStatus.UNPAID
    if paid >= target:
        return SalesOrder.PaymentStatus.PAID
    return SalesOrder.PaymentStatus.PARTIAL


def _recalculate(order):
    subtotal = sum((item.line_total for item in order.items.all()), Decimal("0.00"))
    discount = order.discount_amount or Decimal("0.00")
    shipping = order.shipping_charge or Decimal("0.00")
    total = max(subtotal - discount + shipping, Decimal("0.00"))
    order.subtotal = subtotal
    order.grand_total = total
    if order.amount_paid > order.payable_total:
        raise SalesOrderError("Paid amount cannot exceed the payable order total after return credits.")
    order.payment_status = _derive_payment_status(order)
    order.save(update_fields=["subtotal", "grand_total", "payment_status", "updated_at"])
    return order


def _release_reserved(order, *, actor=""):
    for item in order.items.select_related("variant").all():
        if item.reserved_quantity <= 0:
            continue
        try:
            release_reserved_stock(
                warehouse=order.warehouse,
                variant=item.variant,
                quantity=item.reserved_quantity,
                reference_no=order.order_number,
                note="Sales order reservation released.",
                actor=actor,
            )
        except InventoryError as exc:
            raise SalesOrderError(str(exc)) from exc
        item.reserved_quantity = 0
        item.save(update_fields=["reserved_quantity"])


def _reserve_remaining(order, *, actor=""):
    for item in order.items.select_related("variant").all():
        remaining = item.quantity - item.issued_quantity - item.reserved_quantity
        if remaining <= 0:
            continue
        try:
            reserve_stock(
                warehouse=order.warehouse,
                variant=item.variant,
                quantity=remaining,
                reference_no=order.order_number,
                note="Reserved for sales order.",
                actor=actor,
            )
        except InventoryError as exc:
            raise SalesOrderError(str(exc)) from exc
        item.reserved_quantity += remaining
        item.save(update_fields=["reserved_quantity"])


def _issue_all_reserved(order, *, actor=""):
    _reserve_remaining(order, actor=actor)
    for item in order.items.select_related("variant").all():
        remaining = item.quantity - item.issued_quantity
        if remaining <= 0:
            continue
        if item.reserved_quantity < remaining:
            raise SalesOrderError(f"Reservation mismatch for {item.sku_snapshot}.")
        try:
            issue_reserved_stock(
                warehouse=order.warehouse,
                variant=item.variant,
                quantity=remaining,
                reference_no=order.order_number,
                note="Sales order completed / sold.",
                actor=actor,
            )
        except InventoryError as exc:
            raise SalesOrderError(str(exc)) from exc
        item.issued_quantity += remaining
        item.reserved_quantity -= remaining
        item.save(update_fields=["issued_quantity", "reserved_quantity"])


def _fill_customer_snapshot(order):
    if not order.customer_id:
        return
    customer = order.customer
    if not order.shipping_name:
        order.shipping_name = customer.name
    if not order.shipping_phone:
        order.shipping_phone = customer.phone
    if not order.shipping_email:
        order.shipping_email = customer.email
    if not order.shipping_address:
        order.shipping_address = customer.address
    if not order.shipping_city:
        order.shipping_city = customer.city
    if not order.shipping_district:
        order.shipping_district = customer.district
    if not order.shipping_postal_code:
        order.shipping_postal_code = customer.postal_code


@transaction.atomic
def save_sales_order(*, header_data, item_rows, order=None, actor=""):
    is_new = order is None
    if order is not None:
        order = SalesOrder.objects.select_for_update().select_related("customer", "warehouse").get(pk=order.pk)
        if order.status not in EDITABLE_STATUSES:
            raise SalesOrderError("Only Draft or Pending orders can be edited.")
        _release_reserved(order, actor=actor)
    else:
        order = SalesOrder()

    target_status = header_data.get("status") or SalesOrder.Status.DRAFT
    if target_status not in EDITABLE_STATUSES:
        raise SalesOrderError("Create or edit an order as Draft or Pending, then use status actions.")

    for field in [
        "customer",
        "warehouse",
        "channel",
        "status",
        "order_date",
        "shipping_name",
        "shipping_phone",
        "shipping_email",
        "shipping_address",
        "shipping_city",
        "shipping_district",
        "shipping_postal_code",
        "discount_amount",
        "shipping_charge",
        "amount_paid",
        "notes",
    ]:
        if field in header_data:
            setattr(order, field, header_data[field])
    number = (header_data.get("order_number") or "").strip().upper()
    if number:
        order.order_number = number
    elif not order.order_number:
        order.order_number = make_order_number()
    if is_new:
        order.created_by = actor
    _fill_customer_snapshot(order)
    if not order.shipping_name or not order.shipping_phone:
        raise SalesOrderError("Shipping name and phone are required.")
    order.save()

    order.items.all().delete()
    for row in item_rows:
        variant = row["variant"]
        SalesOrderItem.objects.create(
            order=order,
            variant=variant,
            product_snapshot=variant.product.name,
            variant_snapshot=variant.name,
            sku_snapshot=variant.sku,
            quantity=int(row["quantity"]),
            unit_price=row["unit_price"],
            discount_amount=row.get("discount_amount") or Decimal("0.00"),
        )
    _recalculate(order)

    if target_status == SalesOrder.Status.PENDING:
        _reserve_remaining(order, actor=actor)
        _history(
            order,
            SalesOrderHistory.Event.STOCK,
            note="Order stock reserved.",
            actor=actor,
        )

    _history(
        order,
        SalesOrderHistory.Event.CREATED if is_new else SalesOrderHistory.Event.UPDATED,
        previous_status="" if is_new else order.status,
        new_status=order.status,
        note="Sales order created." if is_new else "Sales order updated.",
        actor=actor,
    )
    return order


ALLOWED_TRANSITIONS = {
    SalesOrder.Status.DRAFT: {SalesOrder.Status.PENDING, SalesOrder.Status.CONFIRMED, SalesOrder.Status.CANCELLED},
    SalesOrder.Status.PENDING: {SalesOrder.Status.CONFIRMED, SalesOrder.Status.CANCELLED},
    SalesOrder.Status.CONFIRMED: {SalesOrder.Status.PROCESSING, SalesOrder.Status.COMPLETED, SalesOrder.Status.CANCELLED},
    SalesOrder.Status.PROCESSING: {SalesOrder.Status.COMPLETED, SalesOrder.Status.CANCELLED},
    SalesOrder.Status.COMPLETED: set(),
    SalesOrder.Status.CANCELLED: set(),
}


@transaction.atomic
def transition_order(*, order, new_status, actor="", note=""):
    order = SalesOrder.objects.select_for_update().select_related("customer", "warehouse").get(pk=order.pk)
    old_status = order.status
    if new_status == old_status:
        return order
    if new_status not in ALLOWED_TRANSITIONS.get(old_status, set()):
        raise SalesOrderError(f"Cannot move order from {order.get_status_display()} to {SalesOrder.Status(new_status).label}.")

    if new_status in RESERVED_STATUSES:
        _reserve_remaining(order, actor=actor)
    elif new_status == SalesOrder.Status.COMPLETED:
        _issue_all_reserved(order, actor=actor)
    elif new_status == SalesOrder.Status.CANCELLED:
        if order.items.filter(issued_quantity__gt=0).exists():
            raise SalesOrderError("A sold/completed order cannot be cancelled. Use the Returns module.")
        _release_reserved(order, actor=actor)

    order.status = new_status
    order.save(update_fields=["status", "updated_at"])
    _history(
        order,
        SalesOrderHistory.Event.STATUS,
        previous_status=old_status,
        new_status=new_status,
        note=note or f"Status changed from {old_status} to {new_status}.",
        actor=actor,
    )
    return order


@transaction.atomic
def update_order_payment(*, order, amount_paid, actor="", note=""):
    order = SalesOrder.objects.select_for_update().get(pk=order.pk)
    if order.status == SalesOrder.Status.CANCELLED:
        raise SalesOrderError("Payment cannot be updated on a cancelled order.")
    amount_paid = _decimal(amount_paid, "paid amount")
    if amount_paid < 0:
        raise SalesOrderError("Paid amount cannot be negative.")
    if amount_paid > order.payable_total:
        raise SalesOrderError("Paid amount cannot exceed the payable order total after return credits.")
    old_paid = order.amount_paid
    order.amount_paid = amount_paid
    order.payment_status = _derive_payment_status(order)
    order.save(update_fields=["amount_paid", "payment_status", "updated_at"])
    _history(
        order,
        SalesOrderHistory.Event.PAYMENT,
        note=note or f"Paid amount changed from {old_paid} to {amount_paid}.",
        actor=actor,
    )
    return order


@transaction.atomic
def delete_draft_order(*, order):
    order = SalesOrder.objects.select_for_update().get(pk=order.pk)
    if order.status != SalesOrder.Status.DRAFT:
        raise SalesOrderError("Only Draft orders can be deleted. Cancel active orders to preserve history.")
    if order.items.filter(reserved_quantity__gt=0).exists():
        raise SalesOrderError("Draft order has unexpected reservations and cannot be deleted safely.")
    order.delete()
