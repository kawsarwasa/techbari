from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum

from catalog.models import ProductVariant
from inventory.models import Warehouse


ZERO = Decimal("0.00")


class Supplier(models.Model):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=180)
    contact_person = models.CharField(max_length=160, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    tax_id = models.CharField(max_length=80, blank=True)
    payment_terms_days = models.PositiveIntegerField(default=0)
    credit_limit = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    opening_balance = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name", "code")
        indexes = [models.Index(fields=("is_active", "name"), name="purchase_supplier_active_idx")]

    def __str__(self):
        return f"{self.name} ({self.code})"

    @property
    def total_purchases(self):
        total = ZERO
        for purchase in self.purchase_orders.exclude(status__in=[PurchaseOrder.Status.DRAFT, PurchaseOrder.Status.CANCELLED]):
            total += purchase.grand_total
        return total

    @property
    def total_paid(self):
        return self.purchase_payments.aggregate(total=Sum("amount"))["total"] or ZERO

    @property
    def total_returns(self):
        total = ZERO
        for purchase_return in PurchaseReturn.objects.filter(purchase__supplier=self):
            total += purchase_return.total_amount
        return total

    @property
    def outstanding_balance(self):
        due = self.opening_balance + self.total_purchases - self.total_paid - self.total_returns
        return max(ZERO, due)


class PurchaseOrder(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ORDERED = "ordered", "Ordered"
        PARTIALLY_RECEIVED = "partially_received", "Partially Received"
        RECEIVED = "received", "Received"
        CANCELLED = "cancelled", "Cancelled"

    po_number = models.CharField(max_length=80, unique=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="purchase_orders")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="purchase_orders")
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DRAFT)
    purchase_date = models.DateField()
    expected_date = models.DateField(null=True, blank=True)
    supplier_invoice_no = models.CharField(max_length=100, blank=True)
    invoice_date = models.DateField(null=True, blank=True)
    shipping_cost = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    other_cost = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    discount_amount = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    notes = models.TextField(blank=True)
    actor = models.CharField(max_length=160, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-purchase_date", "-id")
        indexes = [
            models.Index(fields=("status", "purchase_date"), name="purchase_order_status_idx"),
            models.Index(fields=("supplier", "purchase_date"), name="purchase_order_supplier_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(shipping_cost__gte=0), name="purchase_shipping_nonnegative"),
            models.CheckConstraint(condition=models.Q(other_cost__gte=0), name="purchase_other_nonnegative"),
            models.CheckConstraint(condition=models.Q(discount_amount__gte=0), name="purchase_discount_nonnegative"),
        ]

    def clean(self):
        if self.expected_date and self.purchase_date and self.expected_date < self.purchase_date:
            raise ValidationError({"expected_date": "Expected date cannot be before purchase date."})
        if self.invoice_date and self.purchase_date and self.invoice_date < self.purchase_date:
            raise ValidationError({"invoice_date": "Invoice date cannot be before purchase date."})

    def __str__(self):
        return self.po_number

    @property
    def subtotal(self):
        return sum((item.line_total for item in self.items.all()), ZERO)

    @property
    def grand_total(self):
        total = self.subtotal + self.shipping_cost + self.other_cost - self.discount_amount
        return max(ZERO, total)

    @property
    def paid_amount(self):
        return self.payments.aggregate(total=Sum("amount"))["total"] or ZERO

    @property
    def returned_amount(self):
        return sum((row.total_amount for row in self.returns.all()), ZERO)

    @property
    def outstanding_amount(self):
        return max(ZERO, self.grand_total - self.paid_amount - self.returned_amount)

    @property
    def payment_status(self):
        if self.outstanding_amount <= ZERO:
            return "Paid"
        if self.paid_amount > ZERO:
            return "Partial"
        return "Unpaid"

    @property
    def ordered_quantity(self):
        return sum(item.ordered_quantity for item in self.items.all())

    @property
    def received_quantity(self):
        return sum(item.received_quantity for item in self.items.all())

    @property
    def remaining_quantity(self):
        return max(0, self.ordered_quantity - self.received_quantity)


class PurchaseOrderItem(models.Model):
    purchase = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="items")
    variant = models.ForeignKey(ProductVariant, on_delete=models.PROTECT, related_name="purchase_items")
    ordered_quantity = models.PositiveIntegerField()
    received_quantity = models.PositiveIntegerField(default=0)
    returned_quantity = models.PositiveIntegerField(default=0)
    unit_cost = models.DecimalField(max_digits=14, decimal_places=2)

    def __init__(self, *args, **kwargs):
        # Backward compatibility for older internal callers/tests while the
        # database no longer stores line-level discounts.
        kwargs.pop("discount_amount", None)
        super().__init__(*args, **kwargs)

    class Meta:
        ordering = ("id",)
        constraints = [
            models.UniqueConstraint(fields=("purchase", "variant"), name="uniq_purchase_variant"),
            models.CheckConstraint(condition=models.Q(ordered_quantity__gt=0), name="purchase_ordered_positive"),
            models.CheckConstraint(condition=models.Q(received_quantity__gte=0), name="purchase_received_nonnegative"),
            models.CheckConstraint(condition=models.Q(returned_quantity__gte=0), name="purchase_returned_nonnegative"),
            models.CheckConstraint(condition=models.Q(unit_cost__gte=0), name="purchase_unit_cost_nonnegative"),
            models.CheckConstraint(condition=models.Q(received_quantity__lte=models.F("ordered_quantity")), name="purchase_received_not_over_ordered"),
            models.CheckConstraint(condition=models.Q(returned_quantity__lte=models.F("received_quantity")), name="purchase_returned_not_over_received"),
        ]

    def clean(self):
        if self.received_quantity > self.ordered_quantity:
            raise ValidationError("Received quantity cannot exceed ordered quantity.")
        if self.returned_quantity > self.received_quantity:
            raise ValidationError("Returned quantity cannot exceed received quantity.")

    @property
    def discount_amount(self):
        # Compatibility read for legacy templates/callers. Line discounts are
        # no longer persisted; Order Discount on PurchaseOrder is authoritative.
        return ZERO

    @property
    def line_total(self):
        return Decimal(self.ordered_quantity) * self.unit_cost

    @property
    def remaining_to_receive(self):
        return max(0, self.ordered_quantity - self.received_quantity)

    @property
    def remaining_to_return(self):
        return max(0, self.received_quantity - self.returned_quantity)

    def __str__(self):
        return f"{self.purchase.po_number} / {self.variant.sku} x {self.ordered_quantity}"


class PurchaseReceipt(models.Model):
    receipt_no = models.CharField(max_length=80, unique=True)
    purchase = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, related_name="receipts")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="purchase_receipts")
    received_date = models.DateField()
    supplier_challan_no = models.CharField(max_length=100, blank=True)
    note = models.TextField(blank=True)
    actor = models.CharField(max_length=160, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-received_date", "-id")

    def clean(self):
        if self.purchase_id and self.warehouse_id and self.purchase.warehouse_id != self.warehouse_id:
            raise ValidationError("Receipt warehouse must match the purchase order warehouse.")

    def __str__(self):
        return self.receipt_no


class PurchaseReceiptItem(models.Model):
    receipt = models.ForeignKey(PurchaseReceipt, on_delete=models.CASCADE, related_name="items")
    purchase_item = models.ForeignKey(PurchaseOrderItem, on_delete=models.PROTECT, related_name="receipt_items")
    quantity = models.PositiveIntegerField()
    serial_data = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ("id",)
        constraints = [
            models.UniqueConstraint(fields=("receipt", "purchase_item"), name="uniq_receipt_purchase_item"),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="purchase_receipt_qty_positive"),
        ]

    def __str__(self):
        return f"{self.receipt.receipt_no} / {self.purchase_item.variant.sku} x {self.quantity}"


class PurchasePayment(models.Model):
    class Method(models.TextChoices):
        CASH = "cash", "Cash"
        BANK = "bank", "Bank Transfer"
        BKASH = "bkash", "bKash"
        NAGAD = "nagad", "Nagad"
        CARD = "card", "Card"
        OTHER = "other", "Other"

    payment_no = models.CharField(max_length=80, unique=True)
    purchase = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, related_name="payments")
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="purchase_payments")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    method = models.CharField(max_length=20, choices=Method.choices, default=Method.CASH)
    reference = models.CharField(max_length=120, blank=True)
    payment_date = models.DateField()
    note = models.TextField(blank=True)
    actor = models.CharField(max_length=160, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-payment_date", "-id")
        constraints = [models.CheckConstraint(condition=models.Q(amount__gt=0), name="purchase_payment_positive")]

    def clean(self):
        if self.purchase_id and self.supplier_id and self.purchase.supplier_id != self.supplier_id:
            raise ValidationError("Payment supplier must match the purchase order supplier.")

    def __str__(self):
        return self.payment_no


class PurchaseReturn(models.Model):
    class Status(models.TextChoices):
        POSTED = "posted", "Posted"

    return_no = models.CharField(max_length=80, unique=True)
    purchase = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, related_name="returns")
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="purchase_returns")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="purchase_returns")
    return_date = models.DateField()
    reason = models.CharField(max_length=255)
    note = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.POSTED)
    actor = models.CharField(max_length=160, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-return_date", "-id")

    def clean(self):
        if self.purchase_id:
            if self.supplier_id and self.purchase.supplier_id != self.supplier_id:
                raise ValidationError("Return supplier must match the purchase order supplier.")
            if self.warehouse_id and self.purchase.warehouse_id != self.warehouse_id:
                raise ValidationError("Return warehouse must match the purchase order warehouse.")

    @property
    def total_amount(self):
        return sum((item.line_total for item in self.items.all()), ZERO)

    def __str__(self):
        return self.return_no


class PurchaseReturnItem(models.Model):
    purchase_return = models.ForeignKey(PurchaseReturn, on_delete=models.CASCADE, related_name="items")
    purchase_item = models.ForeignKey(PurchaseOrderItem, on_delete=models.PROTECT, related_name="return_items")
    quantity = models.PositiveIntegerField()
    unit_cost = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        ordering = ("id",)
        constraints = [
            models.UniqueConstraint(fields=("purchase_return", "purchase_item"), name="uniq_purchase_return_item"),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="purchase_return_qty_positive"),
            models.CheckConstraint(condition=models.Q(unit_cost__gte=0), name="purchase_return_cost_nonnegative"),
        ]

    @property
    def line_total(self):
        return Decimal(self.quantity) * self.unit_cost

    def __str__(self):
        return f"{self.purchase_return.return_no} / {self.purchase_item.variant.sku} x {self.quantity}"


class PurchaseReturnSerialUnit(models.Model):
    return_item = models.ForeignKey(PurchaseReturnItem, on_delete=models.CASCADE, related_name="serial_units")
    unit = models.ForeignKey("serial_tracking.SerializedUnit", on_delete=models.PROTECT, related_name="purchase_return_links")

    class Meta:
        ordering = ("id",)
        constraints = [models.UniqueConstraint(fields=("return_item", "unit"), name="uniq_purchase_return_serial")]

    def __str__(self):
        return f"{self.return_item.purchase_return.return_no} / {self.unit.display_identifier}"
