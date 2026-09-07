# TechBari v1.8.0 — Payment System

This phase introduces the central transaction-level Payment ledger for Sales, POS and Supplier payments.

## Core principle

**Sales Order / POS / Purchasing may initiate a payment, but PaymentTransaction is the financial payment audit trail.**

`SalesOrder.amount_paid` remains as a compatibility/cache field. v1.8.0 keeps it synchronized from the Payment ledger so existing CRM/order calculations continue to work while future Accounting can consume transaction-level payment records.

## Payment methods

Seeded methods:

- Cash
- Bank Transfer
- Card
- bKash
- Nagad
- Other

`PaymentMethodConfig` controls whether a method is active and available for Dashboard, POS and future Storefront use. Provider code, merchant label, test-mode flag and customer instructions are stored; merchant secrets are deliberately not stored in this table.

## Payment transaction ledger

`PaymentTransaction` records:

- unique transaction number
- Sales Order or Supplier PurchasePayment source
- parent transaction for refund/reversal
- type: Sale Payment / Supplier Payment / Refund / Reversal
- direction: Money In / Money Out
- payment method
- status: Pending / Completed / Failed / Reversed
- amount
- provider/reference number
- external transaction ID
- transaction date
- note and actor
- reconciliation status
- reconciliation user/time

Transactions cannot be negative or source-less.

## Sales payments

Dashboard and POS payments now resolve to the same ledger.

A completed Sale Payment:

1. validates active payment method and channel permission;
2. blocks zero/negative amounts;
3. blocks overpayment;
4. requires a reference for non-cash methods;
5. writes an immutable payment event;
6. recalculates `SalesOrder.amount_paid` and payment status from ledger totals.

Multiple partial payments are supported.

## Compatibility with existing Sales/POS code

Some earlier v1.5-v1.7 paths still write `SalesOrder.amount_paid` directly. A compatibility signal compares the Sales Order cache with the central ledger and mirrors only the difference into Payment transactions. This prevents two independent payment truths while avoiding a breaking rewrite of older Sales/POS code.

Existing paid Sales Orders are imported into the Payment ledger during migration.

## Supplier payment integration

Existing `PurchasePayment` remains the Purchasing module's supplier-due record. Every new supplier payment is automatically mirrored into the central Payment ledger as Money Out.

Existing supplier payments are imported during migration.

## Refunds and reversals

Refunds:

- link to the original Sale Payment;
- are Money Out;
- may be partial;
- cannot exceed the remaining refundable amount;
- immediately recalculate order paid/due status.

Reversals:

- are intended for erroneous unreconciled payment entries;
- reverse the original payment in full;
- are blocked after reconciliation or after a prior refund/reversal.

A reconciled payment should use Refund rather than Reversal.

## Reconciliation

Every transaction can be:

- Unreconciled
- Reconciled
- Disputed

Reconciliation records actor/time and an immutable event. This prepares the ledger for the later Accounting and bank/mobile-wallet reconciliation phases.

## Audit trail

`PaymentEvent` is immutable. It records:

- transaction creation
- status changes
- refund creation
- reversal creation
- reconciliation changes

## Dashboard routes

- `/dashboard/payments/`
- `/dashboard/payments/add/`
- `/dashboard/payments/methods/`
- `/dashboard/payments/<id>/`
- `/dashboard/payments/<id>/refund/`
- `/dashboard/payments/<id>/reverse/`
- `/dashboard/payments/<id>/reconcile/`

Order detail pages now show their Payment transactions and link to transaction-level capture/refund/reconciliation workflows.

## Storefront payment scope

v1.8.0 provides the internal ledger and provider configuration foundation. It does **not** fake successful bKash/Nagad/Card gateway payments without merchant credentials and verified callbacks.

The existing storefront COD checkout remains operational. `allow_storefront` is provider readiness/configuration only until a real merchant gateway integration is configured with secure credentials and callback verification.

## Migrations

- `payments.0001_initial` — Payment tables, method seed data, import old Sales/Purchase payments.
- `payments.0002_transaction_date_default` — aligns default transaction date behavior.

No existing payment/order/purchase data is discarded.

## Deployment

```powershell
git pull origin main
python manage.py migrate
python manage.py check
python manage.py test catalog inventory serial_tracking purchasing customers sales payments storefront
python manage.py runserver
```

Do not run seed commands during an upgrade.

## Next roadmap phase

**v1.9.x — Shipping / Courier**

That phase should connect confirmed Sales Orders to courier/shipment records, delivery status, tracking, COD collection and delivery reconciliation while reusing the current Sales + Payment foundation.
