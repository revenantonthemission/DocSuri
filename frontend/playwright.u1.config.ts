import { defineConfig, devices } from '@playwright/test';

// The integrated runner supplies these only after its realm/provider/egress
// preflight. No webServer fallback, default origin, auth bypass or production build.
const origin = process.env.DOCSURI_U1_STAGING_ORIGIN;
const proxy = process.env.DOCSURI_U1_BROWSER_PROXY;
const realm = process.env.DOCSURI_U1_REALM_ID;
if (!origin || !proxy || !realm || process.env.DOCSURI_U1_ENVIRONMENT !== 'u1-staging') {
  throw new Error('U1 browser runner requires the qualified staging realm, HTTPS origin and proxy');
}
const target = new URL(origin);
const helper = new URL(proxy);
if (
  target.protocol !== 'https:' || target.username || target.password ||
  target.pathname !== '/' || target.search || target.hash ||
  helper.protocol !== 'http:' || helper.username || helper.password ||
  helper.pathname !== '/' || helper.search || helper.hash ||
  target.hostname === 'localhost' || target.hostname === 'docsuri.com'
) {
  throw new Error('U1 browser origin/proxy configuration refused');
}

export default defineConfig({
  testDir: './e2e',
  testMatch: ['u1-job-skeleton.spec.ts', 'u1-job-resilience.spec.ts', 'u1-job-performance.spec.ts'],
  fullyParallel: false,
  workers: 1,
  retries: 0,
  forbidOnly: true,
  reporter: [['list'], ['json', { outputFile: 'test-results/u1/results.json' }]],
  use: {
    ...devices['Desktop Chrome'],
    baseURL: target.origin,
    proxy: { server: helper.origin },
    ignoreHTTPSErrors: false,
    // Sensitive cookies/results must not enter automatic trace/video artifacts.
    trace: 'off',
    video: 'off',
    screenshot: 'off',
  },
});
