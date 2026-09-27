from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.urls import reverse

from .mfa import (
    current_totp_code,
    decrypt_secret,
    enable_mfa,
    get_or_create_mfa_device,
    verify_mfa_code,
)
from .models import StaffMFADevice
from .permissions import sync_system_roles


TEST_FERNET_KEY = "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="


@override_settings(
    STAFF_AUTH_ENABLED=True,
    STAFF_MFA_REQUIRED=True,
    STAFF_MFA_ENCRYPTION_KEY=TEST_FERNET_KEY,
)
class StaffMFATests(TestCase):
    def setUp(self):
        sync_system_roles()
        self.password = "StrongPass123!"
        self.user = User.objects.create_user(
            username="mfastaff",
            email="mfa@example.com",
            password=self.password,
            is_staff=True,
            is_active=True,
        )
        self.user.groups.add(Group.objects.get(name="Cashier"))

    def _enabled_device(self, user=None):
        user = user or self.user
        device = get_or_create_mfa_device(user)
        secret = decrypt_secret(device)
        codes = enable_mfa(user, current_totp_code(secret))
        self.assertIsNotNone(codes)
        device.refresh_from_db()
        return device, secret, codes

    def test_required_staff_without_mfa_is_sent_to_setup(self):
        login_response = self.client.post(
            reverse("backoffice:login"),
            {"username": self.user.username, "password": self.password},
        )
        self.assertRedirects(
            login_response,
            reverse("backoffice:dashboard"),
            fetch_redirect_response=False,
        )
        response = self.client.get(reverse("backoffice:dashboard"))
        self.assertRedirects(
            response,
            reverse("backoffice:mfa_setup"),
            fetch_redirect_response=False,
        )

    def test_setup_secret_requires_password_reauthentication_and_is_encrypted_at_rest(self):
        self.client.force_login(self.user)

        initial = self.client.get(reverse("backoffice:mfa_setup"))
        self.assertEqual(initial.status_code, 200)
        self.assertFalse(StaffMFADevice.objects.filter(user=self.user).exists())

        qr_denied = self.client.get(reverse("backoffice:mfa_qr"))
        self.assertEqual(qr_denied.status_code, 403)

        reauth = self.client.post(
            reverse("backoffice:mfa_setup"),
            {"action": "reauth", "password": self.password},
        )
        self.assertRedirects(
            reauth,
            reverse("backoffice:mfa_setup"),
            fetch_redirect_response=False,
        )

        device = StaffMFADevice.objects.get(user=self.user)
        secret = decrypt_secret(device)
        self.assertNotEqual(device.encrypted_secret, secret)
        self.assertNotIn(secret, device.encrypted_secret)

        setup = self.client.get(reverse("backoffice:mfa_setup"))
        self.assertContains(setup, secret)
        qr = self.client.get(reverse("backoffice:mfa_qr"))
        self.assertEqual(qr.status_code, 200)
        self.assertEqual(qr["Content-Type"], "image/svg+xml")
        self.assertIn("no-store", qr["Cache-Control"])

        code = current_totp_code(secret)
        enabled = self.client.post(
            reverse("backoffice:mfa_setup"),
            {"action": "enable", "code": code},
        )
        self.assertRedirects(
            enabled,
            reverse("backoffice:mfa_recovery_codes"),
            fetch_redirect_response=False,
        )
        device.refresh_from_db()
        self.assertTrue(device.is_enabled)
        self.assertEqual(
            self.client.session.get("staff_mfa_verified_user_id"),
            self.user.pk,
        )

        recovery = self.client.get(reverse("backoffice:mfa_recovery_codes"))
        self.assertEqual(recovery.status_code, 200)
        self.assertContains(recovery, "These codes will not be shown again")
        self.assertEqual(len(device.recovery_code_hashes), 10)

    def test_enabled_staff_password_step_does_not_create_authenticated_session_before_mfa(self):
        _device, _secret, recovery_codes = self._enabled_device()

        password_step = self.client.post(
            reverse("backoffice:login"),
            {"username": self.user.username, "password": self.password},
        )
        self.assertRedirects(
            password_step,
            reverse("backoffice:mfa_challenge"),
            fetch_redirect_response=False,
        )
        self.assertNotIn("_auth_user_id", self.client.session)

        challenge = self.client.post(
            reverse("backoffice:mfa_challenge"),
            {"code": recovery_codes[0]},
        )
        self.assertRedirects(
            challenge,
            reverse("backoffice:dashboard"),
            fetch_redirect_response=False,
        )
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)
        self.assertEqual(
            self.client.session.get("staff_mfa_verified_user_id"),
            self.user.pk,
        )

        verified_again, _method = verify_mfa_code(self.user, recovery_codes[0])
        self.assertFalse(verified_again)

    def test_totp_code_cannot_be_replayed(self):
        device = get_or_create_mfa_device(self.user)
        secret = decrypt_secret(device)
        first_time = 1_800_000_000
        first_code = current_totp_code(secret, for_time=first_time)

        with patch("staff_access.mfa.time.time", return_value=first_time):
            self.assertIsNotNone(enable_mfa(self.user, first_code))
            replayed, _method = verify_mfa_code(self.user, first_code)
        self.assertFalse(replayed)

        second_time = first_time + 30
        second_code = current_totp_code(secret, for_time=second_time)
        with patch("staff_access.mfa.time.time", return_value=second_time):
            accepted, method = verify_mfa_code(self.user, second_code)
        self.assertTrue(accepted)
        self.assertEqual(method, "totp")

    def test_existing_authenticated_session_without_mfa_verification_is_invalidated(self):
        self._enabled_device()
        self.client.force_login(self.user)

        response = self.client.get(reverse("backoffice:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("backoffice:login"), response.url)
        self.assertNotIn("_auth_user_id", self.client.session)

    @override_settings(STAFF_MFA_REQUIRED=False)
    def test_only_superuser_can_reset_another_staff_mfa(self):
        self._enabled_device()
        admin_role_user = User.objects.create_user(
            username="roleadmin-mfa",
            password=self.password,
            is_staff=True,
        )
        admin_role_user.groups.add(Group.objects.get(name="Admin"))
        self.client.force_login(admin_role_user)
        denied = self.client.post(
            reverse("backoffice:user_mfa_reset", args=[self.user.pk])
        )
        self.assertEqual(denied.status_code, 403)
        self.assertTrue(StaffMFADevice.objects.filter(user=self.user).exists())

        root = User.objects.create_superuser(
            username="root-mfa",
            email="root-mfa@example.com",
            password=self.password,
        )
        self.client.force_login(root)
        reset = self.client.post(
            reverse("backoffice:user_mfa_reset", args=[self.user.pk])
        )
        self.assertRedirects(
            reset,
            reverse("backoffice:users"),
            fetch_redirect_response=False,
        )
        self.assertFalse(StaffMFADevice.objects.filter(user=self.user).exists())
