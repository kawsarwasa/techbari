# TechBari v3.0 — Production Deployment Runbook

This runbook is intentionally compatible with a conventional MySQL 8 shared-hosting / cPanel deployment. It does not require Redis, Celery or a persistent WebSocket worker.

## 1. Release rule

Deploy only a merged, tested `main` commit. Never deploy a partially completed feature branch.

Before every production release:

1. create/verify a database backup;
2. preserve the current `.env` outside the repository;
3. note the currently deployed Git commit;
4. pull the new `main` commit;
5. install dependencies;
6. run migrations;
7. collect static assets;
8. run deployment checks and the TechBari preflight;
9. restart/reload the production WSGI application;
10. smoke-test storefront, checkout and dashboard.

## 2. Production environment

Copy `.env.example` to `.env` and replace every example value that is relevant to the deployment.

Minimum production rules:

```text
DJANGO_DEBUG=0
DJANGO_SECRET_KEY=<unique long random secret>
DJANGO_ALLOWED_HOSTS=example.com,www.example.com
STAFF_AUTH_ENABLED=1
SECURE_SSL_REDIRECT=1
SESSION_COOKIE_SECURE=1
CSRF_COOKIE_SECURE=1
INTEGRATION_REQUIRE_HTTPS=1
COURIER_WEBHOOK_REQUIRE_TIMESTAMP=1
```

Do not use `*` for `DJANGO_ALLOWED_HOSTS`. Do not commit `.env`.

`TRUST_X_FORWARDED_PROTO=1` and `TRUST_X_FORWARDED_FOR=1` are safe only when the reverse proxy/web server overwrites or sanitizes those headers. Leave them disabled if you cannot confirm that behavior.

### HSTS rollout

Start conservatively after HTTPS is confirmed across the site:

```text
SECURE_HSTS_SECONDS=3600
SECURE_HSTS_INCLUDE_SUBDOMAINS=0
SECURE_HSTS_PRELOAD=0
```

Increase the duration later. Do not enable subdomain coverage or preload until every required subdomain is permanently HTTPS-ready.

## 3. Database backup before migration

Use the hosting provider's database backup feature when available. A command-line MySQL backup is also acceptable:

```bash
mysqldump --single-transaction --routines --triggers -h DB_HOST -u DB_USER -p DB_NAME > techbari-before-deploy.sql
```

Keep database credentials out of shell history where possible. On cPanel, the built-in Backup/Backup Wizard is usually preferable.

A backup is only useful if it can be restored. Perform a restore drill periodically in a non-production database.

Suggested retention:

- daily: 7 days
- weekly: 4–8 weeks
- monthly: 6–12 months

Adjust retention to business/legal requirements and storage limits.

## 4. Deploy commands

Activate the production virtual environment and enter the project directory, then:

```bash
git checkout main
git pull origin main
pip install -r requirements.txt
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py check
python manage.py check --deploy
python manage.py production_preflight
```

`production_preflight` verifies database connectivity, pending migrations, production security switches, enabled integration credentials and storefront payment test-mode state without printing secret values.

Do not use Django `runserver` as the production web server. Configure the hosting platform's WSGI application entry point to `techbari.wsgi.application`.

## 5. Static and media files

`collectstatic` writes collected assets to `STATIC_ROOT` (`staticfiles/`). Configure Apache/Nginx/cPanel to serve `/static/` from that directory.

Uploaded files live under `MEDIA_ROOT` (`media/`). Configure `/media/` separately. The repository does not serve media with Django when `DEBUG=False`.

Back up media files together with the database. Database rows without their uploaded files are not a complete backup.

## 6. Health check

The production-safe readiness endpoint is:

```text
/health/
```

Healthy response:

```json
{"status":"ok"}
```

Database failure returns HTTP 503 with only:

```json
{"status":"unavailable"}
```

No configuration or secrets are returned.

## 7. Integration worker cron

TechBari uses a MySQL-backed outbox, so shared hosting does not need Redis/Celery.

Run every 5 minutes (adjust paths for the hosting account):

```cron
*/5 * * * * cd /path/to/techbari && /path/to/venv/bin/python manage.py process_integrations --limit 100 >> /path/to/logs/integrations.log 2>&1
```

This processes Email, SMS, WhatsApp, Meta CAPI, GA4 and courier jobs. Failed jobs use retry/backoff and do not roll back the original sale/payment transaction.

Run security-state cleanup daily:

```cron
25 3 * * * cd /path/to/techbari && /path/to/venv/bin/python manage.py cleanup_security_state >> /path/to/logs/security-cleanup.log 2>&1
```

## 8. External integration secrets

Keep provider secrets only in `.env` / hosting environment variables.

Examples:

```text
META_CAPI_ACCESS_TOKEN=
META_GRAPH_API_VERSION=
GA4_API_SECRET=
SMS_API_TOKEN=
WHATSAPP_API_TOKEN=
COURIER_API_TOKEN=
COURIER_WEBHOOK_SECRET=
```

Courier-specific configuration uses the provider code, for example `FAST`:

```text
COURIER_FAST_API_BASE_URL=https://provider.example/api
COURIER_FAST_CREATE_PATH=/shipments
COURIER_FAST_API_TOKEN=
COURIER_FAST_WEBHOOK_SECRET=
```

Production outbound integrations require HTTPS and reject local/private destinations. This also protects configurable webhook endpoints from becoming an SSRF path.

## 9. Courier webhook contract

Production courier callbacks use:

```text
X-TechBari-Timestamp: <unix-seconds>
X-TechBari-Signature: sha256=<hex-hmac>
```

The signature input is exactly:

```text
<timestamp>.<raw-request-body>
```

using HMAC-SHA256 with the configured courier webhook secret. Requests outside the configured timestamp skew are rejected. Valid replayed payloads are recognized and are not applied twice.

## 10. Production email and payments

Replace the console email backend with the actual SMTP/provider backend before live email is required.

Before go-live, every storefront-enabled payment method must be reviewed and must not remain in `is_test_mode=True`. `production_preflight` treats an enabled storefront payment method in test mode as a deployment blocker.

## 11. Smoke test after each deploy

Verify at minimum:

- `/health/` returns 200
- homepage and product pages load over HTTPS
- customer register/login/logout
- cart and checkout
- one controlled test order
- dashboard staff login
- role/permission denial for a restricted staff account
- inventory reservation and order status flow
- payment capture/refund path where configured
- notifications page
- integration queue command
- static images/CSS/JS and uploaded media
- 404 and 500 error pages do not expose debug information

## 12. Rollback

If a deployment fails:

1. stop/reload the application as appropriate;
2. restore the previous known-good Git commit;
3. restore the pre-deployment database backup if the new migration changed data/schema in a way that cannot safely remain;
4. restore media files if they changed;
5. restart the WSGI application;
6. verify `/health/`, storefront and dashboard.

Do not blindly reverse a migration containing business-data changes. Prefer restoring the paired code/database backup when rollback safety is uncertain.

## 13. Release gate

A production release is not ready until all of these are green:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py check --deploy
python manage.py production_preflight
python manage.py test
```

For TechBari releases, the project-specific MySQL 8 dedicated suite and full regression must also pass in CI before merging to `main`.
