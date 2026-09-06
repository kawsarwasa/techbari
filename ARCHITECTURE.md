TechBari uses Django template inheritance and Python fixtures while remaining entirely database-free. The approved CSS, image assets, DOM wrappers, icons and responsive rules are preserved. The existing browser cart, wishlist, CRUD and POS behavior remains vanilla JavaScript.

The application is organized as follows:

```text
techbari/
    settings.py             Dummy database backend; no auth or session apps
    urls.py                 Namespaced application routes and error handlers
    views.py                Branded error responses
storefront/
    urls.py                 Named storefront routes and legacy redirects
    views.py                Static page and product-detail views
    context.py              Catalog presentation and browser JSON payloads
    mock_data.py            Catalog, images, specifications, categories, brands,
                            gallery variants, reviews, coupons, cart and tracking
    templatetags/demo.py     Display helpers shared by both applications
backoffice/
    urls.py                 Routes generated from the explicit page registry
    views.py                Static dashboard page and detail views
    page_registry.py        Route names, paths, templates and sidebar selection
    context.py              View context and browser JSON payloads
    mock_data.py            Business collections, POS catalog and statistics
    page_data.py            Reports, dashboard summaries, form defaults/options,
                            campaigns, notifications and other static page data
    table_config.py         Table field definitions shared with JavaScript
templates/
    404.html
    500.html
    storefront/
        base.html
        includes/           Header, footer, responsive category nav, messages
        components/         Product cards, breadcrumbs, pagination, empty states
        pages/              Nine approved storefront templates
    backoffice/
        base.html
        includes/           Sidebar, topbar, footer, messages, breadcrumb content
        components/         Statistics, rows, badges, pagination, form actions,
                            modal, reports, campaigns, notifications, alerts, icons
        pages/              Dashboard and grouped business pages
static/
    store/                  Original storefront CSS, JavaScript and images
    admin/                  Original dashboard asset namespace retained
scripts/
    validate_static.py      Database-free route, template, asset and syntax audit
    validate_interactions.cjs  Optional DOM interaction checks
```

Each view obtains presentation data from its context module. Templates use fields such as `product.name`, `product.price`, `order.order_no` and `customer.name`. The future MySQL/ORM phase can replace the fixture lookup inside these context/view boundaries while retaining the templates and CSS. No future database configuration is enabled now.

JavaScript receives data using Django's `json_script`, with URLs produced by `reverse()` and image URLs produced by `static()`. Storefront cards, including the different approved wishlist layout, use one Django component. Hidden `<template>` elements let JavaScript reuse that component when filtering or updating localStorage lists. No HTML is stored in the product or business fixture dictionaries; icon markup stays in template files.

The browser storage keys remain `nu_cart`, `nu_wish`, `nu_coupon` and `techbari_admin_<entity>` so existing demo state survives the conversion. The two conflicting dashboard product seeds were consolidated using the original custom product page's ten-record seed. Deleting every product now keeps the catalog empty after reload. Repeated storefront listing cards use their real catalog IDs, so their cart and wishlist buttons work.

Canonical navigation uses namespaced Django URLs. Legacy `.html` URLs redirect to the corresponding canonical route while preserving query parameters. Product details support both catalog slug and stable demo ID and return HTTP 404 for invalid products. `/register/` opens the existing register panel in the approved login layout. Dashboard edit forms continue using `?id=...` for localStorage records.

All database-backed functionality remains absent: no models, migrations, database files, ORM queries, authentication views, database sessions, admin integration, or database connection was added. The two existing empty `models.py` placeholders are unchanged. Do not run `migrate` or `makemigrations` during this phase.

To run the project on Windows:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py runserver
```

To validate without creating a database:

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe scripts\validate_static.py
.\.venv\Scripts\python.exe -m compileall -q techbari storefront backoffice scripts
node --check static\store\js\app.js
node --check static\admin\js\admin.js
node --check static\admin\js\product-crud.js
```

The optional interaction test uses jsdom installed outside the project. It is a development validation tool; there is no Node frontend, package manifest, build step or added production dependency:

```powershell
npm install --prefix "$env:TEMP\techbari-validation" jsdom --no-audit --no-fund
.\.venv\Scripts\python.exe scripts\validate_static.py --export-dir "$env:TEMP\techbari-validation"
node scripts\validate_interactions.cjs "$env:TEMP\techbari-validation\node_modules\jsdom" "$env:TEMP\techbari-validation\pages.json"
```

The static validator prevents database connections while rendering 89 page/detail URLs, follows navigation targets, checks legacy redirects and branded errors, compiles every template, parses Python sources, checks local assets and verifies declared pixel font sizes are at least 13px. The interaction checks initialize JavaScript on all exported pages and exercise slider, search, wishlist, cart, coupons, delivery charges, gallery, frontend validation, CRUD and POS behavior.

The design comparison used the original project backup and compared rendered DOM element structure, CSS classes and inline styles after JavaScript initialization. 54 of 55 original pages match exactly. The product listing's repeated cards now show the correct saved wishlist state because their invalid synthetic IDs were removed. All 64 CSS and image assets are byte-for-byte unchanged. No browser was connected, so screenshots, computed font sizes and physical viewport/overflow checks could not be verified. DOM tests do not substitute for those visual checks.

The original demo limitations remain: checkout/payment/login/register do not contact a real service; several filter, report/export and toolbar controls are presentation-only; dashboard metrics are fixed snapshots. Browser edits do not modify Python fixtures or synchronize with the storefront, other browsers, or server-rendered dashboard detail snapshots. Direct detail URLs resolve Python seed records. The View buttons in browser CRUD tables populate the marked identity and amount fields from localStorage, including newly created browser-only records; ancillary timeline and analytics panels remain static demo snapshots. The original external Google Fonts and tracking-page image dependencies remain. Branded error handlers display with `DEBUG=False`; Django displays its development diagnostics with `DEBUG=True`.

See [REFACTOR_REPORT.md](REFACTOR_REPORT.md) for the complete route and file-change inventory.
