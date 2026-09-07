from decimal import Decimal
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


ZERO = Decimal("0.00")


def make_payment_number():
    stamp = timezone.localtime().strftime("%y%m%d")
    return f"PMT-{stamp}-{uuid4().hex[:7].upper()}"


class PaymentMethodConfig(models.Model):
    class Method(models.TextChoices):
        CASH = "cash", "Cash"
        BANK = "bank", "Bank Transfer"
        CARD = "card", "Card"
        BKASH = "bkash", "bKash"
        NAGAD = "nagad", "Nagad"
        OTHER = "other", "Other"

    method = models.CharField(max_length=20, choices=Method.choices, unique=True)
    display_name = models.CharField(max_length=80)
    provider_code = models.CharField(max_length=80, blank=True)
    merchant_label = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)
    allow_dashboard = models.BooleanField(default=True)
    allow_pos = models.BooleanField(default=True)
    allow_storefront = models.BooleanField(default=False)
    is_test_mode = models.BooleanField(default=True)
    instructions = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("id",)

    def __str__(self):
        return self.display_name


class PaymentTransaction(models.Model):
    class Kind(models.TextChoices):
        SALE_PAYMENT = "sale_payment", "Sale Payment"
        SUPPLIER_PAYMENT = "supplier_payment", "Supplier Payment"
        REFUND = "refund", "Customer Refund"
        REVERSAL = "reversal", "Payment Reversal"

    class Direction(models.TextChoices):
        IN = "in", "Money In"
        OUT = "out", "Money Out"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        REVERSED = "reversed", "Reversed"

    class ReconciliationStatus(models.TextChoices):
        UNRECONCILED = "unreconciled", "Unreconciled"
        RECONCILED = "reconciled", "Reconciled"
        DISPUTED = "disputed", "Disputed"

    transaction_no = models.CharField(max_length=64, unique=True, default=make_payment_number)
    sales_order = models.ForeignKey(
        "sales.SalesOrder",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payment_transactions",
    )
    purchase_payment = models.OneToOneField(
        "purchasing.PurchasePayment",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="ledger_transaction",
    )
    parent_transaction = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="child_transactions",
    )
    kind = models.CharField(max_length=24, choices=Kind.choices)
    direction = models.CharField(max_length=8, choices=Direction.choices)
    method = models.CharField(max_length=20, choices=PaymentMethodConfig.Method.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.COMPLETED)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    provider_reference = models.CharField(max_length=160, blank=True)
    external_id = models.CharField(max_length=160, blank=True)
    transaction_date = models.DateField(default=timezone.localdate)
    note = models.TextField(blank=True)
    reconciliation_status = models.CharField(
        max_length=20,
        choices=ReconciliationStatus.choices,
        default=ReconciliationStatus.UNRECONCILED,
    )
    reconciled_at = models.DateTimeField(null=True, blank=True)
    reconciled_by = models.CharField(max_length=160, blank=True)
    created_by = models.CharField(max_length=160, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-transaction_date", "-id")
        indexes = [
            models.Index(fields=("status", "transaction_date"), name="payment_status_date_idx"),
            models.Index(fields=("method", "transaction_date"), name="payment_method_date_idx"),
            models.Index(fields=("reconciliation_status", "transaction_date"), name="payment_recon_date_idx"),
            models.Index(fields=("sales_order", "transaction_date"), name="payment_sales_date_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="payment_amount_positive"),
        ]

    def clean(self):
        if not self.sales_order_id and not self.purchase_payment_id:
            raise ValidationError("A payment transaction must be linked to a sales order or supplier payment.")
        if self.sales_order_id and self.purchase_payment_id:
            raise ValidationError("A payment transaction cannot be linked to sales and purchasing at the same time.")
        if self.kind in {self.Kind.SALE_PAYMENT, self.Kind.REFUND, self.Kind.REVERSAL} and not self.sales_order_id:
            raise ValidationError("Sales payments/refunds/reversals require a sales order.")
        if self.kind == self.Kind.SUPPLIER_PAYMENT and not self.purchase_payment_id:
            raise ValidationError("Supplier payment transactions require a PurchasePayment.")
        if self.kind == self.Kind.SALE_PAYMENT and self.direction != self.Direction.IN:
            raise ValidationError("Sale payments must be money-in transactions.")
        if self.kind in {self.Kind.SUPPLIER_PAYMENT, self.Kind.REFUND, self.Kind.REVERSAL} and self.direction != self.Direction.OUT:
            raise ValidationError("Supplier payments, refunds and reversals must be money-out transactions.")
        if self.parent_transaction_id and self.parent_transaction_id == self.pk:
            raise ValidationError("A payment transaction cannot reference itself as parent.")
        if self.reconciliation_status == self.ReconciliationStatus.RECONCILED and not self.reconciled_at:
            raise ValidationError("A reconciled transaction requires a reconciliation timestamp.")

    @property
    def signed_amount(self):
        return self.amount if self.direction == self.Direction.IN else -self.amount

    @property
    def counterparty(self):
        if self.sales_order_id:
            return self.sales_order.customer_name
        if self.purchase_payment_id:
            return self.purchase_payment.supplier.name
        return "—"

    @property
    def source_reference(self):
        if self.sales_order_id:
            return self.sales_order.order_number
        if self.purchase_payment_id:
            return self.purchase_payment.purchase.po_number
        return ""

    def __str__(self):
        return self.transaction_no


class PaymentEvent(models.Model):
    class Event(models.TextChoices):
        CREATED = "created", "Created"
        STATUS = "status", "Status Changed"
        REFUND = "refund", "Refund Created"
        REVERSAL = "reversal", "Reversal Created"
        RECONCILIATION = "reconciliation", "Reconciliation Updated"

    transaction = models.ForeignKey(PaymentTransaction, on_delete=models.CASCADE, related_name="events")
    event = models.CharField(max_length=24, choices=Event.choices)
    previous_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20, blank=True)
    note = models.TextField(blank=True)
    actor = models.CharField(max_length=160, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [models.Index(fields=("transaction", "created_at"), name="payment_event_txn_idx")]

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            raise ValidationError("Payment event history is immutable and cannot be edited.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Payment event history is immutable and cannot be deleted.")

    def __str__(self):
        return f"{self.transaction.transaction_no}: {self.get_event_display()}"
