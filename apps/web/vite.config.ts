import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiTarget = process.env.VITE_DEV_API_TARGET ?? env.VITE_DEV_API_TARGET ?? "http://127.0.0.1:8000";
  // Keep Host aligned with the browser Origin so API write endpoints can apply
  // the same-origin check during direct Vite development.
  const apiProxy = { target: apiTarget, changeOrigin: false };
  return {
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/chat": apiProxy,
      "/health": apiProxy,
      "/admin": apiProxy,
      "/runs": apiProxy,
      "/threads": apiProxy,
      "/approvals": apiProxy,
      "/auth": apiProxy,
      "/console": apiProxy,
      "/models": apiProxy,
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
