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
    include: ['test/u4-research-novelty/**/*.test.{ts,tsx}'],
    passWithNoTests: false,
    maxWorkers: 1,
    minWorkers: 1,
    testTimeout: 10_000,
    hookTimeout: 15_000,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'json-summary'],
      reportsDirectory: './coverage/u4-research-novelty',
      include: ['src/u4-research/**/*.{ts,tsx}', 'src/App.tsx'],
      // U4-authored production code has its own mandatory floor. The shared
      // shell retains the existing U3 whole-file floor; cumulative lanes own
      // its older account/search flows. Neither denominator is silently removed.
      thresholds: { 'src/u4-research/**/*.{ts,tsx}': { lines: 80 }, 'src/App.tsx': { lines: 48 } },
    },
  },
});
