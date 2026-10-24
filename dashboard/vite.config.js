import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// PhishSentinel AI dashboard — Vite config.
// Dev server runs on :5173 by default; point VITE_API_BASE (see .env.example)
// at your FastAPI backend, normally http://localhost:8000.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
  },
  build: {
    outDir: "dist",
  },
});
