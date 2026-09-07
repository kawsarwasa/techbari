from decimal import Decimal
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from payments.models import PaymentMethodConfig, PaymentTransaction
from sales.models import SalesOrder


ZERO = Decimal("0.00")


def make_shipment_number():
    stamp = timezone.localtime().strftime("%y%m%d")
    return f"SHP-{stamp}-{uuid4().hex[:7].upper()}"


def make_settlement_number():
    stamp = timezone.localtime().strftime("%y%m%d")
    return f"COD-{stamp}-{uuid4().hex[:7].upper()}"


class CourierProvider(models.Model):
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=160)
    contact_person = models.CharField(max_length=160, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    tracking_url_template = models.CharField(
        max_length=500,
        blank=True,
        help_text="Optional URL containing {tracking_id}.",
    )
    supports_cod = models.BooleanField(default=True)
    default_courier_fee = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    is_active = models.BooleanField(default=True)
    api_enabled = models.BooleanField(default=False)
    is_test_mode = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name", "code")
        indexes = [models.Index(fields=("is_active", "name"), name="ship_courier_active_idx")]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(default_courier_fee__gte=0),
                name="ship_courier_fee_nonnegative",
            )
        ]

    def clean(self):
        self.code = str(self.code or "").strip().upper()
        if self.tracking_url_template and "{tracking_id}" not in self.tracking_url_template:
            raise ValidationError({"tracking_url_template": "Tracking URL must contain {tracking_id}."})

    def build_tracking_url(self, tracking_id):
        tracking_id = str(tracking_id or "").strip()
        if not tracking_id or not self.tracking_url_template:
            return ""
        return self.tracking_url_template.replace("{tracking_id}", tracking_id)

    def __str__(self):
        return f"{self.name} ({self.code})"


class Shipment(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        READY = "ready", "Ready for Handover"
        HANDED_OVER = "handed_over", "Handed Over"
        IN_TRANSIT = "in_transit", "In Transit"
        OUT_FOR_DELIVERY = "out_for_delivery", "Out for Delivery"
        DELIVERED = "delivered", "Delivered"
        FAILED = "failed", "Delivery Failed"
        RETURNING = "returning", "Returning to Merchant"
        RETURNED = "returned", "Returned to Merchant"
        CANCELLED = "cancelled", "Cancelled"

    class CODStatus(models.TextChoices):
        NOT_APPLICABLE = "not_applicable", "Not Applicable"
        PENDING = "pending", "Pending Collection"
        COLLECTED = "collected", "Collected"
        PARTIALLY_SETTLED = "partially_settled", "Partially Settled"
        SETTLED = "settled", "Settled"
        DISPUTED = "disputed", "Disputed / Short"

    shipment_no = models.CharField(max_length=64, unique=True, default=make_shipment_number)
    order = models.OneToOneField(
        SalesOrder,
        on_delete=models.PROTECT,
        related_name="shipment",
    )
    courier = models.ForeignKey(
        CourierProvider,
        on_delete=models.PROTECT,
        related_name="shipments",
    )
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DRAFT)
    tracking_id = models.CharField(max_length=160, blank=True)
    courier_reference = models.CharField(max_length=160, blank=True)
    shipment_date = models.DateField(default=timezone.localdate)
    expected_delivery_date = models.DateField(null=True, blank=True)
    parcel_count = models.PositiveIntegerField(default=1)
    weight_kg = models.DecimalField(max_digits=8, decimal_places=2, default=ZERO)
    courier_fee = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    cod_expected = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    cod_collected = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    cod_settled = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    cod_status = models.CharField(
        max_length=24,
        choices=CODStatus.choices,
        default=CODStatus.NOT_APPLICABLE,
    )
    last_location = models.CharField(max_length=180, blank=True)
    failure_reason = models.CharField(max_length=255, blank=True)
    handed_over_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    returned_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    actor = models.CharField(max_length=160, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-shipment_date", "-id")
        indexes = [
            models.Index(fields=("status", "shipment_date"), name="ship_status_date_idx"),
            models.Index(fields=("courier", "status"), name="ship_courier_status_idx"),
            models.Index(fields=("tracking_id",), name="ship_tracking_idx"),
            models.Index(fields=("cod_status", "shipment_date"), name="ship_cod_status_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(parcel_count__gt=0), name="ship_parcel_count_positive"),
            models.CheckConstraint(condition=models.Q(weight_kg__gte=0), name="ship_weight_nonnegative"),
            models.CheckConstraint(condition=models.Q(courier_fee__gte=0), name="ship_fee_nonnegative"),
            models.CheckConstraint(condition=models.Q(cod_expected__gte=0), name="ship_cod_expected_nonnegative"),
            models.CheckConstraint(condition=models.Q(cod_collected__gte=0), name="ship_cod_collected_nonnegative"),
            models.CheckConstraint(condition=models.Q(cod_settled__gte=0), name="ship_cod_settled_nonnegative"),
        ]

    def clean(self):
        if self.expected_delivery_date and self.shipment_date and self.expected_delivery_date < self.shipment_date:
            raise ValidationError({"expected_delivery_date": "Expected delivery date cannot be before shipment date."})
        if self.cod_collected > self.cod_expected:
            raise ValidationError({"cod_collected": "Collected COD cannot exceed expected COD."})
        if self.cod_settled > self.cod_collected:
            raise ValidationError({"cod_settled": "Settled COD cannot exceed collected COD."})
        if self.cod_expected > ZERO and self.courier_id and not self.courier.supports_cod:
            raise ValidationError({"courier": "Selected courier is not configured for COD."})
        if self.tracking_id and self.courier_id:
            duplicate = Shipment.objects.filter(courier_id=self.courier_id, tracking_id=self.tracking_id)
            if self.pk:
                duplicate = duplicate.exclude(pk=self.pk)
            if duplicate.exists():
                raise ValidationError({"tracking_id": "This tracking ID is already used for the selected courier."})

    @property
    def tracking_url(self):
        return self.courier.build_tracking_url(self.tracking_id)

    @property
    def unsettled_cod(self):
        return max((self.cod_collected or ZERO) - (self.cod_settled or ZERO), ZERO)

    @property
    def customer_name(self):
        return self.order.customer_name

    @property
    def is_terminal(self):
        return self.status in {self.Status.DELIVERED, self.Status.RETURNED, self.Status.CANCELLED}

    def __str__(self):
        return self.shipment_no


class ShipmentEvent(models.Model):
    class Event(models.TextChoices):
        CREATED = "created", "Created"
        STATUS = "status", "Status Changed"
        TRACKING = "tracking", "Tracking Updated"
        DELIVERY_ATTEMPT = "delivery_attempt", "Delivery Attempt"
        COD_COLLECTION = "cod_collection", "COD Collection"
        COD_SETTLEMENT = "cod_settlement", "COD Settlement"
        NOTE = "note", "Note"

    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name="events")
    event = models.CharField(max_length=24, choices=Event.choices)
    previous_status = models.CharField(max_length=24, blank=True)
    new_status = models.CharField(max_length=24, blank=True)
    location = models.CharField(max_length=180, blank=True)
    note = models.TextField(blank=True)
    actor = models.CharField(max_length=160, blank=True)
    occurred_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-occurred_at", "-id")
        indexes = [models.Index(fields=("shipment", "occurred_at"), name="ship_event_time_idx")]

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            raise ValidationError("Shipment event history is immutable and cannot be edited.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Shipment event history is immutable and cannot be deleted.")

    def __str__(self):
        return f"{self.shipment.shipment_no}: {self.get_event_display()}"


class CODSettlement(models.Model):
    settlement_no = models.CharField(max_length=64, unique=True, default=make_settlement_number)
    courier = models.ForeignKey(CourierProvider, on_delete=models.PROTECT, related_name="cod_settlements")
    settlement_date = models.DateField(default=timezone.localdate)
    payment_method = models.CharField(max_length=20, choices=PaymentMethodConfig.Method.choices)
    reference = models.CharField(max_length=160, blank=True)
    gross_amount = models.DecimalField(max_digits=18, decimal_places=2)
    courier_deduction = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    net_received = models.DecimalField(max_digits=18, decimal_places=2)
    note = models.TextField(blank=True)
    actor = models.CharField(max_length=160, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-settlement_date", "-id")
        indexes = [
            models.Index(fields=("courier", "settlement_date"), name="ship_settle_courier_idx"),
            models.Index(fields=("settlement_date",), name="ship_settle_date_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(gross_amount__gt=0), name="ship_settle_gross_positive"),
            models.CheckConstraint(condition=models.Q(courier_deduction__gte=0), name="ship_settle_deduct_nonnegative"),
            models.CheckConstraint(condition=models.Q(net_received__gte=0), name="ship_settle_net_nonnegative"),
        ]

    def clean(self):
        # Gross/net values are calculated by the settlement service, so ModelForm header
        # validation may legitimately call clean() before those service-owned values exist.
        if self.gross_amount is None:
            return
        deduction = self.courier_deduction or ZERO
        if deduction > self.gross_amount:
            raise ValidationError({"courier_deduction": "Courier deduction cannot exceed gross COD."})
        if self.net_received is not None:
            expected_net = self.gross_amount - deduction
            if self.net_received != expected_net:
                raise ValidationError({"net_received": "Net received must equal gross COD minus courier deduction."})

    def __str__(self):
        return self.settlement_no


class CODSettlementItem(models.Model):
    settlement = models.ForeignKey(CODSettlement, on_delete=models.CASCADE, related_name="items")
    shipment = models.ForeignKey(Shipment, on_delete=models.PROTECT, related_name="settlement_items")
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    payment_transaction = models.OneToOneField(
        PaymentTransaction,
        on_delete=models.PROTECT,
        related_name="cod_settlement_item",
    )

    class Meta:
        ordering = ("id",)
        constraints = [
            models.UniqueConstraint(fields=("settlement", "shipment"), name="uniq_ship_settlement_item"),
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="ship_settlement_item_positive"),
        ]

    def __str__(self):
        return f"{self.settlement.settlement_no} / {self.shipment.shipment_no}"
