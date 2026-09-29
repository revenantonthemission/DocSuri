"""Resource and dependency observation for the native read load acceptance.

``load_acceptance.py`` measures latency and throughput, but it cannot decide whether the run is
acceptable on its own: the 512 MiB resident budget and the side-effect freedom of
``read``/``check``/``health`` are separate observations, and a latency pass must not be able to
substitute for them.

Two biases are deliberate:

* A peak that exceeds the budget fails the run, even if the average is comfortable. The budget is
  a ceiling, not a target.
* Side-effect freedom is checked by comparing observed state before and after. A probe that is
  unavailable reports unproven rather than clean.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

MIB = 1 << 20
DEFAULT_RSS_BUDGET = 512 * MIB
DEFAULT_LRU_BUDGET = 64 * MIB


@dataclass(frozen=True)
class RssBudget:
    total_bytes: int = DEFAULT_RSS_BUDGET
    lru_bytes: int = DEFAULT_LRU_BUDGET

    def __post_init__(self) -> None:
        for name in ("total_bytes", "lru_bytes"):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if self.lru_bytes > self.total_bytes:
            raise ValueError("the immutable LRU allowance cannot exceed the total budget")


@dataclass
class RssObservation:
    """Accumulates process-tree samples and judges them against the ceiling."""

    budget: RssBudget = field(default_factory=RssBudget)
    samples: int = 0
    peak_bytes: int = 0
    peak_pid: int | None = None
    over_budget: int = 0
    sample_failures: int = 0

    def observe(self, total_bytes: int, *, pid: int | None = None) -> None:
        if type(total_bytes) is not int or total_bytes < 0:
            self.sample_failures += 1
            return
        self.samples += 1
        if total_bytes > self.peak_bytes:
            self.peak_bytes, self.peak_pid = total_bytes, pid
        if total_bytes > self.budget.total_bytes:
            self.over_budget += 1

    @property
    def proven(self) -> bool:
        """Only a run that actually sampled is proven; zero samples is not a pass."""
        return self.samples > 0

    def within_budget(self) -> bool:
        return self.over_budget == 0

    def verdict(self) -> str:
        if self.sample_failures:
            return "INCOMPLETE"
        if not self.proven:
            return "INCOMPLETE"
        return "VERIFIED" if self.within_budget() else "OVER_BUDGET"

    def as_dict(self) -> dict:
        return {
            "verdict": self.verdict(),
            "samples": self.samples,
            "peakBytes": self.peak_bytes,
            "peakMiB": round(self.peak_bytes / MIB, 2),
            "peakPid": self.peak_pid,
            "budgetBytes": self.budget.total_bytes,
            "budgetMiB": self.budget.total_bytes // MIB,
            "lruAllowanceBytes": self.budget.lru_bytes,
            "samplesOverBudget": self.over_budget,
            "sampleFailures": self.sample_failures,
        }


class DependencyProbe(Protocol):
    """A side-effect probe. ``counts`` must be a snapshot of state that a read must not change."""

    def counts(self) -> dict[str, int]: ...


def verify_no_side_effects(
    probe: DependencyProbe, *, before: dict[str, int] | None = None
) -> dict:
    """Compare probe state across a window and report whether anything moved.

    Keys are compared as a whole: a probe that starts reporting a new key mid-run is treated as a
    change, because a read path that begins writing is precisely the failure being guarded.
    """
    try:
        start = dict(before) if before is not None else dict(probe.counts())
        end = dict(probe.counts())
    except Exception as error:  # a probe that cannot answer has proven nothing
        return {"state": "INCOMPLETE", "reason": f"probe_unavailable: {type(error).__name__}"}

    changed = {
        key: {"before": start.get(key), "after": end.get(key)}
        for key in set(start) | set(end)
        if start.get(key) != end.get(key)
    }
    if changed:
        return {"state": "CHANGED", "changed": changed}
    return {"state": "STABLE", "observed": start}


@dataclass
class LoadVerdict:
    """Combines the latency result with the resource and side-effect observations."""

    latency_state: str
    profile_complete: bool
    rss: RssObservation
    side_effects: dict
    dependency_observed: bool

    @property
    def passed(self) -> bool:
        # A latency pass cannot stand in for the resource or side-effect observations.
        return (
            self.latency_state == "MEASURED_PASS"
            and self.profile_complete
            and self.rss.verdict() == "VERIFIED"
            and self.dependency_observed
            and self.side_effects.get("state") == "STABLE"
        )

    def as_dict(self) -> dict:
        return {
            "state": "ACCEPTED" if self.passed else "BLOCKED",
            "latencyState": self.latency_state,
            "profileComplete": self.profile_complete,
            "rss": self.rss.as_dict(),
            "sideEffects": self.side_effects,
            "dependencyObserved": self.dependency_observed,
            "blockers": self._blockers(),
        }

    def _blockers(self) -> list[str]:
        blockers = []
        if self.latency_state != "MEASURED_PASS":
            blockers.append("latency_not_passed")
        if not self.profile_complete:
            blockers.append("profile_incomplete")
        if self.rss.verdict() != "VERIFIED":
            blockers.append(f"rss_{self.rss.verdict().lower()}")
        if not self.dependency_observed:
            blockers.append("dependency_unobserved")
        if self.side_effects.get("state") != "STABLE":
            blockers.append(f"side_effects_{str(self.side_effects.get('state')).lower()}")
        return blockers
