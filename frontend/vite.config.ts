import { sveltekit } from "@sveltejs/kit/vite";
import { defineConfig } from "vitest/config";

const apiProxy = {
  "/auth": { target: "http://localhost:8000", changeOrigin: true },
  "/games": { target: "http://localhost:8000", changeOrigin: true },
  "/characters": { target: "http://localhost:8000", changeOrigin: true },
  "/overworld": { target: "http://localhost:8000", changeOrigin: true },
};

export default defineConfig({
  plugins: [sveltekit()],
  server: {
    // Proxy API requests to the FastAPI backend during local development.
    proxy: apiProxy,
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
