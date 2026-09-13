from django.core.exceptions import ValidationError
from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
    )
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="catalog/categories/", blank=True)
    static_image_path = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("sort_order", "name")
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Brand(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to="catalog/brands/", blank=True)
    static_image_path = models.CharField(max_length=255, blank=True)
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("sort_order", "name")

    def __str__(self):
        return self.name


class Product(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"

    public_id = models.SlugField(
        max_length=80,
        unique=True,
        help_text="Stable browser/cart identifier. Existing demo IDs are preserved.",
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT, related_name="products")
    short_name = models.CharField(max_length=255, blank=True)
    subtitle = models.CharField(max_length=255, blank=True)
    short_description = models.CharField(max_length=300, blank=True)
    description = models.TextField(blank=True)
    regular_price = models.DecimalField(max_digits=18, decimal_places=2)
    sale_price = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    badge = models.CharField(max_length=80, blank=True)
    badge_class = models.CharField(max_length=30, blank=True, default="blue")
    detail_badge = models.CharField(max_length=80, blank=True)
    weight = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    shipping_class = models.CharField(max_length=80, blank=True, default="standard")
    warranty = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    is_featured = models.BooleanField(default=False)
    is_new_arrival = models.BooleanField(default=False)
    meta_title = models.CharField(max_length=255, blank=True)
    meta_description = models.CharField(max_length=500, blank=True)
    description_paragraphs = models.JSONField(default=list, blank=True)
    features = models.JSONField(default=list, blank=True)
    box_contents = models.JSONField(default=list, blank=True)
    reviews = models.JSONField(default=list, blank=True)
    questions = models.JSONField(default=list, blank=True)
    review_score = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    review_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "name")
        indexes = [
            models.Index(fields=("status", "created_at"), name="cat_prod_status_created_idx"),
            models.Index(fields=("category", "status"), name="cat_prod_cat_status_idx"),
            models.Index(fields=("brand", "status"), name="cat_prod_brand_status_idx"),
        ]

    def __str__(self):
        return self.name

    @property
    def current_price(self):
        return self.sale_price if self.sale_price is not None else self.regular_price

    @property
    def stock_quantity(self):
        return sum(v.stock_quantity for v in self.variants.all() if v.is_active)

    @property
    def default_variant(self):
        variants = list(self.variants.all())
        return next((v for v in variants if v.is_default), variants[0] if variants else None)


class VariantAttribute(models.Model):
    class DisplayType(models.TextChoices):
        SWATCH = "swatch", "Color Swatch"
        BUTTON = "button", "Button"
        DROPDOWN = "dropdown", "Dropdown"

    name = models.CharField(max_length=80)
    code = models.SlugField(max_length=80, unique=True)
    display_type = models.CharField(max_length=16, choices=DisplayType.choices, default=DisplayType.BUTTON)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("sort_order", "name", "id")
        constraints = [models.UniqueConstraint(fields=("name",), name="uniq_variant_attribute_name")]
        indexes = [models.Index(fields=("is_active", "sort_order"), name="cat_attr_active_sort_idx")]

    def __str__(self):
        return self.name


class VariantAttributeValue(models.Model):
    attribute = models.ForeignKey(VariantAttribute, on_delete=models.CASCADE, related_name="values")
    value = models.CharField(max_length=120)
    code = models.SlugField(max_length=80)
    symbol = models.CharField(max_length=32, blank=True)
    color_hex = models.CharField(max_length=9, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("attribute_id", "sort_order", "value", "id")
        constraints = [
            models.UniqueConstraint(fields=("attribute", "value"), name="uniq_variant_attr_value"),
            models.UniqueConstraint(fields=("attribute", "code"), name="uniq_variant_attr_code"),
        ]
        indexes = [models.Index(fields=("attribute", "is_active", "sort_order"), name="cat_attrval_active_idx")]

    def __str__(self):
        return f"{self.attribute.name}: {self.value}"


class VariantPreset(models.Model):
    name = models.CharField(max_length=120, unique=True)
    code = models.SlugField(max_length=120, unique=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("sort_order", "name", "id")

    def __str__(self):
        return self.name


class VariantPresetAttribute(models.Model):
    preset = models.ForeignKey(VariantPreset, on_delete=models.CASCADE, related_name="attribute_links")
    attribute = models.ForeignKey(VariantAttribute, on_delete=models.PROTECT, related_name="preset_links")
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("preset_id", "sort_order", "id")
        constraints = [models.UniqueConstraint(fields=("preset", "attribute"), name="uniq_preset_attribute")]

    def __str__(self):
        return f"{self.preset.name} / {self.attribute.name}"


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    name = models.CharField(max_length=120, default="Default")
    sku = models.CharField(max_length=64, unique=True)
    barcode = models.CharField(max_length=64, unique=True, null=True, blank=True)
    symbol = models.CharField(max_length=16, blank=True)
    price_override = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    regular_price_override = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    stock_quantity = models.PositiveIntegerField(default=0)
    low_stock_alert = models.PositiveIntegerField(default=5)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("product_id", "-is_default", "id")
        constraints = [
            models.UniqueConstraint(fields=("product", "name"), name="uniq_product_variant_name")
        ]
        indexes = [
            models.Index(fields=("product", "is_active"), name="cat_var_prod_active_idx"),
        ]

    @property
    def option_summary(self):
        rows = self.variant_values.select_related("value", "value__attribute").order_by(
            "value__attribute__sort_order", "value__attribute_id", "value__sort_order", "id"
        )
        return " / ".join(row.value.value for row in rows)

    @property
    def display_name(self):
        return self.option_summary or self.name

    def __str__(self):
        return f"{self.product.name} - {self.display_name}"


class ProductVariantValue(models.Model):
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name="variant_values")
    value = models.ForeignKey(VariantAttributeValue, on_delete=models.PROTECT, related_name="variant_links")

    class Meta:
        ordering = ("value__attribute__sort_order", "value__sort_order", "id")
        constraints = [models.UniqueConstraint(fields=("variant", "value"), name="uniq_variant_global_value")]
        indexes = [models.Index(fields=("variant", "value"), name="cat_varvalue_idx")]

    def clean(self):
        if not self.variant_id or not self.value_id:
            return
        conflict = ProductVariantValue.objects.filter(
            variant_id=self.variant_id,
            value__attribute_id=self.value.attribute_id,
        )
        if self.pk:
            conflict = conflict.exclude(pk=self.pk)
        if conflict.exists():
            raise ValidationError(f"Choose only one value for {self.value.attribute.name}.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.variant.sku} / {self.value.attribute.name}: {self.value.value}"


class ProductImage(models.Model):
    class Role(models.TextChoices):
        PRIMARY = "primary", "Primary"
        GALLERY = "gallery", "Gallery"
        DETAIL = "detail", "Detail"

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    attribute_value = models.ForeignKey(
        VariantAttributeValue,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="product_images",
        help_text="Optional variant value this image represents, usually a color/finish.",
    )
    image = models.ImageField(upload_to="catalog/products/%Y/%m/", blank=True)
    static_path = models.CharField(max_length=255, blank=True)
    alt_text = models.CharField(max_length=255, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.GALLERY)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("sort_order", "id")
        indexes = [
            models.Index(fields=("product", "role", "sort_order"), name="cat_img_prod_role_idx")
        ]

    def __str__(self):
        return f"{self.product.name} image"


class ProductSpecification(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="specifications")
    name = models.CharField(max_length=160)
    value = models.CharField(max_length=500)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "id")
        constraints = [
            models.UniqueConstraint(fields=("product", "name"), name="uniq_product_spec_name")
        ]

    def __str__(self):
        return f"{self.product.name}: {self.name}"
