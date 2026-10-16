"""Read-only schema reproduction; no network, service calls or file writes."""

from copy import deepcopy
import json
from pathlib import Path
import subprocess

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


ROOT = Path(__file__).resolve().parents[7]
workspace = json.loads((ROOT / "shared/dtos/workspace.schema.json").read_text())
execution = json.loads(subprocess.check_output(
    ["git", "show", "45413571:shared/events/execution.schema.json"], cwd=ROOT, text=True
))
registry = Registry().with_resources([
    (document["$id"], Resource.from_contents(document))
    for document in (workspace, execution)
])
artifact = {
    "artifact": {"artifactId": "fixture-artifact", "revision": "1", "contentHash": "a" * 64},
    "ownerId": "fixture-owner", "contextId": "fixture-context",
    "operationId": "fixture-operation", "kind": "research-answer",
    "output": {
        "summary": "Synthetic abstention", "evidence": [], "coverage": "abstained",
        "limitations": ["Synthetic schema fixture only"], "methodRevision": "1",
    },
    "currentEligibilityRevision": "1", "mediaType": "application/json",
    "policy": {"policyId": "synthetic-local", "revision": "1"},
}
artifact_ref = {"$ref": workspace["$id"] + "#/$defs/ResearchArtifact"}
Draft202012Validator(artifact_ref, registry=registry).validate(artifact)
prepared = execution["$defs"]["DispatchFact"]["properties"]["prepared"]
assert not Draft202012Validator(prepared, registry=registry).is_valid(artifact)
assert Draft202012Validator(prepared, registry=registry).is_valid(None)

# Demonstrate only the proposed owner/type boundary in an in-memory schema.
# Runtime authority, reference equality and state transitions still require real
# mounted checks; this small diagnostic cannot prove those guarantees.
candidate = {
    "type": "object",
    "properties": {
        "ownerComponent": {"type": "string"},
        "prepared": {"anyOf": [*deepcopy(prepared["anyOf"]), artifact_ref]},
    },
    "required": ["ownerComponent", "prepared"],
    "allOf": [{
        "if": {"properties": {"ownerComponent": {"const": "ResearchWorkspace"}}},
        "then": {"properties": {"prepared": {"anyOf": [artifact_ref, {"type": "null"}]}}},
        "else": {"properties": {"prepared": prepared}},
    }],
}
validator = Draft202012Validator(candidate, registry=registry)
assert validator.is_valid({"ownerComponent": "ResearchWorkspace", "prepared": artifact})
assert not validator.is_valid({"ownerComponent": "PaperAssistance", "prepared": artifact})
assert not validator.is_valid({"ownerComponent": "Unregistered", "prepared": artifact})
assert validator.is_valid({"ownerComponent": "ResearchWorkspace", "prepared": None})
print("7 historical schema checks passed: commit 45413571 rejects a valid research artifact; corrected owner boundary accepts only research owner")
