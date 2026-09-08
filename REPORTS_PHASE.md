# Reports Phase — v2.2.x

TechBari Reports is being implemented in controlled sub-releases so operational reports remain reconcilable with the Accounting General Ledger.

Route: `/dashboard/reports/`

## v2.2.0 — Sales + Profit Reports

Implemented reports:

- Sales Report
- Daily Sales
- Monthly Sales
- POS vs Online / Manual Sales
- Product Sales
- Category Sales
- Brand Sales
- Profit Report
- COGS Report

Sales reports support From/To date filtering, sales-channel filtering, KPI summary cards, responsive tables and UTF-8 CSV export.

Only `SalesOrder.Status.COMPLETED` orders are included in v2.2.0 Sales + Profit reporting.

### v2.2.0 calculation rules

Order-level Net Sales:

`grand_total - return_credit_amount`

The primary COGS source is the posted General Ledger COGS account (`5000`) for `SALE` journals linked to the Sales Order reference. Completed return journals with source type `SALE_RETURN` may credit COGS when inventory is restocked; those credits reduce Net COGS.

If a historical completed order does not have its expected posted COGS journal, the report service falls back to the same weighted-cost calculation used by Accounting sale posting.

`Gross Profit = Net Sales - Net COGS`

`Gross Margin % = Gross Profit / Net Sales × 100`

Product-level reports exclude shipping revenue. Order-level discounts and return credits are allocated to product lines, and exact order Net COGS is allocated across sold items. Category and Brand grouping currently use each Product's current Catalog category/brand because category/brand are not snapshotted on Sales Order items.

v2.2.0 is an order-cohort profitability view: completed returns belonging to a completed order reduce that order's current Net Sales/Net COGS even if the return was completed after the original sale date. Period-activity Returns reporting is handled separately in v2.2.2.

## v2.2.1 — Stock + Purchase Reports

Implemented reports:

- Stock Report
- Stock Valuation
- Low Stock
- Stock Movement
- Purchase Report
- Supplier Due
- Customer Due

The same Reports dashboard and CSV export mechanism are reused. Operational reports add Warehouse filtering where the underlying data has a warehouse dimension, and Stock Movement also supports Movement Type filtering.

### Stock Report

Stock Report is date-aware. For the selected **As of** date, TechBari reads the latest immutable `StockMovement` snapshot available for each Warehouse + SKU position and uses its:

- `quantity_after` for On Hand
- `reserved_after` for Reserved
- `On Hand - Reserved` for Available

For current-day data where a legacy/bootstrap balance has no movement snapshot, the current `InventoryBalance` is used as a compatibility fallback.

The report includes Warehouse, Product, SKU, On Hand, Reserved, Available, Low Stock Threshold, weighted Unit Cost and Stock Value.

### Stock Valuation

Stock value is calculated as:

`On Hand Quantity × Weighted Purchase Cost as of the selected date`

The weighted cost is the same purchasing-cost service used by TechBari Accounting. Valuation is summarized by warehouse and reconciles to SKU-level stock rows.

This is an operational weighted-cost valuation. The later Balance Sheet report in v2.2.3 will use the General Ledger Inventory Asset balance as the financial-statement source of truth.

### Low Stock

Low Stock uses:

`Available Quantity <= configured Low Stock Threshold`

The stock quantity is date-aware. The threshold itself currently comes from the SKU/Warehouse's current `InventoryBalance` configuration because historical threshold changes are not snapshotted in the inventory ledger.

### Stock Movement

Stock Movement reads the immutable inventory ledger for the selected From/To range. It supports:

- Warehouse filter
- Movement Type filter
- quantity delta
- reserved delta
- quantity-after snapshot
- source/reference number

Movement types include purchase in, online/POS sale out, returns, purchase returns, adjustments, transfers, damage/loss, reservation and reservation release/sale events.

### Purchase Report

Purchase Report includes non-Draft and non-Cancelled Purchase Orders within the selected purchase-date range.

For each PO it shows:

- ordered and received quantity
- Grand Total
- supplier returns posted on or before the selected To date
- supplier payments posted on or before the selected To date
- Outstanding amount

`Outstanding = Grand Total - Returns - Payments`

A Warehouse filter is available.

### Supplier Due

Supplier Due is an **As of** report:

`Supplier Due = Opening Balance + Purchases - Purchase Returns - Supplier Payments`

Only purchases, returns and payments whose business dates are on or before the selected date are counted.

When a Warehouse filter is applied, purchase activity is restricted to that warehouse. Supplier Opening Balance remains global because the current Supplier model does not allocate opening balance by warehouse.

### Customer Due

Customer Due is also an **As of** report. It uses the transaction history rather than today's cached due property:

`Customer Due = Opening Due + Sales - Completed Return Credits - Net Customer Payments`

Customer sales include non-Draft/non-Cancelled orders dated on or before the selected date. Completed return credits are included only when the return completion date is on or before the selected date.

Net Customer Payments are derived from the central `PaymentTransaction` ledger. Money-in sale payments increase paid amount; refund/reversal money-out transactions reduce net paid amount. This makes historical customer due date-aware.

Guest sales are not assigned to Customer Due because they have no Customer account.

## Shared filters and output

Across v2.2.0 and v2.2.1, the Reports dashboard supports report-appropriate combinations of:

- From date
- To / As of date
- sales channel: All / Online / Manual / POS
- Warehouse
- Stock Movement Type
- KPI summary cards
- UTF-8 CSV export preserving active report filters
- responsive tables

The default period is the current month through today. Reversed From/To input is normalized automatically.

## Validation

### v2.2.0

Validated on GitHub Actions with MySQL 8 and Python 3.12:

- dedicated Reports suite: 5/5 passed
- full application regression suite: 157/157 passed

### v2.2.1

Validated on GitHub Actions with MySQL 8 and Python 3.12 using:

- `python manage.py check`
- `python manage.py makemigrations --check --dry-run`
- `python manage.py migrate --noinput`
- `python manage.py test reports -v 2`
- full application regression suite including Reports

Final validation result:

- dedicated Reports suite: 11/11 passed
- full application regression suite: 163/163 passed
- no new database migration required

## Remaining Reports roadmap

### v2.2.2 — Operational Finance + After-sales Reports

- Payment Report
- Expense Report
- Returns Report
- Warranty Report
- Serial / IMEI Report

### v2.2.3 — Financial Statements

- Profit & Loss
- Balance Sheet
- Cash Flow
- Trial Balance

Financial statements will use the Accounting General Ledger as their source of truth rather than recomputing accounting from operational modules.
