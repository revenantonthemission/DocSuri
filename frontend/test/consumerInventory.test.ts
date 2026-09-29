// @vitest-environment node
import { mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';

// @ts-expect-error The AST inventory is a standalone Node tooling module.
import { inventory, validateInventory } from '../scripts/inventory-consumers.mjs';

it('discovers consumers under the supplied checkout and traces generated aliases', async () => {
  const checkout = await mkdtemp(join(tmpdir(), 'rem1-consumers-'));
  const root = join(checkout, 'frontend');
  try {
    await mkdir(join(root, 'types/wire'), { recursive: true });
    await mkdir(join(root, 'lib/api'), { recursive: true });
    await writeFile(join(root, 'tsconfig.json'), JSON.stringify({ include: ['**/*.ts'] }));
    await writeFile(join(root, 'types/wire/dtos.ts'), 'export interface Wire { id: string }');
    await writeFile(join(root, 'types/local.ts'), "import type { Wire } from './wire/dtos'; export type Alias = Wire;");
    await writeFile(join(root, 'lib/api/apiClient.ts'), `
      import type { Alias } from '../../types/local';
      declare const response: { body: unknown };
      export const result = response.body as Alias;
    `);
    const observed = inventory(root);
    expect(observed.boundaries).toHaveLength(1);
    expect(observed.boundaries[0].generated).toEqual(['Wire']);
    expect(() => validateInventory(observed, { adapters: [] })).not.toThrow();
    await writeFile(join(root, 'lib/api/apiClient.ts'), `
      declare const response: { body: unknown };
      export const result = response.body as { id: string };
    `);
    expect(() => validateInventory(inventory(root), { adapters: [] })).toThrow('generated contract');
  } finally { await rm(checkout, { recursive: true, force: true }); }
}, 20_000);

it('rejects a newly discovered adapter until explicitly registered', () => {
  const observed = { boundaries: [], adapters: [{ file: 'frontend/new.ts', symbol: 'mapNew' }] };
  expect(() => validateInventory(observed, { adapters: [] })).toThrow('unregistered view adapter');
  expect(() => validateInventory(observed, { adapters: observed.adapters })).not.toThrow();
});

it('rejects missing or duplicate policy adapter entries', () => {
  const adapter = { file: 'frontend/old.ts', symbol: 'mapOld' };
  expect(() => validateInventory({ boundaries: [], adapters: [] }, { adapters: [adapter] })).toThrow();
  expect(() => validateInventory({ boundaries: [], adapters: [adapter] }, {
    adapters: [adapter, adapter],
  })).toThrow();
});
