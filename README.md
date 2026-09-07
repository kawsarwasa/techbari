# TechBari — Django E-commerce + Admin

**Current version: v2.1.0**

TechBari is a MySQL 8-backed commerce platform being built phase-by-phase around one shared business architecture:

**One Product Database + One Inventory Engine + One Sales Engine + One Accounting Ledger.**

Catalog, Inventory, Serial / IMEI / Warranty, Supplier / Purchase, Customer / CRM, Sales Order, Storefront Checkout, POS, Payment, Shipping / Courier, Returns / Refunds, Accounting and Expense Management are now connected to the real business data flow.

## v2.1.0 — Expense Management System

Business expenses are now real database records with category/GL mapping, payee/vendor, date, amount, receipt/invoice number, preferred and actual payment method, notes and an auditable Draft → Pending Approval → Approved → Paid lifecycle.

Expense categories map directly to Expense-type Chart of Accounts accounts. The migration seeds dedicated operating-expense accounts and categories for Rent, Utilities, Marketing, Office Supplies, Internet/Communication, Transport/Travel, Repairs, Bank/MFS Charges, Professional Services, Staff Welfare and Other Expense.

When an Approved expense is paid, TechBari posts a balanced Accounting journal atomically:

- Debit the mapped Expense account
- Credit Cash / Bank / Card / bKash / Nagad / Other Funds

Closed Accounting periods block payment without leaving a partial Paid state. Paid expenses are not edited or deleted; a correction uses a reversing journal and marks the Expense Voided while preserving original history.

Expense Management includes immutable workflow events, approval/rejection/cancellation, paid-expense void/reversal, category management, search/filtering and operational KPIs.

See `EXPENSE_MANAGEMENT_PHASE.md` for the workflow, GL mapping, safety rules and routes.

## v2.0.0 — Accounting System / General Ledger

TechBari has a real double-entry Accounting Ledger. Sales, Payments, Purchase Receipts, Supplier Payments, Purchase Returns, completed Sales Returns, Courier COD deductions and now paid business Expenses generate balanced, idempotent journals without replacing the operational source modules.

The Accounting domain includes Chart of Accounts, immutable Posted journals, debit/credit Journal Lines, source-key duplicate protection, journal reversal, Open/Closed Accounting Periods, General Ledger, Trial Balance, Accounting overview and migration/backfill of v1.x business history.

See `ACCOUNTING_SYSTEM_PHASE.md`.

## Earlier completed phases

- **v1.10.0 — Returns / Refunds** — controlled sales returns, inventory disposition, Serial/IMEI handling and Payment-ledger refunds. See `RETURNS_REFUNDS_PHASE.md`.
- **v1.9.0 — Shipping / Courier** — shipment lifecycle, courier providers, tracking and COD settlement. See `SHIPPING_COURIER_PHASE.md`.
- **v1.8.0 — Payment System** — Sale/Supplier payment transaction ledger, partial/multiple payments, refunds, reversals and reconciliation. See `PAYMENT_SYSTEM_PHASE.md`.
- **v1.7.0 — POS** — warehouse-aware counter sales, hold/resume and printable receipt. See `POS_SYSTEM_PHASE.md`.
- **v1.6.0 — Storefront Checkout Backend** — real Online Sales Orders, CRM linkage, server-authoritative totals and stock reservation. See `CHECKOUT_BACKEND_PHASE.md`.
- **v1.5.0 — Customer CRM + Sales Order Engine** — CRM and shared Sales lifecycle. See `CRM_SALES_PHASE.md`.
- **v1.3.0 — Supplier + Purchase** — Supplier, Purchase Order, receiving, payments and Purchase Returns. See `SUPPLIER_PURCHASE_PHASE.md`.
- **v1.2.0 — Serial / IMEI / Warranty** — unit-level tracking and Warranty/RMA. See `SERIAL_IMEI_WARRANTY_PHASE.md`.
- **v1.1.0 — Inventory** — warehouse/SKU ledger, adjustments, transfers and reservations. See `INVENTORY_PHASE1.md`.
- **v1.0.10 — Catalog** — Categories, Brands, Products, Variants/SKUs/Barcodes, media, specifications and Storefront catalog. See `CATALOG_DATABASE_PHASE.md`.

## Current database-backed modules

### Catalog
Categories, Brands, Products, Variants / SKUs / Barcodes, pricing, media, specifications, rich descriptions, SEO and Storefront catalog integration.

### Inventory
Warehouses, warehouse/SKU balances, on-hand/reserved/available stock, immutable Stock Movement ledger, adjustments, transfers and low-stock reporting.

### Serial / IMEI / Warranty
Unit-level lifecycle, Warehouse + SKU linkage, immutable unit events and Warranty/RMA claims.

### Supplier + Purchase
Suppliers, Purchase Orders, receiving, Inventory `PURCHASE_IN`, Serial/IMEI receiving, Supplier Payments and Purchase Returns.

### Customer / CRM
Customer CRUD, groups, source/address, credit/opening due, purchase history, total spent, due balance and repeat-customer tracking.

### Sales Order
Online / Manual / POS channels, real SKU lines, lifecycle/status history, Inventory reservation/deduction, customer linkage and return-credit-aware payable balance.

### Storefront Checkout
Real GET/POST checkout, server-authoritative pricing/stock/coupon/shipping, CRM find/create, Inventory reservation and signed idempotency/confirmation.

### POS
Warehouse-aware SKU/barcode search, walk-in/CRM customers, hold/resume, discounts, Cash/Card/bKash/Nagad tender snapshots, Inventory issue and printable receipt.

### Payment
Central Sale/Supplier payment transaction ledger, partial/multiple payments, refunds/reversals, reconciliation and Payment-method configuration.

### Shipping / Courier
Courier providers, Shipment lifecycle, tracking timeline, courier handover and COD collection/settlement.

### Returns / Refunds
Completed-sale returns, partial/full protection, stock disposition, exact Serial/IMEI lifecycle, Order return credit and Payment-ledger refund allocation.

### Accounting
- Double-entry Chart of Accounts
- balanced immutable Journal Entries
- automatic business-event journals
- Accounts Receivable / Accounts Payable
- Cash/Bank/Card/bKash/Nagad clearing
- Inventory Asset and COGS
- Sales / Shipping Revenue
- Sales Returns contra-revenue
- operating Expense accounts
- controlled manual journals and reversals
- Open / Closed Accounting Periods
- General Ledger and Trial Balance

Routes: `/dashboard/accounts/`, `/dashboard/accounts/chart/`, `/dashboard/accounts/journals/`, `/dashboard/accounts/ledger/`, `/dashboard/accounts/trial-balance/`, `/dashboard/accounts/periods/`.

### Expense Management
- Expense Category → GL Expense account mapping
- seeded operating expense categories/accounts
- Draft / Pending / Approved / Paid / Rejected / Cancelled / Voided lifecycle
- payee/vendor, receipt/invoice, notes and payment reference
- approval and payment audit snapshots
- immutable Expense events
- Cash / Bank / Card / bKash / Nagad / Other payment
- atomic Accounting posting on payment
- closed-period protection
- paid-expense reversal/void flow
- search/filtering and expense KPIs

Routes: `/dashboard/expenses/`, `/dashboard/expenses/add/`, `/dashboard/expenses/categories/`, `/dashboard/expenses/<id>/`, `/dashboard/expenses/<id>/pay/`.

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
python manage.py test catalog inventory serial_tracking purchasing customers sales payments shipping returns accounting expenses storefront
python manage.py runserver
```

Upgrading from v2.0.0 to v2.1.0 applies:

```text
accounting.0003_expense_source
expenses.0001_initial
```

Existing operational and Accounting data are preserved. No catalog seed command is required.

## Roadmap direction

Accounting + Expense Management are now the financial source of truth for the reporting phase.

Next planned phases:

- **v2.2.x — Reports**
- **v2.3.x — Marketing**
- **v2.4.x — Analytics**
- **v2.5.x — Users / Roles / Permissions**
- **v2.6.x — CMS / Settings**
- **v2.7.x — Customer Account**
- **v2.8.x — Notifications / Integrations**
- **v3.0 — Production QA / Release**
