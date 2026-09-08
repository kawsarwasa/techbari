# Reports Phase — v2.2.x

TechBari Reports is being implemented in controlled sub-releases so operational reports remain reconcilable with the Accounting General Ledger.

Route: `/dashboard/reports/`

## v2.2.0 — Sales + Profit Reports

Implemented:

- Sales Report
- Daily Sales
- Monthly Sales
- POS vs Online / Manual Sales
- Product Sales
- Category Sales
- Brand Sales
- Profit Report
- COGS Report

Only completed Sales Orders are included. Order-level Net Sales is `grand_total - return_credit_amount`. Posted General Ledger COGS is the primary cost source, completed return COGS reversals reduce Net COGS, and Gross Profit is `Net Sales - Net COGS`.

Product/Category/Brand reports exclude shipping revenue and allocate order discounts, return credit and exact order COGS across product lines.

## v2.2.1 — Stock + Purchase Reports

Implemented:

- Stock Report
- Stock Valuation
- Low Stock
- Stock Movement
- Purchase Report
- Supplier Due
- Customer Due

Stock/Valuation/Low Stock use the latest immutable Stock Movement quantity/reservation snapshot up to the selected As-of date, with current InventoryBalance as a compatibility fallback for current-day legacy/bootstrap rows that have no movement snapshot.

Operational stock value is:

`On Hand × weighted purchase cost as of date`

Supplier Due is:

`Opening Balance + Purchases - Purchase Returns - Supplier Payments`

Customer Due is:

`Opening Due + Sales - Completed Return Credits - Net Customer Payments`

Historical payment activity comes from the central PaymentTransaction ledger.

## v2.2.2 — Payment + Expense + Returns + Warranty + Serial/IMEI Reports

Implemented:

- Payment Report
- Expense Report
- Returns Report
- Warranty Report
- Serial / IMEI Report

The same Reports dashboard, KPI cards, responsive tables and UTF-8 CSV export are reused.

### Payment Report

Source of truth: `payments.PaymentTransaction`.

Filters:

- From / To date
- Kind: Sale Payment / Supplier Payment / Refund / Reversal
- Method: Cash / Bank / Card / bKash / Nagad / Other
- Status: Pending / Completed / Failed / Reversed

Rows include transaction date/number, kind, direction, method, status, counterparty, source/reference, amount and reconciliation state.

KPI money totals count **Completed** transactions only:

- Completed Money In
- Completed Money Out
- Net Cash Flow
- Reconciled transaction count

This is an operational payment-ledger report. It does not replace the v2.2.3 Cash Flow financial statement, which will use the General Ledger.

### Expense Report

Source of truth: `expenses.Expense`.

Filters:

- From / To expense date
- Expense status
- Expense category
- Payment method

Rows include expense number/date, category, payee, description, workflow status, amount, payment method, exact payment Asset account, payment date and reference.

KPI rules:

- Active Amount excludes Rejected, Cancelled and Voided expenses
- Paid Amount counts Paid expenses only
- Pending Approval and Approved/Unpaid are shown separately

The report reads the Expense workflow directly; v2.2.3 P&L will use posted GL Expense balances instead of recomputing financial statements from Expense records.

### Returns Report

Source of truth: `returns.SalesReturn` plus Return Items and Return Refund links.

The report uses the **requested-date range** and shows both requested and completed dates.

Filters:

- Status
- Source: Customer / Courier Return / POS / Manual
- Reason

Rows include return/order/customer, source, reason, status, returned units, restocked units, return credit, cash refund and completion date.

Financial KPI totals for credit/refund use completed returns so open/rejected/cancelled cases do not inflate completed return value.

### Warranty Report

Source of truth: `serial_tracking.WarrantyClaim`.

Filters:

- Claim-date range
- Claim status
- current unit warehouse

Rows include claim number/date, Product, SKU, Serial/IMEI, customer, status, warranty-coverage result, issue, resolution date and replacement unit.

Coverage uses the claimed unit's stored warranty start/end dates against the claim date.

The Warehouse filter represents the unit's **current** warehouse location; warehouse history remains available through SerializedUnitEvent rather than being inferred here.

### Serial / IMEI Report

Source of truth: `serial_tracking.SerializedUnit`.

The date range is the unit's database registration/creation date.

Filters:

- current serialized-unit status
- current warehouse

Rows include Product, SKU, Serial Number, IMEI 1/2, Warehouse, status, purchase reference, sales reference and warranty end date.

KPI cards include serialized unit count, Available, Sold, Warranty Service and currently active warranty counts.

This is a current-state registry for units created in the selected range; it is not a historical status reconstruction. Immutable `SerializedUnitEvent` remains the lifecycle audit source.

## Shared filters and output

Across v2.2.0–v2.2.2 the Reports dashboard supports report-appropriate combinations of:

- From / To date
- As-of date where applicable
- Sales Channel
- Warehouse
- Stock Movement Type
- Payment Kind / Method / Status
- Expense Status / Category / Method
- Return Status / Source / Reason
- Warranty Status
- Serial/IMEI Status
- KPI summary cards
- UTF-8 CSV export preserving active filters
- responsive report tables

Default range is current month through today. Reversed From/To input is normalized automatically.

## Validation

### v2.2.0

- Reports suite: 5/5 passed
- Full regression: 157/157 passed

### v2.2.1

- Reports suite: 11/11 passed
- Full regression: 163/163 passed
- no new migration

### v2.2.2

Validated on GitHub Actions with MySQL 8 and Python 3.12 using:

- `python manage.py check`
- `python manage.py makemigrations --check --dry-run`
- `python manage.py migrate --noinput`
- `python manage.py test reports -v 2`
- full application regression suite including Reports

Final result:

- Reports suite: **16/16 passed**
- Full regression suite: **168/168 passed**
- migration drift: **No changes detected**
- no new database migration required

## Remaining Reports roadmap

### v2.2.3 — Financial Statements

- Profit & Loss
- Balance Sheet
- Cash Flow
- Trial Balance

Financial statements will use the Accounting General Ledger as the source of truth rather than rebuilding accounting from operational modules.
