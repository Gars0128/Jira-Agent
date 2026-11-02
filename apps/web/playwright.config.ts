import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  use: { baseURL: "http://127.0.0.1:3000", browserName: "chromium", screenshot: "only-on-failure" },
  webServer: { command: "node node_modules/next/dist/bin/next dev --hostname 127.0.0.1", url: "http://127.0.0.1:3000", reuseExistingServer: !process.env.CI, timeout: 60000 },
});
