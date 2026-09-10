from django.contrib.auth.models import Group, Permission, User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import AuditLog
from .permissions import sync_system_roles
from .services import user_role


@override_settings(STAFF_AUTH_ENABLED=True)
class CustomRoleTests(TestCase):
    def setUp(self):
        sync_system_roles()
        self.password = "StrongPass123!"
        self.admin = User.objects.create_user(
            username="roleadmin",
            email="roleadmin@example.com",
            password=self.password,
            is_staff=True,
        )
        self.admin.groups.add(Group.objects.get(name="Admin"))
        self.client.force_login(self.admin)

    def permission(self, codename):
        return Permission.objects.get(
            content_type__app_label="staff_access",
            content_type__model="staffprofile",
            codename=codename,
        )

    def test_admin_can_create_custom_role(self):
        chosen = [self.permission("view_dashboard"), self.permission("view_customers")]
        response = self.client.post(
            reverse("backoffice:role_add"),
            {"name": "Support Lead", "permissions": [permission.pk for permission in chosen]},
        )
        self.assertRedirects(response, reverse("backoffice:roles"), fetch_redirect_response=False)
        role = Group.objects.get(name="Support Lead")
        self.assertEqual(
            set(role.permissions.filter(content_type__app_label="staff_access").values_list("codename", flat=True)),
            {"view_dashboard", "view_customers"},
        )
        self.assertTrue(
            AuditLog.objects.filter(action=AuditLog.Action.CREATE, object_type="Role", object_id=str(role.pk)).exists()
        )

    def test_custom_role_requires_at_least_one_permission(self):
        response = self.client.post(reverse("backoffice:role_add"), {"name": "Empty Role"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Select at least one permission")
        self.assertFalse(Group.objects.filter(name="Empty Role").exists())

    def test_custom_role_can_be_assigned_to_new_staff_user(self):
        role = Group.objects.create(name="Support Agent")
        role.permissions.add(self.permission("view_dashboard"), self.permission("view_customers"))
        response = self.client.post(
            reverse("backoffice:user_add"),
            {
                "username": "supportagent",
                "first_name": "Support",
                "last_name": "Agent",
                "email": "supportagent@example.com",
                "role": role.pk,
                "branch": "Main Branch",
                "phone": "01700000001",
                "password1": self.password,
                "password2": self.password,
                "is_active": "on",
            },
        )
        self.assertRedirects(response, reverse("backoffice:users"), fetch_redirect_response=False)
        user = User.objects.get(username="supportagent")
        self.assertTrue(user.groups.filter(pk=role.pk).exists())
        self.assertEqual(user_role(user), "Support Agent")

    def test_manager_cannot_open_custom_role_create_page(self):
        manager = User.objects.create_user(
            username="managerrole",
            email="managerrole@example.com",
            password=self.password,
            is_staff=True,
        )
        manager.groups.add(Group.objects.get(name="Manager"))
        self.client.force_login(manager)
        self.assertEqual(self.client.get(reverse("backoffice:role_add")).status_code, 403)
