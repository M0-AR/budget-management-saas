import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "../lib/auth";

/** Shown while the boot-time cookie restore settles, so neither route guard
 * can bounce the user before the session has been resolved. */
function AuthSplash() {
  return (
    <div
      className="flex min-h-dvh items-center justify-center bg-surface-0"
      role="status"
      aria-live="polite"
    >
      <span className="text-sm text-ink-muted">Restoring your session…</span>
    </div>
  );
}

export function ProtectedRoute() {
  const { status, ready } = useAuth();
  const location = useLocation();

  if (!ready) return <AuthSplash />;

  if (status === "anonymous") {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return <Outlet />;
}

export function PublicOnlyRoute() {
  const { status, ready } = useAuth();

  if (!ready) return <AuthSplash />;

  if (status === "authenticated") {
    return <Navigate to="/app" replace />;
  }

  return <Outlet />;
}
