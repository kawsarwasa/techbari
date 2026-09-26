from io import BytesIO, StringIO
from unittest.mock import patch
from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings

from PIL import Image

from catalog.management.commands.seed_official_product_images import _discover_image_candidates
from catalog.models import Brand, Category, Product, ProductImage
from catalog.official_product_images import OFFICIAL_PRODUCT_IMAGE_SOURCES


class RealDemoProductSeedTests(TestCase):
    def test_command_seeds_ten_products_with_multiple_images(self):
        with TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                output = StringIO()
                call_command("seed_real_demo_products", stdout=output)

        demo_ids = [
            "baseus",
            "q20i",
            "haylou",
            "jbl",
            "xiaomi",
            "anker",
            "ugreen",
            "budsfe",
            "neckband",
            "amazfit",
        ]
        products = Product.objects.filter(public_id__in=demo_ids)
        self.assertEqual(products.count(), 10)
        for product in products:
            self.assertEqual(product.status, Product.Status.ACTIVE)
            self.assertTrue(product.is_featured)
            self.assertGreaterEqual(product.images.count(), 4)
            self.assertTrue(product.variants.filter(is_active=True).exists())
        self.assertIn("Demo catalog ready: 10 real products", output.getvalue())



def _test_product_image_bytes():
    output = BytesIO()
    Image.new("RGB", (640, 640), "white").save(output, format="PNG")
    return output.getvalue()


class OfficialDemoProductImageSeedTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name="Headphones", slug="official-test-headphones")
        brand = Brand.objects.create(name="Anker", slug="official-test-anker")
        self.product = Product.objects.create(
            public_id="q20i",
            name="Anker Soundcore Q20i Wireless Headphones",
            slug="official-test-q20i",
            category=category,
            brand=brand,
            regular_price="8990.00",
            sale_price="7990.00",
            status=Product.Status.ACTIVE,
        )
        ProductImage.objects.create(
            product=self.product,
            static_path="store/images/q20i.webp",
            alt_text="[Demo gallery] Q20i primary",
            role=ProductImage.Role.PRIMARY,
            sort_order=0,
        )

    def test_official_command_adds_separate_gallery_and_removes_only_generated_demo_variants(self):
        image_bytes = _test_product_image_bytes()
        generated = ProductImage(
            product=self.product,
            alt_text="[Demo gallery] Q20i generated",
            role=ProductImage.Role.GALLERY,
            sort_order=1,
        )

        with TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                generated.image.save(
                    "generated-q20i.webp",
                    SimpleUploadedFile("generated-q20i.webp", image_bytes, content_type="image/png"),
                    save=True,
                )
                html = (
                    '<img src="https://cdn.shopify.com/files/q20i-product-side.jpg" '
                    'alt="soundcore Q20i product side">'
                )
                with patch(
                    "catalog.management.commands.seed_official_product_images._fetch_html",
                    return_value=html,
                ), patch(
                    "catalog.management.commands.seed_official_product_images._download_bytes",
                    return_value=image_bytes,
                ):
                    output = StringIO()
                    call_command(
                        "seed_official_product_images",
                        product=["q20i"],
                        limit=3,
                        stdout=output,
                    )

                official = self.product.images.filter(alt_text__startswith="[Official gallery]")
                self.assertEqual(official.count(), 3)
                self.assertTrue(all(row.image.name.endswith(".webp") for row in official))
                self.assertFalse(
                    self.product.images.filter(
                        alt_text="[Demo gallery] Q20i generated",
                        static_path="",
                    ).exists()
                )
                self.assertTrue(
                    self.product.images.filter(
                        alt_text="[Demo gallery] Q20i primary",
                        static_path="store/images/q20i.webp",
                    ).exists()
                )
                self.assertIn("q20i: added 3 official product image(s)", output.getvalue())

    def test_official_candidate_discovery_rejects_non_manufacturer_hosts(self):
        config = OFFICIAL_PRODUCT_IMAGE_SOURCES["q20i"]
        html = """
            <img src="https://cdn.shopify.com/files/q20i-product-front.jpg" alt="soundcore Q20i front">
            <img src="https://evil.example/q20i-product.jpg" alt="soundcore Q20i">
        """
        candidates = _discover_image_candidates(html, config)
        self.assertEqual(candidates, ["https://cdn.shopify.com/files/q20i-product-front.jpg"])
