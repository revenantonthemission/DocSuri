"""PROP-R1-14/15: current trust, exact exceptions and independent verification-head model."""

import pytest
from evidence_support import SUBJECT, D, request, result, selected, verified_context
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule

from docsuri_platform_integrity.contracts.codec import digest
from docsuri_platform_integrity.contracts.models import (
    CurrentException,
    Finding,
    GateVerdict,
    ReachabilityException,
    SubjectSnapshot,
    TargetRef,
    ValidityWindow,
)
from docsuri_platform_integrity.domain.gate import (
    evaluate,
    pending_selection,
    reserve_selection,
    resolve_selection,
)


def pass_record(**kwargs):
    return result(reserve_selection(request(), None, expected_revision="0"), **kwargs)


def assess(record, *, current=None, now=100):
    return evaluate(
        SUBJECT, (record.slot,), (selected(record),), (record,), lower=now, upper=now,
        trusted=True, current=current,
    )


@pytest.mark.parametrize("status,expected", [
    ("VERIFIED", GateVerdict.ELIGIBLE), ("UNKNOWN", GateVerdict.INCOMPLETE),
    ("REVOKED", GateVerdict.BLOCKED), ("INVALID", GateVerdict.BLOCKED),
])
def test_current_record_trust_is_required(status, expected):
    record = pass_record()
    context = verified_context(SUBJECT, (record,))
    context = context.model_copy(update={
        "checks": (context.checks[0].model_copy(update={"status": status}),)
    })
    assert assess(record, current=context).verdict == expected
    assert assess(record).verdict == GateVerdict.INCOMPLETE


def test_current_check_is_exact_body_bound_and_current_subject_is_not_cached():
    record = pass_record()
    context = verified_context(SUBJECT, (record,))
    changed = record.model_copy(update={"reasons": ("private-sentinel",)})
    assert assess(changed, current=context).verdict == GateVerdict.INCOMPLETE
    restored = context.model_copy(update={
        "subject": SUBJECT.model_copy(update={"incarnation": "restored"})
    })
    assert assess(record, current=restored).verdict == GateVerdict.STALE
    assert "private-sentinel" not in assess(changed, current=context).model_dump_json()


def test_same_target_incarnation_with_changed_state_invalidates_historical_pass():
    subject = SubjectSnapshot(
        subject="database", kind="target", artifact=D, incarnation="install-1", policy=D,
        target=TargetRef(target_id="db", namespace="public", incarnation="install-1"),
        state=digest(b"schema-before"),
    )
    record = result(reserve_selection(request(subject=subject), None, expected_revision="0"))
    current = verified_context(subject, (record,)).model_copy(update={
        "subject": subject.model_copy(update={"state": digest(b"schema-after")})
    })
    assert evaluate(
        subject, ("schema",), (selected(record),), (record,), lower=100, upper=100,
        trusted=True, current=current,
    ).verdict == GateVerdict.STALE


def test_mutable_subject_requires_target_identity_and_relevant_state():
    with pytest.raises(ValueError):
        SubjectSnapshot(
            subject="database", kind="target", artifact=D, incarnation="install-1", policy=D,
        )


def test_trust_expiry_boundary_is_checked_after_observation():
    record = pass_record()
    context = verified_context(SUBJECT, (record,))
    context = context.model_copy(update={"checks": (context.checks[0].model_copy(update={
        "trust_validity": ValidityWindow(valid_from="0", valid_until="101")
    }),)})
    assert assess(record, current=context, now=100).eligible
    assert assess(record, current=context, now=101).verdict == GateVerdict.STALE


@pytest.mark.parametrize("window", [(-1, 0), (2, 1), (True, True), (1.5, 2), (0, 2**64)])
def test_invalid_clock_window_cannot_promote_a_signed_pass(window):
    record = pass_record()
    outcome = evaluate(
        SUBJECT, ("schema",), (selected(record),), (record,), lower=window[0], upper=window[1],
        trusted=True, current=verified_context(SUBJECT, (record,)),
    )
    assert outcome.verdict == GateVerdict.INCOMPLETE and outcome.evaluation_window is None


def exception_observation():
    return CurrentException(
        exception=ReachabilityException(
            exception_id="exception-1", artifact=SUBJECT.artifact, closure=D, assumptions=D,
            policy=SUBJECT.policy, advisory="CVE-test", occurrence="pkg@1", approver="operator",
            validity=ValidityWindow(valid_from="0", valid_until="150"),
        ),
        finding=Finding(advisory="CVE-test", occurrence="pkg@1", severity="high", source="feed"),
        closure=D, assumptions=D, authorized=True, revoked=False,
    )


@pytest.mark.parametrize("change", ["revoked", "authorized", "closure", "assumptions"])
def test_exception_is_revalidated_without_removing_its_reference(change):
    record = pass_record(exceptions=("exception-1",), closure=D, assumptions=D)
    item = exception_observation()
    current = verified_context(SUBJECT, (record,), exceptions=(item,))
    assert assess(record, current=current).verdict == GateVerdict.EXCEPTIONS
    assert assess(record, current=current, now=150).verdict == GateVerdict.BLOCKED
    replacement = {"revoked": True, "authorized": False}.get(change, digest(b"new"))
    current = current.model_copy(update={
        "exceptions": (item.model_copy(update={change: replacement}),)
    })
    evaluated = assess(record, current=current)
    assert evaluated.verdict == GateVerdict.BLOCKED
    assert evaluated.exception_ids == ("exception-1",)
    assert not assess(record, current=verified_context(SUBJECT, (record,))).eligible


def test_all_reason_categories_are_retained_and_blocked_has_precedence():
    failed = result(
        reserve_selection(request("failed"), None, expected_revision="0"), outcome="FAIL"
    )
    pending = pending_selection(reserve_selection(
        request("pending", slot="sca"), None, expected_revision="0"
    ))
    old = result(reserve_selection(request("old", slot="binding"), None, expected_revision="0"))
    old = old.model_copy(update={"validity": ValidityWindow(valid_from="0", valid_until="50")})
    evaluated = evaluate(
        SUBJECT, ("schema", "sca", "binding"), (selected(failed), pending, selected(old)),
        (failed, old), lower=100, upper=100, trusted=True,
        current=verified_context(SUBJECT, (failed, old)),
    )
    assert evaluated.verdict == GateVerdict.BLOCKED
    assert set(evaluated.reasons) == {
        "verification_failed", "verification_pending", "evidence_or_trust_expired"
    }


def test_diagnostics_separate_long_slot_identity_from_safe_codes():
    slot = "s" * 200
    reservation = reserve_selection(request(slot=slot), None, expected_revision="0")
    evaluated = evaluate(
        SUBJECT, (slot,), (pending_selection(reservation),), (), lower=100, upper=100,
        trusted=True, current=verified_context(SUBJECT, ()),
    )
    assert evaluated.diagnostics[0].slot == slot
    assert evaluated.reasons == ("verification_pending",)


@given(st.permutations(("schema", "migration", "sca")))
def test_record_order_and_unrelated_history_do_not_change_the_evaluation_cut(slots):
    records = tuple(
        result(reserve_selection(request(slot, slot=slot), None, expected_revision="0"))
        for slot in slots
    )
    heads = tuple(selected(record) for record in records)
    current = verified_context(SUBJECT, records)
    first = evaluate(
        SUBJECT, slots, heads, records, lower=100, upper=100, trusted=True, current=current
    )
    history = pass_record().model_copy(update={"evidence_id": "unselected-history"})
    second = evaluate(
        SUBJECT, tuple(reversed(slots)), tuple(reversed(heads)), (history, *reversed(records)),
        lower=100, upper=100, trusted=True, current=verified_context(SUBJECT, (history, *records)),
    )
    assert first == second and first.input_fingerprint is not None


def test_same_verification_cannot_change_its_terminal_result_even_after_newer_recheck():
    first = reserve_selection(request("v1"), None, expected_revision="0")
    passed = result(first)
    head = resolve_selection(first, pending_selection(first), passed)
    second = reserve_selection(request("v2"), head, expected_revision="1")
    with pytest.raises(ValueError, match="conflict"):
        resolve_selection(
            first, pending_selection(second), passed.model_copy(update={"outcome": "FAIL"}),
            existing=passed,
        )


def test_result_cannot_be_recorded_against_another_subject_head():
    first = reserve_selection(request("v1"), None, expected_revision="0")
    other = selected(result(first)).model_copy(update={
        "subject": SUBJECT.model_copy(update={"subject": "different-subject"}), "revision": "2"
    })
    with pytest.raises(ValueError, match="scope"):
        resolve_selection(first, other, result(first))


class VerificationHistoryModel(RuleBasedStateMachine):
    """Independent oracle: the most recently RESERVED job alone determines the current slot."""

    def __init__(self):
        super().__init__()
        self.head = None
        self.jobs = {}
        self.published = {}
        self.latest = 0
        self.revoked = False

    @rule()
    def reserve(self):
        reservation = reserve_selection(
            request(f"job-{self.latest + 1}"), self.head, expected_revision=str(self.latest)
        )
        self.latest += 1
        self.jobs[self.latest] = reservation
        self.head = pending_selection(reservation)

    @rule(position=st.integers(0, 200), outcome=st.sampled_from(["PASS", "FAIL", "UNKNOWN"]))
    def complete(self, position, outcome):
        if not self.jobs:
            return
        job = position % len(self.jobs) + 1
        record = result(self.jobs[job], outcome=outcome)
        prior = self.published.get(job)
        if prior is not None and prior.outcome != outcome:
            with pytest.raises(ValueError):
                resolve_selection(self.jobs[job], self.head, record, existing=prior)
        else:
            self.head = resolve_selection(self.jobs[job], self.head, record, existing=prior)
            self.published[job] = record

    @rule(revoked=st.booleans())
    def key_trust_changes(self, revoked):
        self.revoked = revoked

    @invariant()
    def gate_matches_latest_reserved_job_not_latest_pass(self):
        current_record = self.published.get(self.latest)
        records = (current_record,) if current_record else ()
        current = verified_context(SUBJECT, records)
        if self.revoked:
            current = current.model_copy(update={"checks": tuple(
                check.model_copy(update={"status": "REVOKED"}) for check in current.checks
            )})
        evaluated = evaluate(
            SUBJECT, ("schema",), (self.head,) if self.head else (), records,
            lower=100, upper=100, trusted=True, current=current,
        )
        expected = GateVerdict.INCOMPLETE
        if current_record:
            expected = GateVerdict.BLOCKED if self.revoked else {
                "PASS": GateVerdict.ELIGIBLE, "FAIL": GateVerdict.BLOCKED,
                "UNKNOWN": GateVerdict.INCOMPLETE,
            }[current_record.outcome]
        assert evaluated.verdict == expected


TestVerificationHistoryModel = VerificationHistoryModel.TestCase
TestVerificationHistoryModel.settings = settings.get_profile("stateful")
