import { defineConfig, devices } from "@playwright/test";

const port = 5174;

export default defineConfig({
  testDir: "e2e",
  forbidOnly: !!process.env.CI,
  reporter: process.env.CI ? "github" : "list",
  use: { baseURL: `http://localhost:${port}` },
  projects: [
    {
      name: "chromium",
      use: devices["Desktop Chrome"],
    },
  ],
  webServer: {
    command: `vite e2e/app --port ${port} --strictPort`,
    port,
    reuseExistingServer: !process.env.CI,
  },
});
