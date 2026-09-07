from decimal import Decimal
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .forms import (
    BrandForm,
    CategoryForm,
    ProductForm,
    ProductSpecificationForm,
    ProductVariantForm,
    validate_catalog_image,
    validate_product_images,
)
from .models import Brand, Category, Product, ProductImage, ProductSpecification, ProductVariant
from .presentation import catalog_queryset, serialize_product
from .richtext import sanitize_rich_html


class CatalogModelTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Earbuds", slug="earbuds")
        self.brand = Brand.objects.create(name="Tech Brand", slug="tech-brand")

    def product_form_data(self, **overrides):
        data = {
            "name": "Test Earbuds",
            "slug": "test-earbuds",
            "category": self.category.pk,
            "brand": self.brand.pk,
            "short_name": "Test Earbuds",
            "subtitle": "Demo",
            "short_description": "Short",
            "description": "Description",
            "regular_price": "2000",
            "sale_price": "1800",
            "weight": "0.250",
            "shipping_class": "standard",
            "warranty": "1 year",
            "status": Product.Status.ACTIVE,
            "is_featured": "on",
            "meta_title": "Test Earbuds",
            "meta_description": "Test",
            "sku": "TB-TEST-001",
            "barcode": "1234567890123",
            "stock_quantity": "12",
            "low_stock_alert": "3",
        }
        data.update(overrides)
        return data

    def make_product(self, **overrides):
        defaults = {
            "public_id": "stable-id",
            "name": "Stable Product",
            "slug": "stable-product",
            "category": self.category,
            "brand": self.brand,
            "regular_price": Decimal("1000"),
            "status": Product.Status.ACTIVE,
        }
        defaults.update(overrides)
        return Product.objects.create(**defaults)

    def png_upload(self, name="image.png"):
        stream = BytesIO()
        Image.new("RGB", (8, 8), "white").save(stream, format="PNG")
        return SimpleUploadedFile(name, stream.getvalue(), content_type="image/png")

    def test_product_form_creates_default_variant_without_destroying_future_variants(self):
        form = ProductForm(data=self.product_form_data())
        self.assertTrue(form.is_valid(), form.errors)
        product = form.save()
        self.assertEqual(product.public_id, "test-earbuds")
        self.assertEqual(product.current_price, Decimal("1800"))
        self.assertEqual(product.variants.count(), 1)
        default = product.variants.get(is_default=True)
        self.assertEqual(default.sku, "TB-TEST-001")
        self.assertEqual(default.barcode, "1234567890123")
        self.assertEqual(default.stock_quantity, 12)
        extra = ProductVariant.objects.create(
            product=product,
            name="Black",
            sku="TB-TEST-BLK",
            barcode="1234567890124",
            stock_quantity=4,
        )
        edit = ProductForm(data=self.product_form_data(name="Test Earbuds Updated"), instance=product)
        self.assertTrue(edit.is_valid(), edit.errors)
        edit.save()
        self.assertTrue(ProductVariant.objects.filter(pk=extra.pk).exists())

    def test_product_form_uses_plain_short_description_fallback_for_rich_html(self):
        data = self.product_form_data(short_description="", description="<h2>Heading</h2><p>Useful <strong>details</strong></p>")
        form = ProductForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        product = form.save()
        self.assertEqual(product.short_description, "HeadingUseful details")
        self.assertNotIn("<", product.short_description)

    def test_product_form_rejects_duplicate_sku_and_barcode(self):
        product = self.make_product()
        ProductVariant.objects.create(
            product=product,
            name="Default",
            sku="TB-STABLE-001",
            barcode="111",
            stock_quantity=7,
            is_default=True,
        )
        duplicate_product = ProductForm(
            data=self.product_form_data(sku="tb-stable-001", barcode="111")
        )
        self.assertFalse(duplicate_product.is_valid())
        self.assertIn("sku", duplicate_product.errors)
        self.assertIn("barcode", duplicate_product.errors)

    def test_variant_form_rejects_duplicate_barcode(self):
        product = self.make_product()
        ProductVariant.objects.create(
            product=product,
            name="Default",
            sku="TB-STABLE-001",
            barcode="111",
            stock_quantity=7,
            is_default=True,
        )
        form = ProductVariantForm(
            data={
                "product": product.pk,
                "name": "Black",
                "sku": "TB-STABLE-BLK",
                "barcode": "111",
                "symbol": "",
                "regular_price_override": "",
                "price_override": "",
                "stock_quantity": "1",
                "low_stock_alert": "1",
                "is_active": "on",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("barcode", form.errors)

    def test_variant_form_rejects_default_inactive_and_invalid_price_override(self):
        product = self.make_product()
        form = ProductVariantForm(
            data={
                "product": product.pk,
                "name": "Black",
                "sku": "TB-STABLE-BLK",
                "barcode": "",
                "symbol": "⚫",
                "regular_price_override": "1000",
                "price_override": "1100",
                "stock_quantity": "1",
                "low_stock_alert": "1",
                "is_default": "on",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("is_active", form.errors)
        self.assertIn("price_override", form.errors)

    def test_specification_form_rejects_duplicate_name_case_insensitive(self):
        product = self.make_product(public_id="spec-product", name="Spec Product", slug="spec-product")
        ProductSpecification.objects.create(product=product, name="Bluetooth", value="5.3")
        form = ProductSpecificationForm(
            data={"product": product.pk, "name": "bluetooth", "value": "5.4", "sort_order": "0"}
        )
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)

    def test_category_form_blocks_circular_parent(self):
        root = Category.objects.create(name="Root", slug="root")
        child = Category.objects.create(name="Child", slug="child", parent=root)
        form = CategoryForm(
            data={
                "name": root.name,
                "slug": root.slug,
                "parent": child.pk,
                "description": "",
                "sort_order": "0",
                "status": "Active",
            },
            instance=root,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("parent", form.errors)

    def test_brand_form_updates_active_and_featured_flags(self):
        form = BrandForm(
            data={
                "name": "QA Brand",
                "slug": "",
                "description": "",
                "sort_order": "1",
                "status": "Inactive",
                "featured": "Yes",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        brand = form.save()
        self.assertFalse(brand.is_active)
        self.assertTrue(brand.is_featured)
        self.assertEqual(brand.slug, "qa-brand")

    def test_catalog_image_validation_accepts_png_and_rejects_oversize(self):
        upload = self.png_upload()
        self.assertIs(validate_catalog_image(upload), upload)
        oversized = SimpleUploadedFile(
            "large.png",
            b"x" * (2 * 1024 * 1024 + 1),
            content_type="image/png",
        )
        with self.assertRaises(ValidationError):
            validate_catalog_image(oversized)
        with self.assertRaises(ValidationError):
            validate_product_images([self.png_upload(f"{index}.png") for index in range(9)])

    def test_rich_text_sanitizer_preserves_formatting_and_strips_unsafe_markup(self):
        value = '<h2 onclick="bad()">Title</h2><script>alert(1)</script><ol><li><em>One</em></li></ol>'
        sanitized = sanitize_rich_html(value)
        self.assertIn("<h2>Title</h2>", sanitized)
        self.assertIn("<ol><li><em>One</em></li></ol>", sanitized)
        self.assertNotIn("onclick", sanitized)
        self.assertNotIn("<script", sanitized)
        self.assertIn("alert(1)", sanitized)

    def test_storefront_serializer_includes_default_barcode_variants_and_rich_html(self):
        product = self.make_product(
            public_id="serializable",
            name="Serializable Product",
            slug="serializable-product",
            description="<h2>Heading</h2><ul><li>Feature</li></ul>",
            short_description="Short summary",
        )
        default = ProductVariant.objects.create(
            product=product,
            name="Default",
            sku="TB-SERIAL-001",
            barcode="987654321",
            stock_quantity=7,
            is_default=True,
            regular_price_override=Decimal("1200"),
            price_override=Decimal("900"),
        )
        ProductVariant.objects.create(
            product=product,
            name="Black",
            sku="TB-SERIAL-BLK",
            stock_quantity=0,
            price_override=Decimal("950"),
        )
        data = serialize_product(product)
        self.assertEqual(data["id"], "serializable")
        self.assertEqual(data["stock"], 7)
        self.assertEqual(data["sku"], "TB-SERIAL-001")
        self.assertEqual(data["barcode"], "987654321")
        self.assertEqual(data["default_variant_id"], default.pk)
        self.assertEqual(data["price"], 900)
        self.assertEqual(data["regular_price"], 1200)
        self.assertIn("<h2>Heading</h2>", str(data["description_html"]))
        self.assertEqual(data["variants"][1]["available"], False)

    def test_inactive_category_or_brand_hides_product_from_storefront_queryset(self):
        product = self.make_product()
        ProductVariant.objects.create(product=product, name="Default", sku="VISIBLE-1", is_default=True)
        self.assertTrue(catalog_queryset().filter(pk=product.pk).exists())
        self.category.is_active = False
        self.category.save(update_fields=["is_active"])
        self.assertFalse(catalog_queryset().filter(pk=product.pk).exists())


class CatalogViewTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Accessories", slug="accessories")
        self.brand = Brand.objects.create(name="QA Brand", slug="qa-brand")

    def product_post_data(self, **overrides):
        data = {
            "name": "QA Product",
            "slug": "qa-product",
            "category": str(self.category.pk),
            "brand": str(self.brand.pk),
            "short_name": "QA Product",
            "subtitle": "",
            "short_description": "Storefront summary",
            "description": "<h2>QA Heading</h2><p>Full <strong>description</strong>.</p><ul><li>One</li></ul>",
            "regular_price": "2000",
            "sale_price": "1800",
            "weight": "",
            "shipping_class": "standard",
            "warranty": "",
            "status": Product.Status.ACTIVE,
            "meta_title": "",
            "meta_description": "",
            "badge": "",
            "detail_badge": "",
            "sku": "QA-SKU-001",
            "barcode": "QA-BAR-001",
            "stock_quantity": "5",
            "low_stock_alert": "2",
        }
        data.update(overrides)
        return data

    def create_product(self, **overrides):
        defaults = {
            "public_id": "qa-product",
            "name": "QA Product",
            "slug": "qa-product",
            "category": self.category,
            "brand": self.brand,
            "short_description": "Storefront summary",
            "description": "<h2>QA Heading</h2><p>Full description.</p>",
            "regular_price": Decimal("2000"),
            "sale_price": Decimal("1800"),
            "status": Product.Status.ACTIVE,
        }
        defaults.update(overrides)
        product = Product.objects.create(**defaults)
        ProductVariant.objects.create(
            product=product,
            name="Default",
            sku=f"SKU-{product.pk}",
            barcode=f"BAR-{product.pk}",
            stock_quantity=5,
            is_default=True,
        )
        return product

    def test_add_product_page_starts_without_demo_specifications(self):
        response = self.client.get(reverse("backoffice:product_add"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'value="Bluetooth Version"')
        self.assertNotContains(response, 'value="Driver Size"')

    def test_product_create_edit_archive_and_delete_flows(self):
        response = self.client.post(reverse("backoffice:product_add"), self.product_post_data())
        self.assertEqual(response.status_code, 302)
        product = Product.objects.get(slug="qa-product")
        self.assertEqual(product.variants.get(is_default=True).sku, "QA-SKU-001")

        edit_url = reverse("backoffice:product_edit") + f"?id={product.pk}"
        response = self.client.post(edit_url, self.product_post_data(name="QA Product Updated"))
        self.assertEqual(response.status_code, 302)
        product.refresh_from_db()
        self.assertEqual(product.name, "QA Product Updated")

        response = self.client.post(
            reverse("backoffice:products"),
            {"action": "archive", "product_id": product.pk},
        )
        self.assertEqual(response.status_code, 302)
        product.refresh_from_db()
        self.assertEqual(product.status, Product.Status.ARCHIVED)

        response = self.client.post(
            reverse("backoffice:products"),
            {"action": "delete", "product_id": product.pk},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Product.objects.filter(pk=product.pk).exists())

    def test_category_and_brand_used_by_product_are_protected_from_delete(self):
        product = self.create_product()
        response = self.client.post(
            reverse("backoffice:categories"),
            {"action": "delete", "category_id": self.category.pk},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Category.objects.filter(pk=self.category.pk).exists())
        response = self.client.post(
            reverse("backoffice:brands"),
            {"action": "delete", "brand_id": self.brand.pk},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Brand.objects.filter(pk=self.brand.pk).exists())
        self.assertTrue(Product.objects.filter(pk=product.pk).exists())

    def test_last_variant_delete_is_blocked_and_default_reassigned_when_possible(self):
        product = self.create_product()
        default = product.variants.get(is_default=True)
        response = self.client.post(
            reverse("backoffice:catalog_variants"),
            {"action": "delete", "variant_id": default.pk},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ProductVariant.objects.filter(pk=default.pk).exists())

        second = ProductVariant.objects.create(
            product=product,
            name="Black",
            sku="QA-BLACK",
            stock_quantity=2,
        )
        response = self.client.post(
            reverse("backoffice:catalog_variants"),
            {"action": "delete", "variant_id": default.pk},
        )
        self.assertEqual(response.status_code, 302)
        second.refresh_from_db()
        self.assertTrue(second.is_default)

    def test_primary_image_is_reassigned_after_media_delete(self):
        product = self.create_product()
        primary = ProductImage.objects.create(
            product=product,
            static_path="store/images/one.webp",
            role=ProductImage.Role.PRIMARY,
            sort_order=0,
        )
        replacement = ProductImage.objects.create(
            product=product,
            static_path="store/images/two.webp",
            role=ProductImage.Role.GALLERY,
            sort_order=1,
        )
        response = self.client.post(
            reverse("backoffice:catalog_media"),
            {"action": "delete", "image_id": primary.pk},
        )
        self.assertEqual(response.status_code, 302)
        replacement.refresh_from_db()
        self.assertEqual(replacement.role, ProductImage.Role.PRIMARY)

    def test_storefront_product_detail_renders_short_summary_rich_description_and_specs(self):
        product = self.create_product(
            description='<h2 onclick="bad()">QA Heading</h2><p>Full <strong>description</strong>.</p><ol><li>First</li></ol><script>bad()</script>',
        )
        ProductSpecification.objects.create(product=product, name="Connector", value="USB-C")
        response = self.client.get(reverse("storefront:product_detail", kwargs={"slug": product.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Storefront summary")
        self.assertContains(response, "<h2>QA Heading</h2>", html=True)
        self.assertContains(response, "<ol><li>First</li></ol>", html=True)
        self.assertContains(response, "USB-C")
        self.assertNotContains(response, "onclick=\"bad()\"")
        self.assertNotContains(response, "<script>bad()</script>")

    def test_deleted_product_removes_uploaded_media_file_after_commit(self):
        product = self.create_product()
        with TemporaryDirectory() as temp_dir, override_settings(MEDIA_ROOT=temp_dir):
            upload = SimpleUploadedFile("delete-me.txt", b"file", content_type="text/plain")
            image = ProductImage.objects.create(product=product, image=upload, role=ProductImage.Role.PRIMARY)
            path = Path(image.image.path)
            self.assertTrue(path.exists())
            with self.captureOnCommitCallbacks(execute=True):
                product.delete()
            self.assertFalse(path.exists())
