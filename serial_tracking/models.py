from django.core.exceptions import ValidationError
from django.db import models

from catalog.models import ProductVariant
from inventory.models import Warehouse


class SerializedUnit(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        RESERVED = "reserved", "Reserved"
        SOLD = "sold", "Sold"
        RETURNED = "returned", "Returned"
        DAMAGED = "damaged", "Damaged"
        WARRANTY_SERVICE = "warranty_service", "Warranty Service"
        SCRAPPED = "scrapped", "Scrapped"
        SUPPLIER_RETURNED = "supplier_returned", "Returned to Supplier"

    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.PROTECT,
        related_name="serialized_units",
    )
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="serialized_units",
    )
    serial_number = models.CharField(max_length=120, unique=True, null=True, blank=True)
    imei1 = models.CharField(max_length=15, unique=True, null=True, blank=True)
    imei2 = models.CharField(max_length=15, unique=True, null=True, blank=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.AVAILABLE)

    supplier_reference = models.CharField(max_length=160, blank=True)
    purchase_reference = models.CharField(max_length=160, blank=True)
    purchase_date = models.DateField(null=True, blank=True)
    purchase_cost = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    received_date = models.DateField(null=True, blank=True)

    sales_reference = models.CharField(max_length=160, blank=True)
    customer_reference = models.CharField(max_length=160, blank=True)
    sold_at = models.DateField(null=True, blank=True)

    warranty_type = models.CharField(max_length=120, blank=True)
    warranty_start_date = models.DateField(null=True, blank=True)
    warranty_end_date = models.DateField(null=True, blank=True)
    supplier_warranty_reference = models.CharField(max_length=160, blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=("variant", "status"), name="ser_unit_variant_status_idx"),
            models.Index(fields=("warehouse", "status"), name="ser_unit_wh_status_idx"),
            models.Index(fields=("status", "created_at"), name="ser_unit_status_created_idx"),
        ]

    @staticmethod
    def _normalize_identifier(value):
        value = (value or "").strip()
        return value or None

    def clean(self):
        self.serial_number = self._normalize_identifier(self.serial_number)
        self.imei1 = self._normalize_identifier(self.imei1)
        self.imei2 = self._normalize_identifier(self.imei2)

        if not any((self.serial_number, self.imei1, self.imei2)):
            raise ValidationError("Enter at least one Serial Number, IMEI 1 or IMEI 2.")

        for field_name in ("imei1", "imei2"):
            value = getattr(self, field_name)
            if value and (not value.isdigit() or len(value) != 15):
                raise ValidationError({field_name: "IMEI must contain exactly 15 digits."})

        if self.imei1 and self.imei2 and self.imei1 == self.imei2:
            raise ValidationError({"imei2": "IMEI 2 must be different from IMEI 1."})

        if self.warranty_start_date and self.warranty_end_date:
            if self.warranty_end_date < self.warranty_start_date:
                raise ValidationError({"warranty_end_date": "Warranty end date cannot be before the start date."})

        if self.purchase_cost is not None and self.purchase_cost < 0:
            raise ValidationError({"purchase_cost": "Purchase cost cannot be negative."})

    @property
    def display_identifier(self):
        return self.serial_number or self.imei1 or self.imei2 or f"UNIT-{self.pk}"

    @property
    def is_stock_bearing(self):
        return self.status in {
            self.Status.AVAILABLE,
            self.Status.RESERVED,
            self.Status.RETURNED,
        }

    @property
    def warranty_is_active(self):
        from django.utils import timezone

        if not self.warranty_end_date:
            return False
        return self.warranty_end_date >= timezone.localdate()

    def __str__(self):
        return f"{self.variant.sku} / {self.display_identifier}"


class SerializedUnitEvent(models.Model):
    class Type(models.TextChoices):
        REGISTERED = "registered", "Registered"
        IDENTIFIERS_UPDATED = "identifiers_updated", "Identifiers Updated"
        TRANSFERRED = "transferred", "Warehouse Transferred"
        STATUS_CHANGED = "status_changed", "Status Changed"
        WARRANTY_OPENED = "warranty_opened", "Warranty Claim Opened"
        WARRANTY_UPDATED = "warranty_updated", "Warranty Claim Updated"
        WARRANTY_REPLACED = "warranty_replaced", "Warranty Replacement"

    unit = models.ForeignKey(SerializedUnit, on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(max_length=32, choices=Type.choices)
    from_status = models.CharField(max_length=32, blank=True)
    to_status = models.CharField(max_length=32, blank=True)
    from_warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="serialized_events_from",
    )
    to_warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="serialized_events_to",
    )
    reference_no = models.CharField(max_length=160, blank=True)
    note = models.TextField(blank=True)
    actor = models.CharField(max_length=160, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=("unit", "created_at"), name="ser_event_unit_created_idx"),
            models.Index(fields=("event_type", "created_at"), name="ser_event_type_created_idx"),
        ]

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            raise ValidationError("Serialized-unit events are immutable and cannot be edited.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Serialized-unit events are immutable and cannot be deleted.")

    def __str__(self):
        return f"{self.unit.display_identifier}: {self.get_event_type_display()}"


class WarrantyClaim(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_SERVICE = "in_service", "In Service"
        RESOLVED = "resolved", "Resolved"
        REPLACED = "replaced", "Replaced"
        REJECTED = "rejected", "Rejected"

    claim_no = models.CharField(max_length=80, unique=True)
    unit = models.ForeignKey(SerializedUnit, on_delete=models.PROTECT, related_name="warranty_claims")
    customer_name = models.CharField(max_length=160, blank=True)
    customer_phone = models.CharField(max_length=40, blank=True)
    order_reference = models.CharField(max_length=160, blank=True)
    claim_date = models.DateField()
    issue = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    resolution = models.TextField(blank=True)
    service_reference = models.CharField(max_length=160, blank=True)
    replacement_unit = models.ForeignKey(
        SerializedUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="replacement_for_claims",
    )
    resolved_at = models.DateField(null=True, blank=True)
    unit_status_before_claim = models.CharField(max_length=32, blank=True)
    notes = models.TextField(blank=True)
    actor = models.CharField(max_length=160, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-claim_date", "-id")
        indexes = [
            models.Index(fields=("status", "claim_date"), name="ser_claim_status_date_idx"),
            models.Index(fields=("unit", "claim_date"), name="ser_claim_unit_date_idx"),
        ]

    def clean(self):
        if self.replacement_unit_id and self.replacement_unit_id == self.unit_id:
            raise ValidationError({"replacement_unit": "Replacement unit must be different from the claimed unit."})
        if self.replacement_unit_id and self.unit_id:
            if self.replacement_unit.variant_id != self.unit.variant_id:
                raise ValidationError({"replacement_unit": "Replacement unit must use the same product variant/SKU."})
        if self.resolved_at and self.claim_date and self.resolved_at < self.claim_date:
            raise ValidationError({"resolved_at": "Resolved date cannot be before the claim date."})
        if self.status == self.Status.REPLACED and not self.replacement_unit_id:
            raise ValidationError({"replacement_unit": "Choose a replacement unit when status is Replaced."})

    @property
    def within_unit_warranty(self):
        if not self.unit.warranty_end_date:
            return False
        start_ok = not self.unit.warranty_start_date or self.claim_date >= self.unit.warranty_start_date
        return start_ok and self.claim_date <= self.unit.warranty_end_date

    def __str__(self):
        return self.claim_no
