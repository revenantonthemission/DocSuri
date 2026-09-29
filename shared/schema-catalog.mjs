// JSON Schema 2020-12 offline profile; conformance-tested against docsuri_schema (Python).
import { open, readdir } from 'node:fs/promises';
import { constants } from 'node:fs';
import { resolve, relative, join, posix } from 'node:path';

const maps = new Set(['$defs', 'definitions', 'properties', 'patternProperties', 'dependentSchemas']);
const arrays = new Set(['allOf', 'anyOf', 'oneOf', 'prefixItems']);
const singles = new Set(['items', 'contains', 'additionalProperties', 'unevaluatedProperties',
  'unevaluatedItems', 'propertyNames', 'not', 'if', 'then', 'else']);
const definitions = new Set(['$defs', 'definitions']);
const annotations = new Set(['$id', '$schema', '$anchor', '$comment', '$defs', 'definitions',
  'title', 'description', 'examples', 'default', 'deprecated', 'readOnly', 'writeOnly', 'x-docsuri-visibility']);
const unsupported = new Set(['$dynamicRef', '$dynamicAnchor', '$recursiveRef', '$recursiveAnchor', '$vocabulary']);
const exposure = new Map([['public', 0], ['server', 1], ['internal', 2]]);
const dialect = 'https://json-schema.org/draft/2020-12/schema';
const limit = 16 * 1024 ** 2;
const object = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);
const sameKeys = (value, keys) => object(value) && Object.keys(value).sort().join('|') === [...keys].sort().join('|');
const pointer = (path) => path.map((part) => `/${part.replaceAll('~', '~0').replaceAll('/', '~1')}`).join('');
const location = (document, path = []) => ({ document, path, pointer: pointer(path), key: JSON.stringify([document, path]) });

function bounds(value, depth = 0) {
  if (depth > 64) throw new Error('schema nesting limit');
  if (typeof value === 'string') {
    for (const character of value) {
      const code = character.codePointAt(0);
      if (code >= 0xd800 && code <= 0xdfff) throw new Error('invalid schema Unicode');
    }
  } else if (Array.isArray(value)) {
    value.forEach((item) => bounds(item, depth + 1));
  } else if (object(value)) {
    for (const [key, item] of Object.entries(value)) { bounds(key, depth + 1); bounds(item, depth + 1); }
  } else if (typeof value === 'number') {
    if (!Number.isFinite(value) || Math.abs(value) > Number.MAX_SAFE_INTEGER) throw new Error('unsupported schema number');
  } else if (value !== null && typeof value !== 'boolean') throw new Error('invalid JSON value');
}

export function parseJson(bytes) {
  if (bytes.length > limit) throw new Error('schema byte limit');
  let text, value;
  try {
    text = new TextDecoder('utf-8', { fatal: true }).decode(bytes);
    value = JSON.parse(text);
  } catch { throw new Error('invalid schema JSON'); }
  // JSON.parse loses duplicate members. Inspect the already-valid token stream before use.
  const stack = [];
  for (const [token] of text.matchAll(/"(?:\\[\s\S]|[^"\\])*"|[{}\[\],:]|[^{}\[\],:\s]+/gu)) {
    if (token === '{' || token === '[') stack.push({ object: token === '{', key: token === '{', seen: new Set() });
    else if (token === '}' || token === ']') stack.pop();
    else if (token === ',' && stack.at(-1)?.object) stack.at(-1).key = true;
    else if (token.startsWith('"') && stack.at(-1)?.key) {
      const frame = stack.at(-1), key = JSON.parse(token);
      if (frame.seen.has(key)) throw new Error('duplicate JSON key');
      frame.seen.add(key); frame.key = false;
    }
  }
  bounds(value);
  return value;
}

function identity(value) {
  if (typeof value !== 'string' || !value.length || value.length > 4096 || value.includes('#')) throw new Error('invalid schema identity');
  const url = new URL(value);
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || /\s/u.test(value) || url.href !== value) {
    throw new Error('unsupported or noncanonical schema identity');
  }
  return value;
}

function* children(value) {
  for (const [key, item] of Object.entries(value)) {
    if (maps.has(key)) {
      if (!object(item)) throw new Error('invalid schema map');
      for (const [name, schema] of Object.entries(item)) yield [[key, name], schema];
    } else if (arrays.has(key)) {
      if (!Array.isArray(item)) throw new Error('invalid schema array');
      for (const [index, schema] of item.entries()) yield [[key, String(index)], schema];
    } else if (singles.has(key)) yield [[key], item];
  }
}

// Ref-parser crawls arbitrary JSON, including const/default/enum data. Its exclusion callback
// follows schema-position grammar so dereferenced nodes can move without turning data into refs.
export function excludeLiteralPath(path) {
  const pointerPath = path.startsWith('#') ? path.slice(1) : path;
  if (!pointerPath) return false;
  const tokens = pointerPath.slice(1).split('/').map((token) => decodeURIComponent(token).replaceAll('~1', '/').replaceAll('~0', '~'));
  let state = 'schema';
  for (const token of tokens) {
    if (state === 'map') state = 'schema';
    else if (state === 'array') {
      if (!/^(0|[1-9][0-9]*)$/u.test(token)) return true;
      state = 'schema';
    } else if (maps.has(token)) state = 'map';
    else if (arrays.has(token)) state = 'array';
    else if (!singles.has(token)) return true;
  }
  return false;
}

export class Catalog {
  constructor(documents, { visibility = new Map(), paths = new Map(), consumers = {} } = {}) {
    if (!documents.length || documents.length > 1000) throw new Error('empty or oversized schema catalog');
    this.documents = new Map(); this.resources = new Map(); this.anchors = new Map();
    this.nodes = new Map(); this.references = new Map(); this.paths = paths; this.consumers = structuredClone(consumers);
    let total = 0;
    for (const source of documents) {
      if (!object(source)) throw new Error('schema document must declare an identity');
      bounds(source);
      const size = Buffer.byteLength(JSON.stringify(source)); total += size;
      if (size > limit || total > 64 * 1024 ** 2) throw new Error('schema catalog byte limit');
      const id = identity(source.$id);
      if (this.documents.has(id)) throw new Error('duplicate schema identity');
      this.documents.set(id, structuredClone(source));
    }
    for (const [id, document] of this.documents) this.index(location(id), document, id, visibility.has(id) ? visibility.get(id) : 'internal');
    for (const node of this.nodes.values()) {
      if (object(node.value) && Object.hasOwn(node.value, '$ref')) {
        if (this.references.size >= 20000) throw new Error('schema edge limit');
        this.references.set(node.location.key, this.resolve(node.base, node.value.$ref));
      }
    }
  }

  index(at, value, base, visibility) {
    if (this.nodes.size >= 100000 || !exposure.has(visibility)) throw new Error('schema node limit or visibility invalid');
    if (typeof value !== 'boolean' && !object(value)) throw new Error('schema node must be object or boolean');
    if (object(value)) {
      if ((Object.hasOwn(value, '$schema') ? value.$schema : dialect) !== dialect || Object.keys(value).some((key) => unsupported.has(key))) throw new Error('unsupported schema dialect or dynamic feature');
      if (Object.hasOwn(value, '$id')) {
        if (typeof value.$id !== 'string') throw new Error('invalid schema identity');
        base = identity(new URL(value.$id, base).href);
        if (this.resources.has(base) || this.resources.size >= 1000) throw new Error('duplicate or oversized schema resources');
        this.resources.set(base, at);
      }
      if (Object.hasOwn(value, '$anchor')) {
        const anchor = value.$anchor, key = JSON.stringify([base, anchor]);
        if (typeof anchor !== 'string' || !/^[A-Za-z_][-A-Za-z0-9._]*$/u.test(anchor) || this.anchors.has(key)) throw new Error('invalid or duplicate schema anchor');
        this.anchors.set(key, at);
      }
      const declared = Object.hasOwn(value, 'x-docsuri-visibility') ? value['x-docsuri-visibility'] : visibility;
      if (!exposure.has(declared) || exposure.get(declared) < exposure.get(visibility)) throw new Error('schema visibility escalation');
      visibility = declared;
    }
    this.nodes.set(at.key, { location: at, value, base, visibility });
    if (object(value)) for (const [path, child] of children(value)) this.index(location(at.document, [...at.path, ...path]), child, base, visibility);
  }

  resolve(base, reference) {
    if (typeof reference !== 'string' || reference.length > 4096) throw new Error('invalid local reference');
    const url = new URL(reference, base), fragment = decodeURIComponent(url.hash.slice(1)); url.hash = '';
    const resource = this.resources.get(url.href);
    if (!resource) throw new Error('unresolved local reference');
    let target;
    if (!fragment) target = resource;
    else if (fragment.startsWith('/')) {
      const tokens = fragment.slice(1).split('/');
      if (tokens.some((token) => /~(?:[^01]|$)/u.test(token))) throw new Error('invalid JSON pointer escape');
      target = location(resource.document, [...resource.path, ...tokens.map((token) => token.replaceAll('~1', '/').replaceAll('~0', '~'))]);
    } else target = this.anchors.get(JSON.stringify([url.href, fragment]));
    if (!target || !this.nodes.has(target.key)) throw new Error('unresolved local fragment or non-schema target');
    return target;
  }

  exports(roots, visibility) {
    if (!roots.length || new Set(roots).size !== roots.length || !exposure.has(visibility)) throw new Error('invalid consumer roots or visibility');
    const output = [];
    for (const id of roots) {
      const value = this.documents.get(id);
      if (!value) throw new Error('unregistered consumer root');
      const items = ['$defs', 'definitions'].flatMap((key) => Object.keys(value[key] ?? {}).map((name) => location(id, [key, name])));
      output.push(...items);
      if (!items.length || Object.keys(value).some((key) => !annotations.has(key))) output.push(location(id));
    }
    this.closure(output, visibility);
    return output;
  }

  closure(roots, visibility) {
    const pending = [...roots], visited = new Map();
    while (pending.length) {
      const at = pending.pop();
      if (visited.has(at.key)) continue;
      const node = this.nodes.get(at.key);
      if (exposure.get(node.visibility) > exposure.get(visibility)) throw new Error('consumer visibility violation');
      visited.set(at.key, at);
      if (this.references.has(at.key)) pending.push(this.references.get(at.key));
      if (object(node.value)) for (const [path] of children(node.value)) {
        if (!definitions.has(path[0])) pending.push(location(at.document, [...at.path, ...path]));
      }
    }
    return visited;
  }

  rewriteNode(at, encodeReference, transform = (value) => value) {
    const value = this.nodes.get(at.key).value;
    if (typeof value === 'boolean') return transform(value, at);
    const output = transform(structuredClone(value), at);
    for (const key of ['$id', '$anchor', 'x-docsuri-visibility']) delete output[key];
    if (this.references.has(at.key)) output.$ref = encodeReference(this.references.get(at.key));
    for (const [path] of children(value)) {
      if (!Object.hasOwn(output, path[0])) continue;
      const child = this.rewriteNode(location(at.document, [...at.path, ...path]), encodeReference, transform);
      if (path.length === 1) output[path[0]] = child;
      else Object.defineProperty(output[path[0]], path[1], { value: child, enumerable: true, writable: true, configurable: true });
    }
    return output;
  }

  consumerRoots(name) {
    const consumer = this.consumers[name];
    if (!sameKeys(consumer, ['visibility', 'roots']) || !Array.isArray(consumer.roots)) throw new Error('unregistered consumer');
    this.exports(consumer.roots, consumer.visibility);
    return [...consumer.roots];
  }
}

async function source(path) {
  const handle = await open(path, constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK);
  try {
    const info = await handle.stat();
    if (!info.isFile() || info.size > limit) throw new Error('invalid schema file');
    const chunks = []; let size = 0;
    for await (const bytes of handle.createReadStream({ autoClose: false, start: 0, end: limit })) {
      size += bytes.length;
      if (size > limit) throw new Error('schema byte limit');
      chunks.push(bytes);
    }
    return Buffer.concat(chunks);
  } finally { await handle.close(); }
}

function safeRelative(value) {
  if (typeof value !== 'string' || !value || value.length > 4096 || value.includes('\\') || value === '.' || posix.isAbsolute(value) || value.split('/').includes('..') || posix.normalize(value) !== value) throw new Error('schema path escape or alias');
  return value;
}

export async function loadCatalog(root) {
  root = resolve(root);
  const manifestBytes = await source(join(root, 'schema-catalog.json')), manifest = parseJson(manifestBytes);
  if (!sameKeys(manifest, ['version', 'excludedDirectories', 'resources', 'consumers']) || manifest.version !== 1) throw new Error('unsupported schema catalog manifest');
  const excluded = new Set();
  for (const entry of manifest.excludedDirectories) {
    if (safeRelative(entry.path).includes('/') || typeof entry.reason !== 'string' || !entry.reason) throw new Error('invalid schema inventory exclusion');
    excluded.add(entry.path);
  }
  const declared = new Map();
  for (const entry of manifest.resources) {
    if (!sameKeys(entry, ['id', 'path', 'visibility'])) throw new Error('invalid schema resource declaration');
    const path = safeRelative(entry.path);
    if (declared.has(path) || excluded.has(path.split('/')[0]) || !path.endsWith('.json')) throw new Error('duplicate or excluded schema path');
    declared.set(path, entry);
  }
  const found = new Set(), pending = [root];
  while (pending.length) {
    const directory = pending.pop();
    for (const entry of await readdir(directory, { withFileTypes: true })) {
      if (directory === root && excluded.has(entry.name)) continue;
      const path = join(directory, entry.name);
      if (entry.isSymbolicLink()) throw new Error('schema inventory symlink');
      if (entry.isDirectory()) pending.push(path);
      else if (entry.name.endsWith('.schema.json')) found.add(relative(root, path));
      if (found.size > 1000) throw new Error('schema inventory limit');
    }
  }
  if (found.size !== declared.size || [...found].some((name) => !declared.has(name))) throw new Error('schema inventory mismatch');
  const documents = [], visibility = new Map(), paths = new Map(), raw = [manifestBytes];
  let total = 0;
  for (const name of [...declared.keys()].sort()) {
    const entry = declared.get(name), bytes = await source(join(root, name)); total += bytes.length;
    if (total > 64 * 1024 ** 2) throw new Error('schema catalog byte limit');
    const document = parseJson(bytes);
    if (!object(document) || document.$id !== entry.id) throw new Error('schema identity differs from manifest');
    documents.push(document); visibility.set(entry.id, entry.visibility); paths.set(entry.id, name);
    raw.push(Buffer.from(name), bytes);
  }
  const catalog = new Catalog(documents, { visibility, paths, consumers: manifest.consumers });
  const covered = new Set(Object.keys(catalog.consumers).flatMap((name) => catalog.consumerRoots(name)));
  if (covered.size !== catalog.documents.size || [...catalog.documents.keys()].some((id) => !covered.has(id))) throw new Error('unclassified schema consumer coverage');
  return { catalog, raw };
}

export async function loadFlatCatalog(root) {
  const names = (await readdir(root)).filter((name) => name.endsWith('.schema.json')).sort();
  const documents = [], paths = new Map(), visibility = new Map(), raw = [];
  for (const name of names) {
    const bytes = await source(join(root, name)), document = parseJson(bytes);
    documents.push(document); paths.set(document.$id, name); visibility.set(document.$id, 'public');
    raw.push(Buffer.from(name), bytes);
  }
  return { catalog: new Catalog(documents, { paths, visibility }), raw };
}
