import { sveltekit } from "@sveltejs/kit/vite";
import { defineConfig } from "vitest/config";

// vite.config.ts runs in Node.js and has access to `process.env` at runtime.
// We declare the type here so TypeScript resolves it without requiring @types/node.
declare const process: { env: Record<string, string | undefined> };

const apiProxy = {
  "/api": { target: "http://localhost:8000", changeOrigin: true },
  "/static": { target: "http://localhost:8000", changeOrigin: true },
};

export default defineConfig({
  plugins: [sveltekit()],
  server: {
    // Proxy API and static requests to the FastAPI backend during local development.
    proxy: apiProxy,
    hmr: {
      // When running behind a reverse proxy (e.g. Caddy in docker compose),
      // the HMR WebSocket client must connect on the proxy's port (80) rather
      // than the Vite dev server's internal port (5173). Set HMR_CLIENT_PORT=80
      // in the container environment to enable this.
      clientPort: Number(process.env.HMR_CLIENT_PORT) || undefined,
    },
    // macOS Docker volumes don't reliably deliver inotify events into Linux
    // containers, so Vite's native watcher misses host-side edits. Polling
    // detects changes regardless of filesystem event support. The interval is
    // short enough to feel responsive without hammering the CPU.
    watch: {
      usePolling: true,
      interval: 300,
    },
  },
  // Keep preview behavior aligned with dev so E2E uses the same API routing.
  preview: {
    proxy: apiProxy,
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test-setup.ts"],
    include: ["src/**/*.test.ts"],
    exclude: ["tests/**"],
  },
});
