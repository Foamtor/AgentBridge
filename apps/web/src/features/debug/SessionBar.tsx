import { useEffect, useState } from "react";
import { adminFetch } from "../admin/adminFetch";

type Props = {
  threadId: string;
  route: string;
  token: string;
  onThreadId: (v: string) => void;
  onRoute: (v: string) => void;
  onToken: (v: string) => void;
};

const FALLBACK_ROUTES = [
  { value: "echo", label: "echo（最小回声）" },
  { value: "demo_tools", label: "demo_tools（无 LLM / tool + x.*）" },
];

export function SessionBar({
  threadId,
  route,
  token,
  onThreadId,
  onRoute,
  onToken,
}: Props) {
  const [routes, setRoutes] = useState(FALLBACK_ROUTES);

  useEffect(() => {
    void adminFetch<{ domains: Array<{ name: string; description: string }> }>(
      "/admin/domains",
    )
      .then((body) => {
        if (!body.domains.length) return;
        setRoutes(
          body.domains.map((d) => ({
            value: d.name,
            label: d.description ? `${d.name}（${d.description}）` : d.name,
          })),
        );
      })
      .catch(() => {
        /* keep fallback list when admin API unavailable */
      });
  }, []);

  return (
    <div className="session-bar">
      <label>
        thread_id
        <input value={threadId} onChange={(e) => onThreadId(e.target.value)} />
      </label>
      <label>
        route
        <select value={route} onChange={(e) => onRoute(e.target.value)}>
          {routes.map((r) => (
            <option key={r.value} value={r.value}>
              {r.label}
            </option>
          ))}
          {!routes.some((r) => r.value === route) ? (
            <option value={route}>{route}</option>
          ) : null}
        </select>
      </label>
      <label className="grow">
        Bearer（可选）
        <input
          value={token}
          onChange={(e) => onToken(e.target.value)}
          placeholder="粘贴 access token"
        />
      </label>
    </div>
  );
}
