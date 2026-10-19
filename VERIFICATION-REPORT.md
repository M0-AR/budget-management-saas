# Budgetary — Verification & Enhancement Report

**Date:** 2026-10-19 · **Stack:** FastAPI + PostgreSQL (RLS) backend, React 19 + Vite + Tailwind v4 frontend, Caddy edge, Docker Compose
**Scope:** Zero-to-hero audit of every feature, research-backed gap analysis, fixes, and new features (household members/invites, CSV import)

---

## 1. Executive summary

The product was verified end-to-end against a running stack (`http://localhost:8085`) using three independent chains of evidence:

1. **Backend:** 38/38 pytest green (28 pre-existing + 8 CSV-import tests + 2 finance-update audit regression tests), run inside the production Docker image after `docker compose up -d --build backend`.
2. **Contract/E2E:** `scripts/e2e.sh` — extends from health to two-tenant isolation to CSV import — prints `ALL E2E CHECKS PASSED ✔`.
3. **Browser:** Playwright walkthroughs of every page in both themes, with screenshots archived in `/home/md/src/.playwright-mcp/`.

Two capabilities that the market analysis identified as missing were added and verified:

- **Household sharing (members & invites)** — the single most requested gap in family budgeting (see §6), implemented with separate logins per person, per-tenant roles (owner/admin/member/viewer), and full invite lifecycle.
- **CSV import** — round-trips the product's own export format, with row-level validation, duplicate skipping, automatic category creation and full audit trail.

A **P0 security hardening set** (refresh-token rotation with reuse detection, forced RLS, HttpOnly refresh cookies, auth rate limiting, HSTS, CI) was implemented and verified live.

The demo workspace ships a rolling **8-month household story** (Alex and Maya Rivera): $3,297.56 spent of a $3,150 budget in the current month (Over budget, 104.7% utilization, 15 categories, 23 income deposits and 243 expenses). Zero console errors across every verified flow.

---

## 2. Verification method

| Layer | Command | Result |
|---|---|---|
| Backend tests | `docker compose exec backend sh -c "pip install -q -r requirements-dev.txt; python -m pytest -q"` | **38 passed** |
| E2E contract | `BASE=http://localhost:8085 bash scripts/e2e.sh` | **ALL E2E CHECKS PASSED ✔** |
| Frontend build | `npm run build` (tsc --noEmit && vite build) | green, 814.94 kB bundle (240.87 kB gzip) |
| Browser | Playwright MCP, light + dark themes | screenshots in `.playwright-mcp/` |
| Docs & preview | static link/HTML checks + Playwright preview QA | 69 unique ids, 0 missing local files or bad anchors, console clean |

E2E sections: health · two-tenant registration · login · budget/category/expense CRUD · **cross-tenant isolation (404 on foreign IDs, 0 rows visible)** · unauthenticated 401 · reports · **CSV import (mixed expense/income)**.

Preview-specific checks: at 1440 px, `#buyers` lands at 87.6 px against a sticky nav bottom of 69 px; at 390 px it lands at 88.5 px against the same 69 px nav. The 390 px mobile nav shows Buyers, Quiz and Get started (header right 355 px, document scroll width 375 px, no horizontal overflow); the 360 px layout also fits (scroll width 345 px). The 10-question quiz reaches 10/10 Pro, and the nine-image lightbox opens and closes.

---

## 3. Verified feature inventory

- **Auth & tenancy:** register/login/refresh/logout, tenant slug resolution with branded login preview, tokens kept in memory only (refresh in HttpOnly `bms_refresh` cookie), boot restore gate ("Restoring your session…"), 401-driven silent refresh.
- **Budgets:** monthly upsert, alert threshold, utilization + status badges (on track / approaching / over), **spending pace line** ("Day 19 of 31 · ≈$1,716.13 expected · $1,095.17 behind pace"), **undo** of budget changes via toast action (verified 3000→3100→undo).
- **Expenses / Income:** CRUD with category picker, note search, year/month/category filters, pagination totals, delete confirmation, inline edit.
- **Categories:** full management UI (create/edit/delete, colors), usage-aware deletes.
- **Reports:** monthly + yearly, category shares, 6-month trend chart, CSV export (spreadsheet-injection safe: `=+-@` prefixed with `'`).
- **CSV import (new):** see §5.
- **Members & invites (new):** see §4.
- **Settings:** branding (display name/accent/logo — display name now drives the in-app header and sidebar), currency/locale/timezone, Members tab, Categories tab, Preferences; live preview card.
- **Shell:** command palette (⌘K), theme toggle (light/dark), collapsible sidebar, toasts, 404 route, empty states, responsive layouts (mobile verified on Expenses).

---

## 4. Feature added — Members, roles & invites

- **Backend:** `invites` table (migration `20261018_0003_invites.py`), `POST/GET/DELETE /api/v1/members/invites`, role changes, member removal; invite tokens are hashed at rest; accept flow via `/register?invite=…`. Mutations are admin-only (`require_admin`); listing is member-visible.
- **Roles:** owner / admin / member / **viewer**. Viewers are read-only across the UI (Add/Edit/Import hidden via `canWrite`) and enforced server-side (403s covered by tests).
- **Frontend:** Settings → Members tab (roster, role select, remove, pending invites with copy-link and revoke). One real-world defect was found during browser verification and fixed: revoking an invite now clears the "Link ready" copy box immediately (`MembersPanel` revoke `onSuccess` clears matching `issued` state).
- **Verified:** invite → join → role change → remove; revoke → link box disappears; pending list empties. Cross-tenant safety covered by the isolation tests.

## 5. Feature added — CSV import

**Endpoint:** `POST /api/v1/imports/transactions` (multipart `file`; query `kind=expense|income`, `skip_duplicates=true|false`; requires writer role).

- **Format:** round-trips our export — `date,type,category,note,amount`. Header aliases accepted (`happened_on`/`transaction_date`/`posted`, `value`/`total`, `description`/`memo`, `kind`). Dates: `%Y-%m-%d`, `%m/%d/%Y`, `%m/%d/%y`. Amounts may include `$` and commas; must be positive, ≤ 1e12.
- **Guards:** 1 MiB max file, 1000 max rows, 20 errors reported, UTF-8 BOM tolerated, `, ; \t` delimiters sniffed.
- **Duplicate skip:** a row matching an existing entry (same kind, date, amount, note) is skipped; within-file duplicates both import (documented behavior).
- **Categories:** unknown names auto-create (case-insensitive match, audited `category.created` with `source: "csv_import"`); blank/"Uncategorized"/"-" map to none.
- **Audit:** one `transactions.imported` record per batch (entity_type `import`) with the full summary.
- **UI:** "Import" button (hidden for viewers) opens a dialog — file picker with format hints, skip-duplicates checkbox (default on), and a result view: added/skipped/failed counts, new-category note, and a "Line N — message" error list. Query caches are invalidated for transactions/categories/dashboard/reports.

**Evidence:** 8 pytest cases (happy mixed import, aliases/formats, partial failure rows, dedupe, missing columns, row limit, viewer 403, export→import round-trip) + e2e section 8 (`imported 1 expense row`, `imported 1 income row`, totals reconcile) + browser runs on a scratch tenant (fresh import: 2 added / 1 failed with line error / 1 category created; re-import: 0 added / 2 skipped). Screenshots: `import-summary-first.png`, `import-summary-duplicates.png`.

---

## 6. Security posture (research-anchored)

Implemented and verified live:

- **Tenant isolation:** Postgres **row-level security** on every tenant table, pinned per request via session GUC; app role cannot bypass RLS. Cross-tenant probes return 404 / empty sets (e2e §5). Aligned with the **OWASP Multi-Tenant Security Cheat Sheet** — tenant context scoped to the transaction, no RLS-bypassing role on request paths, explicit "verify tenant isolation" testing (https://cheatsheetseries.owasp.org/cheatsheets/Multi_Tenant_Security_Cheat_Sheet.html).
- **Session handling:** refresh-token **rotation with reuse detection** (family revoke), tokens hashed at rest, refresh token delivered as **HttpOnly, SameSite cookie**, access token memory-only. This follows the industry guidance on multi-tenant session management (https://workos.com/blog/multi-tenant-session-management).
- **Rate limiting:** stricter tier on auth endpoints (15/min/IP; configurable), plus global limiter.
- **Transport:** HSTS via Caddy; secure cookie flags.
- **Accessibility:** WCAG 2.2 AA targets, including 2.5.8 target-size and focus management (https://www.w3.org/TR/WCAG22/).
- **CI:** GitHub Actions workflow builds, lints and runs the full test suite.

---

## 7. Market & research context (cited)

- **Household sharing with separate logins is the #1 expectation.** Monarch's couples feature is explicitly "each person will have their own login … contribute to a shared space" (https://help.monarch.com/hc/en-us/articles/20926382202004-Monarch-for-Couples-and-Households; https://www.monarch.com/for-couples). Budgetary now matches this with roles + invites.
- **Envelope/rollover budgeting is table stakes.** Actual Budget's core mechanics are rollover of positive *and* overspent balances (https://actualbudget.org/docs/budgeting) — see §8 for our roadmap.
- **Undo is a differentiator.** Monarch users report there is no way to recover prior category assignments after a mis-applied rule (https://www.reddit.com/r/MonarchMoney/comments/11uueuw/accidentally_applied_new_rule_to_all_transactions). Budgetary ships undo for budget changes today.
- **Apps measurably improve financial capability.** French, McKillop & Stewart, "The effectiveness of smartphone apps in improving financial capability", *The European Journal of Finance* 26(4–5), 302–318 — first study to assess app-driven behavior change (https://ideas.repec.org/a/taf/eurjfi/v26y2020i4-5p302-318.html); follow-up on low-income households: French et al., *Strategic Change* (2021), https://onlinelibrary.wiley.com/doi/10.1002/jsc.2430.

---

## 8. Remaining gaps & suggested roadmap

Ranked by expected user impact:

1. **Category rollover / sinking funds** — carry positive and negative balances month to month (the Actual Budget bar in §7).
2. **Recurring transactions & subscriptions view**.
3. **Tags + saved filter views** for cross-cutting analysis.
4. **Savings goals** (targets with progress) — heavily requested in every competitor's feedback forum.
5. **Bank aggregation** (Plaid-style) — deliberately out of scope; CSV import covers the manual path.
6. **Command-palette import entry** and keyboard-first add-flow (polish).

Accepted cosmetic nits (documented, not blocking): a stray zero-value axis label on the trend chart from recharts; demo seed quirks; Budgets page a11y landmark name "Octobercurrent"; dense empty 2027 report grid.

---

## 9. Evidence index

- **Tests:** `backend/tests/` — auth, isolation, budgets, transactions, categories, reports, members (28) + imports (8) + finance-update regressions (2) = 38.
- **E2E:** `scripts/e2e.sh` (8 sections incl. import).
- **Screenshots:** `/home/md/src/.playwright-mcp/` — `members-readonly-member-view.png`, `members-tab-demo-owner.png`, `categories-tab-verified.png`, `budgets-pace-undo-verified.png`, `import-summary-first.png`, `import-summary-duplicates.png`.
- **CLI tutorial deliverable:** `cli/budget_system.py` (standalone Python CLI budget tutorial, separate from the SaaS).
