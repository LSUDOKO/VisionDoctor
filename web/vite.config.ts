import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const api = "http://localhost:8000";
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": api, "/health": api } },
  build: { outDir: "dist", chunkSizeWarningLimit: 800 },
});
