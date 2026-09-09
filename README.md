# TechBari — Django E-commerce + Admin

**Current version: v3.0.0**

TechBari is a MySQL 8-backed commerce platform built around one shared business architecture:

**One Product Database + One Inventory Engine + One Sales Engine + One Accounting Ledger.**

Catalog, Inventory, Serial / IMEI / Warranty, Supplier / Purchase, Customer / CRM, Sales Order, Storefront Checkout, POS, Payment, Shipping / Courier, Returns / Refunds, Accounting, Expense Management, Reports, Promotion / Marketing, Dashboard Analytics, Staff Access Control, CMS / Store Settings, Customer Account and Notifications / Integrations are connected to real database-backed business flows.

## v3.0.0 — Final Production

v3.0.0 turns the completed business system into a production-ready release baseline.

Included:

- production settings fail closed when `DEBUG=False` with weak secrets or wildcard hosts
- HTTPS redirect, secure cookies, HSTS configuration, referrer/content-type/cross-origin headers and X-Frame clickjacking protection
- explicit trusted-proxy handling instead of unconditionally trusting forwarded client IP headers
- request/upload limits and hardened CMS logo/favicon/banner image validation
- database-backed staff/customer login throttling
- strict customer/staff identity boundary even though both use Django auth
- staff management pages scoped to real staff users only
- outbound SMS/WhatsApp/Courier URL validation with HTTPS/private-network SSRF protection
- timestamped HMAC courier webhooks with stale-request and replay protection
- minimal database-backed `/health/` readiness endpoint
- `python manage.py production_preflight` release/deployment gate
- `python manage.py cleanup_security_state` maintenance command
- recent Sales activity index for production reporting/dashboard access patterns
- environment-driven production logging, database connection persistence and email settings
- deployment, backup/restore, cron, static/media and rollback guidance in `PRODUCTION_DEPLOYMENT.md`

New migrations:

- `integrations/0002_v300_webhook_receipts.py`
- `staff_access/0003_v300_auth_hardening.py`
- `sales/0004_v300_production_indexes.py`

See `PRODUCTION_DEPLOYMENT.md` before putting a real deployment online.

## v2.8.0 — Notifications / Integrations

TechBari has a database-backed notification center and a shared-hosting-friendly external integration outbox.

Included:

- real staff notifications for orders, payments, low/out-of-stock and shipping events
- per-user read/unread state and live dashboard bell count
- database outbox with idempotency, retry state and exponential retry delay
- email delivery through Django email backend
- generic SMS and WhatsApp webhook adapters
- Meta Pixel browser events: PageView, ViewContent, AddToCart, InitiateCheckout and Purchase
- Meta Conversions API Purchase queue using the same stable event ID as browser Purchase
- GA4 browser tracking plus server-side Measurement Protocol Purchase
- generic courier booking adapter configured by courier code and environment variables
- HMAC-SHA256 signed courier webhook for tracking/status updates
- integration delivery failure alerts
- `view_notifications` and `manage_integrations` staff permissions
- external secrets stay in environment variables rather than database/dashboard fields
- shared-hosting processor command: `python manage.py process_integrations --limit 100`

See `NOTIFICATIONS_INTEGRATIONS_PHASE.md` for configuration and integration details.

## v2.7.0 — Customer Account

The storefront customer experience is database-backed and connected to CRM, Sales, Shipping and Serial / Warranty data.

Included customer register/login, dashboard, order history/tracking, database wishlist, saved addresses, profile/password, owned warranty/Serial/IMEI lookup, safe existing-CRM linking and logged-in checkout CRM reuse. See `CUSTOMER_ACCOUNT_PHASE.md`.

## v2.6.0 — CMS / Store Settings

Database-backed branding, contact/social links, Hero Banners, Homepage Sections, delivery rules, policies and SEO. Checkout uses CMS delivery settings as a server-side source of truth. See `CMS_STORE_SETTINGS_PHASE.md`.

## v2.5.0 — Users / Roles / Permissions

Dashboard staff authentication uses Django auth/session with Admin, Manager, Cashier, Inventory Manager, Accountant and Sales Staff roles; fine-grained permissions, password reset/change, idle-session expiry and database-backed Audit Log are implemented. See `STAFF_ACCESS_PHASE.md`.

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

- **v3.0.0 — Final Production** — production security, preflight/readiness checks, integration/webhook hardening, login throttling, operational maintenance and deployment/backup/rollback runbook.
- **v2.8.0 — Notifications / Integrations** — notification center, outbox/retry, Email/SMS/WhatsApp hooks, Meta Pixel/CAPI, GA4 and courier adapter/webhook.
- **v2.7.0 — Customer Account** — customer auth, CRM-safe linking, account dashboard, order/tracking, wishlist, addresses, profile/password and warranty lookup.
- **v2.6.0 — CMS / Store Settings** — branding, contact/social, hero/homepage CMS, delivery rules, policies and SEO.
- **v2.5.0 — Users / Roles / Permissions** — staff authentication, six roles, fine-grained RBAC and Audit Log.
- **v2.4.0 — Dashboard Analytics** — real management KPIs, trends, due balances and stock alerts.
- **v2.3.0 — Promotion / Marketing** — Coupons, Flash Sales, Featured Products and Campaign tracking.
- **v2.2.x — Reports** — operational reports plus GL-backed financial statements.
- **v2.1.1 — Expense Management**
- **v2.0.0 — Accounting / General Ledger**
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
python manage.py test catalog inventory serial_tracking purchasing customers sales payments shipping returns accounting expenses reports promotions storefront store_settings customer_accounts staff_access backoffice.test_dashboard_analytics integrations ops
python manage.py runserver
```

v3.0.0 includes new migrations, so `python manage.py migrate` is required after updating.

For production configuration, do not copy development values blindly. Configure `.env` from `.env.example`, then run:

```text
python manage.py check --deploy --fail-level ERROR
python manage.py production_preflight
python manage.py collectstatic --noinput
```

Queued external integrations can be processed with:

```text
python manage.py process_integrations --limit 100
```

On shared hosting, schedule integration processing and security-state cleanup from cron as described in `PRODUCTION_DEPLOYMENT.md`.

## Validation

v3.0.0 production code is validated on MySQL 8.0.46 / Python 3.12.14 with:

- production/security-focused suite: **78/78 PASS**
- full project regression: **273/273 PASS**
- Django system check: **PASS**
- migration drift: **PASS / No changes detected**
- clean MySQL migration application: **PASS**
- `collectstatic`: **PASS**
- Django production `check --deploy --fail-level ERROR`: **PASS**
- `production_preflight`: **PASS**

HSTS include-subdomains/preload remain opt-in deployment decisions because they should only be enabled when every relevant subdomain is permanently HTTPS-ready.

## Production baseline

The planned v1.x → v2.x → v3.0 roadmap is complete. Future work should be treated as post-v3 enhancements, operational improvements or new product requirements rather than unfinished core roadmap phases.
