import { defineConfig } from "@playwright/test";

// Set CHROMIUM_PATH to use a pre-installed Chromium instead of Playwright's download.
const executablePath = process.env.CHROMIUM_PATH;

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"]],
  use: { baseURL: "http://localhost:3000", launchOptions: executablePath ? { executablePath } : {} },
  webServer: [
    { command: "python3 -m uvicorn app.main:app --port 8000", cwd: "../backend", url: "http://localhost:8000/health", reuseExistingServer: true },
    { command: "npm run build && npx next start -p 3000", url: "http://localhost:3000", reuseExistingServer: true, timeout: 240_000 },
  ],
});
