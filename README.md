# TechBari — Django E-commerce + Admin

**Current version: v1.5.0**

TechBari is being converted phase-by-phase from a static Django template demo into a MySQL 8-backed commerce system. Catalog, Inventory, Serial / IMEI / Warranty, Supplier / Purchase, Customer / CRM and Sales Order are now database-backed; remaining business modules keep the approved presentation until their own database phases are implemented.

## v1.5.0 — Customer CRM + Sales Order Engine

This phase implements the roadmap v1.4.x Customer / CRM foundation and v1.5.x Sales Order Engine together.

Customer profiles are now real database records with customer number, unique phone/email handling, groups, source, address, credit/opening due, notes and active/inactive state. Retail, Wholesale and VIP groups are created by migration. Order count, completed order count, total spent, due balance, first/last purchase and repeat-customer status are derived from real sales data instead of being typed manually.

Sales Orders use real Catalog Variant/SKU rows and the shared Inventory Engine. Draft orders do not reserve stock; Pending, Confirmed and Processing orders hold warehouse stock reservations; Completed / Sold orders issue the reserved stock atomically; Cancelled orders release unsold reservations. Overselling is blocked and Sales never writes `ProductVariant.stock_quantity` directly.

Order-level payment state supports Unpaid / Partial / Paid, and immutable order history records creation, updates, status changes, payment changes and stock reservation events.

See `CRM_SALES_PHASE.md` for schema, lifecycle, routes, inventory behavior and deployment notes.

## v1.3.0 — Supplier + Purchase

This phase adds the procurement engine. Suppliers are real database records with contact details, payment terms, credit/opening balances, active status and live purchase/outstanding calculations. Purchase Orders use real Catalog Variant/SKU rows, cost snapshots and Draft → Ordered → Partially Received → Received / Cancelled lifecycle.

Goods receipts are separately audited and support partial receiving. Receipt posting calls the shared Inventory Engine with `PURCHASE_IN` movements; it never writes catalog stock directly. A receipt may also register Serial/IMEI units against the same supplier, PO, warehouse, purchase cost and received date. Invalid or duplicate serialized identifiers roll the full receipt back atomically.

Supplier payments are stored against the purchase with method/reference/date and cannot exceed outstanding. Purchase returns validate net received quantity, reduce stock, reduce supplier outstanding and can link exact Serial/IMEI units. Serialized units returned to a supplier use the new `Returned to Supplier` lifecycle state.

See `SUPPLIER_PURCHASE_PHASE.md` for schema, workflows, routes and safety rules.

## v1.2.0 — Serial / IMEI / Warranty Tracking

Every tracked electronics unit can be linked to a Product Variant/SKU and Warehouse with unique Serial Number / IMEI 1 / IMEI 2, lifecycle status, purchase source, sales/customer references and warranty dates. Unit status/warehouse changes integrate with Inventory and immutable event history. Warranty/RMA claims support service, resolution and same-SKU replacement.

See `SERIAL_IMEI_WARRANTY_PHASE.md`.

## v1.1.0 — Inventory Phase 1

Inventory is warehouse/SKU based with authoritative `InventoryBalance`, immutable `StockMovement`, Stock Adjustment, Stock Transfer, reservations, low-stock rules and negative-stock protection. Existing catalog quantity is imported into the default warehouse as opening stock; `ProductVariant.stock_quantity` remains only a compatibility cache.

See `INVENTORY_PHASE1.md`.

## v1.0.10 — Catalog final QA

Catalog covers Categories, Brands, Products, Variants/SKUs/Barcodes, managed Product Images, Specifications, rich descriptions, pricing/status/SEO and database-backed Storefront variant/stock/filter behavior.

See `CATALOG_DATABASE_PHASE.md`.

## Current database-backed modules

### Catalog

- Categories / Brands
- Products
- Variants / SKUs / Barcodes
- Variant price overrides
- Product images/media
- Product specifications
- Rich description
- Product pricing / status / SEO
- Storefront catalog integration

Routes:

- `/dashboard/products/`
- `/dashboard/categories/`
- `/dashboard/brands/`
- `/dashboard/variants/`
- `/dashboard/product-media/`
- `/dashboard/specifications/`

### Inventory

- Warehouses
- Warehouse/SKU balances
- On-hand / reserved / available
- Stock movement ledger
- Stock adjustments
- Multi-SKU transfers
- Reservations / releases
- Low-stock reporting
- Negative-stock protection

Routes:

- `/dashboard/inventory/`
- `/dashboard/warehouses/`
- `/dashboard/stock-adjustment/`
- `/dashboard/stock-transfer/`
- `/dashboard/inventory/movements/`
- `/dashboard/inventory/low-stock/`

### Serial / IMEI / Warranty

- Unit-level Serial / IMEI tracking
- Warehouse and Variant/SKU linkage
- Available / Reserved / Sold / Returned / Damaged / Warranty Service / Scrapped / Returned to Supplier states
- Inventory-aware unit lifecycle
- Immutable unit events
- Warranty / RMA claims and replacement

Routes:

- `/dashboard/serials/`
- `/dashboard/serials/add/`
- `/dashboard/warranty/`
- `/dashboard/warranty/add/`

### Supplier + Purchase

- Supplier CRUD with delete protection
- Payment terms / credit / opening balance
- Purchase Order lifecycle
- Real Variant/SKU purchase lines
- Partial/full goods receiving
- Inventory `PURCHASE_IN` integration
- Optional Serial/IMEI registration during receipt
- Supplier payments / outstanding
- Purchase returns / Inventory out
- Serialized supplier-return tracking
- Purchase activity/detail audit view

Routes:

- `/dashboard/suppliers/`
- `/dashboard/suppliers/add/`
- `/dashboard/purchases/`
- `/dashboard/purchases/add/`
- `/dashboard/purchases/<id>/`
- `/dashboard/purchases/<id>/receive/`
- `/dashboard/purchases/<id>/payment/`
- `/dashboard/purchases/<id>/return/`

### Customer / CRM

- Customer CRUD with history-aware delete protection
- Retail / Wholesale / VIP groups
- Customer source and contact/address details
- Credit limit / opening due / notes
- Derived order count and completed-order count
- Derived total spent and due balance
- First / last purchase
- Repeat-customer tracking after 2+ completed orders
- Customer purchase history

Routes:

- `/dashboard/customers/`
- `/dashboard/customers/add/`
- `/dashboard/customers/<id>/`
- `/dashboard/customers/groups/`

### Sales Order

- Real database-backed Sales Orders and Order Items
- Customer-linked and guest orders
- Online / Manual / POS-ready channels
- Real Catalog Variant/SKU order lines
- Draft / Pending / Confirmed / Processing / Completed / Cancelled lifecycle
- Warehouse stock reservation
- Atomic inventory deduction on Completed / Sold
- Reservation release on cancellation
- Unpaid / Partial / Paid order-level payment state
- Immutable Sales Order history
- Customer CRM metrics derived from Sales Orders

Routes:

- `/dashboard/orders/`
- `/dashboard/orders/add/`
- `/dashboard/orders/<id>/`
- `/dashboard/orders/<id>/confirm/`
- `/dashboard/orders/<id>/process/`
- `/dashboard/orders/<id>/complete/`
- `/dashboard/orders/<id>/cancel/`
- `/dashboard/orders/<id>/payment/`

## Local setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Create/configure MySQL 8 database `techbari` in `.env`:

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
python manage.py test catalog inventory serial_tracking purchasing customers sales
python manage.py runserver
```

Upgrading from v1.3.0 creates the Customer / CRM and Sales Order schemas. Existing Catalog, Inventory, Serial/IMEI, Warranty, Supplier and Purchase data are preserved. No seed command is required for CRM; the standard Customer Groups are created by migration.

For a fresh demo database, `python manage.py seed_catalog` remains optional after migrations.

## Architecture direction

TechBari follows:

**One Product Database + One Inventory Engine + One Sales Engine + One Accounting Ledger.**

The next recommended database phase is **Storefront Checkout → Sales Order integration (v1.6.x)**. POS can then reuse the same Sales + Inventory foundation, followed by dedicated Payment, Shipping, Returns / Refunds and Accounting phases.
