from django.core.exceptions import ValidationError
from django.db import models

from catalog.models import ProductVariant


class Warehouse(models.Model):
    name = models.CharField(max_length=160)
    code = models.CharField(max_length=32, unique=True)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-is_default", "name")

    def __str__(self):
        return f"{self.name} ({self.code})"


class InventoryBalance(models.Model):
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="balances")
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name="inventory_balances")
    on_hand = models.PositiveIntegerField(default=0)
    reserved_quantity = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(default=5)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("warehouse__name", "variant__product__name", "variant__sku")
        constraints = [
            models.UniqueConstraint(fields=("warehouse", "variant"), name="uniq_inventory_balance_wh_variant"),
            models.CheckConstraint(check=models.Q(on_hand__gte=0), name="inventory_on_hand_nonnegative"),
            models.CheckConstraint(check=models.Q(reserved_quantity__gte=0), name="inventory_reserved_nonnegative"),
            models.CheckConstraint(
                check=models.Q(reserved_quantity__lte=models.F("on_hand")),
                name="inventory_reserved_not_above_on_hand",
            ),
        ]
        indexes = [
            models.Index(fields=("warehouse", "variant"), name="inv_balance_wh_variant_idx"),
            models.Index(fields=("warehouse", "on_hand"), name="inv_balance_wh_stock_idx"),
        ]

    @property
    def available_quantity(self):
        return max(0, self.on_hand - self.reserved_quantity)

    @property
    def is_low_stock(self):
        return self.available_quantity <= self.low_stock_threshold

    def __str__(self):
        return f"{self.warehouse.code} / {self.variant.sku}: {self.available_quantity} available"


class StockMovement(models.Model):
    class Type(models.TextChoices):
        OPENING = "opening", "Opening Stock"
        PURCHASE_IN = "purchase_in", "Purchase In"
        SALE_OUT = "sale_out", "Online Sale Out"
        POS_SALE_OUT = "pos_sale_out", "POS Sale Out"
        RETURN_IN = "return_in", "Sales Return In"
        PURCHASE_RETURN_OUT = "purchase_return_out", "Purchase Return Out"
        ADJUSTMENT_IN = "adjustment_in", "Adjustment In"
        ADJUSTMENT_OUT = "adjustment_out", "Adjustment Out"
        TRANSFER_IN = "transfer_in", "Transfer In"
        TRANSFER_OUT = "transfer_out", "Transfer Out"
        DAMAGE_OUT = "damage_out", "Damage / Loss Out"
        RESERVE = "reserve", "Reserve Stock"
        RELEASE = "release", "Release Reservation"
        RESERVED_SALE = "reserved_sale", "Reserved Stock Sold"

    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="stock_movements")
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_movements",
    )
    sku_snapshot = models.CharField(max_length=64)
    product_snapshot = models.CharField(max_length=255)
    movement_type = models.CharField(max_length=32, choices=Type.choices)
    quantity_delta = models.IntegerField(default=0)
    reserved_delta = models.IntegerField(default=0)
    quantity_after = models.PositiveIntegerField(default=0)
    reserved_after = models.PositiveIntegerField(default=0)
    reference_type = models.CharField(max_length=40, blank=True)
    reference_no = models.CharField(max_length=80, blank=True)
    note = models.TextField(blank=True)
    actor = models.CharField(max_length=160, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=("warehouse", "created_at"), name="inv_move_wh_created_idx"),
            models.Index(fields=("variant", "created_at"), name="inv_move_var_created_idx"),
            models.Index(fields=("movement_type", "created_at"), name="inv_move_type_created_idx"),
            models.Index(fields=("reference_type", "reference_no"), name="inv_move_reference_idx"),
        ]

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            raise ValidationError("Stock movements are immutable and cannot be edited.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Stock movements are immutable and cannot be deleted.")

    def __str__(self):
        return f"{self.get_movement_type_display()} {self.sku_snapshot} ({self.quantity_delta:+d})"


class StockAdjustment(models.Model):
    class Status(models.TextChoices):
        POSTED = "posted", "Posted"

    reference_no = models.CharField(max_length=80, unique=True)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="stock_adjustments")
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_adjustments",
    )
    sku_snapshot = models.CharField(max_length=64)
    product_snapshot = models.CharField(max_length=255)
    system_quantity = models.PositiveIntegerField()
    actual_quantity = models.PositiveIntegerField()
    difference = models.IntegerField()
    reason = models.CharField(max_length=255)
    note = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.POSTED)
    actor = models.CharField(max_length=160, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")

    def __str__(self):
        return self.reference_no


class StockTransfer(models.Model):
    class Status(models.TextChoices):
        COMPLETED = "completed", "Completed"

    transfer_no = models.CharField(max_length=80, unique=True)
    from_warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="outgoing_transfers")
    to_warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="incoming_transfers")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.COMPLETED)
    note = models.TextField(blank=True)
    actor = models.CharField(max_length=160, blank=True)
    completed_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")

    def clean(self):
        if self.from_warehouse_id and self.from_warehouse_id == self.to_warehouse_id:
            raise ValidationError("Source and destination warehouses must be different.")

    def __str__(self):
        return self.transfer_no


class StockTransferItem(models.Model):
    transfer = models.ForeignKey(StockTransfer, on_delete=models.CASCADE, related_name="items")
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_transfer_items",
    )
    sku_snapshot = models.CharField(max_length=64)
    product_snapshot = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField()

    class Meta:
        ordering = ("id",)
        constraints = [
            models.UniqueConstraint(fields=("transfer", "variant"), name="uniq_transfer_variant")
        ]

    def __str__(self):
        return f"{self.transfer.transfer_no} / {self.sku_snapshot} x {self.quantity}"
