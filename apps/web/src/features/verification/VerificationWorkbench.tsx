import { useI18n } from "../../i18n";
import { useSearchParams } from "react-router-dom";
import { BusinessResults } from "./BusinessResults";
import { EnvironmentSummary } from "./EnvironmentSummary";
import { PlatformEvidence } from "./PlatformEvidence";
import { ScenarioPicker } from "./ScenarioPicker";
import { useVerificationRun } from "./useVerificationRun";

export function VerificationWorkbench() {
  const { t } = useI18n();
  const [searchParams] = useSearchParams();
  const advancedMode = searchParams.get("mode") === "advanced";
  const run = useVerificationRun();
  const phaseLabel = run.verification.phase === "running" ? t("running")
    : run.verification.phase === "waiting_approval" ? t("waitingApproval")
    : run.verification.phase === "complete" ? t("completed")
    : run.verification.phase === "error" ? t("failed")
    : run.verification.phase === "cancelled" ? t("cancelled") : null;

  return <main className="page verification-workbench">
    <header className="workbench-header">
      <div><p className="eyebrow">{t("product")} / {t("preview")}</p><h1>{t("verifyTitle")}</h1><p className="lede">{t("verifyDescription")}</p></div>
      <div className="workbench-meta"><span>{t("route")}</span><code>work_order_ops</code><span>{t("thread")}</span><code>{run.threadId}</code></div>
    </header>
    <EnvironmentSummary />
    <section className="workbench-section">
      <div className="section-heading"><div><h2>{t("chooseScenario")}</h2><p className="muted">{t("scenarioHint")}</p></div>{phaseLabel ? <span className={`run-status status-${run.verification.phase}`}>{phaseLabel}</span> : null}</div>
      <ScenarioPicker value={run.scenario} disabled={run.busy} onChange={run.setScenario} />
      <div className="run-actions"><button type="button" className="primary" onClick={() => void run.run()} disabled={run.busy}>{run.busy ? t("running") : t("runScenario")}</button><button type="button" className="secondary" onClick={() => void run.cancel()} disabled={!run.busy}>{t("cancel")}</button></div>
    </section>
    {run.error ? <p className="error" role="alert">{run.error}</p> : null}
    <BusinessResults events={run.verification.events} token="" onPreset={() => undefined} showPresets={false} />
    <details className="technical-evidence" open={advancedMode}><summary>{t("technicalEvidence")}</summary><PlatformEvidence events={run.verification.events} /></details>
  </main>;
}
