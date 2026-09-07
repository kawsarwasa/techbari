# TechBari v2.1.0 — Expense Management System

## Goal

v2.1.0 adds a real database-backed operating Expense workflow on top of the v2.0.0 Accounting Ledger.

The phase keeps the project architecture intact:

**One Product Database + One Inventory Engine + One Sales Engine + One Accounting Ledger.**

Expense Management owns the operational expense record and approval/payment lifecycle. Accounting remains the financial source of truth and receives a balanced journal only when an approved expense is actually paid.

## Core models

### ExpenseCategory

Expense categories contain:

- unique category code
- category name and description
- active/inactive state
- sort order
- mandatory mapping to an active Expense-type Chart of Accounts account

Default categories are seeded for Rent, Utilities, Marketing, Office Supplies, Internet/Communication, Transport/Travel, Repairs, Bank/MFS Charges, Professional Services, Staff Welfare and Other Expense.

Dedicated GL accounts are seeded under the 6200-series while `6990 Other Expense` remains the fallback category.

### Expense

Each Expense stores:

- generated Expense number
- expense date
- category / GL mapping
- payee or vendor
- description
- amount
- preferred payment method
- actual payment method/reference/date
- receipt or invoice number
- internal notes
- Draft / Pending / Approved / Paid / Rejected / Cancelled / Voided lifecycle
- requester / approver / payer snapshots
- approval and payment timestamps

Paid expenses are treated as historical financial records and are not edited in place.

### ExpenseEvent

Immutable audit events record creation, draft updates, submission, approval, rejection, payment, cancellation and void/reversal activity.

## Workflow

Normal flow:

```text
Draft
  ↓
Pending Approval
  ↓
Approved
  ↓
Paid
```

Alternative terminal states:

```text
Pending → Rejected
Draft/Pending/Approved → Cancelled
Paid → Voided (Accounting reversal required)
```

Only Draft expenses can be edited.

Only Pending expenses can be approved or rejected.

Only Approved expenses can be paid.

A Paid expense can only be voided through a reversing Accounting journal; the original Expense and original Posted journal remain in history.

## Payment methods

Expense payment supports:

- Cash
- Bank Transfer
- Card
- bKash
- Nagad
- Other

Non-cash payments require a transaction/reference number.

The chosen method determines the credited Accounting asset/clearing account.

## Accounting posting

When an Approved expense is paid, Expense Management calls the Accounting posting adapter inside the same database transaction.

Entry:

```text
Debit   Mapped Expense GL Account
Credit  Cash / Bank / Card / bKash / Nagad / Other Funds
```

The journal uses:

- source type: `Business Expense`
- idempotent source key: `expense_payment:<expense_id>`
- Expense number as source reference

If the target Accounting period is Closed, payment posting fails and the Expense remains Approved. No partial Paid state is saved.

## Voiding a paid expense

Voiding does not delete or edit the Posted journal.

The system finds the original Expense journal and creates an Accounting reversal on the requested reversal date. Only after the reversal succeeds is the Expense marked Voided.

This preserves auditability and keeps Trial Balance / General Ledger history intact.

## Dashboard

Routes:

- `/dashboard/expenses/` — expense list, KPIs and filters
- `/dashboard/expenses/add/` — create Draft or create + submit
- `/dashboard/expenses/categories/` — category and GL mapping management
- `/dashboard/expenses/<id>/` — detail and audit trail
- `/dashboard/expenses/<id>/edit/` — Draft-only edit
- `/dashboard/expenses/<id>/submit/` — submit for approval
- `/dashboard/expenses/<id>/approve/` — approve
- `/dashboard/expenses/<id>/reject/` — reject
- `/dashboard/expenses/<id>/cancel/` — cancel pre-payment expense
- `/dashboard/expenses/<id>/pay/` — payment + Accounting posting
- `/dashboard/expenses/<id>/void/` — paid-expense reversal

List filters include search, status, category, payment method and date range.

KPIs include:

- Paid This Month
- Paid This Year
- Approved / Unpaid value
- Pending Approval count

## Safety rules

- Expense amount must be positive.
- Categories must map to Expense-type GL accounts.
- Inactive categories cannot be used for new Expense records.
- Paid expenses require payment method/date and non-cash reference where applicable.
- Payment is allowed only from Approved state.
- Closed Accounting periods block payment and reversal posting.
- Paid expense correction uses Accounting reversal rather than deletion/editing.
- Expense audit events are immutable.
- Expense Management does not write Inventory, Sales, Purchase or Customer balances.

## Reports boundary

v2.1.0 provides operational Expense tracking and posts expenses into the Accounting Ledger.

The roadmap keeps the broader finance/reporting package for **v2.2.x — Reports**, which can now read real Expense and Accounting data for P&L, Balance Sheet, Cash Flow, expense breakdowns and aging reports.

## Deployment

After pulling v2.1.0:

```powershell
python manage.py migrate
python manage.py check
python manage.py test catalog inventory serial_tracking purchasing customers sales payments shipping returns accounting expenses storefront
python manage.py runserver
```

New migrations:

```text
accounting.0003_expense_source
expenses.0001_initial
```

No catalog seed command is required.
