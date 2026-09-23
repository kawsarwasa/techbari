import re
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from django.contrib.staticfiles import finders
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify
from PIL import Image, ImageOps

from catalog.models import Brand, Category, Product, ProductImage, ProductSpecification, ProductVariant
from inventory.models import InventoryBalance
from inventory.services import bootstrap_variant_stock
from storefront import mock_data


DEMO_LIMIT = 10
DEMO_IMAGE_PREFIX = "[Demo gallery]"


def _sku_base(public_id):
    clean = re.sub(r"[^A-Z0-9]", "", str(public_id).upper())[:16] or "ITEM"
    return f"TB-{clean}-001"


def _available_sku(base):
    candidate = base
    suffix = 2
    while ProductVariant.objects.filter(sku__iexact=candidate).exists():
        tail = f"-{suffix}"
        candidate = f"{base[:64 - len(tail)]}{tail}"
        suffix += 1
    return candidate


def _has_business_history(variant):
    return (
        variant.stock_movements.exists()
        or variant.purchase_items.exists()
        or variant.sales_order_items.exists()
        or variant.serialized_units.exists()
    )


def _render_demo_image(source_path, mode):
    with Image.open(source_path) as source:
        image = source.convert("RGB")
        canvas_size = (1000, 1000)

        if mode == "detail":
            rendered = ImageOps.fit(
                image,
                canvas_size,
                method=Image.Resampling.LANCZOS,
                centering=(0.5, 0.45),
            )
        else:
            canvas = Image.new("RGB", canvas_size, "white")
            target = (820, 820) if mode == "gallery" else (700, 700)
            fitted = ImageOps.contain(image, target, method=Image.Resampling.LANCZOS)
            x = (canvas.width - fitted.width) // 2
            y = (canvas.height - fitted.height) // 2
            canvas.paste(fitted, (x, y))
            rendered = canvas

        output = BytesIO()
        rendered.save(output, format="WEBP", quality=90, method=6)
        return ContentFile(output.getvalue())


class Command(BaseCommand):
    help = "Insert/update 10 realistic TechBari demo products with multiple local product images and sellable stock."

    def add_arguments(self, parser):
        parser.add_argument(
            "--refresh",
            action="store_true",
            help="Refresh presentation fields, demo gallery images and specifications for the 10 demo products.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        rows = list(mock_data.PRODUCTS)[:DEMO_LIMIT]
        if len(rows) < DEMO_LIMIT:
            raise CommandError(f"Expected at least {DEMO_LIMIT} demo products in storefront.mock_data.")

        category_meta = {row["name"]: row for row in getattr(mock_data, "CATEGORIES", [])}
        created_products = 0
        updated_products = 0
        image_total = 0
        stocked_variants = 0

        for index, row in enumerate(rows):
            category_defaults = {
                "description": f"{row['category']} products and accessories.",
                "is_active": True,
                "sort_order": index,
            }
            category_source = category_meta.get(row["category"], {}).get("image", "")
            if category_source:
                category_defaults["static_image_path"] = category_source
            category, _ = Category.objects.get_or_create(
                slug=slugify(row["category"]),
                defaults={"name": row["category"], **category_defaults},
            )
            if not category.is_active:
                category.is_active = True
                category.save(update_fields=["is_active", "updated_at"])

            brand, _ = Brand.objects.get_or_create(
                slug=slugify(row["brand"]),
                defaults={
                    "name": row["brand"],
                    "description": f"{row['brand']} products available at TechBari.",
                    "is_active": True,
                    "is_featured": index < 6,
                    "sort_order": index,
                },
            )
            brand_updates = []
            if not brand.is_active:
                brand.is_active = True
                brand_updates.append("is_active")
            if index < 6 and not brand.is_featured:
                brand.is_featured = True
                brand_updates.append("is_featured")
            if brand_updates:
                brand_updates.append("updated_at")
                brand.save(update_fields=brand_updates)

            regular_price = Decimal(str(row.get("regular_price") or row["price"]))
            selling_price = Decimal(str(row["price"]))
            defaults = {
                "name": row["name"],
                "slug": row["slug"],
                "category": category,
                "brand": brand,
                "short_name": row.get("short_name") or row["name"],
                "subtitle": row.get("subtitle", ""),
                "short_description": row.get("description", "")[:300],
                "description": row.get("description", ""),
                "regular_price": regular_price,
                "sale_price": selling_price if selling_price < regular_price else None,
                "badge": row.get("badge", ""),
                "badge_class": row.get("badge_class", "blue"),
                "detail_badge": row.get("detail_badge", row.get("badge", "")),
                "status": Product.Status.ACTIVE,
                "is_featured": True,
                "is_new_arrival": row.get("badge") == "New",
                "description_paragraphs": row.get("description_paragraphs", []),
                "features": row.get("features", []),
                "box_contents": row.get("box_contents", []),
                "reviews": row.get("reviews", []),
                "questions": row.get("questions", []),
                "review_score": Decimal(str(row.get("review_score") or 0)),
                "review_count": int(row.get("review_count") or 0),
                "meta_title": row["name"][:255],
                "meta_description": row.get("description", "")[:500],
            }
            product, created = Product.objects.get_or_create(public_id=row["id"], defaults=defaults)
            if created:
                created_products += 1
            else:
                updated_products += 1
                if options["refresh"]:
                    for field, value in defaults.items():
                        setattr(product, field, value)
                    product.save()
                else:
                    changed = []
                    if product.status != Product.Status.ACTIVE:
                        product.status = Product.Status.ACTIVE
                        changed.append("status")
                    if not product.is_featured:
                        product.is_featured = True
                        changed.append("is_featured")
                    if changed:
                        changed.append("updated_at")
                        product.save(update_fields=changed)

            variant_name = (row.get("variant") or "Default").strip()
            variant = product.variants.filter(name__iexact=variant_name).order_by("id").first()
            if variant is None:
                variant = ProductVariant.objects.create(
                    product=product,
                    name=variant_name,
                    sku=_available_sku(_sku_base(row["id"])),
                    symbol="",
                    stock_quantity=int(row.get("stock") or 0),
                    low_stock_alert=5,
                    is_default=True,
                    is_active=True,
                )
            else:
                updates = []
                if not variant.is_active:
                    variant.is_active = True
                    updates.append("is_active")
                if not product.variants.filter(is_default=True).exists():
                    variant.is_default = True
                    updates.append("is_default")
                if updates:
                    updates.append("updated_at")
                    variant.save(update_fields=updates)

            if not InventoryBalance.objects.filter(variant=variant).exists() and not _has_business_history(variant):
                variant.stock_quantity = int(row.get("stock") or 0)
                variant.low_stock_alert = 5
                variant.save(update_fields=["stock_quantity", "low_stock_alert", "updated_at"])
                bootstrap_variant_stock(variant)
                stocked_variants += 1

            if created or options["refresh"]:
                ProductSpecification.objects.filter(product=product).delete()
                ProductSpecification.objects.bulk_create(
                    [
                        ProductSpecification(
                            product=product,
                            name=spec.get("name", "Specification"),
                            value=spec.get("value", ""),
                            sort_order=spec_index,
                        )
                        for spec_index, spec in enumerate(row.get("specifications", []))
                        if spec.get("name") and spec.get("value")
                    ]
                )

            source_static = row.get("image", "")
            source_path = finders.find(source_static)
            if not source_path:
                raise CommandError(f"Demo source image not found: {source_static}")

            if created or options["refresh"] or product.images.count() < 3:
                ProductImage.objects.filter(product=product, alt_text__startswith=DEMO_IMAGE_PREFIX).delete()

                primary = product.images.filter(role=ProductImage.Role.PRIMARY).order_by("id").first()
                if primary is None:
                    ProductImage.objects.create(
                        product=product,
                        static_path=source_static,
                        alt_text=f"{DEMO_IMAGE_PREFIX} {row['name']} primary",
                        role=ProductImage.Role.PRIMARY,
                        sort_order=0,
                    )

                existing_static = {
                    value
                    for value in product.images.exclude(static_path="").values_list("static_path", flat=True)
                }
                actual_paths = []
                for value in [row.get("detail_image"), *(row.get("images") or [])]:
                    if value and value != source_static and value not in actual_paths:
                        actual_paths.append(value)

                sort_order = 1
                for path_value in actual_paths[:3]:
                    if path_value in existing_static:
                        continue
                    if not finders.find(path_value):
                        continue
                    ProductImage.objects.create(
                        product=product,
                        static_path=path_value,
                        alt_text=f"{DEMO_IMAGE_PREFIX} {row['name']} gallery",
                        role=ProductImage.Role.GALLERY,
                        sort_order=sort_order,
                    )
                    sort_order += 1

                while product.images.count() < 4:
                    mode = ("detail", "gallery", "clean")[min(product.images.count() - 1, 2)]
                    generated = ProductImage(
                        product=product,
                        alt_text=f"{DEMO_IMAGE_PREFIX} {row['name']} {mode}",
                        role=ProductImage.Role.DETAIL if mode == "detail" else ProductImage.Role.GALLERY,
                        sort_order=sort_order,
                    )
                    filename = f"demo-{row['id']}-{mode}-{sort_order}.webp"
                    generated.image.save(filename, _render_demo_image(Path(source_path), mode), save=False)
                    generated.save()
                    sort_order += 1

            image_total += product.images.count()

        self.stdout.write(
            self.style.SUCCESS(
                f"Demo catalog ready: {DEMO_LIMIT} real products "
                f"({created_products} created, {updated_products} existing), "
                f"{image_total} total product images, {stocked_variants} stock balances initialized."
            )
        )
        self.stdout.write(
            "All demo products are Active + Featured. Existing business-linked stock/history is preserved."
        )
