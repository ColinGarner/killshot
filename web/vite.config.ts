/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // `npm run dev` serves the app on :5173 and forwards API calls to uvicorn on :8000.
    proxy: { "/api": "http://localhost:8000", "/healthz": "http://localhost:8000" },
  },
  test: { environment: "jsdom" },
});
