// Read-only document consistency checks. Run with Bun and an installed Mermaid module path.
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { dirname, resolve, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const stage = dirname(fileURLToPath(import.meta.url));
const root = resolve(stage, '../../../../../../../');
const read = name => readFileSync(resolve(stage, name), 'utf8');
const catalogue = read('unit-of-work.md');
const dependencies = read('unit-of-work-dependency.md');
const storyMap = read('unit-of-work-story-map.md');
const questions = read('units-generation-questions.md');
const requirements = read('../requirements-analysis/requirements.md');
const trace = JSON.parse(read('traceability.json'));
const fenced = (s, lang) => {
  const hits = [...s.matchAll(new RegExp('```' + lang + '\\n([\\s\\S]*?)\\n```', 'g'))];
  assert.equal(hits.length, 1, `Exactly one ${lang} block is required`);
  return hits[0][1];
};
const units = [...catalogue.matchAll(/^\| (U\d+) \| (u\d+-[a-z-]+) \| (service|library) \| (shared|embedded|standalone) \| (S|M|L|XL) \|/gm)]
  .map(([, id, name, kind, deployment, complexity]) => ({ id, name, kind, deployment, complexity }));
assert.equal(units.length, 8);
assert.equal(new Set(units.map(u => u.id)).size, units.length);
assert.equal(new Set(units.map(u => u.name)).size, units.length);
assert.deepEqual(units.map(u => u.id), Array.from({ length: 8 }, (_, i) => `U${i + 1}`));
for (const u of units) assert.match(u.name, /^[a-z][a-z0-9-]{0,63}$/);
const byId = new Map(units.map(u => [u.id, u]));
const byName = new Map(units.map(u => [u.name, u]));
const confirmedUnits = [...questions.matchAll(/^\| (U\d+) \| (u\d+-[a-z-]+) \| (service|library) \|/gm)]
  .map(([, id, name, kind]) => ({ id, name, kind }));
assert.deepEqual(units.map(({ id, name, kind }) => ({ id, name, kind })), confirmedUnits);

const graph = Bun.YAML.parse(fenced(dependencies, 'yaml'));
assert.deepEqual(Object.keys(graph), ['units']);
assert.equal(graph.units.length, units.length);
const edges = [];
for (const entry of graph.units) {
  assert.deepEqual(Object.keys(entry).sort(), ['depends_on', 'kind', 'name']);
  const unit = byName.get(entry.name);
  assert.ok(unit, `Unknown unit ${entry.name}`);
  assert.equal(entry.kind, unit.kind);
  assert.ok(Array.isArray(entry.depends_on));
  assert.equal(new Set(entry.depends_on).size, entry.depends_on.length);
  for (const dependency of entry.depends_on) {
    assert.ok(byName.has(dependency), `Unknown dependency ${dependency}`);
    assert.notEqual(dependency, entry.name);
    edges.push(`${unit.id}->${byName.get(dependency).id}`);
  }
}
assert.equal(new Set(graph.units.map(u => u.name)).size, units.length);
const visited = new Set(), active = new Set();
const visit = name => {
  assert.ok(!active.has(name), `Cycle through ${name}`);
  if (visited.has(name)) return;
  active.add(name);
  for (const dep of graph.units.find(u => u.name === name).depends_on) visit(dep);
  active.delete(name); visited.add(name);
};
graph.units.forEach(u => visit(u.name));
const tableEdges = text => [...text.matchAll(/^\| (U\d+) \| (None|U\d+(?:, U\d+)*) \|/gm)]
  .flatMap(([, id, deps]) => deps === 'None' ? [] : deps.split(', ').map(dep => `${id}->${dep}`)).sort();
assert.deepEqual([...edges].sort(), tableEdges(dependencies), 'DAG table parity');
assert.deepEqual([...edges].sort(), tableEdges(questions), 'Confirmed dependency plan parity');
const diagram = fenced(dependencies, 'mermaid');
const diagramNodes = [...diagram.matchAll(/^  (U\d+)\["[^\n]+"\]$/gm)].map(m => m[1]);
assert.deepEqual(diagramNodes, units.map(u => u.id));
const diagramEdges = [...diagram.matchAll(/^  (U\d+) --> (U\d+)$/gm)].map(([, a, b]) => `${a}->${b}`).sort();
assert.deepEqual(diagramEdges, [...edges].sort(), 'Mermaid edge parity');

const domain = Bun.YAML.parse(fenced(read('../domain-design/components.md'), 'yaml'));
const responsibilitySection = catalogue.split('## Component responsibility across increments\n')[1].split('\n## ')[0];
const components = [...responsibilitySection.matchAll(/^\| ([A-Z][A-Za-z]+) \|/gm)]
  .map(m => m[1]).filter(name => name !== 'Component');
assert.deepEqual(components, domain.components.map(c => c.name), 'All approved component owners retained');

const upstreamIds = [...requirements.matchAll(/^(?:### (FR\d+)\s|\- \*\*(FR\d+\.\d+):\*\*)/gm)]
  .map(m => m[1] ?? m[2]);
assert.equal(upstreamIds.length, 70);
assert.equal(trace.stage, 'units-generation');
assert.deepEqual(trace.upstream_ids, upstreamIds);
assert.deepEqual(trace.coverage.map(r => r.id), upstreamIds);
const rows = [...storyMap.matchAll(/^\|\s*[*`]*(FR\d+(?:\.\d+)?)[*`]*\s*\|.*$/gm)];
assert.deepEqual(rows.map(m => m[1]), upstreamIds, 'Exactly one map row per FR in source order');
const participating = new Set();
for (let i = 0; i < rows.length; i++) {
  const row = rows[i][0], entry = trace.coverage[i];
  assert.equal(entry.status, 'OK');
  const target = byId.get(entry.target) ?? byName.get(entry.target);
  assert.ok(target, `Unknown trace target ${entry.target}`);
  assert.match(row, new RegExp(`\\b${target.id}\\b`));
  assert.ok(row.includes(target.name), `Missing target directory on ${entry.id}`);
  for (const [id, u] of byId) if (new RegExp(`\\b${id}\\b`).test(row)) {
    participating.add(id);
    assert.ok(row.includes(u.name), `Missing directory for ${id} on ${entry.id}`);
  }
}
assert.deepEqual([...participating].sort(), [...byId.keys()].sort());
const nfrRows = [...storyMap.matchAll(/^\|\s*[*`]*(NFR\d+)[*`]*(?:\s+—[^|]*)?\s*\|/gm)].map(m => m[1]);
assert.deepEqual(nfrRows, Array.from({ length: 10 }, (_, i) => `NFR${i + 1}`));
for (let i = 1; i <= 9; i++) assert.ok(storyMap.includes(`IB-0${i}`), `Missing IB-0${i}`);
for (const name of ['unit-of-work.md', 'unit-of-work-dependency.md', 'unit-of-work-story-map.md', 'units-generation-questions.md']) {
  const text = read(name);
  assert.ok(!text.includes('\uFFFD'), `${name}: replacement character`);
  for (const [, destination] of text.matchAll(/\]\(([^)]+)\)/g)) {
    if (/^[a-z]+:/i.test(destination) || destination.startsWith('#')) continue;
    assert.ok(existsSync(resolve(stage, destination.split('#')[0])), `${name}: broken link ${destination}`);
  }
}
assert.ok(process.argv[2], 'Pass the installed mermaid.esm.mjs path');
const { JSDOM } = await import(pathToFileURL(join(root, 'frontend/node_modules/jsdom/lib/api.js')).href);
const dom = new JSDOM('<!doctype html><html><body></body></html>');
globalThis.window = dom.window; globalThis.document = dom.window.document; globalThis.DOMParser = dom.window.DOMParser;
const { default: mermaid } = await import(pathToFileURL(resolve(process.argv[2])).href);
mermaid.initialize({ startOnLoad: false, securityLevel: 'strict' });
const parsed = await mermaid.parse(diagram);
console.log(JSON.stringify({ units: units.length, service: units.filter(u => u.kind === 'service').length,
  library: units.filter(u => u.kind === 'library').length, components: components.length, edges: edges.length,
  parentRequirements: upstreamIds.filter(x => !x.includes('.')).length,
  subrequirements: upstreamIds.filter(x => x.includes('.')).length,
  nfrRows: nfrRows.length, mermaid: parsed.diagramType, checks: 'passed' }, null, 2));
