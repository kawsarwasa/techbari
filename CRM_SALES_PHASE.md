# TechBari v1.5.0 — Customer CRM + Sales Order Engine

This combined phase implements roadmap v1.4.x and v1.5.x together while keeping the dependency order explicit:

`Customer CRM → Sales Order → Order Items → Stock Reservation → Status Lifecycle → Inventory Deduction → CRM Metrics`

## Customer / CRM

Database models:

- `CustomerGroup`
- `Customer`

Customer profile fields include customer number, name, unique phone, email, group, source, address, district/city/postal code, credit limit, opening due, notes and active/inactive state.

Default database-backed groups are seeded by migration:

- Retail
- Wholesale
- VIP

CRM metrics are calculated from the Sales Order engine instead of being typed manually:

- Order count
- Completed order count
- Total spent
- Due balance
- First purchase
- Last purchase
- Repeat customer (`2+` completed orders)

Customers with sales history are protected from deletion; they can be made inactive instead. Customer groups in use are also protected from deletion.

Dashboard routes:

- `/dashboard/customers/`
- `/dashboard/customers/add/`
- `/dashboard/customers/<id>/`
- `/dashboard/customers/groups/`

## Sales Order Engine

Database models:

- `SalesOrder`
- `SalesOrderItem`
- `SalesOrderHistory`

Order fields include:

- Unique order number
- Linked CRM customer or guest shipping snapshot
- Warehouse
- Channel: Online / Manual / POS-ready
- Order date
- Shipping contact/address snapshot
- Subtotal
- Order discount
- Shipping charge
- Grand total
- Amount paid
- Derived payment status
- Notes

Order items are tied to the real Catalog `ProductVariant` and store snapshots of product, variant and SKU along with quantity, unit price, line discount, reserved quantity and issued quantity.

## Order lifecycle

Statuses:

- Draft
- Pending
- Confirmed
- Processing
- Completed / Sold
- Cancelled

Stock behavior:

### Draft

No stock reservation.

### Pending

Inventory is reserved for every order line. Overselling is blocked by the Inventory Engine.

### Confirmed / Processing

Reservation remains in place. The system verifies missing reservations before moving forward.

### Completed / Sold

Reserved stock is issued atomically through `issue_reserved_stock()` and therefore reduces warehouse on-hand inventory and releases the reservation in the same ledger movement.

### Cancelled

Unsold reserved stock is released. Orders that already issued stock cannot be cancelled; the later Returns module will handle sold stock coming back.

The Sales Order code never writes `ProductVariant.stock_quantity` directly. Inventory remains the only stock authority.

## Payment state

v1.5.0 tracks operational order-level `amount_paid` and automatically derives:

- Unpaid
- Partial
- Paid

This is intentionally not a full payment transaction ledger. The later Payment module will add transaction-level Cash / bKash / Nagad / Bank / Card records and accounting integration.

Customer due is calculated from non-draft/non-cancelled Sales Orders plus any CRM opening due.

## Order history

`SalesOrderHistory` is immutable and records:

- Created
- Updated
- Status changes
- Payment changes
- Stock reservation events

## Dashboard routes

- `/dashboard/orders/`
- `/dashboard/orders/add/`
- `/dashboard/orders/<id>/`
- `/dashboard/orders/<id>/confirm/`
- `/dashboard/orders/<id>/process/`
- `/dashboard/orders/<id>/complete/`
- `/dashboard/orders/<id>/cancel/`
- `/dashboard/orders/<id>/payment/`

## Safety

- All stock-impacting order operations are wrapped in database transactions.
- Inventory row locking is inherited from the Inventory Engine.
- Insufficient stock rolls back the order/reservation operation.
- Editing a Pending order releases the previous reservation and reserves the replacement item set within one transaction.
- Duplicate SKU rows are rejected.
- Customer/order history deletion protections preserve auditability.

## Deployment

After pulling v1.5.0:

```powershell
git pull origin main
python manage.py migrate
python manage.py check
python manage.py test catalog inventory serial_tracking purchasing customers sales
python manage.py runserver
```

No seed command is required. The CRM migration creates the standard Customer Groups automatically.

## Next roadmap phase

The storefront checkout is intentionally not wired into Sales Orders in this phase. Roadmap v1.6.x will convert Checkout into a real order-creation flow using this Sales Order Engine. POS can then reuse the same Sales + Inventory foundation.
