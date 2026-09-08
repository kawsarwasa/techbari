# TechBari v2.4.0 — Dashboard Analytics

TechBari v2.4.0 replaces the old static/demo dashboard with a database-backed management dashboard that reuses the business rules already established in Sales, Reports, Inventory, Purchasing and Customer CRM.

## Scope

- Today Sales
- Orders
- Profit
- Stock Alerts
- Top Products
- Top Categories
- Purchase Due
- Customer Due
- Sales Trend
- POS vs Online
- Recent Activity

## Source-of-truth rules

Dashboard Analytics does not invent a second set of financial or operational formulas.

### Sales, Profit, Trend, Top Products, Top Categories and Channel Analytics

These reuse the same completed-sale, return-aware Sales/Profit report semantics used by `reports.services`:

- completed Sales Orders are the sales source
- net sales subtract completed return credit
- COGS uses the same Accounting/Reports logic
- dashboard Profit is the same gross-profit concept as the Sales/Profit report: Net Sales − Net COGS
- Top Products and Top Categories reuse report product/category allocation rules
- POS / Online / Manual channel analysis reuses the Sales Order channel field and the report grouping semantics

This keeps dashboard sales/profit numbers consistent with Reports.

### Orders

Order KPIs and status summaries are read from `sales.SalesOrder`. The Today Orders KPI counts placed non-draft orders for the current local date, while completed-order sales/profit metrics remain governed by the Reports semantics above.

### Stock Alerts

Stock alerts use `inventory.InventoryBalance.available_quantity`:

```text
Available = On Hand − Reserved
```

A SKU is an alert when available quantity is less than or equal to its configured low-stock threshold. Zero available quantity is marked Out of Stock.

### Purchase Due

Purchase Due follows Purchasing/Supplier payable semantics:

- Supplier opening balance
- plus non-draft/non-cancelled Purchase Order value
- minus recorded Purchase Payments
- minus Purchase Returns

### Customer Due

Customer Due follows Customer CRM receivable semantics:

- Customer opening due
- plus outstanding non-draft/non-cancelled customer-linked Sales Orders
- return credit and amount paid reduce the outstanding amount

Guest orders are not added to CRM Customer Due because they are not linked to a Customer record.

### Recent Activity

The dashboard combines recent real records from:

- Sales Orders
- Payment Transactions
- Purchase Orders
- Expenses
- Sales Returns

The records are merged by timestamp and shown as a single latest-activity feed with links back to the relevant operational module.

## Dashboard periods

The analytics period selector supports:

- Today
- Last 7 Days
- Last 30 Days
- This Month
- Custom From / To dates

Custom reversed dates are normalized automatically.

The fixed Today KPI cards remain today-specific. The selected period controls the sales summary, trend, channel analysis, top products/categories and order-status summary.

## Dashboard UI

`/dashboard/` now contains:

- Today Sales
- Today Orders
- Today Profit
- Stock Alerts
- Purchase Due
- Customer Due
- selected-period Net Sales / Completed Orders / Gross Profit / Gross Margin
- Sales Trend
- POS vs Online / Manual channel comparison
- Top Products
- Top Categories
- Stock Alert table
- Order Status summary
- Recent Orders
- Recent Activity

The dashboard remains server-rendered and shared-hosting friendly; no Redis, Celery, WebSocket or always-on background service is required for this phase.

## Database migration

v2.4.0 adds no new database model or migration. It reads and aggregates the existing database-backed modules.

`python manage.py migrate` remains safe to run during deployment to ensure all earlier migrations are applied.

## Validation

Validated on GitHub Actions using MySQL 8 and Python 3.12:

- Django system check: PASS
- migration drift (`makemigrations --check --dry-run`): PASS / no changes detected
- migration application: PASS
- Dashboard Analytics dedicated suite: 7/7 PASS
- full regression suite: 195/195 PASS

Dedicated tests verify:

- Dashboard Sales/Profit consistency with the Reports calculation layer
- POS vs Online channel totals
- Top Product and Top Category results
- Customer Due semantics
- Purchase Due semantics
- available-stock / low-stock threshold rules
- period filtering and reversed custom date handling
- recent cross-module activity
