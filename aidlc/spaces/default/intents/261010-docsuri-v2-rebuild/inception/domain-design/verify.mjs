import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';

// Read-only document checks. Run from any directory; Mermaid is supplied as a
// local module path so this verification adds no application dependency.
const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '../../../../../../../');
const require = createRequire(path.join(root, 'frontend/package.json'));
assert.ok(globalThis.Bun?.YAML?.parse, 'Run with Bun, which supplies the YAML parser.');
const read = name => fs.readFileSync(path.join(here, name), 'utf8');
const document = read('components.md');
const fenced = (text, language) => {
  const matches = [...text.matchAll(new RegExp('```' + language + '\\n([\\s\\S]*?)\\n```', 'g'))];
  assert.equal(matches.length, 1, `Exactly one ${language} block`);
  return matches[0][1];
};
const { components } = Bun.YAML.parse(fenced(document, 'yaml'));
assert.ok(Array.isArray(components) && components.length > 0);
const names = new Map();
const entities = new Map();
const keys = (value, allowed, label) => {
  assert.deepEqual(Object.keys(value).sort(), [...allowed].sort(), label);
};
for (const c of components) {
  keys(c, ['name','summary','behaviour','responsibilities','depends_on','dependents','external_dependencies','entities'], c.name);
  assert.match(c.name, /^[A-Z][A-Za-z0-9]*$/);
  assert.ok(!names.has(c.name), `Duplicate component ${c.name}`);
  names.set(c.name, c);
  assert.ok(c.summary && c.behaviour && c.responsibilities.length);
  for (const e of c.entities) {
    keys(e, ['name','identifier','attributes','references'], e.name);
    assert.ok(!entities.has(e.name), `Duplicate entity owner ${e.name}`);
    entities.set(e.name, c.name);
    assert.ok(e.identifier && e.attributes.includes(e.identifier));
    assert.equal(new Set(e.attributes).size, e.attributes.length);
    assert.ok(e.attributes.every(a => typeof a === 'string'));
  }
}
for (const c of components) {
  assert.equal(new Set(c.depends_on.map(d => d.component)).size, c.depends_on.length);
  for (const d of c.depends_on) {
    keys(d, ['component','interaction','style'], `${c.name} dependency`);
    assert.ok(names.has(d.component) && d.component !== c.name);
    assert.ok(['sync','async','event'].includes(d.style) && d.interaction);
    assert.deepEqual(names.get(d.component).dependents.filter(x => x.component === c.name), [{component:c.name,interaction:d.interaction}]);
  }
  for (const d of c.dependents) {
    keys(d, ['component','interaction'], `${c.name} dependent`);
    assert.equal(names.get(d.component)?.depends_on.filter(x => x.component === c.name && x.interaction === d.interaction).length, 1);
  }
  for (const e of c.entities) for (const r of e.references) {
    keys(r, ['entity','owned_by','relationship'], `${e.name} reference`);
    assert.equal(entities.get(r.entity), r.owned_by);
    assert.notEqual(r.owned_by, c.name, 'references is for cross-component identity');
    assert.ok(r.relationship);
  }
  for (const d of c.external_dependencies) {
    keys(d, ['name','kind','purpose'], `${c.name} external dependency`);
    assert.ok(['database','cache','queue','object-store','third-party-api','other'].includes(d.kind));
    assert.ok(d.name && d.purpose);
  }
}
const visited = new Set();
const active = new Set();
const visit = name => {
  assert.ok(!active.has(name), `Dependency cycle at ${name}`);
  if (visited.has(name)) return;
  active.add(name);
  for (const d of names.get(name).depends_on) visit(d.component);
  active.delete(name);
  visited.add(name);
};
for (const name of names.keys()) visit(name);

const table = (cols, rows) => '| '+cols.join(' | ')+' |\n|'+cols.map(()=>'---').join('|')+'|\n'+rows.map(r=>'| '+r.map(x=>String(x).replaceAll('|','\\|').replaceAll('\n',' ')).join(' | ')+' |').join('\n');
const derived = [
  table(['Component','Purpose','Depends On','Dependents','Entities Owned'], components.map(c=>[c.name,c.summary,c.depends_on.map(d=>d.component).join(', ')||'None',c.dependents.map(d=>d.component).join(', ')||'None',c.entities.map(e=>e.name).join(', ')])),
  table(['Entity','Owning Component','Identifier','Attributes','References'], components.flatMap(c=>c.entities.map(e=>[e.name,c.name,e.identifier,e.attributes.join(', '),e.references.map(r=>`${r.owned_by}.${r.entity}: ${r.relationship}`).join('; ')||'No cross-component reference']))),
  table(['Component','Dependency','Kind','Purpose'], components.flatMap(c=>c.external_dependencies.map(d=>[c.name,d.name,d.kind,d.purpose])))
];
for (const t of derived) assert.ok(document.includes(t), 'Human table must match YAML exactly');
const diagram = ['flowchart LR', ...components.map(c=>`  ${c.name}["${c.name}"]`), ...components.flatMap(c=>c.depends_on.map(d=>`  ${c.name} -->|"${d.style}: ${d.interaction}"| ${d.component}`))].join('\n');
assert.equal(fenced(document, 'mermaid'), diagram);

const requirements = fs.readFileSync(path.join(here, '../requirements-analysis/requirements.md'), 'utf8');
const ids = [...requirements.matchAll(/^### (FR\d+)\b|^- \*\*(FR\d+\.\d+):\*\*/gm)].map(m=>m[1]||m[2]);
const trace = JSON.parse(read('traceability.json'));
assert.equal(trace.stage, 'domain-design');
assert.deepEqual(trace.upstream_ids, ids);
assert.deepEqual(trace.coverage.map(row=>row.id), ids);
for (const row of trace.coverage) {
  assert.equal(row.status, 'OK');
  assert.ok(names.has(row.target) || entities.has(row.target), `Unknown target ${row.target}`);
}
const decisions = read('decisions.md');
const records = decisions.split(/^## ADR-/m).slice(1);
assert.ok(records.length > 0);
records.forEach((record, i) => {
  assert.ok(record.startsWith(String(i+1).padStart(3,'0')+':'));
  for (const field of ['Context','Decision','Consequences','Alternatives Rejected']) assert.ok(record.includes(`**${field}.**`), `Missing ADR field ${field}`);
});
for (const name of ['components.md','decisions.md','domain-design-questions.md']) {
  const text = read(name);
  assert.ok(!text.includes('\uFFFD'));
  for (const match of text.matchAll(/\]\(([^)]+)\)/g)) {
    const link = match[1];
    if (!link.includes('://') && !link.startsWith('#')) assert.ok(fs.existsSync(path.resolve(here, link.split('#')[0])), `${name}: ${link}`);
  }
}
const modulePath = process.argv[2];
assert.ok(modulePath, 'Supply the local mermaid.esm.mjs path for syntax validation.');
const { JSDOM } = require('jsdom');
const dom = new JSDOM('<!doctype html><html><body></body></html>');
globalThis.window = dom.window;
globalThis.document = dom.window.document;
const { default: mermaid } = await import(pathToFileURL(path.resolve(modulePath)).href);
const parsed = await mermaid.parse(diagram);
console.log(JSON.stringify({components:components.length,entities:entities.size,edges:components.reduce((n,c)=>n+c.depends_on.length,0),parentRequirements:ids.filter(id=>!id.includes('.')).length,subrequirements:ids.filter(id=>id.includes('.')).length,adrs:records.length,mermaid:parsed.diagramType,checks:'passed'},null,2));
