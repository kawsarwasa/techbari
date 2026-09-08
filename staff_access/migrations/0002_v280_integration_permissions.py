from django.db import migrations


PERMISSIONS = (
    ("view_dashboard", "View dashboard"),
    ("view_notifications", "View notifications"),
    ("manage_integrations", "Manage notifications and integrations"),
    ("view_catalog", "View catalog"), ("manage_catalog", "Manage catalog"),
    ("view_inventory", "View inventory"), ("manage_inventory", "Manage inventory"), ("adjust_inventory", "Adjust or transfer inventory"),
    ("view_serial", "View Serial / IMEI"), ("manage_serial", "Manage Serial / IMEI"),
    ("view_purchasing", "View suppliers and purchases"), ("manage_purchasing", "Manage suppliers and purchases"),
    ("view_customers", "View customers"), ("manage_customers", "Manage customers"),
    ("view_sales", "View sales orders"), ("manage_sales", "Manage sales orders"), ("use_pos", "Use POS"),
    ("view_payments", "View payments"), ("manage_payments", "Manage payments, refunds and reconciliation"),
    ("view_shipping", "View shipping"), ("manage_shipping", "Manage shipping and COD settlements"),
    ("view_returns", "View returns and warranty"), ("manage_returns", "Manage returns and warranty"),
    ("view_accounting", "View accounting"), ("manage_accounting", "Post and reverse accounting journals"), ("manage_accounting_settings", "Manage chart of accounts and accounting periods"),
    ("view_expenses", "View expenses"), ("manage_expenses", "Create, edit, submit, pay and void expenses"), ("approve_expenses", "Approve or reject expenses"),
    ("view_reports", "View reports"), ("view_marketing", "View promotion and marketing"), ("manage_marketing", "Manage promotion and marketing"),
    ("manage_store_settings", "Manage store settings"), ("view_users", "View staff users and roles"), ("manage_users", "Manage staff users, roles and permissions"), ("view_audit_log", "View staff audit log"),
)


class Migration(migrations.Migration):
    dependencies = [("staff_access", "0001_initial")]
    operations = [migrations.AlterModelOptions(name="staffprofile", options={"default_permissions": (), "permissions": PERMISSIONS})]
