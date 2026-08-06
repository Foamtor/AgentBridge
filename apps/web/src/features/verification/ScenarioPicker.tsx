import { useI18n } from "../../i18n";
import type { VerificationScenario } from "./useVerificationRun";

type Props = { value: VerificationScenario; disabled: boolean; onChange: (scenario: VerificationScenario) => void };

const scenarios: Array<{
  id: VerificationScenario;
  title: "scenarioListTitle" | "scenarioChartTitle" | "scenarioKnowledgeTitle" | "scenarioDraftTitle";
  problem: "scenarioListProblem" | "scenarioChartProblem" | "scenarioKnowledgeProblem" | "scenarioDraftProblem";
  expected: "scenarioListExpected" | "scenarioChartExpected" | "scenarioKnowledgeExpected" | "scenarioDraftExpected";
}> = [
  { id: "list", title: "scenarioListTitle", problem: "scenarioListProblem", expected: "scenarioListExpected" },
  { id: "chart", title: "scenarioChartTitle", problem: "scenarioChartProblem", expected: "scenarioChartExpected" },
  { id: "knowledge", title: "scenarioKnowledgeTitle", problem: "scenarioKnowledgeProblem", expected: "scenarioKnowledgeExpected" },
  { id: "draft", title: "scenarioDraftTitle", problem: "scenarioDraftProblem", expected: "scenarioDraftExpected" },
];

export function ScenarioPicker({ value, disabled, onChange }: Props) {
  const { t } = useI18n();
  return <section className="scenario-picker" aria-label={t("chooseScenario")}>
    {scenarios.map((scenario) => <button key={scenario.id} type="button" className={scenario.id === value ? "scenario selected" : "scenario"} aria-pressed={scenario.id === value} disabled={disabled} onClick={() => onChange(scenario.id)}>
      <strong>{t(scenario.title)}</strong>
      <span className="scenario-field"><b>{t("problem")}</b>{t(scenario.problem)}</span>
      <span className="scenario-field"><b>{t("expectedEffect")}</b>{t(scenario.expected)}</span>
    </button>)}
  </section>;
}
