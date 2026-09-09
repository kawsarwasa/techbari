from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from integrations.forms import IntegrationSettingsForm
from integrations.security import UnsafeOutboundURL, validate_outbound_url
from staff_access.models import AuthThrottle
from staff_access.security import clear_auth_throttle, register_auth_failure, throttle_seconds_remaining
from staff_access.services import get_client_ip
from store_settings.forms import validate_cms_image

from .checks import production_security_checks


class HealthAndHeadersTests(TestCase):
    def test_health_endpoint_checks_database_without_exposing_details(self):
        response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertIn("Permissions-Policy", response)
        self.assertEqual(response["Cross-Origin-Resource-Policy"], "same-site")

    def test_health_endpoint_returns_minimal_503_when_database_is_unavailable(self):
        with patch("techbari.views.connection.cursor", side_effect=RuntimeError("database secret detail")):
            response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "unavailable"})
        self.assertNotContains(response, "database secret detail", status_code=503)


class ProxyAndThrottleTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @override_settings(TRUST_X_FORWARDED_FOR=False)
    def test_client_ip_ignores_spoofed_forwarded_header_by_default(self):
        request = self.factory.get("/", REMOTE_ADDR="203.0.113.8", HTTP_X_FORWARDED_FOR="10.0.0.5")
        self.assertEqual(get_client_ip(request), "203.0.113.8")

    @override_settings(TRUST_X_FORWARDED_FOR=True)
    def test_client_ip_uses_forwarded_header_only_when_explicitly_trusted(self):
        request = self.factory.get("/", REMOTE_ADDR="203.0.113.8", HTTP_X_FORWARDED_FOR="198.51.100.2, 10.0.0.5")
        self.assertEqual(get_client_ip(request), "198.51.100.2")

    @override_settings(AUTH_FAILURE_LIMIT=3, AUTH_FAILURE_WINDOW=900, AUTH_LOCKOUT_SECONDS=600, TRUST_X_FORWARDED_FOR=False)
    def test_auth_throttle_locks_and_can_be_cleared(self):
        request = self.factory.post("/login/", REMOTE_ADDR="203.0.113.9")
        for _ in range(3):
            register_auth_failure("test", request, "person@example.com")
        self.assertGreater(throttle_seconds_remaining("test", request, "person@example.com"), 0)
        self.assertEqual(AuthThrottle.objects.count(), 1)
        clear_auth_throttle("test", request, "person@example.com")
        self.assertEqual(throttle_seconds_remaining("test", request, "person@example.com"), 0)


@override_settings(STAFF_AUTH_ENABLED=True)
class StaffIdentityBoundaryTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.customer_user = user_model.objects.create_user(username="customer-only", email="customer@example.com", password="StrongPass123!", is_staff=False)
        permission = Permission.objects.get(content_type__app_label="staff_access", codename="view_dashboard")
        self.customer_user.user_permissions.add(permission)
        self.admin = user_model.objects.create_superuser(username="root-admin", email="root@example.com", password="StrongPass123!")

    def test_customer_identity_is_denied_dashboard_even_with_accidental_permission(self):
        self.client.force_login(self.customer_user)
        response = self.client.get(reverse("backoffice:dashboard"))
        self.assertEqual(response.status_code, 403)

    def test_customer_credentials_cannot_sign_in_through_staff_login(self):
        response = self.client.post(reverse("backoffice:login"), {"username": self.customer_user.username, "password": "StrongPass123!"})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_staff_user_list_excludes_customer_only_auth_users(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("backoffice:users"))
        self.assertEqual(response.status_code, 200)
        listed_ids = {row["user"].pk for row in response.context["user_rows"]}
        self.assertNotIn(self.customer_user.pk, listed_ids)


class OutboundSecurityTests(TestCase):
    @override_settings(DEBUG=False, INTEGRATION_REQUIRE_HTTPS=True)
    def test_production_outbound_urls_require_https_and_public_destinations(self):
        with self.assertRaises(UnsafeOutboundURL):
            validate_outbound_url("http://example.com/hook")
        with self.assertRaises(UnsafeOutboundURL):
            validate_outbound_url("https://127.0.0.1/hook")
        with self.assertRaises(UnsafeOutboundURL):
            validate_outbound_url("https://localhost/hook")
        self.assertEqual(validate_outbound_url("https://example.com/hook"), "https://example.com/hook")

    @override_settings(DEBUG=False, INTEGRATION_REQUIRE_HTTPS=True)
    def test_integration_form_rejects_insecure_sms_webhook(self):
        form = IntegrationSettingsForm(data={"sms_enabled": "on", "sms_webhook_url": "http://example.com/hook"})
        self.assertFalse(form.is_valid())
        self.assertIn("sms_webhook_url", form.errors)


class CmsUploadSecurityTests(TestCase):
    def test_corrupted_cms_image_is_rejected(self):
        upload = SimpleUploadedFile("banner.png", b"not-a-real-image", content_type="image/png")
        with self.assertRaisesMessage(ValidationError, "invalid or corrupted image"):
            validate_cms_image(upload)

    def test_oversized_cms_image_is_rejected_before_processing(self):
        upload = SimpleUploadedFile("banner.jpg", b"x" * (2 * 1024 * 1024 + 1), content_type="image/jpeg")
        with self.assertRaisesMessage(ValidationError, "2MB or smaller"):
            validate_cms_image(upload)


class ProductionCheckTests(TestCase):
    @override_settings(
        DEBUG=False,
        STAFF_AUTH_ENABLED=True,
        SECURE_SSL_REDIRECT=True,
        SESSION_COOKIE_SECURE=True,
        CSRF_COOKIE_SECURE=True,
        INTEGRATION_REQUIRE_HTTPS=True,
        COURIER_WEBHOOK_REQUIRE_TIMESTAMP=True,
        SECURE_HSTS_SECONDS=3600,
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        ALLOWED_HOSTS=["shop.example.com"],
    )
    def test_project_production_checks_have_no_errors_for_safe_settings(self):
        issues = production_security_checks(None)
        self.assertFalse([issue for issue in issues if issue.id.startswith("techbari.E")])
