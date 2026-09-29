import json

import pytest
from evidence_support import verified_context
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule

from docsuri_platform_integrity.contracts.codec import canonical, decode, digest
from docsuri_platform_integrity.contracts.models import (
    EffectAssurance,
    EffectCheckpoint,
    EvidenceHeadSelection,
    Finding,
    GateVerdict,
    ReachabilityException,
    SubjectSnapshot,
    ValidityWindow,
    VerificationAttestation,
)
from docsuri_platform_integrity.domain.bindings import validate_catalog
from docsuri_platform_integrity.domain.gate import evaluate
from docsuri_platform_integrity.domain.run import transition
from docsuri_platform_integrity.domain.supply_chain import exception_matches, normalize

D = digest(b"pinned")
SUBJECT = SubjectSnapshot(subject="r1", artifact=D, incarnation="install-1", policy=D)


class EffectHistory(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.checkpoint = EffectCheckpoint(
            run_id="r", step="s", sequence="0", assurance=EffectAssurance.NOT_STARTED
        )
        self.commits = 0

    @rule(choice=st.sampled_from(list(EffectAssurance)))
    def apply(self, choice):
        before = self.checkpoint
        try:
            self.checkpoint = transition(
                before, choice,
                receipt=None if choice == EffectAssurance.UNKNOWN else "native-receipt",
            )
        except ValueError:
            assert self.checkpoint == before
        else:
            self.commits += choice == EffectAssurance.COMMITTED
            assert int(self.checkpoint.sequence) == int(before.sequence) + 1

    @invariant()
    def no_duplicate_effect(self):
        assert self.commits <= 1


TestEffectHistory = EffectHistory.TestCase
TestEffectHistory.settings = settings.get_profile("stateful")


@given(st.lists(st.sampled_from(["GHSA-1", "GHSA-2", "CVE-3"]), max_size=50))
def test_finding_normalization_preserves_all_identities(ids):
    findings = tuple(
        Finding(advisory=i, occurrence="pkg@1", source="pypi", severity="high") for i in ids
    )
    assert {f.advisory for f in normalize(findings)} == set(ids)
    assert normalize(findings) == normalize(tuple(reversed(findings)))


@given(st.integers(min_value=0, max_value=500))
def test_exception_is_exact_and_expiry_exclusive(now):
    exception = ReachabilityException(
        exception_id="x",
        artifact=D,
        closure=D,
        advisory="CVE-1",
        occurrence="pkg@1",
        assumptions=D,
        policy=D,
        validity=ValidityWindow(valid_from="100", valid_until="200"),
        approver="operator",
    )
    finding = Finding(advisory="CVE-1", occurrence="pkg@1", severity="high", source="pypi")
    kwargs = dict(
        artifact=D,
        closure=D,
        assumptions=D,
        policy=D,
        lower=now,
        upper=now,
        authorized=True,
        revoked=False,
    )
    assert exception_matches(exception, finding, **kwargs) == (100 <= now < 200)
    assert not exception_matches(exception, finding, **{**kwargs, "revoked": True})
    assert not exception_matches(exception, finding, **{**kwargs, "closure": digest(b"other")})


@given(st.integers(min_value=1, max_value=30))
def test_local_recursive_graph_is_finite_and_missing_ref_rejected(count):
    docs = tuple(
        {"$id": f"https://schema.test/{i}", "$ref": f"https://schema.test/{(i + 1) % count}"}
        for i in range(count)
    )
    assert len(validate_catalog(docs)) == count
    with pytest.raises(ValueError):
        validate_catalog(({"$id": "https://schema.test/root", "$ref": "https://external.test/x"},))


@given(st.permutations(("schema", "sca", "migration")))
def test_gate_permutation_and_missing_slot_never_pass(slots):
    evidence = tuple(
        VerificationAttestation(
            evidence_id=f"e-{s}",
            subject=SUBJECT,
            slot=s,
            revision="1",
            verification_id=f"v-{s}",
            outcome="PASS",
            validity=ValidityWindow(valid_from="0", valid_until="200"),
        )
        for s in slots
    )
    heads = tuple(
        EvidenceHeadSelection(
            subject=SUBJECT, verification_id=f"v-{s}", slot=s, revision="1",
            state="RESOLVED", evidence_id=f"e-{s}",
        )
        for s in slots
    )
    current = verified_context(SUBJECT, evidence)
    result = evaluate(
        SUBJECT, slots, heads, evidence, lower=100, upper=100, trusted=True, current=current
    )
    assert result.verdict == GateVerdict.ELIGIBLE
    assert result == evaluate(
        SUBJECT, tuple(reversed(slots)), heads, evidence, lower=100, upper=100,
        trusted=True, current=current,
    )
    assert not evaluate(
        SUBJECT, slots, heads[1:], evidence, lower=100, upper=100, trusted=True, current=current
    ).eligible


@given(st.text(alphabet=st.characters(blacklist_categories=("Cs",)), max_size=100))
def test_unicode_roundtrip_preserves_source_text(text):
    source = {"text": text}
    assert decode(canonical(source)) == source
    assert json.loads(canonical(source)) == source
