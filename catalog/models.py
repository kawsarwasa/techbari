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
    slug = models.SlugField(max_length=280, unique=True)
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


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    name = models.CharField(max_length=120, default="Default")
    sku = models.CharField(max_length=64, unique=True)
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
        constraints = [models.UniqueConstraint(fields=("product", "name"), name="uniq_product_variant_name")]

    def __str__(self):
        return f"{self.product.name} - {self.name}"


class ProductImage(models.Model):
    class Role(models.TextChoices):
        PRIMARY = "primary", "Primary"
        GALLERY = "gallery", "Gallery"
        DETAIL = "detail", "Detail"

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="catalog/products/%Y/%m/", blank=True)
    static_path = models.CharField(max_length=255, blank=True)
    alt_text = models.CharField(max_length=255, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.GALLERY)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("sort_order", "id")

    def __str__(self):
        return f"{self.product.name} image"


class ProductSpecification(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="specifications")
    name = models.CharField(max_length=160)
    value = models.CharField(max_length=500)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "id")
        constraints = [models.UniqueConstraint(fields=("product", "name"), name="uniq_product_spec_name")]

    def __str__(self):
        return f"{self.product.name}: {self.name}"
