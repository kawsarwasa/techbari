from decimal import Decimal

from django.db import migrations, models
import django.core.validators


def seed_cms(apps, schema_editor):
    StoreSettings = apps.get_model("store_settings", "StoreSettings")
    HeroBanner = apps.get_model("store_settings", "HeroBanner")
    HomeSection = apps.get_model("store_settings", "HomeSection")
    ContentPage = apps.get_model("store_settings", "ContentPage")

    StoreSettings.objects.get_or_create(pk=1)
    sections = [
        ("hero", "Featured Offers", 10),
        ("categories", "Shop by Category", 20),
        ("featured", "Featured Products", 30),
        ("promos", "Special Collections", 40),
    ]
    for key, title, order in sections:
        HomeSection.objects.get_or_create(key=key, defaults={"title": title, "sort_order": order, "is_enabled": True})

    banners = [
        {"eyebrow": "Sound that moves you", "title": "Premium Audio\nFor a Better You", "description": "TWS Earbuds | Headphones | Speakers\nDiscover authentic sound. Only at TechBari.", "cta_label": "Shop Audio Products →", "cta_url": "/products/", "fallback_static": "store/images/hero-audio.webp", "alt_text": "Premium audio products", "sort_order": 10},
        {"eyebrow": "Power your day", "title": "Reliable Power\nAlways With You", "description": "Power Banks | Chargers | Cables\nFast, dependable charging for every device.", "cta_label": "Shop Power Solutions →", "cta_url": "/products/", "fallback_static": "store/images/promo-power.webp", "alt_text": "Power banks chargers and cables", "sort_order": 20},
        {"eyebrow": "Style meets function", "title": "Smartwatches\nFor a Smarter You", "description": "Track. Stay Connected. Do More.\nSmart wearables for everyday life.", "cta_label": "Shop Smartwatches →", "cta_url": "/products/", "fallback_static": "store/images/promo-watch.webp", "alt_text": "Smartwatch collection", "sort_order": 30},
    ]
    if not HeroBanner.objects.exists():
        for row in banners:
            HeroBanner.objects.create(**row)

    pages = {
        "terms-and-conditions": ("Terms & Conditions", "These terms govern use of the TechBari storefront and purchases placed through it. Product availability, pricing and order acceptance are confirmed by the system at checkout. Customers are responsible for providing accurate delivery and contact information."),
        "privacy-policy": ("Privacy Policy", "TechBari uses customer information to process orders, provide support, prevent fraud and improve the shopping experience. Access to business and customer data is restricted to authorized staff roles. Personal information should only be retained and shared as required for legitimate business operations and applicable law."),
        "return-refund-policy": ("Return & Refund Policy", "Eligible products may be requested for return within the published return window, subject to product condition, serial or IMEI verification where applicable, warranty rules and the approved return workflow. Refunds are processed against the original order and payment records."),
        "shipping-policy": ("Shipping Policy", "Delivery charges and estimated delivery times are configured by TechBari and shown during checkout. Final shipping charges are recalculated by the server when the order is placed. Delivery times are estimates and may vary by destination and courier conditions."),
    }
    for slug, (title, body) in pages.items():
        ContentPage.objects.get_or_create(slug=slug, defaults={"title": title, "body": body, "seo_title": f"{title} | TechBari", "seo_description": body[:300], "is_published": True})


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="StoreSettings",
            fields=[
                ("id", models.PositiveSmallIntegerField(default=1, editable=False, primary_key=True, serialize=False)),
                ("store_name", models.CharField(default="TechBari", max_length=120)),
                ("tagline", models.CharField(blank=True, default="Upgrade Your Everyday", max_length=180)),
                ("support_phone", models.CharField(blank=True, default="09678-123456", max_length=40)),
                ("support_hours", models.CharField(blank=True, default="10AM - 10PM", max_length=120)),
                ("support_email", models.EmailField(blank=True, default="support@techbari.com", max_length=254)),
                ("business_email", models.EmailField(blank=True, max_length=254)),
                ("address", models.TextField(blank=True, default="Dhaka, Bangladesh")),
                ("logo", models.ImageField(blank=True, upload_to="cms/branding/")),
                ("favicon", models.ImageField(blank=True, upload_to="cms/branding/")),
                ("facebook_url", models.URLField(blank=True)), ("youtube_url", models.URLField(blank=True)), ("instagram_url", models.URLField(blank=True)), ("tiktok_url", models.URLField(blank=True)), ("whatsapp_number", models.CharField(blank=True, max_length=32)),
                ("topbar_delivery_text", models.CharField(blank=True, default="Free Delivery Across Bangladesh", max_length=160)),
                ("topbar_authentic_text", models.CharField(blank=True, default="100% Original Products", max_length=160)),
                ("topbar_return_text", models.CharField(blank=True, default="Easy Return Within 7 Days", max_length=160)),
                ("footer_about", models.TextField(blank=True, default="Your trusted destination for premium electronics and genuine accessories in Bangladesh.")),
                ("copyright_text", models.CharField(blank=True, default="© 2026 TechBari. All rights reserved.", max_length=220)),
                ("currency_code", models.CharField(default="BDT", max_length=8)), ("currency_symbol", models.CharField(default="৳", max_length=8)),
                ("delivery_inside_dhaka_charge", models.DecimalField(decimal_places=2, default=Decimal("60.00"), max_digits=10, validators=[django.core.validators.MinValueValidator(0)])),
                ("delivery_outside_dhaka_charge", models.DecimalField(decimal_places=2, default=Decimal("120.00"), max_digits=10, validators=[django.core.validators.MinValueValidator(0)])),
                ("free_delivery_threshold", models.DecimalField(decimal_places=2, default=Decimal("0.00"), help_text="0 disables automatic free delivery.", max_digits=12, validators=[django.core.validators.MinValueValidator(0)])),
                ("delivery_inside_days_min", models.PositiveSmallIntegerField(default=1)), ("delivery_inside_days_max", models.PositiveSmallIntegerField(default=2)), ("delivery_outside_days_min", models.PositiveSmallIntegerField(default=2)), ("delivery_outside_days_max", models.PositiveSmallIntegerField(default=4)),
                ("cod_enabled", models.BooleanField(default=True)), ("guest_checkout_enabled", models.BooleanField(default=True)),
                ("seo_title", models.CharField(blank=True, default="TechBari - Electronics Store", max_length=180)), ("seo_description", models.CharField(blank=True, default="Premium electronics and genuine accessories in Bangladesh.", max_length=320)), ("seo_keywords", models.CharField(blank=True, max_length=320)),
                ("homepage_seo_title", models.CharField(blank=True, default="TechBari - Electronics Store", max_length=180)), ("homepage_seo_description", models.CharField(blank=True, default="Shop genuine electronics, accessories, audio, power and smart devices from TechBari.", max_length=320)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"verbose_name": "Store settings", "verbose_name_plural": "Store settings"},
        ),
        migrations.CreateModel(
            name="HeroBanner",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("eyebrow", models.CharField(blank=True, max_length=120)), ("title", models.CharField(max_length=220)), ("description", models.TextField(blank=True)), ("cta_label", models.CharField(blank=True, default="Shop Now →", max_length=100)), ("cta_url", models.CharField(blank=True, default="/products/", max_length=500)), ("image", models.ImageField(blank=True, upload_to="cms/hero/")), ("fallback_static", models.CharField(blank=True, help_text="Static path used until an uploaded image exists.", max_length=255)), ("alt_text", models.CharField(blank=True, max_length=180)), ("is_active", models.BooleanField(default=True)), ("sort_order", models.PositiveIntegerField(default=10)), ("starts_at", models.DateTimeField(blank=True, null=True)), ("ends_at", models.DateTimeField(blank=True, null=True)), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ("sort_order", "id")},
        ),
        migrations.CreateModel(
            name="HomeSection",
            fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("key", models.CharField(choices=[("hero", "Hero banners"), ("categories", "Shop by category"), ("featured", "Featured products"), ("promos", "Promotional cards")], max_length=32, unique=True)), ("title", models.CharField(blank=True, max_length=140)), ("is_enabled", models.BooleanField(default=True)), ("sort_order", models.PositiveIntegerField(default=10)), ("updated_at", models.DateTimeField(auto_now=True))],
            options={"ordering": ("sort_order", "id")},
        ),
        migrations.CreateModel(
            name="ContentPage",
            fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("slug", models.SlugField(max_length=120, unique=True)), ("title", models.CharField(max_length=180)), ("body", models.TextField(blank=True)), ("seo_title", models.CharField(blank=True, max_length=180)), ("seo_description", models.CharField(blank=True, max_length=320)), ("is_published", models.BooleanField(default=True)), ("updated_at", models.DateTimeField(auto_now=True))],
            options={"ordering": ("title",)},
        ),
        migrations.AddIndex(model_name="herobanner", index=models.Index(fields=["is_active", "sort_order"], name="store_setti_is_acti_3c5103_idx")),
        migrations.RunPython(seed_cms, migrations.RunPython.noop),
    ]
