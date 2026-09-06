# TechBari Architecture

TechBari is being converted in phases from the approved static Django demo into a database-backed commerce platform. The visual templates and CSS remain the presentation layer while business modules are moved to MySQL one domain at a time.

## Current state

### Database-backed now

The catalog domain is backed by MySQL 8 / Django ORM:

- `Category`
- `Brand`
- `Product`
- `ProductVariant`
- `ProductImage`
- `ProductSpecification`

The storefront reads catalog products, categories and brands from the ORM. Dashboard catalog CRUD writes to the same catalog database.

### Still static/mock for later phases

Orders, customers, POS sale completion, purchasing, warehouse/inventory engine, accounting, shipping, returns, users/permissions, marketing and reporting still retain their approved mock/static presentation until their database phases are implemented.

## Catalog source of truth

`catalog/` owns catalog persistence. `storefront/` consumes catalog presentation serializers. `backoffice/catalog_views.py` contains database-backed dashboard workflows.

Catalog dashboard routes:

```text
/dashboard/products/
/dashboard/products/add/
/dashboard/products/edit/
/dashboard/categories/
/dashboard/brands/
/dashboard/variants/
/dashboard/product-media/
/dashboard/specifications/
```

## Product identity and variants

A `Product` contains shared merchandising data such as category, brand, descriptions, product-level regular/sale price, publishing status and SEO.

A `ProductVariant` represents a sellable SKU. Each variant may have a unique SKU, unique optional barcode, variant name/symbol, regular-price override, selling-price override, catalog-phase stock quantity, low-stock alert, active flag and default flag.

Only one default variant is maintained per product by the dashboard workflows. The default variant supplies the product card/list SKU and barcode.

## Images

`ProductImage` supports Primary, Gallery and Detail roles. The media manager can add, replace, edit, reorder by sort value, set Primary/Detail and delete images. New uploads are limited to JPG/PNG/WebP and 2MB per image, with a maximum of eight images per product.

## Specifications

`ProductSpecification` stores structured name/value rows with display order. Specification names are unique per product and rendered on product-detail pages.

## Inventory boundary

`ProductVariant.stock_quantity` is transitional for the catalog phase. The planned Inventory phase will introduce warehouses, inventory balances and append-only stock movements. At that point inventory will become the source of truth instead of catalog stock fields.

The long-term platform rule remains:

**One Product Database + One Inventory Engine + One Sales Engine + One Accounting Ledger.**

## Database configuration

`techbari/settings.py` loads MySQL connection details from `.env`.

```env
DB_NAME=techbari
DB_USER=root
DB_PASSWORD=...
DB_HOST=127.0.0.1
DB_PORT=3306
```

Apply migrations after pulling database changes:

```powershell
python manage.py migrate
python manage.py check
python manage.py test catalog
```

`python manage.py seed_catalog` preserves existing catalog CRUD edits by default. Use `--refresh-demo` only when intentionally replacing seeded demo data.

## Important legacy note

`scripts/validate_static.py` belongs to the original database-free conversion and contains assertions that deliberately reject database usage. It is not the validator for the current database-backed phase. Use Django checks/tests and JavaScript syntax checks until that legacy validator is replaced.
