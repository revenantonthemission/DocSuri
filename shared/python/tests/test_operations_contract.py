"""Release 4.0.0 carries U8's amendments A1-A8 without breaking any frozen shape.

The checks read the regenerated schema documents through jsonschema Draft 2020-12
validators registered by `$id`, round-trip samples through the pinned generated models,
and read the canonical contract source for operations, versions and HTTP bindings.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest
import yaml
from conftest import all_schema_paths, load_schema
from jsonschema import Draft202012Validator
from pydantic import ValidationError as ModelValidationError
from referencing import Registry, Resource

from docsuri_shared.workspace import execution, wire

PUBLIC_ID = "https://docsuri.dev/shared/dtos/workspace.schema.json"
INTERNAL_ID = "https://docsuri.dev/shared/events/execution.schema.json"
_ID = "ref:Id"
_ARRAY_ID = "array[ref:Id]"

# Frozen shapes of the release before the amendment (contract release 3.1.0), transcribed
# from that release's generated schemas: {def: (properties, required)}.
FROZEN_PUBLIC = {
    "HostNavigationItem": ({
        "routeId": _ID, "titleKey": _ID, "path": "string", "capabilityId": _ID,
        "available": "boolean", "reasonKey": _ID,
    }, {"routeId", "titleKey", "path", "capabilityId", "available"}),
    "HostNavigationResult": ({
        "manifestRevision": "ref:Revision", "authorityRevision": "ref:Revision",
        "items": "array[ref:HostNavigationItem]", "resolvedRouteId": _ID,
        "returnContext": "ref:HostReturnContext", "clearPriorOwnerState": "boolean",
    }, {"manifestRevision", "authorityRevision", "items", "resolvedRouteId",
        "clearPriorOwnerState"}),
    "OpsObservation": ({
        "observationId": _ID, "capability": _ID, "component": _ID, "observedAt": "ref:Time",
        "revision": "ref:Revision", "status": "enum:available|degraded|unavailable|unknown",
        "evidenceRef": _ID, "limitations": _ARRAY_ID,
    }, {"observationId", "capability", "component", "observedAt", "revision", "status",
        "evidenceRef", "limitations"}),
    "OpsObservationPage": ({"items": "array[ref:OpsObservation]", "page": "ref:PageInfo"},
                           {"items", "page"}),
    "OpsIncident": ({
        "incidentId": _ID, "revision": "ref:Revision", "capabilities": _ARRAY_ID,
        "correlationIds": _ARRAY_ID, "state": "enum:open|investigating|recovering|resolved",
        "evidenceRefs": _ARRAY_ID,
    }, {"incidentId", "revision", "capabilities", "correlationIds", "state", "evidenceRefs"}),
    "OpsIncidentPage": ({"items": "array[ref:OpsIncident]", "page": "ref:PageInfo"},
                        {"items", "page"}),
    "OpsQueryHttp": ({"page": "ref:PageRequest", "capability": _ID}, {"page"}),
    "OpsRecoveryRequestHttp": ({
        "incidentId": _ID, "ownerComponent": _ID, "operation": _ID, "targetId": _ID,
        "expectedRevision": "ref:Revision", "evidenceRefs": _ARRAY_ID, "policy": "ref:PolicyRef",
    }, {"incidentId", "ownerComponent", "operation", "targetId", "expectedRevision",
        "evidenceRefs", "policy"}),
    "AccessKnownSession": ({"state": 'const:"authenticated"', "session": "ref:AccessPublicSession"},
                           {"state", "session"}),
    "ResearchJobReadHttp": ({
        "kind": "enum:research-turn|novelty-analysis|novelty-discussion", "jobId": _ID,
        "contextId": _ID,
    }, {"kind", "jobId", "contextId"}),
}
FROZEN_INTERNAL = {
    "HostCapability": ({
        "capabilityId": _ID, "owner": "enum:" + "|".join([
            "AccountAccess", "CorpusContent", "Discovery", "Library", "PaperAssistance",
            "ResearchWorkspace", "Personalization", "TopicsDigests", "ApprovedExport",
            "UsageEntitlements", "ServiceOperations", "PlatformControl", "WebWorkspace"]),
        "state": "enum:available|degraded|unavailable|unknown", "observedAt": "ref:Time",
        "evidenceRevision": "ref:Revision", "reasonKey": _ID,
    }, {"capabilityId", "owner", "state", "observedAt", "evidenceRevision", "reasonKey"}),
    "HostCapabilitiesPage": ({
        "items": "array[ref:HostCapability]", "page": "ref:PageInfo", "appliedLimit": "integer",
        "policyRef": "ref:PolicyRef",
    }, {"items", "page", "appliedLimit", "policyRef"}),
    "OpsRecoveryRequest": ({
        "context": "ref:CommandContext", "incidentId": _ID, "ownerComponent": _ID,
        "operation": _ID, "targetId": _ID, "expectedRevision": "ref:Revision",
        "evidenceRefs": _ARRAY_ID, "policy": "ref:PolicyRef",
    }, {"context", "incidentId", "ownerComponent", "operation", "targetId", "expectedRevision",
        "evidenceRefs", "policy"}),
    "LifecycleManifestInput": ({
        "context": "ref:CommandContext", "manifestRevision": "ref:Revision",
        "policyRef": "ref:PolicyRef", "participants": "array[ref:LifecycleParticipant]",
    }, {"context", "manifestRevision", "policyRef", "participants"}),
    "ResearchJobRead": ({
        "context": "ref:CommandContext",
        "kind": "enum:research-turn|novelty-analysis|novelty-discussion", "jobId": _ID,
        "contextId": _ID,
    }, {"context", "kind", "jobId", "contextId"}),
}
# The one new property on an existing type (A1), and it is optional.
ADDED_PROPERTIES = {("HostNavigationItem", "placement")}

CONTRACT_VERSIONS = {
    "C01": "2.1.0", "C02": "4.0.0", "C03": "3.1.0", "C04": "2.1.0", "C07": "2.1.0",
    "C10": "2.1.0", "C11": "2.1.0", "C12": "2.1.0",
}
UNCHANGED_VERSIONS = {"C05": "2.0.0", "C06": "2.0.0", "C08": "2.0.0", "C09": "2.1.0"}
NEW_REASON_KEYS = ["nav.capabilityDegraded", "nav.capabilityUnavailable", "nav.capabilityStale",
                   "nav.capabilityUnknown", "nav.administratorOnly"]
RECOVERY_OPERATIONS = ["backup.create", "restore.verify", "restore.production"]
MANIFEST_PAIRS = 21
PAIR_BOUND = 32
CONTEXT = {
    "requestId": "request-1",
    "principal": {"kind": "account", "accountId": "account-a", "authorityRevision": "1",
                  "roles": ["admin"], "mfa": True},
}
POLICY = {"policyId": "u8-synthetic-v1", "revision": "1"}
TIME = "2026-10-22T03:00:00Z"
PAGE = {"nextCursor": "cursor-2", "snapshotRevision": "7"}


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
def blocks() -> list[tuple[str, dict]]:
    return canonical_blocks()


@pytest.fixture(scope="module")
def contracts(blocks) -> dict[str, dict]:
    return {body["id"]: body for kind, body in blocks if kind == "contract"}


@pytest.fixture(scope="module")
def api(blocks) -> dict:
    return next(body for kind, body in blocks
                if kind == "openapi" and body["info"]["title"].startswith("DocSuri application"))


@pytest.fixture(scope="module")
def registry() -> Registry:
    resources = []
    for path in all_schema_paths():
        document = load_schema(str(path.relative_to(path.parents[1])))
        resources.append((document["$id"], Resource.from_contents(document)))
    return Registry().with_resources(resources)


def validator(registry: Registry, document_id: str, name: str) -> Draft202012Validator:
    return Draft202012Validator({"$ref": f"{document_id}#/$defs/{name}"}, registry=registry)


def operations_of(contract: dict) -> dict[str, dict]:
    return {operation["name"]: operation for operation in contract["operations"]}


def round_trip(model, sample: dict) -> None:
    dumped = model.model_validate(sample).model_dump(mode="json", by_alias=True,
                                                     exclude_none=True)
    assert dumped == sample


# 1. Frozen shapes ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("document_id", "frozen"), [(PUBLIC_ID, FROZEN_PUBLIC), (INTERNAL_ID, FROZEN_INTERNAL)]
)
def test_frozen_properties_keep_name_type_and_requiredness_with_no_named_exception(
    document_id, frozen
):
    current = defs(document_id)
    for name, (properties, required) in frozen.items():
        assert name in current, f"frozen def {name} left its schema document"
        actual = current[name]
        for prop, signature in properties.items():
            assert prop in actual["properties"], f"{name}.{prop} was removed"
            assert shape(actual["properties"][prop]) == signature, f"{name}.{prop}"
        assert set(actual.get("required", [])) == required, name
        added = {(name, prop) for prop in set(actual["properties"]) - set(properties)}
        assert added <= ADDED_PROPERTIES, added
        assert not {prop for _, prop in added} & set(actual.get("required", []))


def test_superset_answers_keep_every_frozen_field(registry):
    public = defs(PUBLIC_ID)
    for superset, frozen in (("OpsDashboardItem", "OpsObservation"),
                             ("OpsIncidentRead", "OpsIncident")):
        properties, required = FROZEN_PUBLIC[frozen]
        assert {p: shape(public[superset]["properties"][p]) for p in properties} == properties
        assert set(public[superset]["required"]) == required
    branches = [item["$ref"].split("/")[-1] for item in public["AccessSignInResult"]["oneOf"]]
    login = [item["$ref"].split("/")[-1] for item in public["AccessLoginResult"]["oneOf"]]
    assert branches[: len(login)] == login
    assert set(branches) - set(login) == {"AccessConsentPendingSession", "AccessResetRequired"}


# 2. Placement and reason keys ----------------------------------------------------------


NAVIGATION_ITEM = {"routeId": "jobs", "titleKey": "nav.jobs", "path": "/jobs",
                   "capabilityId": "research", "available": True}


@pytest.mark.parametrize("placement", ["primary", "contextual", "footer"])
def test_each_placement_validates_and_round_trips(registry, placement):
    sample = {**NAVIGATION_ITEM, "placement": placement}
    assert validator(registry, PUBLIC_ID, "HostNavigationItem").is_valid(sample)
    round_trip(wire.HostNavigationItem, sample)


def test_an_unknown_placement_is_refused(registry):
    sample = {**NAVIGATION_ITEM, "placement": "sidebar"}
    assert not validator(registry, PUBLIC_ID, "HostNavigationItem").is_valid(sample)
    assert validator(registry, PUBLIC_ID, "HostNavigationItem").is_valid(NAVIGATION_ITEM)


def test_the_new_reason_keys_join_the_vocabulary_and_validate_on_an_item(registry):
    vocabulary = validator(registry, PUBLIC_ID, "HostNavigationReasonKey")
    for key in ["nav.authenticationRequired", "nav.capabilityPending", *NEW_REASON_KEYS]:
        assert vocabulary.is_valid(key), key
        item = {**NAVIGATION_ITEM, "available": False, "reasonKey": key, "placement": "primary"}
        assert validator(registry, PUBLIC_ID, "HostNavigationItem").is_valid(item)
    assert not vocabulary.is_valid("nav.somethingElse")
    assert {member.value for member in wire.HostNavigationReasonKey} >= set(NEW_REASON_KEYS)


# 3. The public capability projection ---------------------------------------------------


PUBLIC_CAPABILITY = {"capabilityId": "account.entry", "state": "available",
                     "reasonKey": "capability.available"}


@pytest.mark.parametrize("extra", [
    {"ageSeconds": 3}, {"limitations": ["semantic-search-unavailable"]},
    {"evidenceRef": "evidence-1"}, {"count": 2}, {"producerId": "accounts-probe"},
    {"observedAt": TIME},
])
def test_the_public_projection_refuses_operational_detail(registry, extra):
    check = validator(registry, PUBLIC_ID, "HostPublicCapability")
    assert check.is_valid(PUBLIC_CAPABILITY)
    assert not check.is_valid({**PUBLIC_CAPABILITY, **extra})
    page = {"manifestRevision": "u8-manifest", "items": [{**PUBLIC_CAPABILITY, **extra}]}
    assert not validator(registry, PUBLIC_ID, "HostPublicCapabilityPage").is_valid(page)


def test_the_public_projection_round_trips_and_names_stale(registry, contracts):
    page = {"manifestRevision": "u8-manifest", "items": [
        PUBLIC_CAPABILITY, {**PUBLIC_CAPABILITY, "capabilityId": "provider.orcid",
                            "state": "stale", "reasonKey": "nav.capabilityStale"}]}
    assert validator(registry, PUBLIC_ID, "HostPublicCapabilityPage").is_valid(page)
    round_trip(wire.HostPublicCapabilityPage, page)
    assert operations_of(contracts["C01"])["host.listCapabilities"]["output"] == (
        "HostCapabilityRead")
    branches = {item["$ref"].split("/")[-1]
                for item in defs(INTERNAL_ID)["HostCapabilityRead"]["oneOf"]}
    assert branches == {"HostCapabilitiesPage", "HostPublicCapabilityPage"}


# 4. listResearchJobs -------------------------------------------------------------------


JOB_ITEM = {"jobId": "job-1", "kind": "novelty", "label": "참신성 분석", "state": "succeeded",
            "createdAt": TIME, "updatedAt": TIME, "resultAvailable": True}


def test_list_research_jobs_refuses_a_page_over_50_and_an_unknown_kind(registry):
    request = validator(registry, PUBLIC_ID, "ResearchJobListHttp")
    assert request.is_valid({})
    assert request.is_valid({"kind": "research", "limit": 50, "cursor": None})
    assert not request.is_valid({"limit": 51})
    assert not request.is_valid({"limit": 0})
    assert not request.is_valid({"kind": "research-turn"})
    internal = validator(registry, INTERNAL_ID, "ResearchJobList")
    assert internal.is_valid({"context": CONTEXT, "kind": "novelty", "limit": 1})
    assert not internal.is_valid({"context": CONTEXT, "limit": 51})


@pytest.mark.parametrize("cursor", ["opaque", "eyJvd25lciI6ImEifQ.c2lnbmF0dXJl", "x" * 512])
def test_the_job_list_cursor_is_opaque(registry, cursor):
    assert validator(registry, PUBLIC_ID, "ResearchJobListHttp").is_valid({"cursor": cursor})
    page = {"items": [JOB_ITEM], "nextCursor": cursor}
    assert validator(registry, PUBLIC_ID, "ResearchJobListPage").is_valid(page)
    round_trip(wire.ResearchJobListPage, page)
    assert not validator(registry, PUBLIC_ID, "ResearchJobListHttp").is_valid(
        {"cursor": "x" * 513})


def test_list_research_jobs_is_a_read_only_browser_operation(contracts):
    operation = operations_of(contracts["C07"])["listResearchJobs"]
    assert (operation["input"], operation["output"], operation["surface"]) == (
        "ResearchJobList", "ResearchJobListPage", "browser")
    assert operation["errors"] == operations_of(contracts["C07"])["readResearchJob"]["errors"]
    assert "never starts" in operation["semantics"]
    assert set(defs(PUBLIC_ID)["ResearchJobListItem"]["required"]) == set(JOB_ITEM)


# 5. requestRecovery --------------------------------------------------------------------


SUBMISSION = {"operation": "restore.verify", "targetId": "backup-1", "expectedRevision": "3",
              "origin": "administrator", "submissionId": "submission-1", "policy": POLICY}


@pytest.mark.parametrize("operation", ["restore.files", "backup.delete", "platform.exec"])
def test_request_recovery_refuses_any_operation_outside_the_three(registry, operation):
    assert not validator(registry, PUBLIC_ID, "OpsRecoverySubmissionHttp").is_valid(
        {**SUBMISSION, "operation": operation})
    assert not validator(registry, INTERNAL_ID, "OpsRecoverySubmission").is_valid(
        {**SUBMISSION, "context": CONTEXT, "operation": operation})


@pytest.mark.parametrize("missing", ["origin", "submissionId"])
def test_request_recovery_requires_origin_and_submission(registry, missing):
    trimmed = {key: value for key, value in SUBMISSION.items() if key != missing}
    assert not validator(registry, PUBLIC_ID, "OpsRecoverySubmissionHttp").is_valid(trimmed)
    assert not validator(registry, INTERNAL_ID, "OpsRecoverySubmission").is_valid(
        {**trimmed, "context": CONTEXT})


def test_each_offered_operation_validates_and_the_browser_cannot_claim_the_schedule(registry):
    for operation in RECOVERY_OPERATIONS:
        sample = {**SUBMISSION, "operation": operation}
        assert validator(registry, PUBLIC_ID, "OpsRecoverySubmissionHttp").is_valid(sample)
        round_trip(wire.OpsRecoverySubmissionHttp, sample)
    assert not validator(registry, PUBLIC_ID, "OpsRecoverySubmissionHttp").is_valid(
        {**SUBMISSION, "origin": "schedule"})
    internal = {**SUBMISSION, "context": CONTEXT, "origin": "schedule"}
    assert validator(registry, INTERNAL_ID, "OpsRecoverySubmission").is_valid(internal)
    round_trip(execution.OpsRecoverySubmission, internal)


# 6. C02's new authority state and manifest ---------------------------------------------


def test_c02_carries_the_consent_pending_purpose_and_the_reset_required_marker(registry):
    assert "consent_pending" in defs(INTERNAL_ID)["AccessSessionPurpose"]["enum"]
    session = {"sessionId": "session-1", "accountId": "account-a", "authorityRevision": "1",
               "verified": True, "authenticationLevel": "primary", "expiresAt": TIME}
    pending = {"state": "consent_pending", "session": session,
               "consentPurposeIds": ["local-research"], "expiresAt": TIME}
    sign_in = validator(registry, PUBLIC_ID, "AccessSignInResult")
    assert validator(registry, PUBLIC_ID, "AccessConsentPendingSession").is_valid(pending)
    assert sign_in.is_valid(pending)
    round_trip(wire.AccessConsentPendingSession, pending)
    for delivery in ("accepted", "held", "over_allowance"):
        marker = {"state": "reset_required", "delivery": delivery, "messageKey": "reset.mail"}
        assert sign_in.is_valid(marker)
        round_trip(wire.AccessResetRequired, marker)
    assert not sign_in.is_valid({"state": "reset_required", "delivery": "sent",
                                 "messageKey": "reset.mail"})


IDENTITY_LINK = {"identityLinkId": "link-1", "provider": "orcid",
                 "providerSubject": "0000-0002-1825-0097", "revision": "1",
                 "profileAvailable": False}


def test_the_identity_answer_carries_the_consent_pending_result(registry, contracts):
    """Your decision of 2026-10-22: a migrated account's first provider sign-in answers
    AccessIdentityConsentPending, the password path's consent-pending session with its
    link; the three earlier branches stay first and unchanged."""
    session = {"sessionId": "session-1", "accountId": "account-a", "authorityRevision": "1",
               "verified": True, "authenticationLevel": "primary", "expiresAt": TIME}
    pending = {"state": "consent_pending", "identityLink": IDENTITY_LINK, "session": session,
               "consentPurposeIds": ["local-research", "personalization"], "expiresAt": TIME}
    answer = validator(registry, INTERNAL_ID, "AccessIdentityResult")
    assert validator(registry, INTERNAL_ID, "AccessIdentityConsentPending").is_valid(pending)
    assert answer.is_valid(pending)
    round_trip(execution.AccessIdentityConsentPending, pending)
    for missing in ("identityLink", "session", "consentPurposeIds", "expiresAt"):
        assert not answer.is_valid({k: v for k, v in pending.items() if k != missing}), missing
    assert not answer.is_valid({**pending, "state": "consent_given"})
    assert not answer.is_valid({**pending, "token": "secret"})
    branches = [item["$ref"].split("/")[-1]
                for item in defs(INTERNAL_ID)["AccessIdentityResult"]["oneOf"]]
    assert branches == ["AccessIdentitySignedIn", "AccessIdentityLinked", "AccessIdentityMfa",
                        "AccessIdentityConsentPending"]
    assert operations_of(contracts["C02"])["access.completeIdentityFlow"]["output"] == (
        "AccessIdentityResult")
    signed_in = {"state": "signed_in", "identityLink": IDENTITY_LINK, "session": session}
    assert answer.is_valid(signed_in)


def test_c02_carries_the_21_pair_manifest_revision_and_version_4(contracts):
    c02 = contracts["C02"]
    assert c02["version"] == "4.0.0"
    manifest = c02["lifecycleManifest"]
    assert manifest["revision"] == "u8-owners-v1" and manifest["maxPairs"] == PAIR_BOUND
    participants = manifest["participants"]
    every = {**defs(PUBLIC_ID), **defs(INTERNAL_ID)}
    components = every["LifecycleParticipant"]["properties"]["component"]["enum"]
    scopes = every["LifecycleScope"]["enum"]
    assert len(participants) == 10
    assert len({entry["component"] for entry in participants}) == 10
    assert sum(len(entry["scopes"]) for entry in participants) == MANIFEST_PAIRS <= PAIR_BOUND
    for entry in participants:
        assert entry["component"] in components
        assert set(entry["scopes"]) <= set(scopes)
    services = next(e for e in participants if e["component"] == "ServiceOperations")
    assert services["scopes"] == ["backups", "restore_enforcement"]
    assert operations_of(c02)["access.login"]["output"] == "AccessSignInResult"
    assert operations_of(c02)["access.replaceVerifierKey"]["surface"] == "internal"


BACKUPS_RETAINED = {"scope": "backups", "disposition": "retained_by_policy",
                    "evidenceReference": "evidence-1",
                    "reasonKey": "backups-retained-until-disposal", "retainedUntil": TIME}


def test_the_backups_retention_key_and_its_optional_date_validate_and_round_trip(registry):
    """Your decision of 2026-10-22 (BR2.5): ServiceOperations' backups scope reports
    backups-retained-until-disposal with the latest date its sets and copies are gone."""
    key = validator(registry, INTERNAL_ID, "LifecycleRetentionReasonKey")
    for name in ("external-copies-retained-by-owner", "backups-retained-until-disposal"):
        assert key.is_valid(name), name
    scope = validator(registry, PUBLIC_ID, "LifecycleScopeDisposition")
    assert scope.is_valid(BACKUPS_RETAINED)
    round_trip(wire.LifecycleScopeDisposition, BACKUPS_RETAINED)
    undated = {name: value for name, value in BACKUPS_RETAINED.items()
               if name != "retainedUntil"}
    assert scope.is_valid(undated)  # the date is optional
    round_trip(wire.LifecycleScopeDisposition, undated)
    with pytest.raises(ModelValidationError):
        wire.LifecycleScopeDisposition.model_validate({**BACKUPS_RETAINED,
                                                       "retainedUntil": "next week"})


@pytest.mark.parametrize("unknown", ["backups-kept-forever", "external-copies", "", "BACKUPS"])
def test_an_unknown_retention_key_is_refused(registry, unknown):
    assert not validator(registry, INTERNAL_ID, "LifecycleRetentionReasonKey").is_valid(unknown)


@pytest.mark.parametrize("disposition", ["erased", "pending", "blocked", "not_applicable"])
def test_a_retained_until_date_belongs_only_to_a_part_retained_by_policy(registry, disposition):
    scope = validator(registry, PUBLIC_ID, "LifecycleScopeDisposition")
    assert not scope.is_valid({**BACKUPS_RETAINED, "disposition": disposition})
    status = {
        "lifecycleRequestId": "request-1", "accountId": "account-a", "action": "erase",
        "revision": "1", "policyRef": POLICY, "manifestRevision": "u8-owners-v1",
        "authorityRevision": "2", "revocation": "effective", "state": "accepted",
        "participants": [{"participantId": "ServiceOperations", "revision": "1",
                          "state": "acknowledged", "scopes": [BACKUPS_RETAINED],
                          "observedAt": TIME}],
    }
    assert validator(registry, PUBLIC_ID, "LifecycleRequest").is_valid(status)
    round_trip(wire.LifecycleRequest, status)


def test_every_import_and_parity_read_is_internal_and_never_browser_reachable(
    contracts, api, registry
):
    imports = {
        "C02": ("access.importAccount", "access.importIdentityLink", "access.readImportParity"),
        "C03": ("settings.importSettings", "settings.readImportParity",
                "library.importSavedPaper", "library.readImportParity"),
        "C04": ("importPaper", "readImportParity"),
    }
    bound = {operation.get("x-contract-operation")
             for item in api["paths"].values() for operation in item.values()
             if isinstance(operation, dict)}
    for contract, names in imports.items():
        operations = operations_of(contracts[contract])
        for name in names:
            assert operations[name]["surface"] == "internal", name
            assert "composition authority" in operations[name]["auth"], name
            assert f"{contract}.{name}" not in bound, name
    outcome = {"sourceKey": "v1:account:7", "targetId": "account-a", "disposition": "refused",
               "storedDigest": "d" * 64}
    with pytest.raises(ModelValidationError):
        execution.ImportOutcome.model_validate({**outcome, "disposition": "merged"})
    check = validator(registry, INTERNAL_ID, "ImportOutcome")
    assert not check.is_valid(outcome), "a refusal carries its reason"
    assert check.is_valid({**outcome, "reasonKey": "email-case-conflict"})
    assert check.is_valid({**outcome, "disposition": "unchanged"})


# 7. C11 accepts no decision, and every route is administrator-only ---------------------


def property_names(document: dict, name: str, seen: set[str] | None = None) -> set[str]:
    """Every property name reachable from one def, across references."""
    seen = set() if seen is None else seen
    if name in seen:
        return set()
    seen.add(name)
    names: set[str] = set()

    def walk(node):
        if isinstance(node, dict):
            if "$ref" in node:
                target = node["$ref"].split("/")[-1]
                if target in document:
                    names.update(property_names(document, target, seen))
            for key, child in node.get("properties", {}).items():
                names.add(key)
                walk(child)
            for key, child in node.items():
                if key != "properties":
                    walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(document[name])
    return names


def test_no_c11_operation_accepts_a_decision(contracts, api):
    every = {**defs(PUBLIC_ID), **defs(INTERNAL_ID)}
    for operation in contracts["C11"]["operations"]:
        names = {name.lower() for name in property_names(every, operation["input"])}
        assert not any("decision" in name or "approval" in name for name in names), (
            operation["name"])
    for path, item in api["paths"].items():
        if path.startswith("/api/v2/c11/"):
            body = item["post"]["requestBody"]["content"]["application/json"]["schema"]["$ref"]
            names = {n.lower() for n in property_names(every, body.split("/")[-1])}
            assert not any("decision" in n or "approval" in n for n in names), path


def test_every_c11_route_is_administrator_only(contracts, api):
    operations = operations_of(contracts["C11"])
    routes = {path: item["post"] for path, item in api["paths"].items()
              if path.startswith("/api/v2/c11/")}
    assert set(routes) == {"/api/v2/c11/read-dashboard", "/api/v2/c11/list-incidents",
                           "/api/v2/c11/request-recovery", "/api/v2/c11/read-recovery-status"}
    for path, post in routes.items():
        name = post["x-contract-operation"].split(".", 1)[1]
        assert operations[name]["surface"] == "admin", path
        assert operations[name]["auth"].startswith("administrator with current MFA"), path
        assert post["x-authorization"].startswith("administrator with current MFA"), path
        assert post["security"] == [{"sessionCookie": []}], path
    assert operations["recordObservation"]["surface"] == "internal"


def test_the_amended_c11_answers_validate_and_round_trip(registry):
    item = {"observationId": "observation-1", "capability": "export", "component": "export",
            "observedAt": TIME, "revision": "4", "status": "degraded",
            "evidenceRef": "evidence-1", "limitations": [], "freshness": "stale",
            "ageSeconds": 900}
    page = {"items": [item], "page": PAGE}
    assert validator(registry, PUBLIC_ID, "OpsDashboardPage").is_valid(page)
    round_trip(wire.OpsDashboardPage, page)
    resolved = {"incidentId": "incident-1", "revision": "2", "capabilities": ["export"],
                "correlationIds": [], "state": "resolved", "evidenceRefs": ["evidence-2"]}
    incidents = validator(registry, PUBLIC_ID, "OpsIncidentRead")
    assert not incidents.is_valid(resolved)
    assert incidents.is_valid({**resolved, "resolutionKind": "capability-available"})
    status = {"recoveryRequestId": "recovery-1", "revision": "1", "environment": "live",
              "origin": "administrator", "operation": "restore.production", "state": "held",
              "evidenceRefs": [], "createdAt": TIME, "updatedAt": TIME}
    assert validator(registry, PUBLIC_ID, "OpsRecoveryStatus").is_valid(status)
    round_trip(wire.OpsRecoveryStatus, status)


# 8. Versions ---------------------------------------------------------------------------


def test_each_version_equals_the_decision_and_the_release_is_4_0_0(contracts, api):
    assert {key: contracts[key]["version"] for key in CONTRACT_VERSIONS} == CONTRACT_VERSIONS
    assert {key: contracts[key]["version"] for key in UNCHANGED_VERSIONS} == UNCHANGED_VERSIONS
    assert api["info"]["version"] == "4.0.0"
    for name in ("dtos/workspace.schema.json", "events/execution.schema.json"):
        assert load_schema(name)["$comment"].startswith(
            "Generated canonical contract release 4.0.0; source SHA256:")


def test_c10_lists_a6_protocols_with_their_authority_classes(contracts):
    """The person's decision of 2026-10-25, "After the move, same build": the contract
    follows the code, so the classes are U7's `routine` and `destructive-release`, as in
    PlatformControl's inventory, and the four profile protocols share `profile-change`."""
    inventory = contracts["C10"]["inventory"]
    assert inventory["revision"] == 2
    classes = {entry["name"]: entry["authorityClass"] for entry in inventory["protocols"]}
    assert len(classes) == 15
    assert {name for name, kind in classes.items() if kind == "routine"} == {
        "platform.database.backup", "platform.database.restore", "platform.isolation.check",
        "platform.copy.dispose", "platform.decision.record", "platform.ledger.copy"}
    assert set(classes.values()) == {"routine", "destructive-release"}
    kinds = {entry["name"]: entry["effectKind"] for entry in inventory["protocols"]}
    assert {name for name, kind in kinds.items() if kind == "profile-change"} == {
        "platform.profile.mode", "platform.profile.admission",
        "platform.profile.rehearsal-database", "platform.profile.backup-volume"}
    assert {operation["name"] for operation in contracts["C10"]["operations"]} == {
        "inspectEvidence", "executeControlled", "readReceipt"}


# The inventory PlatformControl runs, read as a file: this suite imports no `docsuri_ops`
# module.
PLATFORM_INVENTORY = (Path(__file__).resolve().parents[3]
                      / "ops/src/docsuri_ops/platform_control/inventory.json")


def inventory_mismatches(contract: list[dict], inventory: list[dict]) -> list[str]:
    """Each protocol whose name, authority class or effect kind differs between C10's
    inventory and PlatformControl's `u8Protocols`, sorted."""

    def keyed(entries):
        return {entry["name"]: (entry["authorityClass"], entry["effectKind"])
                for entry in entries}

    stated, run = keyed(contract), keyed(inventory)
    return sorted(name for name in set(stated) | set(run) if stated.get(name) != run.get(name))


def test_c10s_inventory_names_the_protocols_platform_control_runs(contracts):
    stated = contracts["C10"]["inventory"]["protocols"]
    run = json.loads(PLATFORM_INVENTORY.read_text())["u8Protocols"]
    assert len(stated) == len(run) == 15
    assert inventory_mismatches(stated, run) == []
    # A planted mismatch in a class, a kind or a name is found.
    planted = [dict(entry) for entry in stated]
    planted[1]["authorityClass"] = "destructive-release"
    planted[7]["effectKind"] = "profile-mode"
    planted[13]["name"] = "platform.decision.recorded"
    assert inventory_mismatches(planted, run) == sorted({
        stated[1]["name"], stated[7]["name"], stated[13]["name"], "platform.decision.recorded"})


def test_c12_names_each_provider_profile_with_its_evidence_gate(contracts):
    profiles = {entry["id"]: entry for entry in contracts["C12"]["providerProfiles"]}
    assert set(profiles) == {"google-identity", "orcid-identity", "resend-account-mail",
                             "resend-digest-mail", "local-model-executor",
                             "local-query-embedder"}
    allowed = {"identity.exchange", "identity.profile", "email.send", "model.generate"}
    for entry in profiles.values():
        assert set(entry["profiles"]) <= allowed and entry["evidenceGate"]
    assert "ModelEvidence" in profiles["local-model-executor"]["evidenceGate"]


# 9. Every A8 path exists and is bound --------------------------------------------------


@pytest.mark.parametrize(("path", "operation_id", "contract_operation"), [
    ("/api/v2/c07/list-research-jobs", "C07_listResearchJobs", "C07.listResearchJobs"),
    ("/api/v2/c11/read-recovery-status", "C11_readRecoveryStatus", "C11.readRecoveryStatus"),
])
def test_each_a8_api_path_is_bound_to_its_operation(api, path, operation_id, contract_operation):
    post = api["paths"][path]["post"]
    assert (post["operationId"], post["x-contract-operation"]) == (
        operation_id, contract_operation)
    headers = {item["name"] for item in post["parameters"]
               if item["in"] == "header" and item["required"] is True}
    assert headers == {"X-CSRF-Token", "Idempotency-Key"}
    body = post["requestBody"]["content"]["application/json"]["schema"]["$ref"].split("/")[-1]
    assert body.endswith("Http") and "context" not in defs(PUBLIC_ID)[body]["properties"]
    assert "default" in post["responses"]


@pytest.mark.parametrize(("path", "operation_id"), [
    ("/privacy", "publicPrivacyDocument"), ("/terms", "publicTermsDocument"),
    ("/sign-in/callback/{provider}", "identityArrivalShell"),
])
def test_each_a8_public_document_is_reachable_signed_out(api, path, operation_id):
    get = api["paths"][path]["get"]
    assert get["operationId"] == operation_id
    assert get["security"] == []
    assert "text/html" in get["responses"]["200"]["content"]
    assert "requestBody" not in get and "x-contract-operation" not in get


SERVED_CALLBACK = "/api/v2/identity/callback/{provider}"
REPOSITORY = Path(__file__).resolve().parents[3]


def test_c13s_identity_callback_path_equals_the_served_route(api):
    """A8 (decision of 2026-10-22): C13 documents the identity callback at the path the
    service serves, `control_http.py`'s one route, and nowhere else."""
    paths = api["paths"]
    get = paths[SERVED_CALLBACK]["get"]
    assert get["operationId"] == "identityCallback" and get["security"] == []
    assert "/api/v2/identity/{provider}/callback" not in paths
    bound = [path for path, item in paths.items() for operation in item.values()
             if isinstance(operation, dict) and operation.get("operationId") == "identityCallback"]
    assert bound == [SERVED_CALLBACK]
    served = (REPOSITORY / "backend/modules/accounts/control_http.py").read_text()
    assert served.count(f'@router.get("{SERVED_CALLBACK}")') == 1
    assert "/api/v2/identity/{provider}/callback" not in served
    # The arrival page hands the provider's answer to that same route.
    shell = " ".join(paths["/sign-in/callback/{provider}"]["get"]["description"].split())
    assert SERVED_CALLBACK in shell


def test_the_mounted_c11_routes_and_the_changed_answers_are_bound(api):
    paths = api["paths"]
    answers = {
        "/api/v2/c11/read-dashboard": "OpsDashboardPage",
        "/api/v2/c11/list-incidents": "OpsIncidentReadPage",
        "/api/v2/c02/access-login": "AccessSignInResult",
    }
    for path, answer in answers.items():
        schema = paths[path]["post"]["responses"]["200"]["content"]["application/json"]["schema"]
        assert schema["$ref"].split("/")[-1] == answer, path
    body = paths["/api/v2/c11/request-recovery"]["post"]["requestBody"]
    assert body["content"]["application/json"]["schema"]["$ref"].endswith(
        "/OpsRecoverySubmissionHttp")
    assert "/maintenance" not in paths
