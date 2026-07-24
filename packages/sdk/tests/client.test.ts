import { describe, expect, it, vi, afterEach } from "vitest";
import { AgentBridgeClient } from "../src/client";

describe("AgentBridgeClient.resolveApproval", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("maps allow to approve in request body", async () => {
    const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => {
      return new Response("{}", { status: 200 });
    });
    vi.stubGlobal("fetch", fetchMock);

    const client = new AgentBridgeClient("http://bridge.test", {
      getToken: () => "tok",
    });
    await client.resolveApproval("appr-1", "allow");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("http://bridge.test/approvals/appr-1");
    expect(init?.method).toBe("POST");
    expect(JSON.parse(String(init?.body))).toEqual({ decision: "approve" });
    const headers = init?.headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer tok");
  });

  it("maps deny to deny", async () => {
    const fetchMock = vi.fn(async () => new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const client = new AgentBridgeClient("http://bridge.test");
    await client.resolveApproval("appr-2", "deny");
    const body = JSON.parse(String(fetchMock.mock.calls[0]![1]?.body));
    expect(body).toEqual({ decision: "deny" });
  });
});
