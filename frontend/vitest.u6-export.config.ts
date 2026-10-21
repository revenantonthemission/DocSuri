// U6 export vitest scope; mirrors vitest.u5-topics.config.ts.
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@': fileURLToPath(new URL('./', import.meta.url)) } },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./test/setup.ts'],
    include: ['test/u6-export/**/*.test.{ts,tsx}'],
    passWithNoTests: false,
    maxWorkers: 1,
    minWorkers: 1,
    testTimeout: 10_000,
    hookTimeout: 15_000,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'json-summary'],
      reportsDirectory: './coverage/u6-export',
      include: ['src/u6-export/**/*.{ts,tsx}'],
      // U6-authored production code carries the feature-scope 80% floor.
      thresholds: { 'src/u6-export/**/*.{ts,tsx}': { lines: 80 } },
    },
  },
});
