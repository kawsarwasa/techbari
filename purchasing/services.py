from decimal import Decimal, InvalidOperation
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from catalog.models import ProductVariant
from inventory.models import StockMovement
from inventory.services import InventoryError, post_movement
from serial_tracking.models import SerializedUnit
from serial_tracking.services import SerialTrackingError, change_serial_unit_status, register_serial_unit
from .models import (
    PurchaseOrder,
    PurchaseOrderItem,
    PurchasePayment,
    PurchaseReceipt,
    PurchaseReceiptItem,
    PurchaseReturn,
    PurchaseReturnItem,
    PurchaseReturnSerialUnit,
    Supplier,
)


class PurchasingError(ValidationError):
    pass


def make_reference(prefix):
    stamp = timezone.localtime().strftime("%y%m%d%H%M%S")
    return f"{prefix}-{stamp}-{uuid4().hex[:6].upper()}"


def _error_text(exc):
    if hasattr(exc, "messages"):
        return " ".join(str(message) for message in exc.messages)
    return str(exc)


def parse_purchase_items(post):
    variant_ids = post.getlist("variant_id")
    quantities = post.getlist("ordered_quantity")
    unit_costs = post.getlist("unit_cost")
    discounts = post.getlist("line_discount")
    count = max(len(variant_ids), len(quantities), len(unit_costs), len(discounts), 0)
    rows = []
    seen = set()
    for index in range(count):
        raw_variant = variant_ids[index].strip() if index < len(variant_ids) else ""
        raw_qty = quantities[index].strip() if index < len(quantities) else ""
        raw_cost = unit_costs[index].strip() if index < len(unit_costs) else ""
        raw_discount = discounts[index].strip() if index < len(discounts) else ""
        if not any((raw_variant, raw_qty, raw_cost, raw_discount)):
            continue
        if not raw_variant.isdigit():
            raise PurchasingError(f"Row {index + 1}: choose a product variant/SKU.")
        try:
            quantity = int(raw_qty)
        except (TypeError, ValueError) as exc:
            raise PurchasingError(f"Row {index + 1}: quantity must be a whole number.") from exc
        try:
            unit_cost = Decimal(raw_cost or "0")
            discount = Decimal(raw_discount or "0")
        except InvalidOperation as exc:
            raise PurchasingError(f"Row {index + 1}: enter valid cost/discount amounts.") from exc
        if quantity <= 0:
            raise PurchasingError(f"Row {index + 1}: quantity must be greater than zero.")
        if unit_cost < 0 or discount < 0:
            raise PurchasingError(f"Row {index + 1}: cost and discount cannot be negative.")
        variant_id = int(raw_variant)
        if variant_id in seen:
            raise PurchasingError("Each Variant/SKU can appear only once in a purchase order.")
        seen.add(variant_id)
        try:
            variant = ProductVariant.objects.select_related("product").get(pk=variant_id, is_active=True)
        except ProductVariant.DoesNotExist as exc:
            raise PurchasingError(f"Row {index + 1}: selected Variant/SKU is not active or does not exist.") from exc
        if discount > Decimal(quantity) * unit_cost:
            raise PurchasingError(f"Row {index + 1}: line discount cannot exceed line value.")
        rows.append({"variant": variant, "ordered_quantity": quantity, "unit_cost": unit_cost, "discount_amount": discount})
    if not rows:
        raise PurchasingError("Add at least one purchase item.")
    return rows


def parse_serial_lines(raw_text):
    rows = []
    for line_number, raw_line in enumerate((raw_text or "").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        parts = [part.strip() for part in line.replace(",", "|").split("|")]
        while len(parts) < 3:
            parts.append("")
        if len(parts) > 3:
            raise PurchasingError(f"Serial line {line_number}: use SERIAL | IMEI1 | IMEI2 format.")
        serial_number, imei1, imei2 = parts
        if serial_number and serial_number.isdigit() and len(serial_number) == 15 and not imei1 and not imei2:
            imei1, serial_number = serial_number, ""
        if not any((serial_number, imei1, imei2)):
            continue
        rows.append({"serial_number": serial_number or None, "imei1": imei1 or None, "imei2": imei2 or None})
    return rows


@transaction.atomic
def save_purchase_order(*, header_data, item_rows, purchase=None, actor=""):
    if purchase:
        purchase = PurchaseOrder.objects.select_for_update().get(pk=purchase.pk)
        if purchase.receipts.exists() or purchase.returns.exists() or purchase.payments.exists():
            raise PurchasingError("A purchase with receipts, returns or payments cannot be structurally edited.")
        if purchase.status == PurchaseOrder.Status.CANCELLED:
            raise PurchasingError("A cancelled purchase cannot be edited.")
    else:
        purchase = PurchaseOrder()

    status = header_data.get("status", PurchaseOrder.Status.DRAFT)
    if status not in {PurchaseOrder.Status.DRAFT, PurchaseOrder.Status.ORDERED}:
        raise PurchasingError("A purchase form can save only Draft or Ordered status before receiving stock.")
    supplier = header_data["supplier"]
    warehouse = header_data["warehouse"]
    if not supplier.is_active:
        raise PurchasingError("Choose an active supplier.")
    if not warehouse.is_active:
        raise PurchasingError("Choose an active warehouse.")

    for field in (
        "po_number",
        "supplier",
        "warehouse",
        "status",
        "purchase_date",
        "expected_date",
        "supplier_invoice_no",
        "invoice_date",
        "shipping_cost",
        "other_cost",
        "discount_amount",
        "notes",
    ):
        setattr(purchase, field, header_data.get(field))
    purchase.actor = actor
    purchase.full_clean()
    purchase.save()

    purchase.items.all().delete()
    for row in item_rows:
        item = PurchaseOrderItem(purchase=purchase, **row)
        item.full_clean()
        item.save()
    purchase.refresh_from_db()
    if purchase.discount_amount > purchase.subtotal + purchase.shipping_cost + purchase.other_cost:
        raise PurchasingError("Order discount cannot exceed purchase value.")
    return purchase


@transaction.atomic
def receive_purchase(*, purchase, received_date, quantities, serial_payloads=None, supplier_challan_no="", note="", actor=""):
    purchase = PurchaseOrder.objects.select_for_update().select_related("supplier", "warehouse").get(pk=purchase.pk)
    if purchase.status not in {PurchaseOrder.Status.ORDERED, PurchaseOrder.Status.PARTIALLY_RECEIVED}:
        raise PurchasingError("Only Ordered or Partially Received purchases can receive stock.")
    if received_date < purchase.purchase_date:
        raise PurchasingError("Receipt date cannot be before purchase date.")

    locked_items = {
        item.pk: item
        for item in PurchaseOrderItem.objects.select_for_update().select_related("variant", "variant__product").filter(purchase=purchase)
    }
    serial_payloads = serial_payloads or {}
    normalized = []
    for item_id, raw_qty in quantities.items():
        try:
            quantity = int(raw_qty or 0)
        except (TypeError, ValueError) as exc:
            raise PurchasingError("Receipt quantities must be whole numbers.") from exc
        if quantity < 0:
            raise PurchasingError("Receipt quantity cannot be negative.")
        if not quantity:
            continue
        item = locked_items.get(int(item_id))
        if not item:
            raise PurchasingError("A receipt item does not belong to this purchase.")
        if quantity > item.remaining_to_receive:
            raise PurchasingError(f"Cannot receive {quantity} of {item.variant.sku}; only {item.remaining_to_receive} remain.")
        serial_rows = serial_payloads.get(item.pk, [])
        if len(serial_rows) > quantity:
            raise PurchasingError(f"{item.variant.sku}: serial/IMEI rows cannot exceed received quantity.")
        normalized.append((item, quantity, serial_rows))
    if not normalized:
        raise PurchasingError("Enter at least one quantity to receive.")

    receipt = PurchaseReceipt(
        receipt_no=make_reference("GRN"),
        purchase=purchase,
        warehouse=purchase.warehouse,
        received_date=received_date,
        supplier_challan_no=supplier_challan_no,
        note=note,
        actor=actor,
    )
    receipt.full_clean()
    receipt.save()

    try:
        for item, quantity, serial_rows in normalized:
            post_movement(
                warehouse=purchase.warehouse,
                variant=item.variant,
                movement_type=StockMovement.Type.PURCHASE_IN,
                quantity_delta=quantity,
                reference_type="purchase_receipt",
                reference_no=receipt.receipt_no,
                note=f"{purchase.po_number}. {note}".strip(),
                actor=actor,
            )
            PurchaseReceiptItem.objects.create(
                receipt=receipt,
                purchase_item=item,
                quantity=quantity,
                serial_data=serial_rows,
            )
            item.received_quantity += quantity
            item.full_clean()
            item.save(update_fields=["received_quantity"])

            for identifiers in serial_rows:
                register_serial_unit(
                    data={
                        "variant": item.variant,
                        "warehouse": purchase.warehouse,
                        "serial_number": identifiers.get("serial_number"),
                        "imei1": identifiers.get("imei1"),
                        "imei2": identifiers.get("imei2"),
                        "status": SerializedUnit.Status.AVAILABLE,
                        "supplier_reference": purchase.supplier.code,
                        "purchase_reference": purchase.po_number,
                        "purchase_date": purchase.purchase_date,
                        "purchase_cost": item.unit_cost,
                        "received_date": received_date,
                        "sales_reference": "",
                        "customer_reference": "",
                        "sold_at": None,
                        "warranty_type": "",
                        "warranty_start_date": None,
                        "warranty_end_date": None,
                        "supplier_warranty_reference": "",
                        "notes": f"Received through {receipt.receipt_no}.",
                    },
                    actor=actor,
                )
    except (InventoryError, SerialTrackingError, ValidationError) as exc:
        raise PurchasingError(_error_text(exc)) from exc

    if all(item.received_quantity >= item.ordered_quantity for item in locked_items.values()):
        purchase.status = PurchaseOrder.Status.RECEIVED
    else:
        purchase.status = PurchaseOrder.Status.PARTIALLY_RECEIVED
    purchase.save(update_fields=["status", "updated_at"])
    return receipt


@transaction.atomic
def pay_purchase(*, purchase, amount, method, payment_date, reference="", note="", actor=""):
    purchase = PurchaseOrder.objects.select_for_update().select_related("supplier").get(pk=purchase.pk)
    if purchase.status in {PurchaseOrder.Status.DRAFT, PurchaseOrder.Status.CANCELLED}:
        raise PurchasingError("Draft or cancelled purchases cannot receive supplier payments.")
    amount = Decimal(amount)
    if amount <= 0:
        raise PurchasingError("Payment amount must be greater than zero.")
    outstanding = purchase.outstanding_amount
    if amount > outstanding:
        raise PurchasingError(f"Payment cannot exceed outstanding amount ({outstanding}).")
    payment = PurchasePayment(
        payment_no=make_reference("PAY"),
        purchase=purchase,
        supplier=purchase.supplier,
        amount=amount,
        method=method,
        reference=reference,
        payment_date=payment_date,
        note=note,
        actor=actor,
    )
    payment.full_clean()
    payment.save()
    return payment


@transaction.atomic
def return_purchase(*, purchase, return_date, quantities, serial_unit_ids=None, reason, note="", actor=""):
    purchase = PurchaseOrder.objects.select_for_update().select_related("supplier", "warehouse").get(pk=purchase.pk)
    if purchase.status not in {PurchaseOrder.Status.PARTIALLY_RECEIVED, PurchaseOrder.Status.RECEIVED}:
        raise PurchasingError("Only received purchases can be returned to the supplier.")
    if return_date < purchase.purchase_date:
        raise PurchasingError("Return date cannot be before purchase date.")

    locked_items = {
        item.pk: item
        for item in PurchaseOrderItem.objects.select_for_update().select_related("variant", "variant__product").filter(purchase=purchase)
    }
    serial_unit_ids = serial_unit_ids or {}
    normalized = []
    for item_id, raw_qty in quantities.items():
        try:
            quantity = int(raw_qty or 0)
        except (TypeError, ValueError) as exc:
            raise PurchasingError("Return quantities must be whole numbers.") from exc
        if quantity < 0:
            raise PurchasingError("Return quantity cannot be negative.")
        if not quantity:
            continue
        item = locked_items.get(int(item_id))
        if not item:
            raise PurchasingError("A return item does not belong to this purchase.")
        if quantity > item.remaining_to_return:
            raise PurchasingError(f"Cannot return {quantity} of {item.variant.sku}; only {item.remaining_to_return} are returnable.")
        unit_ids = [int(value) for value in serial_unit_ids.get(item.pk, []) if str(value).isdigit()]
        if len(set(unit_ids)) != len(unit_ids):
            raise PurchasingError(f"{item.variant.sku}: duplicate serialized unit selected.")
        if len(unit_ids) > quantity:
            raise PurchasingError(f"{item.variant.sku}: serialized units cannot exceed return quantity.")
        normalized.append((item, quantity, unit_ids))
    if not normalized:
        raise PurchasingError("Enter at least one quantity to return.")

    purchase_return = PurchaseReturn(
        return_no=make_reference("PRTN"),
        purchase=purchase,
        supplier=purchase.supplier,
        warehouse=purchase.warehouse,
        return_date=return_date,
        reason=reason,
        note=note,
        actor=actor,
    )
    purchase_return.full_clean()
    purchase_return.save()

    try:
        for item, quantity, unit_ids in normalized:
            return_item = PurchaseReturnItem.objects.create(
                purchase_return=purchase_return,
                purchase_item=item,
                quantity=quantity,
                unit_cost=item.unit_cost,
            )
            serial_count = 0
            for unit_id in unit_ids:
                try:
                    unit = SerializedUnit.objects.select_for_update().select_related("variant", "warehouse").get(pk=unit_id)
                except SerializedUnit.DoesNotExist as exc:
                    raise PurchasingError("Selected serialized unit does not exist.") from exc
                if unit.variant_id != item.variant_id or unit.warehouse_id != purchase.warehouse_id:
                    raise PurchasingError(f"Serialized unit {unit.display_identifier} does not match this purchase item/warehouse.")
                if unit.purchase_reference != purchase.po_number:
                    raise PurchasingError(f"Serialized unit {unit.display_identifier} was not received against {purchase.po_number}.")
                if unit.status not in {SerializedUnit.Status.AVAILABLE, SerializedUnit.Status.RETURNED}:
                    raise PurchasingError(f"Serialized unit {unit.display_identifier} is not available for supplier return.")
                change_serial_unit_status(
                    unit,
                    SerializedUnit.Status.SUPPLIER_RETURNED,
                    actor=actor,
                    note=f"Returned to supplier under {purchase_return.return_no}. {reason}",
                    reference_no=purchase_return.return_no,
                )
                PurchaseReturnSerialUnit.objects.create(return_item=return_item, unit=unit)
                serial_count += 1

            non_serial_quantity = quantity - serial_count
            if non_serial_quantity:
                post_movement(
                    warehouse=purchase.warehouse,
                    variant=item.variant,
                    movement_type=StockMovement.Type.PURCHASE_RETURN_OUT,
                    quantity_delta=-non_serial_quantity,
                    reference_type="purchase_return",
                    reference_no=purchase_return.return_no,
                    note=f"{purchase.po_number}. {reason}. {note}".strip(),
                    actor=actor,
                )
            item.returned_quantity += quantity
            item.full_clean()
            item.save(update_fields=["returned_quantity"])
    except (InventoryError, SerialTrackingError, ValidationError) as exc:
        raise PurchasingError(_error_text(exc)) from exc
    return purchase_return


@transaction.atomic
def cancel_purchase(*, purchase, actor=""):
    purchase = PurchaseOrder.objects.select_for_update().get(pk=purchase.pk)
    if purchase.receipts.exists() or purchase.returns.exists():
        raise PurchasingError("A purchase with received/returned stock cannot be cancelled.")
    if purchase.status == PurchaseOrder.Status.RECEIVED:
        raise PurchasingError("A received purchase cannot be cancelled.")
    if purchase.payments.exists():
        raise PurchasingError("Reverse supplier payments before cancelling this purchase.")
    purchase.status = PurchaseOrder.Status.CANCELLED
    purchase.actor = actor
    purchase.save(update_fields=["status", "actor", "updated_at"])
    return purchase


@transaction.atomic
def delete_draft_purchase(*, purchase):
    purchase = PurchaseOrder.objects.select_for_update().get(pk=purchase.pk)
    if purchase.status != PurchaseOrder.Status.DRAFT:
        raise PurchasingError("Only draft purchases can be deleted.")
    if purchase.receipts.exists() or purchase.payments.exists() or purchase.returns.exists():
        raise PurchasingError("This purchase has linked transactions and cannot be deleted.")
    purchase.delete()


@transaction.atomic
def delete_supplier(*, supplier):
    supplier = Supplier.objects.select_for_update().get(pk=supplier.pk)
    if supplier.purchase_orders.exists() or supplier.purchase_payments.exists() or supplier.purchase_returns.exists():
        raise PurchasingError("Supplier has purchase history and cannot be deleted. Mark it inactive instead.")
    supplier.delete()
