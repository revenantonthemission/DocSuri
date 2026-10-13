from __future__ import annotations

from uuid import uuid4

import pytest

from docsuri_ops.platform_control.errors import ControlError
from docsuri_ops.platform_control.store import Store

pytestmark = pytest.mark.u7_database


def key() -> str:
    return uuid4().hex


def bind(harness, authority, target, digest, key):
    recorded = harness.evidence(target=target, input_hash=digest)
    return harness.runtime.begin_operation(
        actor=harness.actor,
        authority_id=authority,
        operation="platform.file.write",
        target=target,
        input_hash=digest,
        environment=harness.environment,
        evidence_id=recorded["evidenceId"],
        generation=recorded["generation"],
        idempotency_key=key,
        effect_reference=f"{target}/effect-0123456789abcdef.json",
    )


def test_one_in_flight_effect_per_target_refuses_a_second(harness):
    target = harness.target()
    authority = harness.grant(target=target)
    first = bind(harness, authority, target, "a" * 64, key())
    with pytest.raises(ControlError) as excinfo:
        bind(harness, authority, target, "a" * 64, key())
    assert excinfo.value.code == "CONFLICT"
    # settling the first releases the lease for a new operation
    harness.runtime.settle_operation(
        operation_id=first["operationId"],
        outcome="completed",
        disposition="applied",
        effect_refs=["t/effect-0123456789abcdef.json"],
    )
    second = bind(harness, authority, target, "a" * 64, key())
    assert second["operationState"] == "authorized"


def test_binding_is_committed_before_any_effect(harness):
    target = harness.target()
    authority = harness.grant(target=target)
    binding = bind(harness, authority, target, "b" * 64, key())
    # a fresh read (new transaction) sees the bound operation in the authorized state
    receipt = harness.receipt(binding["operationId"], authority)
    assert receipt["operationState"] == "authorized"
    assert receipt["outcome"] is None
    assert receipt["reconciliationState"] == "pending"


def test_lease_is_durable_not_a_transaction_held_open(harness, migrate):
    target = harness.target()
    authority = harness.grant(target=target)
    bind(harness, authority, target, "c" * 64, key())
    # visible to a brand-new connection/transaction: the lease is durable, not a
    # transaction held open across the effect
    rows = migrate.execute(
        "SELECT count(*) FROM platform_control.target_lease WHERE target_id = %s",
        (target,),
    ).fetchone()
    assert rows[0] == 1


def test_failed_transaction_rolls_back_the_binding(harness, migrate):
    target = harness.target()
    authority = harness.grant(target=target)
    recorded = harness.evidence(target=target, input_hash="d" * 64)
    idempotency_key = key()
    with harness.runtime.connection() as conn:
        Store.call(
            conn,
            "begin_operation",
            (
                harness.actor,
                authority,
                "platform.file.write",
                target,
                "d" * 64,
                harness.environment,
                recorded["evidenceId"],
                recorded["generation"],
                idempotency_key,
                f"{target}/effect-0123456789abcdef.json",
            ),
        )
        conn.rollback()
    count = migrate.execute(
        "SELECT count(*) FROM platform_control.operation WHERE authority_actor = %s AND idempotency_key = %s",
        (harness.actor, idempotency_key),
    ).fetchone()[0]
    lease = migrate.execute(
        "SELECT count(*) FROM platform_control.target_lease WHERE target_id = %s",
        (target,),
    ).fetchone()[0]
    assert count == 0
    assert lease == 0


def test_revocation_ordering_denies_the_second_request_with_no_effect(harness):
    target = harness.target()
    authority = harness.grant(target=target)
    first = bind(harness, authority, target, "e" * 64, key())
    harness.runtime.settle_operation(
        operation_id=first["operationId"],
        outcome="failed",
        disposition="not-applied",
        effect_refs=[],
    )
    harness.provisioner.revoke_authority(authority)
    with pytest.raises(ControlError) as excinfo:
        bind(harness, authority, target, "e" * 64, key())
    assert excinfo.value.code == "FORBIDDEN"


def test_stale_in_flight_lease_promotes_to_unknown_not_success(harness, migrate):
    target = harness.target()
    authority = harness.grant(target=target)
    # a real deadline is finite but not zero; backdate the lease through the
    # fixture's migration authority so the over-deadline path is exercised now.
    binding = bind(harness, authority, target, "f" * 64, key())
    harness.runtime.mark_executing(binding["operationId"])
    migrate.execute(
        "UPDATE platform_control.target_lease SET deadline_at = clock_timestamp() - interval '1 hour' WHERE target_id = %s",
        (target,),
    )
    migrate.commit()
    promoted = harness.runtime.promote_in_flight()
    assert promoted >= 1
    receipt = harness.receipt(binding["operationId"], authority)
    assert receipt["operationState"] == "unknown"
    assert receipt["outcome"] == "unknown"
    assert receipt["reconciliationState"] == "unresolved"
