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

  it("renders a knowledge result without an unrelated empty chart", () => {
    render(<VerificationReport
      question="处理此类工单应遵循什么规范？"
      token=""
      scenario="knowledge"
      events={[{
        type: "x.bridge.citation",
        event_id: "e-citation",
        data: {
          citations: [{
            chunk_id: "work-order-reference-sop",
            doc_id: "work-order-reference-sop",
            text: "Work-order handling SOP",
          }],
        },
      }]}
    />);

    expect(screen.getByText("work-order-reference-sop")).toBeInTheDocument();
    expect(screen.getByText("Work-order handling SOP")).toBeInTheDocument();
    expect(screen.queryByText("统计图表")).not.toBeInTheDocument();
  });

  it("does not claim success when knowledge retrieval returns no hits", () => {
    render(<VerificationReport
      question="处理此类工单应遵循什么规范？"
      token=""
      scenario="knowledge"
      events={[
        { type: "x.bridge.citation", event_id: "e-citation", data: { citations: [] } },
        { type: "done", event_id: "e-done" },
      ]}
    />);

    expect(screen.getByText("没有检索到匹配的处理规范。")).toBeInTheDocument();
    expect(screen.queryByText("已生成结构化业务结果，请查看下方业务展示。")).not.toBeInTheDocument();
  });
});
