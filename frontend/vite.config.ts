import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    // In development the API runs separately (uvicorn on :8000)
    proxy: { "/api": "http://localhost:8000" },
  },
  build: {
    // Mermaid is large, but it's split into its own chunk and only loaded for diagrams
    chunkSizeWarningLimit: 1800,
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
  },
});
