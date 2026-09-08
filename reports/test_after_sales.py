from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounting.models import Account
from catalog.models import Brand, Category, Product, ProductVariant
from customers.models import Customer, CustomerGroup
from expenses.models import Expense, ExpenseCategory
from inventory.models import Warehouse
from payments.models import PaymentTransaction
from returns.models import SalesReturn, SalesReturnItem, SalesReturnRefund
from sales.models import SalesOrder, SalesOrderItem
from serial_tracking.models import SerializedUnit, WarrantyClaim

from .after_sales import build_after_sales_report


class AfterSalesReportTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.warehouse = Warehouse.objects.create(name="After Sales WH", code="AS-WH", is_default=True)
        self.other_warehouse = Warehouse.objects.create(name="After Sales Other", code="AS-OTHER")
        self.category = Category.objects.create(name="After Sales Category", slug="after-sales-category")
        self.brand = Brand.objects.create(name="After Sales Brand", slug="after-sales-brand")
        self.product = Product.objects.create(
            public_id="after-sales-product",
            name="After Sales Product",
            slug="after-sales-product",
            category=self.category,
            brand=self.brand,
            regular_price=Decimal("200.00"),
            status=Product.Status.ACTIVE,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            name="Default",
            sku="AS-SKU-1",
            stock_quantity=2,
            is_default=True,
            is_active=True,
        )
        self.group = CustomerGroup.objects.get(code="RETAIL")
        self.customer = Customer.objects.create(
            name="After Sales Customer",
            phone="01700000881",
            group=self.group,
        )
        self.order = SalesOrder.objects.create(
            order_number="SALE-AS-1",
            customer=self.customer,
            warehouse=self.warehouse,
            channel=SalesOrder.Channel.ONLINE,
            status=SalesOrder.Status.COMPLETED,
            payment_status=SalesOrder.PaymentStatus.PAID,
            order_date=self.today,
            shipping_name=self.customer.name,
            shipping_phone=self.customer.phone,
            subtotal=Decimal("200.00"),
            grand_total=Decimal("200.00"),
            amount_paid=Decimal("0.00"),
        )
        self.order_item = SalesOrderItem.objects.create(
            order=self.order,
            variant=self.variant,
            product_snapshot=self.product.name,
            variant_snapshot="Default",
            sku_snapshot=self.variant.sku,
            quantity=1,
            unit_price=Decimal("200.00"),
            issued_quantity=1,
        )
        self.payment = PaymentTransaction.objects.create(
            transaction_no="PMT-AS-IN",
            sales_order=self.order,
            kind=PaymentTransaction.Kind.SALE_PAYMENT,
            direction=PaymentTransaction.Direction.IN,
            method="cash",
            status=PaymentTransaction.Status.COMPLETED,
            amount=Decimal("150.00"),
            transaction_date=self.today,
            reconciliation_status=PaymentTransaction.ReconciliationStatus.RECONCILED,
            reconciled_at=timezone.now(),
        )
        self.refund = PaymentTransaction.objects.create(
            transaction_no="PMT-AS-OUT",
            sales_order=self.order,
            parent_transaction=self.payment,
            kind=PaymentTransaction.Kind.REFUND,
            direction=PaymentTransaction.Direction.OUT,
            method="cash",
            status=PaymentTransaction.Status.COMPLETED,
            amount=Decimal("20.00"),
            transaction_date=self.today,
        )

        self.expense_category = ExpenseCategory.objects.get(code="RENT")
        self.cash_account = Account.objects.get(code="1000")
        self.expense = Expense.objects.create(
            expense_no="EXP-AS-1",
            expense_date=self.today,
            category=self.expense_category,
            payee="Office Landlord",
            description="Monthly office rent",
            amount=Decimal("80.00"),
            payment_method=Expense.Method.CASH,
            payment_account=self.cash_account,
            payment_date=self.today,
            status=Expense.Status.PAID,
            paid_at=timezone.now(),
        )
        Expense.objects.create(
            expense_no="EXP-AS-2",
            expense_date=self.today,
            category=self.expense_category,
            description="Next rent approval",
            amount=Decimal("50.00"),
            status=Expense.Status.APPROVED,
        )
        Expense.objects.create(
            expense_no="EXP-AS-VOID",
            expense_date=self.today,
            category=self.expense_category,
            description="Voided rent",
            amount=Decimal("30.00"),
            status=Expense.Status.VOIDED,
        )

        self.sales_return = SalesReturn.objects.create(
            return_no="RET-AS-1",
            order=self.order,
            warehouse=self.warehouse,
            source=SalesReturn.Source.CUSTOMER,
            status=SalesReturn.Status.COMPLETED,
            resolution=SalesReturn.Resolution.REFUND,
            reason_category=SalesReturn.Reason.DEFECTIVE,
            requested_date=self.today,
            received_date=self.today,
            completed_date=self.today,
        )
        SalesReturnItem.objects.create(
            sales_return=self.sales_return,
            order_item=self.order_item,
            variant=self.variant,
            product_snapshot=self.product.name,
            sku_snapshot=self.variant.sku,
            quantity=1,
            condition=SalesReturnItem.Condition.DEFECTIVE,
            disposition=SalesReturnItem.Disposition.RESTOCK,
            refund_amount=Decimal("20.00"),
            restocked_quantity=1,
        )
        SalesReturnRefund.objects.create(
            sales_return=self.sales_return,
            source_payment=self.payment,
            refund_transaction=self.refund,
            amount=Decimal("20.00"),
        )

        self.unit = SerializedUnit.objects.create(
            variant=self.variant,
            warehouse=self.warehouse,
            serial_number="SER-AS-001",
            imei1="123456789012345",
            status=SerializedUnit.Status.WARRANTY_SERVICE,
            purchase_reference="PO-AS-1",
            purchase_date=self.today - timedelta(days=30),
            purchase_cost=Decimal("100.00"),
            received_date=self.today - timedelta(days=29),
            sales_reference=self.order.order_number,
            customer_reference=self.customer.customer_no,
            sold_at=self.today - timedelta(days=10),
            warranty_type="1 Year",
            warranty_start_date=self.today - timedelta(days=10),
            warranty_end_date=self.today + timedelta(days=355),
        )
        self.replacement = SerializedUnit.objects.create(
            variant=self.variant,
            warehouse=self.other_warehouse,
            serial_number="SER-AS-002",
            imei1="123456789012346",
            status=SerializedUnit.Status.SOLD,
            sales_reference=self.order.order_number,
            warranty_start_date=self.today,
            warranty_end_date=self.today + timedelta(days=365),
        )
        self.claim = WarrantyClaim.objects.create(
            claim_no="WC-AS-1",
            unit=self.unit,
            customer_name=self.customer.name,
            customer_phone=self.customer.phone,
            order_reference=self.order.order_number,
            claim_date=self.today,
            issue="Left earbud stopped working",
            status=WarrantyClaim.Status.REPLACED,
            resolution="Replaced under warranty",
            replacement_unit=self.replacement,
            resolved_at=self.today,
        )

    def params(self, report, **extra):
        return {
            "report": report,
            "date_from": self.today.isoformat(),
            "date_to": self.today.isoformat(),
            **extra,
        }

    def test_payment_report_uses_ledger_direction_status_and_reconciliation(self):
        report = build_after_sales_report(self.params("payment"))
        self.assertEqual(len(report["rows"]), 2)
        self.assertEqual(report["kpis"][1]["value"], Decimal("150.00"))
        self.assertEqual(report["kpis"][2]["value"], Decimal("20.00"))
        self.assertEqual(report["kpis"][3]["value"], Decimal("130.00"))
        self.assertEqual(report["kpis"][4]["value"], 1)

        refunds = build_after_sales_report(self.params("payment", payment_kind=PaymentTransaction.Kind.REFUND))
        self.assertEqual(len(refunds["rows"]), 1)
        self.assertEqual(refunds["rows"][0]["csv"][1], "PMT-AS-OUT")

    def test_expense_report_separates_active_and_paid_amounts(self):
        report = build_after_sales_report(self.params("expense"))
        self.assertEqual(len(report["rows"]), 3)
        self.assertEqual(report["kpis"][1]["value"], Decimal("130.00"))
        self.assertEqual(report["kpis"][2]["value"], Decimal("80.00"))
        self.assertEqual(report["kpis"][4]["value"], 1)

        paid = build_after_sales_report(self.params("expense", expense_status=Expense.Status.PAID))
        self.assertEqual(len(paid["rows"]), 1)
        self.assertEqual(paid["rows"][0]["csv"][1], "EXP-AS-1")

    def test_returns_report_summarizes_credit_refund_and_restock(self):
        report = build_after_sales_report(self.params("returns"))
        self.assertEqual(len(report["rows"]), 1)
        self.assertEqual(report["kpis"][2]["value"], 1)
        self.assertEqual(report["kpis"][3]["value"], 1)
        self.assertEqual(report["kpis"][4]["value"], Decimal("20.00"))
        self.assertEqual(report["kpis"][5]["value"], Decimal("20.00"))
        self.assertEqual(report["rows"][0]["csv"][1], "RET-AS-1")

    def test_warranty_and_serial_reports_filter_current_status_and_warehouse(self):
        warranty = build_after_sales_report(self.params("warranty", warranty_status=WarrantyClaim.Status.REPLACED))
        self.assertEqual(len(warranty["rows"]), 1)
        self.assertEqual(warranty["kpis"][3]["value"], 1)
        self.assertEqual(warranty["kpis"][4]["value"], 1)
        self.assertEqual(warranty["rows"][0]["csv"][10], "SER-AS-002")

        serials = build_after_sales_report(self.params(
            "serial_imei",
            serial_status=SerializedUnit.Status.WARRANTY_SERVICE,
            warehouse=str(self.warehouse.pk),
        ))
        self.assertEqual(len(serials["rows"]), 1)
        self.assertEqual(serials["rows"][0]["csv"][3], "SER-AS-001")
        self.assertEqual(serials["rows"][0]["csv"][4], "123456789012345")

    def test_after_sales_report_views_render_tabs_filters_and_csv(self):
        url = reverse("backoffice:reports")
        response = self.client.get(url, self.params("payment"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Payment Report")
        self.assertContains(response, "Serial / IMEI")
        self.assertContains(response, "PMT-AS-IN")

        expense_response = self.client.get(url, self.params("expense", expense_status=Expense.Status.PAID))
        self.assertEqual(expense_response.status_code, 200)
        self.assertContains(expense_response, "Expense Report")
        self.assertContains(expense_response, "EXP-AS-1")

        csv_response = self.client.get(url, {**self.params("returns"), "export": "csv"})
        self.assertEqual(csv_response.status_code, 200)
        self.assertEqual(csv_response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn(b"RET-AS-1", csv_response.content)
