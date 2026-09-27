# TechBari Security & Go-Live Review

Review date: 2026-09-27  
Baseline reviewed: `main` at `d8e1156c3cd86a4c7cc38ecccd57785f4ce43918`

## Executive status

The project already had a strong baseline: fail-closed dashboard permissions, CSRF middleware, secure-cookie/HTTPS production switches, login throttling, audit logs, signed courier webhooks, outbound URL/SSRF checks, server-side price/coupon validation, upload type/size validation, production checks, and a full MySQL CI suite.

This review found several go-live security gaps. The code-level gaps below are being fixed as part of the review commit. The remaining items require an operational choice or a larger feature.

## Fixed in this review

### Critical / High

- **Superuser takeover path closed.** A staff user with `manage_users` can no longer edit the password or active state of a Django superuser unless the acting user is also a superuser.
- **Forced first password change is now enforced.** Passwords assigned through staff-user administration set `force_password_change`; dashboard access is redirected to the password-change flow until completed.
- **Staff password reset is staff-only and throttled.** The dashboard reset form no longer sends reset mail for customer-only auth users and repeated reset requests are rate limited without revealing account existence.
- **Checkout confirmation token removed from new URLs.** New orders use a session grant and a clean confirmation URL so an access token is not exposed to browser history, analytics page URLs/referrers, or routine access logs. Legacy signed links remain accepted and are immediately redirected to a clean URL.
- **Checkout abuse throttle added.** Successful stock-reserving online orders are capped per phone and per source IP in a configurable time window.
- **Upload decompression-bomb guard added.** Catalog and CMS images now have a pixel-count limit in addition to the existing 2 MB/type/extension/image-verification checks.
- **Staff TOTP MFA implemented.** Staff can enroll using a QR/manual secret, TOTP secrets are encrypted at rest with a dedicated production Fernet key, login requires the second factor once enrolled, TOTP replay is blocked, recovery codes are one-time and hashed, MFA attempts are rate limited, existing authenticated sessions without MFA proof are invalidated, and production policy can force enrollment for every active staff account.

### Deployment gate

- `production_preflight` now rejects production when HTTPS redirect, secure session cookie, secure CSRF cookie, integration HTTPS, signed webhook timestamps, staff idle timeout, or a real email backend are missing.
- CI now runs a production `check --deploy` configuration check.
- CI now runs `pip-audit` against Python dependencies.
- The production runbook documents branch protection, MFA, SMTP, least-privilege DB credentials, backup/restore, cron monitoring, WAF/CAPTCHA escalation and error monitoring.

## Existing controls verified

- Production refuses the development secret key and wildcard `ALLOWED_HOSTS`.
- Staff dashboard routing is fail-closed for unclassified routes.
- Staff idle timeout and DB-backed login throttling are active.
- Customer dashboard objects are scoped to the authenticated customer account.
- Guest checkout does not overwrite an existing CRM profile.
- Existing CRM account claiming requires prior-order knowledge and matching stored email when available.
- Coupon rules and prices are recomputed server-side.
- Courier webhook uses HMAC and optional timestamp freshness/replay protection; production requires timestamps.
- Outbound integration URLs can be restricted to HTTPS/public destinations to reduce SSRF risk.
- Current repository tree does not contain a real `.env`, private key, database dump or service-account credential file; `.gitignore` excludes common secret artifacts.
- Contact form has validation, a honeypot and basic per-IP rate limiting.
- Static/media are not served by Django when `DEBUG=False`.

## Remaining risks / manual go-live blockers

### High — GitHub `main` is currently unprotected

At review time the default branch reports `protected: false` and the repository has no rulesets. Direct pushes can bypass pull-request review and required CI. Configure a branch ruleset/branch protection requiring the Django CI workflow before merge.

### Operational — active staff must complete MFA enrollment

The application now supports and can require staff MFA, but each existing active staff user still has to enroll an authenticator after deployment. `production_preflight` warns while active staff accounts remain unenrolled.

### Medium — existing-customer self-linking is knowledge based

OTP was intentionally not used. Previous order number + stored email is stronger than phone-only linking, but it is not proof of phone/email possession. Keep the support fallback for unverifiable records and consider OTP later for higher assurance.

### Medium — public abuse controls are basic

Checkout now has DB-backed per-phone/IP throttling and contact has a rate limit, but there is no CAPTCHA/WAF. Add Cloudflare/WAF/CAPTCHA if fake accounts/orders or automated coupon guessing becomes material.

### Medium — dependencies are range-pinned, not release-locked

`requirements.txt` constrains major/minor ranges, so two deployments can resolve different patch versions. CI now audits known vulnerabilities, but a generated lock/constraints file should be introduced before stricter release reproducibility is required.

### Medium — no enforced Content-Security-Policy

Security headers include clickjacking, MIME sniffing, referrer, COOP, CORP and Permissions-Policy protections, but there is no CSP. A CSP should be introduced carefully because the storefront currently loads Google Fonts, Meta Pixel and GA4 and contains legacy inline script/style usage.

### Medium — production observability is console-log based

Add centralized error/uptime monitoring and alerts for 5xx responses and repeated integration failures. Console logging alone is easy to miss on shared hosting.

## Go-live release gate

Run these on the actual production environment after the real `.env` is configured:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py check --deploy
python manage.py production_preflight
python manage.py test
```

Then verify HTTPS, `/health/`, staff password reset email, restricted-role 403 behavior, one controlled checkout, stock reservation/release flow, static/media, integration worker cron, security cleanup cron, backup availability, and a 404/500 response with `DEBUG=0`.

Do not call the deployment production-ready until the manual High items above are accepted or resolved.
