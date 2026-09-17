# TechBari Architecture

**Current version: v3.0.0**

TechBari is a database-backed Django commerce platform designed around one shared business architecture:

**One Product Database + One Inventory Engine + One Sales Engine + One Accounting Ledger.**

The storefront, dashboard, POS, purchasing, inventory, accounting, reporting, customer account and integration layers all operate on the same MySQL-backed business data. Static templates remain the presentation layer, but the core business flows are now database-backed.

## Current state

### Database-backed business domains

The following domains are implemented and connected through Django ORM / MySQL 8:

- Catalog
- Inventory and warehouse stock
- Serial / IMEI / warranty tracking
- Supplier and purchasing
- Customer / CRM
- Sales order engine
- Storefront checkout
- POS
- Payments
- Shipping / courier
- Returns / refunds
- Accounting / General Ledger
- Expense management
- Reports and financial statements
- Promotions / marketing
- Dashboard analytics
- Staff users / roles / permissions / audit log
- CMS / store settings
- Customer accounts
- Notifications and external integrations

The planned v1.x -> v2.x -> v3.0 core roadmap is complete. Future work should be treated as post-v3 enhancements, operational improvements or new product requirements rather than unfinished core phases.

## Core source-of-truth boundaries

### Catalog

`catalog/` owns product merchandising and sellable-item identity, including:

- `Category`
- `Brand`
- `Product`
- `ProductVariant`
- `ProductImage`
- `ProductSpecification`

A `Product` stores shared merchandising data. A `ProductVariant` represents a sellable SKU and can have its own SKU, barcode, pricing overrides and active/default state.

Catalog data is consumed by both storefront and dashboard workflows.

### Inventory

`inventory/` is the source of truth for operational stock. Inventory is warehouse-aware and business movements are represented through inventory balances and stock movements rather than relying on catalog stock fields as the long-term authority.

Purchasing, sales, returns and stock adjustments feed the same inventory engine.

### Sales

`sales/` is the shared order engine for commercial sales activity. Storefront checkout, POS and dashboard/manual sales feed the same sales domain so reporting, receivables, stock and accounting remain consistent.

### Accounting

`accounting/` owns the General Ledger and financial source of truth. Operational modules post accounting effects into the shared ledger, and financial statements are generated from that ledger rather than duplicated calculations.

Reports such as P&L, Balance Sheet, Cash Flow and Trial Balance use the General Ledger as their authoritative source.

## Major application modules

```text
catalog/             Product, category, brand, variants, media, specifications
inventory/           Warehouses, balances, movements, adjustments, transfers
serial_tracking/     Serial / IMEI / warranty lifecycle
purchasing/          Suppliers, purchases, purchase due
customers/           CRM/customer business records
sales/               Shared order engine and sales activity
storefront/          Public commerce experience and checkout
payments/            Payment records and payment workflows
shipping/            Shipment/courier workflows and tracking
returns/             Returns and refunds
accounting/          General Ledger and accounting workflows
expenses/            Expense management
reports/             Operational and financial reporting
promotions/          Coupons, flash sales, featured products, campaign tracking
staff_access/        Staff authentication, roles, permissions, throttling, audit
store_settings/      Branding, CMS, delivery rules, policies, SEO
customer_accounts/   Customer auth, account dashboard, wishlist, addresses
integrations/        Notifications, outbox, email/SMS/WhatsApp, Meta/GA4/courier
backoffice/           Dashboard presentation/workflows
ops/                  Production/security/operational utilities
techbari/             Project settings, URLs, ASGI/WSGI and shared configuration
```

## Storefront and dashboard

The storefront reads live catalog, pricing, promotion, account, checkout, shipping and order data from database-backed services.

Dashboard modules operate on the same source-of-truth data used by storefront/POS rather than maintaining a separate admin-only data set.

Representative dashboard areas include:

```text
/dashboard/products/
/dashboard/categories/
/dashboard/brands/
/dashboard/inventory/
/dashboard/warehouses/
/dashboard/purchases/
/dashboard/suppliers/
/dashboard/orders/
/dashboard/pos/
/dashboard/payments/
/dashboard/shipping/
/dashboard/returns/
/dashboard/accounts/
/dashboard/expenses/
/dashboard/reports/
/dashboard/customers/
/dashboard/users/
/dashboard/settings/
/dashboard/notifications/
```

## Images and media

Product media supports Primary, Gallery and Detail roles. Upload handling validates supported image formats and file-size limits. Production configuration also applies request/upload limits and hardened CMS logo/favicon/banner validation.

## Authentication and authorization

Staff access uses Django authentication/session infrastructure with application-specific controls layered on top.

Implemented roles include:

- Admin
- Manager
- Cashier
- Inventory Manager
- Accountant
- Sales Staff

Fine-grained permissions and database-backed audit logging are implemented. Staff and customer identities are kept behind explicit application boundaries even though both use Django authentication infrastructure.

Login throttling and security-state cleanup are database-backed and shared-hosting compatible.

## Integrations

`integrations/` provides a database-backed notification and outbound integration layer.

Implemented integration capabilities include:

- Email delivery
- Generic SMS webhook adapter
- Generic WhatsApp webhook adapter
- Meta Pixel
- Meta Conversions API Purchase queue with browser/server event deduplication
- GA4 browser tracking
- GA4 Measurement Protocol Purchase
- Generic courier booking adapter
- Signed courier status webhooks

Queued work is processed with:

```text
python manage.py process_integrations --limit 100
```

This design intentionally remains compatible with shared hosting and does not require Redis/Celery for the production baseline.

## Production and security architecture

Production settings are environment-driven and fail closed for unsafe production configuration.

When `DEBUG=False`, TechBari requires:

- a strong production `DJANGO_SECRET_KEY`
- explicit `DJANGO_ALLOWED_HOSTS`
- secure cookie / HTTPS settings appropriate to the deployment

Security hardening includes:

- HTTPS redirect support
- HSTS configuration
- secure session and CSRF cookies
- clickjacking protection
- content/referrer/cross-origin response headers
- explicit trusted-proxy handling
- request and upload limits
- login throttling
- outbound URL validation / private-network SSRF protection
- HMAC-signed courier webhooks
- timestamp validation and replay protection
- minimal database-backed `/health/` readiness endpoint

Before production deployment, run:

```text
python manage.py check --deploy --fail-level ERROR
python manage.py production_preflight
python manage.py collectstatic --noinput
```

See `PRODUCTION_DEPLOYMENT.md` for deployment, backup/restore, cron, static/media and rollback guidance.

## Database configuration

TechBari uses MySQL 8 through Django ORM.

`techbari/settings.py` loads connection details from environment variables:

```env
DB_NAME=techbari
DB_USER=root
DB_PASSWORD=...
DB_HOST=127.0.0.1
DB_PORT=3306
```

The MySQL connection uses `utf8mb4`, strict transaction mode and configurable connection persistence.

Apply migrations after pulling database changes:

```powershell
python manage.py migrate
python manage.py check
```

## Validation baseline

The v3.0.0 production baseline documented in `README.md` was validated with:

- production/security-focused suite: 78/78 PASS
- full project regression: 273/273 PASS
- Django system check: PASS
- migration drift: PASS / No changes detected
- clean MySQL migration application: PASS
- `collectstatic`: PASS
- Django production `check --deploy --fail-level ERROR`: PASS
- `production_preflight`: PASS

## Legacy notes

`scripts/validate_static.py` belongs to the original database-free conversion. It is not authoritative for the current v3.0.0 database-backed system.

For current validation use Django checks, migrations, the project test suites and `production_preflight`.
