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
    include: ['test/u1-integrated-paper-journey/**/*.test.{ts,tsx}'],
    passWithNoTests: false,
    maxWorkers: 2,
    minWorkers: 1,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'json-summary'],
      thresholds: { perFile: true, lines: 80 },
      // The runner supplies the explicit changed-module inventory before
      // coverage (JSON array); without it, coverage is not collected.
      include: process.env.DOCSURI_U1_COVERAGE_INCLUDE
        ? (JSON.parse(process.env.DOCSURI_U1_COVERAGE_INCLUDE) as string[])
        : [],
    },
  },
});
