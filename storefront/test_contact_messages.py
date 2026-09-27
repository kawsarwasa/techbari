from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from integrations.models import Notification
from staff_access.permissions import sync_system_roles

from .models import ContactMessage


class ContactMessageFlowTests(TestCase):
    def payload(self, **overrides):
        data = {
            "name": "Rahim Ahmed",
            "email": "rahim@example.com",
            "phone": "01712345678",
            "subject": "Order Support",
            "message": "I need help with an order that has not arrived yet.",
            "website": "",
        }
        data.update(overrides)
        return data

    def test_public_contact_submission_is_saved_and_notified(self):
        response = self.client.post(
            reverse("storefront:contact"),
            self.payload(),
            REMOTE_ADDR="203.0.113.10",
        )
        self.assertRedirects(response, reverse("storefront:contact") + "?sent=1")

        message = ContactMessage.objects.get()
        self.assertEqual(message.name, "Rahim Ahmed")
        self.assertEqual(message.email, "rahim@example.com")
        self.assertEqual(message.phone, "01712345678")
        self.assertEqual(message.subject, "Order Support")
        self.assertEqual(message.status, ContactMessage.Status.NEW)
        self.assertEqual(message.source_ip, "203.0.113.10")

        notification = Notification.objects.get(reference_type="contact_message", reference_id=str(message.pk))
        self.assertEqual(notification.title, "New contact message")
        self.assertEqual(notification.link, reverse("backoffice:contact_message_detail", args=[message.pk]))

        success = self.client.get(reverse("storefront:contact") + "?sent=1")
        self.assertEqual(success.status_code, 200)
        self.assertContains(success, "Your message has been sent successfully")

    def test_contact_honeypot_rejects_submission(self):
        response = self.client.post(
            reverse("storefront:contact"),
            self.payload(website="https://spam.example"),
            REMOTE_ADDR="203.0.113.11",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ContactMessage.objects.count(), 0)
        self.assertContains(response, "Submission could not be accepted")

    def test_contact_rate_limit_blocks_sixth_message_from_same_ip(self):
        for index in range(5):
            ContactMessage.objects.create(
                name=f"Sender {index}",
                email=f"sender{index}@example.com",
                subject="Other",
                message="A valid earlier message for rate limit testing.",
                source_ip="203.0.113.12",
            )

        response = self.client.post(
            reverse("storefront:contact"),
            self.payload(email="sixth@example.com"),
            REMOTE_ADDR="203.0.113.12",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ContactMessage.objects.count(), 5)
        self.assertContains(response, "Too many messages were sent recently")

    def test_contact_inbox_uses_customer_permissions_and_status_workflow(self):
        sync_system_roles()
        message = ContactMessage.objects.create(
            name="Inbox Sender",
            email="inbox@example.com",
            subject="Product Question",
            message="Please tell me whether this product is currently available.",
        )

        denied = User.objects.create_user(username="inventory-contact-test", password="StrongPass123!", is_staff=True)
        denied.groups.add(Group.objects.get(name="Inventory Manager"))
        self.client.force_login(denied)
        self.assertEqual(self.client.get(reverse("backoffice:contact_messages")).status_code, 403)

        allowed = User.objects.create_user(username="sales-contact-test", password="StrongPass123!", is_staff=True)
        allowed.groups.add(Group.objects.get(name="Sales Staff"))
        self.client.force_login(allowed)

        listing = self.client.get(reverse("backoffice:contact_messages"))
        self.assertEqual(listing.status_code, 200)
        self.assertContains(listing, "Inbox Sender")

        detail = self.client.get(reverse("backoffice:contact_message_detail", args=[message.pk]))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "Please tell me whether")

        updated = self.client.post(
            reverse("backoffice:contact_message_status", args=[message.pk]),
            {"status": ContactMessage.Status.REPLIED},
        )
        self.assertRedirects(updated, reverse("backoffice:contact_message_detail", args=[message.pk]))
        message.refresh_from_db()
        self.assertEqual(message.status, ContactMessage.Status.REPLIED)
        self.assertEqual(message.handled_by, allowed)
        self.assertIsNotNone(message.first_read_at)
        self.assertIsNotNone(message.replied_at)
