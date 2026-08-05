import { useI18n } from "../../i18n";
import type { VerificationScenario } from "./useVerificationRun";

type Props = { value: VerificationScenario; disabled: boolean; onChange: (scenario: VerificationScenario) => void };

const scenarios: Array<{ id: VerificationScenario; title: "scenarioListTitle" | "scenarioChartTitle" | "scenarioKnowledgeTitle" | "scenarioDraftTitle"; description: "scenarioListDescription" | "scenarioChartDescription" | "scenarioKnowledgeDescription" | "scenarioDraftDescription" }> = [
  { id: "list", title: "scenarioListTitle", description: "scenarioListDescription" },
  { id: "chart", title: "scenarioChartTitle", description: "scenarioChartDescription" },
  { id: "knowledge", title: "scenarioKnowledgeTitle", description: "scenarioKnowledgeDescription" },
  { id: "draft", title: "scenarioDraftTitle", description: "scenarioDraftDescription" },
];

export function ScenarioPicker({ value, disabled, onChange }: Props) {
  const { t } = useI18n();
  return <section className="scenario-picker" aria-label={t("chooseScenario")}>
    {scenarios.map((scenario) => <button key={scenario.id} type="button" className={scenario.id === value ? "scenario selected" : "scenario"} aria-pressed={scenario.id === value} disabled={disabled} onClick={() => onChange(scenario.id)}>
      <strong>{t(scenario.title)}</strong><span>{t(scenario.description)}</span>
    </button>)}
  </section>;
}
