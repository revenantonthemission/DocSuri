import pytest
from hypothesis import given
from hypothesis import strategies as st

from docsuri_platform_integrity.contracts.codec import canonical, digest
from docsuri_platform_integrity.contracts.models import (
    EffectAssurance,
    EffectCheckpoint,
    EvidenceHeadSelection,
    GateVerdict,
    MigrationSpec,
    SubjectSnapshot,
    ValidityWindow,
    VerificationAttestation,
)
from docsuri_platform_integrity.domain.gate import evaluate
from docsuri_platform_integrity.domain.registry import reconcile_legacy, validate_registry
from docsuri_platform_integrity.domain.run import transition
from docsuri_platform_integrity.domain.supply_chain import parse_pip_audit

D = digest(b"artifact")
SUBJECT = SubjectSnapshot(subject="r1", artifact=D, incarnation="i1", policy=D)


def test_scan_error_with_empty_findings_is_not_clean():
    with pytest.raises(ValueError):
        parse_pip_audit(
            {"dependencies": [], "error": "network"},
            returncode=1,
            expected={"pydantic": "2.13.5"},
            source="pypi",
        )


def test_required_slots_cannot_be_empty_or_old_pass_reused():
    assert evaluate(SUBJECT, (), (), (), lower=100, upper=100).verdict == GateVerdict.INCOMPLETE
    old = VerificationAttestation(
        evidence_id="e1",
        subject=SUBJECT,
        slot="sca",
        revision="1",
        outcome="PASS",
        validity=ValidityWindow(valid_from="0", valid_until="200"),
    )
    head = EvidenceHeadSelection(slot="sca", revision="2", state="PENDING")
    assert not evaluate(SUBJECT, ("sca",), (head,), (old,), lower=100, upper=100).eligible


@given(st.permutations(("accounts", "library", "evidence")))
def test_registry_order_is_independent_of_input_and_names_are_qualified(owners):
    specs = tuple(
        MigrationSpec(owner=owner, local_id="001", path=f"{owner}/001.sql", digest=D, order=i)
        for i, owner in enumerate(sorted(owners))
    )
    by_owner = {s.owner: s for s in specs}
    assert validate_registry(tuple(by_owner[o] for o in owners)) == specs
    assert len({s.identity for s in specs}) == 3


def test_registry_missing_dependency_and_cycle_rejected():
    a = MigrationSpec(
        owner="x", local_id="a", path="a.sql", digest=D, order=1, prerequisites=("x:b",)
    )
    b = MigrationSpec(
        owner="x", local_id="b", path="b.sql", digest=D, order=2, prerequisites=("x:a",)
    )
    with pytest.raises(ValueError):
        validate_registry((a,))
    with pytest.raises(ValueError):
        validate_registry((a, b))


def test_legacy_name_does_not_prove_historical_execution():
    a = MigrationSpec(owner="x", local_id="a", path="x/001.sql", digest=D, order=1)
    assert reconcile_legacy("001.sql", (a,)) == ("NEEDS_RECONCILIATION", ("x:a",))


def test_effect_must_pass_through_unknown_and_committed_is_terminal():
    current = EffectCheckpoint(
        run_id="r1", step="s1", sequence="0", assurance=EffectAssurance.NOT_STARTED
    )
    with pytest.raises(ValueError):
        transition(current, EffectAssurance.COMMITTED, receipt="receipt")
    current = transition(current, EffectAssurance.UNKNOWN)
    with pytest.raises(ValueError):
        transition(current, EffectAssurance.COMMITTED)
    current = transition(current, EffectAssurance.COMMITTED, receipt="receipt")
    with pytest.raises(ValueError):
        transition(current, EffectAssurance.UNKNOWN)


@given(
    st.dictionaries(
        st.from_regex(r"[a-z]{1,8}", fullmatch=True), st.integers(-100, 100), max_size=20
    )
)
def test_canonical_key_order_does_not_change_plan_identity(values):
    assert digest(canonical(values)) == digest(canonical(dict(reversed(list(values.items())))))
