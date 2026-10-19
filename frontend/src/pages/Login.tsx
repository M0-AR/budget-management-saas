import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { KeyRound, Sparkles } from "lucide-react";

import { AuthLayout } from "../components/AuthLayout";
import { Button, Field, Input } from "../components/ui";
import { api, ApiRequestError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { applyBranding } from "../lib/theme";
import type { PublicBranding } from "../lib/types";

const DEMO = { slug: "demo", email: "demo@example.com", password: "Demo@12345" };

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const redirectTo = (location.state as { from?: string } | null)?.from ?? "/app";

  const [tenantSlug, setTenantSlug] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [branding, setBranding] = useState<PublicBranding | null>(null);
  const debounceRef = useRef<number>(0);

  // Theme the page for the workspace slug (debounced), like a white-label login.
  useEffect(() => {
    window.clearTimeout(debounceRef.current);
    const slug = tenantSlug.trim().toLowerCase();
    if (!/^[a-z0-9][a-z0-9-]{1,38}[a-z0-9]$/.test(slug)) {
      setBranding(null);
      applyBranding(null);
      return undefined;
    }
    debounceRef.current = window.setTimeout(async () => {
      try {
        const result = await api.get<PublicBranding>(`/api/v1/settings/public/${slug}`, {
          skipAuth: true,
        });
        setBranding(result);
        applyBranding({ accent_color: result.accent_color, display_name: result.display_name });
      } catch {
        setBranding(null);
      }
    }, 350);
    return () => window.clearTimeout(debounceRef.current);
  }, [tenantSlug]);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(tenantSlug, email, password);
      navigate(redirectTo, { replace: true });
    } catch (caught) {
      if (caught instanceof ApiRequestError) setError(caught.detail);
      else setError("Unable to sign in right now — please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthLayout
      title="Sign in to your workspace"
      subtitle={
        branding
          ? `Welcome back to ${branding.display_name} — enter your credentials to continue.`
          : "Enter your workspace slug and credentials to continue."
      }
    >
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        <Field label="Workspace" hint="The workspace slug your admin gave you, e.g. “demo”.">
          {(id) => (
            <Input
              id={id}
              value={tenantSlug}
              onChange={(event) => setTenantSlug(event.target.value)}
              placeholder="acme"
              autoComplete="organization"
              autoCapitalize="none"
              spellCheck={false}
              required
            />
          )}
        </Field>
        <Field label="Email">
          {(id) => (
            <Input
              id={id}
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="you@company.com"
              autoComplete="email"
              required
            />
          )}
        </Field>
        <Field label="Password">
          {(id) => (
            <Input
              id={id}
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="••••••••"
              autoComplete="current-password"
              required
            />
          )}
        </Field>

        {error ? (
          <div
            role="alert"
            className="rounded-xl border border-danger/30 bg-danger-soft px-3.5 py-2.5 text-sm font-medium text-danger"
          >
            {error}
          </div>
        ) : null}

        <Button type="submit" className="w-full" loading={submitting} icon={<KeyRound className="size-4" />}>
          Sign in
        </Button>
      </form>

      <div className="mt-5 space-y-4">
        <button
          type="button"
          onClick={() => {
            setTenantSlug(DEMO.slug);
            setEmail(DEMO.email);
            setPassword(DEMO.password);
          }}
          className="flex w-full items-center justify-center gap-2 rounded-xl border border-dashed border-line px-3 py-2.5 text-xs font-medium text-ink-muted transition hover:border-accent hover:text-accent"
        >
          <Sparkles className="size-3.5" aria-hidden />
          Try the demo workspace (demo / demo@example.com / Demo@12345)
        </button>

        <p className="text-center text-sm text-ink-muted">
          New here?{" "}
          <Link to="/register" className="font-semibold text-accent hover:underline">
            Create a workspace
          </Link>
        </p>
      </div>
    </AuthLayout>
  );
}
