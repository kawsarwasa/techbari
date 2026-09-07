# TechBari — Django E-commerce + Admin

**Current version: v1.0.10**

TechBari started as a database-free Django template demo. The catalog phase is now backed by MySQL 8 while the remaining business modules continue to use the approved static/mock presentation until their database phases are implemented.

## v1.0.10 — Catalog final QA

The catalog phase received a final QA pass before Inventory development. New products no longer start with fake Bluetooth/headphone specifications, storefront rich descriptions now preserve safe Heading 2/3, lists, quotes, bold, italic and underline markup, and the product summary uses the dedicated short description. Storefront variant selection now follows database-backed variant price, regular price, stock, SKU and barcode values; cart/checkout use actual variants instead of hardcoded Black/White options; product listing category/brand/price/availability/search/sort controls are wired to catalog data. Catalog media cleanup hooks remove replaced/deleted uploaded files, including cascade product deletion. The catalog automated test suite now covers the principal CRUD, validation, storefront serialization/rendering and media cleanup paths.

## v1.0.9 — Self-contained product description editor

The Jodit experiment has been removed from Add Product and Edit Product. Both forms now use the same local, dependency-free editor component with Paragraph, Heading 2, Heading 3, Quote, Bold, Italic, Underline, bulleted list and numbered list controls. The toolbar is isolated from dashboard button styles so active formatting does not inherit unrelated red/button states. The editor stores sanitized HTML in the existing Django `description` field and requires no CDN or external editor script.

## v1.0.8 — Jodit experiment

Jodit was tested for the product description field but was removed in v1.0.9 because its toolbar behavior conflicted with the existing dashboard styling/runtime in the local project.

## v1.0.7 — Native editable description surface

The previous custom editor improved loading and browser-cache handling and provided the basis for the self-contained v1.0.9 implementation.

## v1.0.5 — Working rich product description editor

The initial custom Add/Edit Product Full Description toolbar added paragraph/heading styles, bold, italic, underline and bulleted lists with synchronized Django description values and sanitized storefront presentation.

## v1.0.4 — Unified Add/Edit Product design

The Add Product page uses the Edit Product page as the visual and structural standard. Both product forms share the same two-column layout, card hierarchy, field placement, image/status/shipping/SEO sections and responsive behavior. Product-form buttons also include subtle slide/shine hover animation and smoother toggle motion, while respecting reduced-motion preferences.

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
