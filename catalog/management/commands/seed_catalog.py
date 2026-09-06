from decimal import Decimal
import re

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from catalog.models import Brand, Category, Product, ProductImage, ProductSpecification, ProductVariant
from storefront import mock_data

SYMBOLS = {"White": "⚪", "Black": "⚫", "Blue": "🔵", "Pink": "🩷"}


def sku_for(public_id, index=0):
    clean = re.sub(r"[^A-Z0-9]", "", public_id.upper())[:10] or "ITEM"
    base = f"TB-{clean}-001"
    return base if index == 0 else f"{base}-{index + 1}"


class Command(BaseCommand):
    help = "Seed the TechBari catalog database from the original static storefront fixtures."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete existing catalog products/categories/brands before seeding.")

    @transaction.atomic
    def handle(self, *args, **options):
        if options["reset"]:
            Product.objects.all().delete()
            Category.objects.all().delete()
            Brand.objects.all().delete()

        category_meta = {row["name"]: row for row in getattr(mock_data, "CATEGORIES", [])}
        brand_meta = {row["name"]: row for row in getattr(mock_data, "BRANDS", [])}
        product_rows = list(mock_data.PRODUCTS)
        category_names, brand_names = [], []
        for row in product_rows:
            if row["category"] not in category_names:
                category_names.append(row["category"])
            if row["brand"] not in brand_names:
                brand_names.append(row["brand"])

        categories = {}
        for index, name in enumerate(category_names):
            meta = category_meta.get(name, {})
            category, _ = Category.objects.update_or_create(
                slug=slugify(name),
                defaults={"name": name, "description": meta.get("description", ""), "static_image_path": meta.get("image", ""), "is_active": True, "sort_order": index},
            )
            categories[name] = category

        brands = {}
        for index, name in enumerate(brand_names):
            meta = brand_meta.get(name, {})
            brand, _ = Brand.objects.update_or_create(
                slug=slugify(name),
                defaults={"name": name, "description": meta.get("description", ""), "static_image_path": meta.get("image", ""), "is_featured": index < 6, "is_active": True, "sort_order": index},
            )
            brands[name] = brand

        created = updated = 0
        for index, row in enumerate(product_rows):
            regular_price = Decimal(str(row.get("regular_price") or row["price"]))
            current_price = Decimal(str(row["price"]))
            sale_price = current_price if current_price < regular_price else None
            defaults = {
                "name": row["name"], "slug": row["slug"], "category": categories[row["category"]], "brand": brands[row["brand"]],
                "short_name": row.get("short_name") or row["name"], "subtitle": row.get("subtitle", ""),
                "short_description": row.get("description", "")[:300], "description": row.get("description", ""),
                "regular_price": regular_price, "sale_price": sale_price,
                "badge": row.get("badge", ""), "badge_class": row.get("badge_class", "blue"),
                "detail_badge": row.get("detail_badge", row.get("badge", "")), "status": Product.Status.ACTIVE,
                "is_featured": index < 6 or row.get("badge") == "Bestseller", "is_new_arrival": row.get("badge") == "New",
                "description_paragraphs": row.get("description_paragraphs", []), "features": row.get("features", []),
                "box_contents": row.get("box_contents", []), "reviews": row.get("reviews", []), "questions": row.get("questions", []),
                "review_score": Decimal(str(row.get("review_score") or 0)), "review_count": int(row.get("review_count") or 0),
                "meta_title": row["name"][:255], "meta_description": row.get("description", "")[:500],
            }
            product, was_created = Product.objects.update_or_create(public_id=row["id"], defaults=defaults)
            created += int(was_created)
            updated += int(not was_created)

            ProductVariant.objects.filter(product=product).delete()
            variants = row.get("variants") or [{"name": row.get("variant", "Default"), "symbol": ""}]
            selected_default = row.get("variant") or variants[0].get("name", "Default")
            ordered_variants = sorted(variants, key=lambda item: item.get("name") != selected_default)
            for variant_index, variant_row in enumerate(ordered_variants):
                ProductVariant.objects.create(
                    product=product, name=variant_row.get("name") or "Default", sku=sku_for(row["id"], variant_index),
                    symbol=variant_row.get("symbol") or SYMBOLS.get(variant_row.get("name"), ""),
                    stock_quantity=int(row.get("stock", 0)) if variant_index == 0 else 0,
                    low_stock_alert=5, is_default=variant_index == 0, is_active=True,
                )

            ProductImage.objects.filter(product=product).delete()
            seen_paths = set()
            def add_static(path, role, order):
                if not path or (path, role) in seen_paths:
                    return
                seen_paths.add((path, role))
                ProductImage.objects.create(product=product, static_path=path, alt_text=row["name"], role=role, sort_order=order)

            add_static(row.get("image"), ProductImage.Role.PRIMARY, 0)
            detail_path = row.get("detail_image")
            if detail_path and detail_path != row.get("image"):
                add_static(detail_path, ProductImage.Role.DETAIL, 1)
            for image_index, image_path in enumerate(row.get("images", []), start=2):
                if image_path != row.get("image") and image_path != detail_path:
                    add_static(image_path, ProductImage.Role.GALLERY, image_index)

            ProductSpecification.objects.filter(product=product).delete()
            ProductSpecification.objects.bulk_create([
                ProductSpecification(product=product, name=spec.get("name", "Specification"), value=spec.get("value", ""), sort_order=spec_index)
                for spec_index, spec in enumerate(row.get("specifications", [])) if spec.get("name") and spec.get("value")
            ])

        self.stdout.write(self.style.SUCCESS(f"Catalog seeded: {created} products created, {updated} updated, {len(categories)} categories, {len(brands)} brands."))
