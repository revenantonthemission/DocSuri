#!/usr/bin/env python3
"""Validate inline contract artifacts; no application or external effects."""
import json, re, sys
from pathlib import Path
import yaml
from jsonschema import Draft202012Validator, FormatChecker
from openapi_spec_validator import validate as validate_openapi

root=Path(__file__).resolve().parent
if len(sys.argv)>1: root=Path(sys.argv[1]).resolve()
doc=root/'contract-summary.md'
source=doc.read_text()
assert '\ufffd' not in source
assert not any(x.rstrip()!=x for x in source.splitlines()), 'trailing whitespace'
blocks=[(kind,yaml.safe_load(body)) for kind,body in re.findall(r'```yaml ([^\n]+)\n(.*?)\n```',source,re.S)]
registries=[b for kind,b in blocks if kind=='shared-schema' and '$defs' in b]
assert len(registries)==1
registry=registries[0]
defs=registry['$defs']
Draft202012Validator.check_schema(registry)
for name,schema in defs.items():
 Draft202012Validator.check_schema(schema)

def walk_refs(node):
 if isinstance(node,dict):
  if '$ref' in node: yield node['$ref']
  for child in node.values(): yield from walk_refs(child)
 elif isinstance(node,list):
  for child in node: yield from walk_refs(child)
refs=list(walk_refs(registry))
for ref in refs:
 assert ref.startswith('#/$defs/'),ref
 assert ref[len('#/$defs/'):] in defs, ref

contracts=[b for kind,b in blocks if kind=='contract']
ids={b['id'] for b in contracts}
assert ids=={'C%02d'%i for i in range(1,15) if i!=13}, ids
assert len(ids)==len(contracts)
ops={}
for c in contracts:
 assert c['owner'] and c['providers'] and c['consumers'] and c['invariants'] and c['checks']
 for op in c['operations']:
  key=c['id']+'.'+op['name']
  assert key not in ops,key
  ops[key]=op
  assert op['input'] in defs and op['output'] in defs,key
  assert op['auth'] and op['semantics'] and op['errors'],key
  assert set(op['errors'])<=set(defs['Error']['properties']['code']['enum']),key

requirements=(root.parent/'requirements-analysis/requirements.md').read_text()
frs=re.findall(r'^### (FR\d+)\s|^- \*\*(FR\d+\.\d+):',requirements,re.M)
frs=[a or b for a,b in frs]
maps=[b for kind,b in blocks if kind=='traceability']
assert len(maps)==1
mapping=maps[0]
assert list(mapping['requirements'])==frs, 'FR enumeration/order differs'
for fr,targets in mapping['requirements'].items():
 assert targets and set(targets)<=ids|{'C13'},fr
claimed={fr for c in contracts for fr in c['requirements']}
assert claimed<=set(frs),claimed-set(frs)
assert all(any(fr in c['requirements'] for c in contracts) for fr in frs),'unowned requirement'

dag_doc=(root.parent/'units-generation/unit-of-work-dependency.md').read_text()
dag=yaml.safe_load(re.search(r'```yaml\n(.*?)\n```',dag_doc,re.S).group(1))['units']
names={u['name']:'U'+str(i+1) for i,u in enumerate(dag)}
edges={(names[u['name']],names[p]) for u in dag for p in u['depends_on']}
edge_map={(x['consumer'],x['provider']):x['contracts'] for x in mapping['edges']}
assert len(edge_map)==len(mapping['edges'])==19
assert set(edge_map)==edges
for e,contract_ids in edge_map.items():
 assert contract_ids and set(contract_ids)<=ids|{'C13'},e

apis=[b for kind,b in blocks if kind=='openapi']
assert len(apis)==2,'browser and controlled evidence HTTP specs required'
api_ops=[]
bound_ops=set()
for api in apis:
 validate_openapi(api)
 def rebase(node):
  if isinstance(node,dict):return {k:(v.replace('#/$defs/','#/components/schemas/') if k=='$ref' else rebase(v)) for k,v in node.items()}
  if isinstance(node,list):return [rebase(x) for x in node]
  return node
 for name,schema in api['components']['schemas'].items():
  assert name in defs and schema==rebase(defs[name]),'divergent schema '+name
 for reference in walk_refs(api):
  assert reference.startswith('#/components/'),reference
  target=api
  for part in reference[2:].split('/'):
   assert part in target,reference
   target=target[part]
 for path,item in api['paths'].items():
  for method,operation in item.items():
   if method not in ('get','post','put','patch','delete'): continue
   assert operation['operationId'] not in api_ops
   api_ops.append(operation['operationId'])
   if method=='get': assert 'requestBody' not in operation
   if api['info']['title'].startswith('DocSuri application'):
    if 'x-contract-operation' in operation:
     key=operation['x-contract-operation']
     assert key in ops
     assert key not in bound_ops,key
     bound_ops.add(key)
     assert ops[key].get('surface') in ('browser','admin'),key
     body_ref=operation['requestBody']['content']['application/json']['schema']['$ref']
     body=defs[body_ref.split('/')[-1]]
     assert 'context' not in body.get('properties',{})
     assert body.get('additionalProperties') is False, key
    assert 'default' in operation['responses']

assert bound_ops=={k for k,v in ops.items() if v.get('surface') in ('browser','admin')},'missing browser/admin binding'

cases=[b for kind,b in blocks if kind=='schema-cases']
assert len(cases)==1
valid=invalid=0
for case in cases[0]['cases']:
 assert case['schema'] in defs
 validator=Draft202012Validator({'$ref':'#/$defs/'+case['schema'],'$defs':defs},format_checker=FormatChecker())
 errors=list(validator.iter_errors(case['instance']))
 assert bool(errors) != case['valid'], (case['name'],[e.message for e in errors])
 if case['valid']: valid+=1
 else: invalid+=1
assert valid and invalid
for link in re.findall(r'\]\(([^)]+)\)',source):
 if '://' in link or link.startswith('#'): continue
 assert (root/link.split('#')[0]).exists(),link

print(json.dumps({'contracts':len(contracts)+1,'schemaDefinitions':len(defs),'schemaReferences':len(refs),'typedOperations':len(ops),'httpOperations':len(api_ops),'unitEdges':len(edges),'functionalRequirements':len(frs),'positiveSchemaCases':valid,'negativeSchemaCases':invalid,'openapiDocuments':len(apis),'result':'PASS'},indent=2))
