# TechBari v1.6.0 — Storefront Checkout Backend

This phase connects the public storefront checkout to the existing Customer / CRM, Sales Order and Inventory engines.

## End-to-end flow

`Browser Cart → Checkout Form → Server Validation → Customer Find/Create → Sales Order (Pending) → Inventory Reservation → Secure Confirmation`

The checkout never trusts browser prices, stock totals, discounts or shipping totals. The browser submits only selected Variant IDs and quantities. The server reloads active ProductVariant rows from MySQL, calculates current prices, applies the configured shipping charge/coupon rules and then calls the shared Sales Order service.

## Customer / CRM integration

- Bangladesh mobile number is required and normalized.
- Existing customer is matched by phone.
- A new online customer is created automatically when needed.
- Retail group is used when available.
- Latest checkout name/email/address is synchronized to the CRM profile.
- Email cannot silently move between two different customer records.
- Customer source is `Online Store`.

## Cart and catalog validation

Checkout requires a real Variant/SKU ID and positive quantity for every line.

Server checks:

- Variant exists.
- Variant is active.
- Product is Active.
- Category and Brand are active.
- Duplicate variant rows are merged.
- Maximum 99 units per SKU per checkout.
- Database price is used; browser price is ignored.
- Inventory reservation is performed by the Sales Engine / Inventory Engine.
- Insufficient stock rolls the complete checkout transaction back.

The storefront now displays availability from the default online warehouse, using `on_hand - reserved_quantity`, so public stock aligns with what Checkout can actually reserve.

## Sales Order integration

A successful checkout creates a real `SalesOrder` with:

- Channel: Online Store
- Status: Pending
- Payment status: Unpaid
- Linked CRM customer
- Default active warehouse
- Shipping snapshot
- Real Variant/SKU order items
- Server-calculated unit prices
- Coupon/order discount
- Shipping charge
- Customer note / checkout metadata

Pending status immediately reserves stock. Dashboard Confirmed/Processing preserves that reservation. Completed / Sold later issues the reserved stock and reduces on-hand inventory through the existing Sales Engine.

## Delivery

Current operational shipping rules:

- Inside Dhaka: Tk 60
- Outside Dhaka: Tk 120

These are verified on the server. A later Shipping/Courier phase will replace the fixed rules with configurable zones/courier services.

## Coupons

v1.6.0 keeps compatibility with the current storefront coupon definitions (`SAVE1000`, `SAVE500`, `TECH10`) and recalculates them on the server. This is intentionally temporary; the Promotions / Marketing phase will replace static coupon definitions with database-backed promotion rules.

## Payment scope

Only Cash on Delivery is accepted by the Checkout Backend in v1.6.0.

bKash, Nagad and Card remain visible as disabled future options. The dedicated Payment phase will add real transaction/gateway records and then enable those methods safely.

## Idempotency and confirmation security

- Each checkout GET receives a signed, pre-generated unique Sales Order number token.
- Re-submitting the same signed checkout token returns the existing online order rather than reserving stock twice.
- The confirmation page requires a signed order token in the URL.
- A plain order number is not enough to open the public confirmation page.

No Django session/auth dependency is introduced in this phase.

## Routes

- `/checkout/` — real GET/POST checkout
- `/checkout/success/<order_number>/?token=...` — signed confirmation
- `/dashboard/orders/` — new storefront orders appear here immediately

## Browser cart bridge

The existing browser cart remains localStorage based for this phase. `checkout-v160.js` converts the current cart into a minimal server payload containing only Variant ID + quantity. The server is authoritative for everything else.

A fresh browser now starts with an empty cart instead of the old demo cart data.

## Transaction safety

Checkout placement is wrapped in a database transaction. Customer creation/update, order creation, order items and inventory reservation either complete together or roll back together.

The checkout reuses `save_sales_order()` and Inventory row locking rather than creating a second stock path.

## QA coverage

The v1.6.0 test suite covers:

- Real checkout form rendering
- Empty default storefront cart
- Customer auto-create and existing-customer reuse
- Pending Sales Order creation
- Stock reservation
- Database price authority
- Server coupon calculation
- Inside/Outside Dhaka shipping
- Insufficient-stock rollback
- Duplicate checkout idempotency
- COD-only enforcement
- Tampered/empty cart rejection
- Signed confirmation protection
- Storefront availability after reservation
- Full regression across Catalog, Inventory, Serial/IMEI/Warranty, Purchasing, CRM and Sales

## Deployment

```powershell
git pull origin main
python manage.py migrate
python manage.py check
python manage.py test catalog inventory serial_tracking purchasing customers sales storefront
python manage.py runserver
```

v1.6.0 adds no new application migration. Existing business data is preserved. No seed command is required.

## Next roadmap phase

**v1.7.x — POS System**

POS should reuse the same Sales Order + Inventory foundation with barcode/SKU search, walk-in/customer selection, discounts, payment capture, hold/resume and receipt printing. The dedicated Payment phase follows POS.
