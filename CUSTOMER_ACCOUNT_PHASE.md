# TechBari v2.7.0 — Customer Account

## Scope

v2.7.0 replaces storefront account demos with a database-backed customer account layer connected to the existing CRM, Sales, Shipping and Serial / Warranty systems.

## Identity architecture

- Django authentication remains the authentication engine.
- Staff portal users and storefront customers are separated by role: customer users are created with `is_staff=False`.
- `CustomerAccount` links one Django user one-to-one with one existing `customers.Customer` CRM record.
- Customer registration never creates a second CRM Customer when the mobile number already belongs to an existing buyer.
- Customer login accepts the linked phone number or email.
- Staff users are rejected by the customer login flow.

## Existing CRM customer linking

Existing CRM records require additional proof before self-service account activation:

- if historical non-draft/non-cancelled orders exist, the customer must provide one matching previous TechBari order number;
- an existing CRM email must match the email submitted during registration;
- CRM records with opening balances cannot be self-claimed without stronger verification/support activation;
- already-linked phone/email identities cannot be registered again.

These rules prevent a new storefront login from claiming another customer's purchase history or due balance simply by knowing a phone number.

## Customer account features

- Register / Login / Logout
- Customer Dashboard
- My Orders
- Customer-scoped Order Detail
- Courier tracking and shipment history for owned orders
- Public order tracking using order number + matching phone
- Database-backed Wishlist
- Saved Addresses
- Exactly one default saved address when addresses exist
- Profile editing
- Password change with session preservation
- Warranty / Serial / IMEI lookup scoped to customer purchases

## Order and data isolation

All private order routes query through the linked CRM Customer. A customer cannot open another customer's order by guessing an order number.

Public tracking requires both the order number and the matching order/customer phone number.

Warranty / Serial / IMEI lookup only returns serialized units whose sales/customer references are associated with the signed-in customer's purchase history.

## Checkout integration

Logged-in checkout reuses the linked CRM Customer rather than resolving or creating a new customer from submitted shipping data.

Important invariants:

- the account's linked mobile number remains the ownership identity;
- saved shipping destinations may use another recipient name/phone without overwriting the CRM customer's profile identity;
- shipping destination details are stored on the Sales Order shipping fields;
- guest checkout is blocked server-side when Store Settings disables guest checkout;
- existing delivery-charge and COD rules remain server-authoritative.

## Models

`customer_accounts` introduces:

- `CustomerAccount`
- `SavedAddress`
- `WishlistItem`

Migration:

- `customer_accounts/0001_initial.py`

## Routes

Public/storefront:

- `/login/`
- `/register/`
- `/logout/`
- `/wishlist/`
- `/track-order/`

Private customer account:

- `/account/`
- `/account/orders/`
- `/account/orders/<order_number>/`
- `/account/addresses/`
- `/account/profile/`
- `/account/password/`
- `/account/warranty/`

## Security and privacy rules

- Customer and staff portal identities are separated.
- Private pages require an active customer account linked to an active CRM Customer.
- Cross-customer order access returns 404 rather than exposing ownership information.
- Public tracking requires matching phone verification.
- Existing purchase history linking requires an order challenge.
- Existing opening-balance CRM records are protected from weak self-claim.
- Password validation uses Django's configured password validators.
- Password change preserves the authenticated session.

## Validation

Validated on:

- MySQL 8.0.46
- Python 3.12.14
- Django 5.2.x

Final code-head validation:

- Customer Account dedicated suite: **20/20 PASS**
- full project regression: **243/243 PASS**
- Django system check: **PASS**
- migration drift: **PASS / No changes detected**
- migration application: **PASS**

## Next phase

v2.8.x — Notifications / Integrations.
