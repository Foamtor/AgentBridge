import { useCallback, useEffect, useState } from "react";
import { apiBase } from "../../lib/apiBase";
import { useI18n } from "../../i18n";

type Bootstrap = {
  runtime?: { auth_mode?: string; llm_backend?: string; knowledge_backend?: string };
  context?: { tenant_id?: string };
  reference?: { available?: boolean; data_class?: string };
};
type Ready = { status?: "ready" | "not_ready"; checks?: Record<string, { status?: string }> };
type EnvironmentState = "loading" | "ready" | "degraded" | "offline";

export function EnvironmentSummary() {
  const { t } = useI18n();
  const [snapshot, setSnapshot] = useState<Bootstrap | null>(null);
  const [ready, setReady] = useState<Ready | null>(null);
  const [status, setStatus] = useState<EnvironmentState>("loading");

  const load = useCallback(async () => {
    setStatus("loading");
    try {
      const [readyResponse, bootstrapResponse] = await Promise.all([
        fetch(`${apiBase()}/ready`, { credentials: "include" }),
        fetch(`${apiBase()}/console/bootstrap`, { credentials: "include" }),
      ]);
      if (bootstrapResponse.status === 401 || bootstrapResponse.status === 403) throw new Error("session");
      if (!bootstrapResponse.ok) throw new Error(`bootstrap HTTP ${bootstrapResponse.status}`);
      const bootstrap = (await bootstrapResponse.json()) as Bootstrap;
      const readyBody = (await readyResponse.json().catch(() => ({}))) as Ready;
      setSnapshot(bootstrap);
      setReady(readyBody);
      setStatus(readyResponse.ok && readyBody.status === "ready" && bootstrap.reference?.available !== false ? "ready" : "degraded");
    } catch {
      setStatus("offline");
      setSnapshot(null);
      setReady(null);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const label = status === "ready" ? t("ready") : status === "loading" ? t("checking") : status === "degraded" ? t("degraded") : t("offline");
  const checkCount = ready?.checks ? Object.values(ready.checks).filter((check) => check.status === "ok" || check.status === "skipped").length : 0;
  return <section className={`environment-summary environment-${status}`} aria-label={t("environment")}>
    <div className="environment-state"><span className="environment-status" aria-hidden="true">{status === "ready" ? "●" : status === "loading" ? "○" : "!"}</span><strong>{label}</strong></div>
    {snapshot ? <div className="environment-facts"><span>{t("tenant")} <code>{snapshot.context?.tenant_id ?? "-"}</code></span><span>{t("data")} <code>{snapshot.reference?.data_class ?? "-"}</code></span><span>{snapshot.runtime?.llm_backend ?? t("offlineModel")}</span><span>{checkCount} checks</span></div> : <span className="muted">{t("offlineDescription")}</span>}
    <button type="button" className="environment-refresh" onClick={() => void load()} disabled={status === "loading"} title={t("environment")} aria-label={t("environment")}>↻</button>
  </section>;
}
