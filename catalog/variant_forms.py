from django import forms
from django.core.exceptions import ValidationError

from .models import (
    Product,
    ProductOption,
    ProductOptionValue,
    ProductVariant,
    ProductVariantOptionValue,
)


class OptionValueMultipleChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        symbol = f"{obj.symbol} " if obj.symbol else ""
        return f"{obj.option.name} — {symbol}{obj.value}"


class ProductOptionForm(forms.ModelForm):
    class Meta:
        model = ProductOption
        fields = ("product", "name", "sort_order")

    def __init__(self, *args, **kwargs):
        product_id = kwargs.pop("product_id", None)
        super().__init__(*args, **kwargs)
        self.fields["product"].queryset = Product.objects.order_by("name")
        if product_id:
            self.fields["product"].initial = product_id

    def clean_name(self):
        name = (self.cleaned_data.get("name") or "").strip()
        if not name:
            raise ValidationError("Option name is required.")
        return name

    def clean(self):
        cleaned = super().clean()
        product = cleaned.get("product")
        name = cleaned.get("name")
        if product and name:
            qs = ProductOption.objects.filter(product=product, name__iexact=name)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error("name", "This product already has an option with this name.")
        return cleaned


class ProductOptionValueForm(forms.ModelForm):
    class Meta:
        model = ProductOptionValue
        fields = ("option", "value", "symbol", "sort_order")

    def __init__(self, *args, **kwargs):
        product_id = kwargs.pop("product_id", None)
        super().__init__(*args, **kwargs)
        qs = ProductOption.objects.select_related("product").order_by("product__name", "sort_order", "id")
        if product_id:
            qs = qs.filter(product_id=product_id)
        self.fields["option"].queryset = qs
        self.fields["symbol"].required = False

    def clean_value(self):
        value = (self.cleaned_data.get("value") or "").strip()
        if not value:
            raise ValidationError("Option value is required.")
        return value

    def clean(self):
        cleaned = super().clean()
        option = cleaned.get("option")
        value = cleaned.get("value")
        if option and value:
            qs = ProductOptionValue.objects.filter(option=option, value__iexact=value)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error("value", "This option already has this value.")
        return cleaned


class StructuredProductVariantForm(forms.ModelForm):
    option_values = OptionValueMultipleChoiceField(
        queryset=ProductOptionValue.objects.none(),
        required=False,
        label="Option values",
        help_text="Choose one value from each option. Leave empty only for a legacy/default variant.",
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
        if product_id:
            self.fields["product"].initial = product_id
            self.fields["option_values"].queryset = ProductOptionValue.objects.filter(
                option__product_id=product_id
            ).select_related("option").order_by("option__sort_order", "option_id", "sort_order", "id")

        if self.instance and self.instance.pk:
            self.fields["option_values"].initial = list(
                self.instance.option_selections.values_list("value_id", flat=True)
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
        selected_values = list(cleaned.get("option_values") or [])

        if cleaned.get("is_default") and not cleaned.get("is_active"):
            self.add_error("is_active", "The default variant must stay active.")

        regular = cleaned.get("regular_price_override")
        selling = cleaned.get("price_override")
        if regular is not None and selling is not None and selling > regular:
            self.add_error("price_override", "Selling price override cannot exceed regular price override.")

        generated_name = ""
        if product and selected_values:
            option_ids = set()
            for value in selected_values:
                if value.option.product_id != product.pk:
                    self.add_error("option_values", "Every selected value must belong to the selected product.")
                    continue
                if value.option_id in option_ids:
                    self.add_error("option_values", f"Choose only one value for {value.option.name}.")
                option_ids.add(value.option_id)

            expected_options = list(product.options.order_by("sort_order", "id"))
            if len(option_ids) != len(expected_options):
                missing = [option.name for option in expected_options if option.pk not in option_ids]
                if missing:
                    self.add_error(
                        "option_values",
                        "Choose one value for every product option: " + ", ".join(missing) + ".",
                    )

            ordered_values = sorted(
                selected_values,
                key=lambda item: (item.option.sort_order, item.option_id, item.sort_order, item.id),
            )
            generated_name = " / ".join(item.value for item in ordered_values)
            cleaned["name"] = generated_name[:120]
        else:
            manual_name = (cleaned.get("name") or "").strip()
            if not manual_name:
                self.add_error("name", "Enter a variant name or choose structured option values.")
            cleaned["name"] = manual_name[:120]

        if product and cleaned.get("name"):
            qs = ProductVariant.objects.filter(product=product, name__iexact=cleaned["name"])
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error("option_values" if generated_name else "name", "This product already has this variant combination.")
        return cleaned

    def save(self, commit=True):
        variant = super().save(commit=False)
        variant.name = self.cleaned_data["name"]
        selected_values = list(self.cleaned_data.get("option_values") or [])
        if not variant.symbol and selected_values:
            variant.symbol = next((item.symbol for item in selected_values if item.symbol), "")
        if commit:
            variant.save()
            self.save_option_selections(variant)
        return variant

    def save_option_selections(self, variant):
        selected_values = list(self.cleaned_data.get("option_values") or [])
        ProductVariantOptionValue.objects.filter(variant=variant).delete()
        for value in selected_values:
            ProductVariantOptionValue.objects.create(
                variant=variant,
                option=value.option,
                value=value,
            )
