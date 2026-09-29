import { defineConfig } from '@playwright/test';
import base from './playwright.config';

export default defineConfig({
  ...base,
  workers: 1,
  use: { ...base.use, baseURL: 'http://127.0.0.1:3109' },
  webServer: {
    command: 'node scripts/prepare-standalone-assets.mjs && node .next/standalone/server.js',
    url: 'http://127.0.0.1:3109',
    env: { PORT: '3109', HOSTNAME: '127.0.0.1' },
    reuseExistingServer: false,
    timeout: 30_000,
  },
});
