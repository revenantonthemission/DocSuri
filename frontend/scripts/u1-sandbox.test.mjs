import assert from 'node:assert/strict';
import { mkdtemp, mkdir, readFile, rm, symlink, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';
import { createSandbox } from './u1-sandbox.mjs';

async function fixture(run) {
  const temporary = await mkdtemp(join(tmpdir(), 'docsuri-u1-runner-test-'));
  try {
    const source = join(temporary, 'source');
    await mkdir(join(source, 'frontend'), { recursive: true });
    await writeFile(join(source, 'frontend/package.json'), '{"private":true}');
    await writeFile(join(source, 'frontend/pnpm-lock.yaml'), 'lockfileVersion: "9.0"');
    await run({ temporary, source, target: join(temporary, 'sandbox') });
  } finally {
    await rm(temporary, { recursive: true });
  }
}

test('copies exact public bytes and emits a source-bound inventory', async () => {
  await fixture(async ({ temporary, source, target }) => {
    await mkdir(join(source, 'frontend/app'));
    await writeFile(join(source, 'frontend/app/page.tsx'), 'export default "한글";\n');
    const result = await createSandbox(source, target, temporary);
    assert.equal(result.files, 3);
    assert.equal(await readFile(join(target, 'frontend/app/page.tsx'), 'utf8'), 'export default "한글";\n');
    const inventory = JSON.parse(await readFile(join(target, 'public-source.json'), 'utf8'));
    assert.match(inventory.files[0].sha256, /^[a-f0-9]{64}$/);
    assert.equal(inventory.purpose, 'u1-development-only');
  });
});

test('does not copy fixture credentials, runtime output or dependency trees', async () => {
  await fixture(async ({ temporary, source, target }) => {
    await writeFile(join(source, 'frontend/.env'), 'SYNTHETIC_SECRET=not-a-credential');
    await mkdir(join(source, 'frontend/app'));
    for (const name of ['.env', '.next', 'node_modules']) {
      await mkdir(join(source, 'frontend/app', name));
      await writeFile(join(source, 'frontend/app', name, 'fixture'), 'not-public');
    }
    const result = await createSandbox(source, target, temporary);
    assert.equal(result.files, 2);
    await assert.rejects(readFile(join(target, 'frontend/.env')), { code: 'ENOENT' });
  });
});

test('refuses a target within the source workspace before writing it', async () => {
  await fixture(async ({ temporary, source }) => {
    await assert.rejects(createSandbox(source, join(source, 'sandbox'), source), /outside the workspace/);
    await assert.rejects(readFile(join(source, 'sandbox/public-source.json')), { code: 'ENOENT' });
  });
});

test('refuses nested target parents not equal to the trusted temporary parent', async () => {
  await fixture(async ({ temporary, source }) => {
    const other = join(temporary, 'other');
    await mkdir(other);
    await assert.rejects(createSandbox(source, join(other, 'sandbox'), temporary), /temporary parent/);
  });
});

test('refuses reuse instead of deleting or overwriting an existing target', async () => {
  await fixture(async ({ temporary, source, target }) => {
    await mkdir(target);
    await writeFile(join(target, 'marker'), 'preserve');
    await assert.rejects(createSandbox(source, target, temporary), { code: 'EEXIST' });
    assert.equal(await readFile(join(target, 'marker'), 'utf8'), 'preserve');
  });
});

test('refuses symlinked public sources without following or reading them', async () => {
  await fixture(async ({ temporary, source, target }) => {
    await mkdir(join(source, 'frontend/app'));
    await symlink(join(temporary, 'does-not-exist'), join(source, 'frontend/app/private-link'));
    await assert.rejects(createSandbox(source, target, temporary), /symlink refused/);
  });
});

test('missing required manifests fails rather than producing an empty sandbox pass', async () => {
  await fixture(async ({ temporary, source, target }) => {
    await rm(join(source, 'frontend/package.json'));
    await assert.rejects(createSandbox(source, target, temporary), { code: 'ENOENT' });
  });
});
