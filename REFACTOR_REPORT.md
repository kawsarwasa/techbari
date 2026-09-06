TechBari static template refactor is implemented. The application continues to run with the Django dummy database backend. No database, database model or migration was created, and neither migration command was run. The original empty models.py placeholders remain unchanged.

Changes include shared storefront/dashboard bases, reusable includes and components, named URLs with legacy redirects, Python fixtures, safe JSON context for existing JavaScript, per-product slug/ID detail pages, branded errors, and database-free validation scripts. The existing localStorage keys remain compatible.

The full project structure, mock-data boundaries, run instructions and limitations are documented in [ARCHITECTURE.md](ARCHITECTURE.md).

Validation completed:

| Check | Result |
| --- | --- |
| `python manage.py check` | No issues |
| Live development server after restart | All 89 page/detail URLs and checked CSS/JavaScript assets return HTTP 200 |
| `python scripts/validate_static.py` | 89 page/detail URLs and 166 link/asset targets pass; all templates compile |
| Python AST parsing and `python -m compileall -q techbari storefront backoffice scripts` | Pass |
| `node --check` on all three JavaScript files | Pass |
| `node scripts/validate_interactions.cjs ...` with temporary jsdom installation | All 89 URLs initialize; interaction checks pass |
| Database connection guard while rendering | No database connection attempted |
| Static assets compared against the pre-refactor backup | All 64 CSS/image files unchanged |
| Original/new DOM structure, CSS classes and inline styles | 54/55 exact matches; listing wishlist state corrected for repeated products |
| Minimum declared font-size check | All explicit pixel sizes are at least 13px |
| Browser screenshot / computed viewport checks | Unavailable: no connected browser |

Interaction checks cover slider navigation, product search, wishlist persistence, product gallery and quantity, cart removal/clearing, coupons, delivery selection, login/register validation, product creation/edit/deletion, empty-catalog persistence, customer/supplier/coupon creation, localStorage detail records, and POS quantities/payment/search/completion.

All created routes are listed below. The legacy routes redirect known old HTML addresses and preserve their query strings.

| Route name | Path |
| --- | --- |
| `storefront:home` | `/` |
| `storefront:products` | `/products/` |
| `storefront:cart` | `/cart/` |
| `storefront:checkout` | `/checkout/` |
| `storefront:wishlist` | `/wishlist/` |
| `storefront:track_order` | `/track-order/` |
| `storefront:login` | `/login/` |
| `storefront:register` | `/register/` |
| `storefront:contact` | `/contact/` |
| `storefront:product_detail` | `/product/<slug:slug>/` |
| `storefront:product_by_id` | `/product/id/<slug:product_id>/` |
| `storefront:legacy_page` | `/<slug:page>.html` |
| `backoffice:accounts` | `/dashboard/accounts/` |
| `backoffice:audit_log` | `/dashboard/audit-log/` |
| `backoffice:brand_add` | `/dashboard/brands/add/` |
| `backoffice:brands` | `/dashboard/brands/` |
| `backoffice:categories` | `/dashboard/categories/` |
| `backoffice:category_add` | `/dashboard/categories/add/` |
| `backoffice:coupon_add` | `/dashboard/coupons/add/` |
| `backoffice:coupons` | `/dashboard/coupons/` |
| `backoffice:customer_detail` | `/dashboard/customers/detail/` |
| `backoffice:customer_add` | `/dashboard/customers/add/` |
| `backoffice:customers` | `/dashboard/customers/` |
| `backoffice:dashboard` | `/dashboard/` |
| `backoffice:expense_add` | `/dashboard/expenses/add/` |
| `backoffice:expenses` | `/dashboard/expenses/` |
| `backoffice:inventory` | `/dashboard/inventory/` |
| `backoffice:marketing` | `/dashboard/marketing/` |
| `backoffice:notifications` | `/dashboard/notifications/` |
| `backoffice:order_detail` | `/dashboard/orders/detail/` |
| `backoffice:order_add` | `/dashboard/orders/add/` |
| `backoffice:orders` | `/dashboard/orders/` |
| `backoffice:payment_add` | `/dashboard/payments/add/` |
| `backoffice:payments` | `/dashboard/payments/` |
| `backoffice:pos` | `/dashboard/pos/` |
| `backoffice:product_edit` | `/dashboard/products/edit/` |
| `backoffice:product_add` | `/dashboard/products/add/` |
| `backoffice:products` | `/dashboard/products/` |
| `backoffice:purchase_add` | `/dashboard/purchases/add/` |
| `backoffice:purchases` | `/dashboard/purchases/` |
| `backoffice:reports` | `/dashboard/reports/` |
| `backoffice:return_add` | `/dashboard/returns/add/` |
| `backoffice:returns` | `/dashboard/returns/` |
| `backoffice:serial_add` | `/dashboard/serials/add/` |
| `backoffice:serials` | `/dashboard/serials/` |
| `backoffice:settings` | `/dashboard/settings/` |
| `backoffice:shipment_add` | `/dashboard/shipping/add/` |
| `backoffice:shipping` | `/dashboard/shipping/` |
| `backoffice:stock_adjustment` | `/dashboard/stock-adjustment/` |
| `backoffice:stock_transfer` | `/dashboard/stock-transfer/` |
| `backoffice:supplier_add` | `/dashboard/suppliers/add/` |
| `backoffice:suppliers` | `/dashboard/suppliers/` |
| `backoffice:user_add` | `/dashboard/users/add/` |
| `backoffice:users` | `/dashboard/users/` |
| `backoffice:warehouse_add` | `/dashboard/warehouses/add/` |
| `backoffice:warehouses` | `/dashboard/warehouses/` |
| `backoffice:warranty_add` | `/dashboard/warranty/add/` |
| `backoffice:warranty` | `/dashboard/warranty/` |
| `backoffice:legacy_page` | `/dashboard/<slug:page>.html` |

The original page files moved into the following inherited templates. The redundant backoffice index redirect template was removed; its URL still redirects to the dashboard.

| Previous file | Current template |
| --- | --- |
| `templates/storefront/index.html` | `templates/storefront/pages/home.html` |
| `templates/storefront/product.html` | `templates/storefront/pages/product_detail.html` |
| `templates/storefront/track-order.html` | `templates/storefront/pages/track_order.html` |
| `templates/storefront/products.html` | `templates/storefront/pages/products.html` |
| `templates/storefront/cart.html` | `templates/storefront/pages/cart.html` |
| `templates/storefront/checkout.html` | `templates/storefront/pages/checkout.html` |
| `templates/storefront/wishlist.html` | `templates/storefront/pages/wishlist.html` |
| `templates/storefront/login.html` | `templates/storefront/pages/login.html` |
| `templates/storefront/contact.html` | `templates/storefront/pages/contact.html` |
| `templates/backoffice/accounts.html` | `templates/backoffice/pages/accounts/accounts.html` |
| `templates/backoffice/audit-log.html` | `templates/backoffice/pages/audit/audit_log.html` |
| `templates/backoffice/brand-form.html` | `templates/backoffice/pages/brands/brand_add.html` |
| `templates/backoffice/brands.html` | `templates/backoffice/pages/brands/brands.html` |
| `templates/backoffice/categories.html` | `templates/backoffice/pages/categories/categories.html` |
| `templates/backoffice/category-form.html` | `templates/backoffice/pages/categories/category_add.html` |
| `templates/backoffice/coupon-form.html` | `templates/backoffice/pages/coupons/coupon_add.html` |
| `templates/backoffice/coupons.html` | `templates/backoffice/pages/coupons/coupons.html` |
| `templates/backoffice/customer-details.html` | `templates/backoffice/pages/customers/customer_detail.html` |
| `templates/backoffice/customer-form.html` | `templates/backoffice/pages/customers/customer_add.html` |
| `templates/backoffice/customers.html` | `templates/backoffice/pages/customers/customers.html` |
| `templates/backoffice/dashboard.html` | `templates/backoffice/pages/dashboard.html` |
| `templates/backoffice/expense-form.html` | `templates/backoffice/pages/expenses/expense_add.html` |
| `templates/backoffice/expenses.html` | `templates/backoffice/pages/expenses/expenses.html` |
| `templates/backoffice/inventory.html` | `templates/backoffice/pages/inventory/inventory.html` |
| `templates/backoffice/marketing.html` | `templates/backoffice/pages/marketing/marketing.html` |
| `templates/backoffice/notifications.html` | `templates/backoffice/pages/notifications/notifications.html` |
| `templates/backoffice/order-details.html` | `templates/backoffice/pages/orders/order_detail.html` |
| `templates/backoffice/order-form.html` | `templates/backoffice/pages/orders/order_add.html` |
| `templates/backoffice/orders.html` | `templates/backoffice/pages/orders/orders.html` |
| `templates/backoffice/payment-form.html` | `templates/backoffice/pages/payments/payment_add.html` |
| `templates/backoffice/payments.html` | `templates/backoffice/pages/payments/payments.html` |
| `templates/backoffice/pos.html` | `templates/backoffice/pages/pos/pos.html` |
| `templates/backoffice/product-edit.html` | `templates/backoffice/pages/products/product_edit.html` |
| `templates/backoffice/product-form.html` | `templates/backoffice/pages/products/product_add.html` |
| `templates/backoffice/products.html` | `templates/backoffice/pages/products/products.html` |
| `templates/backoffice/purchase-form.html` | `templates/backoffice/pages/purchases/purchase_add.html` |
| `templates/backoffice/purchases.html` | `templates/backoffice/pages/purchases/purchases.html` |
| `templates/backoffice/reports.html` | `templates/backoffice/pages/reports/reports.html` |
| `templates/backoffice/return-form.html` | `templates/backoffice/pages/returns/return_add.html` |
| `templates/backoffice/returns.html` | `templates/backoffice/pages/returns/returns.html` |
| `templates/backoffice/serial-form.html` | `templates/backoffice/pages/serials/serial_add.html` |
| `templates/backoffice/serials.html` | `templates/backoffice/pages/serials/serials.html` |
| `templates/backoffice/settings.html` | `templates/backoffice/pages/settings/settings.html` |
| `templates/backoffice/shipment-form.html` | `templates/backoffice/pages/shipping/shipment_add.html` |
| `templates/backoffice/shipping.html` | `templates/backoffice/pages/shipping/shipping.html` |
| `templates/backoffice/stock-adjustment.html` | `templates/backoffice/pages/inventory/stock_adjustment.html` |
| `templates/backoffice/stock-transfer.html` | `templates/backoffice/pages/inventory/stock_transfer.html` |
| `templates/backoffice/supplier-form.html` | `templates/backoffice/pages/suppliers/supplier_add.html` |
| `templates/backoffice/suppliers.html` | `templates/backoffice/pages/suppliers/suppliers.html` |
| `templates/backoffice/user-form.html` | `templates/backoffice/pages/users/user_add.html` |
| `templates/backoffice/users.html` | `templates/backoffice/pages/users/users.html` |
| `templates/backoffice/warehouse-form.html` | `templates/backoffice/pages/warehouses/warehouse_add.html` |
| `templates/backoffice/warehouses.html` | `templates/backoffice/pages/warehouses/warehouses.html` |
| `templates/backoffice/warranty-form.html` | `templates/backoffice/pages/warranty/warranty_add.html` |
| `templates/backoffice/warranty.html` | `templates/backoffice/pages/warranty/warranty.html` |

Files created (including the new destinations of moved templates):

- `ARCHITECTURE.md`
- `REFACTOR_REPORT.md`
- `backoffice/context.py`
- `backoffice/mock_data.py`
- `backoffice/page_data.py`
- `backoffice/page_registry.py`
- `backoffice/table_config.py`
- `scripts/validate_interactions.cjs`
- `scripts/validate_static.py`
- `storefront/context.py`
- `storefront/mock_data.py`
- `storefront/templatetags/__init__.py`
- `storefront/templatetags/demo.py`
- `techbari/views.py`
- `templates/404.html`
- `templates/500.html`
- `templates/backoffice/base.html`
- `templates/backoffice/components/breadcrumb.html`
- `templates/backoffice/components/campaign_card.html`
- `templates/backoffice/components/form_actions.html`
- `templates/backoffice/components/icons/icon_0.html`
- `templates/backoffice/components/icons/icon_1.html`
- `templates/backoffice/components/icons/icon_10.html`
- `templates/backoffice/components/icons/icon_11.html`
- `templates/backoffice/components/icons/icon_12.html`
- `templates/backoffice/components/icons/icon_13.html`
- `templates/backoffice/components/icons/icon_14.html`
- `templates/backoffice/components/icons/icon_15.html`
- `templates/backoffice/components/icons/icon_16.html`
- `templates/backoffice/components/icons/icon_17.html`
- `templates/backoffice/components/icons/icon_18.html`
- `templates/backoffice/components/icons/icon_19.html`
- `templates/backoffice/components/icons/icon_2.html`
- `templates/backoffice/components/icons/icon_20.html`
- `templates/backoffice/components/icons/icon_21.html`
- `templates/backoffice/components/icons/icon_22.html`
- `templates/backoffice/components/icons/icon_3.html`
- `templates/backoffice/components/icons/icon_4.html`
- `templates/backoffice/components/icons/icon_5.html`
- `templates/backoffice/components/icons/icon_6.html`
- `templates/backoffice/components/icons/icon_7.html`
- `templates/backoffice/components/icons/icon_8.html`
- `templates/backoffice/components/icons/icon_9.html`
- `templates/backoffice/components/icons/notification_0.html`
- `templates/backoffice/components/icons/notification_1.html`
- `templates/backoffice/components/icons/notification_2.html`
- `templates/backoffice/components/icons/notification_3.html`
- `templates/backoffice/components/icons/report_0.html`
- `templates/backoffice/components/icons/report_1.html`
- `templates/backoffice/components/icons/report_2.html`
- `templates/backoffice/components/icons/report_3.html`
- `templates/backoffice/components/icons/report_4.html`
- `templates/backoffice/components/icons/report_5.html`
- `templates/backoffice/components/icons/report_6.html`
- `templates/backoffice/components/icons/report_7.html`
- `templates/backoffice/components/icons/report_8.html`
- `templates/backoffice/components/modal.html`
- `templates/backoffice/components/notification.html`
- `templates/backoffice/components/product_breadcrumb.html`
- `templates/backoffice/components/record_row.html`
- `templates/backoffice/components/report_card.html`
- `templates/backoffice/components/stat_card.html`
- `templates/backoffice/components/status_badge.html`
- `templates/backoffice/components/stock_alert.html`
- `templates/backoffice/components/table_pagination.html`
- `templates/backoffice/includes/breadcrumbs/brand_add.html`
- `templates/backoffice/includes/breadcrumbs/category_add.html`
- `templates/backoffice/includes/breadcrumbs/coupon_add.html`
- `templates/backoffice/includes/breadcrumbs/customer_add.html`
- `templates/backoffice/includes/breadcrumbs/customer_detail.html`
- `templates/backoffice/includes/breadcrumbs/expense_add.html`
- `templates/backoffice/includes/breadcrumbs/order_add.html`
- `templates/backoffice/includes/breadcrumbs/order_detail.html`
- `templates/backoffice/includes/breadcrumbs/payment_add.html`
- `templates/backoffice/includes/breadcrumbs/product_add.html`
- `templates/backoffice/includes/breadcrumbs/product_edit.html`
- `templates/backoffice/includes/breadcrumbs/purchase_add.html`
- `templates/backoffice/includes/breadcrumbs/return_add.html`
- `templates/backoffice/includes/breadcrumbs/serial_add.html`
- `templates/backoffice/includes/breadcrumbs/shipment_add.html`
- `templates/backoffice/includes/breadcrumbs/stock_adjustment.html`
- `templates/backoffice/includes/breadcrumbs/stock_transfer.html`
- `templates/backoffice/includes/breadcrumbs/supplier_add.html`
- `templates/backoffice/includes/breadcrumbs/user_add.html`
- `templates/backoffice/includes/breadcrumbs/warehouse_add.html`
- `templates/backoffice/includes/breadcrumbs/warranty_add.html`
- `templates/backoffice/includes/footer.html`
- `templates/backoffice/includes/messages.html`
- `templates/backoffice/includes/sidebar.html`
- `templates/backoffice/includes/topbar.html`
- `templates/backoffice/pages/accounts/accounts.html`
- `templates/backoffice/pages/audit/audit_log.html`
- `templates/backoffice/pages/brands/brand_add.html`
- `templates/backoffice/pages/brands/brands.html`
- `templates/backoffice/pages/categories/categories.html`
- `templates/backoffice/pages/categories/category_add.html`
- `templates/backoffice/pages/coupons/coupon_add.html`
- `templates/backoffice/pages/coupons/coupons.html`
- `templates/backoffice/pages/customers/customer_add.html`
- `templates/backoffice/pages/customers/customer_detail.html`
- `templates/backoffice/pages/customers/customers.html`
- `templates/backoffice/pages/dashboard.html`
- `templates/backoffice/pages/expenses/expense_add.html`
- `templates/backoffice/pages/expenses/expenses.html`
- `templates/backoffice/pages/inventory/inventory.html`
- `templates/backoffice/pages/inventory/stock_adjustment.html`
- `templates/backoffice/pages/inventory/stock_transfer.html`
- `templates/backoffice/pages/marketing/marketing.html`
- `templates/backoffice/pages/notifications/notifications.html`
- `templates/backoffice/pages/orders/order_add.html`
- `templates/backoffice/pages/orders/order_detail.html`
- `templates/backoffice/pages/orders/orders.html`
- `templates/backoffice/pages/payments/payment_add.html`
- `templates/backoffice/pages/payments/payments.html`
- `templates/backoffice/pages/pos/pos.html`
- `templates/backoffice/pages/products/product_add.html`
- `templates/backoffice/pages/products/product_edit.html`
- `templates/backoffice/pages/products/products.html`
- `templates/backoffice/pages/purchases/purchase_add.html`
- `templates/backoffice/pages/purchases/purchases.html`
- `templates/backoffice/pages/reports/reports.html`
- `templates/backoffice/pages/returns/return_add.html`
- `templates/backoffice/pages/returns/returns.html`
- `templates/backoffice/pages/serials/serial_add.html`
- `templates/backoffice/pages/serials/serials.html`
- `templates/backoffice/pages/settings/settings.html`
- `templates/backoffice/pages/shipping/shipment_add.html`
- `templates/backoffice/pages/shipping/shipping.html`
- `templates/backoffice/pages/suppliers/supplier_add.html`
- `templates/backoffice/pages/suppliers/suppliers.html`
- `templates/backoffice/pages/users/user_add.html`
- `templates/backoffice/pages/users/users.html`
- `templates/backoffice/pages/warehouses/warehouse_add.html`
- `templates/backoffice/pages/warehouses/warehouses.html`
- `templates/backoffice/pages/warranty/warranty.html`
- `templates/backoffice/pages/warranty/warranty_add.html`
- `templates/storefront/base.html`
- `templates/storefront/components/breadcrumb.html`
- `templates/storefront/components/empty_state.html`
- `templates/storefront/components/pagination.html`
- `templates/storefront/components/product_card.html`
- `templates/storefront/includes/breadcrumbs/cart.html`
- `templates/storefront/includes/breadcrumbs/checkout.html`
- `templates/storefront/includes/breadcrumbs/contact.html`
- `templates/storefront/includes/breadcrumbs/product_detail.html`
- `templates/storefront/includes/breadcrumbs/products.html`
- `templates/storefront/includes/breadcrumbs/wishlist.html`
- `templates/storefront/includes/footer.html`
- `templates/storefront/includes/header.html`
- `templates/storefront/includes/messages.html`
- `templates/storefront/includes/mobile_nav.html`
- `templates/storefront/pages/cart.html`
- `templates/storefront/pages/checkout.html`
- `templates/storefront/pages/contact.html`
- `templates/storefront/pages/home.html`
- `templates/storefront/pages/login.html`
- `templates/storefront/pages/product_detail.html`
- `templates/storefront/pages/products.html`
- `templates/storefront/pages/track_order.html`
- `templates/storefront/pages/wishlist.html`

Existing files modified:

- `PROJECT_MANIFEST.json`
- `README.md`
- `backoffice/urls.py`
- `backoffice/views.py`
- `static/admin/js/admin.js`
- `static/admin/js/product-crud.js`
- `static/store/js/app.js`
- `storefront/urls.py`
- `storefront/views.py`
- `techbari/urls.py`

Old paths removed: the 55 page paths in the move table above, plus `templates/backoffice/index.html`. No CSS or image asset was removed.

Mock-data modules: `storefront/mock_data.py` contains the 15-product catalog, categories, brands, product images/specifications/variants/reviews, coupon definitions, initial cart/wishlist, hero slides and tracking order. `backoffice/mock_data.py` contains 18 business collections, 12 POS products and page statistics. `backoffice/page_data.py` contains dashboard/report/account summaries, campaigns, notifications, alerts, timelines, history, form defaults and options. Context modules adapt these fixtures to templates and JSON without ORM calls.

Known limitations: demo actions do not provide real checkout, payments or authentication; several original filters/export/toolbar controls remain presentation-only. Metrics and ancillary detail panels are static snapshots. Browser CRUD changes do not update Python fixtures or synchronize between browsers. LocalStorage detail links fill their record fields in the browser. The original external font/tracking-image dependencies remain. Responsive CSS is unchanged, but screenshot and computed overflow verification could not be performed without a connected browser.

Pre-refactor backup: `C:\Users\user\AppData\Local\Temp\techbari-before-template-refactor.zip`.
