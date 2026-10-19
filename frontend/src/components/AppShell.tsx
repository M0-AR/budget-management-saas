import { useCallback, useEffect, useState, type ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import {
  Landmark,
  LogOut,
  Menu,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
  Sun,
  X,
} from "lucide-react";

import { useAuth } from "../lib/auth";
import { useTheme } from "../lib/theme";
import { cn } from "../lib/utils";
import { CommandPalette, NAV_ITEMS } from "./CommandPalette";
import { Badge, Kbd } from "./ui";

const SIDEBAR_KEY = "bms.sidebar";

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

function SidebarContent({
  collapsed,
  onNavigate,
}: {
  collapsed: boolean;
  onNavigate?: () => void;
}) {
  const { user, tenant, logout } = useAuth();
  const navigate = useNavigate();
  const brandingName =
    typeof tenant?.branding?.display_name === "string" ? tenant.branding.display_name.trim() : "";
  const workspaceName = brandingName || tenant?.name || "Budgetary";

  const signOut = () => {
    logout();
    navigate("/login", { replace: true });
  };

  return (
    <div className="flex h-full flex-col gap-1 p-3">
      {collapsed ? (
        <div className="flex justify-center pb-3">
          <div
            title={workspaceName}
            className="flex size-10 items-center justify-center rounded-xl bg-accent text-accent-contrast"
          >
            <Landmark className="size-5" aria-hidden />
          </div>
        </div>
      ) : (
        <div className="flex items-center gap-3 px-1 pb-3">
          <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-accent text-accent-contrast">
            <Landmark className="size-5" aria-hidden />
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold tracking-tight">
              {workspaceName}
            </p>
            <div className="mt-0.5 flex items-center gap-1.5">
              <span className="truncate text-xs text-ink-muted">/{tenant?.slug}</span>
              {tenant ? <Badge tone="neutral">{tenant.tier}</Badge> : null}
            </div>
          </div>
        </div>
      )}

      <nav aria-label="Main" className={cn("flex flex-1 flex-col gap-1", collapsed && "items-center")}>
        {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            onClick={onNavigate}
            title={collapsed ? label : undefined}
            className={({ isActive }) =>
              cn(
                "relative flex items-center rounded-lg font-medium transition-colors",
                collapsed ? "size-10 justify-center" : "gap-3 px-3 py-2 text-sm",
                isActive
                  ? "bg-surface-2 text-ink"
                  : "text-ink-muted hover:bg-surface-2 hover:text-ink",
              )
            }
          >
            {({ isActive }) => (
              <>
                <Icon className={cn("size-4 shrink-0", isActive && "text-ink")} aria-hidden />
                {collapsed ? <span className="sr-only">{label}</span> : label}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <div className={cn("border-t border-line pt-3", collapsed && "flex flex-col items-center gap-1")}>
        {collapsed ? (
          <>
            <div
              title={user?.full_name || user?.email || ""}
              className="flex size-9 items-center justify-center rounded-full bg-surface-3 text-xs font-semibold text-ink-muted"
            >
              {initials(user?.full_name ?? user?.email ?? "?")}
            </div>
            <button
              type="button"
              onClick={signOut}
              aria-label="Sign out"
              title="Sign out"
              className="rounded-lg p-2 text-ink-muted transition hover:bg-danger-soft hover:text-danger"
            >
              <LogOut className="size-4" aria-hidden />
            </button>
          </>
        ) : (
          <div className="flex items-center gap-2 px-1">
            <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-surface-3 text-xs font-semibold text-ink-muted">
              {initials(user?.full_name ?? user?.email ?? "?")}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">{user?.full_name || user?.email}</p>
              <p className="truncate text-xs text-ink-muted capitalize">{user?.role}</p>
            </div>
            <button
              type="button"
              onClick={signOut}
              aria-label="Sign out"
              className="shrink-0 rounded-lg p-2 text-ink-muted transition hover:bg-danger-soft hover:text-danger"
            >
              <LogOut className="size-4" aria-hidden />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const { resolved, toggle } = useTheme();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem(SIDEBAR_KEY) === "rail";
    } catch {
      return false;
    }
  });

  const toggleCollapsed = useCallback(() => {
    setCollapsed((current) => {
      const next = !current;
      try {
        localStorage.setItem(SIDEBAR_KEY, next ? "rail" : "wide");
      } catch {
        /* storage unavailable */
      }
      return next;
    });
  }, []);

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPaletteOpen((current) => !current);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  return (
    <div className="min-h-dvh bg-surface-0">
      <a
        href="#main-content"
        className="sr-only rounded-lg bg-accent px-3 py-2 text-sm text-accent-contrast focus:not-sr-only focus:absolute focus:top-3 focus:left-3 focus:z-50"
      >
        Skip to content
      </a>

      {/* Desktop sidebar */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-30 hidden flex-col border-r border-line bg-surface-1 transition-[width] duration-200 lg:flex",
          collapsed ? "w-[4.5rem]" : "w-64",
        )}
      >
        <SidebarContent collapsed={collapsed} />
      </aside>

      <div className={cn("transition-[padding] duration-200", collapsed ? "lg:pl-[4.5rem]" : "lg:pl-64")}>
        {/* Top bar */}
        <header className="glass-header sticky top-0 z-30 border-b border-line">
          <div className="flex h-14 items-center gap-2 px-3 sm:px-4 lg:px-6">
            <button
              type="button"
              onClick={() => setMobileOpen(true)}
              aria-label="Open navigation"
              className="rounded-lg border border-line bg-surface-1 p-2 text-ink-muted transition hover:bg-surface-2 hover:text-ink lg:hidden"
            >
              <Menu className="size-4" aria-hidden />
            </button>
            <p className="text-sm font-bold tracking-tight lg:hidden">Budgetary</p>

            <button
              type="button"
              onClick={toggleCollapsed}
              aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              className="hidden rounded-lg p-2 text-ink-muted transition hover:bg-surface-2 hover:text-ink lg:inline-flex"
            >
              {collapsed ? (
                <PanelLeftOpen className="size-4" aria-hidden />
              ) : (
                <PanelLeftClose className="size-4" aria-hidden />
              )}
            </button>

            <div className="flex-1" />

            <button
              type="button"
              onClick={() => setPaletteOpen(true)}
              className="hidden h-9 w-56 items-center justify-between gap-2 rounded-lg border border-line bg-surface-1 px-3 text-sm text-ink-muted transition hover:bg-surface-2 hover:text-ink sm:flex"
            >
              <span className="flex items-center gap-2">
                <Search className="size-3.5" aria-hidden />
                Search…
              </span>
              <Kbd>⌘K</Kbd>
            </button>
            <button
              type="button"
              onClick={() => setPaletteOpen(true)}
              aria-label="Search"
              className="rounded-lg border border-line bg-surface-1 p-2 text-ink-muted transition hover:bg-surface-2 hover:text-ink sm:hidden"
            >
              <Search className="size-4" aria-hidden />
            </button>

            <button
              type="button"
              onClick={toggle}
              aria-label={resolved === "dark" ? "Switch to light theme" : "Switch to dark theme"}
              className="rounded-lg border border-line bg-surface-1 p-2 text-ink-muted transition hover:bg-surface-2 hover:text-ink"
            >
              {resolved === "dark" ? (
                <Sun className="size-4" aria-hidden />
              ) : (
                <Moon className="size-4" aria-hidden />
              )}
            </button>
          </div>
        </header>

        <main id="main-content" className="px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <div className="mx-auto w-full max-w-6xl">{children}</div>
        </main>
      </div>

      {/* Mobile slide-over */}
      {mobileOpen ? (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div
            className="animate-fade-in absolute inset-0 bg-overlay backdrop-blur-[2px]"
            onClick={() => setMobileOpen(false)}
            aria-hidden
          />
          <div className="animate-slide-in-left absolute inset-y-0 left-0 w-72 max-w-[85vw] border-r border-line bg-surface-1">
            <button
              type="button"
              onClick={() => setMobileOpen(false)}
              aria-label="Close navigation"
              className="absolute top-4 right-3 rounded-lg p-2 text-ink-muted transition hover:bg-surface-2 hover:text-ink"
            >
              <X className="size-4" aria-hidden />
            </button>
            <SidebarContent collapsed={false} onNavigate={() => setMobileOpen(false)} />
          </div>
        </div>
      ) : null}

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </div>
  );
}
