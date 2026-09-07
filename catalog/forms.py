from pathlib import Path

from django import forms
from django.core.exceptions import ValidationError
from django.utils.html import strip_tags
from django.utils.text import slugify
from PIL import Image, UnidentifiedImageError

from .models import Brand, Category, Product, ProductImage, ProductSpecification, ProductVariant

MAX_PRODUCT_IMAGE_BYTES = 2 * 1024 * 1024
ALLOWED_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


def _unique_value(model, field, base, instance_pk=None, max_length=80):
    base = (base or "item")[:max_length].strip("-") or "item"
    candidate = base
    suffix = 2
    qs = model.objects.all()
    if instance_pk:
        qs = qs.exclude(pk=instance_pk)
    while qs.filter(**{field: candidate}).exists():
        tail = f"-{suffix}"
        candidate = f"{base[: max_length - len(tail)]}{tail}"
        suffix += 1
    return candidate


def validate_catalog_image(upload):
    if not upload:
        return upload
    if not hasattr(upload, "content_type"):
        return upload
    if upload.size > MAX_PRODUCT_IMAGE_BYTES:
        raise ValidationError(f"{upload.name}: image must be 2MB or smaller.")
    content_type = getattr(upload, "content_type", "")
    if content_type and content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        raise ValidationError(f"{upload.name}: only JPG, PNG and WebP images are allowed.")
    suffix = Path(upload.name).suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise ValidationError(f"{upload.name}: unsupported image extension.")
    try:
        position = upload.tell()
        image = Image.open(upload)
        image.verify()
        upload.seek(position)
    except (UnidentifiedImageError, OSError, ValueError):
        try:
            upload.seek(0)
        except Exception:
            pass
        raise ValidationError(f"{upload.name}: invalid or corrupted image file.")
    return upload


def validate_product_images(files):
    files = list(files)
    if len(files) > 8:
        raise ValidationError("You can upload a maximum of 8 product images.")
    for upload in files:
        validate_catalog_image(upload)
    return files


class CategoryForm(forms.ModelForm):
    status = forms.ChoiceField(choices=(("Active", "Active"), ("Inactive", "Inactive")))

    class Meta:
        model = Category
        fields = ("name", "slug", "parent", "description", "image", "sort_order")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False
        self.fields["parent"].required = False
        parent_qs = Category.objects.order_by("name")
        if self.instance and self.instance.pk:
            parent_qs = parent_qs.exclude(pk=self.instance.pk)
            self.fields["status"].initial = "Active" if self.instance.is_active else "Inactive"
        self.fields["parent"].queryset = parent_qs

    def clean_slug(self):
        value = slugify(self.cleaned_data.get("slug") or self.cleaned_data.get("name"))
        if not value:
            raise ValidationError("Enter a valid category slug.")
        qs = Category.objects.exclude(pk=self.instance.pk if self.instance else None)
        if qs.filter(slug=value).exists():
            raise ValidationError("A category with this slug already exists.")
        return value

    def clean_image(self):
        return validate_catalog_image(self.cleaned_data.get("image"))

    def clean_parent(self):
        parent = self.cleaned_data.get("parent")
        if not parent or not self.instance or not self.instance.pk:
            return parent
        if parent.pk == self.instance.pk:
            raise ValidationError("A category cannot be its own parent.")
        ancestor = parent
        while ancestor:
            if ancestor.pk == self.instance.pk:
                raise ValidationError("Circular category nesting is not allowed.")
            ancestor = ancestor.parent
        return parent

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.is_active = self.cleaned_data["status"] == "Active"
        if commit:
            obj.save()
        return obj


class BrandForm(forms.ModelForm):
    status = forms.ChoiceField(choices=(("Active", "Active"), ("Inactive", "Inactive")))
    featured = forms.ChoiceField(choices=(("Yes", "Yes"), ("No", "No")))

    class Meta:
        model = Brand
        fields = ("name", "slug", "description", "logo", "sort_order")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False
        if self.instance and self.instance.pk:
            self.fields["status"].initial = "Active" if self.instance.is_active else "Inactive"
            self.fields["featured"].initial = "Yes" if self.instance.is_featured else "No"

    def clean_slug(self):
        value = slugify(self.cleaned_data.get("slug") or self.cleaned_data.get("name"))
        if not value:
            raise ValidationError("Enter a valid brand slug.")
        qs = Brand.objects.exclude(pk=self.instance.pk if self.instance else None)
        if qs.filter(slug=value).exists():
            raise ValidationError("A brand with this slug already exists.")
        return value

    def clean_logo(self):
        return validate_catalog_image(self.cleaned_data.get("logo"))

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.is_active = self.cleaned_data["status"] == "Active"
        obj.is_featured = self.cleaned_data["featured"] == "Yes"
        if commit:
            obj.save()
        return obj


class ProductForm(forms.ModelForm):
    sku = forms.CharField(max_length=64, label="Default SKU")
    barcode = forms.CharField(max_length=64, required=False, label="Default Barcode")
    stock_quantity = forms.IntegerField(min_value=0, label="Default Stock")
    low_stock_alert = forms.IntegerField(min_value=0, initial=5)

    shipping_class = forms.ChoiceField(
        choices=(("standard", "Standard Shipping"), ("fragile", "Fragile / Handle with care"), ("free", "Free Shipping")),
        required=False,
    )
    warranty = forms.ChoiceField(
        choices=(("", "No warranty"), ("7 days", "7 Days"), ("1 month", "1 Month"), ("3 months", "3 Months"), ("6 months", "6 Months"), ("1 year", "1 Year")),
        required=False,
    )

    class Meta:
        model = Product
        fields = (
            "name", "slug", "category", "brand", "short_name", "subtitle", "short_description", "description",
            "regular_price", "sale_price", "weight", "shipping_class", "warranty", "status", "is_featured",
            "is_new_arrival", "meta_title", "meta_description", "badge", "detail_badge",
        )
        widgets = {
            "short_description": forms.Textarea(attrs={"rows": 3, "maxlength": 300}),
            "description": forms.Textarea(attrs={"rows": 8}),
            "meta_description": forms.Textarea(attrs={"rows": 4, "maxlength": 500}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False
        self.fields["category"].queryset = Category.objects.filter(is_active=True).order_by("name")
        self.fields["brand"].queryset = Brand.objects.filter(is_active=True).order_by("name")
        for name in ("shipping_class", "warranty", "short_name", "subtitle", "short_description", "description", "sale_price", "weight", "meta_title", "meta_description", "badge", "detail_badge"):
            self.fields[name].required = False
        self.fields["stock_quantity"].initial = 0
        self.fields["low_stock_alert"].initial = 5
        if self.instance and self.instance.pk:
            default = self._default_variant()
            if default:
                self.fields["sku"].initial = default.sku
                self.fields["barcode"].initial = default.barcode or ""
                self.fields["stock_quantity"].initial = default.stock_quantity
                self.fields["low_stock_alert"].initial = default.low_stock_alert

    def _default_variant(self):
        if not (self.instance and self.instance.pk):
            return None
        variants = list(self.instance.variants.order_by("-is_default", "id"))
        return next((v for v in variants if v.is_default), variants[0] if variants else None)

    def clean_slug(self):
        base = slugify(self.cleaned_data.get("slug") or self.cleaned_data.get("name"))
        if not base:
            raise ValidationError("Enter a valid product slug.")
        base = base[:255]
        qs = Product.objects.exclude(pk=self.instance.pk if self.instance else None)
        if qs.filter(slug=base).exists():
            raise ValidationError("A product with this slug already exists.")
        return base

    def clean_sku(self):
        sku = self.cleaned_data["sku"].strip()
        qs = ProductVariant.objects.filter(sku__iexact=sku)
        default = self._default_variant()
        if default:
            qs = qs.exclude(pk=default.pk)
        if qs.exists():
            raise ValidationError("A product variant with this SKU already exists.")
        return sku

    def clean_barcode(self):
        barcode = (self.cleaned_data.get("barcode") or "").strip()
        if not barcode:
            return ""
        qs = ProductVariant.objects.filter(barcode__iexact=barcode)
        default = self._default_variant()
        if default:
            qs = qs.exclude(pk=default.pk)
        if qs.exists():
            raise ValidationError("A product variant with this barcode already exists.")
        return barcode

    def clean(self):
        cleaned = super().clean()
        regular = cleaned.get("regular_price")
        sale = cleaned.get("sale_price")
        if regular is not None and sale is not None and sale > regular:
            self.add_error("sale_price", "Sale price cannot be higher than regular price.")
        return cleaned

    def _ensure_public_id(self, product):
        if product.public_id:
            return
        base = slugify(product.slug or product.name)[:70]
        product.public_id = _unique_value(Product, "public_id", base, product.pk, 80)

    def _save_default_variant(self, product):
        variants = list(product.variants.order_by("-is_default", "id"))
        variant = next((v for v in variants if v.is_default), variants[0] if variants else None)
        is_new = variant is None
        if is_new:
            variant = ProductVariant(product=product, name="Default", is_default=True, is_active=True)
        elif not variant.is_default:
            product.variants.update(is_default=False)
            variant.is_default = True
        variant.sku = self.cleaned_data["sku"]
        variant.barcode = self.cleaned_data.get("barcode") or None
        variant.stock_quantity = self.cleaned_data["stock_quantity"]
        variant.low_stock_alert = self.cleaned_data["low_stock_alert"]
        variant.save()

    def save(self, commit=True):
        product = super().save(commit=False)
        self._ensure_public_id(product)
        if not product.short_name:
            product.short_name = product.name
        plain_description = " ".join(strip_tags(product.description or "").split())
        if not product.short_description:
            product.short_description = plain_description[:300]
        if not product.description_paragraphs and plain_description:
            product.description_paragraphs = [plain_description]
        if not product.detail_badge:
            product.detail_badge = product.badge
        if commit:
            product.save()
            self._save_default_variant(product)
        return product


class ProductVariantForm(forms.ModelForm):
    class Meta:
        model = ProductVariant
        fields = ("product", "name", "sku", "barcode", "symbol", "regular_price_override", "price_override", "stock_quantity", "low_stock_alert", "is_default", "is_active")
        labels = {"price_override": "Selling price override", "regular_price_override": "Regular price override", "symbol": "Display symbol / color emoji"}

    def __init__(self, *args, **kwargs):
        product_id = kwargs.pop("product_id", None)
        super().__init__(*args, **kwargs)
        self.fields["product"].queryset = Product.objects.order_by("name")
        self.fields["barcode"].required = False
        self.fields["symbol"].required = False
        self.fields["regular_price_override"].required = False
        self.fields["price_override"].required = False
        if self.instance and self.instance.pk:
            self.fields["product"].disabled = True
        elif product_id:
            self.fields["product"].initial = product_id

    def clean_sku(self):
        sku = self.cleaned_data["sku"].strip()
        qs = ProductVariant.objects.filter(sku__iexact=sku)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("A variant with this SKU already exists.")
        return sku

    def clean_barcode(self):
        barcode = (self.cleaned_data.get("barcode") or "").strip()
        if not barcode:
            return None
        qs = ProductVariant.objects.filter(barcode__iexact=barcode)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("A variant with this barcode already exists.")
        return barcode

    def clean(self):
        cleaned = super().clean()
        product = cleaned.get("product")
        name = (cleaned.get("name") or "").strip()
        if product and name:
            qs = ProductVariant.objects.filter(product=product, name__iexact=name)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error("name", "This product already has a variant with this name.")
        if cleaned.get("is_default") and not cleaned.get("is_active"):
            self.add_error("is_active", "The default variant must stay active.")
        regular = cleaned.get("regular_price_override")
        selling = cleaned.get("price_override")
        if regular is not None and selling is not None and selling > regular:
            self.add_error("price_override", "Selling price override cannot exceed regular price override.")
        return cleaned


class ProductImageForm(forms.ModelForm):
    class Meta:
        model = ProductImage
        fields = ("product", "image", "alt_text", "role", "sort_order")

    def __init__(self, *args, **kwargs):
        product_id = kwargs.pop("product_id", None)
        super().__init__(*args, **kwargs)
        self.fields["product"].queryset = Product.objects.order_by("name")
        self.fields["image"].required = not bool(self.instance and self.instance.pk)
        if self.instance and self.instance.pk:
            self.fields["product"].disabled = True
        elif product_id:
            self.fields["product"].initial = product_id

    def clean_image(self):
        upload = self.cleaned_data.get("image")
        if upload and hasattr(upload, "size"):
            validate_catalog_image(upload)
        return upload


class ProductSpecificationForm(forms.ModelForm):
    class Meta:
        model = ProductSpecification
        fields = ("product", "name", "value", "sort_order")

    def __init__(self, *args, **kwargs):
        product_id = kwargs.pop("product_id", None)
        super().__init__(*args, **kwargs)
        self.fields["product"].queryset = Product.objects.order_by("name")
        if self.instance and self.instance.pk:
            self.fields["product"].disabled = True
        elif product_id:
            self.fields["product"].initial = product_id

    def clean(self):
        cleaned = super().clean()
        product = cleaned.get("product")
        name = (cleaned.get("name") or "").strip()
        if product and name:
            qs = ProductSpecification.objects.filter(product=product, name__iexact=name)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error("name", "This product already has a specification with this name.")
        return cleaned
