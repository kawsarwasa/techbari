# TechBari — Django E-commerce + Admin

**Current version: v2.2.1**

TechBari is a MySQL 8-backed commerce platform being built phase-by-phase around one shared business architecture:

**One Product Database + One Inventory Engine + One Sales Engine + One Accounting Ledger.**

Catalog, Inventory, Serial / IMEI / Warranty, Supplier / Purchase, Customer / CRM, Sales Order, Storefront Checkout, POS, Payment, Shipping / Courier, Returns / Refunds, Accounting, Expense Management and Reports are connected to the real business data flow.

## v2.2.1 — Stock + Purchase Reports

The Reports dashboard now adds seven operational reports on top of v2.2.0 Sales + Profit reporting:

- Stock Report
- Stock Valuation
- Low Stock
- Stock Movement
- Purchase Report
- Supplier Due
- Customer Due

Stock, valuation and low-stock reports support an **As of** date and Warehouse filtering. Historical stock is reconstructed from the immutable Stock Movement ledger using quantity/reservation snapshots. Stock valuation uses weighted purchase cost as of the selected date.

Stock Movement supports From/To date, Warehouse and Movement Type filters. Purchase reporting is date-aware and includes receiving, returns, supplier payments and outstanding amounts.

Supplier Due and Customer Due are historical **As of** reports. Supplier Due combines opening payable, purchases, purchase returns and supplier payments. Customer Due combines opening due, customer orders, completed return credits and the central PaymentTransaction ledger.

All v2.2.1 reports support KPI summary cards, responsive tables and UTF-8 CSV export. No new database migration is required.

Route: `/dashboard/reports/`

See `REPORTS_PHASE.md` for calculation rules, historical-data behavior, filters, limitations and the remaining Reports roadmap.

## v2.2.0 — Sales + Profit Reports

The Reports dashboard provides real database-backed Sales and Profit reporting:

- Sales Report
- Daily Sales
- Monthly Sales
- POS vs Online / Manual Sales
- Product Sales
- Category Sales
- Brand Sales
- Profit Report
- COGS Report

Reports support From/To date filtering, sales-channel filtering, KPI cards and UTF-8 CSV export. Only Completed Sales Orders are counted.

Order-level COGS uses posted General Ledger COGS entries as the primary source of truth. Completed sales-return COGS reversals reduce net COGS, while return credits reduce net sales. Gross Profit is calculated as Net Sales minus Net COGS.

Product, Category and Brand reports focus on product revenue and therefore exclude shipping revenue. Order-level discounts and return credits are allocated to product rows, and exact order COGS is allocated across the sold items. Category and Brand grouping use the product's current Catalog classification because those values are not currently snapshotted on Sales Order items.

## v2.1.1 — Expense Management System

Business expenses are real database records with category/GL mapping, payee/vendor, date, amount, receipt/invoice number, attachment, preferred and actual payment method, exact payment account, notes and an auditable Draft → Pending Approval → Approved → Paid lifecycle.

Expense categories map directly to Expense-type Chart of Accounts accounts. The Expense roadmap includes Rent, Utilities, Marketing, Office Supplies, Internet/Communication, Transport/Travel, Repairs, Bank/MFS Charges, Professional Services, Staff Welfare, Salary & Wages, Courier Expense and Other Expense.

When an Approved expense is paid, TechBari posts a balanced Accounting journal atomically:

- Debit the mapped Expense account
- Credit the exact selected Cash / Bank / Card / bKash / Nagad / Other Asset account

Attachments support PDF/JPG/JPEG/PNG/WebP up to 5 MB. Closed Accounting periods block payment without leaving a partial Paid state. Paid expenses are corrected through reversal/void instead of destructive editing.

See `EXPENSE_MANAGEMENT_PHASE.md` for the workflow, GL mapping, safety rules and routes.

## v2.0.0 — Accounting System / General Ledger

TechBari has a real double-entry Accounting Ledger. Sales, Payments, Purchase Receipts, Supplier Payments, Purchase Returns, completed Sales Returns, Courier COD deductions and paid business Expenses generate balanced, idempotent journals without replacing the operational source modules.

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
- **v1.2.0 — Serial / IMEI / Warranty** — unit-level tracking and Warranty/RMA claims. See `SERIAL_IMEI_WARRANTY_PHASE.md`.
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
- seeded operating expense categories including Salary and Courier
- Draft / Pending / Approved / Paid / Rejected / Cancelled / Voided lifecycle
- payee/vendor, receipt/invoice, notes and attachment
- explicit payment Asset account selection
- approval and payment audit snapshots
- immutable Expense events
- atomic Accounting posting on payment
- closed-period protection
- paid-expense reversal/void flow
- search/filtering and expense KPIs

Routes: `/dashboard/expenses/`, `/dashboard/expenses/add/`, `/dashboard/expenses/categories/`, `/dashboard/expenses/<id>/`, `/dashboard/expenses/<id>/pay/`.

### Reports v2.2.1
- Sales / Daily / Monthly Sales
- POS vs Online / Manual Sales
- Product / Category / Brand Sales
- return-aware COGS and Gross Profit
- Stock / Stock Valuation / Low Stock
- Stock Movement
- Purchase Report
- Supplier Due / Customer Due
- report-appropriate Date, Channel, Warehouse and Movement Type filters
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

v2.2.1 adds no database migration. Existing operational, Accounting, Expense and Reports data are preserved.

## Roadmap direction

Reports v2.2.x is being released in controlled sub-phases so operational reports can be reconciled to the Accounting ledger.

Next planned phases:

- **v2.2.2 — Payment + Expense + Returns + Warranty + Serial/IMEI Reports**
- **v2.2.3 — P&L + Balance Sheet + Cash Flow + Trial Balance**
- **v2.3.x — Marketing**
- **v2.4.x — Analytics**
- **v2.5.x — Users / Roles / Permissions**
- **v2.6.x — CMS / Settings**
- **v2.7.x — Customer Account**
- **v2.8.x — Notifications / Integrations**
- **v3.0 — Production QA / Release**
