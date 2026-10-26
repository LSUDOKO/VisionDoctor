import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  timeout: 60_000,
  use: { baseURL: process.env.VD_URL ?? "http://localhost:8000", headless: true },
});
