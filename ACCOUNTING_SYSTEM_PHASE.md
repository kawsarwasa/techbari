# TechBari v2.0.0 — Accounting System / General Ledger

## Goal

v2.0.0 introduces the platform-wide double-entry Accounting Ledger while preserving the existing operational sources of truth:

**One Product Database + One Inventory Engine + One Sales Engine + One Accounting Ledger.**

The Accounting app does not replace Sales, Inventory, Payments, Purchasing, Returns or Shipping. Those modules continue to own their operational workflows and Accounting translates completed financial events into immutable balanced journals.

## Core models

### Account

Chart of Accounts record with:

- unique account code
- name and description
- Asset / Liability / Equity / Revenue / Expense type
- Debit / Credit normal balance
- system-account protection marker
- manual-entry permission
- active/inactive state

### JournalEntry

Double-entry journal header with:

- generated journal number
- entry date
- source type
- idempotent source key
- business reference
- description
- Draft / Posted / Reversed status
- reversal relationship
- actor / posting timestamp

Posted journals are immutable. Corrections are made with a reversing journal rather than editing financial history.

### JournalLine

Each line points to a Chart of Accounts account and contains exactly one positive Debit or Credit amount. A journal must have at least two lines and total debit must equal total credit before posting.

### AccountingPeriod

Accounting periods support Open / Closed state. New journals and reversal journals cannot be posted into a closed period. Periods cannot overlap.

### AccountingEvent

Immutable Accounting audit events record journal creation, posting, reversal and period actions.

## Seeded system Chart of Accounts

| Code | Account | Type |
| --- | --- | --- |
| 1000 | Cash | Asset |
| 1010 | Bank | Asset |
| 1020 | Card Clearing | Asset |
| 1030 | bKash | Asset |
| 1040 | Nagad | Asset |
| 1090 | Other Funds / Clearing | Asset |
| 1100 | Accounts Receivable | Asset |
| 1200 | Inventory Asset | Asset |
| 2000 | Accounts Payable | Liability |
| 3000 | Opening Balance Equity | Equity |
| 4000 | Product Sales Revenue | Revenue |
| 4010 | Shipping Revenue | Revenue |
| 4090 | Sales Returns & Allowances | Contra Revenue |
| 5000 | Cost of Goods Sold | Expense |
| 6100 | Courier & Collection Fees | Expense |
| 6990 | Other Expense | Expense |

System accounts used by automatic postings are protected from ordinary manual postings unless specifically permitted.

## Automatic posting map

### Completed Sales Order

Revenue journal:

- Debit Accounts Receivable
- Credit Product Sales Revenue
- Credit Shipping Revenue when applicable

COGS journal when historical purchase cost is available:

- Debit Cost of Goods Sold
- Credit Inventory Asset

### Sale Payment

- Debit Cash / Bank / Card / bKash / Nagad / Other Funds
- Credit Accounts Receivable

### Customer Refund / Payment Reversal

- Debit Accounts Receivable
- Credit the original payment-method asset account

### Purchase Receipt

For each received purchase line:

- Debit Inventory Asset
- Credit Accounts Payable

Line discounts are included in net received unit cost. Purchase shipping, other cost and order-level discount are posted as a separate purchase-overhead adjustment when the PO becomes fully Received.

### Supplier Payment

- Debit Accounts Payable
- Credit Cash / Bank / payment-method asset

### Purchase Return

- Debit Accounts Payable
- Credit Inventory Asset

### Completed Sales Return

Return credit:

- Debit Sales Returns & Allowances
- Credit Accounts Receivable

Sellable inventory returned to stock also restores recognized cost:

- Debit Inventory Asset
- Credit Cost of Goods Sold

### Courier COD settlement deduction

The Payment Ledger posts COD receipts. Accounting separately recognizes courier/collection deductions:

- Debit Courier & Collection Fees
- Credit settlement asset / clearing account

## Inventory costing

v2.0.0 derives SKU cost from received Purchase history using net weighted receipt cost less Purchase Returns. This provides COGS and returned-inventory valuation for units with procurement history.

Legacy/opening inventory that has no purchase-cost history intentionally receives zero automatic COGS until a reliable cost basis exists. A business may establish opening Inventory/Equity values through a controlled manual journal. Fabricated cost is never inferred from selling price.

## Opening balances and migration

`accounting.0001_initial` creates the ledger schema and seeds the system Chart of Accounts.

`accounting.0002_backfill_existing_business_history` translates existing v1.x operational history into idempotent journals, including:

- customer opening due
- supplier opening balance
- historical purchase receipts
- purchase overhead
- purchase returns
- completed sales
- Payment transactions
- completed Sales Returns
- Courier COD deductions

Every automatic journal uses a unique source key so the same business event cannot be posted twice.

## Dashboard routes

- `/dashboard/accounts/` — Accounting overview
- `/dashboard/accounts/chart/` — Chart of Accounts
- `/dashboard/accounts/chart/add/` — Add custom account
- `/dashboard/accounts/journals/` — Journal Entries
- `/dashboard/accounts/journals/add/` — Manual Journal
- `/dashboard/accounts/journals/<id>/` — Journal detail and audit trail
- `/dashboard/accounts/ledger/` — General Ledger
- `/dashboard/accounts/trial-balance/` — Trial Balance
- `/dashboard/accounts/periods/` — Accounting Periods

The existing `/dashboard/payments/` remains the operational Payment Ledger. Accounting consumes its completed financial transactions.

## Safety rules

- Never directly edit a Posted or Reversed journal.
- Never directly create JournalLine rows for business events outside Accounting services.
- Use a reversal for correction.
- Automatic events use idempotent `source_key` values.
- New postings are rejected for closed accounting periods.
- Every posted journal must be balanced.
- Accounting does not directly mutate InventoryBalance, SalesOrder totals, PaymentTransaction, PurchaseOrder or Returns data.

## Reports boundary

v2.0.0 provides Accounting overview, General Ledger and Trial Balance needed to establish the financial source of truth.

The roadmap intentionally keeps dedicated business Expense management in **v2.1.x** and the broader Financial/Management Reports package (P&L, Balance Sheet, Cash Flow, receivable/payable aging and other reports) in **v2.2.x**. Those phases will read this Accounting Ledger rather than reconstruct finance from operational tables.

## Deployment

After pulling v2.0.0:

```powershell
python manage.py migrate
python manage.py check
python manage.py test catalog inventory serial_tracking purchasing customers sales payments shipping returns accounting storefront
python manage.py runserver
```

No catalog seed command is required.
