// @vitest-environment node
import { describe, expect, it } from "vitest";
import config from "../vite.config";

describe("direct-development proxy", () => {
  it("uses the documented local API port by default", () => {
    const resolved = config({
      command: "serve",
      mode: "test",
      isSsrBuild: false,
      isPreview: false,
    });

    expect(resolved.server?.proxy?.["/health"]).toMatchObject({
      target: "http://127.0.0.1:8000",
    });
  });

  it("preserves the browser Host for same-origin API writes", () => {
    const resolved = config({
      command: "serve",
      mode: "test",
      isSsrBuild: false,
      isPreview: false,
    });
    const proxy = resolved.server?.proxy;

    expect(proxy?.["/admin"]).toMatchObject({ changeOrigin: false });
    expect(proxy?.["/auth"]).toMatchObject({ changeOrigin: false });
  });
});
