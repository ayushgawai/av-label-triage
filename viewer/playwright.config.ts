import { defineConfig } from "@playwright/test";
import { existsSync } from "node:fs";
const macChrome =
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const executablePath =
  process.env.CHROME_PATH || (existsSync(macChrome) ? macChrome : undefined);
export default defineConfig({
  testDir: "./tests",
  use: { browserName: "chromium", launchOptions: { executablePath } },
  webServer: {
    command: "python3 -m http.server 4173 --directory ../space",
    url: "http://127.0.0.1:4173",
    reuseExistingServer: true,
  },
});
