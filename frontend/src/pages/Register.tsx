import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { MailPlus, Rocket } from "lucide-react";

import { AuthLayout } from "../components/AuthLayout";
import { Button, Field, Input } from "../components/ui";
import { ApiRequestError } from "../lib/api";
import { useAuth } from "../lib/auth";

function slugify(value: string): string {
  return value
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 40);
}

export function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const inviteToken = searchParams.get("invite");
  const inviteMode = Boolean(inviteToken);

  const [tenantName, setTenantName] = useState("");
  const [tenantSlug, setTenantSlug] = useState("");
  const [slugTouched, setSlugTouched] = useState(false);
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const effectiveSlug = slugTouched ? tenantSlug : slugify(tenantName);
  const slugValid = /^[a-z0-9][a-z0-9-]{1,38}[a-z0-9]$/.test(effectiveSlug);
  const passwordValid = password.length >= 8;

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    if (!inviteMode && !slugValid) {
      setError("Workspace slug must be 3–40 characters: lowercase letters, numbers and dashes.");
      return;
    }
    if (!passwordValid) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setSubmitting(true);
    try {
      await register({
        ...(inviteMode
          ? { invite_token: inviteToken! }
          : { tenant_name: tenantName.trim(), tenant_slug: effectiveSlug }),
        full_name: fullName.trim(),
        email: email.trim(),
        password,
      });
      navigate("/app", { replace: true });
    } catch (caught) {
      if (caught instanceof ApiRequestError) setError(caught.detail);
      else setError(
        inviteMode
          ? "Unable to accept the invitation right now — please try again."
          : "Unable to create the workspace right now — please try again.",
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthLayout
      title={inviteMode ? "Join your workspace" : "Create your workspace"}
      subtitle={
        inviteMode
          ? "You've been invited — set up your account to join the workspace."
          : "Self-serve in under a minute. You become the owner of an isolated workspace."
      }
    >
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        {inviteMode ? (
          <div className="flex items-start gap-2.5 rounded-xl border border-accent/30 bg-accent-soft px-3.5 py-2.5">
            <MailPlus className="mt-0.5 size-4 shrink-0 text-accent" aria-hidden />
            <p className="text-sm text-ink">
              Invitation detected. Use the email address the invite was sent to — the link only
              works once.
            </p>
          </div>
        ) : (
          <>
            <Field label="Workspace name">
          {(id) => (
            <Input
              id={id}
              value={tenantName}
              onChange={(event) => setTenantName(event.target.value)}
              placeholder="Acme Finance"
              autoComplete="organization"
              required
              minLength={2}
              maxLength={120}
            />
          )}
        </Field>
        <Field
          label="Workspace URL slug"
          hint={
            effectiveSlug
              ? `Your team will sign in with the workspace “${effectiveSlug}”.`
              : "Lowercase letters, numbers and dashes."
          }
          error={
            slugTouched && tenantSlug.length > 0 && !slugValid
              ? "3–40 characters: lowercase letters, numbers and dashes."
              : null
          }
        >
          {(id) => (
            <Input
              id={id}
              value={effectiveSlug}
              onChange={(event) => {
                setSlugTouched(true);
                setTenantSlug(slugify(event.target.value));
              }}
              placeholder="acme-finance"
              autoCapitalize="none"
              spellCheck={false}
              required
            />
          )}
        </Field>
          </>
        )}
        <Field label="Your name">
          {(id) => (
            <Input
              id={id}
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
              placeholder="Ada Lovelace"
              autoComplete="name"
              required
            />
          )}
        </Field>
        <Field label="Work email">
          {(id) => (
            <Input
              id={id}
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="ada@acme.com"
              autoComplete="email"
              required
            />
          )}
        </Field>
        <Field
          label="Password"
          hint="At least 8 characters."
          error={password.length > 0 && !passwordValid ? "Minimum 8 characters." : null}
        >
          {(id) => (
            <Input
              id={id}
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="••••••••"
              autoComplete="new-password"
              required
              minLength={8}
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

        <Button type="submit" className="w-full" loading={submitting} icon={<Rocket className="size-4" />}>
          {inviteMode ? "Join workspace" : "Create workspace"}
        </Button>
      </form>

      <p className="mt-5 text-center text-sm text-ink-muted">
        Already have a workspace?{" "}
        <Link to="/login" className="font-semibold text-accent hover:underline">
          Sign in
        </Link>
      </p>
    </AuthLayout>
  );
}
