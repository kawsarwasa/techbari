# TechBari v1.10.0 — Returns / Refunds System

## Goal

The Returns module sits on top of the existing Sales, Inventory, Serial/IMEI, Payment and Shipping engines. It does not create a second stock or money system.

Core rule:

**Sold item → Return workflow → inspected disposition → Inventory/Serial change + Sales Order credit + Payment refund (only when actually owed).**

## Sales return lifecycle

A return uses the following controlled lifecycle:

1. `Requested`
2. `Approved`
3. `Received / Inspecting`
4. `Completed`

Terminal alternatives:

- `Rejected`
- `Cancelled`

Creating, approving or receiving a return does not change stock or money. Inventory and financial effects are posted atomically only when the return is completed.

## Eligibility and quantity protection

Only `Completed / Sold` Sales Orders can enter the Returns module.

Each return line points to the original `SalesOrderItem` and therefore the exact Product Variant / SKU. The service layer blocks:

- returning more than the original `issued_quantity`,
- overlapping active return quantities,
- refund/credit above the remaining original line value,
- a return item from another Sales Order,
- a mismatched Serial/IMEI unit,
- the same Serial/IMEI appearing in multiple active returns.

Requested, Approved, Received and Completed return lines consume the available return quantity. Rejected and Cancelled return lines do not.

## Return sources

Supported source classifications:

- Customer Return
- Courier Return
- POS / Counter Return
- Manual / Other

A `Courier Return` is only accepted when the linked Shipping record is already `Returned to Merchant`. The Shipping module intentionally does not auto-restock a returned parcel; v1.10.0 requires explicit inspection through Returns before inventory can be increased.

## Item condition and stock disposition

Each return item records condition and a disposition decision.

Conditions:

- Sealed / Unopened
- Opened but Good
- Used
- Defective
- Damaged

Dispositions:

- Return to Sellable Stock
- Damaged / Quarantine
- Warranty / Service
- Scrap
- Do Not Add to Stock

Only `Return to Sellable Stock` increases normal sellable Inventory.

For non-serialized items, completion posts `StockMovement.Type.RETURN_IN` to the selected receiving warehouse.

For serialized items, the exact unit is processed through the Serial/IMEI service. A sold unit can move to Returned, Damaged, Warranty Service or Scrapped according to inspection. When it moves from Sold to Returned, the existing Serial/Inventory service posts the Return-In stock movement; the Returns module does not double-post it.

## Order return credit vs cash refund

v1.10.0 adds `SalesOrder.return_credit_amount` and the derived property `SalesOrder.payable_total`.

Formula:

```text
payable_total = max(grand_total - return_credit_amount, 0)
outstanding   = max(payable_total - net_paid, 0)
```

This distinction is important for partially paid orders.

Example:

```text
Order total:        1,000
Customer paid:        500
Approved return:      200
New payable total:    800
Cash refund needed:     0
Remaining due:        300
```

The system does not incorrectly refund Tk 200 in cash when the customer still owes money. The return credit first reduces the receivable.

If the same order had already been fully paid:

```text
Order total:        1,000
Customer paid:      1,000
Approved return:      200
New payable total:    800
Cash refund needed:   200
Remaining due:          0
```

Only the overpaid portion after return credit becomes an actual Payment refund.

## Payment ledger integration

Actual customer refunds reuse the v1.8 Payment ledger.

The Returns service:

1. Calculates the order credit.
2. Calculates whether the customer is overpaid after that credit.
3. Finds remaining refundable amounts on original Sale Payment transactions.
4. Allocates the required cash refund across one or multiple source payments.
5. Calls the existing `refund_sales_payment()` service.
6. Stores `SalesReturnRefund` links from the return to the source and generated refund transactions.
7. Synchronizes Sales Order payment status and net paid amount.

This supports multiple original payments and avoids independent refund bookkeeping.

## CRM impact

Customer `total_spent` now uses the completed Sales Order `payable_total`, so completed return credits reduce net customer spend. Customer due uses the return-aware `outstanding_amount`.

## Data model

### `SalesReturn`

- return number
- Sales Order
- receiving Warehouse
- source
- status
- resolution
- reason category
- source reference
- refund reference
- requested / received / completed dates
- customer note
- internal note
- actor / timestamps

### `SalesReturnItem`

- Sales Return
- original Sales Order Item
- Variant/SKU snapshots
- quantity
- condition
- disposition
- approved refund/credit amount
- optional exact Serialized Unit
- restocked quantity
- note

### `SalesReturnRefund`

- Sales Return
- original source PaymentTransaction
- generated refund PaymentTransaction
- amount

### `SalesReturnEvent`

Immutable audit history for creation, status, inventory, order credit and payment refund events.

## Dashboard routes

```text
/dashboard/returns/
/dashboard/returns/add/
/dashboard/returns/<id>/
/dashboard/returns/<id>/approve/
/dashboard/returns/<id>/receive/
/dashboard/returns/<id>/complete/
/dashboard/returns/<id>/reject/
/dashboard/returns/<id>/cancel/
```

Completed Sales Order detail pages link directly to the Return form. Courier-returned orders also expose the same workflow rather than silently changing inventory.

## Transaction safety

Return completion runs inside one database transaction. If Inventory, Serial/IMEI, Payment allocation or validation fails, the entire completion is rolled back.

A return cannot be completed twice. Completed, Rejected and Cancelled states are terminal.

## Migrations

v1.10.0 adds:

```text
sales.0003_salesorder_return_credit_amount
returns.0001_initial
```

No seed command is required.

## Upgrade commands

```powershell
git pull origin main
python manage.py migrate
python manage.py check
python manage.py test catalog inventory serial_tracking purchasing customers sales payments shipping returns storefront
python manage.py runserver
```

## Next roadmap dependency

The next major phase is Accounting. Returns already expose the data Accounting will need later:

- sales return credit,
- real customer cash refund transactions,
- sellable stock return quantities,
- damaged/warranty/scrap dispositions,
- courier-return references,
- immutable return audit events.

Accounting should consume these existing records rather than create duplicate return/refund ledgers.
