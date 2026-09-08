from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class StoreSettings(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    store_name = models.CharField(max_length=120, default="TechBari")
    tagline = models.CharField(max_length=180, default="Upgrade Your Everyday", blank=True)
    support_phone = models.CharField(max_length=40, default="09678-123456", blank=True)
    support_hours = models.CharField(max_length=120, default="10AM - 10PM", blank=True)
    support_email = models.EmailField(default="support@techbari.com", blank=True)
    business_email = models.EmailField(blank=True)
    address = models.TextField(default="Dhaka, Bangladesh", blank=True)
    logo = models.ImageField(upload_to="cms/branding/", blank=True)
    favicon = models.ImageField(upload_to="cms/branding/", blank=True)

    facebook_url = models.URLField(blank=True)
    youtube_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    tiktok_url = models.URLField(blank=True)
    whatsapp_number = models.CharField(max_length=32, blank=True)

    topbar_delivery_text = models.CharField(max_length=160, default="Free Delivery Across Bangladesh", blank=True)
    topbar_authentic_text = models.CharField(max_length=160, default="100% Original Products", blank=True)
    topbar_return_text = models.CharField(max_length=160, default="Easy Return Within 7 Days", blank=True)
    footer_about = models.TextField(default="Your trusted destination for premium electronics and genuine accessories in Bangladesh.", blank=True)
    copyright_text = models.CharField(max_length=220, default="© 2026 TechBari. All rights reserved.", blank=True)

    currency_code = models.CharField(max_length=8, default="BDT")
    currency_symbol = models.CharField(max_length=8, default="৳")
    delivery_inside_dhaka_charge = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("60.00"), validators=[MinValueValidator(0)])
    delivery_outside_dhaka_charge = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("120.00"), validators=[MinValueValidator(0)])
    free_delivery_threshold = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(0)], help_text="0 disables automatic free delivery.")
    delivery_inside_days_min = models.PositiveSmallIntegerField(default=1)
    delivery_inside_days_max = models.PositiveSmallIntegerField(default=2)
    delivery_outside_days_min = models.PositiveSmallIntegerField(default=2)
    delivery_outside_days_max = models.PositiveSmallIntegerField(default=4)
    cod_enabled = models.BooleanField(default=True)
    guest_checkout_enabled = models.BooleanField(default=True)

    seo_title = models.CharField(max_length=180, default="TechBari - Electronics Store", blank=True)
    seo_description = models.CharField(max_length=320, default="Premium electronics and genuine accessories in Bangladesh.", blank=True)
    seo_keywords = models.CharField(max_length=320, blank=True)
    homepage_seo_title = models.CharField(max_length=180, default="TechBari - Electronics Store", blank=True)
    homepage_seo_description = models.CharField(max_length=320, default="Shop genuine electronics, accessories, audio, power and smart devices from TechBari.", blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Store settings"
        verbose_name_plural = "Store settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        self.full_clean()
        return super().save(*args, **kwargs)

    def clean(self):
        errors = {}
        if self.delivery_inside_days_max < self.delivery_inside_days_min:
            errors["delivery_inside_days_max"] = "Maximum days cannot be lower than minimum days."
        if self.delivery_outside_days_max < self.delivery_outside_days_min:
            errors["delivery_outside_days_max"] = "Maximum days cannot be lower than minimum days."
        if errors:
            raise ValidationError(errors)

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return self.store_name


class HeroBanner(models.Model):
    eyebrow = models.CharField(max_length=120, blank=True)
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True)
    cta_label = models.CharField(max_length=100, default="Shop Now →", blank=True)
    cta_url = models.CharField(max_length=500, default="/products/", blank=True)
    image = models.ImageField(upload_to="cms/hero/", blank=True)
    fallback_static = models.CharField(max_length=255, blank=True, help_text="Static path used until an uploaded image exists.")
    alt_text = models.CharField(max_length=180, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=10)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("sort_order", "id")
        indexes = [models.Index(fields=("is_active", "sort_order"))]

    def clean(self):
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": "End time must be after start time."})

    @property
    def is_live(self):
        now = timezone.now()
        return bool(self.is_active and (not self.starts_at or self.starts_at <= now) and (not self.ends_at or self.ends_at >= now))

    def __str__(self):
        return self.title


class HomeSection(models.Model):
    class Key(models.TextChoices):
        HERO = "hero", "Hero banners"
        CATEGORIES = "categories", "Shop by category"
        FEATURED = "featured", "Featured products"
        PROMOS = "promos", "Promotional cards"

    key = models.CharField(max_length=32, choices=Key.choices, unique=True)
    title = models.CharField(max_length=140, blank=True)
    is_enabled = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=10)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("sort_order", "id")

    def __str__(self):
        return self.get_key_display()


class ContentPage(models.Model):
    slug = models.SlugField(max_length=120, unique=True)
    title = models.CharField(max_length=180)
    body = models.TextField(blank=True)
    seo_title = models.CharField(max_length=180, blank=True)
    seo_description = models.CharField(max_length=320, blank=True)
    is_published = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("title",)

    def __str__(self):
        return self.title
