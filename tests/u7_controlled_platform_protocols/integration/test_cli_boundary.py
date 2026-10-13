from __future__ import annotations

import json
import subprocess
import sys
import time
from uuid import uuid4

import pytest

from docsuri_shared.workspace import execution

pytestmark = pytest.mark.u7_integration


def call_cli(document: dict, *, environment: str | None = None) -> tuple[int, dict, str]:
    manifest = environment or __import__("os").environ["DOCSURI_U7_ENVIRONMENT_FILE"]
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "docsuri_ops.platform_control",
            "--environment-file",
            manifest,
        ],
        input=json.dumps(document).encode(),
        capture_output=True,
    )
    return proc.returncode, json.loads(proc.stdout), proc.stderr.decode()


def context(harness, authority) -> dict:
    return {
        "requestId": str(uuid4()),
        "principal": {"kind": "operator", "actorId": harness.actor, "authorityRef": authority},
    }


def execute_request(harness, *, target, authority, evidence, digest, key_=None):
    return {
        "context": {**context(harness, authority), "idempotencyKey": key_ or uuid4().hex},
        "operation": "platform.file.write",
        "targetId": target,
        "inputHash": digest,
        "evidenceId": evidence["evidenceId"],
        "evidenceGeneration": str(evidence["generation"]),
        "authorityRef": authority,
        "policy": {"policyId": "policy-1", "revision": "1"},
    }


def fixture(harness, *, digest="a"):
    target = harness.target()
    authority = harness.grant(target=target)
    input_hash = (digest * 64)[:64]
    recorded = harness.evidence(target=target, input_hash=input_hash)
    return target, authority, input_hash, recorded


def test_execute_controlled_produces_a_conforming_operator_receipt(harness):
    target, authority, digest, recorded = fixture(harness)
    rc, out, _ = call_cli(
        {"op": "executeControlled", "request": execute_request(
            harness, target=target, authority=authority, evidence=recorded, digest=digest)}
    )
    assert rc == 0
    assert out["ok"] is True
    execution.OperatorReceipt.model_validate(out["result"])  # conforms to C10
    assert out["result"]["outcome"] == "succeeded"
    assert out["result"]["targetId"] == target
    assert out["result"]["effectRefs"]


def test_replay_returns_the_same_operation_id(harness):
    target, authority, digest, recorded = fixture(harness, digest="b")
    key_ = uuid4().hex
    request = execute_request(
        harness, target=target, authority=authority, evidence=recorded, digest=digest, key_=key_
    )
    _, first, _ = call_cli({"op": "executeControlled", "request": request})
    _, second, _ = call_cli({"op": "executeControlled", "request": request})
    assert first["result"]["operationId"] == second["result"]["operationId"]


def test_inspect_evidence_produces_a_conforming_operator_evidence(harness):
    target, authority, digest, recorded = fixture(harness, digest="c")
    rc, out, _ = call_cli(
        {
            "op": "inspectEvidence",
            "request": {
                "context": context(harness, authority),
                "targetId": target,
                "inputHash": digest,
                "requiredGeneration": str(recorded["generation"]),
            },
        }
    )
    assert rc == 0
    execution.OperatorEvidence.model_validate(out["result"])  # conforms to C10
    assert out["result"]["compatibility"] == "compatible"


def test_inspect_evidence_labels_stale_and_missing_honestly(harness):
    target = harness.target()
    authority = harness.grant(target=target)
    digest = "d" * 64
    recorded = harness.evidence(target=target, input_hash=digest, max_age_seconds=1)
    time.sleep(2)
    _, out, _ = call_cli(
        {
            "op": "inspectEvidence",
            "request": {
                "context": context(harness, authority),
                "targetId": target,
                "inputHash": digest,
                "requiredGeneration": str(recorded["generation"]),
            },
        }
    )
    assert out["result"]["compatibility"] == "incompatible"  # stale, never healthy
    missing_target = harness.target()
    missing_authority = harness.grant(target=missing_target)
    _, out, _ = call_cli(
        {
            "op": "inspectEvidence",
            "request": {
                "context": context(harness, missing_authority),
                "targetId": missing_target,
                "inputHash": digest,
                "requiredGeneration": "1",
            },
        }
    )
    assert out["result"]["compatibility"] == "unknown"


@pytest.mark.parametrize(
    "mutate,code",
    [
        (lambda req: req["context"]["principal"].__setitem__("actorId", "somebody-else"), "FORBIDDEN"),
        (lambda req: req.__setitem__("operation", "rm -rf /"), "INVALID_INPUT"),
        (lambda req: req.__setitem__("operation", "platform.unknown"), "POLICY_UNRESOLVED"),
        (lambda req: req.__setitem__("evidenceId", str(uuid4())), "POLICY_UNRESOLVED"),
    ],
)
def test_execute_controlled_refuses_with_the_stable_vocabulary(harness, mutate, code):
    target, authority, digest, recorded = fixture(harness, digest="e")
    request = execute_request(
        harness, target=target, authority=authority, evidence=recorded, digest=digest
    )
    mutate(request)
    rc, out, _ = call_cli({"op": "executeControlled", "request": request})
    assert rc == 1
    assert out["ok"] is False
    assert out["error"]["code"] == code


def test_read_receipt_of_an_unknown_operation_is_not_found(harness):
    target, authority, _digest, _recorded = fixture(harness, digest="f")
    rc, out, _ = call_cli(
        {
            "op": "readReceipt",
            "request": {"context": context(harness, authority), "operationId": str(uuid4())},
        }
    )
    assert out["error"]["code"] == "NOT_FOUND"


def test_read_receipt_creates_no_second_effect(harness):
    target, authority, digest, recorded = fixture(harness, digest="1")
    _, executed, _ = call_cli(
        {"op": "executeControlled", "request": execute_request(
            harness, target=target, authority=authority, evidence=recorded, digest=digest)}
    )
    operation_id = executed["result"]["operationId"]
    before = harness.counts(authority)
    call_cli(
        {
            "op": "readReceipt",
            "request": {"context": context(harness, authority), "operationId": operation_id},
        }
    )
    after = harness.counts(authority)
    assert before == after


def test_read_receipt_promotes_an_over_deadline_in_flight_operation(harness, migrate):
    target, authority, digest, recorded = fixture(harness, digest="2")
    _, executed, _ = call_cli(
        {"op": "executeControlled", "request": execute_request(
            harness, target=target, authority=authority, evidence=recorded, digest=digest)}
    )
    # a second, separate operation left in flight is driven over its deadline
    inflight = harness.runtime.begin_operation(
        actor=harness.actor,
        authority_id=authority,
        operation="platform.file.write",
        target=target,
        input_hash=digest,
        environment=harness.environment,
        evidence_id=recorded["evidenceId"],
        generation=recorded["generation"],
        idempotency_key=uuid4().hex,
        effect_reference=f"{target}/effect-fedcba9876543210.json",
    )
    harness.runtime.mark_executing(inflight["operationId"])
    migrate.execute(
        "UPDATE platform_control.target_lease SET deadline_at = clock_timestamp() - interval '1 hour' WHERE target_id = %s",
        (target,),
    )
    migrate.commit()
    # a plain receipt read (no separate reconcile call) must promote it to unknown
    rc, out, _ = call_cli(
        {
            "op": "readReceipt",
            "request": {"context": context(harness, authority), "operationId": inflight["operationId"]},
        }
    )
    assert rc == 0
    assert out["result"]["outcome"] == "unknown"  # never accepted/running, never succeeded


def test_malformed_envelope_is_refused_and_emits_exactly_one_document(harness):
    manifest = __import__("os").environ["DOCSURI_U7_ENVIRONMENT_FILE"]
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "docsuri_ops.platform_control",
            "--environment-file",
            manifest,
        ],
        input=b"not-json",
        capture_output=True,
    )
    decoded = json.loads(proc.stdout)
    assert decoded["ok"] is False
    assert decoded["error"]["code"] == "INVALID_INPUT"
    assert proc.stdout.count(b"\n") <= 1


def test_unknown_envelope_operation_is_refused(harness):
    rc, out, _ = call_cli({"op": "launchMissiles", "request": {}})
    assert rc == 1
    assert out["error"]["code"] == "INVALID_INPUT"
