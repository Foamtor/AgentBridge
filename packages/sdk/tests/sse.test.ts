import { describe, expect, it } from "vitest";
import { parseSseChunk } from "../src/sse";

describe("parseSseChunk", () => {
  it("parses data line", () => {
    const evt = parseSseChunk(
      'data: {"type":"text_delta","run_id":"r1","sequence":2,"data":{"content":"hi","agent_id":"writer"}}',
    );
    expect(evt?.type).toBe("text_delta");
    expect(evt?.run_id).toBe("r1");
    expect(evt?.sequence).toBe(2);
    expect(evt?.data?.agent_id).toBe("writer");
  });

  it("returns null for non-data", () => {
    expect(parseSseChunk(": ping")).toBeNull();
    expect(parseSseChunk("data: [DONE]")).toBeNull();
  });
});
