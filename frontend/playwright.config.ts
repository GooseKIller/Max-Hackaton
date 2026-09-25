import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  use: {
    channel: process.env.PLAYWRIGHT_CHANNEL,
    launchOptions: { executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH },
    baseURL: process.env.PLANNER_BASE_URL || "http://127.0.0.1:8000",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "desktop",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1280, height: 900 },
      },
    },
    {
      name: "mobile",
      use: { ...devices["iPhone 13"], defaultBrowserType: "chromium" },
    },
  ],
});
