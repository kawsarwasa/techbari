# TechBari v1.3.0 — Supplier + Purchase Module

This phase converts the Supplier and Purchase dashboard from static/localStorage demo data into the shared MySQL-backed procurement engine.

## Architecture

Purchase is integrated with the existing architecture:

`Supplier → Purchase Order → Receipt → Inventory`

`Purchase Order → Supplier Payment → Outstanding`

`Purchase Order → Purchase Return → Inventory Out + Outstanding Reduction`

`Purchase Receipt → optional Serial/IMEI registration`

The Inventory Engine remains the only stock authority. Purchase code never edits `ProductVariant.stock_quantity` directly.

## Database models

### Supplier

- Unique supplier code
- Name / contact person
- Phone / email / address
- Tax/VAT reference
- Payment terms in days
- Credit limit
- Opening balance
- Active/inactive status
- Notes
- Live purchase, paid, return and outstanding calculations

### PurchaseOrder

Statuses:

- Draft
- Ordered
- Partially Received
- Received
- Cancelled

Fields include supplier, receiving warehouse, purchase/expected date, supplier invoice reference, shipping/other cost, order discount and notes.

### PurchaseOrderItem

Each order line is tied to the real Catalog `ProductVariant`/SKU and stores:

- Ordered quantity
- Received quantity
- Returned quantity
- Unit cost
- Line discount

Guards prevent receiving above ordered quantity or returning above received quantity.

### PurchaseReceipt / PurchaseReceiptItem

Every Goods Receipt Note (GRN) is stored separately so partial receipts have an audit trail. Receipt posting creates `Inventory StockMovement.PURCHASE_IN` records atomically.

Receipt rows optionally accept Serial / IMEI data. Inventory is increased first, then serialized units are registered against the same Supplier, PO, SKU, Warehouse, received date and purchase cost. Duplicate/invalid serial identifiers roll the entire receipt back.

### PurchasePayment

Operational supplier payment records include:

- Payment number
- Purchase order
- Supplier
- Amount
- Cash / Bank / bKash / Nagad / Card / Other
- Transaction reference
- Payment date
- Note

Overpayment above the current purchase outstanding is blocked. These payment records are intentionally operational; the later Accounting phase will post them into the general ledger.

### PurchaseReturn / PurchaseReturnItem

Purchase returns are linked to the original purchase, supplier and warehouse. Posting a return:

- Validates return quantity against net received stock
- Reduces Inventory
- Stores cost snapshots
- Reduces supplier outstanding
- Can link exact Serial/IMEI units

Serialized units returned to the supplier receive the `Returned to Supplier` lifecycle status and are linked through `PurchaseReturnSerialUnit` for auditability.

## Inventory behavior

Purchase receipt:

`+ quantity → PURCHASE_IN`

Purchase return:

`- quantity → PURCHASE_RETURN_OUT` for normal stock.

Serialized purchase returns also leave stock through the serialized-unit lifecycle and retain the purchase-return reference.

All operations use database transactions. Receipt validation, stock movement, item counters and Serial/IMEI registration succeed or fail together.

## Dashboard routes

- `/dashboard/suppliers/`
- `/dashboard/suppliers/add/`
- `/dashboard/purchases/`
- `/dashboard/purchases/add/`
- `/dashboard/purchases/<id>/`
- `/dashboard/purchases/<id>/receive/`
- `/dashboard/purchases/<id>/payment/`
- `/dashboard/purchases/<id>/return/`

Purchase detail shows items, ordered/received/returned quantities, receipts, payments, returns, supplier invoice data, totals and outstanding balance.

## Purchase workflow

1. Create Supplier.
2. Create Purchase Order as Draft or Ordered.
3. Add real Variant/SKU rows and unit costs.
4. Receive stock fully or partially.
5. Optionally register Serial/IMEI rows during receipt.
6. Record supplier payments as required.
7. Post supplier returns against already received quantities.
8. Purchase detail remains the audit view for the full procurement history.

## Safety rules

- Supplier with purchase history cannot be deleted; mark it inactive.
- Only Draft purchases can be deleted.
- Purchases with receipts/returns/payments cannot be structurally edited.
- Purchase receiving is allowed only for Ordered / Partially Received orders.
- Receipt quantity cannot exceed remaining ordered quantity.
- Purchase return quantity cannot exceed received minus already returned quantity.
- Serial/IMEI rows cannot exceed receipt quantity.
- Duplicate Serial/IMEI causes the whole receipt transaction to roll back.
- A serialized supplier return must belong to the same PO, Variant/SKU and Warehouse.
- Supplier payment cannot exceed outstanding amount.
- Received stock is never changed through Catalog fields directly.

## Upgrade

After pulling v1.3.0:

```powershell
python manage.py migrate
python manage.py check
python manage.py test catalog inventory serial_tracking purchasing
python manage.py runserver
```

No reseed is required. Existing Catalog, Inventory and Serial/IMEI data are preserved.

## Next roadmap phase

After Supplier + Purchase, the recommended next database phase is **Customer / CRM**, followed by the shared Sales Order engine, Checkout and POS.
