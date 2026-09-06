# TechBari — Django E-commerce + Admin

**Current version: v1.0.2**

TechBari started as a database-free Django template demo. The catalog phase is now backed by MySQL 8 while the remaining business modules continue to use the approved static/mock presentation until their database phases are implemented.

## v1.0.2 — Catalog dashboard redesign

All catalog-related dashboard pages now use a unified modern TechBari design system based on the approved visual direction. The redesign covers Products, Categories, Brands, Variants / SKUs, Product Media and Product Specifications, including their list/add/edit forms where available. Existing Django routes and MySQL-backed CRUD behavior are preserved.

## Current database-backed catalog

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

Dashboard catalog routes include:

- `/dashboard/products/`
- `/dashboard/categories/`
- `/dashboard/brands/`
- `/dashboard/variants/`
- `/dashboard/product-media/`
- `/dashboard/specifications/`

See `CATALOG_DATABASE_PHASE.md` for complete CRUD coverage.

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

Apply migrations and seed the demo catalog:

```powershell
python manage.py migrate
python manage.py seed_catalog
python manage.py check
python manage.py test catalog
python manage.py runserver
```

Open:

- Storefront: `http://127.0.0.1:8000/`
- Dashboard: `http://127.0.0.1:8000/dashboard/`
- Catalog Products: `http://127.0.0.1:8000/dashboard/products/`

## Image rules

Catalog image uploads support JPG, PNG and WebP. Product/category/brand images are limited to 2MB each. A product supports up to 8 managed images.

## Seed safety

A normal `python manage.py seed_catalog` preserves existing product edits and existing variants/images/specifications. Use `--refresh-demo` only when you intentionally want to overwrite the seeded demo catalog, or `--reset` for a destructive full reseed.

## Architecture direction

TechBari follows the long-term principle:

**One Product Database + One Inventory Engine + One Sales Engine + One Accounting Ledger.**

The next major database phase should introduce warehouse/inventory balances and stock movements so catalog variant stock is no longer the final inventory source of truth.
