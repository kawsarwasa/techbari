from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from catalog.models import Brand, Category, Product, ProductVariant
from inventory.models import InventoryBalance, StockMovement, Warehouse
from serial_tracking.models import SerializedUnit
from .models import PurchaseOrder, PurchasePayment, PurchaseReceipt, PurchaseReturn, PurchaseReturnSerialUnit, Supplier
from .services import (
    PurchasingError,
    cancel_purchase,
    delete_draft_purchase,
    delete_supplier,
    pay_purchase,
    receive_purchase,
    return_purchase,
    save_purchase_order,
)


class PurchasingBase(TestCase):
    def setUp(self):
        self.warehouse = Warehouse.objects.create(name="Main Warehouse", code="MAIN-T", is_active=True, is_default=True)
        self.category = Category.objects.create(name="Phones", slug="phones")
        self.brand = Brand.objects.create(name="Apple", slug="apple")
        self.product = Product.objects.create(
            public_id="iphone-15-test",
            name="iPhone 15",
            slug="iphone-15-test",
            category=self.category,
            brand=self.brand,
            regular_price=Decimal("1000.00"),
            status=Product.Status.ACTIVE,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            name="128GB Black",
            sku="IPH15-128-BLK-T",
            stock_quantity=0,
            is_default=True,
            is_active=True,
        )
        self.supplier = Supplier.objects.create(
            code="SUP-001",
            name="Global Devices",
            phone="01700000000",
            payment_terms_days=30,
        )

    def purchase_header(self, status=PurchaseOrder.Status.ORDERED, po_number="PO-TEST-001"):
        return {
            "po_number": po_number,
            "supplier": self.supplier,
            "warehouse": self.warehouse,
            "status": status,
            "purchase_date": date(2026, 9, 7),
            "expected_date": date(2026, 9, 10),
            "supplier_invoice_no": "INV-001",
            "invoice_date": date(2026, 9, 7),
            "shipping_cost": Decimal("10.00"),
            "other_cost": Decimal("0.00"),
            "discount_amount": Decimal("20.00"),
            "notes": "Test purchase",
        }

    def create_purchase(self, quantity=5, unit_cost=Decimal("100.00"), status=PurchaseOrder.Status.ORDERED, po_number="PO-TEST-001"):
        return save_purchase_order(
            header_data=self.purchase_header(status=status, po_number=po_number),
            item_rows=[{
                "variant": self.variant,
                "ordered_quantity": quantity,
                "unit_cost": unit_cost,
                "discount_amount": Decimal("0.00"),
            }],
            actor="Test",
        )


class PurchasingServiceTests(PurchasingBase):
    def test_purchase_order_totals_and_status(self):
        purchase = self.create_purchase()
        self.assertEqual(purchase.subtotal, Decimal("500.00"))
        self.assertEqual(purchase.grand_total, Decimal("490.00"))
        self.assertEqual(purchase.outstanding_amount, Decimal("490.00"))
        self.assertEqual(purchase.payment_status, "Unpaid")

    def test_partial_and_full_receipt_updates_inventory(self):
        purchase = self.create_purchase()
        item = purchase.items.get()
        receipt = receive_purchase(
            purchase=purchase,
            received_date=date(2026, 9, 8),
            quantities={item.pk: 2},
            serial_payloads={item.pk: [{"serial_number": "SN-001", "imei1": "352099001234567", "imei2": None}]},
            actor="Test",
        )
        purchase.refresh_from_db()
        item.refresh_from_db()
        balance = InventoryBalance.objects.get(warehouse=self.warehouse, variant=self.variant)
        self.assertEqual(receipt.items.get().quantity, 2)
        self.assertEqual(item.received_quantity, 2)
        self.assertEqual(balance.on_hand, 2)
        self.assertEqual(purchase.status, PurchaseOrder.Status.PARTIALLY_RECEIVED)
        self.assertTrue(StockMovement.objects.filter(reference_no=receipt.receipt_no, movement_type=StockMovement.Type.PURCHASE_IN, quantity_delta=2).exists())
        unit = SerializedUnit.objects.get(serial_number="SN-001")
        self.assertEqual(unit.purchase_reference, purchase.po_number)
        self.assertEqual(unit.purchase_cost, Decimal("100.00"))

        receive_purchase(
            purchase=purchase,
            received_date=date(2026, 9, 9),
            quantities={item.pk: 3},
            actor="Test",
        )
        purchase.refresh_from_db()
        item.refresh_from_db()
        balance.refresh_from_db()
        self.assertEqual(item.received_quantity, 5)
        self.assertEqual(balance.on_hand, 5)
        self.assertEqual(purchase.status, PurchaseOrder.Status.RECEIVED)

    def test_receipt_over_ordered_quantity_is_blocked(self):
        purchase = self.create_purchase()
        item = purchase.items.get()
        with self.assertRaises(PurchasingError):
            receive_purchase(
                purchase=purchase,
                received_date=date(2026, 9, 8),
                quantities={item.pk: 6},
                actor="Test",
            )
        balance = InventoryBalance.objects.filter(warehouse=self.warehouse, variant=self.variant).first()
        self.assertTrue(balance is None or balance.on_hand == 0)
        self.assertFalse(PurchaseReceipt.objects.exists())

    def test_duplicate_serial_rolls_back_entire_receipt(self):
        purchase = self.create_purchase(quantity=2)
        item = purchase.items.get()
        payload = [
            {"serial_number": "DUP-SN", "imei1": None, "imei2": None},
            {"serial_number": "DUP-SN", "imei1": None, "imei2": None},
        ]
        with self.assertRaises(PurchasingError):
            receive_purchase(
                purchase=purchase,
                received_date=date(2026, 9, 8),
                quantities={item.pk: 2},
                serial_payloads={item.pk: payload},
                actor="Test",
            )
        balance = InventoryBalance.objects.filter(warehouse=self.warehouse, variant=self.variant).first()
        self.assertTrue(balance is None or balance.on_hand == 0)
        self.assertFalse(PurchaseReceipt.objects.exists())
        self.assertFalse(SerializedUnit.objects.filter(serial_number="DUP-SN").exists())

    def test_supplier_payment_updates_outstanding_and_blocks_overpay(self):
        purchase = self.create_purchase()
        payment = pay_purchase(
            purchase=purchase,
            amount=Decimal("100.00"),
            method=PurchasePayment.Method.BANK,
            payment_date=date(2026, 9, 8),
            reference="BANK-1",
            actor="Test",
        )
        self.assertEqual(payment.supplier, self.supplier)
        self.assertEqual(purchase.outstanding_amount, Decimal("390.00"))
        self.assertEqual(purchase.payment_status, "Partial")
        with self.assertRaises(PurchasingError):
            pay_purchase(
                purchase=purchase,
                amount=Decimal("391.00"),
                method=PurchasePayment.Method.CASH,
                payment_date=date(2026, 9, 8),
            )

    def test_nonserialized_purchase_return_decreases_inventory_and_due(self):
        purchase = self.create_purchase()
        item = purchase.items.get()
        receive_purchase(purchase=purchase, received_date=date(2026, 9, 8), quantities={item.pk: 5}, actor="Test")
        purchase_return = return_purchase(
            purchase=purchase,
            return_date=date(2026, 9, 9),
            quantities={item.pk: 2},
            serial_unit_ids={item.pk: []},
            reason="Supplier defect",
            actor="Test",
        )
        item.refresh_from_db()
        balance = InventoryBalance.objects.get(warehouse=self.warehouse, variant=self.variant)
        self.assertEqual(item.returned_quantity, 2)
        self.assertEqual(balance.on_hand, 3)
        self.assertEqual(purchase_return.total_amount, Decimal("200.00"))
        self.assertEqual(purchase.outstanding_amount, Decimal("290.00"))
        self.assertTrue(StockMovement.objects.filter(reference_no=purchase_return.return_no, movement_type=StockMovement.Type.PURCHASE_RETURN_OUT, quantity_delta=-2).exists())

    def test_serialized_purchase_return_links_exact_unit(self):
        purchase = self.create_purchase(quantity=1)
        item = purchase.items.get()
        receive_purchase(
            purchase=purchase,
            received_date=date(2026, 9, 8),
            quantities={item.pk: 1},
            serial_payloads={item.pk: [{"serial_number": "RETURN-SN", "imei1": None, "imei2": None}]},
            actor="Test",
        )
        unit = SerializedUnit.objects.get(serial_number="RETURN-SN")
        purchase_return = return_purchase(
            purchase=purchase,
            return_date=date(2026, 9, 9),
            quantities={item.pk: 1},
            serial_unit_ids={item.pk: [unit.pk]},
            reason="Supplier replacement",
            actor="Test",
        )
        unit.refresh_from_db()
        balance = InventoryBalance.objects.get(warehouse=self.warehouse, variant=self.variant)
        self.assertEqual(unit.status, SerializedUnit.Status.SUPPLIER_RETURNED)
        self.assertEqual(balance.on_hand, 0)
        self.assertTrue(PurchaseReturnSerialUnit.objects.filter(return_item__purchase_return=purchase_return, unit=unit).exists())

    def test_return_cannot_exceed_received_quantity(self):
        purchase = self.create_purchase(quantity=3)
        item = purchase.items.get()
        receive_purchase(purchase=purchase, received_date=date(2026, 9, 8), quantities={item.pk: 1})
        with self.assertRaises(PurchasingError):
            return_purchase(
                purchase=purchase,
                return_date=date(2026, 9, 9),
                quantities={item.pk: 2},
                reason="Too many",
            )
        self.assertFalse(PurchaseReturn.objects.exists())

    def test_cancel_and_draft_delete_rules(self):
        ordered = self.create_purchase(po_number="PO-CANCEL")
        cancel_purchase(purchase=ordered, actor="Test")
        ordered.refresh_from_db()
        self.assertEqual(ordered.status, PurchaseOrder.Status.CANCELLED)

        draft = self.create_purchase(status=PurchaseOrder.Status.DRAFT, po_number="PO-DRAFT")
        delete_draft_purchase(purchase=draft)
        self.assertFalse(PurchaseOrder.objects.filter(pk=draft.pk).exists())

    def test_supplier_with_purchase_history_cannot_be_deleted(self):
        self.create_purchase()
        with self.assertRaises(PurchasingError):
            delete_supplier(supplier=self.supplier)


class PurchasingDashboardTests(PurchasingBase):
    def test_supplier_pages_are_database_backed(self):
        response = self.client.get(reverse("backoffice:suppliers"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Global Devices")
        response = self.client.post(reverse("backoffice:supplier_add"), {
            "code": "SUP-002",
            "name": "Second Supplier",
            "contact_person": "",
            "phone": "01800000000",
            "email": "",
            "address": "Dhaka",
            "tax_id": "",
            "payment_terms_days": 15,
            "credit_limit": "10000.00",
            "opening_balance": "0.00",
            "is_active": "on",
            "notes": "",
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Supplier.objects.filter(code="SUP-002").exists())

    def test_purchase_form_creates_real_purchase(self):
        response = self.client.post(reverse("backoffice:purchase_add"), {
            "po_number": "PO-WEB-001",
            "supplier": self.supplier.pk,
            "warehouse": self.warehouse.pk,
            "status": PurchaseOrder.Status.ORDERED,
            "purchase_date": "2026-09-07",
            "expected_date": "2026-09-10",
            "supplier_invoice_no": "",
            "invoice_date": "",
            "shipping_cost": "0.00",
            "other_cost": "0.00",
            "discount_amount": "0.00",
            "notes": "",
            "variant_id": [str(self.variant.pk)],
            "ordered_quantity": ["2"],
            "unit_cost": ["90.00"],
            "line_discount": ["0.00"],
        })
        self.assertEqual(response.status_code, 302)
        purchase = PurchaseOrder.objects.get(po_number="PO-WEB-001")
        self.assertEqual(purchase.items.get().ordered_quantity, 2)

    def test_purchase_operational_pages_render(self):
        purchase = self.create_purchase()
        urls = [
            reverse("backoffice:purchases"),
            reverse("backoffice:purchase_add"),
            reverse("backoffice:purchase_detail", args=[purchase.pk]),
            reverse("backoffice:purchase_receive", args=[purchase.pk]),
            reverse("backoffice:purchase_payment", args=[purchase.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_receive_payment_and_return_views_post_transactions(self):
        purchase = self.create_purchase(quantity=3, po_number="PO-WEB-FLOW")
        item = purchase.items.get()

        response = self.client.post(reverse("backoffice:purchase_receive", args=[purchase.pk]), {
            "received_date": "2026-09-08",
            "supplier_challan_no": "CH-1",
            "note": "Received through dashboard",
            f"receive_{item.pk}": "3",
            f"serials_{item.pk}": "",
        })
        self.assertEqual(response.status_code, 302)
        purchase.refresh_from_db()
        item.refresh_from_db()
        self.assertEqual(purchase.status, PurchaseOrder.Status.RECEIVED)
        self.assertEqual(item.received_quantity, 3)
        self.assertEqual(InventoryBalance.objects.get(warehouse=self.warehouse, variant=self.variant).on_hand, 3)

        self.assertEqual(self.client.get(reverse("backoffice:purchase_return", args=[purchase.pk])).status_code, 200)

        response = self.client.post(reverse("backoffice:purchase_payment", args=[purchase.pk]), {
            "amount": "90.00",
            "method": PurchasePayment.Method.BANK,
            "reference": "TX-WEB",
            "payment_date": "2026-09-08",
            "note": "Dashboard payment",
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(PurchasePayment.objects.filter(purchase=purchase, amount=Decimal("90.00")).exists())

        response = self.client.post(reverse("backoffice:purchase_return", args=[purchase.pk]), {
            "return_date": "2026-09-09",
            "reason": "One defective unit",
            "note": "Dashboard return",
            f"return_{item.pk}": "1",
        })
        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        self.assertEqual(item.returned_quantity, 1)
        self.assertTrue(PurchaseReturn.objects.filter(purchase=purchase).exists())
        self.assertEqual(InventoryBalance.objects.get(warehouse=self.warehouse, variant=self.variant).on_hand, 2)
