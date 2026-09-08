# TechBari — Django E-commerce + Admin

**Current version: v2.7.0**

TechBari is a MySQL 8-backed commerce platform built around one shared business architecture:

**One Product Database + One Inventory Engine + One Sales Engine + One Accounting Ledger.**

Catalog, Inventory, Serial / IMEI / Warranty, Supplier / Purchase, Customer / CRM, Sales Order, Storefront Checkout, POS, Payment, Shipping / Courier, Returns / Refunds, Accounting, Expense Management, Reports, Promotion / Marketing, Dashboard Analytics, Staff Access Control, CMS / Store Settings and Customer Account are connected to real database-backed business flows.

## v2.7.0 — Customer Account

The storefront customer experience is now database-backed and connected to the existing CRM, Sales, Shipping and Serial / Warranty data.

Included:

- customer register, login and logout
- customer dashboard
- order history and customer-scoped order details
- public order tracking with order-number + phone verification
- owned courier tracking and shipment history
- database-backed wishlist
- saved delivery addresses with one-default invariant
- customer profile editing
- password change while keeping the session valid
- warranty / Serial / IMEI lookup scoped to the customer's purchases
- logged-in checkout reuses the linked CRM Customer instead of creating duplicates
- guest checkout setting is enforced server-side
- staff portal users cannot sign in through customer login
- existing CRM purchase history requires a verified previous order number before self-linking
- CRM records with opening balances cannot be self-claimed without stronger verification/support activation
- shipping recipient/destination data does not overwrite the linked CRM customer's identity/profile

Customer accounts use Django authentication users with `is_staff=False`, linked one-to-one to the existing `customers.Customer` CRM record through `CustomerAccount`. See `CUSTOMER_ACCOUNT_PHASE.md`.

Customer routes include:

- `/login/`
- `/register/`
- `/wishlist/`
- `/track-order/`
- `/account/`
- `/account/orders/`
- `/account/addresses/`
- `/account/profile/`
- `/account/password/`
- `/account/warranty/`

## v2.6.0 — CMS / Store Settings

The previous static Settings demo and hardcoded storefront business content are now database-backed.

Included:

- shop name, tagline and business/contact information
- logo and favicon uploads
- Facebook / YouTube / Instagram / TikTok / WhatsApp settings
- editable storefront top-bar and footer copy
- scheduled/reorderable Hero Banners
- enabled/disabled/reorderable Homepage Sections
- Inside/Outside Dhaka delivery charges and delivery estimates
- free-delivery threshold
- COD enable/disable rule
- Terms & Conditions
- Privacy Policy
- Return & Refund Policy
- Shipping Policy
- default and homepage SEO metadata
- server-side `manage_store_settings` permission enforcement

Checkout uses the database delivery settings as a server-side source of truth; browser values cannot override the configured final shipping charge. See `CMS_STORE_SETTINGS_PHASE.md`.

CMS routes:

- `/dashboard/settings/`
- `/dashboard/settings/banners/`
- `/dashboard/settings/homepage/`
- `/dashboard/settings/pages/`

Public policy routes:

- `/terms-and-conditions/`
- `/privacy-policy/`
- `/return-refund-policy/`
- `/shipping-policy/`

## v2.5.0 — Users / Roles / Permissions

Dashboard staff authentication uses Django auth/session with Admin, Manager, Cashier, Inventory Manager, Accountant and Sales Staff roles; fine-grained permissions, password reset/change, idle-session expiry and database-backed Audit Log are implemented. Default Cashier cannot access Accounting or edit Accounting settings. See `STAFF_ACCESS_PHASE.md`.

## v2.4.0 — Dashboard Analytics

Database-backed management KPIs include Today Sales, Orders, Profit, Stock Alerts, Top Products/Categories, Purchase/Customer Due, Sales Trend, POS vs Online/Manual and Recent Activity. See `DASHBOARD_ANALYTICS_PHASE.md`.

## v2.3.0 — Promotion / Marketing

Database-backed Coupons, Flash Sales, Featured Products and Campaign attribution are integrated with server-authoritative checkout. See `PROMOTION_MARKETING_PHASE.md`.

## Reports v2.2.x

- **v2.2.0** — Sales / Daily / Monthly / POS vs Online / Product / Category / Brand / Profit / COGS
- **v2.2.1** — Stock / Valuation / Low Stock / Movement / Purchase / Supplier Due / Customer Due
- **v2.2.2** — Payment / Expense / Returns / Warranty / Serial-IMEI
- **v2.2.3** — P&L / Balance Sheet / Cash Flow / Trial Balance

Financial statements use the Accounting General Ledger as their source of truth.

## Completed business phases

- **v2.7.0 — Customer Account** — customer auth, CRM-safe linking, account dashboard, order/tracking, wishlist, addresses, profile/password and warranty lookup. See `CUSTOMER_ACCOUNT_PHASE.md`.
- **v2.6.0 — CMS / Store Settings** — branding, contact/social, hero/homepage CMS, delivery rules, policies and SEO. See `CMS_STORE_SETTINGS_PHASE.md`.
- **v2.5.0 — Users / Roles / Permissions** — staff authentication, six roles, fine-grained RBAC, password reset/session security and Audit Log. See `STAFF_ACCESS_PHASE.md`.
- **v2.4.0 — Dashboard Analytics** — real management KPIs, trends, due balances, stock alerts and recent activity. See `DASHBOARD_ANALYTICS_PHASE.md`.
- **v2.3.0 — Promotion / Marketing** — Coupons, Flash Sales, Featured Products and Campaign tracking. See `PROMOTION_MARKETING_PHASE.md`.
- **v2.2.x — Reports** — operational reports plus GL-backed financial statements. See `REPORTS_PHASE.md`.
- **v2.1.1 — Expense Management** — expense workflow and GL posting. See `EXPENSE_MANAGEMENT_PHASE.md`.
- **v2.0.0 — Accounting / General Ledger** — double-entry accounting and ledger. See `ACCOUNTING_SYSTEM_PHASE.md`.
- **v1.10.0 — Returns / Refunds**
- **v1.9.0 — Shipping / Courier**
- **v1.8.0 — Payment System**
- **v1.7.0 — POS**
- **v1.6.0 — Storefront Checkout Backend**
- **v1.5.0 — Customer CRM + Sales Order Engine**
- **v1.3.0 — Supplier + Purchase**
- **v1.2.0 — Serial / IMEI / Warranty**
- **v1.1.0 — Inventory**
- **v1.0.10 — Catalog**

## Local setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Configure MySQL 8, then:

```powershell
python manage.py migrate
python manage.py bootstrap_admin --email admin@example.com
python manage.py check
python manage.py test catalog inventory serial_tracking purchasing customers sales payments shipping returns accounting expenses reports promotions storefront backoffice.test_dashboard_analytics staff_access store_settings customer_accounts
python manage.py runserver
```

v2.7.0 introduces `customer_accounts/0001_initial.py`; `python manage.py migrate` is required.

## Validation

v2.7.0 is validated on MySQL 8.0.46 / Python 3.12.14 with:

- Customer Account dedicated suite: **20/20 PASS**
- full project regression: **243/243 PASS**
- Django system check: **PASS**
- migration drift: **PASS / No changes detected**
- migration application: **PASS**

## Roadmap direction

Next planned phases:

- **v2.8.x — Notifications + Integrations**
- **v3.0 — Final Production Phase**
