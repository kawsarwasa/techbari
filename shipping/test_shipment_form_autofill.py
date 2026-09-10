from decimal import Decimal

from django.urls import reverse

from .models import Shipment
from .tests import ShippingBase


class ShipmentFormAutofillTests(ShippingBase):
    def test_dashboard_shipment_uses_order_outstanding_even_if_zero_is_posted(self):
        self.confirm()
        self.courier.default_courier_fee = Decimal("25.00")
        self.courier.save(update_fields=["default_courier_fee", "updated_at"])

        response = self.client.post(
            reverse("backoffice:shipment_add"),
            {
                "order": self.order.pk,
                "courier": self.courier.pk,
                "shipment_date": "2026-09-07",
                "expected_delivery_date": "",
                "tracking_id": "",
                "courier_reference": "",
                "parcel_count": "1",
                "weight_kg": "0.00",
                "courier_fee": "",
                "cod_expected": "0.00",
                "notes": "Auto COD test",
            },
        )

        self.assertEqual(response.status_code, 302)
        shipment = Shipment.objects.get(order=self.order)
        self.assertEqual(shipment.cod_expected, Decimal("100.00"))
        self.assertEqual(shipment.courier_fee, Decimal("25.00"))
        self.assertEqual(shipment.cod_status, Shipment.CODStatus.PENDING)

    def test_shipment_add_page_exposes_order_financial_metadata(self):
        self.confirm()
        response = self.client.get(reverse("backoffice:shipment_add") + f"?order={self.order.pk}")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-outstanding="100.00"')
        self.assertContains(response, 'data-shipping-charge="0.00"')
        self.assertContains(response, "Customer Shipping Charge")
        self.assertContains(response, "COD Expected")
        self.assertContains(response, "readonly")
