import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';

/**
 * Scoped U3 paper/corpus frontend unit configuration.
 *
 * Only `test/u3-paper-corpus-capabilities/**` is discovered. The coverage
 * include set names the U3 production surface explicitly: the modules this
 * unit authored (`src/u3-corpus/**`) plus the shared shell file U3 extended
 * (`src/App.tsx`, the capability-gated corpus-workspace branch exercised by
 * `shell.test.tsx` and the browser journeys). Nothing is excluded to inflate
 * a number.
 *
 * Thresholds are per-glob so each obligation keeps its real denominator:
 * - `src/u3-corpus/**` keeps the mandatory 80% new-code floor (measured
 *   86.89% with the U3 suites).
 * - `src/App.tsx` is predominantly pre-existing shell code owned by the
 *   U1/U2/U7 lanes; the shell lanes evidence its whole-file coverage
 *   (`vitest.u2-account-controls.config.ts` reports `src/**` at 80.2% with
 *   `src/App.tsx` at 54.5% whole-file). This lane measures 48.62% from the
 *   U3 shell composition test and enforces 48% as a no-regression floor —
 *   it never lowers the U3-authored modules' 80% target.
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
      include: ['src/u3-corpus/**/*.{ts,tsx}', 'src/App.tsx'],
      exclude: ['src/u3-corpus/**/*.d.ts'],
      thresholds: {
        'src/u3-corpus/**/*.{ts,tsx}': { lines: 80 },
        'src/App.tsx': { lines: 48 },
      },
    },
  },
});
