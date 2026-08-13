import { useEffect, useState } from "react";
import { useI18n } from "../../i18n";
import { Link } from "react-router-dom";
import { apiBase } from "../../lib/apiBase";
import { EnvironmentSummary } from "./EnvironmentSummary";
import { PlatformEvidence } from "./PlatformEvidence";
import { ScenarioPicker } from "./ScenarioPicker";
import { useVerificationRun } from "./useVerificationRun";
import { VerificationReport } from "./VerificationReport";

export function VerificationWorkbench() {
  const { t } = useI18n();
  const run = useVerificationRun();
  const [models, setModels] = useState<Array<{ alias: string; model_name: string; last_test_status?: "success" | "failed" | null; last_test_capability?: string | null }>>([]);
  const [modelsReady, setModelsReady] = useState(false);
  useEffect(() => {
    void fetch(`${apiBase()}/models`, { credentials: "include" })
      .then(async (response) => response.ok ? response.json() as Promise<{ models: Array<{ alias: string; model_name: string; last_test_status?: "success" | "failed" | null; last_test_capability?: string | null }> }> : { models: [] })
      .then((body) => setModels(Array.isArray(body.models) ? body.models : []))
      .catch(() => setModels([]))
      .finally(() => setModelsReady(true));
  }, []);
  const testedModels = models.filter((model) => model.last_test_status === "success" && model.last_test_capability === "tool_calling_v1");
  useEffect(() => {
    if (testedModels.length > 0 && !testedModels.some((model) => model.alias === run.model)) {
      run.setModel(testedModels[0].alias);
    }
  }, [testedModels, run.model, run.setModel]);
  const phaseLabel = run.verification.phase === "running" ? t("running")
    : run.verification.phase === "waiting_approval" ? t("waitingApproval")
    : run.verification.phase === "complete" ? t("completed")
    : run.verification.phase === "error" ? t("failed")
    : run.verification.phase === "cancelled" ? t("cancelled") : null;

  return <main className="page verification-workbench">
    <header className="workbench-header">
      <div><p className="eyebrow">{t("product")} / {t("preview")}</p><h1>{t("verifyTitle")}</h1><p className="lede">{t("verifyDescription")}</p></div>
      <div className="workbench-meta"><span>{t("route")}</span><code>{run.routeDecision?.route ?? (run.scenario === "routing" ? t("notYetRouted") : "work_order_ops")}</code><span>{t("thread")}</span><code>{run.threadId}</code><Link className="playground-link" to="/playground">{t("playground")} →</Link></div>
    </header>
    <EnvironmentSummary />
    <section className="workbench-section">
      <div className="section-heading"><div><h2>{t("chooseScenario")}</h2><p className="muted">{t("scenarioHint")}</p></div>{phaseLabel ? <span className={`run-status status-${run.verification.phase}`}>{phaseLabel}</span> : null}</div>
      <div className="execution-mode" role="group" aria-label={t("executionMode")}><span>{t("executionMode")}</span><button type="button" className={run.mode === "fake" ? "selected" : ""} onClick={() => run.setMode("fake")} disabled={run.busy}>{t("fakeMode")}</button><button type="button" className={run.mode === "real" ? "selected" : ""} onClick={() => { run.setMode("real"); if (testedModels.length > 0 && !testedModels.some((model) => model.alias === run.model)) run.setModel(testedModels[0].alias); }} disabled={run.busy || !testedModels.length}>{t("realMode")}</button>{run.mode === "real" ? <label className="model-picker"><span>{t("modelAlias")}</span><select value={run.model} onChange={(event) => run.setModel(event.target.value)} disabled={run.busy}>{testedModels.map((model) => <option value={model.alias} key={model.alias}>{model.alias} · {model.model_name}</option>)}</select></label> : null}<small>{run.mode === "real" ? t("realModeHint") : t("fakeModeHint")}{modelsReady && !testedModels.length ? ` ${t("realModelUnavailable")}` : ""}</small></div>
      <ScenarioPicker value={run.scenario} disabled={run.busy} onChange={run.setScenario} />
      {run.scenario === "routing" ? <label className="route-question"><span>{t("routeQuestionLabel")}</span><textarea value={run.routeQuestion} onChange={(event) => run.setRouteQuestion(event.target.value)} disabled={run.busy} placeholder={t("routeQuestionPlaceholder")} rows={3} /></label> : null}
      <div className="run-actions"><button type="button" className="primary" onClick={() => void run.run()} disabled={run.busy || (run.mode === "real" && !testedModels.length) || (run.scenario === "routing" && !run.routeQuestion.trim())}>{run.busy ? t("running") : t("runScenario")}</button><button type="button" className="secondary" onClick={() => void run.cancel()} disabled={!run.busy}>{t("cancel")}</button>{modelsReady && !testedModels.length ? <Link className="playground-link" to="/models">{t("configureModel")}</Link> : null}</div>
    </section>
    {run.error ? <p className="error" role="alert">{run.error}</p> : null}
    <VerificationReport events={run.verification.events} question={run.query} scenario={run.scenario} routeDecision={run.routeDecision} token="" onApprovalResolved={run.reload} />
    <details className="technical-evidence" open><summary>{t("technicalEvidence")}</summary><PlatformEvidence events={run.verification.events} /></details>
  </main>;
}
