# TechBari Catalog Database Phase

The catalog is MySQL-backed and the dashboard exposes CRUD workflows for the catalog entities.

## Database entities

- Category
- Brand
- Product
- ProductVariant
- ProductImage
- ProductSpecification

## CRUD coverage

### Category
- List
- Create
- Edit
- Delete when unused
- Parent category
- Circular-parent protection
- Active/inactive
- Sort order
- Image upload (JPG/PNG/WebP, max 2MB)
- Replaced/deleted upload cleanup

### Brand
- List
- Create
- Edit
- Delete when unused
- Featured flag
- Active/inactive
- Sort order
- Logo upload (JPG/PNG/WebP, max 2MB)
- Replaced/deleted upload cleanup

### Product
- List/search/filter/sort
- Create
- Edit
- Delete
- Archive
- Bulk activate/draft/archive/delete
- Category and brand
- Regular price / sale price
- Default SKU, barcode, stock and low-stock alert
- Status, featured, new arrival
- Shipping/warranty
- SEO title, meta description and slug
- Initial multi-image upload
- Initial specification editing
- New products start with no fake/demo specifications
- Safe rich product description plus plain short summary

### Variants / SKUs
Route: `/dashboard/variants/`

- List/filter by product
- Create
- Edit
- Delete (the last variant of a product is protected)
- SKU
- Unique optional barcode
- Variant symbol/name
- Regular-price override
- Selling-price override
- Stock quantity
- Low-stock alert
- Active/inactive
- Default variant management
- Storefront uses active database variants for price, stock, SKU and barcode
- Cart/checkout use the selected database variant rather than hardcoded color names

### Product Media
Route: `/dashboard/product-media/`

- List/filter by product
- Upload
- Replace
- Edit alt text
- Edit sort order
- Set Primary
- Set Detail
- Delete
- Maximum 8 images per product
- JPG/PNG/WebP, max 2MB each
- Primary image reassignment after deletion
- Uploaded file cleanup on replacement, image deletion, product deletion and bulk product deletion

### Specifications
Route: `/dashboard/specifications/`

- List/filter by product
- Create
- Edit
- Delete
- Sort order
- Case-insensitive duplicate-name validation per product
- Add Product starts blank and saves only user-entered specifications

## Storefront catalog QA

The storefront catalog is backed by active database products/categories/brands. Product detail renders the dedicated short description in the summary and sanitized rich HTML in the Description tab. Heading 2/3, paragraphs, bold, italic, underline, ordered/unordered lists and blockquotes are retained by the allow-list sanitizer. Executable/embed content and attributes are removed.

The All Products page supports client-side catalog search plus category, brand, price, availability and sort controls. Product detail variant selection updates displayed price, regular price, stock, SKU and barcode, and selected variant data is carried into cart/checkout calculations.

## Automated QA

Run:

```powershell
python manage.py check
python manage.py test catalog
```

The catalog test suite covers product form/default-variant behavior, SKU/barcode uniqueness, variant validation, category circular-parent protection, brand flags, image validation, rich-text sanitization, storefront serialization, active catalog visibility, product create/edit/archive/delete, protected category/brand deletion, last-variant protection/default reassignment, primary-image reassignment, storefront rich-description/specification rendering and uploaded media cleanup after product deletion.

## Migration

No new database migration is required for v1.0.10. Migration `catalog.0002_catalog_crud_expansion` remains the latest catalog schema migration; it adds variant barcodes, catalog indexes and changes `Product.slug` to 255 characters to avoid the MySQL unique-character-field warning.

## Seed behavior

A normal `python manage.py seed_catalog` preserves existing products and their variants/images/specifications. Use `python manage.py seed_catalog --refresh-demo` only when you intentionally want to overwrite the demo catalog, or `--reset` for a destructive full reseed.

## Architecture note

Variant stock is still the catalog-phase stock field. The future Inventory phase will replace it as the authoritative inventory source with warehouse balances and stock movements. Catalog CRUD remains the source of product identity, SKU/barcode and presentation data.
