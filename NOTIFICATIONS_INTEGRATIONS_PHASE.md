# TechBari v2.8.0 — Notifications / Integrations

## Scope

v2.8.0 adds operational notifications and external integration hooks without introducing Redis, Celery or a permanently running worker. The design remains compatible with typical shared hosting by using a durable MySQL-backed outbox that can be processed from cron.

## Notification Center

The dashboard notification center is database-backed and receives operational alerts for:

- Sales Order create/status events
- completed/changed Payment transactions
- low-stock and out-of-stock Inventory balances
- Shipment create/status/tracking events
- external integration delivery failures

Notifications have per-user read/unread state. The dashboard bell count is calculated from unread records for the current staff user.

## External Outbox

`OutboundMessage` stores queued external deliveries with:

- channel and event type
- idempotency key
- reference type/reference ID
- payload/body/recipient
- pending/sent/failed/skipped status
- attempts, next availability, last attempt and sent timestamps
- sanitized failure text

External provider failure does not roll back the Sales, Payment, Inventory or Shipping business transaction. Failed jobs use exponential retry delay and remain visible from the integration dashboard.

Process the queue manually with:

```bash
python manage.py process_integrations --limit 100
```

For shared hosting, a practical production setup is to execute the same command from cron every five minutes. The exact frequency can be adjusted to traffic and hosting limits.

## Email / SMS / WhatsApp

- Email uses Django's configured email backend.
- SMS uses a configurable generic JSON webhook.
- WhatsApp uses a configurable generic JSON webhook.
- SMS/WhatsApp authentication tokens are read from environment variables when delivery occurs.

The generic webhook payload contains the destination, message, event type and internal reference. Provider-specific APIs can later be added behind the same outbox interface.

## Meta Pixel + Conversions API

Browser-side events:

- PageView
- ViewContent
- AddToCart
- InitiateCheckout
- Purchase

Server-side Purchase is queued for Meta Conversions API when enabled. Browser Purchase and CAPI Purchase use the same stable event ID:

```text
tb-purchase-<ORDER_NUMBER>
```

This allows Meta browser/server event deduplication. Customer email/phone used in CAPI user data are SHA-256 hashed before being placed in the outbound payload. `META_CAPI_ACCESS_TOKEN` is never exposed to storefront HTML.

Meta configuration uses:

```text
META_CAPI_ACCESS_TOKEN
META_GRAPH_API_VERSION
META_CAPI_BASE_URL
```

The Graph API version is environment-configurable so it can be upgraded without changing the core delivery design.

## Google Analytics 4

Browser tracking uses the public GA4 Measurement ID. Server-side Purchase uses Google Analytics Measurement Protocol and keeps `GA4_API_SECRET` on the server.

Relevant environment variables:

```text
GA4_API_SECRET
GA4_MEASUREMENT_PROTOCOL_URL=https://www.google-analytics.com/mp/collect
```

The server event includes the order transaction ID, BDT currency, value, shipping and item details.

## Courier Integration

Courier API integration is provider-code based. Existing `CourierProvider.api_enabled` controls whether a provider may use API hooks; provider endpoints/secrets stay in environment variables.

For a provider with code `FAST`:

```text
COURIER_FAST_API_BASE_URL=https://courier.example/api
COURIER_FAST_CREATE_PATH=/shipments
COURIER_FAST_API_TOKEN=...
COURIER_FAST_WEBHOOK_SECRET=...
```

Generic fallbacks are also supported:

```text
COURIER_API_TOKEN
COURIER_WEBHOOK_SECRET
```

Courier booking responses can update tracking ID/reference through the existing Shipping service layer.

Inbound courier webhook:

```text
/integrations/courier/<CODE>/webhook/
```

The webhook verifies an HMAC-SHA256 signature from `X-TechBari-Signature` against the raw request body before accepting any update. Valid updates go through the existing Shipping Engine so shipment transition rules remain authoritative.

## Security / Secret Handling

Private integration secrets are not editable dashboard fields and are not emitted into storefront HTML. They belong in `.env` / hosting environment configuration.

Examples:

```text
SMS_API_TOKEN
WHATSAPP_API_TOKEN
META_CAPI_ACCESS_TOKEN
GA4_API_SECRET
COURIER_<CODE>_API_TOKEN
COURIER_<CODE>_WEBHOOK_SECRET
```

Delivery errors are sanitized before persistence; configured environment values with names containing TOKEN, SECRET or PASSWORD are redacted from stored exception text.

Public storefront tracking context contains only public identifiers and enabled flags such as Meta Pixel ID and GA4 Measurement ID.

## Staff Permissions

v2.8.0 adds:

- `staff_access.view_notifications`
- `staff_access.manage_integrations`

All six system roles receive notification viewing by default. Admin has all permissions. Manager receives `manage_integrations` by default. Cashier, Inventory Manager, Accountant and Sales Staff do not receive integration-management access by default.

Integration settings/process/retry routes are enforced server-side by `StaffAccessMiddleware`; hiding links in the UI is not the security boundary.

## Database Migrations

v2.8.0 introduces:

- `integrations/0001_initial.py`
- `staff_access/0002_v280_integration_permissions.py`

Run:

```bash
python manage.py migrate
```

## Dashboard Routes

- `/dashboard/notifications/`
- `/dashboard/integrations/`

The existing notification URL is preserved for compatibility.

## Production Setup

1. Deploy/pull v2.8.0.
2. Install requirements.
3. Run migrations and Django check.
4. Configure SMTP and only the provider secrets actually being used.
5. Enable desired channels/analytics in Dashboard → Integrations.
6. Configure courier providers in Shipping and provider-code environment variables if API booking is needed.
7. Add a cron job for `python manage.py process_integrations --limit 100`.
8. Verify provider test-mode events before enabling production traffic.

External channels are not automatically usable just because v2.8.0 is installed; the relevant dashboard toggle, public ID/endpoint and private environment secret must be configured.

## QA

Validated on GitHub Actions with Ubuntu 24.04, Python 3.12.14 and MySQL 8.0.46:

- Django system check: PASS
- migration drift: PASS / No changes detected
- MySQL migration application: PASS
- v2.8 dedicated Notifications / Integrations tests: **13/13 PASS**
- full project regression: **256/256 PASS**
