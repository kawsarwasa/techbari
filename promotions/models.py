from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from catalog.models import Category, Product
from sales.models import SalesOrder


class Campaign(models.Model):
    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=180)
    source = models.CharField(max_length=80, blank=True)
    medium = models.CharField(max_length=80, blank=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-starts_at", "-id")
        indexes = [models.Index(fields=("is_active", "starts_at", "ends_at"), name="promo_campaign_live_idx")]

    def clean(self):
        super().clean()
        self.code = (self.code or "").strip().upper()
        if self.ends_at and self.starts_at and self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": "Campaign end must be after its start."})

    def save(self, *args, **kwargs):
        self.code = (self.code or "").strip().upper()
        return super().save(*args, **kwargs)

    @property
    def is_live(self):
        now = timezone.now()
        return bool(self.is_active and self.starts_at <= now <= self.ends_at)

    def __str__(self):
        return f"{self.code} — {self.name}"


class Coupon(models.Model):
    class DiscountType(models.TextChoices):
        FIXED = "fixed", "Fixed amount"
        PERCENTAGE = "percentage", "Percentage"

    class Scope(models.TextChoices):
        ALL = "all", "All products"
        PRODUCTS = "products", "Specific products"
        CATEGORIES = "categories", "Specific categories"

    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=180)
    discount_type = models.CharField(max_length=20, choices=DiscountType.choices)
    value = models.DecimalField(max_digits=18, decimal_places=2)
    minimum_order_amount = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    usage_limit = models.PositiveIntegerField(null=True, blank=True)
    usage_count = models.PositiveIntegerField(default=0)
    scope = models.CharField(max_length=20, choices=Scope.choices, default=Scope.ALL)
    products = models.ManyToManyField(Product, blank=True, related_name="marketing_coupons")
    categories = models.ManyToManyField(Category, blank=True, related_name="marketing_coupons")
    campaign = models.ForeignKey(Campaign, on_delete=models.SET_NULL, null=True, blank=True, related_name="coupons")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "code")
        indexes = [
            models.Index(fields=("is_active", "starts_at", "ends_at"), name="promo_coupon_live_idx"),
            models.Index(fields=("campaign", "is_active"), name="promo_coupon_campaign_idx"),
        ]

    def clean(self):
        super().clean()
        self.code = (self.code or "").strip().upper()
        if self.value is None or self.value <= 0:
            raise ValidationError({"value": "Discount value must be greater than zero."})
        if self.discount_type == self.DiscountType.PERCENTAGE and self.value > 100:
            raise ValidationError({"value": "Percentage discount cannot exceed 100%."})
        if self.minimum_order_amount is not None and self.minimum_order_amount < 0:
            raise ValidationError({"minimum_order_amount": "Minimum order cannot be negative."})
        if self.ends_at and self.starts_at and self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": "Coupon end must be after its start."})
        if self.usage_limit is not None and self.usage_count > self.usage_limit:
            raise ValidationError({"usage_limit": "Usage limit cannot be below usage already recorded."})

    def save(self, *args, **kwargs):
        self.code = (self.code or "").strip().upper()
        return super().save(*args, **kwargs)

    @property
    def is_live(self):
        now = timezone.now()
        usage_ok = self.usage_limit is None or self.usage_count < self.usage_limit
        return bool(self.is_active and self.starts_at <= now <= self.ends_at and usage_ok)

    @property
    def remaining_uses(self):
        if self.usage_limit is None:
            return None
        return max(self.usage_limit - self.usage_count, 0)

    def __str__(self):
        return self.code


class FlashSale(models.Model):
    class DiscountType(models.TextChoices):
        FIXED = "fixed", "Fixed amount"
        PERCENTAGE = "percentage", "Percentage"

    name = models.CharField(max_length=180)
    discount_type = models.CharField(max_length=20, choices=DiscountType.choices)
    value = models.DecimalField(max_digits=18, decimal_places=2)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    products = models.ManyToManyField(Product, related_name="flash_sales")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-starts_at", "-id")
        indexes = [models.Index(fields=("is_active", "starts_at", "ends_at"), name="promo_flash_live_idx")]

    def clean(self):
        super().clean()
        if self.value is None or self.value <= 0:
            raise ValidationError({"value": "Discount value must be greater than zero."})
        if self.discount_type == self.DiscountType.PERCENTAGE and self.value > 100:
            raise ValidationError({"value": "Percentage discount cannot exceed 100%."})
        if self.ends_at and self.starts_at and self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": "Flash Sale end must be after its start."})

    @property
    def is_live(self):
        now = timezone.now()
        return bool(self.is_active and self.starts_at <= now <= self.ends_at)

    def __str__(self):
        return self.name


class CouponRedemption(models.Model):
    coupon = models.ForeignKey(Coupon, on_delete=models.PROTECT, related_name="redemptions")
    order = models.OneToOneField(SalesOrder, on_delete=models.PROTECT, related_name="coupon_redemption")
    discount_amount = models.DecimalField(max_digits=18, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")

    def __str__(self):
        return f"{self.coupon.code} / {self.order.order_number}"


class CampaignEvent(models.Model):
    class EventType(models.TextChoices):
        VISIT = "visit", "Visit"
        COUPON_APPLIED = "coupon_applied", "Coupon Applied"
        CONVERSION = "conversion", "Conversion"

    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(max_length=30, choices=EventType.choices)
    tracking_token = models.CharField(max_length=64, blank=True)
    order = models.ForeignKey(SalesOrder, on_delete=models.SET_NULL, null=True, blank=True, related_name="campaign_events")
    coupon = models.ForeignKey(Coupon, on_delete=models.SET_NULL, null=True, blank=True, related_name="campaign_events")
    source = models.CharField(max_length=80, blank=True)
    medium = models.CharField(max_length=80, blank=True)
    landing_path = models.CharField(max_length=500, blank=True)
    referrer = models.CharField(max_length=500, blank=True)
    amount = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=("campaign", "event_type", "created_at"), name="promo_event_campaign_idx"),
            models.Index(fields=("tracking_token", "created_at"), name="promo_event_token_idx"),
        ]
        constraints = [models.UniqueConstraint(fields=("campaign", "order", "event_type"), name="uniq_promo_campaign_order_event")]

    def __str__(self):
        return f"{self.campaign.code}: {self.event_type}"
