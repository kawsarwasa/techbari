from datetime import timedelta
from decimal import Decimal

from django.test import Client, TestCase
from django.utils import timezone

from catalog.models import Brand, Category, Product, ProductVariant
from customers.models import Customer, CustomerGroup
from inventory.models import InventoryBalance, Warehouse
from purchasing.models import PurchaseOrder, PurchaseOrderItem, PurchasePayment, Supplier
from reports.services import build_sales_profit_report
from sales.models import SalesOrder, SalesOrderItem

from .dashboard_analytics import build_dashboard_context, parse_dashboard_period


class DashboardAnalyticsTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.category = Category.objects.create(name="Analytics Audio", slug="analytics-audio")
        self.brand = Brand.objects.create(name="Analytics Brand", slug="analytics-brand")
        self.product = Product.objects.create(
            public_id="analytics-product",
            name="Analytics Earbuds",
            slug="analytics-earbuds",
            category=self.category,
            brand=self.brand,
            regular_price=Decimal("100.00"),
            status=Product.Status.ACTIVE,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            name="Default",
            sku="AN-DASH-1",
            is_default=True,
            stock_quantity=10,
        )
        self.warehouse = Warehouse.objects.filter(is_default=True, is_active=True).order_by("id").first()
        if self.warehouse is None:
            self.warehouse = Warehouse.objects.create(name="Analytics Main", code="AN-MAIN", is_default=True)
        self.group, _ = CustomerGroup.objects.get_or_create(name="Retail", code="RETAIL")
        self.customer = Customer.objects.create(
            name="Dashboard Buyer",
            phone="01711112222",
            group=self.group,
            opening_due=Decimal("10.00"),
        )

    def make_sale(self, number, *, channel=SalesOrder.Channel.ONLINE, amount="100.00", days_ago=0, status=SalesOrder.Status.COMPLETED, paid=None):
        amount = Decimal(amount)
        order = SalesOrder.objects.create(
            order_number=number,
            customer=self.customer,
            warehouse=self.warehouse,
            channel=channel,
            status=status,
            payment_status=SalesOrder.PaymentStatus.PAID if paid is None and status == SalesOrder.Status.COMPLETED else SalesOrder.PaymentStatus.PARTIAL,
            order_date=self.today - timedelta(days=days_ago),
            subtotal=amount,
            grand_total=amount,
            amount_paid=amount if paid is None and status == SalesOrder.Status.COMPLETED else Decimal(paid or "0.00"),
        )
        SalesOrderItem.objects.create(
            order=order,
            variant=self.variant,
            product_snapshot=self.product.name,
            variant_snapshot=self.variant.name,
            sku_snapshot=self.variant.sku,
            quantity=1,
            issued_quantity=1 if status == SalesOrder.Status.COMPLETED else 0,
            unit_price=amount,
        )
        return order

    def test_dashboard_uses_real_sales_and_report_profit_semantics(self):
        self.make_sale("TB-DASH-ONLINE", amount="120.00")
        response = Client().get("/dashboard/?period=today")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["analytics_database"])
        self.assertEqual(response.context["dashboard_summary"]["net_sales"], Decimal("120.00"))
        report = build_sales_profit_report({"date_from": self.today.isoformat(), "date_to": self.today.isoformat(), "report": "sales"})
        self.assertEqual(response.context["dashboard_summary"]["profit"], report["summary"]["profit"])

    def test_pos_online_top_product_and_category_are_real(self):
        self.make_sale("TB-DASH-ONLINE-2", channel=SalesOrder.Channel.ONLINE, amount="100.00")
        self.make_sale("TB-DASH-POS-2", channel=SalesOrder.Channel.POS, amount="200.00")
        response = Client().get("/dashboard/?period=7d")
        channels = {row["_key"]: row for row in response.context["channel_rows"]}
        self.assertEqual(channels[SalesOrder.Channel.ONLINE]["net_sales"], Decimal("100.00"))
        self.assertEqual(channels[SalesOrder.Channel.POS]["net_sales"], Decimal("200.00"))
        self.assertEqual(response.context["top_products"][0]["product_name"], self.product.name)
        self.assertEqual(response.context["top_products"][0]["net_sales"], Decimal("300.00"))
        self.assertEqual(response.context["top_categories"][0]["label"], self.category.name)

    def test_customer_and_purchase_due_follow_business_outstanding_rules(self):
        self.make_sale("TB-DASH-DUE", amount="100.00", status=SalesOrder.Status.CONFIRMED, paid="30.00")
        supplier = Supplier.objects.create(code="AN-SUP", name="Analytics Supplier", opening_balance=Decimal("10.00"))
        purchase = PurchaseOrder.objects.create(
            po_number="PO-AN-DASH",
            supplier=supplier,
            warehouse=self.warehouse,
            status=PurchaseOrder.Status.ORDERED,
            purchase_date=self.today,
        )
        PurchaseOrderItem.objects.create(
            purchase=purchase,
            variant=self.variant,
            ordered_quantity=2,
            unit_cost=Decimal("50.00"),
        )
        PurchasePayment.objects.create(
            payment_no="PP-AN-DASH",
            purchase=purchase,
            supplier=supplier,
            amount=Decimal("25.00"),
            payment_date=self.today,
        )
        response = Client().get("/dashboard/")
        self.assertEqual(response.context["customer_due"], Decimal("80.00"))
        self.assertEqual(response.context["purchase_due"], Decimal("85.00"))

    def test_stock_alerts_use_available_quantity_and_threshold(self):
        InventoryBalance.objects.update_or_create(
            warehouse=self.warehouse,
            variant=self.variant,
            defaults={"on_hand": 5, "reserved_quantity": 3, "low_stock_threshold": 2},
        )
        response = Client().get("/dashboard/")
        row = next(row for row in response.context["stock_alert_rows"] if row["sku"] == self.variant.sku)
        self.assertEqual(row["available"], 2)
        self.assertEqual(row["severity"], "Low stock")

    def test_period_filter_excludes_old_sales(self):
        self.make_sale("TB-DASH-RECENT", amount="100.00", days_ago=1)
        self.make_sale("TB-DASH-OLD", amount="900.00", days_ago=10)
        response = Client().get("/dashboard/?period=7d")
        self.assertEqual(response.context["dashboard_summary"]["net_sales"], Decimal("100.00"))
        self.assertEqual(response.context["dashboard_period"]["key"], "7d")

    def test_custom_period_swaps_reversed_dates(self):
        period = parse_dashboard_period({"period": "custom", "date_from": "2026-09-08", "date_to": "2026-09-01"})
        self.assertEqual(period["date_from"].isoformat(), "2026-09-01")
        self.assertEqual(period["date_to"].isoformat(), "2026-09-08")

    def test_recent_activity_contains_real_order_and_purchase(self):
        self.make_sale("TB-DASH-ACTIVITY", amount="150.00")
        supplier = Supplier.objects.create(code="AN-ACT", name="Activity Supplier")
        PurchaseOrder.objects.create(
            po_number="PO-AN-ACTIVITY",
            supplier=supplier,
            warehouse=self.warehouse,
            status=PurchaseOrder.Status.ORDERED,
            purchase_date=self.today,
        )
        request = type("Request", (), {"GET": {}})()
        context = build_dashboard_context(request)
        titles = [row["title"] for row in context["recent_activity"]]
        self.assertTrue(any("TB-DASH-ACTIVITY" in title for title in titles))
        self.assertTrue(any("PO-AN-ACTIVITY" in title for title in titles))
