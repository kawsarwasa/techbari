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
- Active/inactive
- Sort order
- Image upload (JPG/PNG/WebP, max 2MB)

### Brand
- List
- Create
- Edit
- Delete when unused
- Featured flag
- Active/inactive
- Sort order
- Logo upload (JPG/PNG/WebP, max 2MB)

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

### Specifications
Route: `/dashboard/specifications/`

- List/filter by product
- Create
- Edit
- Delete
- Sort order
- Case-insensitive duplicate-name validation per product

## Migration

After pulling this phase:

```powershell
python manage.py migrate
python manage.py check
python manage.py test catalog
```

Migration `catalog.0002_catalog_crud_expansion` adds variant barcodes, catalog indexes and changes `Product.slug` to 255 characters to avoid the MySQL unique-character-field warning.

## Seed behavior

A normal `python manage.py seed_catalog` preserves existing products and their variants/images/specifications. Use `python manage.py seed_catalog --refresh-demo` only when you intentionally want to overwrite the demo catalog, or `--reset` for a destructive full reseed.

## Architecture note

Variant stock is still the catalog-phase stock field. The future Inventory phase will replace it as the authoritative inventory source with warehouse balances and stock movements. Catalog CRUD remains the source of product identity, SKU/barcode and presentation data.
