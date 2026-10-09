import { defineConfig } from "@playwright/test";

import {
  backendDir,
  e2eApiUrl,
  e2eAppUrl,
  e2eProcessEnv,
  frontendDir,
} from "./e2e/environment";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: e2eAppUrl,
    trace: "retain-on-failure",
  },
  globalTeardown: "./e2e/global-teardown.ts",
  projects: [{ name: "chromium", use: { browserName: "chromium" } }],
  webServer: [
    {
      command: "python3 -m app.e2e_server",
      cwd: backendDir,
      env: e2eProcessEnv(),
      url: `${e2eApiUrl}/health/ready`,
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: "npm run build && npm run start -- --port 3010 --hostname 127.0.0.1",
      cwd: frontendDir,
      env: {
        PATH: process.env.PATH ?? "",
        HOME: process.env.HOME ?? "",
        TMPDIR: process.env.TMPDIR ?? "/tmp",
        NEXT_PUBLIC_API_URL: e2eApiUrl,
      },
      url: `${e2eAppUrl}/login`,
      reuseExistingServer: false,
      timeout: 300_000,
    },
  ],
});
