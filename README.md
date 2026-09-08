# TechBari — Django E-commerce + Admin

**Current version: v2.3.0**

TechBari is a MySQL 8-backed commerce platform built around one shared business architecture:

**One Product Database + One Inventory Engine + One Sales Engine + One Accounting Ledger.**

Catalog, Inventory, Serial / IMEI / Warranty, Supplier / Purchase, Customer / CRM, Sales Order, Storefront Checkout, POS, Payment, Shipping / Courier, Returns / Refunds, Accounting, Expense Management, Reports and Promotion / Marketing are connected to the real business data flow.

## v2.3.0 — Promotion / Marketing

Promotion / Marketing is now database-backed and integrated with the real Storefront Checkout and Sales Order flow.

Included:

- Coupon backend
- Fixed and percentage discounts
- Minimum order amount
- Start/end date range
- Usage limit and one-redemption-per-order tracking
- Product-specific and Category-specific offers
- Flash Sales
- Featured Products
- Campaign visit/conversion tracking

Checkout remains server-authoritative: Catalog prices and all coupon/Flash Sale rules are reloaded and recalculated on the server. Coupon usage is validated inside the checkout transaction, and the selected Coupon row can be locked before redemption to protect the final usage slot from concurrent checkouts.

Flash Sales choose the best valid price against the existing Catalog current/sale price rather than compounding multiple sale discounts. One coupon can then apply to its eligible subtotal.

Campaign links accept `campaign` or `utm_campaign` plus optional `utm_source` / `utm_medium`; valid landings are stored as campaign events with signed cookie attribution and successful orders create conversion events.

Dashboard routes:

- `/dashboard/marketing/`
- `/dashboard/coupons/`
- `/dashboard/coupons/add/`

See `PROMOTION_MARKETING_PHASE.md` for pricing rules, data model, tracking semantics, concurrency behavior and validation details.

## Reports v2.2.x — completed

### v2.2.0 — Sales + Profit
- Sales / Daily / Monthly Sales
- POS vs Online / Manual Sales
- Product / Category / Brand Sales
- Profit Report
- COGS Report

### v2.2.1 — Stock + Purchase
- Stock
- Stock Valuation
- Low Stock
- Stock Movement
- Purchase
- Supplier Due
- Customer Due

### v2.2.2 — Operational Finance + After-sales
- Payment
- Expense
- Returns
- Warranty
- Serial / IMEI

### v2.2.3 — Financial Statements
- Profit & Loss
- Balance Sheet
- Cash Flow
- Trial Balance

Reports use report-appropriate Date/As-of, Channel, Warehouse, lifecycle and transaction filters, KPI cards, responsive tables and UTF-8 CSV export. Financial statements use the Accounting General Ledger as their source of truth.

## Completed business phases

- **v2.3.0 — Promotion / Marketing** — database-backed Coupons, Flash Sales, Featured Products and Campaign tracking. See `PROMOTION_MARKETING_PHASE.md`.
- **v2.2.x — Reports** — operational reports plus GL-backed P&L, Balance Sheet, Cash Flow and Trial Balance. See `REPORTS_PHASE.md`.
- **v2.1.1 — Expense Management** — category → GL mapping, approval/payment lifecycle, attachment, exact payment account and automatic Accounting posting. See `EXPENSE_MANAGEMENT_PHASE.md`.
- **v2.0.0 — Accounting / General Ledger** — double-entry Chart of Accounts, automatic journals, periods, General Ledger and Trial Balance. See `ACCOUNTING_SYSTEM_PHASE.md`.
- **v1.10.0 — Returns / Refunds** — controlled customer returns, stock disposition, Serial/IMEI handling and refunds. See `RETURNS_REFUNDS_PHASE.md`.
- **v1.9.0 — Shipping / Courier** — shipment lifecycle, courier tracking and COD settlement. See `SHIPPING_COURIER_PHASE.md`.
- **v1.8.0 — Payment System** — central Sale/Supplier payment ledger with refunds, reversals and reconciliation. See `PAYMENT_SYSTEM_PHASE.md`.
- **v1.7.0 — POS** — warehouse-aware counter sales, hold/resume and receipt. See `POS_SYSTEM_PHASE.md`.
- **v1.6.0 — Storefront Checkout Backend** — real online Sales Orders, CRM linkage and stock reservation. See `CHECKOUT_BACKEND_PHASE.md`.
- **v1.5.0 — Customer CRM + Sales Order Engine** — shared CRM and Sales lifecycle. See `CRM_SALES_PHASE.md`.
- **v1.3.0 — Supplier + Purchase** — Purchase Orders, receiving, supplier payments and Purchase Returns. See `SUPPLIER_PURCHASE_PHASE.md`.
- **v1.2.0 — Serial / IMEI / Warranty** — unit-level tracking and Warranty/RMA claims. See `SERIAL_IMEI_WARRANTY_PHASE.md`.
- **v1.1.0 — Inventory** — warehouse/SKU ledger, reservations, adjustments and transfers. See `INVENTORY_PHASE1.md`.
- **v1.0.10 — Catalog** — Categories, Brands, Products, Variants/SKUs/Barcodes, media and specifications. See `CATALOG_DATABASE_PHASE.md`.

## Main database-backed modules

- **Catalog** — Categories, Brands, Products, Variants/SKUs/Barcodes, pricing, media, specifications and storefront catalog.
- **Inventory** — Warehouses, on-hand/reserved/available stock, immutable Stock Movement ledger, adjustments and transfers.
- **Serial / IMEI / Warranty** — serialized-unit lifecycle, Warehouse/SKU linkage, immutable events and warranty claims.
- **Supplier + Purchase** — Purchase Orders, receiving, supplier payments and Purchase Returns.
- **Customer / CRM** — Customer groups, addresses, opening due, purchase history and due tracking.
- **Sales Order** — Online / Manual / POS channels, inventory reservation/deduction and return-credit-aware balance.
- **Storefront Checkout** — server-authoritative checkout, CRM linkage, stock reservation, promotions and idempotency.
- **POS** — warehouse-aware counter sale, hold/resume, payment tender and printable receipt.
- **Payment** — central payment transaction ledger with partial payments, refunds, reversals and reconciliation.
- **Shipping / Courier** — courier providers, shipment lifecycle, tracking and COD settlement.
- **Returns / Refunds** — controlled returns, inventory disposition and refund allocation.
- **Accounting** — double-entry Chart of Accounts, immutable journals, AR/AP, cash/payment assets, Inventory/COGS, Revenue/Expense, periods, ledger and Trial Balance.
- **Expense Management** — expense categories, approval/payment workflow, attachment, exact payment account and GL posting.
- **Reports** — operational reports plus General Ledger financial statements.
- **Promotion / Marketing** — Coupons, redemptions, Flash Sales, Featured Products and Campaign attribution.

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
python manage.py test catalog inventory serial_tracking purchasing customers sales payments shipping returns accounting expenses reports promotions storefront
python manage.py runserver
```

v2.3.0 adds the initial Promotion / Marketing database migration. Existing Catalog, Sales, Accounting and Reports data are preserved.

## Validation

v2.3.0 is validated on GitHub Actions using MySQL 8 and Python 3.12 with:

- dedicated Promotion / Marketing tests
- full project regression suite
- Django system check
- migration drift check
- migration application

## Roadmap direction

Next planned phases:

- **v2.4.x — Dashboard Analytics**
- **v2.5.x — Users / Roles / Permissions**
- **v2.6.x — CMS / Store Settings**
- **v2.7.x — Real Customer Account**
- **v2.8.x — Notifications + Integrations**
- **v3.0 — Final Production Phase**
