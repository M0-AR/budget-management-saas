import type { ReactNode } from "react";
import { BarChart3, Landmark, Moon, ShieldCheck, Sparkles, Sun } from "lucide-react";

import { useTheme } from "../lib/theme";

const FEATURES = [
  {
    icon: BarChart3,
    title: "Budgets that warn before you overspend",
    body: "Monthly limits, live utilization and threshold alerts on every workspace.",
  },
  {
    icon: ShieldCheck,
    title: "Every workspace isolated by design",
    body: "Postgres row-level security pins each request to its tenant — no leaks, ever.",
  },
  {
    icon: Sparkles,
    title: "White-label ready",
    body: "Your colours, your currency, your timezone — applied across the entire app.",
  },
] as const;

export function AuthLayout({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  const { resolved, toggle } = useTheme();

  return (
    <div className="grid min-h-dvh lg:grid-cols-[1.05fr_1fr]">
      <aside className="relative hidden flex-col justify-between overflow-hidden bg-accent p-10 text-accent-contrast lg:flex xl:p-12">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0"
          style={{
            backgroundImage:
              "linear-gradient(rgb(255 255 255 / 0.07) 1px, transparent 1px), linear-gradient(90deg, rgb(255 255 255 / 0.07) 1px, transparent 1px)",
            backgroundSize: "2.25rem 2.25rem",
            maskImage: "radial-gradient(60rem 60rem at 25% 15%, black, transparent 78%)",
            WebkitMaskImage: "radial-gradient(60rem 60rem at 25% 15%, black, transparent 78%)",
          }}
        />
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              "radial-gradient(42rem 42rem at 12% -10%, rgb(255 255 255 / 0.18), transparent 60%), radial-gradient(36rem 36rem at 110% 110%, rgb(255 255 255 / 0.14), transparent 55%)",
          }}
        />
        <div className="relative z-10 flex items-center gap-3">
          <div className="flex size-11 items-center justify-center rounded-2xl border border-white/20 bg-white/10 backdrop-blur">
            <Landmark className="size-5" aria-hidden />
          </div>
          <div>
            <p className="text-lg font-bold tracking-tight">Budgetary</p>
            <p className="text-xs opacity-80">Multi-tenant budget management</p>
          </div>
        </div>

        <div className="relative z-10 max-w-md space-y-8">
          <h2 className="text-3xl leading-tight font-semibold tracking-tight">
            One platform. Every team gets its own workspace.
          </h2>
          <ul className="space-y-5">
            {FEATURES.map(({ icon: Icon, title, body }) => (
              <li key={title} className="flex gap-3">
                <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-xl bg-white/15">
                  <Icon className="size-4" aria-hidden />
                </span>
                <div>
                  <p className="text-sm font-semibold">{title}</p>
                  <p className="text-xs leading-relaxed opacity-80">{body}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>

        <p className="relative z-10 text-xs opacity-70">
          Budgetary · Self-serve workspaces · RBAC · Audit trail
        </p>
      </aside>

      <main className="relative flex items-center justify-center bg-surface-0 px-4 py-10 sm:px-8">
        <button
          type="button"
          onClick={toggle}
          aria-label={resolved === "dark" ? "Switch to light theme" : "Switch to dark theme"}
          className="absolute top-4 right-4 rounded-lg border border-line bg-surface-1 p-2 text-ink-muted transition hover:bg-surface-2 hover:text-ink sm:top-6 sm:right-6"
        >
          {resolved === "dark" ? (
            <Sun className="size-4" aria-hidden />
          ) : (
            <Moon className="size-4" aria-hidden />
          )}
        </button>
        <div className="animate-rise w-full max-w-md">
          <div className="mb-8 lg:hidden">
            <div className="flex items-center gap-2.5">
              <div className="flex size-10 items-center justify-center rounded-2xl bg-accent text-accent-contrast">
                <Landmark className="size-5" aria-hidden />
              </div>
              <p className="text-lg font-bold tracking-tight">Budgetary</p>
            </div>
          </div>
          <h1 className="text-2xl font-semibold tracking-tight text-ink">{title}</h1>
          {subtitle ? <p className="mt-1.5 text-sm text-ink-muted">{subtitle}</p> : null}
          <div className="mt-7">{children}</div>
        </div>
      </main>
    </div>
  );
}
