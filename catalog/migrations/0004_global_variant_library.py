from django.db import migrations, models
import django.db.models.deletion
from django.utils.text import slugify


def _unique_code(model, base, *, scope=None, max_length=80):
    base = (slugify(base) or "item")[:max_length]
    candidate = base
    suffix = 2
    qs = model.objects.all()
    if scope:
        qs = qs.filter(**scope)
    while qs.filter(code=candidate).exists():
        tail = f"-{suffix}"
        candidate = f"{base[: max_length - len(tail)]}{tail}"
        suffix += 1
    return candidate


def migrate_product_options_to_global_library(apps, schema_editor):
    ProductOption = apps.get_model("catalog", "ProductOption")
    ProductOptionValue = apps.get_model("catalog", "ProductOptionValue")
    ProductVariantOptionValue = apps.get_model("catalog", "ProductVariantOptionValue")
    VariantAttribute = apps.get_model("catalog", "VariantAttribute")
    VariantAttributeValue = apps.get_model("catalog", "VariantAttributeValue")
    ProductVariantValue = apps.get_model("catalog", "ProductVariantValue")

    option_to_attribute = {}
    value_to_global = {}

    for option in ProductOption.objects.order_by("sort_order", "id"):
        name = (option.name or "Variant").strip() or "Variant"
        attribute = VariantAttribute.objects.filter(name__iexact=name).first()
        if attribute is None:
            display_type = "swatch" if any(token in name.casefold() for token in ("color", "colour", "finish")) else "button"
            attribute = VariantAttribute.objects.create(
                name=name,
                code=_unique_code(VariantAttribute, name),
                display_type=display_type,
                is_active=True,
                sort_order=option.sort_order,
            )
        option_to_attribute[option.pk] = attribute.pk

    for old_value in ProductOptionValue.objects.select_related("option").order_by("sort_order", "id"):
        attribute_id = option_to_attribute.get(old_value.option_id)
        if not attribute_id:
            continue
        value_text = (old_value.value or "Value").strip() or "Value"
        value = VariantAttributeValue.objects.filter(
            attribute_id=attribute_id,
            value__iexact=value_text,
        ).first()
        if value is None:
            value = VariantAttributeValue.objects.create(
                attribute_id=attribute_id,
                value=value_text,
                code=_unique_code(
                    VariantAttributeValue,
                    value_text,
                    scope={"attribute_id": attribute_id},
                    max_length=80,
                ),
                symbol=old_value.symbol or "",
                color_hex="",
                is_active=True,
                sort_order=old_value.sort_order,
            )
        elif not value.symbol and old_value.symbol:
            value.symbol = old_value.symbol
            value.save(update_fields=["symbol"])
        value_to_global[old_value.pk] = value.pk

    for link in ProductVariantOptionValue.objects.order_by("variant_id", "id"):
        global_value_id = value_to_global.get(link.value_id)
        if global_value_id:
            ProductVariantValue.objects.get_or_create(
                variant_id=link.variant_id,
                value_id=global_value_id,
            )


def noop_reverse(apps, schema_editor):
    # This migration intentionally retires the temporary per-product option tables.
    # Existing ProductVariant identities remain unchanged, but recreating the old
    # per-product rows would duplicate the new global source of truth.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0003_product_variant_options"),
    ]

    operations = [
        migrations.CreateModel(
            name="VariantAttribute",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=80)),
                ("code", models.SlugField(max_length=80, unique=True)),
                ("display_type", models.CharField(choices=[("swatch", "Color Swatch"), ("button", "Button"), ("dropdown", "Dropdown")], default="button", max_length=16)),
                ("is_active", models.BooleanField(default=True)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ("sort_order", "name", "id")},
        ),
        migrations.CreateModel(
            name="VariantPreset",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, unique=True)),
                ("code", models.SlugField(max_length=120, unique=True)),
                ("is_active", models.BooleanField(default=True)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ("sort_order", "name", "id")},
        ),
        migrations.CreateModel(
            name="VariantAttributeValue",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("value", models.CharField(max_length=120)),
                ("code", models.SlugField(max_length=80)),
                ("symbol", models.CharField(blank=True, max_length=32)),
                ("color_hex", models.CharField(blank=True, max_length=9)),
                ("is_active", models.BooleanField(default=True)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("attribute", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="values", to="catalog.variantattribute")),
            ],
            options={"ordering": ("attribute_id", "sort_order", "value", "id")},
        ),
        migrations.CreateModel(
            name="VariantPresetAttribute",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("attribute", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="preset_links", to="catalog.variantattribute")),
                ("preset", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="attribute_links", to="catalog.variantpreset")),
            ],
            options={"ordering": ("preset_id", "sort_order", "id")},
        ),
        migrations.CreateModel(
            name="ProductVariantValue",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("value", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="variant_links", to="catalog.variantattributevalue")),
                ("variant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="variant_values", to="catalog.productvariant")),
            ],
            options={"ordering": ("value__attribute__sort_order", "value__sort_order", "id")},
        ),
        migrations.AddField(
            model_name="productimage",
            name="attribute_value",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="product_images", to="catalog.variantattributevalue"),
        ),
        migrations.AddConstraint(
            model_name="variantattribute",
            constraint=models.UniqueConstraint(fields=("name",), name="uniq_variant_attribute_name"),
        ),
        migrations.AddIndex(
            model_name="variantattribute",
            index=models.Index(fields=["is_active", "sort_order"], name="cat_attr_active_sort_idx"),
        ),
        migrations.AddConstraint(
            model_name="variantattributevalue",
            constraint=models.UniqueConstraint(fields=("attribute", "value"), name="uniq_variant_attr_value"),
        ),
        migrations.AddConstraint(
            model_name="variantattributevalue",
            constraint=models.UniqueConstraint(fields=("attribute", "code"), name="uniq_variant_attr_code"),
        ),
        migrations.AddIndex(
            model_name="variantattributevalue",
            index=models.Index(fields=["attribute", "is_active", "sort_order"], name="cat_attrval_active_idx"),
        ),
        migrations.AddConstraint(
            model_name="variantpresetattribute",
            constraint=models.UniqueConstraint(fields=("preset", "attribute"), name="uniq_preset_attribute"),
        ),
        migrations.AddConstraint(
            model_name="productvariantvalue",
            constraint=models.UniqueConstraint(fields=("variant", "value"), name="uniq_variant_global_value"),
        ),
        migrations.AddIndex(
            model_name="productvariantvalue",
            index=models.Index(fields=["variant", "value"], name="cat_varvalue_idx"),
        ),
        migrations.RunPython(migrate_product_options_to_global_library, noop_reverse),
        migrations.DeleteModel(name="ProductVariantOptionValue"),
        migrations.DeleteModel(name="ProductOptionValue"),
        migrations.DeleteModel(name="ProductOption"),
    ]
