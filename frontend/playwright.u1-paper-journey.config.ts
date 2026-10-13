import { defineConfig, devices } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const environment = process.env.DOCSURI_U1_ENVIRONMENT_FILE;
if (!environment) {
  throw new Error('U1 requires its owned environment manifest');
}
const manifest = JSON.parse(readFileSync(environment, 'utf8')) as { applicationPort: number };
// The mounted journey realm is the owned HTTPS loopback composition; the
// browser scenarios never attach to a legacy dev server or an HTTP fallback.
const origin = `https://127.0.0.1:${manifest.applicationPort}`;
const here = dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  testDir: './e2e/u1-integrated-paper-journey',
  forbidOnly: true,
  workers: 1,
  retries: 0,
  timeout: 120_000,
  expect: { timeout: 15_000 },
  use: {
    baseURL: origin,
    ignoreHTTPSErrors: true,
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: `corepack pnpm@9.15.9 exec vite build && ../backend/.venv/bin/python ../scripts/serve_docsuri_u1.py --environment-file ${environment}`,
    cwd: here,
    url: `${origin}/health/live`,
    ignoreHTTPSErrors: true,
    reuseExistingServer: true,
    timeout: 120_000,
  },
});
