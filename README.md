# TechBari — Django E-commerce + Admin

**Current version: v1.3.0**

TechBari is being converted phase-by-phase from a static Django template demo into a MySQL 8-backed commerce system. Catalog, Inventory, Serial / IMEI / Warranty and Supplier / Purchase are database-backed; remaining business modules keep the approved presentation until their own database phases are implemented.

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
python manage.py test catalog inventory serial_tracking purchasing
python manage.py runserver
```

Upgrading from v1.2.0 only creates the purchasing schema and the Serialized Unit supplier-return status migration. Existing Catalog, Inventory, Serial/IMEI and Warranty data are preserved. Do not reseed just to initialize purchasing.

For a fresh demo database, `python manage.py seed_catalog` remains optional after migrations.

## Architecture direction

TechBari follows:

**One Product Database + One Inventory Engine + One Sales Engine + One Accounting Ledger.**

The next recommended database phase is **Customer / CRM**, followed by Sales Order, Checkout and POS.
