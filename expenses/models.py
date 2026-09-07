from decimal import Decimal
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


ZERO = Decimal("0.00")


def make_expense_number():
    stamp = timezone.localtime().strftime("%y%m%d")
    return f"EXP-{stamp}-{uuid4().hex[:7].upper()}"


class ExpenseCategory(models.Model):
    code = models.CharField(max_length=24, unique=True)
    name = models.CharField(max_length=120, unique=True)
    account = models.ForeignKey(
        "accounting.Account",
        on_delete=models.PROTECT,
        related_name="expense_categories",
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("sort_order", "name")
        indexes = [models.Index(fields=("is_active", "sort_order"), name="expense_cat_active_idx")]

    def clean(self):
        self.code = str(self.code or "").strip().upper()
        self.name = str(self.name or "").strip()
        if not self.code:
            raise ValidationError({"code": "Category code is required."})
        if self.account_id and self.account.account_type != self.account.Type.EXPENSE:
            raise ValidationError({"account": "Expense categories must map to an Expense-type account."})

    def __str__(self):
        return f"{self.code} — {self.name}"


class Expense(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING = "pending", "Pending Approval"
        APPROVED = "approved", "Approved"
        PAID = "paid", "Paid"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"
        VOIDED = "voided", "Voided"

    class Method(models.TextChoices):
        CASH = "cash", "Cash"
        BANK = "bank", "Bank Transfer"
        CARD = "card", "Card"
        BKASH = "bkash", "bKash"
        NAGAD = "nagad", "Nagad"
        OTHER = "other", "Other"

    expense_no = models.CharField(max_length=64, unique=True, default=make_expense_number)
    expense_date = models.DateField(default=timezone.localdate)
    category = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT, related_name="expenses")
    payee = models.CharField(max_length=160, blank=True)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    preferred_payment_method = models.CharField(max_length=20, choices=Method.choices, blank=True)
    payment_method = models.CharField(max_length=20, choices=Method.choices, blank=True)
    payment_account = models.ForeignKey(
        "accounting.Account",
        on_delete=models.PROTECT,
        related_name="expense_payments",
        null=True,
        blank=True,
    )
    payment_reference = models.CharField(max_length=160, blank=True)
    payment_date = models.DateField(null=True, blank=True)
    receipt_no = models.CharField(max_length=120, blank=True)
    attachment = models.FileField(upload_to="expenses/attachments/%Y/%m/", blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    requested_by = models.CharField(max_length=160, blank=True)
    approved_by = models.CharField(max_length=160, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    paid_by = models.CharField(max_length=160, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_by = models.CharField(max_length=160, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-expense_date", "-id")
        indexes = [
            models.Index(fields=("status", "expense_date"), name="expense_status_date_idx"),
            models.Index(fields=("category", "expense_date"), name="expense_cat_date_idx"),
            models.Index(fields=("payment_method", "expense_date"), name="expense_method_date_idx"),
            models.Index(fields=("payment_account", "payment_date"), name="expense_payacct_date_idx"),
        ]
        constraints = [models.CheckConstraint(condition=models.Q(amount__gt=0), name="expense_amount_positive")]

    def clean(self):
        if (self.amount or ZERO) <= ZERO:
            raise ValidationError({"amount": "Expense amount must be greater than zero."})
        if self.category_id and not self.category.is_active and not self.pk:
            raise ValidationError({"category": "Select an active expense category."})
        if self.payment_account_id:
            if self.payment_account.account_type != "asset":
                raise ValidationError({"payment_account": "Expense payments must use an Asset payment account."})
            if not self.payment_account.is_active:
                raise ValidationError({"payment_account": "Inactive payment accounts cannot be used."})
            if not self.payment_account.allow_manual_entries:
                raise ValidationError({"payment_account": "Select a cash/bank/payment Asset account, not a controlled operational asset."})
        if self.status == self.Status.PAID:
            if not self.payment_method:
                raise ValidationError({"payment_method": "Paid expenses require a payment method."})
            if not self.payment_account_id:
                raise ValidationError({"payment_account": "Paid expenses require a payment account."})
            if not self.payment_date:
                raise ValidationError({"payment_date": "Paid expenses require a payment date."})
            if self.payment_method != self.Method.CASH and not self.payment_reference.strip():
                raise ValidationError({"payment_reference": "Non-cash expense payments require a reference."})
            if not self.paid_at:
                raise ValidationError("Paid expenses require a paid timestamp.")

    @property
    def accounting_source_key(self):
        return f"expense_payment:{self.pk}" if self.pk else ""

    def __str__(self):
        return self.expense_no


class ExpenseEvent(models.Model):
    class Event(models.TextChoices):
        CREATED = "created", "Created"
        UPDATED = "updated", "Updated"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        PAID = "paid", "Paid"
        CANCELLED = "cancelled", "Cancelled"
        VOIDED = "voided", "Voided"

    expense = models.ForeignKey(Expense, on_delete=models.CASCADE, related_name="events")
    event = models.CharField(max_length=20, choices=Event.choices)
    previous_status = models.CharField(max_length=16, blank=True)
    new_status = models.CharField(max_length=16, blank=True)
    note = models.TextField(blank=True)
    actor = models.CharField(max_length=160, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [models.Index(fields=("expense", "created_at"), name="expense_event_exp_idx")]

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            raise ValidationError("Expense audit events are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Expense audit events cannot be deleted.")

    def __str__(self):
        return f"{self.expense.expense_no}: {self.get_event_display()}"
