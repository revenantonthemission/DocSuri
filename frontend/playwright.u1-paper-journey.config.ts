import { defineConfig, devices } from '@playwright/test';

const origin = process.env.DOCSURI_U1_ORIGIN;
if (!origin || !/^http:\/\/127\.0\.0\.1:\d+$/.test(origin)) {
  throw new Error('U1 requires its manifest-owned mounted loopback origin');
}

export default defineConfig({
  testDir: './e2e/u1-integrated-paper-journey',
  forbidOnly: true,
  workers: 1,
  retries: 0,
  timeout: 120_000,
  expect: { timeout: 10_000 },
  use: { baseURL: origin, trace: 'retain-on-failure' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  // The owned supervisor starts the actual backend/static assembly. Never attach
  // to a generic legacy dev server or start a mock frontend implicitly.
});
