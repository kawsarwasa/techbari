import time
from urllib.parse import quote

from django.conf import settings
from django.contrib.auth import logout
from django.shortcuts import redirect, render
from django.urls import resolve, reverse

from .models import AuditLog
from .services import record_audit

PUBLIC_ROUTES = {"login", "password_reset", "password_reset_done", "password_reset_confirm", "password_reset_complete"}
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

CATALOG_LIST = {"products", "categories", "brands", "catalog_variants", "catalog_media", "catalog_specifications"}
CATALOG_MANAGE = {"product_add", "product_edit", "category_add", "brand_add", "catalog_variant_form", "catalog_media_form", "catalog_specification_form"}
INVENTORY_LIST = {"inventory", "warehouses", "inventory_movements", "inventory_low_stock"}
INVENTORY_MANAGE = {"warehouse_add"}
INVENTORY_ADJUST = {"stock_adjustment", "stock_transfer"}
SERIAL_LIST = {"serials"}
SERIAL_MANAGE = {"serial_add"}
PURCHASE_LIST = {"suppliers", "purchases", "purchase_detail"}
PURCHASE_MANAGE = {"supplier_add", "supplier_delete", "purchase_add", "purchase_receive", "purchase_payment", "purchase_return", "purchase_cancel", "purchase_delete"}
CUSTOMER_LIST = {"customers", "customer_detail", "customer_detail_id", "customer_groups"}
CUSTOMER_MANAGE = {"customer_add", "customer_delete", "customer_group_delete"}
SALES_LIST = {"orders", "order_detail", "order_detail_id"}
SALES_MANAGE = {"order_add", "order_confirm", "order_process", "order_complete", "order_cancel", "order_payment", "order_delete"}
PAYMENT_LIST = {"payments", "payment_detail", "payment_methods"}
PAYMENT_MANAGE = {"payment_add", "payment_refund", "payment_reverse", "payment_reconcile"}
SHIPPING_LIST = {"shipping", "shipment_detail", "cod_settlement_detail"}
SHIPPING_MANAGE = {"shipment_add", "courier_providers", "cod_settlements", "cod_settlement_add", "shipment_status", "shipment_tracking"}
RETURN_LIST = {"returns", "return_detail", "warranty"}
RETURN_MANAGE = {"return_add", "return_approve", "return_receive", "return_complete", "return_reject", "return_cancel", "warranty_add"}
ACCOUNTING_VIEW = {"accounts", "chart_accounts", "journals", "journal_detail", "general_ledger", "trial_balance", "accounting_periods"}
ACCOUNTING_MANAGE = {"journal_add", "journal_reverse"}
ACCOUNTING_SETTINGS = {"account_add", "accounting_period_toggle"}
EXPENSE_VIEW = {"expenses", "expense_detail", "expense_categories"}
EXPENSE_MANAGE = {"expense_add", "expense_edit", "expense_submit", "expense_cancel", "expense_pay", "expense_void", "expense_category_toggle"}
EXPENSE_APPROVE = {"expense_approve", "expense_reject"}
MARKETING_VIEW = {"marketing", "coupons"}
MARKETING_MANAGE = {"coupon_add"}
STORE_SETTINGS_ROUTES = {"settings", "cms_banners", "cms_banner_add", "cms_banner_edit", "cms_banner_toggle", "cms_banner_delete", "cms_homepage_sections", "cms_homepage_section_update", "cms_content_pages", "cms_content_page_edit"}
USER_VIEW = {"users", "roles"}
USER_MANAGE = {"user_add", "user_edit", "user_toggle", "role_edit"}
NOTIFICATION_ROUTES = {"notifications", "notification_read", "notifications_read_all"}
INTEGRATION_ROUTES = {"integration_settings", "integration_retry", "integration_process"}


def _permission(route_name, method):
    write = method in MUTATING_METHODS
    if route_name == "dashboard": return "staff_access.view_dashboard"
    if route_name in NOTIFICATION_ROUTES: return "staff_access.view_notifications"
    if route_name in INTEGRATION_ROUTES: return "staff_access.manage_integrations"
    if route_name in CATALOG_MANAGE or (route_name in CATALOG_LIST and write): return "staff_access.manage_catalog"
    if route_name in CATALOG_LIST: return "staff_access.view_catalog"
    if route_name in INVENTORY_ADJUST: return "staff_access.adjust_inventory"
    if route_name in INVENTORY_MANAGE or (route_name in INVENTORY_LIST and write): return "staff_access.manage_inventory"
    if route_name in INVENTORY_LIST: return "staff_access.view_inventory"
    if route_name in SERIAL_MANAGE or (route_name in SERIAL_LIST and write): return "staff_access.manage_serial"
    if route_name in SERIAL_LIST: return "staff_access.view_serial"
    if route_name in PURCHASE_MANAGE or (route_name in PURCHASE_LIST and write): return "staff_access.manage_purchasing"
    if route_name in PURCHASE_LIST: return "staff_access.view_purchasing"
    if route_name in CUSTOMER_MANAGE or (route_name in CUSTOMER_LIST and write): return "staff_access.manage_customers"
    if route_name in CUSTOMER_LIST: return "staff_access.view_customers"
    if route_name in SALES_MANAGE or (route_name in SALES_LIST and write): return "staff_access.manage_sales"
    if route_name in SALES_LIST: return "staff_access.view_sales"
    if route_name in {"pos", "pos_action", "pos_hold_detail", "pos_receipt"}: return "staff_access.use_pos"
    if route_name in PAYMENT_MANAGE or (route_name in PAYMENT_LIST and write): return "staff_access.manage_payments"
    if route_name in PAYMENT_LIST: return "staff_access.view_payments"
    if route_name in SHIPPING_MANAGE or (route_name in SHIPPING_LIST and write): return "staff_access.manage_shipping"
    if route_name in SHIPPING_LIST: return "staff_access.view_shipping"
    if route_name in RETURN_MANAGE or (route_name in RETURN_LIST and write): return "staff_access.manage_returns"
    if route_name in RETURN_LIST: return "staff_access.view_returns"
    if route_name in ACCOUNTING_SETTINGS: return "staff_access.manage_accounting_settings"
    if route_name in ACCOUNTING_MANAGE or (route_name in ACCOUNTING_VIEW and write): return "staff_access.manage_accounting"
    if route_name in ACCOUNTING_VIEW: return "staff_access.view_accounting"
    if route_name in EXPENSE_APPROVE: return "staff_access.approve_expenses"
    if route_name in EXPENSE_MANAGE or (route_name in EXPENSE_VIEW and write): return "staff_access.manage_expenses"
    if route_name in EXPENSE_VIEW: return "staff_access.view_expenses"
    if route_name == "reports": return "staff_access.view_reports"
    if route_name in MARKETING_MANAGE or (route_name in MARKETING_VIEW and write): return "staff_access.manage_marketing"
    if route_name in MARKETING_VIEW: return "staff_access.view_marketing"
    if route_name in STORE_SETTINGS_ROUTES: return "staff_access.manage_store_settings"
    if route_name == "audit_log": return "staff_access.view_audit_log"
    if route_name in USER_MANAGE or (route_name in USER_VIEW and write): return "staff_access.manage_users"
    if route_name in USER_VIEW: return "staff_access.view_users"
    if route_name in {"logout", "password_change", "password_change_done", "legacy_page"}: return None
    return "__deny__"


class StaffAccessMiddleware:
    def __init__(self, get_response): self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith("/dashboard/") or not getattr(settings, "STAFF_AUTH_ENABLED", True):
            return self.get_response(request)
        try:
            match = resolve(request.path_info)
            route_name = match.url_name or ""
        except Exception:
            route_name = ""
        if route_name in PUBLIC_ROUTES:
            return self.get_response(request)
        if not request.user.is_authenticated:
            login_url = reverse("backoffice:login")
            return redirect(f"{login_url}?next={quote(request.get_full_path())}")
        if not (request.user.is_staff or request.user.is_superuser):
            record_audit(request, AuditLog.Action.DENIED, status_code=403, summary="Non-staff identity denied dashboard access", route_name=route_name)
            return render(request, "backoffice/auth/403.html", {"required_permission": "staff identity"}, status=403)

        idle_timeout = int(getattr(settings, "STAFF_IDLE_TIMEOUT", 1800))
        now = int(time.time())
        previous = request.session.get("staff_last_activity")
        if idle_timeout > 0 and previous and now - int(previous) > idle_timeout:
            record_audit(request, AuditLog.Action.LOGOUT, summary="Session expired after inactivity")
            logout(request)
            return redirect(reverse("backoffice:login") + "?expired=1")
        request.session["staff_last_activity"] = now

        permission = _permission(route_name, request.method)
        allowed = request.user.is_superuser or permission is None or (permission != "__deny__" and request.user.has_perm(permission))
        if not allowed:
            record_audit(request, AuditLog.Action.DENIED, status_code=403, summary=f"Denied route {route_name or request.path}; required {permission}", route_name=route_name)
            return render(request, "backoffice/auth/403.html", {"required_permission": permission}, status=403)

        response = self.get_response(request)
        if request.method in MUTATING_METHODS and route_name not in {"login", "logout"}:
            record_audit(request, AuditLog.Action.MUTATE, status_code=response.status_code, summary=f"{request.method} {route_name or request.path}", route_name=route_name)
        return response
