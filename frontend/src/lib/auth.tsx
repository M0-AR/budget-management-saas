import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { api, isTokenExpired, setTokenAccessors } from "./api";
import { applyBranding } from "./theme";
import type { AuthResponse, MeOut, TenantOut, TokenPair, UserOut } from "./types";

const STORAGE_KEY = "bms.auth";

/** What we persist locally: the short-lived access token only.
 *
 * The refresh token lives in an HttpOnly cookie (bms_refresh) that
 * JavaScript cannot read — so an XSS cannot exfiltrate a long-lived
 * credential. `user`/`tenant` start null when a session is restored from
 * the cookie on boot (filled from /auth/me immediately after). */
interface StoredAuth {
  user: UserOut | null;
  tenant: TenantOut | null;
  tokens: Pick<TokenPair, "access_token" | "token_type" | "expires_in">;
}

function toStoredTokens(pair: TokenPair): StoredAuth["tokens"] {
  return {
    access_token: pair.access_token,
    token_type: pair.token_type,
    expires_in: pair.expires_in,
  };
}

function loadStored(): StoredAuth | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<StoredAuth>;
    if (parsed?.tokens?.access_token) {
      return { user: parsed.user ?? null, tenant: parsed.tenant ?? null, tokens: parsed.tokens };
    }
  } catch {
    /* corrupted storage — treat as signed out */
  }
  return null;
}

export interface RegisterPayload {
  /** Omitted when registering via an invite link (joining a workspace). */
  tenant_name?: string;
  tenant_slug?: string;
  full_name: string;
  email: string;
  password: string;
  invite_token?: string;
}

interface AuthContextValue {
  status: "anonymous" | "authenticated";
  /** False while the boot-time cookie restore is still in flight. */
  ready: boolean;
  user: UserOut | null;
  tenant: TenantOut | null;
  login: (tenantSlug: string, email: string, password: string) => Promise<AuthResponse>;
  register: (payload: RegisterPayload) => Promise<AuthResponse>;
  logout: () => void;
  updateTenant: (tenant: TenantOut) => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [stored, setStored] = useState<StoredAuth | null>(loadStored);
  // Ready immediately only when the local session is fully usable; otherwise
  // the boot effect (cookie restore) must settle before routes may redirect.
  const [ready, setReady] = useState(() => {
    const initial = loadStored();
    return Boolean(
      initial?.user && initial.tokens.access_token && !isTokenExpired(initial.tokens.access_token),
    );
  });
  const storedRef = useRef<StoredAuth | null>(stored);
  storedRef.current = stored;
  const refreshInFlight = useRef<Promise<boolean> | null>(null);

  const persist = useCallback((next: StoredAuth | null) => {
    storedRef.current = next;
    setStored(next);
    try {
      if (next) localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      else localStorage.removeItem(STORAGE_KEY);
    } catch {
      /* storage unavailable */
    }
  }, []);

  /** Exchange the HttpOnly refresh cookie for a fresh token pair. */
  const refreshSession = useCallback(async (): Promise<boolean> => {
    if (refreshInFlight.current) return refreshInFlight.current;
    const run = (async (): Promise<boolean> => {
      try {
        const pair = await api.post<TokenPair>("/api/v1/auth/refresh", undefined, {
          skipAuth: true,
          skipRetry: true,
        });
        const latest = storedRef.current;
        persist({
          user: latest?.user ?? null,
          tenant: latest?.tenant ?? null,
          tokens: toStoredTokens(pair),
        });
        return true;
      } catch {
        return false;
      }
    })();
    refreshInFlight.current = run;
    try {
      return await run;
    } finally {
      refreshInFlight.current = null;
    }
  }, [persist]);

  const logout = useCallback(() => {
    // Revoke server-side (clears the cookie) without blocking the UI.
    void api
      .post("/api/v1/auth/logout", undefined, { skipAuth: true, skipRetry: true })
      .catch(() => undefined);
    persist(null);
    applyBranding(null);
  }, [persist]);

  const accessorsRegistered = useRef(false);
  if (!accessorsRegistered.current) {
    accessorsRegistered.current = true;
    setTokenAccessors({
      accessToken: () => storedRef.current?.tokens.access_token ?? null,
      refresh: refreshSession,
      onUnauthorized: () => logout(),
    });
  }

  // Session restore: if the local access token is gone/expired, the refresh
  // cookie may still be valid — swap it for a fresh pair, then reload the
  // profile if we do not have it cached.
  const booted = useRef(false);
  useEffect(() => {
    if (booted.current) return;
    booted.current = true;
    const access = storedRef.current?.tokens.access_token;
    if (access && !isTokenExpired(access) && storedRef.current?.user) {
      setReady(true);
      return;
    }
    void (async () => {
      try {
        const restored = await refreshSession();
        if (!restored || storedRef.current?.user) return;
        try {
          const me = await api.get<MeOut>("/api/v1/auth/me");
          const latest = storedRef.current;
          persist({
            user: me.user,
            tenant: me.tenant,
            tokens: latest?.tokens ?? { access_token: "", token_type: "bearer", expires_in: 0 },
          });
        } catch {
          /* still anonymous; the sign-in page takes over */
        }
      } finally {
        setReady(true);
      }
    })();
  }, [persist, refreshSession]);

  useEffect(() => {
    if (!stored?.tenant) return;
    const branding = stored.tenant.branding as
      | { accent_color?: string | null; display_name?: string }
      | undefined;
    applyBranding({
      accent_color: branding?.accent_color ?? null,
      display_name: branding?.display_name || stored.tenant.name,
    });
  }, [stored]);

  const login = useCallback(
    async (tenantSlug: string, email: string, password: string) => {
      const response = await api.post<AuthResponse>(
        "/api/v1/auth/login",
        { tenant_slug: tenantSlug.trim().toLowerCase(), email: email.trim(), password },
        { skipAuth: true, skipRetry: true },
      );
      persist({ user: response.user, tenant: response.tenant, tokens: toStoredTokens(response.tokens) });
      return response;
    },
    [persist],
  );

  const register = useCallback(
    async (payload: RegisterPayload) => {
      const response = await api.post<AuthResponse>(
        "/api/v1/auth/register",
        {
          ...payload,
          tenant_slug: payload.tenant_slug
            ? payload.tenant_slug.trim().toLowerCase()
            : undefined,
          email: payload.email.trim(),
        },
        { skipAuth: true, skipRetry: true },
      );
      persist({ user: response.user, tenant: response.tenant, tokens: toStoredTokens(response.tokens) });
      return response;
    },
    [persist],
  );

  const updateTenant = useCallback(
    (tenant: TenantOut) => {
      const current = storedRef.current;
      if (!current) return;
      persist({ ...current, tenant });
    },
    [persist],
  );

  const value = useMemo<AuthContextValue>(
    () => ({
      status: stored ? "authenticated" : "anonymous",
      ready,
      user: stored?.user ?? null,
      tenant: stored?.tenant ?? null,
      login,
      register,
      logout,
      updateTenant,
    }),
    [stored, ready, login, register, logout, updateTenant],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside <AuthProvider>");
  return context;
}
