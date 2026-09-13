import re

from django import forms
from django.core.exceptions import ValidationError
from django.utils.text import slugify

from .models import (
    Product,
    ProductVariant,
    ProductVariantValue,
    VariantAttribute,
    VariantAttributeValue,
    VariantPreset,
    VariantPresetAttribute,
)
from .variant_services import combination_signature, ordered_values, variant_name


class AttributeValueMultipleChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        symbol = f"{obj.symbol} " if obj.symbol else ""
        return f"{obj.attribute.name} — {symbol}{obj.value}"


class VariantAttributeForm(forms.ModelForm):
    class Meta:
        model = VariantAttribute
        fields = ("name", "code", "display_type", "is_active", "sort_order")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["code"].required = False
        if self.instance and self.instance.pk:
            self.fields["code"].disabled = True
            self.fields["code"].help_text = "Stable internal code. Rename the display name without changing this code."

    def clean_name(self):
        name = " ".join((self.cleaned_data.get("name") or "").split())
        if not name:
            raise ValidationError("Attribute name is required.")
        qs = VariantAttribute.objects.filter(name__iexact=name)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("An attribute with this name already exists.")
        return name

    def clean_code(self):
        if self.instance and self.instance.pk:
            return self.instance.code
        code = slugify(self.cleaned_data.get("code") or self.cleaned_data.get("name"))[:80]
        if not code:
            raise ValidationError("Enter a valid attribute code.")
        if VariantAttribute.objects.filter(code__iexact=code).exists():
            raise ValidationError("This attribute code already exists.")
        return code


class VariantAttributeValueForm(forms.ModelForm):
    class Meta:
        model = VariantAttributeValue
        fields = ("attribute", "value", "code", "symbol", "color_hex", "is_active", "sort_order")

    def __init__(self, *args, **kwargs):
        attribute_id = kwargs.pop("attribute_id", None)
        super().__init__(*args, **kwargs)
        self.fields["attribute"].queryset = VariantAttribute.objects.order_by("sort_order", "name")
        self.fields["code"].required = False
        self.fields["symbol"].required = False
        self.fields["color_hex"].required = False
        if self.instance and self.instance.pk:
            self.fields["attribute"].disabled = True
            self.fields["code"].disabled = True
            self.fields["code"].help_text = "Stable internal value code. The display value can be renamed safely."
        elif attribute_id:
            self.fields["attribute"].initial = attribute_id

    def clean_value(self):
        value = " ".join((self.cleaned_data.get("value") or "").split())
        if not value:
            raise ValidationError("Attribute value is required.")
        return value

    def clean_code(self):
        if self.instance and self.instance.pk:
            return self.instance.code
        return slugify(self.cleaned_data.get("code") or self.cleaned_data.get("value"))[:80]

    def clean_color_hex(self):
        value = (self.cleaned_data.get("color_hex") or "").strip().upper()
        if value and not re.fullmatch(r"#[0-9A-F]{6}(?:[0-9A-F]{2})?", value):
            raise ValidationError("Use a hex color such as #1D4ED8.")
        return value

    def clean(self):
        cleaned = super().clean()
        attribute = cleaned.get("attribute") or (self.instance.attribute if self.instance and self.instance.pk else None)
        value = cleaned.get("value")
        code = cleaned.get("code")
        if attribute and value:
            qs = VariantAttributeValue.objects.filter(attribute=attribute, value__iexact=value)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error("value", "This attribute already has that value.")
        if attribute and code:
            qs = VariantAttributeValue.objects.filter(attribute=attribute, code__iexact=code)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error("code", "This attribute already has that internal code.")
        return cleaned


class VariantPresetForm(forms.ModelForm):
    attributes = forms.ModelMultipleChoiceField(
        queryset=VariantAttribute.objects.none(),
        required=True,
        help_text="Choose the reusable attributes included in this preset.",
    )

    class Meta:
        model = VariantPreset
        fields = ("name", "code", "is_active", "sort_order")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["code"].required = False
        self.fields["attributes"].queryset = VariantAttribute.objects.filter(is_active=True).order_by("sort_order", "name")
        if self.instance and self.instance.pk:
            self.fields["code"].disabled = True
            self.fields["attributes"].initial = self.instance.attribute_links.values_list("attribute_id", flat=True)

    def clean_name(self):
        name = " ".join((self.cleaned_data.get("name") or "").split())
        qs = VariantPreset.objects.filter(name__iexact=name)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("A preset with this name already exists.")
        return name

    def clean_code(self):
        if self.instance and self.instance.pk:
            return self.instance.code
        code = slugify(self.cleaned_data.get("code") or self.cleaned_data.get("name"))[:120]
        if not code:
            raise ValidationError("Enter a valid preset code.")
        if VariantPreset.objects.filter(code__iexact=code).exists():
            raise ValidationError("This preset code already exists.")
        return code

    def save(self, commit=True):
        preset = super().save(commit=commit)
        if commit:
            VariantPresetAttribute.objects.filter(preset=preset).delete()
            VariantPresetAttribute.objects.bulk_create(
                [
                    VariantPresetAttribute(preset=preset, attribute=attribute, sort_order=index)
                    for index, attribute in enumerate(self.cleaned_data["attributes"])
                ]
            )
        return preset


class StructuredProductVariantForm(forms.ModelForm):
    attribute_values = AttributeValueMultipleChoiceField(
        queryset=VariantAttributeValue.objects.none(),
        required=False,
        label="Attribute values",
        help_text="Choose one value from each attribute used by this product. Leave empty only for a simple/legacy SKU.",
    )

    class Meta:
        model = ProductVariant
        fields = (
            "product",
            "name",
            "sku",
            "barcode",
            "symbol",
            "regular_price_override",
            "price_override",
            "stock_quantity",
            "low_stock_alert",
            "is_default",
            "is_active",
        )
        labels = {
            "price_override": "Selling price override",
            "regular_price_override": "Regular price override",
            "symbol": "Display symbol / color emoji",
        }

    def __init__(self, *args, **kwargs):
        product_id = kwargs.pop("product_id", None)
        super().__init__(*args, **kwargs)
        self.fields["product"].queryset = Product.objects.order_by("name")
        self.fields["name"].required = False
        self.fields["barcode"].required = False
        self.fields["symbol"].required = False
        self.fields["regular_price_override"].required = False
        self.fields["price_override"].required = False

        if self.instance and self.instance.pk:
            product_id = self.instance.product_id
            self.fields["product"].disabled = True
        elif not product_id:
            raw_product = self.data.get("product") if self.is_bound else None
            if str(raw_product or "").isdigit():
                product_id = int(raw_product)

        attribute_ids = []
        if product_id:
            self.fields["product"].initial = product_id
            attribute_ids = list(
                VariantAttribute.objects.filter(
                    values__variant_links__variant__product_id=product_id,
                ).distinct().values_list("id", flat=True)
            )
            value_qs = VariantAttributeValue.objects.filter(is_active=True, attribute__is_active=True)
            if attribute_ids:
                value_qs = value_qs.filter(attribute_id__in=attribute_ids)
            self.fields["attribute_values"].queryset = value_qs.select_related("attribute").order_by(
                "attribute__sort_order", "attribute_id", "sort_order", "id"
            )

        self.product_attribute_ids = attribute_ids
        if self.instance and self.instance.pk:
            self.fields["attribute_values"].initial = list(
                self.instance.variant_values.values_list("value_id", flat=True)
            )

    def clean_sku(self):
        sku = (self.cleaned_data.get("sku") or "").strip()
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
        product = cleaned.get("product") or (self.instance.product if self.instance and self.instance.pk else None)
        selected_values = list(cleaned.get("attribute_values") or [])

        if cleaned.get("is_default") and not cleaned.get("is_active"):
            self.add_error("is_active", "The default variant must stay active.")

        regular = cleaned.get("regular_price_override")
        selling = cleaned.get("price_override")
        if regular is not None and selling is not None and selling > regular:
            self.add_error("price_override", "Selling price override cannot exceed regular price override.")

        generated_name = ""
        if product and selected_values:
            selected_attribute_ids = []
            seen_attributes = set()
            for value in selected_values:
                if value.attribute_id in seen_attributes:
                    self.add_error("attribute_values", f"Choose only one value for {value.attribute.name}.")
                seen_attributes.add(value.attribute_id)
                selected_attribute_ids.append(value.attribute_id)

            expected_ids = set(self.product_attribute_ids)
            if expected_ids and set(selected_attribute_ids) != expected_ids:
                missing = list(
                    VariantAttribute.objects.filter(pk__in=expected_ids - set(selected_attribute_ids))
                    .order_by("sort_order", "name")
                    .values_list("name", flat=True)
                )
                if missing:
                    self.add_error(
                        "attribute_values",
                        "Choose one value for every product attribute: " + ", ".join(missing) + ".",
                    )

            generated_name = variant_name(selected_values)
            cleaned["name"] = generated_name

            signature = combination_signature(selected_values)
            candidates = ProductVariant.objects.filter(product=product).prefetch_related("variant_values")
            if self.instance and self.instance.pk:
                candidates = candidates.exclude(pk=self.instance.pk)
            for candidate in candidates:
                candidate_signature = tuple(sorted(candidate.variant_values.values_list("value_id", flat=True)))
                if candidate_signature and candidate_signature == signature:
                    self.add_error("attribute_values", "This product already has this exact variant combination.")
                    break
        else:
            manual_name = (cleaned.get("name") or "").strip()
            if not manual_name:
                self.add_error("name", "Enter a variant name or choose structured attribute values.")
            cleaned["name"] = manual_name[:120]

        if product and cleaned.get("name"):
            qs = ProductVariant.objects.filter(product=product, name__iexact=cleaned["name"])
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error("attribute_values" if generated_name else "name", "This product already has this variant name.")
        return cleaned

    def save(self, commit=True):
        variant = super().save(commit=False)
        variant.name = self.cleaned_data["name"]
        selected_values = list(self.cleaned_data.get("attribute_values") or [])
        if not variant.symbol and selected_values:
            variant.symbol = next((item.symbol for item in ordered_values(selected_values) if item.symbol), "")[:16]
        if commit:
            variant.save()
            self.save_attribute_values(variant)
        return variant

    def save_attribute_values(self, variant):
        selected_values = list(self.cleaned_data.get("attribute_values") or [])
        ProductVariantValue.objects.filter(variant=variant).delete()
        for value in ordered_values(selected_values):
            ProductVariantValue.objects.create(variant=variant, value=value)
