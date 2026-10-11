"""Read-only consistency checks for the U1 functional design (requires PyYAML).
Run: python validate_design.py. This does not verify the runnable application.
"""
from pathlib import Path
import json
import re
import sys
import yaml

HERE = Path(__file__).resolve().parent
RECORD = HERE.parents[2]
UNIT = "u1-integrated-paper-journey"
errors = []

def check(condition, message):
    if not condition:
        errors.append(message)

def model(name):
    text = (HERE / name).read_text()
    blocks = re.findall(r"```yaml\n(.*?)\n```", text, re.S)
    check(len(blocks) == 1, name + ": exactly one authoritative YAML block")
    return yaml.safe_load(blocks[0])

entities = model("entities.md")
rules_doc = model("rules.md")
rules = rules_doc["rules"]
entity_names = {e["name"] for e in entities["entities"]}
rule_names = {r["id"] for r in rules}
check(len(entity_names) == len(entities["entities"]), "duplicate entity")
check(len(rule_names) == len(rules), "duplicate rule")

domain = (RECORD / "inception/domain-design/components.md").read_text()
owners = {}
for row in domain.splitlines():
    if row.startswith("| "):
        cells = [x.strip() for x in row.strip("|").split("|")]
        if len(cells) == 5 and cells[0] in entity_names:
            owners[cells[0]] = cells[1]
for entity in entities["entities"]:
    name = entity["name"]
    check(owners.get(name) == entity["owner"], name + ": upstream ownership differs")
    for field in ("description", "attributes", "constraints", "relationships"):
        check(field in entity, name + ": missing " + field)
    seen = set()
    for attr in entity["attributes"]:
        check(attr["name"] not in seen, name + ": duplicate attribute " + attr["name"])
        seen.add(attr["name"])
        for field in ("name", "type", "required", "unique", "constraints"):
            check(field in attr, name + ": attribute lacks " + field)
        if "references" in attr:
            check(attr["references"] in entity_names, name + ": unknown entity reference")
    for rel in entity["relationships"]:
        check(rel["target"] in entity_names, name + ": unknown relationship")
        check(all(k in rel for k in ("cardinality", "direction", "description")),
              name + ": incomplete relationship")

requirements = (RECORD / "inception/requirements-analysis/requirements.md").read_text()
known_requirements = set(re.findall(r"\b(?:FR\d+(?:\.\d+)?|NFR\d+)\b", requirements))
for rule in rules:
    check(re.fullmatch(r"BR\d+\.\d+", rule["id"]), "invalid rule ID")
    for field in ("statement", "category", "applies_to", "trigger", "logic", "violation", "source"):
        check(field in rule, rule["id"] + ": missing " + field)
    check(rule["category"] in {"validation", "authorization", "constraint", "calculation", "policy"},
          rule["id"] + ": invalid category")
    for source in re.findall(r"\b(?:FR\d+(?:\.\d+)?|NFR\d+)\b", str(rule.get("source", ""))):
        check(source in known_requirements, rule["id"] + ": unknown requirement " + source)

trace = json.loads((HERE / "traceability.json").read_text())
check(trace["stage"] == "functional-design" and trace["unit"] == UNIT, "trace identity")
assignment = (RECORD / "inception/units-generation/unit-of-work-story-map.md").read_text()
assigned = []
for row in assignment.splitlines():
    if row.startswith("| FR") and UNIT in row:
        assigned.append(row.split("|")[1].strip())
all_ids = [row.split("|")[1].strip() for row in assignment.splitlines() if re.match(r"\| FR\d", row)]
check(trace["upstream_ids"] == all_ids, "trace does not match release requirement order")
check(len(trace["coverage"]) == len(all_ids), "coverage row count")
check([r["id"] for r in trace["coverage"] if r["status"] == "OK"] == assigned, "U1 assignment differs")
check({r["id"] for r in trace["coverage"]} == set(all_ids), "coverage set")
used = set()
spec = (HERE / "functional-spec.md").read_text()
wfs = set(re.findall(r"^### (WF\d+) ", spec, re.M))
checks = set(re.findall(r"^\| (LC\d+) ", spec, re.M))
for row in trace["coverage"]:
    if row["status"] == "N/A":
        check(row["id"] not in assigned and row["kind"] == "outside-U1-assignment", "incorrect scope exclusion")
        check(bool(row["target"]), row["id"] + ": missing downstream owner")
        continue
    ids = set(re.findall(r"BR\d+\.\d+", row["target"]))
    check(row["status"] == "OK" and bool(ids), row["id"] + ": invalid target")
    check(ids <= rule_names, row["id"] + ": undefined rule target")
    used |= ids
    if row["kind"] == "inline-acceptance":
        line = next(l for l in requirements.splitlines() if l.startswith("- **" + row["id"] + ":**"))
        check(row["acceptance_text"] == line.split("Acceptance: ", 1)[1], row["id"] + ": acceptance text drift")
        check(set(row["workflows"]) <= wfs, row["id"] + ": missing workflow")
        check(set(row["local_checks"]) <= checks, row["id"] + ": missing check")
        check(bool(row["remaining_full_parity"]), row["id"] + ": lost remainder")
explained = {r["id"] for r in trace.get("reverse", [])}
check(rule_names <= used | explained, "unexplained business rules: " + str(rule_names - used - explained))
check({r["id"] for r in trace["non_functional_obligations"]} == {f"NFR{i}" for i in range(1, 11)}, "NFR coverage")
check({r["id"] for r in trace["evidence_obligations"]} == {f"IB-{i:02}" for i in range(1, 10)}, "IB coverage")
for row in trace["non_functional_obligations"] + trace["evidence_obligations"]:
    check(set(row["local_checks"]) <= checks, row["id"] + ": missing local check")
    for pre in row["prerequisites"]:
        check("| " + pre + " " in spec, row["id"] + ": missing prerequisite")

paths = ["entities.md", "rules.md", "functional-spec.md", "frontend-components.md", "contract-revision-plan.md"]
links = 0
for name in paths:
    text = (HERE / name).read_text()
    check("\ufffd" not in text and "\x00" not in text, name + ": damaged character")
    check(sum(1 for line in text.splitlines() if line.startswith("```")) % 2 == 0, name + ": unclosed fence")
    for target in re.findall(r"\]\(([^)]+)\)", text):
        if "://" in target or target.startswith("#"):
            continue
        target = target.split("#")[0]
        check((HERE / target).is_file(), name + ": broken link " + target)
        links += 1
    references = set(re.findall(r"\bBR\d+\.\d+\b", text))
    check(references <= rule_names, name + ": undefined BR IDs")
diagram = re.search(r"```mermaid\n(.*?)\n```", spec, re.S).group(1)
for a, b in re.findall(r"^\s*(\w+)\s+[|}o{]+--[|}o{]+\s+(\w+)\s*:", diagram, re.M):
    check(a in entity_names and b in entity_names, "diagram entity mismatch")
if errors:
    print("\n".join(errors))
    sys.exit(1)
print(json.dumps({"result": "PASS", "entities": len(entity_names), "rules": len(rule_names),
                  "U1_FR_rows": len(assigned), "release_FR_rows": len(all_ids), "inline_acceptance_rows": sum(r["kind"] == "inline-acceptance" for r in trace["coverage"]),
                  "workflows": len(wfs), "local_checks": len(checks), "NFR": 10, "IB": 9, "local_links": links}))

