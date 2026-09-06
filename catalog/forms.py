from pathlib import Path

from django import forms
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from PIL import Image, UnidentifiedImageError

from .models import Brand, Category, Product, ProductVariant

MAX_PRODUCT_IMAGE_BYTES = 2 * 1024 * 1024
ALLOWED_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
VARIANT_CHOICES = (("White", "White"), ("Black", "Black"), ("Blue", "Blue"), ("Pink", "Pink"))


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


def validate_product_images(files):
    files = list(files)
    if len(files) > 8:
        raise ValidationError("You can upload a maximum of 8 product images.")
    for upload in files:
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
    return files


class CategoryForm(forms.ModelForm):
    status = forms.ChoiceField(choices=(("Active", "Active"), ("Inactive", "Inactive")))

    class Meta:
        model = Category
        fields = ("name", "slug", "parent", "description", "image")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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
        return value

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
        fields = ("name", "slug", "description", "logo")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["status"].initial = "Active" if self.instance.is_active else "Inactive"
            self.fields["featured"].initial = "Yes" if self.instance.is_featured else "No"

    def clean_slug(self):
        value = slugify(self.cleaned_data.get("slug") or self.cleaned_data.get("name"))
        if not value:
            raise ValidationError("Enter a valid brand slug.")
        return value

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.is_active = self.cleaned_data["status"] == "Active"
        obj.is_featured = self.cleaned_data["featured"] == "Yes"
        if commit:
            obj.save()
        return obj


class ProductForm(forms.ModelForm):
    sku = forms.CharField(max_length=64)
    stock_quantity = forms.IntegerField(min_value=0)
    low_stock_alert = forms.IntegerField(min_value=0, initial=5)
    variant_names = forms.MultipleChoiceField(choices=VARIANT_CHOICES, required=False)
    shipping_class = forms.ChoiceField(choices=(("standard", "Standard Shipping"), ("fragile", "Fragile / Handle with care"), ("free", "Free Shipping")), required=False)
    warranty = forms.ChoiceField(choices=(("", "No warranty"), ("7 days", "7 Days"), ("1 month", "1 Month"), ("3 months", "3 Months"), ("6 months", "6 Months"), ("1 year", "1 Year")), required=False)

    class Meta:
        model = Product
        fields = ("name", "slug", "category", "brand", "short_name", "subtitle", "short_description", "description", "regular_price", "sale_price", "weight", "shipping_class", "warranty", "status", "is_featured", "is_new_arrival", "meta_title", "meta_description", "badge", "detail_badge")
        widgets = {"short_description": forms.Textarea(attrs={"rows": 3, "maxlength": 300}), "description": forms.Textarea(attrs={"rows": 8}), "meta_description": forms.Textarea(attrs={"rows": 4, "maxlength": 500})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False
        self.fields["category"].queryset = Category.objects.filter(is_active=True).order_by("name")
        self.fields["brand"].queryset = Brand.objects.filter(is_active=True).order_by("name")
        for name in ("shipping_class", "warranty", "short_name", "subtitle", "short_description", "description", "sale_price", "weight", "meta_title", "meta_description", "badge", "detail_badge"):
            self.fields[name].required = False
        if not (self.instance and self.instance.pk):
            self.fields["variant_names"].initial = ["White"]
            self.fields["stock_quantity"].initial = 0
            self.fields["low_stock_alert"].initial = 5
        if self.instance and self.instance.pk:
            variants = list(self.instance.variants.all())
            default = next((v for v in variants if v.is_default), variants[0] if variants else None)
            if default:
                self.fields["sku"].initial = default.sku
                self.fields["stock_quantity"].initial = default.stock_quantity
                self.fields["low_stock_alert"].initial = default.low_stock_alert
            self.fields["variant_names"].initial = [v.name for v in variants if v.name in dict(VARIANT_CHOICES)]

    def clean_slug(self):
        base = slugify(self.cleaned_data.get("slug") or self.cleaned_data.get("name"))
        if not base:
            raise ValidationError("Enter a valid product slug.")
        qs = Product.objects.exclude(pk=self.instance.pk if self.instance else None)
        if qs.filter(slug=base).exists():
            raise ValidationError("A product with this slug already exists.")
        return base

    def clean_sku(self):
        sku = self.cleaned_data["sku"].strip()
        qs = ProductVariant.objects.filter(sku__iexact=sku)
        if self.instance and self.instance.pk:
            qs = qs.exclude(product=self.instance)
        if qs.exists():
            raise ValidationError("A product variant with this SKU already exists.")
        return sku

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

    def _save_variants(self, product):
        selected = list(self.cleaned_data.get("variant_names") or [])
        existing = list(product.variants.all())
        current_default = next((v for v in existing if v.is_default), existing[0] if existing else None)
        if not selected:
            selected = [current_default.name if current_default else "Default"]
        base_sku = self.cleaned_data["sku"]
        stock = self.cleaned_data["stock_quantity"]
        low_stock = self.cleaned_data["low_stock_alert"]
        symbols = {"White": "⚪", "Black": "⚫", "Blue": "🔵", "Pink": "🩷", "Default": ""}
        existing_by_name = {v.name: v for v in existing}
        if self.cleaned_data.get("variant_names"):
            product.variants.exclude(name__in=selected).delete()
        for index, name in enumerate(selected):
            variant = existing_by_name.get(name) or ProductVariant(product=product, name=name)
            candidate_sku = base_sku if index == 0 else f"{base_sku}-{index + 1}"
            if variant.pk is None or variant.sku != candidate_sku:
                candidate_sku = _unique_value(ProductVariant, "sku", candidate_sku, variant.pk, 64)
            variant.sku = candidate_sku
            variant.symbol = symbols.get(name, "")
            variant.stock_quantity = stock if index == 0 else variant.stock_quantity or 0
            variant.low_stock_alert = low_stock
            variant.is_default = index == 0
            variant.is_active = True
            variant.save()
        product.variants.exclude(name__in=selected).update(is_default=False)

    def save(self, commit=True):
        product = super().save(commit=False)
        self._ensure_public_id(product)
        if not product.short_name:
            product.short_name = product.name
        if not product.short_description:
            product.short_description = product.description[:300]
        if not product.description_paragraphs and product.description:
            product.description_paragraphs = [product.description]
        if not product.detail_badge:
            product.detail_badge = product.badge
        if commit:
            product.save()
            self._save_variants(product)
        return product
