# TechBari Serial / IMEI / Warranty Phase — v1.2.0

## Goal

Add unit-level electronics tracking on top of the v1.1.0 Inventory Engine without creating a second stock source of truth.

Catalog Variant/SKU remains the product identity. InventoryBalance remains authoritative for warehouse stock. SerializedUnit maps individual physical units to that stock and records identity/lifecycle/warranty information.

## Data model

### SerializedUnit

- `variant` → `catalog.ProductVariant`
- `warehouse` → `inventory.Warehouse`
- `serial_number` (unique, optional)
- `imei1` (unique, optional, 15 digits)
- `imei2` (unique, optional, 15 digits)
- `status`
  - Available
  - Reserved
  - Sold
  - Returned
  - Damaged
  - Warranty Service
  - Scrapped
- supplier / purchase references
- purchase date / received date / purchase cost
- sales / order reference
- customer reference
- sold date
- warranty type
- warranty start / end
- supplier warranty reference
- notes and timestamps

At least one of Serial Number, IMEI 1 or IMEI 2 is required.

### SerializedUnitEvent

Immutable audit history for:

- registration
- identifier edits
- warehouse transfer
- lifecycle status changes
- warranty claim opening/update
- warranty replacement

Events cannot be edited or deleted through the model API.

### WarrantyClaim

- unique claim number
- exact SerializedUnit
- customer name / phone
- order reference
- claim date
- issue
- Open / In Service / Resolved / Replaced / Rejected status
- resolution / service reference
- optional same-SKU replacement unit
- resolved date
- original unit status snapshot
- notes / actor / timestamps

## Inventory integration

Serialized registration does **not** create stock. Stock must already exist in Inventory before a stock-bearing unit can be registered.

For stock-bearing states, registration count cannot exceed warehouse `on_hand` for that Variant/SKU.

Lifecycle transitions call the Inventory service layer:

- Available → Reserved: reserve 1
- Reserved → Available/Returned: release reservation
- Reserved → Sold: reserved sale, on-hand -1 and reserved -1
- Available/Returned → Sold: sale out -1
- Sold → Returned/Available: return in +1
- Available/Returned → Damaged/Scrapped: damage out -1
- Available/Returned → Warranty Service: adjustment out -1
- Damaged/Warranty Service/Scrapped → stock-bearing state: adjustment/return in +1

Warehouse changes are also inventory-aware:

- Available/Returned units use a real StockTransfer quantity of 1.
- Reserved units release the reservation, transfer quantity 1, then restore the reservation in the destination warehouse inside one database transaction.
- Non-stock-bearing units update their location record without changing warehouse stock.

All service operations use Django transactions and the Inventory Engine's row locks/negative-stock protections.

## Warranty workflow

Opening a claim records the unit's previous lifecycle status and moves the unit to Warranty Service.

For a normal Resolved or Rejected claim, the previous lifecycle status is restored.

For Replaced claims:

1. replacement must be another unit of the same Variant/SKU;
2. replacement must be Available or Returned;
3. replacement is transitioned to Sold through Inventory;
4. original unit is transitioned to Scrapped;
5. replacement relation and immutable history are retained on the claim/unit.

## Dashboard routes

- `/dashboard/serials/`
- `/dashboard/serials/add/`
- `/dashboard/warranty/`
- `/dashboard/warranty/add/`

The serial list supports search across Serial, IMEI, SKU, product, customer and sales reference plus status/warehouse filters.

The serialized-unit form supports registration and edit. Editing warehouse or lifecycle status uses the service layer; it does not directly bypass Inventory.

The unit page displays recent immutable event history and linked warranty claims.

Warranty screens support claim search/filter and add/edit flows.

## Migration

`serial_tracking.0001_initial` creates the unit/event/claim tables only. It does not rewrite existing Catalog or Inventory quantities.

Upgrade from v1.1.0:

```powershell
python manage.py migrate
python manage.py check
python manage.py test catalog inventory serial_tracking
```

No seed command is required for this phase.

## Future integration points

The fields are intentionally ready for the roadmap modules that come next:

- Supplier/Purchase can populate supplier reference, purchase reference, purchase cost and received date while receiving serialized units.
- Sales Order/POS can assign an Available/Reserved SerializedUnit and populate sales/customer references.
- Returns can transition sold units back into Returned status through the same Inventory Engine.
- Customer/CRM can later replace the temporary customer-reference text with relational customer/order links through a compatibility migration.
