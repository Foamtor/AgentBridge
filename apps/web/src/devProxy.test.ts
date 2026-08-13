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

  it("keeps the prompts page while forwarding its API list request", () => {
    const resolved = config({
      command: "serve",
      mode: "test",
      isSsrBuild: false,
      isPreview: false,
    });
    const promptProxy = resolved.server?.proxy?.["/prompts"];
    const bypass = typeof promptProxy === "object" ? promptProxy.bypass : undefined;
    type BypassRequest = Parameters<NonNullable<typeof bypass>>[0];
    type BypassResponse = Parameters<NonNullable<typeof bypass>>[1];
    type BypassOptions = Parameters<NonNullable<typeof bypass>>[2];

    const response = {} as BypassResponse;
    const options = {} as BypassOptions;
    expect(bypass?.({ url: "/prompts", headers: { accept: "text/html" } } as BypassRequest, response, options)).toBe("/prompts");
    expect(bypass?.({ url: "/prompts", headers: { accept: "*/*" } } as BypassRequest, response, options)).toBeUndefined();
  });
});
