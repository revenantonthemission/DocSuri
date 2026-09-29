// F13: all public DTO schemas form ONE offline, build-consumed generation.
import { compile } from 'json-schema-to-typescript';
import { createHash } from 'node:crypto';
import { readFile, mkdir, writeFile, rename, rm } from 'node:fs/promises';
import { resolve, dirname, basename } from 'node:path';
import { fileURLToPath } from 'node:url';
import { excludeLiteralPath, loadCatalog, loadFlatCatalog } from '../../shared/schema-catalog.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const check = args.includes('--check');
const rootArg = args.indexOf('--schema-root');
const schemaRoot = rootArg >= 0 ? resolve(args[rootArg + 1] ?? '') : resolve(here, '../../shared');
const output = resolve(here, '../types/wire/dtos.ts');
const identifier = (name) => {
  const value = name.replace(/[^A-Za-z0-9_]/gu, '_');
  return /^[A-Za-z_]/u.test(value) ? value : `_${value}`;
};

export async function build(root, { manifest = false } = {}) {
  // An explicit custom root is a developer/test input. Normal CLI/CI always requires the manifest.
  const { catalog, raw } = await (manifest ? loadCatalog(root) : loadFlatCatalog(root));
  const roots = manifest ? catalog.consumerRoots('typescript') : [...catalog.documents.keys()];
  const exports = catalog.exports(roots, 'public');
  const closure = catalog.closure(exports, 'public');
  const hash = createHash('sha256');
  hash.update(manifest ? 'catalog-v1:typescript' : 'explicit-flat-catalog');
  for (const bytes of raw) hash.update(bytes);
  const aliases = new Map(), names = new Map();
  function prefix(at) {
    const name = identifier(basename(catalog.paths.get(at.document), '.schema.json'));
    return name[0].toUpperCase() + name.slice(1);
  }
  function declare(at, name) {
    if (names.has(name) && names.get(name) !== at.key) throw new Error('generated export collision');
    names.set(name, at.key); aliases.set(at.key, { at, name });
  }
  for (const at of exports) declare(at, `${prefix(at)}${at.path.length ? identifier(at.path[1]) : 'Response'}`);
  for (const at of closure.values()) {
    const target = catalog.references.get(at.key);
    if (target && !aliases.has(target.key)) {
      declare(target, `${prefix(target)}Ref${createHash('sha256').update(target.key).digest('hex').slice(0, 16)}`);
    }
  }
  function normalize(value) {
    if (typeof value === 'boolean') return value;
    const result = { ...value };
    for (const key of ['$schema', '$defs', 'definitions']) delete result[key];
    // Annotation-only JSON Schema permits EVERY JSON value. The emitter otherwise infers an
    // object for description-only fields, narrowing valid wire IDs/reasons/relevance incorrectly.
    if (Object.keys(result).every((key) => ['title', 'description', 'default', 'examples', '$comment', 'deprecated', 'readOnly', 'writeOnly'].includes(key))) {
      result.tsType = 'unknown';
    }
    return result;
  }
  const definitions = {};
  for (const { at, name } of aliases.values()) {
    const node = catalog.rewriteNode(at, (target) => `#/$defs/${aliases.get(target.key).name}`, normalize);
    definitions[name] = typeof node === 'boolean'
      ? { tsType: node ? 'unknown' : 'never', title: name }
      : { ...node, title: name };
  }
  return compile({ type: 'object', properties: {}, additionalProperties: false, $defs: definitions }, 'PublicWire', {
    bannerComment: `/* DO NOT EDIT. Declared public schema closure, offline. SHA256:${hash.digest('hex')} */`,
    unreachableDefinitions: true,
    declareExternallyReferenced: true,
    unknownAny: true,
    $refOptions: {
      resolve: { file: false, http: false, external: false },
      dereference: { excludedPathMatcher: excludeLiteralPath },
    },
  });
}

async function main() {
  const source = await build(schemaRoot, { manifest: rootArg < 0 });
  if (check) {
    const committed = await readFile(output, 'utf8');
    if (committed !== source) throw new Error('build-consumed contract drift');
    console.log('ok: generated wire matches every public DTO schema');
    return;
  }
  await mkdir(dirname(output), { recursive: true });
  // One generated module is the complete TS publication unit. Rename preserves old-or-new.
  const staged = `${output}.${process.pid}.tmp`;
  try {
    await writeFile(staged, source, { flag: 'wx' });
    await rename(staged, output);
  } finally {
    await rm(staged, { force: true });
  }
  console.log('generated build-consumed public wire');
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    console.error(`contract generation failed: ${error.message}`);
    process.exitCode = 1;
  });
}
