from decimal import Decimal

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalog.models import (
    Product,
    VariantAttribute,
    VariantAttributeValue,
    VariantPreset,
    VariantPresetAttribute,
)
from catalog.variant_services import generate_variant_combinations, variant_usage_reasons
from storefront import mock_data


ATTRIBUTE_DEFINITIONS = {
    "Color": {
        "code": "color",
        "display_type": "swatch",
        "values": [
            ("Black", "black", "⚫", "#111111"),
            ("White", "white", "⚪", "#FFFFFF"),
            ("Blue", "blue", "🔵", "#2563EB"),
            ("Pink", "pink", "🩷", "#EC4899"),
            ("Silver", "silver", "", "#C0C0C0"),
            ("Graphite", "graphite", "", "#4B5563"),
            ("Red", "red", "🔴", "#DC2626"),
        ],
    },
    "Storage": {
        "code": "storage",
        "display_type": "button",
        "values": [("128GB", "128gb", "", ""), ("256GB", "256gb", "", ""), ("512GB", "512gb", "", ""), ("1TB", "1tb", "", "")],
    },
    "Region / Type": {
        "code": "region",
        "display_type": "button",
        "values": [("USA", "usa", "", ""), ("Japan", "japan", "", ""), ("AUS", "aus", "", ""), ("SGP", "sgp", "", "")],
    },
    "RAM": {
        "code": "ram",
        "display_type": "button",
        "values": [("8GB", "8gb", "", ""), ("12GB", "12gb", "", ""), ("16GB", "16gb", "", "")],
    },
    "Size": {
        "code": "size",
        "display_type": "button",
        "values": [("Small", "small", "", ""), ("Medium", "medium", "", ""), ("Large", "large", "", "")],
    },
    "Capacity": {
        "code": "capacity",
        "display_type": "button",
        "values": [("10000mAh", "10000mah", "", ""), ("20000mAh", "20000mah", "", "")],
    },
    "Plug Type": {
        "code": "plug-type",
        "display_type": "button",
        "values": [("US", "us", "", ""), ("EU", "eu", "", ""), ("UK", "uk", "", "")],
    },
    "Length": {
        "code": "length",
        "display_type": "button",
        "values": [("1m", "1m", "", ""), ("2m", "2m", "", ""), ("3m", "3m", "", "")],
    },
}

PRESET_DEFINITIONS = {
    "Smartphone": ["Color", "Storage", "Region / Type", "RAM"],
    "Laptop": ["Color", "RAM", "Storage"],
    "TWS / Earbuds": ["Color"],
    "Headphones": ["Color"],
    "Smartwatch": ["Color", "Size"],
    "Power Bank": ["Color", "Capacity"],
    "Charger": ["Color", "Plug Type"],
    "Cable": ["Color", "Length"],
    "Speaker": ["Color"],
}

DEMO_CONFIG = {
    "baseus": {"Color": ["White", "Black", "Pink", "Blue"]},
    "q20i": {"Color": ["Black", "Blue"]},
    "haylou": {"Color": ["Black", "Silver"]},
    "jbl": {"Color": ["Black", "Blue", "Red"]},
    "xiaomi": {"Color": ["Black", "White"]},
    "anker": {"Color": ["White", "Black"], "Plug Type": ["US", "EU"]},
    "ugreen": {"Color": ["Black"], "Length": ["1m", "2m", "3m"]},
    "budsfe": {"Color": ["White", "Graphite"]},
    "neckband": {"Color": ["Black", "Blue"]},
    "amazfit": {"Color": ["Black", "Pink"]},
}


class Command(BaseCommand):
    help = "Seed the reusable global variant library, presets and 10 realistic TechBari demo product configurations."

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-seed-catalog",
            action="store_true",
            help="Do not seed the existing demo catalog when the catalog is empty.",
        )

    def _attribute_library(self):
        attributes = {}
        values = {}
        for attr_index, (name, definition) in enumerate(ATTRIBUTE_DEFINITIONS.items()):
            attribute, created = VariantAttribute.objects.get_or_create(
                code=definition["code"],
                defaults={
                    "name": name,
                    "display_type": definition["display_type"],
                    "is_active": True,
                    "sort_order": attr_index,
                },
            )
            if created:
                pass
            else:
                changed = False
                if not attribute.is_active:
                    attribute.is_active = True
                    changed = True
                if changed:
                    attribute.save(update_fields=["is_active", "updated_at"])
            attributes[name] = attribute
            for value_index, (label, code, symbol, color_hex) in enumerate(definition["values"]):
                value, value_created = VariantAttributeValue.objects.get_or_create(
                    attribute=attribute,
                    code=code,
                    defaults={
                        "value": label,
                        "symbol": symbol,
                        "color_hex": color_hex,
                        "is_active": True,
                        "sort_order": value_index,
                    },
                )
                if not value_created:
                    updates = []
                    if not value.is_active:
                        value.is_active = True
                        updates.append("is_active")
                    if not value.symbol and symbol:
                        value.symbol = symbol
                        updates.append("symbol")
                    if not value.color_hex and color_hex:
                        value.color_hex = color_hex
                        updates.append("color_hex")
                    if updates:
                        updates.append("updated_at")
                        value.save(update_fields=updates)
                values[(name, label)] = value
        return attributes, values

    def _presets(self, attributes):
        for index, (name, attribute_names) in enumerate(PRESET_DEFINITIONS.items()):
            code = name.lower().replace(" / ", "-").replace(" ", "-")
            preset, _ = VariantPreset.objects.get_or_create(
                code=code,
                defaults={"name": name, "is_active": True, "sort_order": index},
            )
            if not preset.is_active:
                preset.is_active = True
                preset.save(update_fields=["is_active", "updated_at"])
            expected = [attributes[name] for name in attribute_names if name in attributes]
            existing_ids = list(preset.attribute_links.order_by("sort_order", "id").values_list("attribute_id", flat=True))
            expected_ids = [attribute.pk for attribute in expected]
            if existing_ids != expected_ids:
                preset.attribute_links.all().delete()
                VariantPresetAttribute.objects.bulk_create(
                    [
                        VariantPresetAttribute(preset=preset, attribute=attribute, sort_order=sort_order)
                        for sort_order, attribute in enumerate(expected)
                    ]
                )

    def _seed_product_variants(self, product, config, values, demo_index):
        selected_values = []
        for attribute_name, labels in config.items():
            for label in labels:
                selected_values.append(values[(attribute_name, label)])
        result = generate_variant_combinations(
            product=product,
            value_ids=[value.pk for value in selected_values],
        )

        selected_ids = {value.pk for value in selected_values}
        expected_attribute_count = len(config)
        variants = list(product.variants.prefetch_related("variant_values__value").order_by("id"))
        demo_variants = []
        for variant in variants:
            links = list(variant.variant_values.all())
            value_ids = {link.value_id for link in links}
            if len(links) == expected_attribute_count and value_ids.issubset(selected_ids):
                demo_variants.append(variant)

        for index, variant in enumerate(demo_variants):
            if variant_usage_reasons(variant):
                continue
            base_price = Decimal(product.current_price)
            price_step = Decimal("150.00") * Decimal(index)
            selling = base_price + price_step
            regular = max(Decimal(product.regular_price), selling)
            variant.price_override = selling
            variant.regular_price_override = regular
            variant.stock_quantity = 4 + ((demo_index + index) % 12)
            variant.low_stock_alert = 3
            variant.is_active = True
            variant.save()
        return result, len(demo_variants)

    @transaction.atomic
    def handle(self, *args, **options):
        if not Product.objects.exists():
            if options["no_seed_catalog"]:
                raise CommandError("Catalog is empty. Run python manage.py seed_catalog first.")
            call_command("seed_catalog")

        attributes, values = self._attribute_library()
        self._presets(attributes)

        configured_products = 0
        configured_variants = 0
        created_total = reused_total = skipped_total = 0
        missing_products = []

        demo_rows = list(mock_data.PRODUCTS)[:10]
        for demo_index, row in enumerate(demo_rows):
            config = DEMO_CONFIG.get(row["id"])
            if not config:
                continue
            try:
                product = Product.objects.get(public_id=row["id"])
            except Product.DoesNotExist:
                missing_products.append(row["id"])
                continue
            result, variant_count = self._seed_product_variants(product, config, values, demo_index)
            configured_products += 1
            configured_variants += variant_count
            created_total += result["created"]
            reused_total += result["reused"]
            skipped_total += result["skipped"]

        self.stdout.write(
            self.style.SUCCESS(
                "Global variant demo ready: "
                f"{len(attributes)} reusable attributes, {len(PRESET_DEFINITIONS)} presets, "
                f"{configured_products} demo products, {configured_variants} configured SKU combinations."
            )
        )
        self.stdout.write(
            f"Generator result: {created_total} created, {reused_total} safe existing SKUs reused, {skipped_total} existing combinations skipped."
        )
        self.stdout.write(
            "The demo products keep the existing local branded product images already stored in static/store/images; no runtime image hotlinks are required."
        )
        if missing_products:
            self.stdout.write(
                self.style.WARNING(
                    "Skipped missing demo products: " + ", ".join(missing_products) + ". Run python manage.py seed_catalog first if needed."
                )
            )
