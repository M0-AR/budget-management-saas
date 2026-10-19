import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { useNavigate } from "react-router-dom";
import {
  BarChart3,
  CornerDownLeft,
  LayoutDashboard,
  LogOut,
  Moon,
  PiggyBank,
  Search,
  Settings,
  Sun,
  Target,
  Wallet,
  type LucideIcon,
} from "lucide-react";

import { useAuth } from "../lib/auth";
import { useTheme } from "../lib/theme";
import { cn } from "../lib/utils";
import { Kbd } from "./ui";

export const NAV_ITEMS = [
  { to: "/app", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/app/expenses", label: "Expenses", icon: Wallet, end: false },
  { to: "/app/income", label: "Income", icon: PiggyBank, end: false },
  { to: "/app/budgets", label: "Budgets", icon: Target, end: false },
  { to: "/app/reports", label: "Reports", icon: BarChart3, end: false },
  { to: "/app/settings", label: "Settings", icon: Settings, end: false },
] as const;

interface PaletteItem {
  id: string;
  group: "Pages" | "Actions";
  label: string;
  icon: LucideIcon;
  hint?: string;
  run: () => void;
}

function fuzzyScore(query: string, text: string): number {
  if (!query) return 1;
  const q = query.toLowerCase();
  const t = text.toLowerCase();
  let score = 0;
  let index = 0;
  for (const character of q) {
    const found = t.indexOf(character, index);
    if (found === -1) return 0;
    score += found === index ? 2 : 1;
    index = found + 1;
  }
  return score;
}

export function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const { resolved, toggle } = useTheme();
  const { logout } = useAuth();
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);

  const items = useMemo<PaletteItem[]>(
    () => [
      ...NAV_ITEMS.map(({ to, label, icon }) => ({
        id: `nav:${to}`,
        group: "Pages" as const,
        label,
        icon,
        run: () => navigate(to),
      })),
      {
        id: "action:theme",
        group: "Actions",
        label: resolved === "dark" ? "Switch to light theme" : "Switch to dark theme",
        icon: resolved === "dark" ? Sun : Moon,
        run: toggle,
      },
      {
        id: "action:logout",
        group: "Actions",
        label: "Sign out",
        icon: LogOut,
        run: () => {
          logout();
          navigate("/login", { replace: true });
        },
      },
    ],
    [navigate, resolved, toggle, logout],
  );

  const filtered = useMemo(() => {
    const scored = items
      .map((item) => ({ item, score: fuzzyScore(query, item.label) }))
      .filter((entry) => entry.score > 0);
    if (query) scored.sort((a, b) => b.score - a.score);
    return scored.map((entry) => entry.item);
  }, [items, query]);

  useEffect(() => {
    if (open) {
      setQuery("");
      setActive(0);
    }
  }, [open]);

  useEffect(() => {
    setActive(0);
  }, [query]);

  useEffect(() => {
    if (!open) return undefined;
    const previous = document.activeElement as HTMLElement | null;
    return () => previous?.focus?.();
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const node = listRef.current?.querySelector('[data-active="true"]');
    node?.scrollIntoView({ block: "nearest" });
  }, [active, open]);

  if (!open) return null;

  const runItem = (item: PaletteItem) => {
    onClose();
    item.run();
  };

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((current) => Math.min(current + 1, filtered.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((current) => Math.max(current - 1, 0));
    } else if (event.key === "Enter") {
      event.preventDefault();
      const item = filtered[active];
      if (item) runItem(item);
    } else if (event.key === "Escape") {
      event.preventDefault();
      onClose();
    }
  };

  let lastGroup = "";

  return (
    <div
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
      className="fixed inset-0 z-50 flex items-start justify-center px-4 pt-[16vh]"
    >
      <div aria-hidden className="animate-fade-in absolute inset-0 bg-overlay backdrop-blur-[2px]" />
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        className="animate-zoom-in relative w-full max-w-lg overflow-hidden rounded-2xl border border-line bg-surface-1 shadow-lg"
      >
        <div className="flex items-center gap-2.5 border-b border-line px-4">
          <Search className="size-4 shrink-0 text-ink-muted" aria-hidden />
          <input
            ref={inputRef}
            autoFocus
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Search pages and actions…"
            aria-label="Search commands"
            className="h-12 w-full bg-transparent text-sm text-ink outline-none placeholder:text-ink-muted/60"
          />
          <Kbd>esc</Kbd>
        </div>

        {filtered.length === 0 ? (
          <p className="px-4 py-10 text-center text-sm text-ink-muted">
            No matches for “{query}”.
          </p>
        ) : (
          <ul
            ref={listRef}
            role="listbox"
            aria-label="Commands"
            className="max-h-80 overflow-y-auto p-2"
          >
            {filtered.map((item, index) => {
              const header = item.group !== lastGroup ? item.group : null;
              lastGroup = item.group;
              const isActive = index === active;
              const Icon = item.icon;
              return (
                <li key={item.id}>
                  {header ? (
                    <p className="px-3 pt-3 pb-1 text-[11px] font-semibold tracking-wide text-ink-muted uppercase">
                      {header}
                    </p>
                  ) : null}
                  <button
                    type="button"
                    role="option"
                    aria-selected={isActive}
                    data-active={isActive}
                    onMouseMove={() => setActive(index)}
                    onClick={() => runItem(item)}
                    className={cn(
                      "flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm transition-colors",
                      isActive ? "bg-surface-2 text-ink" : "text-ink-muted",
                    )}
                  >
                    <Icon className="size-4 shrink-0" aria-hidden />
                    <span className="min-w-0 flex-1 truncate">{item.label}</span>
                    {isActive ? (
                      <CornerDownLeft className="size-3.5 shrink-0 text-ink-muted" aria-hidden />
                    ) : null}
                  </button>
                </li>
              );
            })}
          </ul>
        )}

        <div className="flex items-center gap-4 border-t border-line bg-surface-2/40 px-4 py-2.5 text-[11px] text-ink-muted">
          <span className="flex items-center gap-1.5">
            <Kbd>↑</Kbd>
            <Kbd>↓</Kbd> navigate
          </span>
          <span className="flex items-center gap-1.5">
            <Kbd>↵</Kbd> open
          </span>
          <span className="ml-auto flex items-center gap-1.5">
            <Kbd>⌘K</Kbd> toggle
          </span>
        </div>
      </div>
    </div>
  );
}
