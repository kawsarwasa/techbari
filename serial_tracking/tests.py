from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse

from catalog.models import Brand, Category, Product, ProductVariant
from inventory.models import InventoryBalance, Warehouse
from inventory.services import get_default_warehouse
from .forms import SerializedUnitForm
from .models import SerializedUnit, SerializedUnitEvent, WarrantyClaim
from .services import (
    SerialTrackingError,
    change_serial_unit_status,
    open_warranty_claim,
    register_serial_unit,
    transfer_serial_unit,
    update_warranty_claim,
)


class SerialTrackingBase(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Phones", slug="phones")
        self.brand = Brand.objects.create(name="Test Brand", slug="test-brand")
        self.product = Product.objects.create(
            public_id="phone-1",
            name="Test Phone",
            slug="test-phone",
            category=self.category,
            brand=self.brand,
            regular_price=1000,
            status=Product.Status.ACTIVE,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            name="128GB Black",
            sku="PHONE-128-BLK",
            barcode="9988776655",
            stock_quantity=4,
            low_stock_alert=1,
            is_default=True,
            is_active=True,
        )
        self.main = get_default_warehouse()
        self.balance = InventoryBalance.objects.get(warehouse=self.main, variant=self.variant)
        self.branch = Warehouse.objects.create(name="Branch Shop", code="BR01", is_active=True)

    def unit_data(self, serial, **overrides):
        data = {
            "variant": self.variant,
            "warehouse": self.main,
            "serial_number": serial,
            "imei1": None,
            "imei2": None,
            "status": SerializedUnit.Status.AVAILABLE,
            "supplier_reference": "",
            "purchase_reference": "PO-1",
            "purchase_date": date.today(),
            "purchase_cost": 900,
            "received_date": date.today(),
            "sales_reference": "",
            "customer_reference": "",
            "sold_at": None,
            "warranty_type": "1 Year",
            "warranty_start_date": date.today(),
            "warranty_end_date": date.today() + timedelta(days=365),
            "supplier_warranty_reference": "",
            "notes": "",
        }
        data.update(overrides)
        return data


class SerializedUnitModelTests(SerialTrackingBase):
    def test_unit_requires_identifier_and_valid_imei(self):
        unit = SerializedUnit(variant=self.variant, warehouse=self.main)
        with self.assertRaises(ValidationError):
            unit.full_clean()

        unit.serial_number = "SER-1"
        unit.imei1 = "1234"
        with self.assertRaises(ValidationError):
            unit.full_clean()

        unit.imei1 = "123456789012345"
        unit.full_clean()

    def test_form_rejects_duplicate_serial_and_imei(self):
        register_serial_unit(data=self.unit_data("SER-DUP", imei1="123456789012345"), actor="Test")
        form = SerializedUnitForm(
            data={
                "variant": self.variant.pk,
                "warehouse": self.main.pk,
                "serial_number": "SER-DUP",
                "imei1": "123456789012345",
                "status": SerializedUnit.Status.AVAILABLE,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertTrue("serial_number" in form.errors or "imei1" in form.errors)

    def test_event_history_is_immutable(self):
        unit = register_serial_unit(data=self.unit_data("SER-EVENT"), actor="Test")
        event = unit.events.first()
        event.note = "changed"
        with self.assertRaises(ValidationError):
            event.save()
        with self.assertRaises(ValidationError):
            event.delete()


class SerialInventoryServiceTests(SerialTrackingBase):
    def test_registration_does_not_create_stock_and_enforces_capacity(self):
        for number in range(4):
            register_serial_unit(data=self.unit_data(f"SER-{number}"), actor="Test")
        self.balance.refresh_from_db()
        self.assertEqual(self.balance.on_hand, 4)
        with self.assertRaises(SerialTrackingError):
            register_serial_unit(data=self.unit_data("SER-OVER"), actor="Test")

    def test_reserve_sell_return_flow_updates_inventory(self):
        unit = register_serial_unit(data=self.unit_data("SER-LIFE"), actor="Test")
        change_serial_unit_status(unit, SerializedUnit.Status.RESERVED, actor="Test")
        self.balance.refresh_from_db()
        self.assertEqual(self.balance.on_hand, 4)
        self.assertEqual(self.balance.reserved_quantity, 1)

        unit.refresh_from_db()
        change_serial_unit_status(unit, SerializedUnit.Status.SOLD, actor="Test")
        self.balance.refresh_from_db()
        self.assertEqual(self.balance.on_hand, 3)
        self.assertEqual(self.balance.reserved_quantity, 0)

        unit.refresh_from_db()
        change_serial_unit_status(unit, SerializedUnit.Status.RETURNED, actor="Test")
        self.balance.refresh_from_db()
        self.assertEqual(self.balance.on_hand, 4)
        self.assertEqual(self.balance.reserved_quantity, 0)

    def test_available_unit_transfer_moves_inventory_and_location(self):
        unit = register_serial_unit(data=self.unit_data("SER-MOVE"), actor="Test")
        transfer_serial_unit(unit, self.branch, actor="Test")
        unit.refresh_from_db()
        source = InventoryBalance.objects.get(warehouse=self.main, variant=self.variant)
        destination = InventoryBalance.objects.get(warehouse=self.branch, variant=self.variant)
        self.assertEqual(unit.warehouse, self.branch)
        self.assertEqual(source.on_hand, 3)
        self.assertEqual(destination.on_hand, 1)
        self.assertTrue(unit.events.filter(event_type=SerializedUnitEvent.Type.TRANSFERRED).exists())

    def test_reserved_unit_transfer_preserves_reservation(self):
        unit = register_serial_unit(data=self.unit_data("SER-RMOVE"), actor="Test")
        change_serial_unit_status(unit, SerializedUnit.Status.RESERVED, actor="Test")
        unit.refresh_from_db()
        transfer_serial_unit(unit, self.branch, actor="Test")
        source = InventoryBalance.objects.get(warehouse=self.main, variant=self.variant)
        destination = InventoryBalance.objects.get(warehouse=self.branch, variant=self.variant)
        unit.refresh_from_db()
        self.assertEqual(unit.warehouse, self.branch)
        self.assertEqual(source.reserved_quantity, 0)
        self.assertEqual(destination.on_hand, 1)
        self.assertEqual(destination.reserved_quantity, 1)


class WarrantyServiceTests(SerialTrackingBase):
    def _claim_data(self, unit, **overrides):
        data = {
            "claim_no": "WCL-001",
            "unit": unit,
            "customer_name": "Rahim",
            "customer_phone": "01700000000",
            "order_reference": "TB-1001",
            "claim_date": date.today(),
            "issue": "Device does not power on",
            "status": WarrantyClaim.Status.OPEN,
            "resolution": "",
            "service_reference": "",
            "replacement_unit": None,
            "resolved_at": None,
            "notes": "",
        }
        data.update(overrides)
        return data

    def test_open_and_resolve_claim_restores_previous_unit_status(self):
        unit = register_serial_unit(data=self.unit_data("SER-WAR"), actor="Test")
        change_serial_unit_status(unit, SerializedUnit.Status.SOLD, actor="Test")
        unit.refresh_from_db()
        claim = open_warranty_claim(data=self._claim_data(unit), actor="Test")
        unit.refresh_from_db()
        self.assertEqual(unit.status, SerializedUnit.Status.WARRANTY_SERVICE)
        self.assertEqual(claim.unit_status_before_claim, SerializedUnit.Status.SOLD)

        update_warranty_claim(
            claim=claim,
            data={**self._claim_data(unit), "status": WarrantyClaim.Status.RESOLVED, "resolution": "Repaired"},
            actor="Test",
        )
        unit.refresh_from_db()
        claim.refresh_from_db()
        self.assertEqual(unit.status, SerializedUnit.Status.SOLD)
        self.assertEqual(claim.status, WarrantyClaim.Status.RESOLVED)
        self.assertIsNotNone(claim.resolved_at)

    def test_replacement_sells_replacement_and_scraps_original(self):
        original = register_serial_unit(data=self.unit_data("SER-OLD"), actor="Test")
        replacement = register_serial_unit(data=self.unit_data("SER-NEW"), actor="Test")
        change_serial_unit_status(original, SerializedUnit.Status.SOLD, actor="Test")
        original.refresh_from_db()
        claim = open_warranty_claim(data=self._claim_data(original, claim_no="WCL-REP"), actor="Test")

        update_warranty_claim(
            claim=claim,
            data={
                **self._claim_data(original, claim_no="WCL-REP"),
                "status": WarrantyClaim.Status.REPLACED,
                "replacement_unit": replacement,
                "resolution": "Replaced with new unit",
            },
            actor="Test",
        )
        original.refresh_from_db()
        replacement.refresh_from_db()
        claim.refresh_from_db()
        self.assertEqual(original.status, SerializedUnit.Status.SCRAPPED)
        self.assertEqual(replacement.status, SerializedUnit.Status.SOLD)
        self.assertEqual(claim.replacement_unit, replacement)


class SerialDashboardTests(SerialTrackingBase):
    def setUp(self):
        super().setUp()
        self.client = Client()

    def test_serial_and_warranty_pages_render(self):
        for route in ("backoffice:serials", "backoffice:serial_add", "backoffice:warranty", "backoffice:warranty_add"):
            response = self.client.get(reverse(route))
            self.assertEqual(response.status_code, 200)

    def test_serial_form_creates_database_unit(self):
        response = self.client.post(
            reverse("backoffice:serial_add"),
            data={
                "variant": self.variant.pk,
                "warehouse": self.main.pk,
                "serial_number": "SER-WEB",
                "imei1": "",
                "imei2": "",
                "status": SerializedUnit.Status.AVAILABLE,
                "supplier_reference": "",
                "purchase_reference": "",
                "purchase_date": "",
                "purchase_cost": "",
                "received_date": "",
                "sales_reference": "",
                "customer_reference": "",
                "sold_at": "",
                "warranty_type": "1 Year",
                "warranty_start_date": "",
                "warranty_end_date": "",
                "supplier_warranty_reference": "",
                "notes": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(SerializedUnit.objects.filter(serial_number="SER-WEB").exists())

    def test_warranty_form_opens_claim_for_selected_unit(self):
        unit = register_serial_unit(data=self.unit_data("SER-WEB-WAR"), actor="Test")
        change_serial_unit_status(unit, SerializedUnit.Status.SOLD, actor="Test")
        response = self.client.post(
            reverse("backoffice:warranty_add"),
            data={
                "claim_no": "WCL-WEB",
                "unit": unit.pk,
                "customer_name": "Karim",
                "customer_phone": "",
                "order_reference": "TB-12",
                "claim_date": date.today().isoformat(),
                "issue": "Battery issue",
                "status": WarrantyClaim.Status.OPEN,
                "resolution": "",
                "service_reference": "",
                "replacement_unit": "",
                "resolved_at": "",
                "notes": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(WarrantyClaim.objects.filter(claim_no="WCL-WEB").exists())
