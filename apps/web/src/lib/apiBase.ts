export function apiBase(): string {
  const raw = import.meta.env.VITE_API_BASE as string | undefined;
  return (raw ?? "").replace(/\/$/, "");
}
