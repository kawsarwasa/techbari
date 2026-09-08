# TechBari v2.6.0 — CMS / Store Settings

v2.6.0 replaces the old static dashboard Settings demo and hardcoded storefront business content with a database-backed CMS / Store Settings layer.

## Scope

The phase covers the roadmap items:

- Shop information
- Logo and favicon
- Contact details and social links
- Hero banners
- Homepage sections
- Delivery settings
- Terms & Conditions
- Privacy Policy
- Return & Refund Policy
- Shipping Policy
- Storefront SEO

## Data model

### `StoreSettings`

A singleton row (`pk=1`) stores business-wide configuration:

- store name and tagline
- support phone, hours, support/business email and address
- logo and favicon
- Facebook, YouTube, Instagram, TikTok and WhatsApp values
- top-bar messages and footer copy
- currency code/symbol
- inside/outside Dhaka delivery charges
- free-delivery threshold
- inside/outside estimated delivery days
- COD and reserved guest-checkout switches
- default and homepage SEO metadata

Uploaded branding files are stored under `media/cms/branding/`.

### `HeroBanner`

Hero banners support:

- eyebrow, headline, description and CTA
- uploaded image or existing static fallback image
- alt text
- active/inactive state
- sort order
- optional start/end schedule

Uploaded hero images are stored under `media/cms/hero/`.

Only active banners inside their schedule are exposed to the storefront. Banner headline/description text is escaped before the intentional `<br>` conversion used by the existing slider script.

### `HomeSection`

The four primary homepage blocks are database ordered and individually enabled/disabled:

1. Hero banners
2. Shop by Category
3. Featured Products
4. Promotional cards

Each section can also have an editable display title and sort order.

### `ContentPage`

Customer-facing policy pages are database-backed:

- Terms & Conditions
- Privacy Policy
- Return & Refund Policy
- Shipping Policy

Each page has title/body, SEO title/description and published status. Unpublished pages return 404. Policy body is treated as plain text and escaped by Django rendering.

## Dashboard routes

- `/dashboard/settings/`
- `/dashboard/settings/banners/`
- `/dashboard/settings/banners/add/`
- `/dashboard/settings/homepage/`
- `/dashboard/settings/pages/`

Every CMS route requires `staff_access.manage_store_settings`. Default Admin and Manager roles have this permission; default Cashier does not. Permission enforcement happens server-side in `StaffAccessMiddleware`, not only in the sidebar.

## Storefront integration

The storefront now reads the database settings for:

- brand/store name and tagline
- uploaded logo and favicon
- support/contact information
- top-bar messages
- footer copy/social links
- homepage hero slides
- homepage section ordering/visibility
- policy links/pages
- SEO title/description/keywords
- delivery charges and estimated delivery times

The seeded migration preserves the previous visual starting point by creating hero/banner content that references the existing static assets until the admin uploads replacements.

## Delivery and checkout source of truth

Delivery settings are not presentation-only.

At checkout the server reloads `StoreSettings` and calculates shipping from the real merchandise subtotal after the server has resolved current/Flash Sale product prices. A configured free-delivery threshold can reduce shipping to zero. The final charge does not trust the browser preview.

Current rules:

- Inside Dhaka charge: configurable
- Outside Dhaka charge: configurable
- Free-delivery threshold: configurable (`0` disables it)
- Invalid delivery zone: rejected
- COD disabled in Store Settings: server rejects a COD checkout

The browser checkout UI receives the same settings for display/recalculation, but the server remains authoritative.

## Migration

v2.6.0 adds:

- `store_settings_store_settings`
- `store_settings_herobanner`
- `store_settings_homesection`
- `store_settings_contentpage`

Migration: `store_settings/0001_initial.py`

The migration seeds the singleton settings row, four homepage sections, three starting hero banners and four policy pages. Existing commerce/accounting data is unchanged.

## Validation

Validated on MySQL 8.0.46 and Python 3.12.14:

- Django system check: PASS
- migration drift: PASS / No changes detected
- migration application: PASS
- CMS / Store Settings dedicated tests: **11/11 PASS**
- full project regression: **223/223 PASS**

Dedicated coverage includes seeded CMS defaults, settings persistence, banner CRUD/safe serialization, homepage section visibility/order, content-page publication/SEO, storefront branding/SEO, delivery service rules, Cashier/Manager permissions, custom checkout shipping, free-delivery threshold and COD-disabled checkout rejection.
