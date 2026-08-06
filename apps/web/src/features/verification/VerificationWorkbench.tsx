import { useEffect, useState } from "react";
import { useI18n } from "../../i18n";
import { Link, useSearchParams } from "react-router-dom";
import { apiBase } from "../../lib/apiBase";
import { EnvironmentSummary } from "./EnvironmentSummary";
import { PlatformEvidence } from "./PlatformEvidence";
import { ScenarioPicker } from "./ScenarioPicker";
import { useVerificationRun } from "./useVerificationRun";
import { VerificationReport } from "./VerificationReport";

export function VerificationWorkbench() {
  const { t } = useI18n();
  const [searchParams] = useSearchParams();
  const advancedMode = searchParams.get("mode") === "advanced";
  const run = useVerificationRun();
  const [models, setModels] = useState<Array<{ alias: string; model_name: string }>>([]);
  const [modelsReady, setModelsReady] = useState(false);
  useEffect(() => {
    void fetch(`${apiBase()}/models`, { credentials: "include" })
      .then(async (response) => response.ok ? response.json() as Promise<{ models: Array<{ alias: string; model_name: string }> }> : { models: [] })
      .then((body) => setModels(Array.isArray(body.models) ? body.models : []))
      .catch(() => setModels([]))
      .finally(() => setModelsReady(true));
  }, []);
  const phaseLabel = run.verification.phase === "running" ? t("running")
    : run.verification.phase === "waiting_approval" ? t("waitingApproval")
    : run.verification.phase === "complete" ? t("completed")
    : run.verification.phase === "error" ? t("failed")
    : run.verification.phase === "cancelled" ? t("cancelled") : null;

  return <main className="page verification-workbench">
    <header className="workbench-header">
      <div><p className="eyebrow">{t("product")} / {t("preview")}</p><h1>{t("verifyTitle")}</h1><p className="lede">{t("verifyDescription")}</p></div>
      <div className="workbench-meta"><span>{t("route")}</span><code>work_order_ops</code><span>{t("thread")}</span><code>{run.threadId}</code><Link className="playground-link" to="/playground">{t("playground")} →</Link></div>
    </header>
    <EnvironmentSummary />
    <section className="workbench-section">
      <div className="section-heading"><div><h2>{t("chooseScenario")}</h2><p className="muted">{t("scenarioHint")}</p></div>{phaseLabel ? <span className={`run-status status-${run.verification.phase}`}>{phaseLabel}</span> : null}</div>
      <div className="execution-mode" role="group" aria-label={t("executionMode")}><span>{t("executionMode")}</span><button type="button" className={run.mode === "fake" ? "selected" : ""} onClick={() => run.setMode("fake")} disabled={run.busy}>{t("fakeMode")}</button><button type="button" className={run.mode === "real" ? "selected" : ""} onClick={() => run.setMode("real")} disabled={run.busy || !models.length}>{t("realMode")}</button>{run.mode === "real" ? <label className="model-picker"><span>{t("modelAlias")}</span><select value={run.model} onChange={(event) => run.setModel(event.target.value)} disabled={run.busy}>{models.map((model) => <option value={model.alias} key={model.alias}>{model.alias} · {model.model_name}</option>)}</select></label> : null}<small>{run.mode === "real" ? t("realModeHint") : t("fakeModeHint")}{modelsReady && !models.length ? ` ${t("realModelUnavailable")}` : ""}</small></div>
      <ScenarioPicker value={run.scenario} disabled={run.busy} onChange={run.setScenario} />
      <div className="run-actions"><button type="button" className="primary" onClick={() => void run.run()} disabled={run.busy || (run.mode === "real" && !models.length)}>{run.busy ? t("running") : t("runScenario")}</button><button type="button" className="secondary" onClick={() => void run.cancel()} disabled={!run.busy}>{t("cancel")}</button>{run.mode === "real" && !models.length ? <Link className="playground-link" to="/models">{t("models")}</Link> : null}</div>
    </section>
    {run.error ? <p className="error" role="alert">{run.error}</p> : null}
    <VerificationReport events={run.verification.events} question={run.query} token="" />
    <details className="technical-evidence" open={advancedMode}><summary>{t("technicalEvidence")}</summary><PlatformEvidence events={run.verification.events} /></details>
  </main>;
}
