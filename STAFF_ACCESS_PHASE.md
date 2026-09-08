# TechBari v2.5.0 — Users / Roles / Permissions

## Goal

v2.5.0 converts the old static/localStorage Users & Audit pages into a real Django staff authentication and authorization system. The dashboard is private by default and every dashboard route is checked server-side against a TechBari permission.

The implementation takes the useful authentication/session pattern from the CreativeITMart project (Django auth, sessions, password validation and secure cookies) and extends it with proper RBAC, because CreativeITMart itself only has login-required dashboard access and no fine-grained role layer.

## System roles

TechBari creates six Django Group-backed system roles after migrations:

| Role | Default responsibility |
| --- | --- |
| Admin | Full TechBari access; protected full-permission role |
| Manager | Broad operational access; cannot manage staff permissions or Accounting settings by default |
| Cashier | POS, sales/customer and payment operations; no Accounting access |
| Inventory Manager | Catalog, inventory, Serial/IMEI, purchasing, returns and reports |
| Accountant | Payments, Accounting, Accounting settings, expenses/approval and reports |
| Sales Staff | Catalog/customer/sales/shipping/returns operational access |

Non-Admin role permission matrices can be edited from the dashboard. Individual staff users can also receive extra direct permissions in addition to their role. Admin remains protected and always keeps every TechBari permission.

## Fine-grained permissions

Custom permissions are grouped around real TechBari actions, including:

- Dashboard view
- Catalog view/manage
- Inventory view/manage/adjust-transfer
- Serial / IMEI view/manage
- Purchasing view/manage
- Customers view/manage
- Sales view/manage
- POS use
- Payments view/manage
- Shipping view/manage
- Returns/Warranty view/manage
- Accounting view/manage
- Accounting Settings manage
- Expenses view/manage/approve
- Reports view
- Marketing view/manage
- Store settings manage
- Users view/manage
- Audit Log view

The permission layer is enforced in `StaffAccessMiddleware`, not only by hiding links in templates. Sidebar visibility is a convenience; direct URL access is still checked server-side.

### Required accounting restriction

A default Cashier does **not** have `staff_access.view_accounting`, `staff_access.manage_accounting`, or `staff_access.manage_accounting_settings`.

`account_add` and `accounting_period_toggle` require `manage_accounting_settings`, so a Cashier cannot edit Chart of Accounts or Accounting periods even by calling the URL directly.

## Authentication

Dashboard authentication routes:

- `/dashboard/login/`
- `/dashboard/logout/` — POST only
- `/dashboard/password-reset/`
- `/dashboard/password-change/`

Login accepts username or a unique active staff email. Django password hashing and configured password validators are used. Password reset uses Django's signed reset-token flow and a configurable email backend.

## Session security

Defaults:

- dashboard auth enabled
- 30-minute idle timeout (`STAFF_IDLE_TIMEOUT=1800`)
- 8-hour session cookie age (`SESSION_COOKIE_AGE=28800`)
- HttpOnly session cookie
- SameSite=Lax session and CSRF cookies
- secure session/CSRF cookies by default when `DJANGO_DEBUG=0`
- CSRF protection on mutations
- `X_FRAME_OPTIONS = DENY`
- content-type sniffing protection
- safe validation of post-login `next` redirects

An idle dashboard session is logged out and the user is sent back to login.

## Audit Log

`AuditLog` is database-backed and records staff security/operational events such as:

- successful login
- failed login
- logout / idle-session expiry
- permission denied
- staff/role create or update
- password change
- dashboard POST/PUT/PATCH/DELETE mutations

Audit rows retain user/role snapshots, route/path, HTTP method, response status, IP, user agent and summary. The log is viewable only by users with `view_audit_log` (or superusers).

## Staff management UI

Real database-backed pages now include:

- `/dashboard/users/`
- `/dashboard/users/add/`
- user edit/activate/deactivate
- `/dashboard/users/roles/`
- role permission editor
- `/dashboard/audit-log/`

The top bar shows the signed-in staff member and role, with Password and POST-only Logout actions. The sidebar only displays modules the user is allowed to access.

## First administrator

After applying v2.5 migrations, bootstrap the first administrator:

```powershell
python manage.py bootstrap_admin --email admin@example.com
```

The command prompts for a password if `--password` is omitted. It creates/updates the user, assigns the Admin role, creates the StaffProfile and makes the account a Django superuser by default. `--no-superuser` is available when only the TechBari Admin role is desired.

## Environment settings

Useful `.env` values:

```env
STAFF_AUTH_ENABLED=1
STAFF_IDLE_TIMEOUT=1800
SESSION_COOKIE_AGE=28800
DJANGO_EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
DEFAULT_FROM_EMAIL=noreply@techbari.local
```

`SESSION_COOKIE_SECURE` and `CSRF_COOKIE_SECURE` default to secure when `DJANGO_DEBUG=0`; do not turn them off on normal HTTPS production deployments.

## Database changes

v2.5.0 introduces Django's built-in auth/contenttypes/session tables to TechBari plus:

- `staff_access_staffprofile`
- `staff_access_auditlog`

Migration: `staff_access/0001_initial.py`.

The six system roles and their initial permission sets are synchronized after migration.

## Test strategy

Pre-v2.5 business tests were written before dashboard authentication existed. `TechBariTestRunner` keeps those historical tests focused on business/transaction semantics by disabling the staff-auth boundary for legacy tests. `StaffAccessTests` explicitly re-enables the real auth boundary and validates authentication, authorization and session behavior.

Security coverage includes:

- anonymous dashboard block
- username/email login and inactive-user rejection
- six role defaults
- Cashier Accounting denial
- Cashier Accounting Settings denial
- Accountant Accounting access
- Manager user-management restriction
- direct per-user permission grants
- Admin protected role
- editable non-Admin permission matrix
- real staff-user creation
- idle session expiry
- password reset
- POST-only audited logout
- superuser bypass
- authenticated Admin access across every major dashboard module

## Next roadmap phase

v2.6.x — CMS / Store Settings.
