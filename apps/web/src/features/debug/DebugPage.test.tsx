import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DebugPage } from "./DebugPage";

describe("DebugPage", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("parses terminal SSE events into the timeline", async () => {
    const encoder = new TextEncoder();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode('data: {"type":"start","sequence":1}\n\n'));
        controller.enqueue(encoder.encode('data: {"type":"done","sequence":2}\n\n'));
        controller.close();
      },
    });
    // A minimal fetch response keeps the SSE parser on its real ReadableStream
    // path while avoiding jsdom's incompatible Response implementation.
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, body: stream } as Response),
    );

    render(<DebugPage />, { wrapper: MemoryRouter });
    fireEvent.click(screen.getByRole("button", { name: "发送" }));

    await waitFor(() => expect(screen.getByText("start")).toBeInTheDocument());
    expect(screen.getByText("done")).toBeInTheDocument();
  });

  it("replays a run selected from the runs page", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => [{ type: "done", sequence: 3 }],
      } as Response),
    );

    render(
      <MemoryRouter initialEntries={["/debug?run_id=run-123"]}>
        <DebugPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText("done")).toBeInTheDocument());
    expect(screen.getByText("回放 run：run-123")).toBeInTheDocument();
  });

  it("shows a safe replay error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 403 } as Response),
    );

    render(
      <MemoryRouter initialEntries={["/debug?run_id=run-123"]}>
        <DebugPage />
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(screen.getByText(/replay failed HTTP 403/)).toBeInTheDocument(),
    );
  });
});
