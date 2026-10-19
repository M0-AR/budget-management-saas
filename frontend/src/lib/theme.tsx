import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { isHexColor } from "./utils";

export type ThemeMode = "light" | "dark" | "system";

const THEME_KEY = "bms.theme";
const BRANDING_KEY = "bms.branding";

export interface BrandingInput {
  accent_color?: string | null;
  display_name?: string;
}

function systemPrefersDark(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function readMode(): ThemeMode {
  try {
    const stored = localStorage.getItem(THEME_KEY);
    if (stored === "light" || stored === "dark" || stored === "system") return stored;
  } catch {
    /* storage unavailable */
  }
  return "system";
}

function resolve(mode: ThemeMode): "light" | "dark" {
  if (mode === "system") return systemPrefersDark() ? "dark" : "light";
  return mode;
}

/** Apply (or clear) the workspace accent colour. Validated to prevent CSS injection. */
export function applyBranding(branding: BrandingInput | null): void {
  const root = document.documentElement;
  if (branding && isHexColor(branding.accent_color ?? undefined)) {
    root.style.setProperty("--accent", branding.accent_color as string);
  } else {
    root.style.removeProperty("--accent");
  }
  try {
    if (branding) {
      localStorage.setItem(
        BRANDING_KEY,
        JSON.stringify({ accent_color: branding.accent_color ?? null, display_name: branding.display_name ?? "" }),
      );
    } else {
      localStorage.removeItem(BRANDING_KEY);
    }
  } catch {
    /* storage unavailable */
  }
}

interface ThemeContextValue {
  mode: ThemeMode;
  resolved: "light" | "dark";
  setMode: (mode: ThemeMode) => void;
  toggle: () => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<ThemeMode>(readMode);
  const [resolved, setResolved] = useState<"light" | "dark">(() => resolve(readMode()));

  useEffect(() => {
    const next = resolve(mode);
    setResolved(next);
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem(THEME_KEY, mode);
    } catch {
      /* storage unavailable */
    }
  }, [mode]);

  useEffect(() => {
    if (mode !== "system") return undefined;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const listener = () => {
      const next = resolve("system");
      setResolved(next);
      document.documentElement.dataset.theme = next;
    };
    media.addEventListener("change", listener);
    return () => media.removeEventListener("change", listener);
  }, [mode]);

  const setMode = useCallback((next: ThemeMode) => setModeState(next), []);
  const toggle = useCallback(() => {
    setModeState((current) => (resolve(current) === "dark" ? "light" : "dark"));
  }, []);

  const value = useMemo<ThemeContextValue>(
    () => ({ mode, resolved, setMode, toggle }),
    [mode, resolved, setMode, toggle],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext);
  if (!context) throw new Error("useTheme must be used inside <ThemeProvider>");
  return context;
}
