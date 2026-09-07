from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from .forms import CustomerForm
from .models import Customer, CustomerGroup
from .services import CustomerError, delete_customer, delete_customer_group


class CustomerModelTests(TestCase):
    def setUp(self):
        self.group = CustomerGroup.objects.get(code="RETAIL")
        self.customer = Customer.objects.create(
            name="Tanvir Hasan",
            phone="01711111111",
            email="tanvir@example.com",
            group=self.group,
            source=Customer.Source.FACEBOOK,
            address="Mirpur",
            city="Dhaka",
            credit_limit=Decimal("5000.00"),
            opening_due=Decimal("250.00"),
        )

    def test_default_groups_are_seeded(self):
        self.assertTrue(CustomerGroup.objects.filter(code="RETAIL").exists())
        self.assertTrue(CustomerGroup.objects.filter(code="WHOLESALE").exists())
        self.assertTrue(CustomerGroup.objects.filter(code="VIP").exists())

    def test_customer_number_and_base_metrics(self):
        self.assertTrue(self.customer.customer_no.startswith("CUST-"))
        self.assertEqual(self.customer.order_count, 0)
        self.assertEqual(self.customer.total_spent, Decimal("0.00"))
        self.assertEqual(self.customer.due_balance, Decimal("250.00"))
        self.assertFalse(self.customer.repeat_customer)

    def test_customer_form_blocks_duplicate_phone_and_email(self):
        form = CustomerForm(data={
            "name": "Another",
            "phone": "01711111111",
            "email": "TANVIR@example.com",
            "source": Customer.Source.ONLINE,
            "credit_limit": "0.00",
            "opening_due": "0.00",
            "is_active": "on",
        })
        self.assertFalse(form.is_valid())
        self.assertIn("phone", form.errors)
        self.assertIn("email", form.errors)

    def test_customer_and_group_deletes_protect_history_links(self):
        with self.assertRaises(CustomerError):
            delete_customer_group(group=self.group)
        unused = CustomerGroup.objects.create(name="Unused", code="UNUSED")
        delete_customer_group(group=unused)
        self.assertFalse(CustomerGroup.objects.filter(code="UNUSED").exists())


class CustomerDashboardTests(TestCase):
    def setUp(self):
        self.group = CustomerGroup.objects.get(code="RETAIL")
        self.customer = Customer.objects.create(name="Dashboard Customer", phone="01811111111", group=self.group)

    def test_customer_pages_render_from_database(self):
        response = self.client.get(reverse("backoffice:customers"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dashboard Customer")
        response = self.client.get(reverse("backoffice:customer_detail_id", args=[self.customer.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.customer.customer_no)
        response = self.client.get(reverse("backoffice:customer_groups"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Retail")

    def test_customer_form_creates_real_customer(self):
        response = self.client.post(reverse("backoffice:customer_add"), {
            "name": "New Customer",
            "phone": "01922222222",
            "email": "new@example.com",
            "group": self.group.pk,
            "source": Customer.Source.REFERRAL,
            "address": "Dhanmondi",
            "district": "Dhaka",
            "city": "Dhaka",
            "postal_code": "1209",
            "credit_limit": "10000.00",
            "opening_due": "100.00",
            "notes": "Priority client",
            "is_active": "on",
        })
        self.assertEqual(response.status_code, 302)
        customer = Customer.objects.get(phone="01922222222")
        self.assertEqual(customer.group, self.group)
        self.assertEqual(customer.source, Customer.Source.REFERRAL)

    def test_customer_delete_without_sales_history(self):
        response = self.client.post(reverse("backoffice:customer_delete", args=[self.customer.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Customer.objects.filter(pk=self.customer.pk).exists())
