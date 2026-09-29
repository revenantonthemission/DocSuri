"""Finding disposition and closure evaluation for the G1 gate.

The rule this module exists to enforce: a vulnerability cannot be made to disappear. Every finding
counted by a scanner stays counted; an exception changes a finding's *disposition*, never the total.
That is why ``accepted_risk`` is reported alongside rather than subtracted from the findings.

An acceptance must also be time-boxed and justified. An exception with no expiry is functionally a
suppression, so it is rejected at construction rather than quietly treated as a pass.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Literal

SEVERITIES = ("critical", "high", "medium", "low", "negligible", "unknown")
SEVERITY_ORDER = {name: index for index, name in enumerate(SEVERITIES)}
BLOCKING = ("critical", "high")
DISPOSITIONS = ("unresolved", "fixed", "accepted_risk")


class DispositionError(ValueError):
    """A disposition that cannot be honoured -- surfaced, never downgraded to a pass."""


@dataclass(frozen=True)
class Finding:
    """One scanner finding. ``count`` preserves occurrence multiplicity, not just distinct CVEs."""

    identifier: str
    severity: str
    count: int = 1
    artifact: str = ""

    def __post_init__(self) -> None:
        if self.severity not in SEVERITY_ORDER:
            raise DispositionError(f"unknown severity {self.severity!r}")
        if type(self.count) is not int or self.count < 1:
            raise DispositionError("a finding must occur at least once")

    @property
    def blocking(self) -> bool:
        return self.severity in BLOCKING


@dataclass(frozen=True)
class Acceptance:
    """A time-boxed, justified exception. Without both, this is a suppression and is refused."""

    justification: str
    expires: datetime
    approver: str

    def __post_init__(self) -> None:
        if not self.justification.strip():
            raise DispositionError("an acceptance requires a justification")
        if not self.approver.strip():
            raise DispositionError("an acceptance requires a named approver")
        if self.expires.tzinfo is None:
            raise DispositionError("an acceptance expiry must be timezone-aware")

    def expired(self, now: datetime) -> bool:
        return now >= self.expires

    def as_dict(self) -> dict:
        return {
            "justification": self.justification,
            "approver": self.approver,
            "expires": self.expires.isoformat(),
        }


@dataclass(frozen=True)
class Disposition:
    finding: Finding
    state: Literal["unresolved", "fixed", "accepted_risk"]
    acceptance: Acceptance | None = None
    note: str = ""

    def __post_init__(self) -> None:
        if self.state not in DISPOSITIONS:
            raise DispositionError(f"unknown disposition {self.state!r}")
        if self.state == "accepted_risk" and self.acceptance is None:
            raise DispositionError("accepted_risk requires an Acceptance")
        if self.state != "accepted_risk" and self.acceptance is not None:
            raise DispositionError("only accepted_risk may carry an Acceptance")


@dataclass
class ClosureReport:
    scanned: int
    findings: list[Finding] = field(default_factory=list)
    dispositions: list[Disposition] = field(default_factory=list)
    now: datetime | None = None
    extra_blockers: tuple[str, ...] = ()

    def _applicable(self) -> list[Disposition]:
        return self.dispositions

    def by_severity(self) -> dict[str, int]:
        """The scanner's occurrence totals, computed from the findings themselves.

        Deliberately not derived from the dispositions: if this were computed over the
        dispositioned subset, an unaccounted finding would shrink the total and become
        invisible, which is precisely the failure this module exists to prevent.
        """
        totals: dict[str, int] = {}
        for finding in self.findings:
            totals[finding.severity] = totals.get(finding.severity, 0) + finding.count
        return totals

    def dispositioned_by_severity(self) -> dict[str, int]:
        totals: dict[str, int] = {}
        for entry in self._applicable():
            severity = entry.finding.severity
            totals[severity] = totals.get(severity, 0) + entry.finding.count
        return totals

    def unaccounted(self) -> list[Finding]:
        """Findings with no recorded disposition, matched by identifier."""
        recorded = {d.finding.identifier for d in self._applicable()}
        return [f for f in self.findings if f.identifier not in recorded]

    def unresolved(self) -> list[Disposition]:
        return [d for d in self._applicable() if d.state == "unresolved"]

    def unresolved_blocking(self) -> list[Disposition]:
        return [d for d in self.unresolved() if d.finding.blocking]

    def lapsed_acceptances(self) -> list[Disposition]:
        if self.now is None:
            return []
        return [
            d for d in self._applicable()
            if d.state == "accepted_risk" and d.acceptance and d.acceptance.expired(self.now)
        ]

    def blockers(self) -> list[str]:
        reasons = []
        if self.unresolved_blocking():
            reasons.append("unresolved_blocking_findings")
        lapsed = self.lapsed_acceptances()
        if lapsed:
            reasons.append("expired_acceptances")
        if not self._applicable():
            reasons.append("no_dispositions_recorded")
        reasons.extend(self.extra_blockers)
        return reasons

    @property
    def closed(self) -> bool:
        return not self.blockers()

    def as_dict(self) -> dict:
        return {
            "g1": "BLOCKED" if not self.closed else "READY",
            "scanned": self.scanned,
            "severityTotals": self.by_severity(),
            "dispositionedTotals": self.dispositioned_by_severity(),
            "unaccounted": [f.identifier for f in self.unaccounted()],
            "dispositionTotals": {
                state: sum(d.finding.count for d in self._applicable() if d.state == state)
                for state in DISPOSITIONS
            },
            "unresolvedBlocking": [d.finding.identifier for d in self.unresolved_blocking()],
            "lapsedAcceptances": [d.finding.identifier for d in self.lapsed_acceptances()],
            "blockers": self.blockers(),
        }


def evaluate_closure(
    findings: Iterable[Finding],
    dispositions: Iterable[Disposition],
    *,
    scanned: int | None = None,
    now: datetime | None = None,
) -> ClosureReport:
    """Reconcile dispositions against the findings and decide whether G1 can proceed.

    ``scanned`` is the scanner's own occurrence total. If the dispositions do not account for every
    finding, the result is INCOMPLETE rather than a partial pass -- an unaccounted finding is
    exactly the one that would otherwise be invisible.
    """
    found = list(findings)
    recorded = list(dispositions)
    total = scanned if scanned is not None else sum(f.count for f in found)
    accounted = sum(d.finding.count for d in recorded)
    extra = () if accounted == total else ("disposition_count_mismatch",)
    return ClosureReport(
        scanned=total,
        findings=found,
        dispositions=recorded,
        now=now or datetime.now(UTC),
        extra_blockers=extra,
    )


def acceptance_for(days: int, *, justification: str, approver: str, now: datetime) -> Acceptance:
    if type(days) is not int or not 1 <= days <= 365:
        raise DispositionError("an acceptance must be for 1..365 days")
    return Acceptance(
        justification=justification, approver=approver, expires=now + timedelta(days=days)
    )
