# TechBari v1.9.0 — Shipping / Courier System

This phase turns the existing Shipping dashboard from a browser/localStorage demo into a MySQL-backed fulfillment and courier workflow connected to Sales, Inventory and Payment.

## Core rule

**Sales Order owns the sale, Inventory owns stock, Shipping owns parcel delivery state, and Payment owns customer money.**

Shipping never edits stock balances or payment totals directly.

## Courier providers

`CourierProvider` stores:

- unique code and provider name
- contact details
- website
- optional tracking URL template using `{tracking_id}`
- COD capability
- default courier fee
- active/inactive state
- API-enabled/test-mode readiness
- notes

v1.9.0 seeds Manual / Own Delivery plus common Bangladesh courier profiles (Pathao, Steadfast and RedX) as editable configurations. API calls are disabled by default and no third-party success response is faked without real credentials/provider verification.

## Shipment lifecycle

`Shipment` is linked one-to-one with a non-POS Sales Order in v1.9.0. This intentionally avoids partial/split fulfillment while the current Sales Engine issues inventory at order level.

Statuses:

- Draft
- Ready for Handover
- Handed Over
- In Transit
- Out for Delivery
- Delivered
- Delivery Failed
- Returning to Merchant
- Returned to Merchant
- Cancelled

Shipment records store tracking ID, courier reference, ship/expected dates, parcel count, weight, courier fee, locations, failure reason and fulfillment timestamps.

## Inventory handover contract

Creating a shipment does **not** deduct stock.

When a parcel moves to Handed Over (or later fulfillment states), Shipping calls the existing Sales transition service and completes the Sales Order. The Sales Engine then issues the reserved inventory through the Inventory Engine.

Courier Return / Returned status does not silently put stock back. The physical return and inventory re-entry belong to the next Returns/Refunds phase.

## Tracking and audit

`ShipmentEvent` is immutable and records:

- shipment creation
- status changes
- tracking updates
- delivery attempts/failures
- COD collection
- COD settlement
- notes, location and actor

Tracking IDs are unique within the same courier provider.

## COD collection

At shipment creation, COD defaults to the Sales Order's current outstanding amount. It may be reduced for prepaid/partially-paid orders, but cannot exceed the order due.

On Delivered:

- COD shipments require a recorded collected amount;
- collection cannot exceed expected COD;
- short collection is marked Disputed / Short;
- prepaid shipments remain Not Applicable.

The shipment tracks expected, collected, settled and unsettled COD separately.

## Courier COD settlement

`CODSettlement` supports courier remittance batches.

A settlement records:

- courier
- settlement date
- payment method
- bank/wallet/settlement reference
- gross COD
- courier deduction
- net received
- note/actor

Each `CODSettlementItem` links one delivered shipment to one generated Payment transaction.

Posting a settlement:

1. validates the shipment is Delivered and belongs to the selected courier;
2. blocks settlement above collected/unsettled COD;
3. blocks Sales Order overpayment;
4. creates a completed Sale Payment in the central Payment ledger;
5. marks the Payment transaction Reconciled;
6. updates Shipment COD settled state.

Gross customer COD is posted as the Sales payment. Courier deduction is stored separately so the later Accounting module can post courier expense/fee and bank net correctly.

## Dashboard routes

- `/dashboard/shipping/`
- `/dashboard/shipping/add/`
- `/dashboard/shipping/providers/`
- `/dashboard/shipping/<id>/`
- `/dashboard/shipping/<id>/status/`
- `/dashboard/shipping/<id>/tracking/`
- `/dashboard/shipping/cod-settlements/`
- `/dashboard/shipping/cod-settlements/add/`
- `/dashboard/shipping/cod-settlements/<id>/`

Sales Order detail pages link directly to their Shipment or offer Create Shipment when eligible.

## Database tables

- `shipping_courierprovider`
- `shipping_shipment`
- `shipping_shipmentevent`
- `shipping_codsettlement`
- `shipping_codsettlementitem`

Migration: `shipping.0001_initial`.

## Deployment

```powershell
git pull origin main
python manage.py migrate
python manage.py check
python manage.py test catalog inventory serial_tracking purchasing customers sales payments shipping storefront
python manage.py runserver
```

No seed command is required; the migration creates editable courier profiles without touching existing Sales/Payment data.

## Deferred on purpose

- live courier booking/API calls without real merchant credentials
- webhook signature verification without a configured provider
- split/partial shipment inventory issue
- physical returned-stock re-entry
- customer refunds for returned deliveries
- courier fee accounting journal entries

These are kept out rather than simulated incorrectly.

## Next roadmap phase

**v1.10.x — Returns / Refunds**

The next phase should consume Returned/Delivered Sales + Shipment history, receive sale returns back into Inventory, restore serialized units when applicable, create customer refunds through Payment, and prepare accounting entries without duplicating any existing ledger.
