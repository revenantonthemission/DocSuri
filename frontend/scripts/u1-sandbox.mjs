/** Credential-free public-source copy for U1 installs/builds. Never copies .env,
 * node_modules, .next, credentials or symlinks; never deletes an existing target.
 * This is a development runner, not staging or network-isolation evidence.
 */
import { createHash } from 'node:crypto';
import { lstat, mkdir, readdir, readFile, realpath, writeFile } from 'node:fs/promises';
import { basename, dirname, isAbsolute, join, relative, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const PUBLIC_DIRS = ['app', 'components', 'lib', 'types', 'mocks', 'test', 'e2e', 'scripts', 'public'];
const PUBLIC_FILES = [
  'package.json', 'pnpm-lock.yaml', 'next.config.mjs', 'next-env.d.ts', 'middleware.ts',
  'tsconfig.json', 'tsconfig.u1.json', 'vitest.config.ts', 'vitest.u1.config.ts',
  'vitest.contracts.config.ts', 'playwright.config.ts', 'playwright.u1.config.ts',
  'eslint.config.mjs', 'postcss.config.mjs', '.prettierrc',
  'instrumentation-client.ts', 'instrumentation.ts', 'sentry.server.config.ts',
];

function inside(root, path) {
  const rel = relative(root, path);
  return rel !== '' && !rel.startsWith(`..${sep}`) && rel !== '..' && !isAbsolute(rel);
}

async function copyPublic(source, target, hashes) {
  const info = await lstat(source);
  if (info.isSymbolicLink()) throw new Error('Public source symlink refused');
  if (info.isDirectory()) {
    await mkdir(target, { recursive: true, mode: 0o700 });
    for (const entry of (await readdir(source)).sort()) {
      // No runtime/credential-bearing dotfile or dependency tree is copied.
      if (entry.startsWith('.') || entry === 'node_modules' || entry === 'coverage') continue;
      await copyPublic(join(source, entry), join(target, entry), hashes);
    }
    return;
  }
  if (!info.isFile()) throw new Error('Non-regular public source refused');
  const bytes = await readFile(source);
  await mkdir(dirname(target), { recursive: true, mode: 0o700 });
  await writeFile(target, bytes, { flag: 'wx', mode: info.mode & 0o777 });
  hashes.push({ source, target, sha256: createHash('sha256').update(bytes).digest('hex') });
}

export async function createSandbox(workspace, target, temporaryParent) {
  const root = await realpath(workspace);
  const parent = await realpath(temporaryParent);
  const requested = resolve(target);
  const targetParent = await realpath(dirname(requested));
  const destination = join(targetParent, basename(requested));
  // Caller supplies an already-existing trusted temporary parent. Only a new
  // immediate child is admitted, preventing hidden parent symlink traversal.
  if (targetParent !== parent || inside(root, destination) || destination === root) {
    throw new Error('Sandbox must be a new child of the temporary parent outside the workspace');
  }
  await mkdir(destination, { mode: 0o700 });
  const hashes = [];
  for (const path of [...PUBLIC_DIRS, ...PUBLIC_FILES]) {
    const source = join(root, 'frontend', path);
    try { await lstat(source); } catch (error) {
      if (error.code === 'ENOENT' && !['package.json', 'pnpm-lock.yaml'].includes(path)) continue;
      throw error;
    }
    await copyPublic(source, join(destination, 'frontend', path), hashes);
  }
  // Type/contract scripts retain their relative shared-schema source boundary.
  for (const path of [
    'shared/dtos', 'shared/events', 'shared/vector-spec', 'ops/platform-integrity/timeouts.yaml',
  ]) {
    const source = join(root, path);
    try { await lstat(source); } catch (error) {
      if (error.code === 'ENOENT') continue;
      throw error;
    }
    await copyPublic(source, join(destination, path), hashes);
  }
  const inventory = hashes.map(({ source, target: copied, sha256 }) => ({
    path: relative(root, source), copiedPath: relative(destination, copied), sha256,
  }));
  await writeFile(join(destination, 'public-source.json'), JSON.stringify({
    version: 1, purpose: 'u1-development-only', files: inventory,
  }, null, 2), { flag: 'wx', mode: 0o600 });
  await mkdir(join(destination, 'empty-home'), { mode: 0o700 });
  return { directory: destination, files: inventory.length };
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const [workspace, target, temporaryParent] = process.argv.slice(2);
  if (!workspace || !target || !temporaryParent) {
    throw new Error('Usage: node scripts/u1-sandbox.mjs <workspace> <new-target> <temporary-parent>');
  }
  console.log(JSON.stringify(await createSandbox(workspace, target, temporaryParent)));
}
