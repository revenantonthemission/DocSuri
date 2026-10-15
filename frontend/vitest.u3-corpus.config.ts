import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';

/**
 * Scoped U3 paper/corpus frontend unit configuration.
 *
 * Only `test/u3-paper-corpus-capabilities/**` is discovered; the coverage
 * include set names the U3 production surface explicitly (the new
 * `src/u3-corpus/**` modules plus the shared Transport they extend) and never
 * narrows to inflate results.
 */
export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@': fileURLToPath(new URL('./', import.meta.url)) } },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./test/setup.ts'],
    include: ['test/u3-paper-corpus-capabilities/**/*.test.{ts,tsx}'],
    passWithNoTests: false,
    maxWorkers: 1,
    minWorkers: 1,
    testTimeout: 10_000,
    hookTimeout: 15_000,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'json-summary'],
      reportsDirectory: './coverage/u3-paper-corpus-capabilities',
      include: ['src/u3-corpus/**/*.{ts,tsx}', 'src/api.ts'],
      exclude: ['src/u3-corpus/**/*.d.ts'],
      thresholds: { lines: 80 },
    },
  },
});
