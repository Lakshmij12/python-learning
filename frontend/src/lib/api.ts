// Minimal typed API client for the dashboard.
// Tokens are kept in memory + localStorage; all requests go through `/api/*`,
// which Next.js rewrites to the FastAPI backend.

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

const ACCESS_KEY = "wa_access_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(ACCESS_KEY);
}

export function setToken(token: string): void {
  window.localStorage.setItem(ACCESS_KEY, token);
}

export function clearToken(): void {
  window.localStorage.removeItem(ACCESS_KEY);
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`/api${path}`, { ...options, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.error?.message || `Request failed (${res.status})`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  login: (email: string, password: string) =>
    request<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  me: () => request<{ email: string; full_name: string | null }>("/auth/me"),
  tasks: () => request<Array<{ id: string; title: string; status: string }>>("/tasks"),
  createTask: (title: string) =>
    request("/tasks", { method: "POST", body: JSON.stringify({ title }) }),
  health: () => request<{ status: string }>("/health"),
};
