# TechBari v1.7.0 — POS System

This phase implements the roadmap POS foundation on top of the existing Catalog, CRM, Sales Order and Inventory engines.

## Core principle

`POS UI → Sales Order Engine → Inventory Engine`

The POS does not create a second sales or stock system. Every counter sale becomes a real `SalesOrder` with channel `POS`, real `SalesOrderItem` rows, real CRM customer linkage when selected, and real Inventory movements.

## Features

- Product/variant search by name, SKU, barcode, brand and category.
- Warehouse-aware availability using `InventoryBalance.available_quantity`.
- Variant/SKU-level cart.
- Walk-in customer or existing CRM customer selection.
- Fixed or percentage discount in the browser; the server receives the calculated discount amount and validates it against current database prices.
- Multiple tender methods: Cash, Card, bKash and Nagad.
- Payment reference required for non-cash tender.
- Cash tender/change calculation.
- Hold / resume using Draft POS Sales Orders.
- Held orders do not reserve stock, so stock stays sellable until the held sale is resumed and completed.
- Completing a sale creates/updates a Pending POS order, reserves inventory, marks the order paid, confirms it and completes/sells it atomically.
- Completion issues inventory through the shared Sales Engine and Inventory Engine.
- Overselling is blocked.
- Printable receipt route.
- POS orders are immediately visible in the existing Sales Order dashboard and CRM history.

## POS tender metadata

`SalesOrder` now also stores:

- `payment_method`
- `payment_reference`
- `tendered_amount`
- `change_amount`

These fields are operational snapshots for POS v1.7.0. The dedicated Payment phase will introduce full payment transaction/gateway records and can migrate or build on this metadata.

## Hold / resume lifecycle

Held POS cart:

`POS cart → SalesOrder(Draft, channel=POS)`

No inventory reservation is created while held.

Resume + complete:

`Draft → Pending → Confirmed → Completed`

The Pending transition reserves current stock. Completed issues the reserved stock. If stock is no longer available when the held order is resumed, the entire completion fails safely.

## Payment behavior

- Cash: tendered amount must be at least the grand total; excess becomes change.
- Card / bKash / Nagad: tender must match the sale total exactly and a payment reference is required.
- POS v1.7.0 records these methods but does not call external gateways. Gateway verification belongs to the Payment roadmap phase.

## Routes

- `/dashboard/pos/` — real POS workspace
- `/dashboard/pos/action/` — hold / complete / discard actions
- `/dashboard/pos/held/<id>/` — held order JSON
- `/dashboard/pos/receipt/<id>/` — printable completed-sale receipt
- `/dashboard/orders/` — all resulting POS Sales Orders

## Database migration

`sales.0002_pos_tender_fields`

No Catalog or Inventory data is replaced. Existing Sales Orders receive blank/default POS tender metadata.

## QA scope

Automated coverage includes:

- Held POS order remains Draft without stock reservation.
- Cash sale completes and reduces on-hand inventory.
- Cash change is captured.
- Held order resumes into the same Sales Order.
- Non-cash reference validation.
- Oversell protection.
- Real POS dashboard rendering.
- Printable receipt rendering.
- Full project regression should continue to run against MySQL 8.

## Deployment

```powershell
git pull origin main
python manage.py migrate
python manage.py check
python manage.py test catalog inventory serial_tracking purchasing customers sales storefront
python manage.py runserver
```

Then open `/dashboard/pos/`.

## Next roadmap phase

**v1.8.x — Payment System**

The Payment phase should add durable payment transactions, provider/method configuration, partial/multi-payment support, gateway references/statuses, refunds/reversals, reconciliation and payment audit trails. POS will then write through that payment engine instead of relying only on Sales Order tender snapshots.
