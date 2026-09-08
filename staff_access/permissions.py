ACCESS_PERMISSIONS = (
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
    ("view_reports", "View reports"),
    ("view_marketing", "View promotion and marketing"),
    ("manage_marketing", "Manage promotion and marketing"),
    ("manage_store_settings", "Manage store settings"),
    ("view_users", "View staff users and roles"),
    ("manage_users", "Manage staff users, roles and permissions"),
    ("view_audit_log", "View staff audit log"),
)

PERMISSION_CODES = tuple(code for code, _ in ACCESS_PERMISSIONS)
SYSTEM_ROLE_NAMES = ("Admin", "Manager", "Cashier", "Inventory Manager", "Accountant", "Sales Staff")

ROLE_DEFAULTS = {
    "Admin": set(PERMISSION_CODES),
    "Manager": set(PERMISSION_CODES) - {"manage_users", "manage_accounting_settings"},
    "Cashier": {
        "view_dashboard", "view_notifications", "view_catalog", "view_customers", "manage_customers",
        "view_sales", "manage_sales", "use_pos", "view_payments", "manage_payments", "view_returns",
    },
    "Inventory Manager": {
        "view_dashboard", "view_notifications", "view_catalog", "manage_catalog", "view_inventory", "manage_inventory",
        "adjust_inventory", "view_serial", "manage_serial", "view_purchasing", "manage_purchasing",
        "view_returns", "manage_returns", "view_reports",
    },
    "Accountant": {
        "view_dashboard", "view_notifications", "view_purchasing", "view_customers", "view_sales", "view_payments",
        "manage_payments", "view_accounting", "manage_accounting", "manage_accounting_settings",
        "view_expenses", "manage_expenses", "approve_expenses", "view_reports", "view_audit_log",
    },
    "Sales Staff": {
        "view_dashboard", "view_notifications", "view_catalog", "view_customers", "manage_customers", "view_sales",
        "manage_sales", "view_payments", "view_shipping", "view_returns",
    },
}


def staff_permissions_queryset():
    from django.contrib.auth.models import Permission
    return Permission.objects.filter(content_type__app_label="staff_access", content_type__model="staffprofile")


def sync_system_roles(sender=None, **kwargs):
    from django.contrib.auth.models import Group
    permissions = {p.codename: p for p in staff_permissions_queryset()}
    if not permissions:
        return
    for role_name in SYSTEM_ROLE_NAMES:
        group, created = Group.objects.get_or_create(name=role_name)
        desired = [permissions[code] for code in ROLE_DEFAULTS[role_name] if code in permissions]
        if role_name == "Admin" or created:
            group.permissions.set(desired)
