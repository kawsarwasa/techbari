from decimal import Decimal
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
from django.utils import timezone


ZERO = Decimal("0.00")


def make_journal_number():
    stamp = timezone.localtime().strftime("%y%m%d")
    return f"JE-{stamp}-{uuid4().hex[:7].upper()}"


class Account(models.Model):
    class Type(models.TextChoices):
        ASSET = "asset", "Asset"
        LIABILITY = "liability", "Liability"
        EQUITY = "equity", "Equity"
        REVENUE = "revenue", "Revenue"
        EXPENSE = "expense", "Expense"

    class NormalBalance(models.TextChoices):
        DEBIT = "debit", "Debit"
        CREDIT = "credit", "Credit"

    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=160)
    account_type = models.CharField(max_length=16, choices=Type.choices)
    normal_balance = models.CharField(max_length=8, choices=NormalBalance.choices)
    description = models.TextField(blank=True)
    is_system = models.BooleanField(default=False)
    allow_manual_entries = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("code",)
        indexes = [models.Index(fields=("account_type", "is_active"), name="acct_type_active_idx")]

    def clean(self):
        self.code = str(self.code or "").strip().upper()
        if not self.code:
            raise ValidationError({"code": "Account code is required."})

    @property
    def debit_total(self):
        return self.lines.filter(entry__status__in=[JournalEntry.Status.POSTED, JournalEntry.Status.REVERSED]).aggregate(total=Sum("debit"))["total"] or ZERO

    @property
    def credit_total(self):
        return self.lines.filter(entry__status__in=[JournalEntry.Status.POSTED, JournalEntry.Status.REVERSED]).aggregate(total=Sum("credit"))["total"] or ZERO

    @property
    def balance(self):
        if self.normal_balance == self.NormalBalance.DEBIT:
            return self.debit_total - self.credit_total
        return self.credit_total - self.debit_total

    def __str__(self):
        return f"{self.code} — {self.name}"


class AccountingPeriod(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"

    name = models.CharField(max_length=120, unique=True)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.CharField(max_length=160, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-start_date", "-id")
        indexes = [models.Index(fields=("status", "start_date", "end_date"), name="acct_period_status_idx")]

    def clean(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "Period end date cannot be before its start date."})
        if self.start_date and self.end_date:
            overlap = AccountingPeriod.objects.filter(start_date__lte=self.end_date, end_date__gte=self.start_date)
            if self.pk:
                overlap = overlap.exclude(pk=self.pk)
            if overlap.exists():
                raise ValidationError("Accounting periods cannot overlap.")
        if self.status == self.Status.CLOSED and not self.closed_at:
            raise ValidationError("A closed accounting period requires a close timestamp.")

    def __str__(self):
        return self.name


class JournalEntry(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        POSTED = "posted", "Posted"
        REVERSED = "reversed", "Reversed"

    class SourceType(models.TextChoices):
        SALE = "sale", "Sales Order"
        SALE_RETURN = "sale_return", "Sales Return"
        SALE_PAYMENT = "sale_payment", "Sale Payment"
        SUPPLIER_PAYMENT = "supplier_payment", "Supplier Payment"
        PURCHASE_RECEIPT = "purchase_receipt", "Purchase Receipt"
        PURCHASE_OVERHEAD = "purchase_overhead", "Purchase Overhead"
        PURCHASE_RETURN = "purchase_return", "Purchase Return"
        COURIER_FEE = "courier_fee", "Courier / Collection Fee"
        EXPENSE = "expense", "Business Expense"
        OPENING_BALANCE = "opening_balance", "Opening Balance"
        MANUAL = "manual", "Manual Journal"
        REVERSAL = "reversal", "Journal Reversal"

    entry_no = models.CharField(max_length=64, unique=True, default=make_journal_number)
    entry_date = models.DateField(default=timezone.localdate)
    source_type = models.CharField(max_length=24, choices=SourceType.choices, default=SourceType.MANUAL)
    source_key = models.CharField(max_length=190, unique=True, null=True, blank=True)
    source_reference = models.CharField(max_length=160, blank=True)
    description = models.TextField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    reversal_of = models.OneToOneField(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reversal_entry",
    )
    created_by = models.CharField(max_length=160, blank=True)
    posted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-entry_date", "-id")
        indexes = [
            models.Index(fields=("status", "entry_date"), name="acct_journal_status_idx"),
            models.Index(fields=("source_type", "entry_date"), name="acct_journal_source_idx"),
            models.Index(fields=("source_reference",), name="acct_journal_ref_idx"),
        ]

    def clean(self):
        if self.status == self.Status.POSTED and not self.posted_at:
            raise ValidationError("A posted journal requires a posting timestamp.")
        if self.reversal_of_id and self.source_type != self.SourceType.REVERSAL:
            raise ValidationError("Only a reversal journal may link to an original journal.")

    @property
    def total_debit(self):
        return self.lines.aggregate(total=Sum("debit"))["total"] or ZERO

    @property
    def total_credit(self):
        return self.lines.aggregate(total=Sum("credit"))["total"] or ZERO

    @property
    def is_balanced(self):
        return self.total_debit > ZERO and self.total_debit == self.total_credit

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            previous = type(self).objects.filter(pk=self.pk).values("status").first()
            if previous and previous["status"] in {self.Status.POSTED, self.Status.REVERSED}:
                raise ValidationError("Posted journal entries are immutable. Use a reversal journal instead.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status != self.Status.DRAFT:
            raise ValidationError("Posted journal entries cannot be deleted. Use a reversal journal instead.")
        return super().delete(*args, **kwargs)

    def __str__(self):
        return self.entry_no


class JournalLine(models.Model):
    entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name="lines")
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="lines")
    debit = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    credit = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    memo = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ("id",)
        indexes = [models.Index(fields=("account", "id"), name="acct_line_account_idx")]
        constraints = [
            models.CheckConstraint(condition=models.Q(debit__gte=0), name="acct_line_debit_nonnegative"),
            models.CheckConstraint(condition=models.Q(credit__gte=0), name="acct_line_credit_nonnegative"),
            models.CheckConstraint(
                condition=(models.Q(debit__gt=0, credit=0) | models.Q(credit__gt=0, debit=0)),
                name="acct_line_one_side_positive",
            ),
        ]

    def clean(self):
        debit = self.debit or ZERO
        credit = self.credit or ZERO
        if debit < ZERO or credit < ZERO:
            raise ValidationError("Journal amounts cannot be negative.")
        if (debit > ZERO) == (credit > ZERO):
            raise ValidationError("Each journal line must contain either a debit or a credit, not both.")
        if self.account_id and not self.account.is_active:
            raise ValidationError({"account": "Inactive accounts cannot receive new journal entries."})

    def save(self, *args, **kwargs):
        if self.entry_id and self.entry.status != JournalEntry.Status.DRAFT:
            raise ValidationError("Lines of a posted journal entry are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.entry_id and self.entry.status != JournalEntry.Status.DRAFT:
            raise ValidationError("Lines of a posted journal entry cannot be deleted.")
        return super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.entry.entry_no} / {self.account.code}"


class AccountingEvent(models.Model):
    class Event(models.TextChoices):
        CREATED = "created", "Journal Created"
        POSTED = "posted", "Journal Posted"
        REVERSED = "reversed", "Journal Reversed"
        PERIOD = "period", "Period Updated"

    journal = models.ForeignKey(
        JournalEntry,
        on_delete=models.CASCADE,
        related_name="events",
        null=True,
        blank=True,
    )
    event = models.CharField(max_length=20, choices=Event.choices)
    note = models.TextField(blank=True)
    actor = models.CharField(max_length=160, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [models.Index(fields=("journal", "created_at"), name="acct_event_journal_idx")]

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            raise ValidationError("Accounting audit events are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Accounting audit events cannot be deleted.")

    def __str__(self):
        return f"{self.get_event_display()} / {self.journal or 'Accounting'}"
