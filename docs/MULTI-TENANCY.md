# Multi-Tenancy Playbook

How Budgetary implements each of the ten multi-tenancy patterns that a
sellable, global SaaS needs — what is shipped today and the concrete
upgrade path for each.

## 1. Hybrid data isolation

**Shipped:** shared database, shared schema, `tenant_id` on every tenant-
owned table, with PostgreSQL **Row-Level Security enabled and forced**.
Every request transaction runs
`SELECT set_config('app.current_tenant_id', :tid, true)` before touching
data, so the database — not application code — is the isolation boundary.
The app connects as a dedicated **non-superuser role** (`APP_DB_USER`,
default `budget_app`, created on first boot by `deploy/postgres/`) because
superusers bypass RLS entirely — the admin `POSTGRES_USER` is only used to
initialize the cluster. The tenant contract test suite proves a second
tenant cannot see, fetch or attach rows from the first, even via raw SQL.

**Path:** large customers can move to a schema-per-tenant or database-
per-tenant without API changes: the same `tenant_id` context and
repository layer apply; only the connection routing changes.

## 2. Geo-compliance routing

**Shipped:** tenant table carries `locale`, `timezone`, `currency`;
compose is region-agnostic so the stack can be deployed into any region
(EU, US, Middle East) unchanged.

**Path:** add a `data_region` column and route connections to the regional
Postgres (EU-west vs US-east) in the tenancy dependency; pair with
per-region S3 buckets for exports. GDPR/CCPA stays a deployment decision,
not a rewrite.

## 3. Self-serve provisioning

**Shipped:** `POST /api/v1/auth/register` creates the tenant, the owner
user, default categories and an audit entry in one transaction — no human
in the loop. Slug uniqueness is enforced with a 409.

**Path:** add plan selection + Stripe checkout on the register screen and
provision entitlements from the tenant's `tier`.

## 4. Centralized identity and RBAC

**Shipped:** tenant-scoped login (`slug + email + password`), JWT with
`tid`/`role` claims, four roles (owner/admin/member/viewer) enforced in
the API dependency layer; the UI gates write affordances by role.

**Path:** plug OIDC/SAML SSO in front of the same JWT issuance — the
principal shape (`user`, `tenant`, `role`) does not change.

## 5. Multi-currency billing and localization

**Shipped:** every tenant stores `currency` and `locale`; all money is
`NUMERIC(14,2)` aggregated in SQL and formatted client-side with
`Intl.NumberFormat`. Category/expense data is currency-agnostic.

**Path:** add a price table keyed by currency for subscription billing;
FX conversions, if ever needed, happen at report time, never in storage.

## 6. Noisy-neighbour throttling

**Shipped:** sliding-window rate limiter keyed by `tenant:{id}` (falls
back to `ip:{addr}` for unauthenticated traffic), applied as middleware
before routing, with `429` + `Retry-After`.

**Path:** swap the in-process store for Redis (`INCR` + expiry) when
running multiple API replicas; add per-tier limits by reading
`tenants.tier`.

## 7. White-labeling per tenant

**Shipped:** tenants own `display_name`, `accent_color`, `logo_url`,
`currency`, `locale`, `timezone`. The public
`GET /api/v1/settings/public/{slug}` endpoint themes the login page before
authentication; authenticated pages apply the same accent live. Accent
values are validated as hex, so tenant input cannot inject CSS.

**Path:** custom domains require a hostname→tenant lookup (a `domains`
table + Caddy `on_demand_tls`); dynamic logos can be served from tenant
object storage.

## 8. Encryption and key custody (BYOK)

**Shipped:** passwords are bcrypt-hashed; secrets (JWT key, DB password)
come from the environment and never appear in logs; no PII beyond
name/email is stored.

**Path:** BYOK = per-tenant envelope encryption: store a wrapped data key
per tenant, encrypt sensitive columns (notes, exports) with it, keep the
KEK in the customer's KMS. The service layer is already the single place
that reads/writes tenant rows, so encryption hooks land there.

## 9. Feature flags and entitlements

**Shipped:** `tenants.tier` travels in every auth response and the UI can
gate on it; the settings payload exposes it.

**Path:** add `tenant_features` (flag, enabled, limit) and a
`require_feature("csv_export")` dependency; pair limits with the rate
limiter keyed by tier.

## 10. Sharded, tenant-tagged observability

**Shipped:** every request carries `X-Request-ID`; access logs include the
request id, tenant id and principal; audit logs are per-tenant and
queryable.

**Path:** emit OpenTelemetry spans tagged `tenant.id`, ship to a backend
with per-tenant views; use the same tag on metrics
(`http_requests_total{tenant=...}`) so a noisy tenant is visible before
users feel it.

---

## Isolation guarantees (tested)

The `backend/tests/test_tenancy_contract.py` suite asserts:

1. Tenant B receives zero rows for Tenant A's data through the API.
2. Direct SQL without tenant context returns no tenant rows; inserts are
   rejected by the RLS `WITH CHECK` policy.
3. Cross-tenant `GET` of a known id returns 404 (not 403 — no existence
   leak).
4. A category id from another tenant is rejected (422) on expense create.
5. Login only succeeds against the user's own tenant slug.
6. Duplicate workspace slugs are rejected with 409.
