from __future__ import annotations

from uuid import uuid4

import pytest

from docsuri_ops.platform_control import enums
from docsuri_ops.platform_control.errors import ControlError

pytestmark = pytest.mark.u7_database


def key() -> str:
    return uuid4().hex


def begin(harness, *, authority, target, digest, key, operation="platform.file.write", generation=None, evidence=None):
    recorded = evidence or harness.evidence(target=target, input_hash=digest)
    return harness.runtime.begin_operation(
        actor=harness.actor,
        authority_id=authority,
        operation=operation,
        target=target,
        input_hash=digest,
        environment=harness.environment,
        evidence_id=recorded["evidenceId"],
        generation=generation or recorded["generation"],
        idempotency_key=key,
        effect_reference=f"{target}/effect-0123456789abcdef.json",
    )


def test_wrong_actor_is_forbidden_before_any_effect(harness):
    target = harness.target()
    foreign = harness.grant(target=target, actor="a-different-local-user")
    with pytest.raises(ControlError) as excinfo:
        begin(harness, authority=foreign, target=target, digest="d" * 64, key=key())
    assert excinfo.value.code == "FORBIDDEN"


def test_application_admin_without_a_grant_is_forbidden(harness):
    target = harness.target()
    unprovisioned = "00000000-0000-0000-0000-000000000000"
    with pytest.raises(ControlError) as excinfo:
        begin(harness, authority=unprovisioned, target=target, digest="e" * 64, key=key())
    assert excinfo.value.code == "FORBIDDEN"


def test_target_outside_the_grant_is_forbidden(harness):
    granted_target = harness.target()
    other_target = harness.target()
    authority = harness.grant(target=granted_target)
    with pytest.raises(ControlError) as excinfo:
        begin(harness, authority=authority, target=other_target, digest="f" * 64, key=key())
    assert excinfo.value.code == "FORBIDDEN"


def test_destructive_release_requires_its_own_class(harness):
    target = harness.target()
    routine = harness.grant(target=target, operations=["platform.target.release"])
    recorded = harness.evidence(target=target, input_hash="a" * 64)
    with pytest.raises(ControlError) as excinfo:
        begin(
            harness,
            authority=routine,
            target=target,
            digest="a" * 64,
            key=key(),
            operation="platform.target.release",
            evidence=recorded,
        )
    assert excinfo.value.code == "FORBIDDEN"
    # the same operation succeeds under a separately provisioned destructive-release grant
    destructive = harness.grant(
        target=target,
        operations=["platform.target.release"],
        authority_class=enums.CLASS_DESTRUCTIVE,
    )
    binding = begin(
        harness,
        authority=destructive,
        target=target,
        digest="a" * 64,
        key=key(),
        operation="platform.target.release",
        evidence=recorded,
    )
    assert binding["operationState"] == "authorized"


def test_revocation_takes_effect_immediately(harness):
    target = harness.target()
    authority = harness.grant(target=target)
    harness.provisioner.revoke_authority(authority)
    with pytest.raises(ControlError) as excinfo:
        begin(harness, authority=authority, target=target, digest="1" * 64, key=key())
    assert excinfo.value.code == "FORBIDDEN"


def test_evidence_reader_grant_reads_but_cannot_execute(harness):
    target = harness.target()
    reader = harness.grant(
        target=target,
        operations=["inspectEvidence", "readReceipt"],
        authority_class=enums.CLASS_READER,
    )
    # a read is admitted for the exact target
    harness.runtime.call_committed(
        "guard_authority",
        (harness.actor, reader, enums.CLASS_ROUTINE, "inspectEvidence", target, False),
    )
    with pytest.raises(ControlError) as excinfo:
        begin(harness, authority=reader, target=target, digest="2" * 64, key=key())
    assert excinfo.value.code == "FORBIDDEN"


def test_reads_are_target_scope_bounded_in_the_store_layer(harness):
    target = harness.target()
    authority = harness.grant(target=target)
    digest = "9" * 64
    binding = begin(harness, authority=authority, target=target, digest=digest, key=key())
    # an authority scoped to a different target cannot read this target's data
    other = harness.target()
    foreign = harness.grant(target=other)
    with pytest.raises(ControlError) as receipt_error:
        harness.runtime.read_receipt(harness.actor, foreign, binding["operationId"])
    assert receipt_error.value.code == "FORBIDDEN"
    with pytest.raises(ControlError) as evidence_error:
        harness.runtime.latest_evidence(harness.actor, foreign, target)
    assert evidence_error.value.code == "FORBIDDEN"
    # the owner's own scope still reads correctly
    assert harness.receipt(binding["operationId"], authority)["targetId"] == target


def test_status_and_unresolved_are_bounded_to_the_callers_scope(harness):
    target = harness.target()
    authority = harness.grant(target=target)
    digest = "8" * 64
    binding = begin(harness, authority=authority, target=target, digest=digest, key=key())
    harness.runtime.mark_executing(binding["operationId"])
    harness.runtime.settle_operation(
        operation_id=binding["operationId"],
        outcome="unknown",
        disposition="unknown",
        effect_refs=[],
    )
    other = harness.target()
    foreign = harness.grant(target=other)
    assert binding["operationId"] not in [
        item["operationId"] for item in harness.unresolved(foreign)
    ]
    assert binding["operationId"] in [item["operationId"] for item in harness.unresolved(authority)]
    assert harness.counts(foreign)["unresolved"] == 0


def test_scope_validation_refuses_wildcards(harness):
    with pytest.raises(ControlError) as excinfo:
        harness.provisioner.provision_authority(
            authority_id="11111111-1111-1111-1111-111111111111",
            actor=harness.actor,
            scope=["*"],
            operations=["platform.file.write"],
            authority_class=enums.CLASS_ROUTINE,
            binding={},
        )
    assert excinfo.value.code == "INVALID_INPUT"
