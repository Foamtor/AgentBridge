import { apiBase } from "../../lib/apiBase";
import { getToken } from "../auth/token";

export async function adminFetch<T>(path: string): Promise<T> {
  const headers: Record<string, string> = {};
  const token = getToken().trim();
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${apiBase()}${path}`, { headers });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    const message =
      typeof detail?.detail?.message === "string"
        ? detail.detail.message
        : `HTTP ${res.status}`;
    throw new Error(message);
  }
  return (await res.json()) as T;
}
