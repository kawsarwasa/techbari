from decimal import Decimal
from uuid import uuid4

from django.db import models
from django.db.models import Sum
from django.utils import timezone


def make_customer_number():
    stamp = timezone.localtime().strftime("%y%m%d")
    return f"CUST-{stamp}-{uuid4().hex[:6].upper()}"


class CustomerGroup(models.Model):
    name = models.CharField(max_length=120, unique=True)
    code = models.CharField(max_length=40, unique=True)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name


class Customer(models.Model):
    class Source(models.TextChoices):
        ONLINE = "online", "Online Store"
        FACEBOOK = "facebook", "Facebook"
        POS = "pos", "POS / Walk-in"
        REFERRAL = "referral", "Referral"
        PHONE = "phone", "Phone Order"
        OTHER = "other", "Other"

    customer_no = models.CharField(max_length=40, unique=True, default=make_customer_number, editable=False)
    name = models.CharField(max_length=180)
    phone = models.CharField(max_length=40, unique=True)
    email = models.EmailField(blank=True)
    group = models.ForeignKey(
        CustomerGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customers",
    )
    source = models.CharField(max_length=24, choices=Source.choices, default=Source.ONLINE)
    address = models.TextField(blank=True)
    district = models.CharField(max_length=120, blank=True)
    city = models.CharField(max_length=120, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    credit_limit = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    opening_due = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name", "customer_no")
        indexes = [
            models.Index(fields=("phone",), name="crm_customer_phone_idx"),
            models.Index(fields=("is_active", "created_at"), name="crm_customer_active_idx"),
            models.Index(fields=("source", "created_at"), name="crm_customer_source_idx"),
        ]

    def __str__(self):
        return f"{self.name} ({self.customer_no})"

    @property
    def initials(self):
        parts = [part for part in self.name.split() if part]
        return "".join(part[0].upper() for part in parts[:2]) or "C"

    @property
    def display_address(self):
        parts = [self.address, self.city, self.district, self.postal_code]
        return ", ".join(str(part).strip() for part in parts if str(part).strip())

    def _active_orders(self):
        manager = getattr(self, "sales_orders", None)
        if manager is None:
            return None
        return manager.exclude(status__in=["draft", "cancelled"])

    @property
    def order_count(self):
        orders = self._active_orders()
        return orders.count() if orders is not None else 0

    @property
    def completed_order_count(self):
        manager = getattr(self, "sales_orders", None)
        return manager.filter(status="completed").count() if manager is not None else 0

    @property
    def total_spent(self):
        manager = getattr(self, "sales_orders", None)
        if manager is None:
            return Decimal("0.00")
        total = manager.filter(status="completed").aggregate(total=Sum("grand_total"))["total"]
        return total or Decimal("0.00")

    @property
    def due_balance(self):
        orders = self._active_orders()
        if orders is None:
            return self.opening_due
        due = sum((order.outstanding_amount for order in orders), Decimal("0.00"))
        return self.opening_due + due

    @property
    def repeat_customer(self):
        return self.completed_order_count >= 2

    @property
    def first_purchase_at(self):
        manager = getattr(self, "sales_orders", None)
        if manager is None:
            return None
        return manager.exclude(status__in=["draft", "cancelled"]).order_by("order_date", "id").values_list("order_date", flat=True).first()

    @property
    def last_purchase_at(self):
        manager = getattr(self, "sales_orders", None)
        if manager is None:
            return None
        return manager.exclude(status__in=["draft", "cancelled"]).order_by("-order_date", "-id").values_list("order_date", flat=True).first()
