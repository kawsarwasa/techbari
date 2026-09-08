import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from catalog.models import Brand, Category, Product, ProductVariant
from customers.models import Customer, CustomerGroup
from inventory.models import InventoryBalance, Warehouse
from sales.models import SalesOrder
from serial_tracking.models import SerializedUnit
from shipping.models import CourierProvider, Shipment, ShipmentEvent
from store_settings.models import StoreSettings

from .models import CustomerAccount, SavedAddress, WishlistItem
from .services import register_customer_account


PASSWORD = "StrongPass123!"


class CustomerAccountPhaseTests(TestCase):
    def setUp(self):
        self.group, _ = CustomerGroup.objects.get_or_create(name="Retail", code="RETAIL", defaults={"is_active": True})
        self.warehouse = Warehouse.objects.filter(is_default=True).first()
        if not self.warehouse:
            self.warehouse = Warehouse.objects.create(name="Main Warehouse", code="MAIN-V270", is_default=True, is_active=True)
        self.category = Category.objects.create(name="V270 Audio", slug="v270-audio")
        self.brand = Brand.objects.create(name="V270 Brand", slug="v270-brand")
        self.product = Product.objects.create(public_id="v270-earbuds", name="V270 Earbuds", slug="v270-earbuds", category=self.category, brand=self.brand, regular_price=Decimal("1000.00"), status=Product.Status.ACTIVE)
        self.variant = ProductVariant.objects.create(product=self.product, name="Black", sku="V270-BLK", stock_quantity=10, is_default=True, is_active=True)

    def make_account(self, phone="01710000001", email="one@example.com", name="Customer One"):
        return register_customer_account(name=name, phone=phone, email=email, password=PASSWORD)

    def make_order(self, customer, order_number, status=SalesOrder.Status.PENDING, total=Decimal("1000.00")):
        return SalesOrder.objects.create(order_number=order_number, customer=customer, warehouse=self.warehouse, channel=SalesOrder.Channel.ONLINE, status=status, payment_status=SalesOrder.PaymentStatus.UNPAID, subtotal=total, grand_total=total, shipping_name=customer.name, shipping_phone=customer.phone, shipping_email=customer.email, shipping_address="Dhaka")

    def registration_payload(self, **overrides):
        data = {"name": "New Buyer", "phone": "01720000001", "email": "new@example.com", "previous_order_number": "", "password1": PASSWORD, "password2": PASSWORD, "terms": "on"}
        data.update(overrides)
        return data

    def test_register_creates_non_staff_account_and_crm_customer(self):
        response = self.client.post(reverse("storefront:register"), self.registration_payload())
        self.assertEqual(response.status_code, 302)
        account = CustomerAccount.objects.select_related("customer", "user").get(customer__phone="01720000001")
        self.assertFalse(account.user.is_staff)
        self.assertEqual(account.customer.email, "new@example.com")
        self.assertIsNotNone(account.link_verified_at)
        self.assertEqual(Customer.objects.filter(phone="01720000001").count(), 1)
        self.assertEqual(int(self.client.session["_auth_user_id"]), account.user_id)

    def test_existing_buyer_requires_matching_previous_order_and_is_not_duplicated(self):
        customer = Customer.objects.create(name="Existing Buyer", phone="01720000002", email="existing@example.com", group=self.group, source=Customer.Source.ONLINE)
        self.make_order(customer, "TB-260908-EXIST1", status=SalesOrder.Status.COMPLETED)
        missing = self.client.post(reverse("storefront:register"), self.registration_payload(phone=customer.phone, email=customer.email))
        self.assertEqual(missing.status_code, 200)
        self.assertContains(missing, "previous TechBari order number")
        ok = self.client.post(reverse("storefront:register"), self.registration_payload(phone=customer.phone, email=customer.email, previous_order_number="TB-260908-EXIST1"))
        self.assertEqual(ok.status_code, 302)
        account = CustomerAccount.objects.get(customer=customer)
        self.assertEqual(account.customer_id, customer.pk)
        self.assertEqual(Customer.objects.filter(phone=customer.phone).count(), 1)

    def test_existing_buyer_rejects_wrong_order_challenge(self):
        customer = Customer.objects.create(name="Existing Buyer", phone="01720000003", email="three@example.com", group=self.group)
        self.make_order(customer, "TB-260908-REAL03")
        response = self.client.post(reverse("storefront:register"), self.registration_payload(phone=customer.phone, email=customer.email, previous_order_number="TB-260908-WRONG"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "could not be verified")
        self.assertFalse(CustomerAccount.objects.filter(customer=customer).exists())

    def test_existing_buyer_rejects_mismatched_email(self):
        customer = Customer.objects.create(name="Existing Buyer", phone="01720000004", email="known@example.com", group=self.group)
        response = self.client.post(reverse("storefront:register"), self.registration_payload(phone=customer.phone, email="attacker@example.com"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "email already linked")
        self.assertFalse(CustomerAccount.objects.filter(customer=customer).exists())

    def test_customer_login_works_by_phone_and_email_but_staff_portal_user_is_rejected(self):
        account = self.make_account()
        phone_login = self.client.post(reverse("storefront:login"), {"identity": account.customer.phone, "password": PASSWORD, "remember": "on"})
        self.assertEqual(phone_login.status_code, 302)
        self.client.post(reverse("storefront:logout"))
        email_login = self.client.post(reverse("storefront:login"), {"identity": account.customer.email, "password": PASSWORD})
        self.assertEqual(email_login.status_code, 302)
        self.client.post(reverse("storefront:logout"))
        staff = get_user_model().objects.create_user(username="staff-v270", email="staff-v270@example.com", password=PASSWORD, is_staff=True)
        denied = self.client.post(reverse("storefront:login"), {"identity": staff.email, "password": PASSWORD})
        self.assertEqual(denied.status_code, 200)
        self.assertContains(denied, "Invalid email/phone or password")

    def test_account_dashboard_requires_customer_login(self):
        response = self.client.get(reverse("customer_accounts:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])
        account = self.make_account(phone="01710000005", email="five@example.com")
        self.client.force_login(account.user)
        allowed = self.client.get(reverse("customer_accounts:dashboard"))
        self.assertEqual(allowed.status_code, 200)
        self.assertContains(allowed, account.customer.name)

    def test_order_detail_is_scoped_to_linked_customer(self):
        account = self.make_account(phone="01710000006", email="six@example.com")
        other = self.make_account(phone="01710000007", email="seven@example.com", name="Other Buyer")
        own_order = self.make_order(account.customer, "TB-260908-OWN006")
        other_order = self.make_order(other.customer, "TB-260908-OTH007")
        self.client.force_login(account.user)
        self.assertEqual(self.client.get(reverse("customer_accounts:order_detail", args=[own_order.order_number])).status_code, 200)
        self.assertEqual(self.client.get(reverse("customer_accounts:order_detail", args=[other_order.order_number])).status_code, 404)

    def test_public_tracking_requires_matching_order_phone(self):
        account = self.make_account(phone="01710000008", email="eight@example.com")
        order = self.make_order(account.customer, "TB-260908-TRK008")
        ok = self.client.post(reverse("storefront:track_order"), {"order_number": order.order_number, "phone": account.customer.phone})
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.context["tracked_order"], order)
        bad = self.client.post(reverse("storefront:track_order"), {"order_number": order.order_number, "phone": "01719999999"})
        self.assertIsNone(bad.context["tracked_order"])
        self.assertContains(bad, "Order not found")

    def test_database_wishlist_toggle_and_header_count(self):
        account = self.make_account(phone="01710000009", email="nine@example.com")
        self.client.force_login(account.user)
        add = self.client.post(reverse("storefront:wishlist_toggle", args=[self.product.public_id]), {"next": reverse("storefront:products")})
        self.assertEqual(add.status_code, 302)
        self.assertTrue(WishlistItem.objects.filter(account=account, product=self.product).exists())
        page = self.client.get(reverse("storefront:wishlist"))
        self.assertEqual(page.status_code, 200)
        self.assertEqual(page.context["customer_wishlist_count"], 1)
        self.assertContains(page, self.product.name)
        self.client.post(reverse("storefront:wishlist_toggle", args=[self.product.public_id]))
        self.assertFalse(WishlistItem.objects.filter(account=account, product=self.product).exists())

    def test_saved_address_default_invariant(self):
        account = self.make_account(phone="01710000010", email="ten@example.com")
        self.client.force_login(account.user)
        base = {"label": "Home", "recipient_name": "Customer Ten", "phone": account.customer.phone, "division": "Dhaka", "district": "Dhaka", "upazila": "Dhanmondi", "address": "Road 1", "landmark": "", "postal_code": "1209"}
        self.client.post(reverse("customer_accounts:address_add"), base)
        first = SavedAddress.objects.get(account=account)
        self.assertTrue(first.is_default)
        second_data = {**base, "label": "Office", "address": "Road 2", "is_default": "on"}
        self.client.post(reverse("customer_accounts:address_add"), second_data)
        first.refresh_from_db()
        second = SavedAddress.objects.get(account=account, label="Office")
        self.assertFalse(first.is_default)
        self.assertTrue(second.is_default)
        self.assertEqual(SavedAddress.objects.filter(account=account, is_default=True).count(), 1)

    def test_profile_update_syncs_crm_and_auth_email(self):
        account = self.make_account(phone="01710000011", email="eleven@example.com")
        self.client.force_login(account.user)
        response = self.client.post(reverse("customer_accounts:profile"), {"name": "Updated Customer", "email": "updated@example.com", "address": "House 11", "city": "Dhanmondi", "district": "Dhaka", "postal_code": "1209"})
        self.assertEqual(response.status_code, 302)
        account.customer.refresh_from_db()
        account.user.refresh_from_db()
        self.assertEqual(account.customer.name, "Updated Customer")
        self.assertEqual(account.customer.email, "updated@example.com")
        self.assertEqual(account.user.email, "updated@example.com")

    def test_password_change_keeps_session_valid(self):
        account = self.make_account(phone="01710000012", email="twelve@example.com")
        self.client.force_login(account.user)
        response = self.client.post(reverse("customer_accounts:password_change"), {"old_password": PASSWORD, "new_password1": "AnotherStrong456!", "new_password2": "AnotherStrong456!"})
        self.assertEqual(response.status_code, 302)
        account.user.refresh_from_db()
        self.assertTrue(account.user.check_password("AnotherStrong456!"))
        self.assertEqual(self.client.get(reverse("customer_accounts:dashboard")).status_code, 200)

    def test_warranty_lookup_only_returns_units_linked_to_customer_purchase(self):
        account = self.make_account(phone="01710000013", email="thirteen@example.com")
        own_order = self.make_order(account.customer, "TB-260908-WAR013", status=SalesOrder.Status.COMPLETED)
        other = self.make_account(phone="01710000014", email="fourteen@example.com")
        other_order = self.make_order(other.customer, "TB-260908-WAR014", status=SalesOrder.Status.COMPLETED)
        own_unit = SerializedUnit.objects.create(variant=self.variant, warehouse=self.warehouse, serial_number="SER-OWN-013", status=SerializedUnit.Status.SOLD, sales_reference=own_order.order_number, customer_reference=account.customer.phone, sold_at=timezone.localdate(), warranty_start_date=timezone.localdate(), warranty_end_date=timezone.localdate().replace(year=timezone.localdate().year + 1))
        other_unit = SerializedUnit.objects.create(variant=self.variant, warehouse=self.warehouse, serial_number="SER-OTHER-014", status=SerializedUnit.Status.SOLD, sales_reference=other_order.order_number, customer_reference=other.customer.phone)
        self.client.force_login(account.user)
        own_response = self.client.get(reverse("customer_accounts:warranty"), {"identifier": own_unit.serial_number})
        self.assertEqual(own_response.context["warranty_unit"], own_unit)
        denied = self.client.get(reverse("customer_accounts:warranty"), {"identifier": other_unit.serial_number})
        self.assertIsNone(denied.context["warranty_unit"])
        self.assertContains(denied, "linked to your TechBari purchases")

    def test_order_detail_exposes_owned_courier_tracking(self):
        account = self.make_account(phone="01710000015", email="fifteen@example.com")
        order = self.make_order(account.customer, "TB-260908-SHP015")
        courier = CourierProvider.objects.create(code="V270C", name="V270 Courier", tracking_url_template="https://courier.example/track/{tracking_id}")
        shipment = Shipment.objects.create(order=order, courier=courier, status=Shipment.Status.IN_TRANSIT, tracking_id="TRACK-015", last_location="Dhaka Hub")
        ShipmentEvent.objects.create(shipment=shipment, event=ShipmentEvent.Event.STATUS, new_status=Shipment.Status.IN_TRANSIT, location="Dhaka Hub")
        self.client.force_login(account.user)
        response = self.client.get(reverse("customer_accounts:order_detail", args=[order.order_number]))
        self.assertContains(response, "TRACK-015")
        self.assertContains(response, "Dhaka Hub")

    def test_logged_in_checkout_reuses_linked_crm_customer(self):
        account = self.make_account(phone="01710000016", email="sixteen@example.com")
        InventoryBalance.objects.update_or_create(warehouse=self.warehouse, variant=self.variant, defaults={"on_hand": 10, "reserved_quantity": 0, "low_stock_threshold": 2})
        self.client.force_login(account.user)
        get_response = self.client.get(reverse("storefront:checkout"))
        token = get_response.context["checkout_form"].initial["checkout_token"]
        payload = {"full_name": account.customer.name, "phone": account.customer.phone, "email": account.customer.email, "division": "Dhaka", "district": "Dhaka", "upazila": "Dhanmondi", "address": "House 16", "landmark": "", "delivery_option": "inside", "payment_method": "cod", "order_note": "", "coupon_code": "", "cart_payload": json.dumps([{"variant_id": self.variant.pk, "qty": 1}]), "checkout_token": token}
        response = self.client.post(reverse("storefront:checkout"), payload)
        self.assertEqual(response.status_code, 302)
        order = SalesOrder.objects.filter(customer=account.customer, order_number__startswith="TB-").order_by("-id").first()
        self.assertIsNotNone(order)
        self.assertEqual(order.customer_id, account.customer_id)
        self.assertEqual(Customer.objects.filter(phone=account.customer.phone).count(), 1)

    def test_logged_in_checkout_rejects_another_customer_phone(self):
        account = self.make_account(phone="01710000017", email="seventeen@example.com")
        InventoryBalance.objects.update_or_create(warehouse=self.warehouse, variant=self.variant, defaults={"on_hand": 10, "reserved_quantity": 0, "low_stock_threshold": 2})
        self.client.force_login(account.user)
        token = self.client.get(reverse("storefront:checkout")).context["checkout_form"].initial["checkout_token"]
        payload = {"full_name": account.customer.name, "phone": "01719999998", "email": account.customer.email, "division": "Dhaka", "district": "Dhaka", "upazila": "Dhanmondi", "address": "House 17", "landmark": "", "delivery_option": "inside", "payment_method": "cod", "order_note": "", "coupon_code": "", "cart_payload": json.dumps([{"variant_id": self.variant.pk, "qty": 1}]), "checkout_token": token}
        response = self.client.post(reverse("storefront:checkout"), payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "mobile number linked to your profile")
        self.assertFalse(Customer.objects.filter(phone="01719999998").exists())

    def test_guest_checkout_setting_requires_customer_login(self):
        store = StoreSettings.get_solo()
        store.guest_checkout_enabled = False
        store.save()
        response = self.client.get(reverse("storefront:checkout"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith(reverse("storefront:login")))
        self.assertIn("next=/checkout/", response["Location"])
