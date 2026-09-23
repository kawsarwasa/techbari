from io import StringIO
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.test import TestCase, override_settings

from catalog.models import Product


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
