from decimal import Decimal
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
from django.utils import timezone

from inventory.models import Warehouse
from payments.models import PaymentTransaction
from sales.models import SalesOrder, SalesOrderItem
from serial_tracking.models import SerializedUnit


ZERO = Decimal("0.00")


def make_return_number():
    stamp = timezone.localtime().strftime("%y%m%d")
    return f"RET-{stamp}-{uuid4().hex[:7].upper()}"


class SalesReturn(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        APPROVED = "approved", "Approved"
        RECEIVED = "received", "Received / Inspecting"
        COMPLETED = "completed", "Completed"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    class Source(models.TextChoices):
        CUSTOMER = "customer", "Customer Return"
        COURIER_RETURN = "courier_return", "Courier Return"
        POS = "pos", "POS / Counter Return"
        MANUAL = "manual", "Manual / Other"

    class Resolution(models.TextChoices):
        REFUND = "refund", "Refund / Credit"
        NO_REFUND = "no_refund", "No Refund"

    class Reason(models.TextChoices):
        DEFECTIVE = "defective", "Defective Product"
        DAMAGED = "damaged", "Damaged Product"
        WRONG_ITEM = "wrong_item", "Wrong Item"
        NOT_AS_DESCRIBED = "not_as_described", "Not as Described"
        CHANGED_MIND = "changed_mind", "Changed Mind"
        COURIER_RETURN = "courier_return", "Courier Returned Parcel"
        OTHER = "other", "Other"

    return_no = models.CharField(max_length=64, unique=True, default=make_return_number)
    order = models.ForeignKey(SalesOrder, on_delete=models.PROTECT, related_name="sales_returns")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="sales_returns")
    source = models.CharField(max_length=24, choices=Source.choices, default=Source.CUSTOMER)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REQUESTED)
    resolution = models.CharField(max_length=20, choices=Resolution.choices, default=Resolution.REFUND)
    reason_category = models.CharField(max_length=32, choices=Reason.choices, default=Reason.OTHER)
    source_reference = models.CharField(max_length=160, blank=True)
    refund_reference = models.CharField(max_length=160, blank=True)
    requested_date = models.DateField(default=timezone.localdate)
    received_date = models.DateField(null=True, blank=True)
    completed_date = models.DateField(null=True, blank=True)
    customer_note = models.TextField(blank=True)
    internal_note = models.TextField(blank=True)
    actor = models.CharField(max_length=160, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-requested_date", "-id")
        indexes = [
            models.Index(fields=("status", "requested_date"), name="ret_status_date_idx"),
            models.Index(fields=("order", "requested_date"), name="ret_order_date_idx"),
            models.Index(fields=("source", "requested_date"), name="ret_source_date_idx"),
        ]

    @property
    def item_count(self):
        return sum(item.quantity for item in self.items.all())

    @property
    def credit_total(self):
        return self.items.aggregate(total=Sum("refund_amount"))["total"] or ZERO

    @property
    def refunded_total(self):
        return self.refunds.aggregate(total=Sum("amount"))["total"] or ZERO

    @property
    def restocked_total(self):
        return self.items.aggregate(total=Sum("restocked_quantity"))["total"] or 0

    @property
    def customer_name(self):
        return self.order.customer_name

    @property
    def is_terminal(self):
        return self.status in {self.Status.COMPLETED, self.Status.REJECTED, self.Status.CANCELLED}

    def __str__(self):
        return self.return_no


class SalesReturnItem(models.Model):
    class Condition(models.TextChoices):
        SEALED = "sealed", "Sealed / Unopened"
        GOOD = "good", "Opened but Good"
        USED = "used", "Used"
        DEFECTIVE = "defective", "Defective"
        DAMAGED = "damaged", "Damaged"

    class Disposition(models.TextChoices):
        RESTOCK = "restock", "Return to Sellable Stock"
        DAMAGED = "damaged", "Damaged / Quarantine"
        WARRANTY = "warranty", "Warranty / Service"
        SCRAP = "scrap", "Scrap"
        NO_STOCK = "no_stock", "Do Not Add to Stock"

    sales_return = models.ForeignKey(SalesReturn, on_delete=models.CASCADE, related_name="items")
    order_item = models.ForeignKey(SalesOrderItem, on_delete=models.PROTECT, related_name="return_items")
    variant = models.ForeignKey("catalog.ProductVariant", on_delete=models.PROTECT, related_name="sales_return_items")
    product_snapshot = models.CharField(max_length=255)
    sku_snapshot = models.CharField(max_length=64)
    quantity = models.PositiveIntegerField()
    condition = models.CharField(max_length=20, choices=Condition.choices, default=Condition.GOOD)
    disposition = models.CharField(max_length=20, choices=Disposition.choices, default=Disposition.RESTOCK)
    refund_amount = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    serialized_unit = models.ForeignKey(
        SerializedUnit,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="sales_return_items",
    )
    restocked_quantity = models.PositiveIntegerField(default=0)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ("id",)
        indexes = [
            models.Index(fields=("order_item",), name="ret_item_order_item_idx"),
            models.Index(fields=("variant",), name="ret_item_variant_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="ret_item_quantity_positive"),
            models.CheckConstraint(condition=models.Q(refund_amount__gte=0), name="ret_item_refund_nonnegative"),
            models.CheckConstraint(condition=models.Q(restocked_quantity__gte=0), name="ret_item_restock_nonnegative"),
        ]

    def clean(self):
        if self.order_item_id and self.sales_return_id:
            if self.order_item.order_id != self.sales_return.order_id:
                raise ValidationError({"order_item": "Return item must belong to the selected Sales Order."})
        if self.variant_id and self.order_item_id and self.variant_id != self.order_item.variant_id:
            raise ValidationError({"variant": "Return item variant must match the Sales Order item."})
        if self.serialized_unit_id:
            if self.quantity != 1:
                raise ValidationError({"quantity": "A serialized return row must contain exactly one unit."})
            if self.variant_id and self.serialized_unit.variant_id != self.variant_id:
                raise ValidationError({"serialized_unit": "Selected Serial/IMEI does not match this SKU."})
        if self.restocked_quantity > self.quantity:
            raise ValidationError({"restocked_quantity": "Restocked quantity cannot exceed return quantity."})

    def __str__(self):
        return f"{self.sales_return.return_no} / {self.sku_snapshot} x {self.quantity}"


class SalesReturnRefund(models.Model):
    sales_return = models.ForeignKey(SalesReturn, on_delete=models.PROTECT, related_name="refunds")
    source_payment = models.ForeignKey(
        PaymentTransaction,
        on_delete=models.PROTECT,
        related_name="return_refund_sources",
    )
    refund_transaction = models.OneToOneField(
        PaymentTransaction,
        on_delete=models.PROTECT,
        related_name="sales_return_refund",
    )
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("id",)
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="ret_refund_amount_positive"),
        ]

    def clean(self):
        if self.source_payment_id and self.sales_return_id:
            if self.source_payment.sales_order_id != self.sales_return.order_id:
                raise ValidationError({"source_payment": "Refund source payment must belong to the return order."})
        if self.refund_transaction_id and self.refund_transaction.kind != PaymentTransaction.Kind.REFUND:
            raise ValidationError({"refund_transaction": "Linked transaction must be a customer refund."})

    def __str__(self):
        return f"{self.sales_return.return_no} / {self.refund_transaction.transaction_no}"


class SalesReturnEvent(models.Model):
    class Event(models.TextChoices):
        CREATED = "created", "Created"
        STATUS = "status", "Status Changed"
        INVENTORY = "inventory", "Inventory Processed"
        CREDIT = "credit", "Return Credit Applied"
        REFUND = "refund", "Cash Refund Posted"
        NOTE = "note", "Note"

    sales_return = models.ForeignKey(SalesReturn, on_delete=models.CASCADE, related_name="events")
    event = models.CharField(max_length=20, choices=Event.choices)
    previous_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20, blank=True)
    note = models.TextField(blank=True)
    actor = models.CharField(max_length=160, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [models.Index(fields=("sales_return", "created_at"), name="ret_event_return_idx")]

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            raise ValidationError("Sales return event history is immutable and cannot be edited.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Sales return event history is immutable and cannot be deleted.")

    def __str__(self):
        return f"{self.sales_return.return_no}: {self.get_event_display()}"
