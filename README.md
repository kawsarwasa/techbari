# TechBari — Django E-commerce + Admin

**Current version: v1.1.0**

TechBari is being converted phase-by-phase from a static Django template demo into a MySQL 8-backed commerce system. Catalog and Inventory Phase 1 are database-backed; the remaining business modules continue to use the approved presentation until their own database phases are implemented.

## v1.1.0 — Inventory Phase 1

Inventory Phase 1 adds the shared stock engine that future Purchase, Online Order, POS and Return modules will call. It introduces Warehouse, InventoryBalance, immutable StockMovement, StockAdjustment, StockTransfer and StockTransferItem models; atomic service-layer stock operations; reservations; negative-stock protection; low-stock thresholds/reports; and database-backed warehouse/adjustment/transfer/movement dashboard pages.

Existing catalog stock is preserved by migration `inventory.0002_import_catalog_opening_stock`, which creates the default `MAIN` warehouse and imports every existing variant quantity as opening stock. `ProductVariant.stock_quantity` remains only as a backward-compatible available-stock cache; warehouse balances are authoritative. Legacy catalog stock writes are reconciled through inventory ledger movements instead of bypassing Inventory.

See `INVENTORY_PHASE1.md` for the full schema, stock flow, routes and service API.

## v1.0.10 — Catalog final QA

The catalog phase received a final QA pass before Inventory development. New products no longer start with fake Bluetooth/headphone specifications, storefront rich descriptions preserve safe Heading 2/3, lists, quotes, bold, italic and underline markup, and the product summary uses the dedicated short description. Storefront variant selection follows database-backed variant price, regular price, stock, SKU and barcode values; cart/checkout use actual variants instead of hardcoded Black/White options; product listing category/brand/price/availability/search/sort controls are wired to catalog data. Catalog media cleanup hooks remove replaced/deleted uploaded files, including cascade product deletion. The catalog automated test suite covers the principal CRUD, validation, storefront serialization/rendering and media cleanup paths.

## v1.0.9 — Self-contained product description editor

The Jodit experiment was removed from Add Product and Edit Product. Both forms use the same local, dependency-free editor component with Paragraph, Heading 2, Heading 3, Quote, Bold, Italic, Underline, bulleted list and numbered list controls. The toolbar is isolated from dashboard button styles and stores sanitized HTML in the existing Django `description` field.

## Current database-backed modules

### Catalog

- Categories
- Brands
- Products
- Variants / SKUs
- Barcodes
- Variant-level price overrides
- Product images/media
- Product specifications
- Product pricing and sale pricing
- Draft / Active / Archived status
- Featured / New Arrival
- SEO title, description and slug

Catalog routes:

- `/dashboard/products/`
- `/dashboard/categories/`
- `/dashboard/brands/`
- `/dashboard/variants/`
- `/dashboard/product-media/`
- `/dashboard/specifications/`

### Inventory Phase 1

- Warehouses
- Warehouse/SKU balances
- On-hand / reserved / available stock
- Stock movement ledger
- Stock adjustments
- Multi-SKU stock transfers
- Reservations and releases
- Negative-stock protection
- Low-stock thresholds and reports
- Opening-stock migration from existing catalog data

Inventory routes:

- `/dashboard/inventory/`
- `/dashboard/warehouses/`
- `/dashboard/warehouses/add/`
- `/dashboard/stock-adjustment/`
- `/dashboard/stock-transfer/`
- `/dashboard/inventory/movements/`
- `/dashboard/inventory/low-stock/`

See `CATALOG_DATABASE_PHASE.md` and `INVENTORY_PHASE1.md` for detailed coverage.

## Local setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Create a MySQL 8 database named `techbari`, then configure `.env`:

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
python manage.py test catalog inventory
python manage.py runserver
```

For an existing v1.0.10 database, `python manage.py migrate` automatically imports current variant stock into the default warehouse. Do not reseed just to initialize Inventory.

For a fresh demo database, you may run `python manage.py seed_catalog` after migrations. New variants automatically receive inventory balances.

Open:

- Storefront: `http://127.0.0.1:8000/`
- Dashboard: `http://127.0.0.1:8000/dashboard/`
- Inventory: `http://127.0.0.1:8000/dashboard/inventory/`

## Image rules

Catalog image uploads support JPG, PNG and WebP. Product/category/brand images are limited to 2MB each. A product supports up to 8 managed images.

## Seed safety

A normal `python manage.py seed_catalog` preserves existing product edits and existing variants/images/specifications. Use `--refresh-demo` only when you intentionally want to overwrite the seeded demo catalog, or `--reset` for a destructive full reseed.

## Architecture direction

TechBari follows the long-term principle:

**One Product Database + One Inventory Engine + One Sales Engine + One Accounting Ledger.**

The next recommended database phase is Serial / IMEI / Warranty tracking, followed by Purchase/Supplier, Customer/CRM and the shared Sales Order engine.
