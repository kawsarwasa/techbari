# TechBari — Django E-commerce + Admin

**Current version: v1.0.7**

TechBari started as a database-free Django template demo. The catalog phase is now backed by MySQL 8 while the remaining business modules continue to use the approved static/mock presentation until their database phases are implemented.

## v1.0.5 — Working rich product description editor

The Add Product and Edit Product Full Description toolbar is now interactive. Paragraph/heading styles, bold, italic, underline and bulleted lists work in a contenteditable editor, formatting is synchronized back to the Django description field before submit, and stored rich description output is sanitized before storefront presentation.

## v1.0.6 — Reliable rich editor loading

## v1.0.7 — Native editable description surface

The editor no longer inherits textarea resizing behavior, has a text cursor, and uses a new asset URL so browsers load the repaired editor immediately.

The description editor now initializes whether the page is freshly loaded, restored from browser cache, or its dashboard context is incomplete. Its stylesheet and script use a new versioned URL so browsers fetch the working editor instead of an older cached script.

## v1.0.4 — Unified Add/Edit Product design

The Add Product page now uses the Edit Product page as the visual and structural standard. Both product forms share the same two-column layout, card hierarchy, field placement, image/status/shipping/SEO sections and responsive behavior. Product-form buttons also include a subtle slide/shine hover animation and smoother toggle motion, while respecting reduced-motion preferences.

## v1.0.3 — Add Product redesign

The Add Product dashboard page was rebuilt around the approved TechBari catalog direction while preserving the MySQL-backed form fields and validation.

## v1.0.2 — Catalog dashboard redesign

All catalog-related dashboard pages use a unified modern TechBari design system. The redesign covers Products, Categories, Brands, Variants / SKUs, Product Media and Product Specifications, including their list/add/edit forms where available. Existing Django routes and MySQL-backed CRUD behavior are preserved.

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
