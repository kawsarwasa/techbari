import time

from django.contrib.auth.models import Group, Permission, User
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import AuditLog
from .permissions import PERMISSION_CODES, SYSTEM_ROLE_NAMES, sync_system_roles


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class StaffAccessTests(TestCase):
    def setUp(self):
        sync_system_roles()
        self.password = "StrongPass123!"

    def make_user(self, username, role, *, active=True, superuser=False):
        user = User.objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password=self.password,
            is_active=active,
            is_staff=True,
            is_superuser=superuser,
        )
        if role:
            user.groups.add(Group.objects.get(name=role))
        return user

    def test_six_system_roles_and_cashier_restriction_exist(self):
        self.assertEqual(set(Group.objects.filter(name__in=SYSTEM_ROLE_NAMES).values_list("name", flat=True)), set(SYSTEM_ROLE_NAMES))
        admin = Group.objects.get(name="Admin")
        cashier = Group.objects.get(name="Cashier")
        self.assertEqual(
            set(admin.permissions.filter(content_type__app_label="staff_access").values_list("codename", flat=True)),
            set(PERMISSION_CODES),
        )
        self.assertFalse(cashier.permissions.filter(codename="manage_accounting_settings").exists())
        self.assertTrue(cashier.permissions.filter(codename="use_pos").exists())

    def test_anonymous_dashboard_redirects_to_staff_login(self):
        response = self.client.get(reverse("backoffice:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("backoffice:login"), response.url)

    def test_login_accepts_email_and_writes_audit_log(self):
        user = self.make_user("cashier1", "Cashier")
        response = self.client.post(reverse("backoffice:login"), {"username": user.email, "password": self.password})
        self.assertRedirects(response, reverse("backoffice:dashboard"), fetch_redirect_response=False)
        self.assertTrue(AuditLog.objects.filter(user=user, action=AuditLog.Action.LOGIN).exists())

    def test_inactive_user_cannot_login(self):
        user = self.make_user("inactive", "Sales Staff", active=False)
        response = self.client.post(reverse("backoffice:login"), {"username": user.username, "password": self.password})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid username/email or password")
        self.assertTrue(AuditLog.objects.filter(action=AuditLog.Action.LOGIN_FAILED).exists())

    def test_cashier_can_open_dashboard_but_not_accounting(self):
        user = self.make_user("cashier2", "Cashier")
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("backoffice:dashboard")).status_code, 200)
        denied = self.client.get(reverse("backoffice:accounts"))
        self.assertEqual(denied.status_code, 403)
        self.assertTrue(AuditLog.objects.filter(user=user, action=AuditLog.Action.DENIED).exists())

    def test_cashier_cannot_edit_accounting_settings(self):
        user = self.make_user("cashier3", "Cashier")
        self.client.force_login(user)
        response = self.client.post(reverse("backoffice:accounting_period_toggle", args=[999]))
        self.assertEqual(response.status_code, 403)

    def test_accountant_can_open_accounting(self):
        user = self.make_user("accountant1", "Accountant")
        self.client.force_login(user)
        response = self.client.get(reverse("backoffice:accounts"))
        self.assertEqual(response.status_code, 200)

    def test_manager_can_view_users_but_cannot_add_user(self):
        user = self.make_user("manager1", "Manager")
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("backoffice:users")).status_code, 200)
        self.assertEqual(self.client.get(reverse("backoffice:user_add")).status_code, 403)

    def test_admin_can_create_real_staff_user_with_role(self):
        admin = self.make_user("admin1", "Admin")
        self.client.force_login(admin)
        cashier = Group.objects.get(name="Cashier")
        response = self.client.post(reverse("backoffice:user_add"), {
            "username": "counterstaff",
            "first_name": "Counter",
            "last_name": "Staff",
            "email": "counter@example.com",
            "role": cashier.pk,
            "branch": "Dhanmondi",
            "phone": "01700000000",
            "password1": self.password,
            "password2": self.password,
            "is_active": "on",
        })
        self.assertRedirects(response, reverse("backoffice:users"), fetch_redirect_response=False)
        created = User.objects.get(username="counterstaff")
        self.assertTrue(created.check_password(self.password))
        self.assertTrue(created.groups.filter(name="Cashier").exists())
        self.assertEqual(created.staff_profile.branch, "Dhanmondi")
        self.assertTrue(AuditLog.objects.filter(action=AuditLog.Action.CREATE, object_type="User", object_id=str(created.pk)).exists())

    def test_direct_user_permission_can_extend_role(self):
        user = self.make_user("salesplus", "Sales Staff")
        permission = Permission.objects.get(content_type__app_label="staff_access", codename="view_accounting")
        user.user_permissions.add(permission)
        user = User.objects.get(pk=user.pk)
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("backoffice:accounts")).status_code, 200)

    def test_admin_role_is_protected_from_edit(self):
        admin_user = self.make_user("admin2", "Admin")
        self.client.force_login(admin_user)
        admin_role = Group.objects.get(name="Admin")
        response = self.client.get(reverse("backoffice:role_edit", args=[admin_role.pk]))
        self.assertRedirects(response, reverse("backoffice:roles"), fetch_redirect_response=False)
        self.assertEqual(admin_role.permissions.filter(content_type__app_label="staff_access").count(), len(PERMISSION_CODES))

    def test_role_permission_matrix_is_editable_for_non_admin(self):
        admin_user = self.make_user("admin3", "Admin")
        self.client.force_login(admin_user)
        manager = Group.objects.get(name="Manager")
        chosen = Permission.objects.filter(content_type__app_label="staff_access", codename__in=["view_dashboard", "view_reports"])
        response = self.client.post(reverse("backoffice:role_edit", args=[manager.pk]), {"permissions": [p.pk for p in chosen]})
        self.assertRedirects(response, reverse("backoffice:roles"), fetch_redirect_response=False)
        manager.refresh_from_db()
        self.assertEqual(set(manager.permissions.filter(content_type__app_label="staff_access").values_list("codename", flat=True)), {"view_dashboard", "view_reports"})

    @override_settings(STAFF_IDLE_TIMEOUT=1)
    def test_idle_staff_session_expires(self):
        user = self.make_user("idleuser", "Cashier")
        self.client.force_login(user)
        session = self.client.session
        session["staff_last_activity"] = int(time.time()) - 10
        session.save()
        response = self.client.get(reverse("backoffice:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("expired=1", response.url)
        self.assertTrue(AuditLog.objects.filter(user=user, action=AuditLog.Action.LOGOUT).exists())

    def test_password_reset_flow_sends_email_for_active_staff(self):
        user = self.make_user("resetme", "Sales Staff")
        response = self.client.post(reverse("backoffice:password_reset"), {"email": user.email})
        self.assertRedirects(response, reverse("backoffice:password_reset_done"), fetch_redirect_response=False)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("TechBari staff password reset", mail.outbox[0].subject)

    def test_logout_is_post_only_and_audited(self):
        user = self.make_user("logoutuser", "Cashier")
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("backoffice:logout")).status_code, 405)
        response = self.client.post(reverse("backoffice:logout"))
        self.assertRedirects(response, reverse("backoffice:login"), fetch_redirect_response=False)
        self.assertTrue(AuditLog.objects.filter(user=user, action=AuditLog.Action.LOGOUT).exists())

    def test_superuser_bypasses_role_permission_checks(self):
        user = self.make_user("rootstaff", None, superuser=True)
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("backoffice:accounts")).status_code, 200)
        self.assertEqual(self.client.get(reverse("backoffice:user_add")).status_code, 200)
