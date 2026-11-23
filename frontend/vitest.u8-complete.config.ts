// U8 complete-application vitest scope; mirrors vitest.u6-export.config.ts.
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
    include: ['test/u8-complete/**/*.test.{ts,tsx}'],
    passWithNoTests: false,
    maxWorkers: 1,
    minWorkers: 1,
    testTimeout: 10_000,
    hookTimeout: 15_000,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'json-summary'],
      reportsDirectory: './coverage/u8-complete',
      // U8's own code, plus the owner file U8 changes (U2's account controls gain the
      // lifecycle-retained state), so its lines are measured in U8's report too.
      // By your decision of 2026-10-24, also U4's three research files U8 changes (the
      // composer's limit and novelty without scores).
      // By your answers of 2026-11-02, also U6's two export files U8 changes: the
      // history's fresh-preview offer for an export invalidated before its write
      // (history.tsx, L1-61) and one authority-revoked text for both causes (copy.ts,
      // L1-62). U6's src/u6-export/** and U2's src/** floors judge them.
      // By L1-9 ("Route through the shell"), also U4's job status line (jobs.tsx), which
      // announces through the complete shell's region; U4's src/u4-research/** floor
      // judges it.
      include: [
        'src/u8-*/**/*.{ts,tsx}',
        'src/account-controls.tsx',
        'src/u4-research/api.ts',
        'src/u4-research/composer.tsx',
        'src/u4-research/evidence.tsx',
        'src/u4-research/jobs.tsx',
        'src/u6-export/history.tsx',
        'src/u6-export/copy.ts',
      ],
      // U8-authored production code carries the feature-scope 80% floor.
      thresholds: { 'src/u8-*/**/*.{ts,tsx}': { lines: 80 } },
    },
  },
});
