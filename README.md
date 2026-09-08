# TechBari — Django E-commerce + Admin

**Current version: v2.2.2**

TechBari is a MySQL 8-backed commerce platform built around one shared business architecture:

**One Product Database + One Inventory Engine + One Sales Engine + One Accounting Ledger.**

Catalog, Inventory, Serial / IMEI / Warranty, Supplier / Purchase, Customer / CRM, Sales Order, Storefront Checkout, POS, Payment, Shipping / Courier, Returns / Refunds, Accounting, Expense Management and Reports are connected to the real business data flow.

## v2.2.2 — Payment + Expense + Returns + Warranty + Serial/IMEI Reports

The Reports dashboard now includes the third Reports v2.2.x release:

- Payment Report
- Expense Report
- Returns Report
- Warranty Report
- Serial / IMEI Report

Payment reporting reads the central `PaymentTransaction` ledger and supports Kind, Method and Status filters. Completed Money In / Money Out and Net Cash Flow KPIs are calculated from completed payment-ledger transactions.

Expense reporting reads the real Expense workflow and supports Status, Category and Payment Method filters. It shows exact payment Asset account, payment date/reference, Active Amount, Paid Amount, Pending Approval and Approved/Unpaid KPIs.

Returns reporting reads Sales Return cases, items and refund links and shows returned/restocked units, credit, actual cash refund and completion outcome. Warranty reporting reads WarrantyClaim records with claim status, warranty coverage and replacement data. Serial/IMEI reporting reads the serialized-unit registry with current Warehouse/Status, identifiers, purchase/sales references and warranty dates.

All reports reuse the shared responsive Reports UI, KPI cards and UTF-8 CSV export.

Route: `/dashboard/reports/`

See `REPORTS_PHASE.md` for calculation rules, date semantics, filters and the remaining Reports roadmap.

## v2.2.1 — Stock + Purchase Reports

- Stock Report
- Stock Valuation
- Low Stock
- Stock Movement
- Purchase Report
- Supplier Due
- Customer Due

Stock/valuation/low-stock reporting uses immutable Stock Movement snapshots for historical As-of quantities, with weighted purchase cost for operational valuation. Supplier Due and Customer Due are date-aware historical reports.

## v2.2.0 — Sales + Profit Reports

- Sales Report
- Daily / Monthly Sales
- POS vs Online / Manual Sales
- Product / Category / Brand Sales
- Profit Report
- COGS Report

Completed Sales Orders are the operational source. Posted GL COGS is the primary cost source; completed return credits and COGS reversals reduce Net Sales / Net COGS.

## Completed business phases

- **v2.1.1 — Expense Management** — category → GL mapping, approval/payment lifecycle, attachment, exact payment account, automatic Accounting posting. See `EXPENSE_MANAGEMENT_PHASE.md`.
- **v2.0.0 — Accounting / General Ledger** — double-entry Chart of Accounts, automatic journals, periods, ledger and Trial Balance. See `ACCOUNTING_SYSTEM_PHASE.md`.
- **v1.10.0 — Returns / Refunds** — controlled customer returns, stock disposition, Serial/IMEI handling and refunds. See `RETURNS_REFUNDS_PHASE.md`.
- **v1.9.0 — Shipping / Courier** — shipment lifecycle, courier tracking and COD settlement. See `SHIPPING_COURIER_PHASE.md`.
- **v1.8.0 — Payment System** — central Sale/Supplier payment ledger, refunds, reversals and reconciliation. See `PAYMENT_SYSTEM_PHASE.md`.
- **v1.7.0 — POS** — warehouse-aware counter sales, hold/resume and receipt. See `POS_SYSTEM_PHASE.md`.
- **v1.6.0 — Storefront Checkout Backend** — real online Sales Orders, CRM linkage and stock reservation. See `CHECKOUT_BACKEND_PHASE.md`.
- **v1.5.0 — Customer CRM + Sales Order Engine** — shared CRM and Sales lifecycle. See `CRM_SALES_PHASE.md`.
- **v1.3.0 — Supplier + Purchase** — Supplier, Purchase Order, receiving, payments and Purchase Returns. See `SUPPLIER_PURCHASE_PHASE.md`.
- **v1.2.0 — Serial / IMEI / Warranty** — unit-level tracking and Warranty/RMA claims. See `SERIAL_IMEI_WARRANTY_PHASE.md`.
- **v1.1.0 — Inventory** — warehouse/SKU ledger, reservations, adjustments and transfers. See `INVENTORY_PHASE1.md`.
- **v1.0.10 — Catalog** — Categories, Brands, Products, Variants/SKUs/Barcodes, media and specifications. See `CATALOG_DATABASE_PHASE.md`.

## Current database-backed modules

### Catalog
Categories, Brands, Products, Variants / SKUs / Barcodes, pricing, media, specifications, rich descriptions, SEO and Storefront catalog integration.

### Inventory
Warehouses, warehouse/SKU balances, on-hand/reserved/available stock, immutable Stock Movement ledger, adjustments, transfers and low-stock thresholds.

### Serial / IMEI / Warranty
Serialized-unit lifecycle, Warehouse + SKU linkage, immutable unit events and Warranty/RMA claims.

### Supplier + Purchase
Suppliers, Purchase Orders, receiving, Inventory `PURCHASE_IN`, Serial/IMEI receiving, Supplier Payments and Purchase Returns.

### Customer / CRM
Customer CRUD, groups, source/address, credit/opening due, purchase history, total spent, due balance and repeat-customer tracking.

### Sales Order
Online / Manual / POS channels, SKU lines, lifecycle/status history, Inventory reservation/deduction, customer linkage and return-credit-aware payable balance.

### Storefront Checkout
Real GET/POST checkout, server-authoritative pricing/stock/shipping, CRM find/create, Inventory reservation and signed idempotency/confirmation.

### POS
Warehouse-aware SKU/barcode search, walk-in/CRM customers, hold/resume, discounts, Cash/Card/bKash/Nagad tender snapshots, Inventory issue and printable receipt.

### Payment
Central Sale/Supplier `PaymentTransaction` ledger, partial/multiple payments, refunds/reversals, reconciliation and payment-method configuration.

### Shipping / Courier
Courier providers, Shipment lifecycle, tracking timeline, courier handover and COD collection/settlement.

### Returns / Refunds
Completed-sale returns, partial/full protection, stock disposition, exact Serial/IMEI lifecycle, order return credit and Payment-ledger refund allocation.

### Accounting
Double-entry Chart of Accounts, balanced immutable journals, automatic business-event posting, AR/AP, Cash/Bank/Card/MFS clearing, Inventory/COGS, Revenue/Expense, periods, General Ledger and Trial Balance.

Routes: `/dashboard/accounts/`, `/dashboard/accounts/chart/`, `/dashboard/accounts/journals/`, `/dashboard/accounts/ledger/`, `/dashboard/accounts/trial-balance/`, `/dashboard/accounts/periods/`.

### Expense Management
Expense Category → GL mapping, Draft/Pending/Approved/Paid/Rejected/Cancelled/Voided lifecycle, payee/vendor, attachment, exact payment Asset account, audit events, automatic Accounting posting and reversal/void flow.

Routes: `/dashboard/expenses/`, `/dashboard/expenses/add/`, `/dashboard/expenses/categories/`.

### Reports v2.2.2

- Sales / Daily / Monthly / Channel reports
- Product / Category / Brand Sales
- Profit / COGS
- Stock / Valuation / Low Stock / Stock Movement
- Purchase / Supplier Due / Customer Due
- Payment / Expense / Returns
- Warranty / Serial / IMEI
- report-appropriate Date, Channel, Warehouse, lifecycle and transaction filters
- KPI summary cards
- UTF-8 CSV export

Route: `/dashboard/reports/`.

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
python manage.py test catalog inventory serial_tracking purchasing customers sales payments shipping returns accounting expenses reports storefront
python manage.py runserver
```

v2.2.2 adds no database migration. Existing business and Reports data are preserved.

## Roadmap direction

Next planned phases:

- **v2.2.3 — P&L + Balance Sheet + Cash Flow + Trial Balance**
- **v2.3.x — Marketing**
- **v2.4.x — Analytics**
- **v2.5.x — Users / Roles / Permissions**
- **v2.6.x — CMS / Settings**
- **v2.7.x — Customer Account**
- **v2.8.x — Notifications / Integrations**
- **v3.0 — Production QA / Release**
