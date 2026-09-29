"""A vulnerability must not be made to disappear by the way it is dispositioned.

The tests below pin the properties that make the G1 gate trustworthy: acceptances never reduce a
severity total, an unjustified or permanent exception is refused outright, an expired exception
re-blocks, and an unaccounted finding blocks instead of passing as a partial review.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from docsuri_ops.finding_disposition import (
    Acceptance,
    ClosureReport,
    Disposition,
    DispositionError,
    Finding,
    acceptance_for,
    evaluate_closure,
)

NOW = datetime(2026, 9, 29, tzinfo=UTC)
# The shape actually recorded for the PostgreSQL image.
CRITICALS = [Finding("CVE-2026-CRIT-1", "critical", 2)]
HIGHS = [Finding("CVE-2026-HIGH-1", "high", 96)]


def acceptance(**overrides):
    kwargs = dict(
        justification="segmented at the host; no reachable path",
        approver="ops-lead",
        expires=NOW + timedelta(days=30),
    )
    kwargs.update(overrides)
    return Acceptance(**kwargs)


# -- finding shape ---------------------------------------------------------


def test_severity_totals_preserve_occurrence_multiplicity():
    report = evaluate_closure(CRITICALS + HIGHS, [], scanned=98, now=NOW)
    totals = report.by_severity()
    assert totals["critical"] == 2
    assert totals["high"] == 96


def test_an_unknown_severity_is_refused():
    with pytest.raises(DispositionError):
        Finding("CVE-X", "catastrophic")


def test_a_zero_occurrence_finding_is_refused():
    with pytest.raises(DispositionError):
        Finding("CVE-X", "high", 0)


# -- the core property: acceptance never reduces a total ------------------


def test_accepting_every_high_does_not_reduce_the_high_total():
    dispositions = [Disposition(f, "accepted_risk", acceptance()) for f in HIGHS]
    report = evaluate_closure(HIGHS, dispositions, scanned=96, now=NOW)
    assert report.by_severity()["high"] == 96
    assert report.as_dict()["dispositionTotals"]["accepted_risk"] == 96


def test_unresolved_blocking_findings_block_g1():
    dispositions = [Disposition(f, "unresolved") for f in CRITICALS + HIGHS]
    report = evaluate_closure(CRITICALS + HIGHS, dispositions, scanned=98, now=NOW)
    assert not report.closed
    assert report.as_dict()["g1"] == "BLOCKED"
    assert "unresolved_blocking_findings" in report.blockers()
    assert set(report.as_dict()["unresolvedBlocking"]) == {
        "CVE-2026-CRIT-1", "CVE-2026-HIGH-1"
    }


def test_a_fully_fixed_and_dated_closure_is_ready():
    dispositions = [
        Disposition(CRITICALS[0], "fixed"),
        *[Disposition(f, "accepted_risk", acceptance()) for f in HIGHS],
    ]
    report = evaluate_closure(CRITICALS + HIGHS, dispositions, scanned=98, now=NOW)
    assert report.closed
    assert report.as_dict()["g1"] == "READY"
    assert report.blockers() == []


# -- an exception must be justified, owned and time-boxed ------------------


@pytest.mark.parametrize(
    "kwargs",
    [
        {"justification": "  "},
        {"approver": ""},
        {"expires": datetime(2026, 12, 1)},  # naive
    ],
)
def test_an_unqualified_acceptance_is_refused(kwargs):
    with pytest.raises(DispositionError):
        acceptance(**kwargs)


def test_accepted_risk_without_an_acceptance_is_refused():
    with pytest.raises(DispositionError):
        Disposition(HIGHS[0], "accepted_risk")


def test_a_fixed_finding_may_not_carry_an_acceptance():
    with pytest.raises(DispositionError):
        Disposition(HIGHS[0], "fixed", acceptance())


def test_an_expired_acceptance_blocks_again():
    lapsed = acceptance(expires=NOW - timedelta(days=1))
    dispositions = [Disposition(f, "accepted_risk", lapsed) for f in HIGHS]
    report = evaluate_closure(HIGHS, dispositions, scanned=96, now=NOW)
    assert not report.closed
    assert "expired_acceptances" in report.blockers()
    assert report.as_dict()["lapsedAcceptances"] == ["CVE-2026-HIGH-1"]


def test_acceptance_for_bounds_the_window():
    with pytest.raises(DispositionError):
        acceptance_for(0, justification="x", approver="y", now=NOW)
    with pytest.raises(DispositionError):
        acceptance_for(400, justification="x", approver="y", now=NOW)
    window = acceptance_for(7, justification="x", approver="y", now=NOW)
    assert window.expires == NOW + timedelta(days=7)
    assert window.expired(NOW + timedelta(days=8))


# -- reconciliation --------------------------------------------------------


def test_an_unaccounted_finding_blocks_instead_of_passing_partially():
    """Dropping a disposition must not quietly shrink the review."""
    dispositions = [Disposition(CRITICALS[0], "fixed")]
    report = evaluate_closure(CRITICALS + HIGHS, dispositions, scanned=98, now=NOW)
    assert not report.closed
    assert "disposition_count_mismatch" in report.blockers()
    assert report.as_dict()["g1"] == "BLOCKED"
    # The severity totals still show every finding, and the gap is named explicitly.
    assert report.as_dict()["severityTotals"] == {"critical": 2, "high": 96}
    assert report.as_dict()["dispositionedTotals"] == {"critical": 2}
    assert report.as_dict()["unaccounted"] == ["CVE-2026-HIGH-1"]


def test_no_dispositions_at_all_blocks():
    report = evaluate_closure([], [], scanned=0, now=NOW)
    assert not report.closed
    assert "no_dispositions_recorded" in report.blockers()


def test_the_scanner_total_is_taken_from_the_scanner_when_given():
    report = evaluate_closure([], [], scanned=98, now=NOW)
    assert report.scanned == 98


def test_omitting_the_scanner_total_derives_it_from_the_findings():
    report = evaluate_closure(CRITICALS + HIGHS, [], now=NOW)
    assert report.scanned == 98


# -- report plumbing -------------------------------------------------------


def test_non_blocking_unresolved_findings_do_not_block():
    low = [Finding("CVE-LOW", "low", 3)]
    report = evaluate_closure(low, [Disposition(low[0], "unresolved")], scanned=3, now=NOW)
    assert report.closed
    assert report.as_dict()["unresolvedBlocking"] == []


def test_unknown_severity_findings_are_never_treated_as_blocking():
    unknown = [Finding("CVE-?", "unknown", 5)]
    report = evaluate_closure(unknown, [Disposition(unknown[0], "unresolved")], scanned=5, now=NOW)
    # Not blocking, but still counted and still unresolved, so the report cannot read as clean.
    assert report.closed
    assert report.by_severity()["unknown"] == 5
    assert report.as_dict()["dispositionTotals"]["unresolved"] == 5


def test_report_defaults_now_when_not_supplied():
    report = ClosureReport(scanned=1, dispositions=[])
    assert report.now is None
    assert ClosureReport(scanned=0, dispositions=[]).blockers()
