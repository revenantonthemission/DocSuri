import { defineConfig } from 'vitest/config';

// Node-only generator tests must not inherit the browser UI setup.
export default defineConfig({ test: { environment: 'node', include: [
  'test/contractGenerator.test.ts', 'test/consumerInventory.test.ts',
] } });
