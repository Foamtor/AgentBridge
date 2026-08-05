import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/chat": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
      "/admin": "http://127.0.0.1:8000",
      "/runs": "http://127.0.0.1:8000",
      "/threads": "http://127.0.0.1:8000",
      "/approvals": "http://127.0.0.1:8000",
      "/auth": "http://127.0.0.1:8000",
      "/console": "http://127.0.0.1:8000",
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    globals: true,
  },
});
