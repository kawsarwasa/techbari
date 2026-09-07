from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class OpeningStockMigrationTests(TransactionTestCase):
    reset_sequences = True

    migrate_from = [("inventory", "0001_initial")]
    migrate_to = [("inventory", "0002_import_catalog_opening_stock")]

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        old_apps = executor.loader.project_state(self.migrate_from).apps

        Category = old_apps.get_model("catalog", "Category")
        Brand = old_apps.get_model("catalog", "Brand")
        Product = old_apps.get_model("catalog", "Product")
        ProductVariant = old_apps.get_model("catalog", "ProductVariant")

        category = Category.objects.create(name="Migration Category", slug="migration-category")
        brand = Brand.objects.create(name="Migration Brand", slug="migration-brand")
        product = Product.objects.create(
            public_id="migration-product",
            name="Migration Product",
            slug="migration-product",
            category=category,
            brand=brand,
            regular_price=100,
        )
        ProductVariant.objects.create(
            product=product,
            name="Default",
            sku="MIG-001",
            stock_quantity=17,
            low_stock_alert=4,
            is_default=True,
            is_active=True,
        )

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        self.apps = executor.loader.project_state(self.migrate_to).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_existing_variant_stock_is_imported_without_loss(self):
        Warehouse = self.apps.get_model("inventory", "Warehouse")
        InventoryBalance = self.apps.get_model("inventory", "InventoryBalance")
        StockMovement = self.apps.get_model("inventory", "StockMovement")
        ProductVariant = self.apps.get_model("catalog", "ProductVariant")

        warehouse = Warehouse.objects.get(code="MAIN")
        variant = ProductVariant.objects.get(sku="MIG-001")
        balance = InventoryBalance.objects.get(warehouse=warehouse, variant=variant)
        movement = StockMovement.objects.get(warehouse=warehouse, variant=variant, movement_type="opening")

        self.assertTrue(warehouse.is_default)
        self.assertEqual(balance.on_hand, 17)
        self.assertEqual(balance.low_stock_threshold, 4)
        self.assertEqual(movement.quantity_delta, 17)
        self.assertEqual(movement.quantity_after, 17)
        self.assertEqual(variant.stock_quantity, 17)
