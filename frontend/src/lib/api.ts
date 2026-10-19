/**
 * Tiny typed fetch client.
 *
 * - Same-origin base ("/api/..."), so the Vite dev proxy and the production
 *   nginx reverse proxy both work without CORS.
 * - `setTokenAccessors` is wired by the auth provider, which keeps this
 *   module free of React context (and of import cycles).
 * - On 401 it refreshes once, then retries the original request.
 */

export class ApiRequestError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiRequestError";
    this.status = status;
    this.detail = detail;
  }
}

interface TokenAccessors {
  accessToken: () => string | null;
  refresh: () => Promise<boolean>;
  onUnauthorized: () => void;
}

let accessors: TokenAccessors = {
  accessToken: () => null,
  refresh: async () => false,
  onUnauthorized: () => undefined,
};

export function setTokenAccessors(next: TokenAccessors): void {
  accessors = next;
}

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  skipAuth?: boolean;
  skipRetry?: boolean;
  signal?: AbortSignal;
}

export function isTokenExpired(token: string): boolean {
  const payload = token.split(".")[1];
  if (!payload) return false;
  try {
    const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
    const claims = JSON.parse(atob(normalized)) as { exp?: unknown };
    if (typeof claims.exp !== "number") return false;
    return claims.exp * 1000 <= Date.now();
  } catch {
    return false;
  }
}

async function ensureFreshToken(): Promise<void> {
  const current = accessors.accessToken();
  if (!current || !isTokenExpired(current)) return;
  const refreshed = await accessors.refresh();
  if (!refreshed) {
    accessors.onUnauthorized();
    throw new ApiRequestError(401, "Your session expired — please sign in again.");
  }
}

async function extractDetail(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as {
      detail?: unknown;
    };
    if (typeof payload.detail === "string") return payload.detail;
    if (Array.isArray(payload.detail)) {
      const first = payload.detail[0] as { msg?: string; loc?: unknown[] } | undefined;
      if (first?.msg) {
        const where = Array.isArray(first.loc) ? first.loc.slice(1).join(".") : "";
        return where ? `${where}: ${first.msg}` : first.msg;
      }
    }
  } catch {
    /* not JSON */
  }
  if (response.status === 429) return "Too many requests — please slow down.";
  if (response.status === 413) return "Payload too large.";
  return `Request failed (${response.status})`;
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  if (!options.skipAuth && !options.skipRetry) await ensureFreshToken();

  const headers = new Headers();
  if (options.body !== undefined) headers.set("Content-Type", "application/json");
  if (!options.skipAuth) {
    const token = accessors.accessToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(path, {
    method: options.method ?? "GET",
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    signal: options.signal,
  });

  if (response.status === 401 && !options.skipAuth && !options.skipRetry) {
    const refreshed = await accessors.refresh();
    if (refreshed) {
      return request<T>(path, { ...options, skipRetry: true });
    }
    accessors.onUnauthorized();
    throw new ApiRequestError(401, "Your session expired — please sign in again.");
  }

  if (!response.ok) {
    throw new ApiRequestError(response.status, await extractDetail(response));
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  get: <T>(path: string, options?: Omit<RequestOptions, "method" | "body">) =>
    request<T>(path, { ...options, method: "GET" }),
  post: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, "method" | "body">) =>
    request<T>(path, { ...options, method: "POST", body }),
  put: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, "method" | "body">) =>
    request<T>(path, { ...options, method: "PUT", body }),
  patch: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, "method" | "body">) =>
    request<T>(path, { ...options, method: "PATCH", body }),
  delete: <T = void>(path: string, options?: Omit<RequestOptions, "method" | "body">) =>
    request<T>(path, { ...options, method: "DELETE" }),
};

/** Authenticated multipart upload (CSV import). */
export async function uploadFile<T>(path: string, file: File): Promise<T> {
  await ensureFreshToken();
  const form = new FormData();
  form.append("file", file, file.name);
  const token = accessors.accessToken();
  const response = await fetch(path, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    body: form,
  });
  if (response.status === 401) {
    const refreshed = await accessors.refresh();
    if (!refreshed) {
      accessors.onUnauthorized();
      throw new ApiRequestError(401, "Your session expired — please sign in again.");
    }
    return uploadFile<T>(path, file);
  }
  if (!response.ok) {
    throw new ApiRequestError(response.status, await extractDetail(response));
  }
  return (await response.json()) as T;
}

/** Authenticated file download (CSV export). */
export async function downloadFile(path: string, fallbackName: string): Promise<void> {
  await ensureFreshToken();
  const token = accessors.accessToken();
  const response = await fetch(path, {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  if (response.status === 401) {
    const refreshed = await accessors.refresh();
    if (!refreshed) {
      accessors.onUnauthorized();
      throw new ApiRequestError(401, "Your session expired — please sign in again.");
    }
    return downloadFile(path, fallbackName);
  }
  if (!response.ok) {
    throw new ApiRequestError(response.status, await extractDetail(response));
  }
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const match = /filename="([^"]+)"/.exec(disposition);
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = match?.[1] ?? fallbackName;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export function buildQuery(params: Record<string, string | number | undefined | null>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    search.set(key, String(value));
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}
