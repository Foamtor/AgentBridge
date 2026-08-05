import { apiBase } from "../../lib/apiBase";
import { getToken } from "../auth/token";

export async function playgroundFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  const token = getToken().trim();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init?.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const response = await fetch(`${apiBase()}${path}`, { ...init, headers, credentials: "include" });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  if (response.status === 204) return undefined as T;
  return await response.json() as T;
}

export async function downloadRunEvents(runId: string): Promise<void> {
  const headers = new Headers();
  const token = getToken().trim();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(
    `${apiBase()}/runs/${encodeURIComponent(runId)}/events.jsonl`,
    { headers, credentials: "include" },
  );
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = `${runId}.jsonl`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
