import { defineConfig, devices } from "@playwright/test"

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  reporter: "line",
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:8000",
    trace: "retain-on-failure",
  },
  webServer: {
    command: "../scripts/run_dashboard.sh",
    url: "http://127.0.0.1:8000/api/v1/health",
    timeout: 120_000,
    reuseExistingServer: true,
  },
  projects: [
    { name: "desktop", grep: /@desktop/, use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", grep: /@mobile/, use: { ...devices["Desktop Chrome"], viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
  ],
})
