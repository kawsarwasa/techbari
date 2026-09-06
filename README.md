# TechBari — Django E-commerce + Admin

TechBari is now in **Catalog Database Phase 1**. The approved storefront and dashboard UI remain Django-template based, while the product catalog is persisted in **MySQL 8 / InnoDB**.

## Database-backed in this phase

- Categories: list, add, edit, delete (protected while products use them)
- Brands: list, add, edit, delete (protected while products use them)
- Products: list, add, edit, delete, archive and bulk status/delete actions
- Product variants and SKU
- Product stock quantity / low-stock threshold for the default variant
- Product images (JPG/PNG/WebP, max 2MB each, up to 8 per save)
- Product specifications
- Storefront Home / All Products / Product Details now read the catalog from Django ORM
- Existing stable storefront product IDs are preserved when demo data is seeded, so cart/wishlist localStorage remains compatible

Other business modules remain static/localStorage demos for now.

## Local setup (Windows)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Create a MySQL 8 database:

```sql
CREATE DATABASE techbari CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Set your MySQL credentials in `.env`, then run:

```powershell
python manage.py migrate
python manage.py seed_catalog
python manage.py check
python manage.py test catalog
python manage.py runserver
```

Open:
- Storefront: http://127.0.0.1:8000/
- Dashboard: http://127.0.0.1:8000/dashboard/
- Product management: http://127.0.0.1:8000/dashboard/products/

## Important

- `.env` is ignored and must not be committed.
- `media/` contains uploaded catalog images and is ignored by Git.
- Do not use SQLite for this project phase; the configured database backend is MySQL.
- Django auth/admin/session database integration is intentionally not enabled yet.

See `CATALOG_DATABASE_PHASE.md` for the migration checklist.
