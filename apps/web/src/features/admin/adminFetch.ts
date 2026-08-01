import { apiBase } from "../../lib/apiBase";
import { getToken } from "../auth/token";

export async function adminFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const headers: Record<string, string> = {
    ...(init?.headers as Record<string, string> | undefined),
  };
  const token = getToken().trim();
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${apiBase()}${path}`, { ...init, headers });
  if (!res.ok) {
    // API error bodies may include operator-only diagnostics. The console only
    // needs a stable status-level message and must not surface them to users.
    const message =
      res.status === 401
        ? "Unauthorized"
        : res.status === 403
          ? "Forbidden"
          : `Request failed (HTTP ${res.status})`;
    throw new Error(message);
  }
  return (await res.json()) as T;
}
