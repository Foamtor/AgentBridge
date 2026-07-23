const KEY = "agent_base_bearer";

export function getToken(): string {
  return localStorage.getItem(KEY) ?? (import.meta.env.VITE_BEARER_TOKEN as string) ?? "";
}

export function setToken(token: string): void {
  localStorage.setItem(KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(KEY);
}
