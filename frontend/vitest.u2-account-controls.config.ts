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
    include: ['test/u2-account-personal-controls/**/*.test.{ts,tsx}'],
    passWithNoTests: false,
    maxWorkers: 1,
    minWorkers: 1,
    testTimeout: 10_000,
    hookTimeout: 15_000,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'json-summary'],
      reportsDirectory: './coverage/u2-account-controls',
      // Include the entire live v2 workspace: never an empty include or a
      // hand-picked subset that hides account/shell integration paths.
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/main.tsx'],
      thresholds: { lines: 80 },
    },
  },
});
