# Reports Phase — v2.2.x

TechBari Reports is implemented in controlled sub-releases so operational reporting remains reconcilable with the Accounting General Ledger.

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

Completed Sales Orders are the operational source. Net Sales is `grand_total - return_credit_amount`. Posted General Ledger COGS is the primary cost source, completed return COGS reversals reduce Net COGS, and Gross Profit is `Net Sales - Net COGS`.

## v2.2.1 — Stock + Purchase Reports

Implemented:

- Stock Report
- Stock Valuation
- Low Stock
- Stock Movement
- Purchase Report
- Supplier Due
- Customer Due

Historical Stock/Valuation/Low Stock use immutable Stock Movement snapshots up to the selected As-of date. Operational stock value uses weighted purchase cost. Supplier Due and Customer Due are date-aware and use their underlying purchase/payment/sales ledgers.

## v2.2.2 — Payment + Expense + Returns + Warranty + Serial/IMEI Reports

Implemented:

- Payment Report
- Expense Report
- Returns Report
- Warranty Report
- Serial / IMEI Report

These are operational reports. Payment reads `PaymentTransaction`; Expense reads the Expense workflow; Returns reads SalesReturn/items/refunds; Warranty and Serial/IMEI read serialized-unit lifecycle data. Report-specific lifecycle filters, KPI cards, responsive tables and UTF-8 CSV export are supported.

## v2.2.3 — Financial Statements

Implemented:

- Profit & Loss
- Balance Sheet
- Cash Flow
- Trial Balance

All four financial statements use the **Accounting General Ledger** rather than recomputing accounting from Sales, Payments, Purchases or Expenses.

### Profit & Loss

Date semantics: selected **From / To period**.

Source: posted/reversed General Ledger journal lines belonging to Revenue and Expense accounts.

Structure:

- Revenue
- Less: contra-revenue such as Sales Returns & Allowances
- Net Revenue
- Cost of Goods Sold
- Gross Profit
- Operating Expenses
- Net Profit / Loss

Core formulas:

`Net Revenue = credit-normal Revenue - debit-normal Contra Revenue`

`Gross Profit = Net Revenue - COGS`

`Net Profit = Gross Profit - Operating Expenses`

COGS account `5000` is separated from other Expense accounts so Gross Profit remains visible.

### Balance Sheet

Date semantics: selected **As of** date.

Source: cumulative General Ledger balances through that date.

Sections:

- Assets
- Liabilities
- Equity
- GL-derived Cumulative Earnings

TechBari does not require a closing journal just to render the Balance Sheet. Revenue/Expense temporary-account balances are converted into a synthetic presentation line named **Cumulative Earnings from GL**:

`Cumulative Earnings = cumulative Net Revenue - cumulative Expenses`

The report exposes an Accounting Equation check:

`Assets - Liabilities - Equity - Cumulative Earnings = 0`

An `Equation Difference` KPI makes any ledger inconsistency visible rather than hiding it.

### Cash Flow

Date semantics: selected **From / To period**.

Cash-equivalent General Ledger accounts:

- 1000 Cash
- 1010 Bank
- 1020 Card Clearing
- 1030 bKash
- 1040 Nagad
- 1090 Other Funds / Clearing

The statement reads actual debit/credit movement in those GL accounts and reconciles:

`Opening Cash + Net Cash Movement = Closing Cash`

Activity is classified as:

- Operating
- Investing
- Financing

Known operational journal sources such as Sale Payment, Supplier Payment, Courier Fee and Expense are classified as Operating. Reversal journals inherit the source classification of the journal being reversed so the original and reversal cancel within the same Cash Flow section.

For Manual Journals, classification is inferred from the non-cash counterpart accounts:

- Equity or Liability counterpart → Financing
- non-operational Asset counterpart → Investing
- otherwise → Operating

Because the current Chart of Accounts does not yet store an explicit cash-flow classification field per account, this Manual Journal classification is intentionally rule-based. The report always exposes `Reconciliation Difference`; the amount must remain zero when all cash-equivalent GL movements are included.

### Trial Balance

Date semantics: selected **As of** date.

The Reports version reuses Accounting's existing `trial_balance(as_of=...)` service, so it follows the same Posted/Reversed journal semantics as the Accounting module.

Rows show:

- Account Code
- Account Name
- Type
- Debit Activity
- Credit Activity
- Ending Debit
- Ending Credit

The report exposes Total Debit, Total Credit and Difference. Difference should be zero for a balanced ledger.

## Shared output

Across v2.2.0–v2.2.3 the Reports dashboard provides report-appropriate Date/As-of and operational filters, KPI cards, responsive tables and UTF-8 CSV export.

## Validation

### v2.2.0
- Reports: 5/5 passed
- Full regression: 157/157 passed

### v2.2.1
- Reports: 11/11 passed
- Full regression: 163/163 passed

### v2.2.2
- Reports: 16/16 passed
- Full regression: 168/168 passed

### v2.2.3

Validated on GitHub Actions with MySQL 8 and Python 3.12:

- `python manage.py check` — PASS
- `python manage.py makemigrations --check --dry-run` — PASS / No changes detected
- migrations — PASS
- Reports suite — **21/21 passed**
- full application regression suite — **173/173 passed**
- no new database migration required

Dedicated v2.2.3 tests verify:

- P&L is calculated from General Ledger activity
- Balance Sheet equation difference is zero
- Cash Flow opening + net movement reconciles to closing cash
- Trial Balance total debit equals total credit
- all four financial tabs render and export CSV

## Reports v2.2.x status

Reports v2.2.x is now complete. The next roadmap phase is **v2.3.x — Promotion / Marketing**.
