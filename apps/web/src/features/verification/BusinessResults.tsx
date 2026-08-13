import type { StreamEvent } from "../../lib/sseClient";
import { GoldenCasePanel } from "../debug/GoldenCasePanel";

type Props = {
  events: StreamEvent[];
  token: string;
  onPreset: (preset: "list" | "chart" | "draft") => void;
  onApprovalResolved?: (runId: string) => Promise<void>;
  showPresets?: boolean;
  showHeading?: boolean;
};

/** Stable business-result boundary for the verification workbench. */
export function BusinessResults(props: Props) {
  return <GoldenCasePanel {...props} />;
}
