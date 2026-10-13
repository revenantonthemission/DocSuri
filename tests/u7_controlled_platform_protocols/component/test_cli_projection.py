from __future__ import annotations

import pytest

from docsuri_ops.platform_control import cli

pytestmark = pytest.mark.u7_component


def internal_receipt(**overrides):
    base = {
        "operationId": "op-1",
        "receiptId": "rec-1",
        "targetId": "t-1",
        "inputHash": "a" * 64,
        "authorityRef": "auth-1",
        "evidenceId": "ev-1",
        "revision": "rev-1",
        "operationState": "completed",
        "outcome": "completed",
        "effectRefs": ["t-1/effect-0123456789abcdef.json"],
        "reconciliationEvidence": [],
    }
    base.update(overrides)
    return base


def test_effect_token_is_deterministic_and_operation_scoped():
    one = cli.effect_token("t-1", "a" * 64, "key")
    assert one == cli.effect_token("t-1", "a" * 64, "key")
    assert len(one) == 16
    assert one != cli.effect_token("t-2", "a" * 64, "key")
    assert one != cli.effect_token("t-1", "b" * 64, "key")


@pytest.mark.parametrize(
    "state,wire",
    [
        ("authorized", "accepted"),
        ("executing", "running"),
        ("completed", "succeeded"),
        ("failed", "failed"),
        ("unknown", "unknown"),
    ],
)
def test_receipt_projection_follows_the_operation_state(state, wire):
    projected = cli.project_receipt(internal_receipt(operationState=state))
    assert projected["outcome"] == wire
    assert projected["operationId"] == "op-1"
    assert projected["revision"] == "rev-1"


def test_receipt_projection_keeps_effect_and_reconciliation_lists():
    projected = cli.project_receipt(
        internal_receipt(reconciliationEvidence=["promoted:deadline"])
    )
    assert projected["effectRefs"] == ["t-1/effect-0123456789abcdef.json"]
    assert projected["reconciliationEvidence"] == ["promoted:deadline"]
