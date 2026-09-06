# TechBari — Django Static E-commerce + Admin Demo

TechBari uses reusable Django templates and Python mock-data modules **without creating or using a database**. Browser interactions keep their demo changes in localStorage. The approved CSS, images and responsive layouts are preserved.

Read [ARCHITECTURE.md](ARCHITECTURE.md) for the template/data structure and validation commands, and [REFACTOR_REPORT.md](REFACTOR_REPORT.md) for the full file and route inventory.

## Included
- Storefront: Home, All Products, Product Details, Cart, Checkout, Wishlist, Track Order, Login/Register, Contact
- Backoffice: 46 dashboard pages including Dashboard, Orders, Products CRUD demo, Customers, POS, Purchases, Inventory, Accounts, Reports, Shipping, Returns/Warranty, Users, Settings, etc.
- Responsive frontend/admin CSS and local image assets
- Static CRUD/POS interactions preserved through JavaScript/localStorage
- TechBari branding applied to text, localStorage/export naming, titles, footer, and navigation
- No database migrations required in this phase

## Run locally
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
# source .venv/bin/activate

pip install -r requirements.txt
python manage.py runserver
```

Open:
- Storefront: http://127.0.0.1:8000/
- Dashboard: http://127.0.0.1:8000/dashboard/

**Do not run `migrate` for this static-only version.** `DATABASES` intentionally uses Django's dummy backend, so no SQLite/MySQL/PostgreSQL database is created.

## Static data behavior
- Storefront cart, coupon, wishlist, hero slider, product zoom and checkout interactions use JavaScript/localStorage.
- Admin CRUD/POS demo state uses localStorage; it does not persist to a server database.
- Clearing browser localStorage resets the demo state.

## Shared hosting note
This version is intentionally WSGI/shared-hosting friendly. When you later enable real data, switch `DATABASES` to MySQL 8/InnoDB, add Django models/migrations, and replace localStorage CRUD with server views/forms/API endpoints.

## Project structure
```
techbari_django/
├── manage.py
├── techbari/
├── storefront/
├── backoffice/
├── templates/
│   ├── storefront/
│   └── backoffice/
└── static/
    ├── store/
    └── admin/
```
