from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="StaffProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("phone", models.CharField(blank=True, max_length=32)),
                ("branch", models.CharField(blank=True, default="Main Branch", max_length=120)),
                ("force_password_change", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="staff_profile", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "default_permissions": (),
                "permissions": (("view_dashboard", "View dashboard"), ("view_catalog", "View catalog"), ("manage_catalog", "Manage catalog"), ("view_inventory", "View inventory"), ("manage_inventory", "Manage inventory"), ("adjust_inventory", "Adjust or transfer inventory"), ("view_serial", "View Serial / IMEI"), ("manage_serial", "Manage Serial / IMEI"), ("view_purchasing", "View suppliers and purchases"), ("manage_purchasing", "Manage suppliers and purchases"), ("view_customers", "View customers"), ("manage_customers", "Manage customers"), ("view_sales", "View sales orders"), ("manage_sales", "Manage sales orders"), ("use_pos", "Use POS"), ("view_payments", "View payments"), ("manage_payments", "Manage payments, refunds and reconciliation"), ("view_shipping", "View shipping"), ("manage_shipping", "Manage shipping and COD settlements"), ("view_returns", "View returns and warranty"), ("manage_returns", "Manage returns and warranty"), ("view_accounting", "View accounting"), ("manage_accounting", "Post and reverse accounting journals"), ("manage_accounting_settings", "Manage chart of accounts and accounting periods"), ("view_expenses", "View expenses"), ("manage_expenses", "Create, edit, submit, pay and void expenses"), ("approve_expenses", "Approve or reject expenses"), ("view_reports", "View reports"), ("view_marketing", "View promotion and marketing"), ("manage_marketing", "Manage promotion and marketing"), ("manage_store_settings", "Manage store settings"), ("view_users", "View staff users and roles"), ("manage_users", "Manage staff users, roles and permissions"), ("view_audit_log", "View staff audit log")),
            },
        ),
        migrations.AddIndex(model_name="staffprofile", index=models.Index(fields=["branch"], name="staff_profile_branch_idx")),
        migrations.CreateModel(
            name="AuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("username_snapshot", models.CharField(blank=True, max_length=150)),
                ("role_snapshot", models.CharField(blank=True, max_length=150)),
                ("action", models.CharField(choices=[("login", "Login"), ("login_failed", "Login Failed"), ("logout", "Logout"), ("create", "Create"), ("update", "Update"), ("delete", "Delete"), ("mutate", "Change"), ("denied", "Permission Denied"), ("password", "Password Change")], max_length=24)),
                ("method", models.CharField(blank=True, max_length=10)),
                ("path", models.CharField(blank=True, max_length=500)),
                ("route_name", models.CharField(blank=True, max_length=160)),
                ("status_code", models.PositiveSmallIntegerField(default=200)),
                ("object_type", models.CharField(blank=True, max_length=100)),
                ("object_id", models.CharField(blank=True, max_length=100)),
                ("summary", models.CharField(blank=True, max_length=500)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.CharField(blank=True, max_length=500)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="staff_audit_logs", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-created_at", "-id")},
        ),
        migrations.AddIndex(model_name="auditlog", index=models.Index(fields=["created_at"], name="staff_audit_created_idx")),
        migrations.AddIndex(model_name="auditlog", index=models.Index(fields=["action", "created_at"], name="staff_audit_action_idx")),
        migrations.AddIndex(model_name="auditlog", index=models.Index(fields=["user", "created_at"], name="staff_audit_user_idx")),
    ]
