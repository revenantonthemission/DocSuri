// @vitest-environment node
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { expect, it } from 'vitest';
import { mkdtemp, readFile, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import fc from 'fast-check';

// @ts-expect-error The Node emitter is a standalone .mjs tooling entrypoint.
import { build } from '../scripts/gen-types.mjs';
// @ts-expect-error Shared offline tooling is a standalone .mjs module.
import { Catalog, loadCatalog, parseJson } from '../../shared/schema-catalog.mjs';

interface SchemaCase {
  name: string;
  valid: boolean;
  documents: Record<string, unknown>[];
  visibility?: Record<string, string>;
  consumer?: { roots: string[]; visibility: string };
  references?: { base: string; ref: string; document: string; pointer: string }[];
}
const cases: SchemaCase[] = JSON.parse(await readFile(new URL('../../shared/schema-conformance.json', import.meta.url), 'utf8'));
it.each(cases)('cross-language catalog: $name', (item) => {
  function validate() {
    const catalog = new Catalog(item.documents, { visibility: new Map(Object.entries(item.visibility ?? {})) });
    if (item.consumer) catalog.exports(item.consumer.roots, item.consumer.visibility);
    for (const ref of item.references ?? []) {
      const location = catalog.resolve(ref.base, ref.ref);
      expect([location.document, location.pointer]).toEqual([ref.document, ref.pointer]);
    }
  }
  if (item.valid) validate();
  else expect(validate).toThrow();
});

it('rejects duplicate JSON members, invalid UTF-8 and nonfinite numeric literals', () => {
  for (const input of [Buffer.from('{"a":1,"a":2}'), Buffer.from([0xff]), Buffer.from('1e999')]) {
    expect(() => parseJson(input)).toThrow();
  }
});

it('validates the production inventory and keeps internal resources outside public roots', async () => {
  const { catalog } = await loadCatalog(fileURLToPath(new URL('../../shared', import.meta.url)));
  expect(catalog.documents.size).toBe(14);
  expect(catalog.consumerRoots('typescript')).toHaveLength(8);
  expect(catalog.consumerRoots('python')).toHaveLength(14);
});

it('F13 rejects a missing local schema catalog rather than skipping targets', () => {
  const script = fileURLToPath(new URL('../scripts/gen-types.mjs', import.meta.url));
  const result = spawnSync(process.execPath, [script, '--check', '--schema-root', '/missing-schema-catalog'], {
    encoding: 'utf8', timeout: 120_000,
    env: { PATH: process.env.PATH, HOME: process.env.HOME, NODE_OPTIONS: '', NODE_ENV: 'test' },
  });
  expect(result.error).toBeUndefined();
  expect(result.status).not.toBe(0);
}, 125_000);

it('preserves title fields and annotation-only unknown values in generated wire', async () => {
  const root = await mkdtemp(join(tmpdir(), 'docsuri-schema-'));
  try {
    await writeFile(join(root, 'sample.schema.json'), JSON.stringify({
      $id: 'https://schema.test/sample', $defs: { Item: {
        type: 'object', properties: { title: { type: 'string' }, id: { description: 'opaque value' } },
        required: ['title', 'id'], additionalProperties: false,
      } },
    }));
    const generated = await build(root);
    expect(generated).toContain('title: string;');
    expect(generated).toContain('id: unknown;');
  } finally { await rm(root, { recursive: true, force: true }); }
});

it('rejects every undeclared remote reference without network resolution', async () => {
  await fc.assert(fc.asyncProperty(fc.integer({ min: 1, max: 1000 }), async (id) => {
    const root = await mkdtemp(join(tmpdir(), 'docsuri-schema-'));
    try {
      await writeFile(join(root, 'sample.schema.json'), JSON.stringify({
        $id: 'https://schema.test/sample', $defs: { Item: { $ref: `https://missing.test/${id}#/$defs/Item` } },
      }));
      await expect(build(root)).rejects.toThrow('unresolved local reference');
    } finally { await rm(root, { recursive: true, force: true }); }
  }), { seed: 20260924, numRuns: 200 });
});

it('treats keyword-shaped literal values as data and supports nested local IDs', async () => {
  const root = await mkdtemp(join(tmpdir(), 'docsuri-schema-'));
  try {
    await writeFile(join(root, 'sample.schema.json'), JSON.stringify({
      $id: 'https://schema.test/sample', $defs: {
        Node: { $id: 'node', $anchor: 'Node', type: 'object', properties: {
          $id: { type: 'string' }, next: { $ref: '#Node' },
          metadata: { type: 'object', default: { $id: 'data', $ref: 'https://literal.test/data' } },
        } },
        Alias: { $ref: 'node#Node' },
      },
    }));
    const source = await build(root);
    expect(source).toContain('SampleNode');
    expect(source).toContain('SampleAlias');
    expect(source).toContain('$id');
  } finally { await rm(root, { recursive: true, force: true }); }
});

it('supports boolean schemas and preserves literal reference-shaped constants', async () => {
  const root = await mkdtemp(join(tmpdir(), 'docsuri-schema-'));
  try {
    await writeFile(join(root, 'sample.schema.json'), JSON.stringify({
      $id: 'https://schema.test/sample', $defs: {
        Never: false, Anything: true,
        Literal: { const: { $ref: '#not-a-schema', $id: 'data' } },
      },
    }));
    const source = await build(root);
    expect(source).toContain('SampleNever = never;');
    expect(source).toContain('SampleAnything = unknown;');
    expect(source).toContain('#not-a-schema');
  } finally { await rm(root, { recursive: true, force: true }); }
});

it('rejects export-name collisions rather than silently dropping a target', async () => {
  const root = await mkdtemp(join(tmpdir(), 'docsuri-schema-'));
  try {
    await writeFile(join(root, 'sample.schema.json'), JSON.stringify({
      $id: 'https://schema.test/sample', $defs: { 'A/B': { type: 'string' }, A_B: { type: 'number' } },
    }));
    await expect(build(root)).rejects.toThrow('collision');
  } finally { await rm(root, { recursive: true, force: true }); }
});

it('leaves published wire untouched if one declared target fails', async () => {
  const root = await mkdtemp(join(tmpdir(), 'docsuri-schema-'));
  const output = new URL('../types/wire/dtos.ts', import.meta.url);
  const before = await readFile(output);
  try {
    await writeFile(join(root, 'valid.schema.json'), JSON.stringify({ $id: 'https://schema.test/valid', type: 'string' }));
    await writeFile(join(root, 'invalid.schema.json'), JSON.stringify({ $id: 'https://schema.test/invalid', $ref: 'https://missing.test/schema' }));
    const script = fileURLToPath(new URL('../scripts/gen-types.mjs', import.meta.url));
    const result = spawnSync(process.execPath, [script, '--schema-root', root], { encoding: 'utf8', timeout: 5000 });
    expect(result.status).not.toBe(0);
    expect(await readFile(output)).toEqual(before);
  } finally { await rm(root, { recursive: true, force: true }); }
});
