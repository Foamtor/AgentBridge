import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { UsagePage } from "./UsagePage";

describe("UsagePage", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("keeps the latest date-window response when earlier requests finish later", async () => {
    let call = 0;
    const fetch = vi.fn(() => {
      call += 1;
      const response = call === 1
        ? { group_by: "route", items: [{ route: "old", input_tokens: 1, output_tokens: 1 }], totals: { input_tokens: 1, output_tokens: 1 } }
        : { group_by: "route", items: [], totals: { input_tokens: 0, output_tokens: 0 } };
      const delay = call === 1 ? 40 : 0;
      return new Promise<Response>((resolve) => window.setTimeout(() => resolve(new Response(JSON.stringify(response), { status: 200 })), delay));
    });
    vi.stubGlobal("fetch", fetch);
    const user = userEvent.setup();
    render(<UsagePage />);
    await user.type(screen.getByLabelText("开始日期"), "2020-01-01");
    await user.type(screen.getByLabelText("结束日期"), "2020-01-02");

    await waitFor(() => expect(screen.getByText("这个时间范围内没有用量数据。")).toBeInTheDocument());
    expect(screen.queryByText("old")).not.toBeInTheDocument();
  });
});
