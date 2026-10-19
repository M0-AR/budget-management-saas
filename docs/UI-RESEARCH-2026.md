# UI Research 2026 — Design Brief

Verified findings that drive the frontend redesign. Every rule below was sourced
from live research (August–October 2026) before any UI file was edited, per the
project's verify-first mandate.

## Sources consulted

| Tool | Query theme | Key takeaway used |
| --- | --- | --- |
| exa websearch | SaaS dashboard design trends 2026 | Mobbin study of 2,108 real dashboards: restraint, verdict-first layout |
| exa websearch | WCAG 3 / APCA contrast 2026 | WCAG 2.2 is normative; 4.5:1 text, 3:1 non-text; plan for APCA |
| DuckDuckGo | best finance apps UI 2026 (Monarch, Copilot, YNAB) | Numbers in context, plain-language verdicts, calm density |
| free-search (multi-engine) | Base UI vs Radix vs shadcn 2026 | Base UI 1.0 stable (Feb 2026); shadcn/ui default switched to Base UI (Jul 2026) |
| openresearch web search | Base UI 1.0 headless components | 35 accessible primitives by MUI/Radix/Floating-UI maintainers |
| agent-reach search | OKLCH design tokens / white-label | 3-tier token architecture, DTCG spec, dark mode as parallel system |
| paper-search (OpenAlex) | dashboard design patterns research | Bach et al. — dashboarddesignpatterns.github.io patterns (verdict first, annotate data) |
| gitmcp (shadcn-ui/ui docs) | component catalog 2026 | Sidebar, Command, Sonner, Empty, Skeleton, Data Table, Chart, Field |
| free-search search | micro-interaction timing 2026 | 150–200 ms interactions, ease-out entrances, fewer purposeful motions |
| free-search fetch_batch | mobbin + dashboarddesignpatterns.github.io | "So what?" summaries, direct labels over legends, designed empty states |

`gsd_websearch` was unavailable (no Brave key) and searxng has no MCP server in
this environment; the fallback chain (free-search multi-engine, openresearch)
covered the same ground.

## Binding decisions

### 1. Tokens — 3-tier, OKLCH, dark as a parallel system

- Tier 1 *primitives* → Tier 2 *semantic* (`--surface-*`, `--ink*`, `--line`,
  `--accent`, `--success|warning|danger`) → Tier 3 *component derivations*
  (`*-soft` mixes, ring, shadows).
- All colours expressed in **OKLCH** (perceptually uniform, easier to keep
  contrast while allowing white-label accents).
- Dark theme is a full parallel value set, not an inversion: elevated surfaces
  get *lighter* (luminance steps), near-black is avoided, accents are lifted.
- White-label override surface stays minimal: **accent colour, logo, radius
  personality**. Status colours are never tenant-overridable.
- Flash-free first paint: the inline blocking script in `index.html` (already
  present) continues to set `data-theme` + accent before CSS executes.

### 2. Typography

- Self-hosted **Inter Variable** (`@fontsource-variable/inter`); CSP stays
  `font-src 'self'`, no CDN and no third-party requests.
- Tabular numerals (`.tnum`) mandatory on every money figure, table column and
  chart axis.
- `text-wrap: balance` on headings; tighter tracking on display sizes.

### 3. Layout & density

- Collapsible sidebar, **240–280 px wide → 72 px rail**, state persisted.
- Sticky glass topbar, **56 px**; page headers live in content.
- 12-column grid; content column capped (max-w-6xl) so KPIs stay scannable.
- Density over decoration: 1 px borders, radii 6–16 px, shadows only for
  elevation (dialogs, popovers, toasts) — cards get hairline shadows.

### 4. Colour discipline

- **One accent.** Colour communicates *status* only: success / warning / danger.
- Never colour alone: status always carries a text label and/or dot; category
  swatches always sit next to names.
- Charts keep text labels/legends and `role="img"` + `aria-label` summaries.

### 5. Dashboard craft (verdict-first)

- A hero block answers "so what?": status badge, headline number, plain-language
  verdict, budget context, 6-month sparkline.
- KPIs carry period deltas (spend/income vs previous month) and context lines.
- First-run is a designed onboarding card, not empty charts.
- Empty / loading / error are all designed states (shimmer skeletons matching
  final layout).

### 6. Motion

- 150–200 ms interactions (global Tailwind default set to 160 ms), ease-out
  entrances (`cubic-bezier(0.22, 1, 0.36, 1)`).
- Motion limited to: dialog zoom-fade, drawer slide, toast rise, skeleton
  shimmer, progress width. All respect `prefers-reduced-motion`.

### 7. Accessibility (WCAG 2.2 normative)

- Text ≥ 4.5:1, non-text UI and chart strokes ≥ 3:1 (verified against the
  OKLCH palette; dark accent lifted for this reason).
- Visible focus rings via `:focus-visible` + accent ring tokens.
- Command palette (⌘K) is a full dialog: focus moves in, restores on close,
  ArrowUp/Down/Enter/Esc keyboard model.

### 8. Signature interactions (2026 credibility)

- ⌘K command palette (Linear/Stripe pattern) covering navigation + actions.
- Collapsible rail sidebar with persisted state.
- Sonner-style toasts with close affordance and countdown progress.
- Sparklines for trend context where full charts are too heavy.
