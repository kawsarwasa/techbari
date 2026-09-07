# TechBari — Django E-commerce + Admin

**Current version: v1.9.0**

TechBari is being converted phase-by-phase from a static Django template demo into a MySQL 8-backed commerce system. Catalog, Inventory, Serial / IMEI / Warranty, Supplier / Purchase, Customer / CRM, Sales Order, Storefront Checkout, POS, Payment and Shipping / Courier are now connected to the real business data flow.

## v1.9.0 — Shipping / Courier System

Shipping is now a real database-backed fulfillment workflow. Confirmed/Processing non-POS Sales Orders can be assigned to one courier shipment with provider, tracking, parcel, fee, COD and delivery state.

Inventory remains owned by the Sales + Inventory engines: creating a shipment does not deduct stock; moving a parcel to courier handover completes the Sales Order and issues its reserved inventory through the existing Sales service. Returned courier parcels do not silently re-add stock because that belongs to the next Returns/Refunds phase.

Courier COD is tracked as Expected / Collected / Settled / Unsettled. Delivered COD may be reconciled through courier settlement batches; each settlement creates and reconciles transaction-level Sale Payments in the existing Payment ledger while keeping courier deduction/net-receipt data for later Accounting.

Courier profiles are configurable and API readiness is stored, but no live third-party booking/tracking success is faked without real credentials and verified responses.

See `SHIPPING_COURIER_PHASE.md`.

## v1.8.0 — Payment System

TechBari now has a central transaction-level Payment ledger for Sales, POS and Supplier payments. It supports Cash, Bank Transfer, Card, bKash, Nagad and Other methods, multiple/partial Sales payments, refunds, full unreconciled reversals, reconciliation status and immutable payment audit events.

Existing SalesOrder paid amounts and existing Supplier PurchasePayment rows are imported during migration so historical payment data is preserved. New POS/order paid-amount writes are compatibility-synchronized into the Payment ledger, and new Supplier payments are mirrored automatically as Money Out.

Payment Method configuration controls Dashboard/POS/storefront readiness, provider code, merchant label and test mode. Storefront bKash/Nagad/Card gateway success is not faked without real merchant credentials/callback verification; current COD checkout remains operational.

See `PAYMENT_SYSTEM_PHASE.md`.

## v1.7.0 — POS System

The `/dashboard/pos/` screen is a real database-backed counter-sales system. It searches real Product Variants by product name, SKU, barcode, brand and category; stock shown is warehouse-aware and comes from `InventoryBalance.available_quantity`.

Counter sales reuse the same Sales Order + Inventory engines used by the storefront. Walk-in/CRM customers, discounts, hold/resume, Cash/Card/bKash/Nagad tender snapshots and printable receipts are supported.

See `POS_SYSTEM_PHASE.md`.

## v1.6.0 — Storefront Checkout Backend

The public `/checkout/` page creates real database-backed Online Sales Orders with CRM customer find/create, server-authoritative pricing/stock/coupon/shipping, Inventory reservation, signed idempotency and signed confirmation.

See `CHECKOUT_BACKEND_PHASE.md`.

## v1.5.0 — Customer CRM + Sales Order Engine

Customer profiles are real database records with group/source/address/credit/history metrics. Sales Orders use real Catalog Variant/SKU rows and the shared Inventory Engine with Draft / Pending / Confirmed / Processing / Completed / Cancelled lifecycle.

See `CRM_SALES_PHASE.md`.

## v1.3.0 — Supplier + Purchase

Suppliers, Purchase Orders, partial/full receipts, supplier payments and purchase returns are database-backed. Goods receipts call the Inventory Engine with `PURCHASE_IN`; optional Serial/IMEI registration is linked to the same supplier/PO/warehouse.

See `SUPPLIER_PURCHASE_PHASE.md`.

## v1.2.0 — Serial / IMEI / Warranty Tracking

Every tracked electronics unit can be linked to a Product Variant/SKU and Warehouse with unique Serial Number / IMEI 1 / IMEI 2, lifecycle status, purchase source, sales/customer references and warranty dates.

See `SERIAL_IMEI_WARRANTY_PHASE.md`.

## v1.1.0 — Inventory Phase 1

Inventory is warehouse/SKU based with authoritative `InventoryBalance`, immutable `StockMovement`, Stock Adjustment, Stock Transfer, reservations, low-stock rules and negative-stock protection. `ProductVariant.stock_quantity` remains a compatibility cache.

See `INVENTORY_PHASE1.md`.

## v1.0.10 — Catalog final QA

Catalog covers Categories, Brands, Products, Variants/SKUs/Barcodes, Product Images, Specifications, rich descriptions, pricing/status/SEO and database-backed Storefront catalog behavior.

See `CATALOG_DATABASE_PHASE.md`.

## Current database-backed modules

### Catalog
Categories / Brands, Products, Variants / SKUs / Barcodes, variant pricing, media, specifications, rich description, SEO and Storefront catalog integration.

### Inventory
Warehouses, warehouse/SKU balances, on-hand/reserved/available stock, Stock Movement ledger, adjustments, transfers, reservations, low-stock reporting and negative-stock protection.

### Serial / IMEI / Warranty
Unit-level tracking, Warehouse + SKU linkage, inventory-aware lifecycle, immutable unit events and Warranty/RMA claims.

### Supplier + Purchase
Supplier CRUD, Purchase Orders, receiving, Inventory `PURCHASE_IN`, optional Serial/IMEI registration, supplier payments and returns.

### Customer / CRM
Customer CRUD, Retail/Wholesale/VIP groups, customer source/address, credit/opening due, purchase history and derived customer metrics.

### Sales Order
Database-backed Sales Orders and items, Online / Manual / POS channels, real SKU lines, lifecycle/status history, inventory reservation/deduction and customer linkage.

### Storefront Checkout
Real GET/POST checkout, server-authoritative pricing/stock/coupon/shipping, CRM find/create, Inventory reservation, signed idempotency and signed public confirmation.

### POS
- Real warehouse-aware Product Variant catalog
- SKU / barcode search
- Walk-in or CRM customer
- Fixed / percentage discount
- Hold / resume Draft POS orders
- Cash / Card / bKash / Nagad tender snapshots
- Cash change calculation
- Atomic completion through Sales + Inventory
- Printable receipt

Routes: `/dashboard/pos/`, `/dashboard/pos/action/`, `/dashboard/pos/held/<id>/`, `/dashboard/pos/receipt/<id>/`.

### Payment
- Central Money In / Money Out ledger
- Sale payments and Supplier payment mirrors
- Partial and multiple Sales payments
- Cash / Bank / Card / bKash / Nagad / Other methods
- Refund and unreconciled full reversal
- Reconciliation / dispute state
- Immutable payment audit trail
- Payment method configuration
- Existing payment data import during migration

Routes: `/dashboard/payments/`, `/dashboard/payments/add/`, `/dashboard/payments/methods/`, `/dashboard/payments/<id>/`.

### Shipping / Courier
- Courier provider configuration
- Sales Order linked shipment lifecycle
- Tracking ID / courier reference / location timeline
- Parcel, weight and courier fee data
- Hand-over driven inventory issue through Sales Engine
- Delivery failure / returning / returned states
- COD expected / collected / settled / unsettled
- Short COD dispute state
- Multi-shipment courier COD settlement batches
- Payment-ledger posting and reconciliation for settled COD
- Immutable shipment event audit trail

Routes: `/dashboard/shipping/`, `/dashboard/shipping/add/`, `/dashboard/shipping/providers/`, `/dashboard/shipping/<id>/`, `/dashboard/shipping/cod-settlements/`.

## Local setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Configure MySQL 8 in `.env`:

```env
DB_NAME=techbari
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_HOST=127.0.0.1
DB_PORT=3306
```

Apply migrations and verify:

```powershell
python manage.py migrate
python manage.py check
python manage.py test catalog inventory serial_tracking purchasing customers sales payments shipping storefront
python manage.py runserver
```

Upgrading from v1.8.0 to v1.9.0 applies `shipping.0001_initial`. Existing Sales, Inventory, Payment and Purchase data are preserved. No seed command is required.

## Architecture direction

TechBari follows:

**One Product Database + One Inventory Engine + One Sales Engine + One Accounting Ledger.**

The next recommended roadmap phase is **v1.10.x — Returns / Refunds**, followed by Accounting, Reports, Marketing, Roles/Permissions, CMS, Customer Account, Integrations and Production QA.
