// API client — thin wrapper around fetch with auth header + token refresh.
const BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const API_PREFIX = "/api/v1";

const ACCESS_KEY = "video_rag_access";
const REFRESH_KEY = "video_rag_refresh";

export function getAccess(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ACCESS_KEY);
}
export function getRefresh(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(REFRESH_KEY);
}
export function setTokens(access: string, refresh: string): void {
  localStorage.setItem(ACCESS_KEY, access);
  localStorage.setItem(REFRESH_KEY, refresh);
}
export function clearTokens(): void {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

async function refresh(): Promise<boolean> {
  const r = getRefresh();
  if (!r) return false;
  const res = await fetch(`${BASE}${API_PREFIX}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: r })
  });
  if (!res.ok) {
    clearTokens();
    return false;
  }
  const data = await res.json();
  setTokens(data.access_token, data.refresh_token);
  return true;
}

type ApiOptions = RequestInit & { _retried?: boolean };

export async function api<T = unknown>(path: string, opts: ApiOptions = {}): Promise<T> {
  const url = `${BASE}${API_PREFIX}${path}`;
  const headers = new Headers(opts.headers || {});
  const token = getAccess();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (!(opts.body instanceof FormData) && opts.body) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(url, { ...opts, headers });
  if (res.status === 401 && !opts._retried) {
    const ok = await refresh();
    if (ok) return api<T>(path, { ...opts, _retried: true });
  }
  if (!res.ok) {
    const errBody = await res.text();
    throw new Error(`API ${res.status}: ${errBody.slice(0, 500)}`);
  }
  if (res.status === 204) return null as T;
  return res.json() as Promise<T>;
}

export function apiBaseUrl() {
  return `${BASE}${API_PREFIX}`;
}
