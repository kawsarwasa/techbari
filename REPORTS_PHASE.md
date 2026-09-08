# Reports Phase — v2.2.x

TechBari Reports is being implemented in controlled sub-releases so operational reports remain reconcilable with the Accounting General Ledger.

## v2.2.0 — Sales + Profit Reports

Route: `/dashboard/reports/`

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

## Shared filters and output

v2.2.0 supports:

- From date
- To date
- sales channel: All / Online / Manual / POS
- default period: current month through today
- automatic normalization when From/To are entered in reverse order
- KPI summary cards
- UTF-8 CSV export preserving the active date/channel/report filters
- responsive dashboard tables

Only `SalesOrder.Status.COMPLETED` orders are included.

## Core calculations

### Net Sales

Order-level Net Sales:

`grand_total - return_credit_amount`

This includes customer shipping revenue at the order level because it is part of the completed order total.

### COGS

The primary COGS source is the posted General Ledger COGS account (`5000`) for `SALE` journals linked to the Sales Order reference.

Completed return journals with source type `SALE_RETURN` may credit COGS when inventory is restocked. Those credits reduce the order's Net COGS.

If a historical completed order does not have its expected posted COGS journal, the report service falls back to the Accounting weighted-cost calculation used by sale posting.

### Gross Profit

`Gross Profit = Net Sales - Net COGS`

### Gross Margin

`Gross Margin % = Gross Profit / Net Sales × 100`

A zero-sales row returns a zero margin instead of dividing by zero.

## Product / Category / Brand reporting

Product-level reports use Sales Order items and exclude shipping revenue so that product performance is not inflated by delivery charges.

- item line sales come from the order item snapshot/value
- order-level discount is allocated across product lines
- completed return refund amounts are deducted from affected product lines
- legacy/unallocated order return credit is distributed across order lines
- exact order Net COGS is allocated across sold items using weighted-cost estimates as the allocation weight
- if an item cost weight is unavailable, the allocation falls back to product net-sales weights

The final item COGS allocation always reconciles back to the exact order-level Net COGS.

Category and Brand grouping currently use each Product's **current** Catalog category/brand. Sales Order items snapshot product name/SKU but do not yet snapshot category/brand. If historical classification snapshots become necessary, that should be added as a separate schema change rather than silently inferred.

## Returns treatment

v2.2.0 is an order-cohort profitability view: completed returns belonging to a completed order reduce that order's current Net Sales/Net COGS even if the return was completed after the original sale date.

A period-activity Returns Report will be implemented separately in v2.2.2, and period financial reporting will come from the General Ledger in v2.2.3.

## Validation

The v2.2.0 branch was validated on GitHub Actions with MySQL 8 and Python 3.12:

- `python manage.py check`
- `python manage.py makemigrations --check --dry-run`
- `python manage.py migrate --noinput`
- `python manage.py test reports -v 2`
- full application regression suite including Reports

At implementation time the dedicated Reports suite passed 5/5 tests and the full regression suite passed 157/157 tests.

## Remaining Reports roadmap

### v2.2.1 — Stock + Purchase Reports

- Stock Report
- Stock Valuation
- Low Stock
- Stock Movement
- Purchase Report
- Supplier Due
- Customer Due

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
