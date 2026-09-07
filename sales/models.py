from decimal import Decimal
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from catalog.models import ProductVariant
from customers.models import Customer
from inventory.models import Warehouse


def make_order_number():
    stamp = timezone.localtime().strftime("%y%m%d")
    return f"TB-{stamp}-{uuid4().hex[:6].upper()}"


class SalesOrder(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed / Sold"
        CANCELLED = "cancelled", "Cancelled"

    class PaymentStatus(models.TextChoices):
        UNPAID = "unpaid", "Unpaid"
        PARTIAL = "partial", "Partial"
        PAID = "paid", "Paid"
        REFUNDED = "refunded", "Refunded"

    class Channel(models.TextChoices):
        ONLINE = "online", "Online Store"
        MANUAL = "manual", "Manual Order"
        POS = "pos", "POS"

    order_number = models.CharField(max_length=50, unique=True, default=make_order_number)
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="sales_orders",
    )
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="sales_orders")
    channel = models.CharField(max_length=20, choices=Channel.choices, default=Channel.ONLINE)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    payment_status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.UNPAID)
    order_date = models.DateField(default=timezone.localdate)

    shipping_name = models.CharField(max_length=180, blank=True)
    shipping_phone = models.CharField(max_length=40, blank=True)
    shipping_email = models.EmailField(blank=True)
    shipping_address = models.TextField(blank=True)
    shipping_city = models.CharField(max_length=120, blank=True)
    shipping_district = models.CharField(max_length=120, blank=True)
    shipping_postal_code = models.CharField(max_length=20, blank=True)

    subtotal = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    discount_amount = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    shipping_charge = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    grand_total = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    amount_paid = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    notes = models.TextField(blank=True)
    created_by = models.CharField(max_length=160, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-order_date", "-id")
        indexes = [
            models.Index(fields=("status", "order_date"), name="sales_order_status_date_idx"),
            models.Index(fields=("payment_status", "order_date"), name="sales_order_pay_date_idx"),
            models.Index(fields=("customer", "order_date"), name="sales_order_customer_idx"),
            models.Index(fields=("warehouse", "status"), name="sales_order_wh_status_idx"),
        ]

    def __str__(self):
        return self.order_number

    @property
    def outstanding_amount(self):
        value = (self.grand_total or Decimal("0.00")) - (self.amount_paid or Decimal("0.00"))
        return max(value, Decimal("0.00"))

    @property
    def customer_name(self):
        return self.customer.name if self.customer_id else (self.shipping_name or "Guest Customer")

    @property
    def customer_phone(self):
        return self.customer.phone if self.customer_id else self.shipping_phone

    @property
    def item_count(self):
        return sum(item.quantity for item in self.items.all())

    @property
    def shipping_summary(self):
        parts = [self.shipping_address, self.shipping_city, self.shipping_district, self.shipping_postal_code]
        return ", ".join(str(part).strip() for part in parts if str(part).strip())


class SalesOrderItem(models.Model):
    order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, related_name="items")
    variant = models.ForeignKey(ProductVariant, on_delete=models.PROTECT, related_name="sales_order_items")
    product_snapshot = models.CharField(max_length=255)
    variant_snapshot = models.CharField(max_length=120)
    sku_snapshot = models.CharField(max_length=64)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=18, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    reserved_quantity = models.PositiveIntegerField(default=0)
    issued_quantity = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("id",)
        constraints = [
            models.UniqueConstraint(fields=("order", "variant"), name="uniq_sales_order_variant"),
            models.CheckConstraint(check=models.Q(quantity__gt=0), name="sales_item_quantity_positive"),
            models.CheckConstraint(check=models.Q(reserved_quantity__gte=0), name="sales_item_reserved_nonnegative"),
            models.CheckConstraint(check=models.Q(issued_quantity__gte=0), name="sales_item_issued_nonnegative"),
        ]

    @property
    def gross_total(self):
        return self.unit_price * self.quantity

    @property
    def line_total(self):
        return max(self.gross_total - self.discount_amount, Decimal("0.00"))

    def __str__(self):
        return f"{self.order.order_number} / {self.sku_snapshot} x {self.quantity}"


class SalesOrderHistory(models.Model):
    class Event(models.TextChoices):
        CREATED = "created", "Created"
        UPDATED = "updated", "Updated"
        STATUS = "status", "Status Changed"
        PAYMENT = "payment", "Payment Updated"
        STOCK = "stock", "Stock Updated"

    order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, related_name="history")
    event = models.CharField(max_length=20, choices=Event.choices)
    previous_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20, blank=True)
    note = models.TextField(blank=True)
    actor = models.CharField(max_length=160, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [models.Index(fields=("order", "created_at"), name="sales_history_order_idx")]

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            raise ValidationError("Sales order history is immutable and cannot be edited.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Sales order history is immutable and cannot be deleted.")

    def __str__(self):
        return f"{self.order.order_number}: {self.get_event_display()}"
