from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounting.models import JournalEntry
from accounting.services import SYSTEM_ACCOUNTS, post_journal
from catalog.models import Brand, Category, Product, ProductVariant
from inventory.models import Warehouse
from sales.models import SalesOrder, SalesOrderItem

from .services import build_sales_profit_report


class SalesProfitReportTests(TestCase):
    def setUp(self):
        self.warehouse = Warehouse.objects.create(name="Report Warehouse", code="RPT-WH", is_default=True, is_active=True)
        self.category = Category.objects.create(name="Report Audio", slug="report-audio")
        self.brand = Brand.objects.create(name="Report Brand", slug="report-brand")
        self.product = Product.objects.create(public_id="report-product", name="Report Earbuds", slug="report-earbuds", category=self.category, brand=self.brand, regular_price=Decimal("100.00"), status=Product.Status.ACTIVE)
        self.variant = ProductVariant.objects.create(product=self.product, name="Black", sku="RPT-BLK", is_default=True, is_active=True, stock_quantity=0)
        self.online = self._completed_order("RPT-ONLINE-1", SalesOrder.Channel.ONLINE, date(2026, 9, 7), Decimal("200.00"), Decimal("20.00"), 2, Decimal("120.00"))
        self.pos = self._completed_order("RPT-POS-1", SalesOrder.Channel.POS, date(2026, 9, 8), Decimal("100.00"), Decimal("0.00"), 1, Decimal("50.00"))

    def _completed_order(self, number, channel, order_date, subtotal, shipping, quantity, cogs):
        order = SalesOrder.objects.create(order_number=number, warehouse=self.warehouse, channel=channel, status=SalesOrder.Status.COMPLETED, order_date=order_date, subtotal=subtotal, discount_amount=Decimal("0.00"), shipping_charge=shipping, grand_total=subtotal + shipping, shipping_name="Report Customer", shipping_phone="01700000000")
        SalesOrderItem.objects.create(order=order, variant=self.variant, product_snapshot=self.product.name, variant_snapshot=self.variant.name, sku_snapshot=self.variant.sku, quantity=quantity, unit_price=Decimal("100.00"), issued_quantity=quantity)
        post_journal(entry_date=order_date, source_type=JournalEntry.SourceType.SALE, source_key=f"sales_order:{order.pk}:cogs", source_reference=order.order_number, description=f"Report COGS {number}", lines=[{"account": SYSTEM_ACCOUNTS["cogs"], "debit": cogs, "credit": Decimal("0.00")}, {"account": SYSTEM_ACCOUNTS["inventory"], "debit": Decimal("0.00"), "credit": cogs}], actor="Report Test")
        return order

    def params(self, report="sales", **extra):
        return {"report": report, "date_from": "2026-09-01", "date_to": "2026-09-30", **extra}

    def test_sales_summary_uses_completed_order_and_posted_cogs(self):
        result = build_sales_profit_report(self.params())
        self.assertEqual(result["summary"]["orders"], 2)
        self.assertEqual(result["summary"]["units"], 3)
        self.assertEqual(result["summary"]["net_sales"], Decimal("320.00"))
        self.assertEqual(result["summary"]["cogs"], Decimal("170.00"))
        self.assertEqual(result["summary"]["profit"], Decimal("150.00"))

    def test_channel_filter_and_channel_report(self):
        result = build_sales_profit_report(self.params("channel", channel=SalesOrder.Channel.POS))
        self.assertEqual(result["summary"]["orders"], 1)
        self.assertEqual(result["summary"]["net_sales"], Decimal("100.00"))
        self.assertEqual(len(result["rows"]), 1)
        self.assertEqual(result["rows"][0]["csv"][0], "POS")

    def test_daily_monthly_product_category_and_brand_reports(self):
        daily = build_sales_profit_report(self.params("daily"))
        monthly = build_sales_profit_report(self.params("monthly"))
        product = build_sales_profit_report(self.params("product"))
        category = build_sales_profit_report(self.params("category"))
        brand = build_sales_profit_report(self.params("brand"))
        self.assertEqual(len(daily["rows"]), 2)
        self.assertEqual(len(monthly["rows"]), 1)
        self.assertEqual(product["rows"][0]["csv"][0], "Report Earbuds")
        self.assertEqual(product["rows"][0]["csv"][2], Decimal("300.00"))
        self.assertEqual(product["rows"][0]["csv"][3], Decimal("170.00"))
        self.assertEqual(category["rows"][0]["csv"][0], "Report Audio")
        self.assertEqual(brand["rows"][0]["csv"][0], "Report Brand")

    def test_profit_and_cogs_views_render_and_csv_exports(self):
        url = reverse("backoffice:reports")
        response = self.client.get(url, self.params("profit"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Profit Report")
        self.assertContains(response, "RPT-ONLINE-1")
        response = self.client.get(url, {**self.params("cogs"), "export": "csv"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        body = response.content.decode("utf-8-sig")
        self.assertIn("Original COGS", body)
        self.assertIn("RPT-POS-1", body)

    def test_reversed_date_range_is_normalized(self):
        result = build_sales_profit_report({"report": "sales", "date_from": "2026-09-30", "date_to": "2026-09-01"})
        self.assertEqual(result["filters"]["date_from"], date(2026, 9, 1))
        self.assertEqual(result["filters"]["date_to"], date(2026, 9, 30))
