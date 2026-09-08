# TechBari — Django E-commerce + Admin

**Current version: v2.5.0**

TechBari is a MySQL 8-backed commerce platform built around one shared business architecture:

**One Product Database + One Inventory Engine + One Sales Engine + One Accounting Ledger.**

Catalog, Inventory, Serial / IMEI / Warranty, Supplier / Purchase, Customer / CRM, Sales Order, Storefront Checkout, POS, Payment, Shipping / Courier, Returns / Refunds, Accounting, Expense Management, Reports, Promotion / Marketing, Dashboard Analytics and Staff Access Control are connected to the real business data flow.

## v2.5.0 — Users / Roles / Permissions

The dashboard is now private and database-backed for staff authentication/authorization instead of using static User/Audit demo data.

Included:

- Admin
- Manager
- Cashier
- Inventory Manager
- Accountant
- Sales Staff
- fine-grained module/action permissions
- username or staff-email login
- password reset and password change
- secure Django sessions with idle timeout
- database-backed Audit Log
- real User add/edit/activate/deactivate
- editable non-Admin role permission matrix
- per-user extra permission grants
- permission-aware sidebar and server-side route enforcement

The required Accounting restriction is enforced server-side: a default Cashier cannot open Accounting or edit Chart of Accounts / Accounting periods. Hiding sidebar links is not the security boundary; `StaffAccessMiddleware` checks direct URL access too.

Dashboard staff routes include:

- `/dashboard/login/`
- `/dashboard/users/`
- `/dashboard/users/roles/`
- `/dashboard/audit-log/`
- `/dashboard/password-reset/`

After migrating a new/local database, create the first administrator with:

```powershell
python manage.py bootstrap_admin --email admin@example.com
```

See `STAFF_ACCESS_PHASE.md` for the role matrix, permission semantics, session rules, audit behavior, bootstrap command and test strategy.

## v2.4.0 — Dashboard Analytics

The main admin dashboard is database-backed instead of static/demo data.

Included: Today Sales, Orders, Profit, Stock Alerts, Top Products, Top Categories, Purchase Due, Customer Due, Sales Trend, POS vs Online / Manual, Recent Activity and date filtering. Sales/profit analytics reuse the return-aware Reports calculation layer.

See `DASHBOARD_ANALYTICS_PHASE.md`.

## v2.3.0 — Promotion / Marketing

Promotion / Marketing is database-backed and integrated with the real Storefront Checkout and Sales Order flow: Coupons, fixed/percentage discounts, minimum/date/usage rules, product/category scope, Flash Sales, Featured Products and Campaign attribution.

See `PROMOTION_MARKETING_PHASE.md`.

## Reports v2.2.x — completed

- **v2.2.0** — Sales / Daily / Monthly / POS vs Online / Product / Category / Brand / Profit / COGS
- **v2.2.1** — Stock / Valuation / Low Stock / Movement / Purchase / Supplier Due / Customer Due
- **v2.2.2** — Payment / Expense / Returns / Warranty / Serial-IMEI
- **v2.2.3** — P&L / Balance Sheet / Cash Flow / Trial Balance

Financial statements use the Accounting General Ledger as their source of truth.

## Completed business phases

- **v2.5.0 — Users / Roles / Permissions** — staff authentication, six roles, fine-grained RBAC, password reset/session security and Audit Log. See `STAFF_ACCESS_PHASE.md`.
- **v2.4.0 — Dashboard Analytics** — real management KPIs, trends, channel/product/category analysis, due balances, stock alerts and recent activity. See `DASHBOARD_ANALYTICS_PHASE.md`.
- **v2.3.0 — Promotion / Marketing** — database-backed Coupons, Flash Sales, Featured Products and Campaign tracking. See `PROMOTION_MARKETING_PHASE.md`.
- **v2.2.x — Reports** — operational reports plus GL-backed P&L, Balance Sheet, Cash Flow and Trial Balance. See `REPORTS_PHASE.md`.
- **v2.1.1 — Expense Management** — category → GL mapping, approval/payment lifecycle, attachment and GL posting. See `EXPENSE_MANAGEMENT_PHASE.md`.
- **v2.0.0 — Accounting / General Ledger** — double-entry Chart of Accounts, automatic journals, periods, General Ledger and Trial Balance. See `ACCOUNTING_SYSTEM_PHASE.md`.
- **v1.10.0 — Returns / Refunds** — controlled returns, inventory disposition and refunds. See `RETURNS_REFUNDS_PHASE.md`.
- **v1.9.0 — Shipping / Courier** — shipment lifecycle, courier tracking and COD settlement. See `SHIPPING_COURIER_PHASE.md`.
- **v1.8.0 — Payment System** — central payment ledger with refunds, reversals and reconciliation. See `PAYMENT_SYSTEM_PHASE.md`.
- **v1.7.0 — POS** — warehouse-aware counter sales, hold/resume and receipt. See `POS_SYSTEM_PHASE.md`.
- **v1.6.0 — Storefront Checkout Backend** — online Sales Orders, CRM linkage and stock reservation. See `CHECKOUT_BACKEND_PHASE.md`.
- **v1.5.0 — Customer CRM + Sales Order Engine** — shared CRM and Sales lifecycle. See `CRM_SALES_PHASE.md`.
- **v1.3.0 — Supplier + Purchase** — Purchase Orders, receiving, payments and Purchase Returns. See `SUPPLIER_PURCHASE_PHASE.md`.
- **v1.2.0 — Serial / IMEI / Warranty** — unit-level tracking and Warranty/RMA. See `SERIAL_IMEI_WARRANTY_PHASE.md`.
- **v1.1.0 — Inventory** — warehouse/SKU ledger, reservations, adjustments and transfers. See `INVENTORY_PHASE1.md`.
- **v1.0.10 — Catalog** — Categories, Brands, Products, Variants/SKUs/Barcodes, media and specifications. See `CATALOG_DATABASE_PHASE.md`.

## Main database-backed modules

- **Catalog** — categories, brands, products, variants/SKUs/barcodes, pricing, media and specifications.
- **Inventory** — warehouses, on-hand/reserved/available stock, immutable movement ledger, adjustments and transfers.
- **Serial / IMEI / Warranty** — serialized-unit lifecycle and claims.
- **Supplier + Purchase** — Purchase Orders, receiving, supplier payments and Purchase Returns.
- **Customer / CRM** — groups, addresses, opening due, purchase history and due tracking.
- **Sales Order** — Online / Manual / POS channels, reservation/deduction and return-credit-aware balances.
- **Storefront Checkout** — server-authoritative checkout, CRM linkage, promotions and idempotency.
- **POS** — warehouse-aware counter sales, tenders and receipts.
- **Payment** — central payment ledger with partial payments, refunds, reversals and reconciliation.
- **Shipping / Courier** — providers, shipment lifecycle, tracking and COD settlement.
- **Returns / Refunds** — returns, inventory disposition and refund allocation.
- **Accounting** — double-entry Chart of Accounts, journals, AR/AP, cash/payment assets, Inventory/COGS, Revenue/Expense, periods and ledger.
- **Expense Management** — categories, approval/payment workflow, attachments and GL posting.
- **Reports** — operational reports plus GL-backed financial statements.
- **Promotion / Marketing** — Coupons, Flash Sales, Featured Products and Campaign attribution.
- **Dashboard Analytics** — management KPIs, trends, stock alerts, due balances and recent activity.
- **Staff Access Control** — Users, roles, fine-grained permissions, login/session security and Audit Log.

## Local setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Configure MySQL 8 in `.env`:

```env
DB_NAME=techbari
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_HOST=127.0.0.1
DB_PORT=3306
```

Apply migrations, create the first administrator and verify:

```powershell
python manage.py migrate
python manage.py bootstrap_admin --email admin@example.com
python manage.py check
python manage.py test catalog inventory serial_tracking purchasing customers sales payments shipping returns accounting expenses reports promotions storefront backoffice.test_dashboard_analytics staff_access
python manage.py runserver
```

v2.5.0 introduces Django auth/contenttypes/session tables plus `staff_access` StaffProfile and AuditLog tables. Existing commerce/accounting data is preserved.

## Validation

v2.5.0 is validated on GitHub Actions using MySQL 8 and Python 3.12 with:

- dedicated Staff Access / RBAC security tests
- authenticated Admin route smoke coverage across major dashboard modules
- full project regression suite using the RBAC-aware test runner
- Django system check
- migration drift check
- migration application

## Roadmap direction

Next planned phases:

- **v2.6.x — CMS / Store Settings**
- **v2.7.x — Real Customer Account**
- **v2.8.x — Notifications + Integrations**
- **v3.0 — Final Production Phase**
