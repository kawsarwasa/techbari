# Catalog Database Phase 1

The runtime catalog source is now Django ORM/MySQL instead of the static product list.

## Models
- Category
- Brand
- Product
- ProductVariant
- ProductImage
- ProductSpecification

## Real CRUD
- Product list/add/edit/delete/archive/bulk actions
- Category list/add/edit/delete
- Brand list/add/edit/delete

## First local installation

```powershell
git pull origin main
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

If `.env` already exists, do not overwrite it; only add/update the DB variables.

Create MySQL database:

```sql
CREATE DATABASE techbari CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Then:

```powershell
python manage.py migrate
python manage.py seed_catalog
python manage.py check
python manage.py test catalog
python manage.py runserver
```

`python manage.py seed_catalog` is idempotent for the original demo products and preserves stable public IDs used by browser cart/wishlist data.

`python manage.py seed_catalog --reset` deletes and reseeds the catalog. Do not use `--reset` after entering real data unless you intentionally want to remove it.

## Manual QA
- `/`
- `/products/`
- product detail
- `/dashboard/products/`
- add/edit/delete/archive product
- category CRUD
- brand CRUD
- <=2MB image accepted
- >2MB image rejected
- desktop/mobile visual checks
