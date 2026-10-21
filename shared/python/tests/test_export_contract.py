"""C09 2.1.0 adds U6's export amendments without breaking any frozen C09 shape."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from copy import deepcopy
from pathlib import Path

import pytest
import yaml
from conftest import SHARED_ROOT, all_schema_paths, load_schema
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from pydantic import ValidationError as ModelValidationError
from referencing import Registry, Resource

from docsuri_shared.workspace import execution, wire

PUBLIC_ID = "https://docsuri.dev/shared/dtos/workspace.schema.json"
INTERNAL_ID = "https://docsuri.dev/shared/events/execution.schema.json"
VECTORS = SHARED_ROOT / "export-hash-vectors.json"
BINDING_FIELDS = {
    "ownerId", "previewId", "revision", "source", "sourceEligibilityRevision",
    "connectionRevision", "destination", "renderedContentHash", "renderPolicy",
}
DESTINATION_IDENTITY = {
    "destinationId", "connectionId", "workspaceId", "parentPageId", "formatRevision",
}
BASE_ERRORS = [
    "INVALID_ARGUMENT", "UNAUTHENTICATED", "FORBIDDEN", "NOT_FOUND", "POLICY_UNRESOLVED",
    "DEPENDENCY_UNAVAILABLE",
]
CONNECTION_STATES = ["connected", "disconnected", "revoked", "unavailable"]

# Frozen shapes of the release before the amendment (contract release 3.0.0, C09 2.0.0),
# transcribed from that release's generated schemas: {def: (properties, required)}.
_ID = "ref:Id"
FROZEN_PUBLIC = {
    "ExportConnection": ({
        "connectionId": _ID, "ownerId": _ID, "revision": "ref:Revision",
        "provider": 'const:"notion"', "state": "enum:" + "|".join(CONNECTION_STATES),
        "destinationScopeIds": "array[ref:Id]", "limitations": "array[string]",
    }, {"connectionId", "ownerId", "revision", "provider", "state", "destinationScopeIds",
        "limitations"}),
    "ExportDestination": ({
        "connectionId": _ID, "workspaceId": _ID, "parentPageId": _ID,
        "formatRevision": "ref:Revision",
    }, {"connectionId", "workspaceId", "parentPageId", "formatRevision"}),
    "ExportDestinations": ({
        "connectionId": _ID, "connectionRevision": "ref:Revision",
        "destinations": "array[ref:ExportDestination]",
    }, {"connectionId", "connectionRevision", "destinations"}),
    "ExportPreview": ({
        "previewId": _ID, "ownerId": _ID, "revision": "ref:Revision",
        "source": "ref:ResearchArtifactRef", "sourceEligibilityRevision": "ref:Revision",
        "connectionRevision": "ref:Revision", "destination": "ref:ExportDestination",
        "renderedText": "string", "renderedContentHash": "ref:Hash", "bindingHash": "ref:Hash",
        "renderPolicy": "ref:PolicyRef",
    }, {"previewId", "ownerId", "revision", "source", "sourceEligibilityRevision",
        "connectionRevision", "destination", "renderedText", "renderedContentHash", "bindingHash",
        "renderPolicy"}),
    "ExportApproval": ({
        "approvalId": _ID, "ownerId": _ID, "previewId": _ID, "previewRevision": "ref:Revision",
        "bindingHash": "ref:Hash", "approvedAt": "ref:Time", "expiresAt": "anyOf(ref:Time,null)",
        "state": "enum:approved|invalidated|consumed|cancelled|expired", "policy": "ref:PolicyRef",
    }, {"approvalId", "ownerId", "previewId", "previewRevision", "bindingHash", "approvedAt",
        "expiresAt", "state", "policy"}),
    "ExportEffect": ({
        "effectId": _ID, "approvalId": _ID, "ownerId": _ID, "revision": "ref:Revision",
        "bindingHash": "ref:Hash",
        "state": "enum:accepted|executing|succeeded|failed|unknown|cancelled|invalidated",
        "remoteReference": "anyOf(ref:Id,null)", "remoteUrl": "anyOf(string,null)",
        "reconciliationEvidenceHash": "anyOf(ref:Hash,null)", "limitations": "array[string]",
    }, {"effectId", "approvalId", "ownerId", "revision", "bindingHash", "state",
        "remoteReference", "remoteUrl", "reconciliationEvidenceHash", "limitations"}),
    "ExportConnectionConfigureHttp": ({
        "token": "string", "expectedRevision": "anyOf(ref:Revision,null)",
        "credentialPolicy": "ref:PolicyRef",
    }, {"token", "expectedRevision", "credentialPolicy"}),
    "ExportConnectionReadHttp": ({"connectionId": _ID}, {"connectionId"}),
    "ExportPreviewRequestHttp": ({
        "source": "ref:ResearchArtifactRef", "destination": "ref:ExportDestination",
        "renderPolicy": "ref:PolicyRef",
    }, {"source", "destination", "renderPolicy"}),
    "ExportApprovalRequestHttp": ({
        "previewId": _ID, "previewRevision": "ref:Revision", "bindingHash": "ref:Hash",
        "explicitApproval": "const:true",
    }, {"previewId", "previewRevision", "bindingHash", "explicitApproval"}),
    "ExportExecuteHttp": ({"approvalId": _ID, "bindingHash": "ref:Hash"},
                          {"approvalId", "bindingHash"}),
    "ExportEffectReadHttp": ({"effectId": _ID}, {"effectId"}),
    "ExportCancelHttp": ({"approvalId": _ID, "expectedRevision": "ref:Revision"},
                         {"approvalId", "expectedRevision"}),
}
FROZEN_INTERNAL = {
    "ExportConnectionConfigure": ({
        "context": "ref:CommandContext", "token": "string",
        "expectedRevision": "anyOf(ref:Revision,null)", "credentialPolicy": "ref:PolicyRef",
    }, {"context", "token", "expectedRevision", "credentialPolicy"}),
    "ExportConnectionRead": ({"context": "ref:CommandContext", "connectionId": _ID},
                             {"context", "connectionId"}),
    "ExportPreviewRequest": ({
        "context": "ref:CommandContext", "source": "ref:ResearchArtifactRef",
        "destination": "ref:ExportDestination", "renderPolicy": "ref:PolicyRef",
    }, {"context", "source", "destination", "renderPolicy"}),
    "ExportApprovalRequest": ({
        "context": "ref:CommandContext", "previewId": _ID, "previewRevision": "ref:Revision",
        "bindingHash": "ref:Hash", "explicitApproval": "const:true",
    }, {"context", "previewId", "previewRevision", "bindingHash", "explicitApproval"}),
    "ExportExecute": ({"context": "ref:CommandContext", "approvalId": _ID,
                       "bindingHash": "ref:Hash"}, {"context", "approvalId", "bindingHash"}),
    "ExportEffectRead": ({"context": "ref:CommandContext", "effectId": _ID},
                         {"context", "effectId"}),
    "ExportCancel": ({"context": "ref:CommandContext", "approvalId": _ID,
                      "expectedRevision": "ref:Revision"},
                     {"context", "approvalId", "expectedRevision"}),
    "ProviderNotionRequest": ({
        "effectId": _ID, "approvalId": _ID, "connectionId": _ID, "destinationId": _ID,
        "artifact": "ref:ResultRef", "previewHash": "ref:Hash",
    }, {"effectId", "approvalId", "connectionId", "destinationId", "artifact", "previewHash"}),
    "ProviderNotionResult": ({
        "effectId": _ID, "remotePageId": "anyOf(ref:Id,null)",
        "disposition": "enum:committed|rejected|unknown",
    }, {"effectId", "remotePageId", "disposition"}),
    "ProviderNotionInspect": ({"connectionId": _ID, "connectionRevision": "ref:Revision",
                               "page": "ref:PageRequest"},
                              {"connectionId", "connectionRevision", "page"}),
    "ProviderNotionInspection": ({
        "connectionId": _ID, "connectionRevision": "ref:Revision", "valid": "boolean",
        "destinations": "array[object]", "page": "ref:PageInfo", "observedAt": "ref:Time",
    }, {"connectionId", "connectionRevision", "valid", "destinations", "page", "observedAt"}),
    "ProviderEffectReconcile": ({
        "effectId": _ID, "providerId": _ID, "credentialRef": _ID, "requestHash": "ref:Hash",
        "remoteReference": "anyOf(ref:Id,null)",
    }, {"effectId", "providerId", "credentialRef", "requestHash", "remoteReference"}),
    "ProviderEffectEvidence": ({
        "effectId": _ID, "disposition": "enum:committed|definitely_not_committed|unknown",
        "remoteReference": "anyOf(ref:Id,null)", "evidenceHash": "anyOf(ref:Hash,null)",
        "observedAt": "ref:Time",
    }, {"effectId", "disposition", "remoteReference", "evidenceHash", "observedAt"}),
}
FROZEN_INSPECTION_ITEM = ({"destinationId": _ID, "title": "string",
                           "revision": "ref:Revision", "writable": "boolean"},
                          {"destinationId", "title", "revision", "writable"})
# The only two permitted deviations from a frozen property (Step 3).
SHAPE_EXCEPTIONS = {
    ("ExportDestinations", "destinations"): "array[ref:ExportDestinationEntry]",
    ("ExportPreview", "destination"): "ref:ExportDestinationEntry",
}
OPTIONAL_EXCEPTIONS = {("ExportConnectionReadHttp", "connectionId"),
                       ("ExportConnectionRead", "connectionId")}
FROZEN_ERRORS = {
    "configureNotionConnection": BASE_ERRORS
    + ["INVALID_TOKEN", "CONFLICT", "IDEMPOTENCY_CONFLICT"],
    "readNotionConnection": BASE_ERRORS,
    "disconnectNotion": BASE_ERRORS + ["CONFLICT", "OUTCOME_UNKNOWN"],
    "listExportDestinations": BASE_ERRORS,
    "prepareExportPreview": BASE_ERRORS + ["SOURCE_INELIGIBLE", "CONFLICT"],
    "approveExportPreview": BASE_ERRORS + ["CONFLICT", "SOURCE_INELIGIBLE", "IDEMPOTENCY_CONFLICT"],
    "executeApprovedExport": BASE_ERRORS + ["CONFLICT", "SOURCE_INELIGIBLE", "APPROVAL_REQUIRED",
                                            "OUTCOME_UNKNOWN", "CAPACITY_EXHAUSTED"],
    "readExportEffect": BASE_ERRORS,
    "cancelExportApproval": BASE_ERRORS + ["CONFLICT", "OUTCOME_UNKNOWN"],
    "reconcileExportEffect": BASE_ERRORS + ["OUTCOME_UNKNOWN"],
}


def shape(node: dict) -> str:
    """Name-and-type signature of one property schema; annotations and bounds are ignored."""
    if "$ref" in node:
        return "ref:" + node["$ref"].split("/")[-1]
    if "anyOf" in node:
        return "anyOf(" + ",".join(shape(item) for item in node["anyOf"]) + ")"
    if "const" in node:
        return "const:" + json.dumps(node["const"])
    if "enum" in node:
        return "enum:" + "|".join(node["enum"])
    kind = node.get("type")
    if kind == "array":
        return f"array[{shape(node['items'])}]"
    return "|".join(kind) if isinstance(kind, list) else kind


def defs(document_id: str) -> dict:
    public = document_id == PUBLIC_ID
    name = "dtos/workspace.schema.json" if public else "events/execution.schema.json"
    return load_schema(name)["$defs"]


def canonical_blocks() -> list[tuple[str, dict]]:
    spec = importlib.util.spec_from_file_location(
        "export_workspace_contract",
        Path(__file__).resolve().parents[1] / "tools/export_workspace_contract.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = module.SOURCE.read_text()
    return [(kind, yaml.safe_load(body))
            for kind, body in re.findall(r"```yaml ([^\n]+)\n(.*?)\n```", source, re.S)]


@pytest.fixture(scope="module")
def registry() -> Registry:
    resources = []
    for path in all_schema_paths():
        document = load_schema(str(path.relative_to(path.parents[1])))
        resources.append((document["$id"], Resource.from_contents(document)))
    return Registry().with_resources(resources)


def validator(registry: Registry, document_id: str, name: str) -> Draft202012Validator:
    return Draft202012Validator({"$ref": f"{document_id}#/$defs/{name}"}, registry=registry)


@pytest.mark.parametrize(
    ("document_id", "frozen"), [(PUBLIC_ID, FROZEN_PUBLIC), (INTERNAL_ID, FROZEN_INTERNAL)]
)
def test_frozen_properties_keep_name_type_and_requiredness_with_two_named_exceptions(
    document_id, frozen
):
    current = defs(document_id)
    deviations = set()
    for name, (properties, required) in frozen.items():
        assert name in current, f"frozen def {name} left its schema document"
        actual = current[name]
        for prop, signature in properties.items():
            assert prop in actual["properties"], f"{name}.{prop} was removed"
            if shape(actual["properties"][prop]) != signature:
                deviations.add(("shape", name, prop))
                assert shape(actual["properties"][prop]) == SHAPE_EXCEPTIONS[(name, prop)]
            if (prop in required) != (prop in actual.get("required", [])):
                deviations.add(("optional", name, prop))
                assert (name, prop) in OPTIONAL_EXCEPTIONS
    expected = {("shape", *key) for key in SHAPE_EXCEPTIONS if key[0] in frozen}
    expected |= {("optional", *key) for key in OPTIONAL_EXCEPTIONS if key[0] in frozen}
    assert deviations == expected


def test_destination_entry_is_the_frozen_destination_plus_required_identity_and_title():
    entry = defs(PUBLIC_ID)["ExportDestinationEntry"]
    properties, required = FROZEN_PUBLIC["ExportDestination"]
    for prop, signature in properties.items():
        assert shape(entry["properties"][prop]) == signature
    assert set(entry["required"]) == required | {"destinationId", "title"}
    assert shape(entry["properties"]["destinationId"]) == "ref:Id"
    assert shape(entry["properties"]["title"]) == "string"
    assert entry["additionalProperties"] is False


def test_inspection_destination_items_keep_their_frozen_fields():
    item = defs(INTERNAL_ID)["ProviderNotionInspection"]["properties"]["destinations"]["items"]
    properties, required = FROZEN_INSPECTION_ITEM
    assert {prop: shape(item["properties"][prop]) for prop in properties} == properties
    assert set(item["required"]) == required
    assert {"readable", "creationCapability"} <= set(item["properties"]) - required


@pytest.mark.parametrize(
    ("document_id", "frozen"), [(PUBLIC_ID, FROZEN_PUBLIC), (INTERNAL_ID, FROZEN_INTERNAL)]
)
def test_added_properties_on_frozen_defs_are_optional(document_id, frozen):
    current = defs(document_id)
    for name, (properties, _) in frozen.items():
        added = set(current[name]["properties"]) - set(properties)
        assert not added & set(current[name].get("required", [])), name
    entry = defs(PUBLIC_ID)["ExportDestinationEntry"]
    added = set(entry["properties"]) - set(FROZEN_PUBLIC["ExportDestination"][0])
    assert added & set(entry["required"]) == {"destinationId", "title"}


def test_connection_states_stay_the_frozen_four_and_never_pending():
    state = defs(PUBLIC_ID)["ExportConnection"]["properties"]["state"]
    assert state["enum"] == CONNECTION_STATES
    assert "pending" not in json.dumps(defs(PUBLIC_ID)["ExportConnection"])
    assert [member.value for member in wire.ExportConnection.model_fields["state"].annotation] == (
        CONNECTION_STATES
    )


def test_operations_keep_frozen_errors_and_add_two_browser_operations_with_headers():
    blocks = canonical_blocks()
    c09 = next(body for kind, body in blocks if kind == "contract" and body["id"] == "C09")
    api = next(body for kind, body in blocks
               if kind == "openapi" and body["info"]["title"].startswith("DocSuri application"))
    assert (c09["version"], api["info"]["version"]) == ("2.1.0", "3.1.0")
    operations = {operation["name"]: operation for operation in c09["operations"]}
    for name, errors in FROZEN_ERRORS.items():
        assert operations[name]["errors"] == errors, name
    added = {
        "listExportHistory": ("list-export-history", "ExportHistoryList", "ExportHistoryPage",
                              BASE_ERRORS),
        "settleExportEffect": ("settle-export-effect", "ExportSettle", "ExportEffect",
                               BASE_ERRORS + ["CONFLICT", "IDEMPOTENCY_CONFLICT"]),
    }
    assert set(operations) == set(FROZEN_ERRORS) | set(added)
    for name, (path, request, response, errors) in added.items():
        operation = operations[name]
        assert (operation["input"], operation["output"], operation["surface"]) == (
            request, response, "browser")
        assert operation["errors"] == errors
        post = api["paths"][f"/api/v2/c09/{path}"]["post"]
        headers = {item["name"] for item in post["parameters"]
                   if item["in"] == "header" and item["required"] is True}
        assert headers == {"X-CSRF-Token", "Idempotency-Key"}
        body = post["requestBody"]["content"]["application/json"]["schema"]["$ref"]
        result = post["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
        assert (body.split("/")[-1], result.split("/")[-1]) == (f"{request}Http", response)
        assert "context" in defs(INTERNAL_ID)[request]["required"]
        assert "context" not in defs(PUBLIC_ID)[f"{request}Http"]["properties"]


def test_regenerated_schemas_name_release_3_1_0():
    for name in ("dtos/workspace.schema.json", "events/execution.schema.json"):
        assert load_schema(name)["$comment"].startswith(
            "Generated canonical contract release 3.1.0; source SHA256:"
        )


CONTEXT = {
    "requestId": "request-1",
    "principal": {"kind": "account", "accountId": "account-a", "authorityRevision": "1",
                  "roles": ["user"], "mfa": False},
}
PAGE_URL = "https://www.notion.so/Result-0f6c3a7e2b9d4c1e8a5f6b7c8d9e0a1b"
ENTRY = {
    "connectionId": "connection-a", "workspaceId": "workspace-a",
    "parentPageId": "0f6c3a7e2b9d4c1e8a5f6b7c8d9e0a1b", "formatRevision": "1",
    "destinationId": "0f6c3a7e2b9d4c1e8a5f6b7c8d9e0a1b", "title": "연구 노트",
    "context": "팀 공간 / 연구", "readable": True, "creationCapability": "unknown",
    "writable": True,
}
HISTORY_EFFECT = {
    "effectId": "effect-1", "state": "unknown", "revision": "3",
    "nextCheckAt": "2026-10-20T03:10:00Z", "settledBy": "reconciliation",
    "possibleDuplicates": [{"remoteReference": "page-2", "remoteUrl": PAGE_URL}],
    "settlementOffered": False,
}
HISTORY_ENTRY = {
    "approvalId": "approval-1", "previewId": "preview-a", "previewRevision": "1",
    "bindingHash": "b" * 64, "state": "consumed", "approvedAt": "2026-10-20T03:00:00Z",
    "sourceTitle": "신규성 검토: Attention", "destinationTitle": "연구 노트",
    "continuable": False, "effect": HISTORY_EFFECT,
}
EARLIER = {"effectId": "effect-0", "disposition": "exported", "endedAt": "2026-10-19T01:00:00Z",
           "remoteUrl": PAGE_URL}
SAMPLES = {
    (PUBLIC_ID, "ExportDestinationEntry"): ENTRY,
    (PUBLIC_ID, "ExportDestinations"): {
        "connectionId": "connection-a", "connectionRevision": "1", "destinations": [ENTRY],
        "listingComplete": False, "lastDestinationId": ENTRY["destinationId"],
    },
    (PUBLIC_ID, "ExportConnection"): {
        "connectionId": "connection-a", "ownerId": "account-a", "revision": "1",
        "provider": "notion", "state": "connected", "destinationScopeIds": [],
        "limitations": [], "workspaceName": "DocSuri 합성 작업공간",
    },
    (PUBLIC_ID, "ExportConnectionReadHttp"): {},
    (PUBLIC_ID, "ExportPreview"): {
        "previewId": "preview-a", "ownerId": "account-a", "revision": "1",
        "source": {"artifactId": "artifact-1", "revision": "3", "contentHash": "a" * 64},
        "sourceEligibilityRevision": "7", "connectionRevision": "1", "destination": ENTRY,
        "renderedText": "신규성 검토\ndocsuri-export:preview-a:1", "renderedContentHash": "c" * 64,
        "bindingHash": "b" * 64, "renderPolicy": {"policyId": "u6-render", "revision": "1"},
        "earlierExports": [EARLIER, {"effectId": "effect-00", "disposition": "may-exist",
                                     "endedAt": "2026-10-18T01:00:00Z",
                                     "outcomeReason": "not-found-after-checks"}],
        "marker": "docsuri-export:preview-a:1", "sourceTitle": "신규성 검토: Attention",
    },
    (PUBLIC_ID, "ExportApproval"): {
        "approvalId": "approval-1", "ownerId": "account-a", "previewId": "preview-a",
        "previewRevision": "1", "bindingHash": "b" * 64, "approvedAt": "2026-10-20T03:00:00Z",
        "expiresAt": None, "state": "invalidated",
        "policy": {"policyId": "u6-approval", "revision": "1"},
        "invalidationReason": "connection-changed",
    },
    (PUBLIC_ID, "ExportEffect"): {
        "effectId": "effect-1", "approvalId": "approval-1", "ownerId": "account-a",
        "revision": "4", "bindingHash": "b" * 64, "state": "succeeded",
        "remoteReference": "page-1", "remoteUrl": PAGE_URL, "reconciliationEvidenceHash": None,
        "limitations": [], "outcomeReason": "owner-settled-delivered", "settledBy": "owner",
        "settlementOffered": False,
    },
    (PUBLIC_ID, "ExportEarlierExport"): EARLIER,
    (PUBLIC_ID, "ExportPossibleDuplicate"): {"remoteReference": "page-2"},
    (PUBLIC_ID, "ExportHistoryEffect"): HISTORY_EFFECT,
    (PUBLIC_ID, "ExportHistoryEntry"): {**HISTORY_ENTRY, "endedAt": "2026-10-20T04:00:00Z"},
    (PUBLIC_ID, "ExportHistoryPage"): {"entries": [HISTORY_ENTRY], "nextCursor": "cursor-2"},
    (PUBLIC_ID, "ExportHistoryListHttp"): {"limit": 20, "cursor": None},
    (PUBLIC_ID, "ExportSettleHttp"): {
        "effectId": "effect-1", "expectedRevision": "3", "disposition": "delivered",
        "assumptionAccepted": True, "remoteUrl": PAGE_URL,
    },
    (INTERNAL_ID, "ExportHistoryList"): {"context": CONTEXT, "limit": 1},
    (INTERNAL_ID, "ExportSettle"): {
        "context": CONTEXT, "effectId": "effect-1", "expectedRevision": "3",
        "disposition": "not-delivered", "assumptionAccepted": True,
    },
    (INTERNAL_ID, "ExportConnectionRead"): {"context": CONTEXT},
    (INTERNAL_ID, "ProviderNotionRequest"): {
        "effectId": "effect-1", "approvalId": "approval-1", "connectionId": "connection-a",
        "destinationId": "0f6c3a7e2b9d4c1e8a5f6b7c8d9e0a1b",
        "artifact": {"resultId": "artifact-1", "revision": "3", "contentHash": "a" * 64,
                     "mediaType": "application/json"},
        "previewHash": "b" * 64, "contentHash": "c" * 64, "marker": "docsuri-export:preview-a:1",
    },
    (INTERNAL_ID, "ProviderNotionResult"): {
        "effectId": "effect-1", "remotePageId": None, "disposition": "rejected",
        "providerRequestId": "request-n1", "refusalClass": "workspace-block-limit",
    },
    (INTERNAL_ID, "ProviderNotionInspection"): {
        "connectionId": "connection-a", "connectionRevision": "1", "valid": True,
        "destinations": [{"destinationId": "page-1", "title": "연구 노트", "revision": "1",
                          "writable": False, "readable": True,
                          "creationCapability": "refused"}],
        "page": {"nextCursor": None, "snapshotRevision": "1"},
        "observedAt": "2026-10-20T03:00:00Z", "workspaceName": "DocSuri 합성 작업공간",
        "integrationIdentity": "bot-1",
    },
    (INTERNAL_ID, "ProviderEffectReconcile"): {
        "effectId": "effect-1", "providerId": "notion", "credentialRef": "connection-a",
        "requestHash": "c" * 64, "remoteReference": None, "marker": "docsuri-export:preview-a:1",
        "destinationId": "page-1", "firstAttemptStartedAt": "2026-10-20T03:01:00Z",
        "writerIdentity": "bot-1",
    },
    (INTERNAL_ID, "ProviderEffectEvidence"): {
        "effectId": "effect-1", "disposition": "unknown", "remoteReference": None,
        "evidenceHash": "d" * 64, "observedAt": "2026-10-20T03:30:00Z", "scanComplete": False,
    },
}
ENUMS = {
    "ExportCreationCapability": ["unknown", "confirmed", "refused"],
    "ExportInvalidationReason": ["source-changed", "destination-changed", "connection-changed",
                                 "authority-revoked", "account-withdrawn"],
    "ExportSettledBy": ["provider", "reconciliation", "owner"],
    "ExportSettleDisposition": ["delivered", "not-delivered"],
    "ExportEarlierExportDisposition": ["exported", "may-exist"],
    "ExportApprovalState": ["approved", "invalidated", "consumed", "cancelled", "expired"],
    "ExportEffectState": ["accepted", "executing", "succeeded", "failed", "unknown", "cancelled",
                          "invalidated"],
}
OUTCOME_REASONS = [
    "token-invalid", "no-access", "destination-missing", "content-rejected",
    "workspace-block-limit", "provider-blocked", "rate-limit-budget-spent",
    "not-found-after-checks", "owner-settled-delivered", "owner-settled-not-delivered",
    "dependency-unavailable", "policy-unresolved", "source-changed", "destination-changed",
    "connection-changed", "authority-revoked", "account-withdrawn", "owner-cancelled",
]


def model(document_id: str, name: str):
    return getattr(wire if document_id == PUBLIC_ID else execution, name)


@pytest.mark.parametrize(("document_id", "name"), sorted(SAMPLES))
def test_amended_and_new_defs_validate_and_round_trip_through_generated_models(
    registry, document_id, name
):
    value = SAMPLES[(document_id, name)]
    validator(registry, document_id, name).validate(value)
    decoded = model(document_id, name).model_validate(value)
    encoded = decoded.model_dump(mode="json", by_alias=True, exclude_unset=True)
    assert encoded == value
    validator(registry, document_id, name).validate(encoded)


def test_enumerations_match_their_generated_bindings():
    assert defs(PUBLIC_ID)["ExportOutcomeReason"]["enum"] == OUTCOME_REASONS
    for name, values in {**ENUMS, "ExportOutcomeReason": OUTCOME_REASONS}.items():
        assert defs(PUBLIC_ID)[name]["enum"] == values
        assert [member.value for member in getattr(wire, name)] == values
    refusal = defs(INTERNAL_ID)["ProviderNotionRefusalClass"]["enum"]
    assert set(refusal) <= set(OUTCOME_REASONS)
    assert [member.value for member in execution.ProviderNotionRefusalClass] == refusal


MUTATIONS = [
    ("extra-field", (PUBLIC_ID, "ExportHistoryEntry"), lambda v: v.update(privateNote="x")),
    ("extra-field", (PUBLIC_ID, "ExportDestinationEntry"), lambda v: v.update(token="secret")),
    ("unknown-enum", (PUBLIC_ID, "ExportSettleHttp"), lambda v: v.update(disposition="maybe")),
    ("unknown-enum", (PUBLIC_ID, "ExportEffect"), lambda v: v.update(outcomeReason="other")),
    ("unknown-enum", (PUBLIC_ID, "ExportConnection"), lambda v: v.update(state="pending")),
    ("missing-required", (PUBLIC_ID, "ExportDestinationEntry"), lambda v: v.pop("title")),
    ("missing-required", (PUBLIC_ID, "ExportHistoryEffect"),
     lambda v: v.pop("settlementOffered")),
    ("missing-required", (INTERNAL_ID, "ExportSettle"), lambda v: v.pop("context")),
    ("bound", (PUBLIC_ID, "ExportHistoryListHttp"), lambda v: v.update(limit=21)),
    ("const", (PUBLIC_ID, "ExportSettleHttp"), lambda v: v.update(assumptionAccepted=False)),
]


@pytest.mark.parametrize(("kind", "target", "mutate"), MUTATIONS,
                         ids=[f"{kind}-{target[1]}" for kind, target, _ in MUTATIONS])
def test_negative_mutations_are_rejected_by_schema_and_model(registry, kind, target, mutate):
    value = deepcopy(SAMPLES[target])
    mutate(value)
    with pytest.raises(ValidationError):
        validator(registry, *target).validate(value)
    with pytest.raises(ModelValidationError):
        model(*target).model_validate(value)


def jcs(value) -> str:
    """RFC 8785 for the JSON forms the vectors use: objects, arrays, strings, integers,
    booleans and null. Keys sort by UTF-16 code units; strings use ECMAScript escaping."""
    if isinstance(value, dict):
        items = sorted(value.items(), key=lambda item: item[0].encode("utf-16-be"))
        return "{" + ",".join(f"{jcs(key)}:{jcs(item)}" for key, item in items) + "}"
    if isinstance(value, list):
        return "[" + ",".join(jcs(item) for item in value) + "]"
    if isinstance(value, bool) or value is None:
        return json.dumps(value)
    if isinstance(value, int) and abs(value) <= 2**53:
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    raise TypeError(f"no canonical form in these vectors for {type(value).__name__}")


def test_golden_vectors_recompute_from_the_canonical_hash_rules(registry):
    vectors = json.loads(VECTORS.read_text(encoding="utf-8"))
    rendered = vectors["renderedContentHash"]["cases"]
    binding = vectors["bindingHash"]
    assert rendered and binding["cases"]
    for case in rendered:
        assert set(case["input"]) == {"properties", "children"}, case["name"]
        body = json.dumps(case["input"], sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False).encode()
        assert body.hex() == case["canonicalHex"], case["name"]
        assert hashlib.sha256(body).hexdigest() == case["sha256"], case["name"]
    assert binding["prefix"] == "docsuri:export-binding:v1\n"
    for case in binding["cases"]:
        value = case["input"]
        assert set(value) == BINDING_FIELDS, case["name"]
        assert set(value["destination"]) == DESTINATION_IDENTITY, case["name"]
        for field, name in (("source", "ResearchArtifactRef"), ("renderPolicy", "PolicyRef"),
                            ("renderedContentHash", "Hash")):
            validator(registry, PUBLIC_ID, name).validate(value[field])
        body = jcs(value).encode()
        assert body.hex() == case["canonicalHex"], case["name"]
        digest = hashlib.sha256(binding["prefix"].encode() + body).hexdigest()
        assert digest == case["sha256"], case["name"]


def test_binding_hash_changes_with_destination_identity_but_not_with_key_order():
    case = json.loads(VECTORS.read_text(encoding="utf-8"))["bindingHash"]["cases"][0]
    prefix = b"docsuri:export-binding:v1\n"
    renamed = deepcopy(case["input"])
    renamed["destination"]["destinationId"] = "f" * 32
    assert hashlib.sha256(prefix + jcs(renamed).encode()).hexdigest() != case["sha256"]
    reordered = dict(reversed(list(case["input"].items())))
    assert hashlib.sha256(prefix + jcs(reordered).encode()).hexdigest() == case["sha256"]
