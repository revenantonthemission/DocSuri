"""In-process CLI dispatcher tests: the same envelope the mounted boundary uses.

These exercise every dispatch branch without a new process so the operator CLI
module is measured directly; the subprocess suite proves the real mounted wire.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from docsuri_ops.platform_control import cli, enums

pytestmark = pytest.mark.u7_integration


def context(harness, authority) -> dict:
    return {
        "requestId": str(uuid4()),
        "principal": {"kind": "operator", "actorId": harness.actor, "authorityRef": authority},
    }


def test_execute_then_read_then_inspect_round_trip(harness):
    target = harness.target()
    authority = harness.grant(target=target)
    digest = "a" * 64
    recorded = harness.evidence(target=target, input_hash=digest)
    request = {
        "context": {**context(harness, authority), "idempotencyKey": uuid4().hex},
        "operation": "platform.file.write",
        "targetId": target,
        "inputHash": digest,
        "evidenceId": recorded["evidenceId"],
        "evidenceGeneration": str(recorded["generation"]),
        "authorityRef": authority,
        "policy": {"policyId": "p", "revision": "1"},
    }
    response, status = cli.run({"op": "executeControlled", "request": request}, harness.profile)
    assert status == 0 and response["ok"] is True
    operation_id = response["result"]["operationId"]
    read, _ = cli.run(
        {"op": "readReceipt", "request": {"context": context(harness, authority), "operationId": operation_id}},
        harness.profile,
    )
    assert read["result"]["outcome"] == "succeeded"
    inspect, _ = cli.run(
        {
            "op": "inspectEvidence",
            "request": {
                "context": context(harness, authority),
                "targetId": target,
                "inputHash": digest,
                "requiredGeneration": str(recorded["generation"]),
            },
        },
        harness.profile,
    )
    assert inspect["result"]["compatibility"] == "compatible"


def test_provisioning_and_revocation_via_the_cli(harness):
    target = harness.target()
    authority_id = str(uuid4())
    provision, status = cli.run(
        {
            "op": "provisionAuthority",
            "request": {
                "authorityId": authority_id,
                "scope": [target],
                "operations": ["platform.file.write"],
                "authorityClass": enums.CLASS_ROUTINE,
            },
        },
        harness.profile,
    )
    assert status == 0 and provision["result"]["actorReference"] == harness.actor
    revoke, _ = cli.run({"op": "revokeAuthority", "request": {"authorityId": authority_id}}, harness.profile)
    assert revoke["result"]["revocation"] == "revoked"


def test_provision_target_and_record_evidence_via_the_cli(harness):
    target = f"t-{uuid4().hex[:12]}"
    created, _ = cli.run({"op": "provisionTarget", "request": {"targetId": target}}, harness.profile)
    assert created["result"]["targetId"] == target
    recorded, _ = cli.run(
        {"op": "recordEvidence", "request": {"targetId": target, "inputHash": "b" * 64, "maxAgeSeconds": 60}},
        harness.profile,
    )
    assert recorded["result"]["generation"] == 1


def test_status_and_reconcile_paths(harness):
    target = harness.target()
    authority = harness.grant(target=target)
    digest = "c" * 64
    recorded = harness.evidence(target=target, input_hash=digest)
    binding = harness.runtime.begin_operation(
        actor=harness.actor,
        authority_id=authority,
        operation="platform.file.write",
        target=target,
        input_hash=digest,
        environment=harness.environment,
        evidence_id=recorded["evidenceId"],
        generation=recorded["generation"],
        idempotency_key=uuid4().hex,
        effect_reference=f"{target}/effect-0123456789abcdef.json",
    )
    harness.runtime.settle_operation(
        operation_id=binding["operationId"],
        outcome="unknown",
        disposition="unknown",
        effect_refs=[],
    )
    status, _ = cli.run(
        {"op": "status", "request": {"context": context(harness, authority)}}, harness.profile
    )
    assert status["result"]["unresolvedCount"] >= 1
    reconciled, _ = cli.run(
        {
            "op": "reconcile",
            "request": {"context": context(harness, authority), "operationId": binding["operationId"]},
        },
        harness.profile,
    )
    assert reconciled["result"]["reconciliationState"] == "reconciled-not-applied"


def test_status_is_bounded_to_the_callers_scope(harness):
    target = harness.target()
    other = harness.target()
    authority = harness.grant(target=target)
    digest = "e" * 64
    recorded = harness.evidence(target=other, input_hash=digest)
    other_authority = harness.grant(target=other)
    binding = harness.runtime.begin_operation(
        actor=harness.actor,
        authority_id=other_authority,
        operation="platform.file.write",
        target=other,
        input_hash=digest,
        environment=harness.environment,
        evidence_id=recorded["evidenceId"],
        generation=recorded["generation"],
        idempotency_key=uuid4().hex,
        effect_reference=f"{other}/effect-0123456789abcdef.json",
    )
    harness.runtime.settle_operation(
        operation_id=binding["operationId"],
        outcome="unknown",
        disposition="unknown",
        effect_refs=[],
    )
    # the first target's authority cannot see the other target's unresolved work
    response, _ = cli.run(
        {"op": "status", "request": {"context": context(harness, authority)}}, harness.profile
    )
    assert binding["operationId"] not in response["result"]["unresolvedOperations"]


def test_non_numeric_evidence_generation_is_invalid_input(harness):
    target = harness.target()
    authority = harness.grant(target=target)
    digest = "f" * 64
    recorded = harness.evidence(target=target, input_hash=digest)
    request = {
        "context": {**context(harness, authority), "idempotencyKey": uuid4().hex},
        "operation": "platform.file.write",
        "targetId": target,
        "inputHash": digest,
        "evidenceId": recorded["evidenceId"],
        "evidenceGeneration": "not-a-number",
        "authorityRef": authority,
        "policy": {"policyId": "p", "revision": "1"},
    }
    response, status = cli.run({"op": "executeControlled", "request": request}, harness.profile)
    assert status == 1
    assert response["error"]["code"] == "INVALID_INPUT"


@pytest.mark.parametrize(
    "document",
    [
        {"op": "nonsense", "request": {}},
        {"op": "provisionAuthority", "request": {"authorityId": "", "scope": ["t"], "operations": [], "authorityClass": "routine"}},
        {"op": "revokeAuthority", "request": {}},
        {"op": "provisionTarget", "request": {"targetId": "bad/../path"}},
        {"op": "reconcile", "request": {}},
        {"op": "recordEvidence", "request": {"targetId": "t", "inputHash": "short"}},
    ],
)
def test_invalid_requests_are_refused_with_a_stable_code(harness, document):
    response, status = cli.run(document, harness.profile)
    assert status == 1
    assert response["ok"] is False
    assert response["error"]["code"] in {
        "INVALID_INPUT",
        "FORBIDDEN",
        "NOT_FOUND",
        "POLICY_UNRESOLVED",
    }


def test_wire_validation_rejects_missing_required_fields(harness):
    target = harness.target()
    authority = harness.grant(target=target)
    response, status = cli.run(
        {"op": "inspectEvidence", "request": {"context": context(harness, authority)}},
        harness.profile,
    )
    assert status == 1
    assert response["error"]["code"] == "INVALID_INPUT"
