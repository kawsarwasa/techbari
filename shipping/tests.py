from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from catalog.models import Brand, Category, Product, ProductVariant
from customers.models import Customer, CustomerGroup
from inventory.models import InventoryBalance, Warehouse
from payments.models import PaymentTransaction
from sales.models import SalesOrder
from sales.services import save_sales_order, transition_order

from .models import CODSettlement, CourierProvider, Shipment, ShipmentEvent
from .services import ShippingError, change_shipment_status, create_shipment, post_cod_settlement


class ShippingBase(TestCase):
    def setUp(self):
        self.warehouse = Warehouse.objects.create(name="Shipping Warehouse", code="SHIP-WH", is_default=True, is_active=True)
        self.category = Category.objects.create(name="Shipping Phones", slug="shipping-phones")
        self.brand = Brand.objects.create(name="Shipping Brand", slug="shipping-brand")
        self.product = Product.objects.create(
            public_id="shipping-phone",
            name="Shipping Phone",
            slug="shipping-phone",
            category=self.category,
            brand=self.brand,
            regular_price=Decimal("100.00"),
            status=Product.Status.ACTIVE,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            name="Black",
            sku="SHIP-PHONE-BLK",
            stock_quantity=5,
            is_default=True,
            is_active=True,
        )
        balance, _ = InventoryBalance.objects.get_or_create(
            warehouse=self.warehouse,
            variant=self.variant,
            defaults={"on_hand": 5, "reserved_quantity": 0, "low_stock_threshold": 1},
        )
        balance.on_hand = 5
        balance.reserved_quantity = 0
        balance.save(update_fields=["on_hand", "reserved_quantity", "updated_at"])
        ProductVariant.objects.filter(pk=self.variant.pk).update(stock_quantity=5)

        group = CustomerGroup.objects.get(code="RETAIL")
        self.customer = Customer.objects.create(
            name="Courier Customer",
            phone="01766666666",
            email="courier@example.com",
            group=group,
            address="Road 10",
            city="Dhaka",
            district="Dhaka",
        )
        self.courier = CourierProvider.objects.get(code="MANUAL")
        self.order = self.make_order()

    def make_order(self):
        order = save_sales_order(
            header_data={
                "order_number": "",
                "customer": self.customer,
                "warehouse": self.warehouse,
                "channel": SalesOrder.Channel.ONLINE,
                "status": SalesOrder.Status.PENDING,
                "order_date": date(2026, 9, 7),
                "shipping_name": "",
                "shipping_phone": "",
                "shipping_email": "",
                "shipping_address": "",
                "shipping_city": "",
                "shipping_district": "",
                "shipping_postal_code": "",
                "discount_amount": Decimal("0.00"),
                "shipping_charge": Decimal("0.00"),
                "amount_paid": Decimal("0.00"),
                "notes": "Shipping test",
            },
            item_rows=[{
                "variant": self.variant,
                "quantity": 1,
                "unit_price": Decimal("100.00"),
                "discount_amount": Decimal("0.00"),
            }],
            actor="Test",
        )
        return order

    def confirm(self, order=None):
        order = order or self.order
        return transition_order(order=order, new_status=SalesOrder.Status.CONFIRMED, actor="Test")

    def shipment(self, order=None, tracking_id=""):
        order = order or self.order
        self.confirm(order)
        return create_shipment(
            order=order,
            courier=self.courier,
            shipment_date=date(2026, 9, 7),
            tracking_id=tracking_id,
            actor="Test",
        )

    def handover(self, shipment):
        shipment = change_shipment_status(shipment=shipment, new_status=Shipment.Status.READY, actor="Test")
        return change_shipment_status(shipment=shipment, new_status=Shipment.Status.HANDED_OVER, actor="Test")


class ShippingServiceTests(ShippingBase):
    def test_seeded_courier_profiles_exist(self):
        self.assertTrue(CourierProvider.objects.filter(code="MANUAL", is_active=True).exists())
        self.assertTrue(CourierProvider.objects.filter(code="PATHAO").exists())
        self.assertTrue(CourierProvider.objects.filter(code="STEADFAST").exists())
        self.assertTrue(CourierProvider.objects.filter(code="REDX").exists())

    def test_shipment_requires_confirmed_order_and_is_unique_per_order(self):
        with self.assertRaises(ShippingError):
            create_shipment(order=self.order, courier=self.courier, actor="Test")
        self.confirm()
        shipment = create_shipment(order=self.order, courier=self.courier, actor="Test")
        self.assertEqual(shipment.cod_expected, Decimal("100.00"))
        self.assertEqual(shipment.cod_status, Shipment.CODStatus.PENDING)
        self.assertTrue(shipment.events.filter(event=ShipmentEvent.Event.CREATED).exists())
        with self.assertRaises(ShippingError):
            create_shipment(order=self.order, courier=self.courier, actor="Test")

    def test_courier_handover_completes_sales_order_and_issues_reserved_stock(self):
        shipment = self.handover(self.shipment())
        self.order.refresh_from_db()
        balance = InventoryBalance.objects.get(warehouse=self.warehouse, variant=self.variant)
        self.assertEqual(shipment.status, Shipment.Status.HANDED_OVER)
        self.assertIsNotNone(shipment.handed_over_at)
        self.assertEqual(self.order.status, SalesOrder.Status.COMPLETED)
        self.assertEqual(balance.on_hand, 4)
        self.assertEqual(balance.reserved_quantity, 0)

    def test_delivered_cod_settlement_posts_reconciled_sales_payment(self):
        shipment = self.handover(self.shipment())
        shipment = change_shipment_status(
            shipment=shipment,
            new_status=Shipment.Status.DELIVERED,
            cod_collected=Decimal("100.00"),
            actor="Test",
        )
        self.assertEqual(shipment.cod_status, Shipment.CODStatus.COLLECTED)
        settlement = post_cod_settlement(
            courier=self.courier,
            settlement_date=date(2026, 9, 8),
            payment_method="cash",
            shipment_amounts={shipment.pk: "100.00"},
            courier_deduction="10.00",
            actor="Test",
        )
        shipment.refresh_from_db()
        self.order.refresh_from_db()
        payment = settlement.items.get().payment_transaction
        self.assertEqual(settlement.gross_amount, Decimal("100.00"))
        self.assertEqual(settlement.net_received, Decimal("90.00"))
        self.assertEqual(shipment.cod_settled, Decimal("100.00"))
        self.assertEqual(shipment.cod_status, Shipment.CODStatus.SETTLED)
        self.assertEqual(payment.kind, PaymentTransaction.Kind.SALE_PAYMENT)
        self.assertEqual(payment.reconciliation_status, PaymentTransaction.ReconciliationStatus.RECONCILED)
        self.assertEqual(self.order.amount_paid, Decimal("100.00"))
        self.assertEqual(self.order.payment_status, SalesOrder.PaymentStatus.PAID)

    def test_short_cod_collection_remains_disputed_after_settling_collected_amount(self):
        shipment = self.handover(self.shipment())
        shipment = change_shipment_status(
            shipment=shipment,
            new_status=Shipment.Status.DELIVERED,
            cod_collected="80.00",
            actor="Test",
        )
        self.assertEqual(shipment.cod_status, Shipment.CODStatus.DISPUTED)
        post_cod_settlement(
            courier=self.courier,
            settlement_date=date(2026, 9, 8),
            payment_method="cash",
            shipment_amounts={shipment.pk: "80.00"},
            actor="Test",
        )
        shipment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(shipment.cod_status, Shipment.CODStatus.DISPUTED)
        self.assertEqual(self.order.outstanding_amount, Decimal("20.00"))

    def test_courier_return_does_not_silently_readd_inventory(self):
        shipment = self.handover(self.shipment())
        shipment = change_shipment_status(
            shipment=shipment,
            new_status=Shipment.Status.FAILED,
            failure_reason="Customer unavailable",
            actor="Test",
        )
        shipment = change_shipment_status(shipment=shipment, new_status=Shipment.Status.RETURNING, actor="Test")
        shipment = change_shipment_status(shipment=shipment, new_status=Shipment.Status.RETURNED, actor="Test")
        balance = InventoryBalance.objects.get(warehouse=self.warehouse, variant=self.variant)
        self.assertEqual(shipment.status, Shipment.Status.RETURNED)
        self.assertEqual(balance.on_hand, 4)
        self.assertEqual(shipment.cod_status, Shipment.CODStatus.DISPUTED)

    def test_tracking_id_is_unique_within_courier(self):
        first = self.shipment(tracking_id="TRACK-001")
        second_order = self.make_order()
        self.confirm(second_order)
        with self.assertRaises((ShippingError, ValidationError)):
            create_shipment(
                order=second_order,
                courier=self.courier,
                tracking_id=first.tracking_id,
                actor="Test",
            )

    def test_shipment_events_are_immutable(self):
        shipment = self.shipment()
        event = shipment.events.first()
        event.note = "tamper"
        with self.assertRaises(ValidationError):
            event.save()
        with self.assertRaises(ValidationError):
            event.delete()

    def test_over_settlement_is_blocked(self):
        shipment = self.handover(self.shipment())
        shipment = change_shipment_status(
            shipment=shipment,
            new_status=Shipment.Status.DELIVERED,
            cod_collected="100.00",
            actor="Test",
        )
        with self.assertRaises(ShippingError):
            post_cod_settlement(
                courier=self.courier,
                settlement_date=date(2026, 9, 8),
                payment_method="cash",
                shipment_amounts={shipment.pk: "101.00"},
                actor="Test",
            )
        self.assertEqual(CODSettlement.objects.count(), 0)


class ShippingDashboardTests(ShippingBase):
    def test_shipping_pages_render_and_form_creates_database_shipment(self):
        self.confirm()
        response = self.client.post(reverse("backoffice:shipment_add"), {
            "order": self.order.pk,
            "courier": self.courier.pk,
            "shipment_date": "2026-09-07",
            "expected_delivery_date": "2026-09-09",
            "tracking_id": "DASH-TRACK-1",
            "courier_reference": "CR-1",
            "parcel_count": "1",
            "weight_kg": "0.50",
            "courier_fee": "60.00",
            "cod_expected": "100.00",
            "notes": "Dashboard shipment",
        })
        self.assertEqual(response.status_code, 302)
        shipment = Shipment.objects.get(order=self.order)
        self.assertEqual(shipment.tracking_id, "DASH-TRACK-1")
        self.assertEqual(self.client.get(reverse("backoffice:shipping")).status_code, 200)
        self.assertEqual(self.client.get(reverse("backoffice:shipment_detail", args=[shipment.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("backoffice:courier_providers")).status_code, 200)
        self.assertEqual(self.client.get(reverse("backoffice:cod_settlements")).status_code, 200)

    def test_status_and_cod_settlement_dashboard_actions_post_real_transactions(self):
        shipment = self.shipment()
        self.assertEqual(self.client.post(reverse("backoffice:shipment_status", args=[shipment.pk]), {"new_status": "ready"}).status_code, 302)
        shipment.refresh_from_db()
        self.assertEqual(self.client.post(reverse("backoffice:shipment_status", args=[shipment.pk]), {"new_status": "handed_over"}).status_code, 302)
        shipment.refresh_from_db()
        self.assertEqual(self.client.post(reverse("backoffice:shipment_status", args=[shipment.pk]), {"new_status": "delivered", "cod_collected": "100.00"}).status_code, 302)
        shipment.refresh_from_db()
        response = self.client.post(reverse("backoffice:cod_settlement_add"), {
            "courier": self.courier.pk,
            "settlement_date": "2026-09-08",
            "payment_method": "cash",
            "reference": "",
            "courier_deduction": "5.00",
            "note": "Dashboard COD",
            "shipment_id": [str(shipment.pk)],
            f"amount_{shipment.pk}": "100.00",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(CODSettlement.objects.count(), 1)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, SalesOrder.PaymentStatus.PAID)
