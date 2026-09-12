from django.template import Context
from django.test import SimpleTestCase

from backoffice.templatetags.notification_tags import collect_toast_messages


class BackofficeToastNotificationTests(SimpleTestCase):
    def test_collects_action_notices_and_errors(self):
        context = Context({
            "catalog_notice": "Product created successfully.",
            "inventory_error": "Warehouse cannot be deleted.",
        })

        items = collect_toast_messages(context)

        self.assertIn(
            {"level": "success", "message": "Product created successfully.", "source": "catalog_notice"},
            items,
        )
        self.assertIn(
            {"level": "error", "message": "Warehouse cannot be deleted.", "source": "inventory_error"},
            items,
        )

    def test_keeps_form_errors_inline(self):
        context = Context({
            "purchase_form_error": "Please correct the highlighted purchase fields.",
            "purchase_notice": "Purchase order saved successfully.",
        })

        items = collect_toast_messages(context)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["message"], "Purchase order saved successfully.")

    def test_deduplicates_same_notification(self):
        context = Context({
            "catalog_notice": "Product updated successfully.",
            "inventory_notice": "Product updated successfully.",
        })

        items = collect_toast_messages(context)

        self.assertEqual(len(items), 1)
