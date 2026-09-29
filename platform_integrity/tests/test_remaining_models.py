"""Independent readiness oracles for registry, compatibility and observation projections."""

from dataclasses import replace

import pytest
from hypothesis import given
from hypothesis import strategies as st

from docsuri_platform_integrity.contracts.codec import canonical, digest
from docsuri_platform_integrity.contracts.models import (
    Assurance,
    CompatibilityManifest,
    GateVerdict,
    LedgerObservation,
    MigrationSatisfaction,
    MigrationSpec,
    TargetRef,
)
from docsuri_platform_integrity.domain.compatibility import (
    CompatibilityPolicy,
    RuntimeObservation,
    evaluate_compatibility,
)
from docsuri_platform_integrity.domain.observation import health_projection, safe_observation
from docsuri_platform_integrity.domain.registry import assess_registry, validate_registry

D = digest(b"fixture")
TARGET = TargetRef(target_id="db", namespace="public", incarnation="test-1")
SPECS = (
    MigrationSpec(owner="a", local_id="one", path="a/one.sql", digest=D, order=1),
    MigrationSpec(
        owner="a", local_id="two", path="a/two.sql", digest=D, order=2, prerequisites=("a:one",)
    ),
)


def assess(observation, **kwargs):
    return assess_registry(
        SPECS, observation, target=TARGET, required_capabilities=frozenset({"schema-v1"}),
        capabilities=frozenset({"schema-v1"}), **kwargs,
    )


def proof(identity, assurance=Assurance.VERIFIED):
    return MigrationSatisfaction(target=TARGET, migration_id=identity, definition_digest=D,
                                 assurance=assurance, receipt="native-receipt")


def test_missing_ledger_never_proves_empty_target_or_readiness():
    missing = LedgerObservation(target=TARGET, state="ABSENT")
    assert not assess(missing).ready
    assert "fresh_target_unproven" in assess(missing).reasons
    assert not assess(missing, fresh_confirmed=True).ready


def test_adoption_and_missing_prerequisite_keep_their_assurance():
    observed = LedgerObservation(target=TARGET, state="AVAILABLE", proofs=(proof("a:two"),))
    assert "satisfied_step_has_missing_prerequisite" in assess(observed).reasons
    observed = observed.model_copy(update={
        "proofs": (proof("a:one", Assurance.ADOPTED), proof("a:two"))
    })
    assert not assess(observed).ready
    accepted = assess(observed, allow_adopted=True)
    assert accepted.ready and dict(accepted.states)["a:one"] == "ADOPTED_BASELINE"


@given(st.permutations((0, 1, 2)))
def test_conflicting_history_is_order_independent(order):
    claims = (
        proof("a:one"), proof("a:one").model_copy(update={"definition_digest": digest(b"changed")}),
        proof("a:two"),
    )
    before = LedgerObservation(target=TARGET, state="AVAILABLE", proofs=claims)
    after = before.model_copy(update={"proofs": tuple(claims[index] for index in order)})
    assert assess(before) == assess(after)
    assert not assess(after).ready


def test_registry_path_and_identity_aliases_are_rejected():
    for replacement in ({"path": "a//one.sql"}, {"owner": "a:b"}, {"local_id": "x:y"}):
        with pytest.raises(ValueError):
            validate_registry((SPECS[0].model_copy(update=replacement),))


def test_compatibility_requires_supported_exact_role_and_runtime_state():
    manifest = CompatibilityManifest(artifact=D, registry=D, generation=D,
                                     operations=("read-v1",), required_capabilities=("control-v1",))
    policy = CompatibilityPolicy(frozenset({digest(canonical(manifest.model_dump(mode="json")))}),
                                 "1", (("control", "1"),), (("reader", D),), D)
    observed = RuntimeObservation(D, D, D, frozenset({"read-v1"}), frozenset({"control-v1"}),
                                  "1", (("control", "1"),), (("reader", D),), D)
    assert evaluate_compatibility(manifest, policy, observed)[0] == GateVerdict.ELIGIBLE
    assert evaluate_compatibility(manifest, policy, None)[0] == GateVerdict.INCOMPLETE
    changed_epoch = evaluate_compatibility(manifest, policy, replace(observed, writer_epoch="2"))
    changed_generation = evaluate_compatibility(
        manifest, policy, replace(observed, generation=digest(b"new"))
    )
    assert changed_epoch[0] == GateVerdict.BLOCKED
    assert changed_generation[0] == GateVerdict.STALE


@given(st.text(max_size=100), st.integers(-100, 100))
def test_safe_observation_never_copies_private_error_text(secret, elapsed):
    value = safe_observation(event_time="100", time_quality="unknown", role="reader",
                             correlation="request-1", reason="PRIVATE:" + secret,
                             started_ns=100, ended_ns=elapsed)
    assert value.code == "unavailable" and "PRIVATE:" not in value.model_dump_json()
    assert value.duration_ms is None or value.duration_ms >= 0


def test_liveness_does_not_promote_subject_or_empty_dependency_checks():
    assert health_projection(alive=True, dependencies={}, subject_eligible=False) == {
        "alive": True, "ready": False, "subjectEligible": False,
    }
    stopped = health_projection(alive=False, dependencies={"db": True}, subject_eligible=None)
    assert not stopped["ready"]
