import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiTarget = process.env.VITE_DEV_API_TARGET ?? env.VITE_DEV_API_TARGET ?? "http://127.0.0.1:8000";
  // Keep Host aligned with the browser Origin so API write endpoints can apply
  // the same-origin check during direct Vite development.
  const apiProxy = { target: apiTarget, changeOrigin: false };
  // Several SPA pages intentionally share names with API prefixes. Keep the
  // exact document routes in Vite so navigation renders React; only nested
  // paths such as /admin/models should be forwarded to the API.
  const apiProxyWithSpaBypass = {
    ...apiProxy,
    bypass(req: { url?: string; headers?: { accept?: string } }) {
      const path = (req.url ?? "").split("?", 1)[0];
      const acceptsHtml = req.headers?.accept?.includes("text/html");
      if (acceptsHtml && ["/admin", "/models", "/config", "/knowledge", "/domains", "/tools", "/runs", "/prompts", "/usage"].includes(path)) {
        return path;
      }
      return undefined;
    },
  };
  return {
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/chat": apiProxy,
      "/health": apiProxy,
      "/admin": apiProxyWithSpaBypass,
      "/runs": apiProxy,
      "/threads": apiProxy,
      "/approvals": apiProxy,
      "/auth": apiProxy,
      "/console": apiProxy,
      "/models": apiProxyWithSpaBypass,
      "/prompts": apiProxyWithSpaBypass,
      "/ready": apiProxy,
      "/metrics": apiProxy,
      "/ingest": apiProxy,
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    globals: true,
  },
  };
});
