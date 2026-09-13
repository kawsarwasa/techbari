from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from catalog.models import Product, ProductOption, ProductOptionValue, ProductVariantOptionValue
from storefront import mock_data


COLOR_NAMES = {"black", "white", "blue", "pink", "green", "red", "silver", "gold", "gray", "grey", "purple"}


class Command(BaseCommand):
    help = "Ensure the first 10 TechBari demo products have structured variant options and values."

    def add_arguments(self, parser):
        parser.add_argument(
            "--seed-catalog-if-empty",
            action="store_true",
            default=True,
            help="Seed the existing storefront demo catalog first when the catalog is empty.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if not Product.objects.exists() and options["seed_catalog_if_empty"]:
            call_command("seed_catalog")

        configured_products = 0
        configured_variants = 0
        missing_products = []

        for row in list(mock_data.PRODUCTS)[:10]:
            try:
                product = Product.objects.get(public_id=row["id"])
            except Product.DoesNotExist:
                missing_products.append(row["id"])
                continue

            variant_rows = row.get("variants") or [{"name": row.get("variant", "Default"), "symbol": ""}]
            names = [(item.get("name") or "Default").strip() for item in variant_rows]
            specification_names = {
                str(item.get("name") or "").strip().lower()
                for item in row.get("specifications", [])
            }
            option_name = "Color" if "color" in specification_names or all(name.lower() in COLOR_NAMES for name in names) else "Variant"
            option, _ = ProductOption.objects.get_or_create(
                product=product,
                name=option_name,
                defaults={"sort_order": 0},
            )

            for sort_order, variant_row in enumerate(variant_rows):
                name = (variant_row.get("name") or "Default").strip()
                symbol = (variant_row.get("symbol") or "").strip()
                value, created = ProductOptionValue.objects.get_or_create(
                    option=option,
                    value=name,
                    defaults={"symbol": symbol, "sort_order": sort_order},
                )
                if not created:
                    changed = False
                    if symbol and value.symbol != symbol:
                        value.symbol = symbol
                        changed = True
                    if value.sort_order != sort_order:
                        value.sort_order = sort_order
                        changed = True
                    if changed:
                        value.save(update_fields=["symbol", "sort_order", "updated_at"])

                variant = product.variants.filter(name__iexact=name).order_by("id").first()
                if not variant:
                    continue
                ProductVariantOptionValue.objects.update_or_create(
                    variant=variant,
                    option=option,
                    defaults={"value": value},
                )
                configured_variants += 1

            configured_products += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Structured demo variants ready: {configured_products} products, {configured_variants} SKU combinations."
            )
        )
        if missing_products:
            self.stdout.write(
                self.style.WARNING(
                    "Skipped missing demo products: " + ", ".join(missing_products) + ". Run python manage.py seed_catalog first if needed."
                )
            )
