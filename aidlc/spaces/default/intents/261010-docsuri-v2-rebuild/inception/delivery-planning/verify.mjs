// Read-only planning checks; does not approve or execute a construction command.
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { parseBoltDag } from '../../../../../../../.codex/tools/aidlc-lib.ts';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '../../../../../../../');
const read = p => readFileSync(resolve(here, p), 'utf8');
const block = (s, language) => {
  const matches = [...s.matchAll(new RegExp('```' + language + '\\n([\\s\\S]*?)\\n```', 'g'))];
  assert.equal(matches.length, 1, `One ${language} block required`);
  return matches[0][1];
};
const requirements = read('../requirements-analysis/requirements.md');
const ids = [...requirements.matchAll(/^(?:### (FR\d+)\s|\- \*\*(FR\d+\.\d+):\*\*)/gm)]
  .map(m => m[1] ?? m[2]);
assert.equal(ids.length, 70);
assert.equal(new Set(ids).size, ids.length);
const {components} = Bun.YAML.parse(block(read('../domain-design/components.md'), 'yaml'));
const domainTargets = new Set(components.flatMap(c => [c.name, ...c.entities.map(e => e.name)]));
const units = [...read('../units-generation/unit-of-work.md').matchAll(/^\| (U\d+) \| (u\d+-[a-z-]+) \| (service|library) \| (shared|embedded|standalone) \| (S|M|L|XL) \|/gm)]
  .map(([,id,name,kind,group,complexity]) => ({id,name,kind,group,complexity}));
assert.equal(units.length, 8);
const byName = new Map(units.map(u => [u.name, u]));
const byId = new Map(units.map(u => [u.id, u]));
const traces = ['domain-design','units-generation'].map(stage => {
  const t = JSON.parse(read(`../${stage}/traceability.json`));
  assert.equal(t.stage, stage);
  assert.deepEqual(Object.keys(t).sort(), ['coverage','stage','upstream_ids']);
  assert.deepEqual(t.upstream_ids, ids, `${stage}: missing/extra/reordered upstream IDs`);
  assert.deepEqual(t.coverage.map(c => c.id), ids, `${stage}: duplicate/missing/orphan coverage`);
  const targets = stage === 'domain-design' ? domainTargets : new Set(byId.keys());
  for (const c of t.coverage) {
    assert.equal(c.status, 'OK', `${stage}/${c.id}: unresolved finding`);
    assert.ok(targets.has(c.target), `${stage}/${c.id}: invalid target ${c.target}`);
  }
  return t;
});
const dag = parseBoltDag(read('../units-generation/unit-of-work-dependency.md'));
assert.equal(dag.ok, true);
const order = dag.batches.flat().map(n => byName.get(n)?.id);
assert.deepEqual(order, ['U1','U7','U2','U3','U4','U5','U6','U8']);
const edgeCount = dag.units.reduce((n,u) => n + u.depends_on.length, 0);
assert.equal(edgeCount, 19);
for (const unit of dag.units) for (const dep of unit.depends_on) {
  assert.ok(order.indexOf(byName.get(dep).id) < order.indexOf(byName.get(unit.name).id));
}
const plan = read('bolt-plan.md');
const rows = [...plan.matchAll(/^\| (B\d\d) \| (U\d+) \| (u\d+-[a-z-]+) \| ([^|]+) \| (S|M|L|XL) \| ([^|]+) \|/gm)];
assert.equal(rows.length, 8);
for (let i=0; i<rows.length; i++) {
  const [,b,id,name,kindGroup,complexity,deps] = rows[i];
  assert.equal(b, `B${String(i+1).padStart(2,'0')}`);
  assert.equal(id, order[i]);
  const u = byId.get(id);
  assert.equal(name, u.name);
  assert.equal(kindGroup.trim(), `${u.kind} / ${u.group}`);
  assert.equal(complexity, u.complexity);
  const declared = deps.trim() === 'None' ? [] : deps.trim().split(', ');
  assert.deepEqual(declared, dag.units.find(x => x.name === name).depends_on.map(n => byName.get(n).id));
  assert.match(plan, new RegExp(`^### ${b} — ${id} `, 'm'));
}
const map = read('../units-generation/unit-of-work-story-map.md');
assert.deepEqual([...map.matchAll(/^\| (FR\d+(?:\.\d+)?) \|/gm)].map(m => m[1]), ids);
const nfrIds = [...map.matchAll(/^\| (NFR\d+) —/gm)].map(m => m[1]);
assert.deepEqual(nfrIds, Array.from({length:10}, (_,i) => `NFR${i+1}`));
const ibIds = [...map.matchAll(/^\| (IB-\d\d) —/gm)].map(m => m[1]);
assert.deepEqual(ibIds, Array.from({length:9}, (_,i) => `IB-${String(i+1).padStart(2,'0')}`));
const external = read('external-dependency-map.md');
assert.deepEqual([...external.matchAll(/^\| (EXT-\d\d) \|/gm)].map(m=>m[1]),
  Array.from({length:15}, (_,i)=>`EXT-${String(i+1).padStart(2,'0')}`));
const allocation = read('team-allocation.md');
assert.deepEqual([...allocation.matchAll(/^\| (B\d\d) \/ (U\d+) —/gm)].map(m=>m[2]), order);
const componentSection = allocation.split('## Component accountability through the increments\n')[1].split('\n## ')[0];
assert.deepEqual([...componentSection.matchAll(/^\| ([A-Z][A-Za-z]+) \|/gm)].map(m=>m[1]), components.map(c=>c.name));
const review = read('../contract-design/reviews/review-01.md');
const contractFindings = [...review.matchAll(/^\| (R-\d\d) \| Major \|/gm)].map(m=>m[1]);
assert.deepEqual(contractFindings, ['R-01','R-02','R-03']);
assert.match(review, /\*\*Verdict:\*\* NOT-READY/);
const definitions = plan.split(/^### B\d\d — U\d+ .+$/m).slice(1);
assert.equal(definitions.length, 8);
for (const definition of definitions) for (const field of ['Owner','Prerequisites','Definition of done','Confidence hypothesis','Expected demo']) {
  assert.ok(definition.includes(`**${field}:**`), `Missing Bolt field: ${field}`);
}

const data = {checks:'passed', boltedUnits:8, order, dependencyEdges:edgeCount,
  components:components.length, entities:components.reduce((n,c)=>n+c.entities.length,0),
  functionalIds:ids.length, traceabilityRows:traces.reduce((n,t)=>n+t.coverage.length,0),
  unresolvedTraceabilityFindings:0, nfrRows:nfrIds.length, evidenceBacklogRows:ibIds.length,
  externalDependencies:15, acceptedContractFindingsStillOpen:contractFindings.length};
if (process.argv.includes('--trace-data')) {
  console.log(JSON.stringify({...data, rows:ids.map((id,i)=>({id,domain:traces[0].coverage[i].target,unit:traces[1].coverage[i].target}))}));
} else {
  const phase = read('../../verification/phase-check-inception.md');
  assert.match(phase, /^\*\*Verdict: PASS — planning traceability only\.\*\*/m);
  const consolidated = [...phase.matchAll(/^\| (FR\d+(?:\.\d+)?) \| ([^|]+) \| (U\d+) \| OK \|/gm)];
  assert.equal(consolidated.length, ids.length);
  for (let i=0; i<ids.length; i++) {
    assert.equal(consolidated[i][1], ids[i]);
    assert.equal(consolidated[i][2].trim(), traces[0].coverage[i].target);
    assert.equal(consolidated[i][3], traces[1].coverage[i].target);
  }
  const files = ['bolt-plan.md','team-allocation.md','risk-and-sequencing-rationale.md',
    'external-dependency-map.md','delivery-planning-questions.md','verification.md','../../verification/phase-check-inception.md'];
  let links = 0;
  const slug = s => s.toLowerCase().replace(/[^\p{L}\p{N}_\- ]/gu,'').replace(/ /g,'-');
  const headings = s => new Set([...s.matchAll(/^#{1,6} (.+)$/gm)].map(m=>slug(m[1])));
  for (const file of files) {
    const text = read(file);
    assert.ok(!text.includes('\uFFFD'), `Replacement character in ${file}`);
    assert.ok(!text.includes('\r'), `Unexpected CR in ${file}`);
    for (const [,raw] of text.matchAll(/\[[^\]\n]+\]\(([^)\n]+)\)/g)) {
      if (/^https?:/.test(raw)) continue;
      const [path, fragment] = raw.split('#');
      const target = path ? resolve(here, dirname(file), path) : resolve(here,file);
      assert.ok(existsSync(target), `${file}: missing ${raw}`);
      if (fragment) assert.ok(headings(readFileSync(target,'utf8')).has(fragment), `${file}: missing anchor ${raw}`);
      links++;
    }
  }
  const {JSDOM} = await import(pathToFileURL(resolve(root,'frontend/node_modules/jsdom/lib/api.js')).href);
  const window = new JSDOM('').window;
  globalThis.window = window; globalThis.document = window.document;
  assert.ok(process.argv[2], 'Supply installed Mermaid module path');
  const {default:mermaid} = await import(pathToFileURL(resolve(process.argv[2])).href);
  mermaid.initialize({startOnLoad:false});
  const parsed = await mermaid.parse(block(plan,'mermaid'));
  console.log(JSON.stringify({...data, localLinks:links, mermaid:parsed.diagramType},null,2));
}
