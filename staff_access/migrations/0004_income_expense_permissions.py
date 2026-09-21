from django.db import migrations


PERMISSIONS = (
    ("view_dashboard", "View dashboard"),
    ("view_notifications", "View notifications"),
    ("manage_integrations", "Manage notifications and integrations"),
    ("view_catalog", "View catalog"),
    ("manage_catalog", "Manage catalog"),
    ("view_inventory", "View inventory"),
    ("manage_inventory", "Manage inventory"),
    ("adjust_inventory", "Adjust or transfer inventory"),
    ("view_serial", "View Serial / IMEI"),
    ("manage_serial", "Manage Serial / IMEI"),
    ("view_purchasing", "View suppliers and purchases"),
    ("manage_purchasing", "Manage suppliers and purchases"),
    ("view_customers", "View customers"),
    ("manage_customers", "Manage customers"),
    ("view_sales", "View sales orders"),
    ("manage_sales", "Manage sales orders"),
    ("use_pos", "Use POS"),
    ("view_payments", "View payments"),
    ("manage_payments", "Manage payments, refunds and reconciliation"),
    ("view_shipping", "View shipping"),
    ("manage_shipping", "Manage shipping and COD settlements"),
    ("view_returns", "View returns and warranty"),
    ("manage_returns", "Manage returns and warranty"),
    ("view_accounting", "View accounting"),
    ("manage_accounting", "Post and reverse accounting journals"),
    ("manage_accounting_settings", "Manage chart of accounts and accounting periods"),
    ("view_expenses", "View expenses"),
    ("manage_expenses", "Create, edit, submit, pay and void expenses"),
    ("approve_expenses", "Approve or reject expenses"),
    ("view_income_expense", "View Income & Expense"),
    ("manage_income_expense", "Manage Income & Expense"),
    ("view_reports", "View reports"),
    ("view_marketing", "View promotion and marketing"),
    ("manage_marketing", "Manage promotion and marketing"),
    ("manage_store_settings", "Manage store settings"),
    ("view_users", "View staff users and roles"),
    ("manage_users", "Manage staff users, roles and permissions"),
    ("view_audit_log", "View staff audit log"),
)


def create_and_preserve_income_expense_access(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")
    Group = apps.get_model("auth", "Group")
    User = apps.get_model("auth", "User")

    # On a freshly created database (including Django's test database),
    # content-type rows are normally populated by post_migrate, which has not
    # run yet while this data migration is executing. Create/reuse the row
    # explicitly so the migration works both on upgrades and fresh installs.
    content_type, _ = ContentType.objects.get_or_create(
        app_label="staff_access",
        model="staffprofile",
    )
    mapping = (
        ("view_expenses", "view_income_expense", "View Income & Expense"),
        ("manage_expenses", "manage_income_expense", "Manage Income & Expense"),
    )

    created_permissions = {}
    for old_code, new_code, label in mapping:
        new_permission, _ = Permission.objects.get_or_create(
            content_type=content_type,
            codename=new_code,
            defaults={"name": label},
        )
        if new_permission.name != label:
            new_permission.name = label
            new_permission.save(update_fields=["name"])
        created_permissions[new_code] = new_permission

        old_permission = Permission.objects.filter(
            content_type=content_type,
            codename=old_code,
        ).first()
        if old_permission:
            for group in Group.objects.filter(permissions=old_permission).distinct():
                group.permissions.add(new_permission)
            for user in User.objects.filter(user_permissions=old_permission).distinct():
                user.user_permissions.add(new_permission)

    # Preserve the current built-in role behavior on upgrade. These roles already
    # had access through the legacy expense permissions before the split.
    for role_name in ("Admin", "Manager", "Accountant"):
        group = Group.objects.filter(name=role_name).first()
        if group:
            group.permissions.add(
                created_permissions["view_income_expense"],
                created_permissions["manage_income_expense"],
            )


def remove_income_expense_permissions(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")
    content_type = ContentType.objects.filter(app_label="staff_access", model="staffprofile").first()
    if content_type:
        Permission.objects.filter(
            content_type=content_type,
            codename__in=("view_income_expense", "manage_income_expense"),
        ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("staff_access", "0003_v300_auth_hardening"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="staffprofile",
            options={
                "default_permissions": (),
                "permissions": PERMISSIONS,
            },
        ),
        migrations.RunPython(
            create_and_preserve_income_expense_access,
            remove_income_expense_permissions,
        ),
    ]
