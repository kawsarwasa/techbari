# TechBari — Django E-commerce + Admin

**Current version: v1.6.0**

TechBari is being converted phase-by-phase from a static Django template demo into a MySQL 8-backed commerce system. Catalog, Inventory, Serial / IMEI / Warranty, Supplier / Purchase, Customer / CRM, Sales Order and Storefront Checkout are now connected to the real business data flow.

## v1.6.0 — Storefront Checkout Backend

The public `/checkout/` page now creates real database-backed Online Sales Orders instead of showing a fake “Order Placed” animation. Checkout validates Bangladesh customer/contact and delivery data, finds or creates the CRM customer, reloads real Variant/SKU rows from MySQL, recalculates price/discount/shipping on the server and creates a Pending Sales Order through the shared Sales Engine.

Pending checkout orders reserve stock in the default online warehouse. Insufficient stock rolls the full transaction back, and repeated submission of the same signed checkout token does not reserve stock twice. The public confirmation page is protected by a signed order token.

Only Cash on Delivery is accepted in v1.6.0. bKash, Nagad and Card remain disabled until the dedicated Payment phase. The current storefront coupon definitions are server-validated for compatibility until the Promotions module replaces them with database-backed rules.

See `CHECKOUT_BACKEND_PHASE.md` for the complete flow, security rules and deployment notes.

## v1.5.0 — Customer CRM + Sales Order Engine

This phase implements the roadmap v1.4.x Customer / CRM foundation and v1.5.x Sales Order Engine together.

Customer profiles are real database records with customer number, unique phone/email handling, groups, source, address, credit/opening due, notes and active/inactive state. Retail, Wholesale and VIP groups are created by migration. Order count, completed order count, total spent, due balance, first/last purchase and repeat-customer status are derived from real sales data.

Sales Orders use real Catalog Variant/SKU rows and the shared Inventory Engine. Draft orders do not reserve stock; Pending, Confirmed and Processing orders hold warehouse stock reservations; Completed / Sold orders issue the reserved stock atomically; Cancelled orders release unsold reservations. Overselling is blocked and Sales never writes `ProductVariant.stock_quantity` directly.

See `CRM_SALES_PHASE.md`.

## v1.3.0 — Supplier + Purchase

Suppliers, Purchase Orders, partial/full receipts, supplier payments and purchase returns are database-backed. Goods receipts call the Inventory Engine with `PURCHASE_IN`; optional Serial/IMEI registration is linked to the same supplier/PO/warehouse. Purchase returns can link exact serialized units.

See `SUPPLIER_PURCHASE_PHASE.md`.

## v1.2.0 — Serial / IMEI / Warranty Tracking

Every tracked electronics unit can be linked to a Product Variant/SKU and Warehouse with unique Serial Number / IMEI 1 / IMEI 2, lifecycle status, purchase source, sales/customer references and warranty dates. Warranty/RMA claims support service, resolution and same-SKU replacement.

See `SERIAL_IMEI_WARRANTY_PHASE.md`.

## v1.1.0 — Inventory Phase 1

Inventory is warehouse/SKU based with authoritative `InventoryBalance`, immutable `StockMovement`, Stock Adjustment, Stock Transfer, reservations, low-stock rules and negative-stock protection. `ProductVariant.stock_quantity` remains a compatibility cache.

See `INVENTORY_PHASE1.md`.

## v1.0.10 — Catalog final QA

Catalog covers Categories, Brands, Products, Variants/SKUs/Barcodes, Product Images, Specifications, rich descriptions, pricing/status/SEO and database-backed Storefront catalog behavior.

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

Routes: `/dashboard/products/`, `/dashboard/categories/`, `/dashboard/brands/`, `/dashboard/variants/`, `/dashboard/product-media/`, `/dashboard/specifications/`.

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

Routes: `/dashboard/inventory/`, `/dashboard/warehouses/`, `/dashboard/stock-adjustment/`, `/dashboard/stock-transfer/`, `/dashboard/inventory/movements/`, `/dashboard/inventory/low-stock/`.

### Serial / IMEI / Warranty

- Unit-level Serial / IMEI tracking
- Warehouse and Variant/SKU linkage
- Inventory-aware lifecycle
- Immutable unit events
- Warranty / RMA claims and replacement

Routes: `/dashboard/serials/`, `/dashboard/serials/add/`, `/dashboard/warranty/`, `/dashboard/warranty/add/`.

### Supplier + Purchase

- Supplier CRUD
- Purchase Order lifecycle
- Real Variant/SKU purchase lines
- Partial/full receiving
- Inventory `PURCHASE_IN`
- Optional Serial/IMEI registration
- Supplier payments / outstanding
- Purchase returns

Routes: `/dashboard/suppliers/`, `/dashboard/suppliers/add/`, `/dashboard/purchases/`, `/dashboard/purchases/add/`, `/dashboard/purchases/<id>/`, `/dashboard/purchases/<id>/receive/`, `/dashboard/purchases/<id>/payment/`, `/dashboard/purchases/<id>/return/`.

### Customer / CRM

- Customer CRUD with history-aware delete protection
- Retail / Wholesale / VIP groups
- Customer source and contact/address details
- Credit limit / opening due / notes
- Derived order metrics, total spent and due
- Repeat-customer tracking
- Customer purchase history

Routes: `/dashboard/customers/`, `/dashboard/customers/add/`, `/dashboard/customers/<id>/`, `/dashboard/customers/groups/`.

### Sales Order

- Database-backed Sales Orders and Order Items
- Customer-linked and guest orders
- Online / Manual / POS-ready channels
- Real Catalog Variant/SKU lines
- Draft / Pending / Confirmed / Processing / Completed / Cancelled lifecycle
- Warehouse stock reservation
- Atomic deduction on Completed / Sold
- Reservation release on cancellation
- Unpaid / Partial / Paid state
- Immutable Sales Order history

Routes: `/dashboard/orders/`, `/dashboard/orders/add/`, `/dashboard/orders/<id>/`, `/dashboard/orders/<id>/confirm/`, `/dashboard/orders/<id>/process/`, `/dashboard/orders/<id>/complete/`, `/dashboard/orders/<id>/cancel/`, `/dashboard/orders/<id>/payment/`.

### Storefront Checkout

- Real GET/POST checkout
- Server-side customer and address validation
- CRM customer find/create by phone
- Server-authoritative Variant/SKU pricing
- Server-authoritative coupon and shipping calculation
- Pending Online Sales Order creation
- Inventory reservation and overselling protection
- Signed checkout idempotency
- Signed public confirmation page
- Default online warehouse availability shown on storefront
- COD-only until Payment phase

Routes: `/checkout/` and `/checkout/success/<order_number>/?token=...`.

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
python manage.py test catalog inventory serial_tracking purchasing customers sales storefront
python manage.py runserver
```

Upgrading from v1.5.0 to v1.6.0 adds no application migration. Existing business data is preserved and no seed command is required.

## Architecture direction

TechBari follows:

**One Product Database + One Inventory Engine + One Sales Engine + One Accounting Ledger.**

The next recommended roadmap phase is **v1.7.x — POS System**. POS will reuse the same Sales + Inventory foundation. Dedicated Payment, Shipping/Courier, Returns/Refunds and Accounting phases follow.
