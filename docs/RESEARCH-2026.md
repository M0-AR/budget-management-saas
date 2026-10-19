# Research Notes (2026)

Every architectural decision below was checked against a primary source
before coding. The sources are listed with what each one settled.

## Sources

1. **ClickHouse — "Multi-tenant SaaS with Postgres" architecture guide**
   https://clickhouse.com/resources/engineering/multi-tenant-saas-postgres-architecture
   → Confirmed the shared-schema + `tenant_id` + RLS pattern as the
   default for early-stage SaaS, with per-tenant schemas/databases as a
   later escape hatch. Drove decision: FORCE RLS with a transaction-scoped
   `set_config` tenant context, because it makes the database itself the
   isolation boundary.

2. **Designveloper — front-end framework comparison (2026)**
   https://www.designveloper.com/blog/front-end-frameworks/
   → React remains the safest ecosystem bet for a product UI (hiring,
   component libraries, tooling). Drove decision: React 19 + TypeScript +
   Vite.

3. **ChromUI — SaaS design system guide**
   https://chromui.app/guides/saas-design-system
   → Token-first design systems with a single accent variable, semantic
   status colours that are never re-mapped, and dark mode as a first-class
   theme. Drove decisions: Tailwind 4 `@theme inline` tokens, runtime
   `--accent` injection, `data-theme` switcher, charts that never rely on
   colour alone.

4. **VipraSol — white-label SaaS implementation guide**
   https://viprasol.com/blog/saas-white-label/
   → Per-tenant branding must be resolvable *before login* (login page
   theming) and must be input-validated before it reaches CSS. Drove
   decisions: public `GET /settings/public/{slug}` endpoint, hex-validated
   accent colour, cached pre-paint branding bootstrap in `index.html`.

5. **eugeneliukindev — FastAPI clean layered architecture example**
   https://github.com/eugeneliukindev/fastapi-clean-layered-arch-example
   → Confirmed the api / services / repositories / schemas / models split
   keeps tenancy and business rules testable. Drove decision: all
   tenant-scoped data access flows through one repository layer where the
   RLS context is guaranteed set.

## Decisions locked by research

| Decision | Source |
| --- | --- |
| Shared schema + FORCE RLS + `set_config` per transaction | 1 |
| React 19 + TS + Vite as the frontend stack | 2 |
| Token-first design system, runtime accent, WCAG AA | 3 |
| Pre-login branding endpoint + validated accent input | 4 |
| Layered FastAPI structure with a single tenancy choke point | 5 |

## Dependency versions verified live

Backend pins (checked against PyPI at build time): FastAPI 0.146.0,
Uvicorn 0.54.0, SQLAlchemy 2.1.5, asyncpg 0.32.0, Alembic 1.20.0,
Pydantic 2.14.1, PyJWT 2.15.1, bcrypt 5.0.0.

Frontend pins (checked against npm at build time): React 19.3.1,
react-router-dom 7.18.4, TanStack Query 5.104.4, Recharts 3.10.1,
Vite 8.3.4, TypeScript 5.9.3 (deliberately the stable 5.x line rather
than the 6.x preview), Tailwind CSS 4.3.3.
