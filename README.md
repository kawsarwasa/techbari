# TechBari — Django E-commerce + Admin

**Current version: v2.0.0**

TechBari is a MySQL 8-backed commerce platform being built phase-by-phase around one shared business architecture:

**One Product Database + One Inventory Engine + One Sales Engine + One Accounting Ledger.**

Catalog, Inventory, Serial / IMEI / Warranty, Supplier / Purchase, Customer / CRM, Sales Order, Storefront Checkout, POS, Payment, Shipping / Courier, Returns / Refunds and Accounting are now connected to the real business data flow.

## v2.0.0 — Accounting System / General Ledger

TechBari now has a real double-entry Accounting Ledger. Sales, Payments, Purchase Receipts, Supplier Payments, Purchase Returns, completed Sales Returns and Courier COD deductions generate balanced, idempotent journals without replacing the operational source modules.

The Accounting domain includes:

- Chart of Accounts
- system and custom ledger accounts
- immutable Posted journals
- debit/credit Journal Lines
- unique source-key protection against duplicate automatic posting
- journal reversal instead of financial-history editing
- Open / Closed Accounting Periods
- General Ledger
- Trial Balance
- Accounting overview and ledger health
- immutable Accounting audit events
- migration/backfill of existing v1.x business history

Automatic posting covers Accounts Receivable, Accounts Payable, Cash/Bank/Card/bKash/Nagad clearing, Product Sales, Shipping Revenue, Inventory Asset, COGS, Sales Returns and Courier/Collection Fees.

SKU cost is derived from Purchase receipt history. Legacy/opening inventory without a reliable purchase-cost basis is not assigned fabricated COGS from selling price; opening Inventory/Equity can instead be established through a controlled manual journal.

See `ACCOUNTING_SYSTEM_PHASE.md` for the full posting map, Chart of Accounts, migration behavior and safety rules.

## v1.10.0 — Returns / Refunds

Completed Sales Orders support Requested → Approved → Received → Completed return lifecycle, original Order Item/SKU linkage, partial/full return protection, exact Serial/IMEI handling, stock disposition, return credit and Payment-ledger refunds.

See `RETURNS_REFUNDS_PHASE.md`.

## v1.9.0 — Shipping / Courier

Database-backed shipment lifecycle, courier providers, tracking history, courier handover, delivery/return states and COD collection/settlement are integrated with Sales, Inventory and Payments.

See `SHIPPING_COURIER_PHASE.md`.

## v1.8.0 — Payment System

Central Money In / Money Out transaction ledger for Sales, POS and Supplier payments with partial/multiple payments, refunds, reversals, reconciliation and immutable audit history.

See `PAYMENT_SYSTEM_PHASE.md`.

## v1.7.0 — POS

Warehouse-aware counter sale with Product/SKU/barcode search, hold/resume, CRM/walk-in customer, multiple tender methods and printable receipt. POS reuses the shared Sales + Inventory engines.

See `POS_SYSTEM_PHASE.md`.

## v1.6.0 — Storefront Checkout Backend

The public checkout creates real Online Sales Orders with CRM find/create, server-authoritative price/stock/shipping/coupon calculation, Inventory reservation and idempotent confirmation.

See `CHECKOUT_BACKEND_PHASE.md`.

## v1.5.0 — Customer CRM + Sales Order Engine

Customer profiles, groups/source/history metrics and the shared Sales Order lifecycle with Inventory reservation/deduction.

See `CRM_SALES_PHASE.md`.

## v1.3.0 — Supplier + Purchase

Supplier CRUD, Purchase Orders, partial/full goods receiving, Inventory `PURCHASE_IN`, optional Serial/IMEI receiving, Supplier payments and Purchase Returns.

See `SUPPLIER_PURCHASE_PHASE.md`.

## v1.2.0 — Serial / IMEI / Warranty

Unit-level Serial/IMEI lifecycle, Warehouse + SKU linkage and Warranty/RMA tracking.

See `SERIAL_IMEI_WARRANTY_PHASE.md`.

## v1.1.0 — Inventory

Warehouse/SKU balances, immutable Stock Movement ledger, adjustments, transfers, reservations, low-stock reporting and negative-stock protection.

See `INVENTORY_PHASE1.md`.

## v1.0.10 — Catalog

Categories, Brands, Products, Variants/SKUs/Barcodes, media, specifications, rich descriptions, pricing, SEO and Storefront catalog behavior.

See `CATALOG_DATABASE_PHASE.md`.

## Current database-backed modules

### Catalog

Categories, Brands, Products, Variants / SKUs / Barcodes, variant pricing, media, specifications, rich descriptions, SEO and Storefront catalog integration.

### Inventory

Warehouses, warehouse/SKU balances, on-hand/reserved/available stock, Stock Movement ledger, adjustments, transfers, reservations, low-stock reporting and negative-stock protection.

### Serial / IMEI / Warranty

Unit-level lifecycle, Warehouse + SKU linkage, immutable unit events and Warranty/RMA claims.

### Supplier + Purchase

Suppliers, Purchase Orders, receiving, Inventory `PURCHASE_IN`, Serial/IMEI receiving, Supplier Payments and Purchase Returns.

### Customer / CRM

Customer CRUD, groups, source/address, credit/opening due, purchase history, total spent, due balance and repeat-customer tracking.

### Sales Order

Online / Manual / POS channels, real SKU lines, Draft/Pending/Confirmed/Processing/Completed/Cancelled lifecycle, Inventory reservation/deduction, customer linkage and return-credit-aware payable balance.

### Storefront Checkout

Real GET/POST checkout, server-authoritative pricing/stock/coupon/shipping, CRM find/create, Inventory reservation and signed idempotency/confirmation.

### POS

Real warehouse-aware SKU/barcode search, walk-in/CRM customers, hold/resume, discounts, Cash/Card/bKash/Nagad tender snapshots, Inventory issue and printable receipt.

Routes: `/dashboard/pos/`, `/dashboard/pos/action/`, `/dashboard/pos/held/<id>/`, `/dashboard/pos/receipt/<id>/`.

### Payment

Central Payment transaction ledger, partial/multiple Sale payments, Supplier payment mirrors, refunds/reversals, reconciliation, Payment-method configuration and immutable audit history.

Routes: `/dashboard/payments/`, `/dashboard/payments/add/`, `/dashboard/payments/methods/`, `/dashboard/payments/<id>/`.

### Shipping / Courier

Courier providers, Shipment lifecycle, tracking timeline, courier handover, COD collection/settlement and Payment-ledger settlement integration.

Routes: `/dashboard/shipping/`, `/dashboard/shipping/add/`, `/dashboard/shipping/providers/`, `/dashboard/shipping/<id>/`, `/dashboard/shipping/cod-settlements/`.

### Returns / Refunds

Completed-sale returns, partial/full return protection, stock disposition, exact Serial/IMEI lifecycle, Order return credit and Payment-ledger refund allocation.

Routes: `/dashboard/returns/`, `/dashboard/returns/add/`, `/dashboard/returns/<id>/`.

### Accounting

- Double-entry Chart of Accounts
- balanced immutable Journal Entries
- automatic business-event journals
- Accounts Receivable / Accounts Payable
- Cash/Bank/Card/bKash/Nagad clearing accounts
- Inventory Asset and COGS
- Product and Shipping Revenue
- Sales Returns contra-revenue
- Courier/collection expense
- controlled manual journals
- journal reversals
- Open / Closed Accounting Periods
- General Ledger
- Trial Balance
- Accounting audit trail

Routes:

- `/dashboard/accounts/`
- `/dashboard/accounts/chart/`
- `/dashboard/accounts/chart/add/`
- `/dashboard/accounts/journals/`
- `/dashboard/accounts/journals/add/`
- `/dashboard/accounts/journals/<id>/`
- `/dashboard/accounts/ledger/`
- `/dashboard/accounts/trial-balance/`
- `/dashboard/accounts/periods/`

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

Apply migrations and verify:

```powershell
python manage.py migrate
python manage.py check
python manage.py test catalog inventory serial_tracking purchasing customers sales payments shipping returns accounting storefront
python manage.py runserver
```

Upgrading from v1.10.0 to v2.0.0 applies:

```text
accounting.0001_initial
accounting.0002_backfill_existing_business_history
```

The first migration creates and seeds the Accounting Ledger. The second translates existing v1.x business history into idempotent balanced journals. Existing operational data is preserved. No catalog seed command is required.

## Roadmap direction

Accounting is now the financial source of truth for later finance/reporting work.

Next planned phases:

- **v2.1.x — Expense Management**
- **v2.2.x — Reports**
- **v2.3.x — Marketing**
- **v2.4.x — Analytics**
- **v2.5.x — Users / Roles / Permissions**
- **v2.6.x — CMS / Settings**
- **v2.7.x — Customer Account**
- **v2.8.x — Notifications / Integrations**
- **v3.0 — Production QA / Release**
