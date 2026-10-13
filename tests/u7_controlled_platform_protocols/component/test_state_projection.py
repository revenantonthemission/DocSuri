from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from docsuri_ops.platform_control import enums, errors, evidence

pytestmark = pytest.mark.u7_component


@pytest.mark.parametrize(
    "internal,wire",
    [
        ("current", "compatible"),
        ("stale", "incompatible"),
        ("mismatched", "incompatible"),
        ("missing", "unknown"),
    ],
)
def test_compatibility_projects_onto_the_wire_enum(internal, wire):
    assert enums.wire_compatibility(internal) == wire


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
def test_operation_state_projects_onto_the_wire_outcome(state, wire):
    assert enums.wire_outcome(state) == wire


def test_unknown_projection_is_never_succeeded():
    assert enums.wire_outcome("unknown") == "unknown"


@pytest.mark.parametrize(
    "sqlstate,code",
    [
        ("42501", errors.FORBIDDEN),
        ("23505", errors.CONFLICT),
        ("U7001", errors.POLICY_UNRESOLVED),
        ("U7002", errors.CONFLICT),
        ("U7003", errors.INVALID_INPUT),
        ("U7004", errors.NOT_FOUND),
        ("U7005", errors.UNKNOWN_OUTCOME),
        ("XX000", errors.DEPENDENCY_UNAVAILABLE),
    ],
)
def test_sqlstate_maps_onto_the_stable_vocabulary(sqlstate, code):
    assert errors.code_for_sqlstate(sqlstate) == code


def test_control_error_only_accepts_the_c10_vocabulary():
    with pytest.raises(ValueError):
        errors.ControlError("NOT_A_CODE", "nope")
    error = errors.ControlError(errors.FORBIDDEN, "denied", request_id="r-1")
    assert error.as_wire_error()["code"] == "FORBIDDEN"
    assert error.as_wire_error()["requestId"] == "r-1"


def _evidence(generation=1, observed_offset=-1, max_age=300, target="t", digest="a" * 64, env="e"):
    return {
        "evidenceId": "11111111-1111-1111-1111-111111111111",
        "targetId": target,
        "inputHash": digest,
        "environmentBinding": env,
        "generation": generation,
        "observedAt": datetime.now(timezone.utc) + timedelta(seconds=observed_offset),
        "maxAgeSeconds": max_age,
    }


def test_current_evidence_is_the_only_authorizing_state():
    state, checks = evidence.classify(
        evidence=_evidence(),
        target="t",
        input_hash="a" * 64,
        environment="e",
        required_generation=1,
    )
    assert state == enums.COMPATIBILITY_CURRENT
    assert checks[0]["outcome"] == "pass"


def test_stale_evidence_is_labelled_stale():
    state, _ = evidence.classify(
        evidence=_evidence(observed_offset=-1000, max_age=1),
        target="t",
        input_hash="a" * 64,
        environment="e",
        required_generation=1,
    )
    assert state == enums.COMPATIBILITY_STALE


def test_mismatched_and_missing_evidence_are_distinguished():
    mismatched, _ = evidence.classify(
        evidence=_evidence(target="other"),
        target="t",
        input_hash="a" * 64,
        environment="e",
        required_generation=1,
    )
    missing, checks = evidence.classify(
        evidence=None,
        target="t",
        input_hash="a" * 64,
        environment="e",
        required_generation=1,
    )
    assert mismatched == enums.COMPATIBILITY_MISMATCHED
    assert missing == enums.COMPATIBILITY_MISSING
    assert checks[0]["outcome"] == "unknown"


def test_missing_evidence_never_silently_substitutes_healthy_values():
    projected = evidence.to_wire_evidence(
        evidence=None,
        target="t",
        input_hash="a" * 64,
        required_generation=3,
        internal=enums.COMPATIBILITY_MISSING,
        checks=[{"name": "observation", "outcome": "unknown", "evidenceRef": "evidence:none"}],
    )
    assert projected["compatibility"] == "unknown"
    assert projected["evidenceId"] == "evidence:none"
    assert projected["generation"] == "3"
