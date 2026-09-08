# TechBari v2.3.0 — Promotion / Marketing

TechBari v2.3.0 replaces the old static/mock coupon behavior with a database-backed promotion engine integrated with Catalog, Storefront Checkout and Sales Orders.

## Scope

- Coupon backend
- Fixed and percentage discounts
- Minimum order amount
- Start/end date range
- Global usage limit with recorded redemptions
- Product-specific and category-specific coupons
- Flash Sales
- Featured Products
- Campaign tracking and conversion attribution

## Data model

### Campaign
Stores a campaign code, name, source, medium, active date range and enabled state.

### Coupon
Stores coupon code/name, discount type/value, minimum order, active date range, optional usage limit, usage count, scope, optional Product/Category targets and optional Campaign relationship.

### FlashSale
Stores a temporary fixed/percentage discount, active date range and the Products included in the sale.

### CouponRedemption
Creates one immutable redemption record per Sales Order and stores the actual discount amount granted. This is the accounting/audit-friendly source for coupon usage reporting.

### CampaignEvent
Tracks Visit, Coupon Applied and Conversion events. Conversion events can reference the resulting Sales Order and amount.

## Pricing and stacking rules

1. Product/variant price still originates from the Catalog database.
2. If one or more live Flash Sales apply, TechBari calculates each Flash Sale from the regular price and chooses the best valid price against the existing current/sale price.
3. A weaker Flash Sale never makes an existing sale price worse and Flash Sales do not compound with each other.
4. One coupon code can be used per checkout.
5. Coupon minimum-order validation uses the real server-calculated cart subtotal after automatic Flash Sale pricing.
6. Product/category coupons discount only their eligible line subtotal.
7. Fixed discounts are capped at the eligible subtotal; a promotion cannot make an eligible subtotal negative.
8. Checkout is server-authoritative. Browser/cart display values are never trusted for order unit price or final discount.
9. Browser coupon previews include the live minimum-order rule and the exact eligible Product set for Product/Category scoped coupons so the displayed preview matches the server rule as closely as possible.

## Usage-limit safety

Checkout is wrapped in a database transaction. Coupon validation can lock the Coupon row using `select_for_update()` before the Sales Order is saved. The redemption and usage-count update happen in the same transaction, preventing two concurrent checkouts from legitimately consuming the same final usage slot.

Duplicate checkout submissions remain idempotent through the existing checkout token/order-number behavior. A CouponRedemption is one-to-one with a Sales Order, so one order cannot increment coupon usage twice.

## Campaign tracking

A campaign can be linked with:

```text
?campaign=FB-SEPT&utm_source=facebook&utm_medium=cpc
```

`utm_campaign` is also accepted as the campaign code. Valid live campaign landings create a Visit event and set a signed, HTTP-only `tb_campaign` cookie.

Checkout does not trust a posted/hidden campaign code. It decodes the signed cookie, resolves the exact Visit event by Campaign + tracking token, and carries that Visit attribution into the Conversion event. The Conversion therefore preserves the original tracking token, source, medium, landing path and referrer. A forged/tampered attribution cookie is ignored. Coupon-linked campaigns can still record Coupon Applied events and can act as a fallback attribution when there is no trusted Visit attribution.

The signed cookie does not contain pricing authority and cannot grant a discount. It is attribution data only.

## Featured Products

Featured Products reuse `catalog.Product.is_featured` as the single source of truth. The Marketing dashboard can toggle this flag and the storefront featured collection reads it directly.

## Dashboard routes

- `/dashboard/marketing/` — campaign management, Flash Sales, Featured Products, KPIs and recent campaign activity
- `/dashboard/coupons/` — coupon list/search/filter/status/usage
- `/dashboard/coupons/add/` — add/edit coupon rules

## Storefront integration

The Storefront catalog displays valid Flash Sale pricing and exposes live coupon data only as a browser preview. Checkout always re-fetches Catalog/Promotion data and recomputes the real order server-side.

## Migration

v2.3.0 adds:

- `promotions_campaign`
- `promotions_coupon`
- Coupon Product/Category many-to-many tables
- `promotions_flashsale` and its Product mapping table
- `promotions_couponredemption`
- `promotions_campaignevent`

Apply with:

```powershell
python manage.py migrate
```

## Validation gates

Validated on GitHub Actions using MySQL 8 and Python 3.12:

- Django system check: PASS
- migration drift (`makemigrations --check --dry-run`): PASS / no changes detected
- migrations: PASS
- Promotion / Marketing suite: 15/15 PASS
- full regression suite: 188/188 PASS

Dedicated tests cover fixed/percentage calculations, minimum order, usage limit, scheduled/expired/inactive coupons, Product/Category scope, scoped browser preview data, Flash Sale best-price behavior, redemption idempotency, Featured Product dashboard toggling, campaign landing capture, signed Visit-to-Conversion attribution, tampered attribution rejection, campaign conversion idempotency, checkout integration and database-backed dashboard rendering.
