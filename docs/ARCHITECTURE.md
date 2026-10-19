# Architecture

Budgetary is a multi-tenant budgeting SaaS: one deployment serves many
workspaces ("tenants") with hard data isolation, per-tenant branding and
regional settings.

## Stack

| Layer     | Choice                                            |
| --------- | ------------------------------------------------- |
| API       | FastAPI + Uvicorn (Python 3.12)                   |
| Data      | PostgreSQL 17, SQLAlchemy 2.1 (async), asyncpg    |
| Migrations| Alembic (async env)                               |
| Auth      | JWT access + refresh (PyJWT), bcrypt password hash|
| Frontend  | React 19 + TypeScript + Vite 8 + Tailwind CSS 4   |
| Data (UI) | TanStack Query v5, Recharts                       |
| Edge      | Caddy (auto-TLS) → nginx (static SPA) → API       |

## Repository layout

```
budget-management-saas/
├── backend/
│   ├── app/
│   │   ├── api/            # HTTP layer: deps, routers (v1)
│   │   ├── core/           # config, security, database, tenancy, rate limit
│   │   ├── middleware/     # request context, security headers, rate limiting
│   │   ├── models/         # SQLAlchemy ORM (control plane + tenant plane)
│   │   ├── repositories/   # query building, tenant-scoped
│   │   ├── schemas/        # Pydantic request/response contracts
│   │   └── services/       # business logic (auth, finance, reports, tenants)
│   ├── alembic/            # migrations (schema + RLS policies)
│   ├── scripts/seed_demo.py
│   └── tests/              # unit + DB-backed tenancy contract tests
├── frontend/
│   ├── src/components/     # design system (ui.tsx) + product components
│   ├── src/lib/            # api client, auth, theme, types, formatting
│   └── src/pages/          # route screens
├── cli/budget_system.py    # original educational CLI edition
├── deploy/caddy/           # edge reverse proxy (TLS termination)
├── docs/                   # this documentation
└── docker-compose.yml      # db + backend + frontend + edge
```

## Request lifecycle

1. **Edge** — Caddy terminates TLS (automatic when `SITE_ADDRESS` is a real
   domain) and proxies to the frontend container.
2. **Frontend nginx** — serves the static SPA; `/api/*` is proxied to the
   backend. Security headers + CSP are attached to every response.
3. **Backend middleware (outermost → innermost)**:
   - CORS
   - Rate limiting — sliding window keyed `tenant:{id}` when a valid bearer
     token is present, else `ip:{addr}`
   - Security headers
   - Request context — parses the principal, sets `request_id` +
     `tenant_id` context vars, emits an access log line
4. **Route → service → repository** — every service call runs inside a
   session whose transaction starts with
   `set_config('app.current_tenant_id', :tenant_id, true)`, so Postgres RLS
   scopes every query to the tenant even if application code forgets a
   `WHERE` clause.
5. **Errors** — `DomainError` subclasses map to stable JSON responses:
   `{"detail": "..."}` with 400/401/403/404/409/429 statuses.

## Data model

Control plane (no RLS):

- `tenants` — slug (unique), name, tier, currency, locale, timezone,
  branding JSONB, `alert_threshold_pct`, `is_active`.

Tenant plane (RLS forced on `tenant_id`):

- `users` — unique `(tenant_id, email)`, role owner/admin/member/viewer
- `categories` — kind expense|income, colour, archive flag
- `budgets` — unique `(tenant_id, year, month)`; one limit per month
- `expenses` / `incomes` — money, category, note, `happened_on`
- `audit_logs` — append-only actor/action/entity trail per tenant

Money is stored as `NUMERIC(14,2)` and aggregated server-side; the client
only ever formats numbers. Timestamps are timezone-aware (`timestamptz`).

## Authentication

- `POST /api/v1/auth/register` creates a tenant + owner atomically and
  returns the user, tenant and a token pair.
- Login is **tenant-scoped**: `tenant_slug + email + password`.
- JWT claims: `sub` (user), `tid` (tenant), `role`, `typ`
  (`access`|`refresh`), `iat`, `exp`, `jti`. Access tokens live 30 minutes;
  refresh tokens 14 days.
- Refresh rotates: the client swaps the pair on 401 once, then gives up and
  returns the user to the login screen.

## Frontend architecture

- **Design system** (`components/ui.tsx`): buttons, fields, cards, badges,
  dialogs (native `<dialog>` for built-in focus management), toasts.
- **Theming**: CSS variables (`data-theme="light|dark"`) + Tailwind 4
  `@theme inline`. The tenant accent colour is injected at runtime via
  `applyBranding()` — validated as a 6-digit hex so it cannot smuggle CSS.
- **Data**: TanStack Query owns server state; mutations invalidate the
  related keys (`dashboard`, `reports`, `transactions`, `budgets`).
- **Auth**: `AuthProvider` persists the session in `localStorage` and wires
  the fetch client's token accessors; `ProtectedRoute` / `PublicOnlyRoute`
  gate the routes.
- **Accessibility**: WCAG 2.2 AA posture — labels on controls, visible
  focus rings, `aria-live` toasts, progressbar roles, charts carry text
  labels, reduced-motion honoured.

## Operations

- `docker compose up --build -d` is the whole deployment.
- The backend entrypoint waits for Postgres, runs `alembic upgrade head`
  and starts Uvicorn with proxy headers enabled.
- Health: `/healthz` (liveness) and `/readyz` (DB round-trip).
- `SEED_DEMO=true` (default in compose) seeds a demo tenant on first boot.
- Scaling path: backend is stateless (JWT + DB), so run N replicas behind
  the proxy; move the rate limiter to Redis when running >1 replica.
