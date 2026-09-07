# TechBari — Django E-commerce + Admin

**Current version: v1.7.0**

TechBari is being converted phase-by-phase from a static Django template demo into a MySQL 8-backed commerce system. Catalog, Inventory, Serial / IMEI / Warranty, Supplier / Purchase, Customer / CRM, Sales Order, Storefront Checkout and POS are now connected to the real business data flow.

## v1.7.0 — POS System

The `/dashboard/pos/` screen is now a real database-backed counter-sales system instead of a localStorage demo. POS searches real Product Variants by product name, SKU, barcode, brand and category; stock shown is warehouse-aware and comes from `InventoryBalance.available_quantity`.

Counter sales reuse the same Sales Order + Inventory engines used by the storefront. Walk-in sales or CRM customers are supported, fixed/percentage discounts are validated against real server prices, and held carts are stored as Draft POS Sales Orders without reserving stock. A resumed sale revalidates current stock before completion.

Cash, Card, bKash and Nagad tender snapshots are supported. Cash can calculate change; non-cash methods require a payment reference. Completing a sale atomically creates/updates the POS Sales Order, reserves stock, records payment, confirms the order and completes/sells it through the existing Inventory Engine. Printable receipts are available.

See `POS_SYSTEM_PHASE.md`.

## v1.6.0 — Storefront Checkout Backend

The public `/checkout/` page creates real database-backed Online Sales Orders. Checkout validates Bangladesh customer/contact and delivery data, finds or creates the CRM customer, reloads real Variant/SKU rows from MySQL, recalculates price/discount/shipping on the server and creates a Pending Sales Order through the shared Sales Engine.

Pending checkout orders reserve stock in the default online warehouse. Insufficient stock rolls the full transaction back, and repeated submission of the same signed checkout token does not reserve stock twice. The public confirmation page is protected by a signed order token.

See `CHECKOUT_BACKEND_PHASE.md`.

## v1.5.0 — Customer CRM + Sales Order Engine

Customer profiles are real database records with customer number, unique phone/email handling, groups, source, address, credit/opening due, notes and active/inactive state. Sales Orders use real Catalog Variant/SKU rows and the shared Inventory Engine with Draft / Pending / Confirmed / Processing / Completed / Cancelled lifecycle.

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
Database-backed Sales Orders and items, Online / Manual / POS channels, real SKU lines, lifecycle/status history, inventory reservation/deduction, payment status and customer linkage.

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
- Server-side stock and price validation
- Atomic completion through Sales + Inventory
- Printable receipt

Routes:
- `/dashboard/pos/`
- `/dashboard/pos/action/`
- `/dashboard/pos/held/<id>/`
- `/dashboard/pos/receipt/<id>/`
- `/dashboard/orders/`

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
python manage.py test catalog inventory serial_tracking purchasing customers sales storefront
python manage.py runserver
```

Upgrading from v1.6.0 to v1.7.0 applies `sales.0002_pos_tender_fields`. Existing orders and business data are preserved.

## Architecture direction

TechBari follows:

**One Product Database + One Inventory Engine + One Sales Engine + One Accounting Ledger.**

The next recommended roadmap phase is **v1.8.x — Payment System**, followed by Shipping/Courier, Returns/Refunds, Accounting, Reports, Marketing, Roles/Permissions, CMS, Customer Account, Integrations and Production QA.
