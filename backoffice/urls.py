from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from staff_access import views as staff_views
from . import accounting_views, catalog_views, customer_views, expense_views, inventory_views, payment_views, pos_views, purchase_views, report_views, return_views, sales_views, shipping_views, store_settings_views, views
from .page_registry import PAGES

app_name = "backoffice"

auth_patterns = [
    path("login/", staff_views.login_view, name="login"),
    path("logout/", staff_views.logout_view, name="logout"),
    path("password-reset/", auth_views.PasswordResetView.as_view(template_name="backoffice/auth/password_reset.html", email_template_name="backoffice/auth/password_reset_email.txt", subject_template_name="backoffice/auth/password_reset_subject.txt", success_url=reverse_lazy("backoffice:password_reset_done")), name="password_reset"),
    path("password-reset/done/", auth_views.PasswordResetDoneView.as_view(template_name="backoffice/auth/password_reset_done.html"), name="password_reset_done"),
    path("reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(template_name="backoffice/auth/password_reset_confirm.html", success_url=reverse_lazy("backoffice:password_reset_complete")), name="password_reset_confirm"),
    path("reset/done/", auth_views.PasswordResetCompleteView.as_view(template_name="backoffice/auth/password_reset_complete.html"), name="password_reset_complete"),
    path("password-change/", staff_views.password_change, name="password_change"),
    path("password-change/done/", staff_views.password_change_done, name="password_change_done"),
    path("users/", staff_views.users, name="users"),
    path("users/add/", staff_views.user_form, name="user_add"),
    path("users/<int:user_id>/edit/", staff_views.user_form, name="user_edit"),
    path("users/<int:user_id>/toggle/", staff_views.user_toggle, name="user_toggle"),
    path("users/roles/", staff_views.roles, name="roles"),
    path("users/roles/<int:role_id>/edit/", staff_views.role_edit, name="role_edit"),
    path("audit-log/", staff_views.audit_log, name="audit_log"),
]

catalog_patterns = [
    path("variants/", catalog_views.variants, name="catalog_variants"), path("variants/form/", catalog_views.variant_form, name="catalog_variant_form"),
    path("product-media/", catalog_views.media, name="catalog_media"), path("product-media/form/", catalog_views.media_form, name="catalog_media_form"),
    path("specifications/", catalog_views.specifications, name="catalog_specifications"), path("specifications/form/", catalog_views.specification_form, name="catalog_specification_form"),
]
inventory_patterns = [path("inventory/movements/", inventory_views.movements, name="inventory_movements"), path("inventory/low-stock/", inventory_views.low_stock, name="inventory_low_stock")]
purchase_patterns = [
    path("suppliers/<int:supplier_id>/delete/", purchase_views.supplier_delete, name="supplier_delete"), path("purchases/<int:purchase_id>/", purchase_views.purchase_detail, name="purchase_detail"),
    path("purchases/<int:purchase_id>/receive/", purchase_views.purchase_receive, name="purchase_receive"), path("purchases/<int:purchase_id>/payment/", purchase_views.purchase_payment, name="purchase_payment"),
    path("purchases/<int:purchase_id>/return/", purchase_views.purchase_return, name="purchase_return"), path("purchases/<int:purchase_id>/cancel/", purchase_views.purchase_cancel, name="purchase_cancel"), path("purchases/<int:purchase_id>/delete/", purchase_views.purchase_delete, name="purchase_delete"),
]
customer_patterns = [path("customers/groups/", customer_views.customer_groups, name="customer_groups"), path("customers/groups/<int:group_id>/delete/", customer_views.customer_group_delete, name="customer_group_delete"), path("customers/<int:customer_id>/", customer_views.customer_detail, name="customer_detail_id"), path("customers/<int:customer_id>/delete/", customer_views.customer_delete, name="customer_delete")]
sales_patterns = [path("orders/<int:order_id>/", sales_views.order_detail, name="order_detail_id"), path("orders/<int:order_id>/confirm/", sales_views.order_confirm, name="order_confirm"), path("orders/<int:order_id>/process/", sales_views.order_process, name="order_process"), path("orders/<int:order_id>/complete/", sales_views.order_complete, name="order_complete"), path("orders/<int:order_id>/cancel/", sales_views.order_cancel, name="order_cancel"), path("orders/<int:order_id>/payment/", sales_views.order_payment, name="order_payment"), path("orders/<int:order_id>/delete/", sales_views.order_delete, name="order_delete")]
pos_patterns = [path("pos/", pos_views.pos, name="pos"), path("pos/action/", pos_views.pos_action, name="pos_action"), path("pos/held/<int:order_id>/", pos_views.pos_hold_detail, name="pos_hold_detail"), path("pos/receipt/<int:order_id>/", pos_views.pos_receipt, name="pos_receipt")]
payment_patterns = [path("payments/", payment_views.payments, name="payments"), path("payments/add/", payment_views.payment_add, name="payment_add"), path("payments/methods/", payment_views.payment_methods, name="payment_methods"), path("payments/<int:payment_id>/", payment_views.payment_detail, name="payment_detail"), path("payments/<int:payment_id>/refund/", payment_views.payment_refund, name="payment_refund"), path("payments/<int:payment_id>/reverse/", payment_views.payment_reverse, name="payment_reverse"), path("payments/<int:payment_id>/reconcile/", payment_views.payment_reconcile, name="payment_reconcile")]
shipping_patterns = [path("shipping/", shipping_views.shipping, name="shipping"), path("shipping/add/", shipping_views.shipment_add, name="shipment_add"), path("shipping/providers/", shipping_views.courier_providers, name="courier_providers"), path("shipping/cod-settlements/", shipping_views.cod_settlements, name="cod_settlements"), path("shipping/cod-settlements/add/", shipping_views.cod_settlement_add, name="cod_settlement_add"), path("shipping/cod-settlements/<int:settlement_id>/", shipping_views.cod_settlement_detail, name="cod_settlement_detail"), path("shipping/<int:shipment_id>/", shipping_views.shipment_detail, name="shipment_detail"), path("shipping/<int:shipment_id>/status/", shipping_views.shipment_status, name="shipment_status"), path("shipping/<int:shipment_id>/tracking/", shipping_views.shipment_tracking, name="shipment_tracking")]
return_patterns = [path("returns/", return_views.returns, name="returns"), path("returns/add/", return_views.return_add, name="return_add"), path("returns/<int:return_id>/", return_views.return_detail, name="return_detail"), path("returns/<int:return_id>/approve/", return_views.return_approve, name="return_approve"), path("returns/<int:return_id>/receive/", return_views.return_receive, name="return_receive"), path("returns/<int:return_id>/complete/", return_views.return_complete, name="return_complete"), path("returns/<int:return_id>/reject/", return_views.return_reject, name="return_reject"), path("returns/<int:return_id>/cancel/", return_views.return_cancel, name="return_cancel")]
accounting_patterns = [path("accounts/", accounting_views.accounts, name="accounts"), path("accounts/chart/", accounting_views.chart_accounts, name="chart_accounts"), path("accounts/chart/add/", accounting_views.account_add, name="account_add"), path("accounts/journals/", accounting_views.journals, name="journals"), path("accounts/journals/add/", accounting_views.journal_add, name="journal_add"), path("accounts/journals/<int:journal_id>/", accounting_views.journal_detail, name="journal_detail"), path("accounts/journals/<int:journal_id>/reverse/", accounting_views.journal_reverse, name="journal_reverse"), path("accounts/ledger/", accounting_views.general_ledger, name="general_ledger"), path("accounts/trial-balance/", accounting_views.trial_balance_view, name="trial_balance"), path("accounts/periods/", accounting_views.periods, name="accounting_periods"), path("accounts/periods/<int:period_id>/toggle/", accounting_views.period_toggle, name="accounting_period_toggle")]
expense_patterns = [path("expenses/", expense_views.expenses, name="expenses"), path("expenses/add/", expense_views.expense_add, name="expense_add"), path("expenses/categories/", expense_views.expense_categories, name="expense_categories"), path("expenses/categories/<int:category_id>/toggle/", expense_views.expense_category_toggle, name="expense_category_toggle"), path("expenses/<int:expense_id>/", expense_views.expense_detail, name="expense_detail"), path("expenses/<int:expense_id>/edit/", expense_views.expense_edit, name="expense_edit"), path("expenses/<int:expense_id>/submit/", expense_views.expense_submit, name="expense_submit"), path("expenses/<int:expense_id>/approve/", expense_views.expense_approve, name="expense_approve"), path("expenses/<int:expense_id>/reject/", expense_views.expense_reject, name="expense_reject"), path("expenses/<int:expense_id>/cancel/", expense_views.expense_cancel, name="expense_cancel"), path("expenses/<int:expense_id>/pay/", expense_views.expense_pay, name="expense_pay"), path("expenses/<int:expense_id>/void/", expense_views.expense_void, name="expense_void")]
report_patterns = [path("reports/", report_views.reports, name="reports")]
store_settings_patterns = [
    path("settings/", store_settings_views.settings_view, name="settings"),
    path("settings/banners/", store_settings_views.banners, name="cms_banners"),
    path("settings/banners/add/", store_settings_views.banner_form, name="cms_banner_add"),
    path("settings/banners/<int:banner_id>/edit/", store_settings_views.banner_form, name="cms_banner_edit"),
    path("settings/banners/<int:banner_id>/toggle/", store_settings_views.banner_toggle, name="cms_banner_toggle"),
    path("settings/banners/<int:banner_id>/delete/", store_settings_views.banner_delete, name="cms_banner_delete"),
    path("settings/homepage/", store_settings_views.homepage_sections, name="cms_homepage_sections"),
    path("settings/homepage/<int:section_id>/update/", store_settings_views.homepage_section_update, name="cms_homepage_section_update"),
    path("settings/pages/", store_settings_views.content_pages, name="cms_content_pages"),
    path("settings/pages/<int:page_id>/edit/", store_settings_views.content_page_edit, name="cms_content_page_edit"),
]

RESERVED = {"accounts", "expenses", "expense_add", "pos", "payments", "payment_add", "shipping", "shipment_add", "returns", "return_add", "reports", "users", "user_add", "audit_log", "settings"}
urlpatterns = auth_patterns + catalog_patterns + inventory_patterns + purchase_patterns + customer_patterns + sales_patterns + pos_patterns + payment_patterns + shipping_patterns + return_patterns + accounting_patterns + expense_patterns + report_patterns + store_settings_patterns + [path(info["path"], views.page, {"page_name": name}, name=name) for name, info in PAGES.items() if name not in RESERVED]
urlpatterns += [path("<slug:page>.html", views.legacy_page, name="legacy_page")]
