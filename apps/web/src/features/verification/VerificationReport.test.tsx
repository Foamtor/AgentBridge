import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { VerificationReport } from "./VerificationReport";

describe("VerificationReport", () => {
  it("shows the streamed response instead of the scenario instruction", () => {
    render(<VerificationReport
      question="当前租户有哪些工单？"
      token=""
      events={[
        { type: "text_delta", event_id: "e-1", data: { content: "这是本次运行的真实回复" } },
        { type: "tool_call", event_id: "e-2", data: { name: "list_work_orders" } },
      ]}
    />);

    expect(screen.getByText("这是本次运行的真实回复")).toBeInTheDocument();
    expect(screen.queryByText("先确认问题与预期效果，再运行并审阅业务展示和平台链路。")).not.toBeInTheDocument();
  });

  it("places business results before acceptance checks", () => {
    const { container } = render(<VerificationReport
      question="按状态统计工单"
      token=""
      events={[
        { type: "x.work_order_ops.list", event_id: "e-list", data: { rows: [{ id: "WO-1" }], columns: [] } },
      ]}
    />);

    const display = container.querySelector(".report-display");
    const checks = container.querySelector(".report-checks");
    expect(display?.compareDocumentPosition(checks!)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
  });
});
