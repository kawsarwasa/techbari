from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from catalog.models import Brand, Category, Product, ProductVariant
from customers.models import Customer, CustomerGroup
from inventory.models import InventoryBalance, StockMovement, Warehouse
from payments.models import PaymentTransaction
from purchasing.models import (
    PurchaseOrder,
    PurchaseOrderItem,
    PurchasePayment,
    PurchaseReceipt,
    PurchaseReceiptItem,
    PurchaseReturn,
    PurchaseReturnItem,
    Supplier,
)
from sales.models import SalesOrder

from .stock_purchase import build_stock_purchase_report


class StockPurchaseReportTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.warehouse = Warehouse.objects.create(name="Report Warehouse", code="RPT-WH", is_default=True)
        self.other_warehouse = Warehouse.objects.create(name="Other Warehouse", code="RPT-OTHER")
        self.category = Category.objects.create(name="Report Category", slug="report-category")
        self.brand = Brand.objects.create(name="Report Brand", slug="report-brand")
        self.product = Product.objects.create(
            public_id="report-product",
            name="Report Product",
            slug="report-product",
            category=self.category,
            brand=self.brand,
            regular_price=Decimal("100.00"),
            status=Product.Status.ACTIVE,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            name="Default",
            sku="RPT-SKU-1",
            stock_quantity=5,
            is_default=True,
            is_active=True,
        )
        balance, _ = InventoryBalance.objects.get_or_create(
            warehouse=self.warehouse,
            variant=self.variant,
            defaults={"on_hand": 5, "reserved_quantity": 1, "low_stock_threshold": 4},
        )
        balance.on_hand = 5
        balance.reserved_quantity = 1
        balance.low_stock_threshold = 4
        balance.save(update_fields=["on_hand", "reserved_quantity", "low_stock_threshold", "updated_at"])
        InventoryBalance.objects.get_or_create(
            warehouse=self.other_warehouse,
            variant=self.variant,
            defaults={"on_hand": 0, "reserved_quantity": 0, "low_stock_threshold": 2},
        )

        StockMovement.objects.create(
            warehouse=self.warehouse,
            variant=self.variant,
            sku_snapshot=self.variant.sku,
            product_snapshot=self.product.name,
            movement_type=StockMovement.Type.PURCHASE_IN,
            quantity_delta=5,
            quantity_after=5,
            reserved_after=0,
            reference_type="purchase",
            reference_no="PO-RPT-1",
        )
        StockMovement.objects.create(
            warehouse=self.warehouse,
            variant=self.variant,
            sku_snapshot=self.variant.sku,
            product_snapshot=self.product.name,
            movement_type=StockMovement.Type.RESERVE,
            quantity_delta=0,
            reserved_delta=1,
            quantity_after=5,
            reserved_after=1,
            reference_type="sales",
            reference_no="SALE-RPT-1",
        )

        self.supplier = Supplier.objects.create(code="SUP-RPT", name="Report Supplier", opening_balance=Decimal("20.00"))
        self.purchase = PurchaseOrder.objects.create(
            po_number="PO-RPT-1",
            supplier=self.supplier,
            warehouse=self.warehouse,
            status=PurchaseOrder.Status.RECEIVED,
            purchase_date=self.today,
        )
        self.purchase_item = PurchaseOrderItem.objects.create(
            purchase=self.purchase,
            variant=self.variant,
            ordered_quantity=5,
            received_quantity=5,
            returned_quantity=1,
            unit_cost=Decimal("40.00"),
        )
        receipt = PurchaseReceipt.objects.create(
            receipt_no="GRN-RPT-1",
            purchase=self.purchase,
            warehouse=self.warehouse,
            received_date=self.today,
        )
        PurchaseReceiptItem.objects.create(receipt=receipt, purchase_item=self.purchase_item, quantity=5)
        PurchasePayment.objects.create(
            payment_no="PP-RPT-1",
            purchase=self.purchase,
            supplier=self.supplier,
            amount=Decimal("50.00"),
            method=PurchasePayment.Method.CASH,
            payment_date=self.today,
        )
        purchase_return = PurchaseReturn.objects.create(
            return_no="PRET-RPT-1",
            purchase=self.purchase,
            supplier=self.supplier,
            warehouse=self.warehouse,
            return_date=self.today,
            reason="Test return",
        )
        PurchaseReturnItem.objects.create(
            purchase_return=purchase_return,
            purchase_item=self.purchase_item,
            quantity=1,
            unit_cost=Decimal("40.00"),
        )

        self.group = CustomerGroup.objects.get(code="RETAIL")
        self.customer = Customer.objects.create(
            name="Due Customer",
            phone="01700000991",
            group=self.group,
            opening_due=Decimal("10.00"),
        )
        self.sales_order = SalesOrder.objects.create(
            order_number="SALE-RPT-1",
            customer=self.customer,
            warehouse=self.warehouse,
            channel=SalesOrder.Channel.ONLINE,
            status=SalesOrder.Status.COMPLETED,
            payment_status=SalesOrder.PaymentStatus.PARTIAL,
            order_date=self.today,
            shipping_name=self.customer.name,
            shipping_phone=self.customer.phone,
            subtotal=Decimal("100.00"),
            grand_total=Decimal("100.00"),
            amount_paid=Decimal("40.00"),
        )
        PaymentTransaction.objects.create(
            transaction_no="PMT-RPT-1",
            sales_order=self.sales_order,
            kind=PaymentTransaction.Kind.SALE_PAYMENT,
            direction=PaymentTransaction.Direction.IN,
            method="cash",
            status=PaymentTransaction.Status.COMPLETED,
            amount=Decimal("40.00"),
            transaction_date=self.today,
        )

    def params(self, report, **extra):
        return {
            "report": report,
            "date_from": self.today.isoformat(),
            "date_to": self.today.isoformat(),
            **extra,
        }

    def test_stock_valuation_and_low_stock_use_weighted_cost_and_snapshot(self):
        stock = build_stock_purchase_report(self.params("stock", warehouse=str(self.warehouse.pk)))
        self.assertEqual(stock["rows"][0]["csv"][3], 5)
        self.assertEqual(stock["rows"][0]["csv"][5], 4)
        self.assertEqual(stock["rows"][0]["csv"][7], Decimal("40.00"))
        self.assertEqual(stock["rows"][0]["csv"][8], Decimal("200.00"))

        valuation = build_stock_purchase_report(self.params("stock_valuation", warehouse=str(self.warehouse.pk)))
        self.assertEqual(valuation["kpis"][-1]["value"], Decimal("200.00"))

        low = build_stock_purchase_report(self.params("low_stock", warehouse=str(self.warehouse.pk)))
        self.assertEqual(len(low["rows"]), 1)
        self.assertEqual(low["rows"][0]["csv"][5], 4)

    def test_stock_movement_filters_by_warehouse_and_type(self):
        report = build_stock_purchase_report(self.params(
            "stock_movement",
            warehouse=str(self.warehouse.pk),
            movement_type=StockMovement.Type.RESERVE,
        ))
        self.assertEqual(len(report["rows"]), 1)
        self.assertEqual(report["rows"][0]["csv"][2], "Reserve Stock")
        self.assertEqual(report["rows"][0]["csv"][8], "SALE-RPT-1")

    def test_purchase_report_calculates_returns_payments_and_outstanding_as_of_date(self):
        report = build_stock_purchase_report(self.params("purchase", warehouse=str(self.warehouse.pk)))
        row = report["rows"][0]["csv"]
        self.assertEqual(row[7], Decimal("200.00"))
        self.assertEqual(row[8], Decimal("40.00"))
        self.assertEqual(row[9], Decimal("50.00"))
        self.assertEqual(row[10], Decimal("110.00"))
        self.assertEqual(report["kpis"][-1]["value"], Decimal("110.00"))

    def test_supplier_due_includes_opening_purchase_return_and_payment(self):
        report = build_stock_purchase_report(self.params("supplier_due"))
        row = report["rows"][0]["csv"]
        self.assertEqual(row[2], Decimal("20.00"))
        self.assertEqual(row[3], Decimal("200.00"))
        self.assertEqual(row[4], Decimal("40.00"))
        self.assertEqual(row[5], Decimal("50.00"))
        self.assertEqual(row[6], Decimal("130.00"))

    def test_customer_due_uses_opening_sales_and_payment_as_of_date(self):
        report = build_stock_purchase_report(self.params("customer_due"))
        row = next(row["csv"] for row in report["rows"] if row["csv"][0] == self.customer.name)
        self.assertEqual(row[2], Decimal("10.00"))
        self.assertEqual(row[4], Decimal("100.00"))
        self.assertEqual(row[6], Decimal("40.00"))
        self.assertEqual(row[7], Decimal("70.00"))

    def test_operational_report_views_render_and_csv_export(self):
        url = reverse("backoffice:reports")
        response = self.client.get(url, self.params("stock"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Stock Report")
        self.assertContains(response, "RPT-SKU-1")
        self.assertContains(response, "Supplier Due")

        csv_response = self.client.get(url, {**self.params("purchase"), "export": "csv"})
        self.assertEqual(csv_response.status_code, 200)
        self.assertEqual(csv_response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn(b"PO-RPT-1", csv_response.content)
