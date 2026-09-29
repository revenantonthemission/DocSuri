"""Retention, relay-cursor and correlation rules. Pure: no clock, no filesystem, no network.

Two invariants dominate:

* GC is approval-bound and bounded to records this system owns. A record that predates the
  managed set is never a candidate, so enabling retention cannot delete pre-existing operator
  logs or backups.
* A relay cursor only advances. A regression or a replay is refused rather than rewound, because
  a rewound cursor silently re-delivers or drops audit records.
"""

from pydantic import model_validator

from ..contracts.models import Ref, Value

ORDINARY_DAYS = 14
CRITICAL_DAYS = 90
CLASSIFICATIONS = ("ordinary", "critical")
DAY_US = 86_400 * 1_000_000


class RetentionPolicy(Value):
    ordinary_days: int = ORDINARY_DAYS
    critical_days: int = CRITICAL_DAYS

    @model_validator(mode="after")
    def bounded_windows(self):
        # Reject at configuration time, not on first use: an invalid policy must never be
        # constructible and then applied.
        for days in (self.ordinary_days, self.critical_days):
            if type(days) is not int or not 1 <= days <= 3650:
                raise ValueError("retention window out of range")
        if self.critical_days < self.ordinary_days:
            raise ValueError("critical retention must not be shorter than ordinary")
        return self

    def window_us(self, classification: str) -> int:
        if classification == "ordinary":
            days = self.ordinary_days
        elif classification == "critical":
            days = self.critical_days
        else:
            raise ValueError("unknown classification")
        return days * DAY_US


class Correlation(Value):
    """Request/run/effect nesting. An effect always names the run that produced it."""

    request: Ref
    run: Ref | None = None
    effect: Ref | None = None


def correlation_is_nested(correlation: Correlation) -> bool:
    if correlation.effect is not None and correlation.run is None:
        return False
    return True


def retention_deadline_us(classification: str, event_time_us: int, policy: RetentionPolicy) -> int:
    if type(event_time_us) is not int or event_time_us < 0:
        raise ValueError("invalid event time")
    return event_time_us + policy.window_us(classification)


def gc_decision(
    classification: str, event_time_us: int, now_us: int, policy: RetentionPolicy, *,
    managed: bool, approved: bool = False, writer_resolved: bool = True,
) -> bool:
    """True only when deleting this record is both permitted and safe right now."""
    if type(now_us) is not int or now_us < 0:
        raise ValueError("invalid now")
    if not managed:
        # Pre-existing logs and backups are outside this system's authority to delete.
        return False
    if not writer_resolved:
        # An unresolved writer could still be appending to this record.
        return False
    if classification == "critical" and not approved:
        # Critical retention is never automatic; it is approval-bound.
        return False
    if now_us < retention_deadline_us(classification, event_time_us, policy):
        return False
    return True


def advance_relay_cursor(current: int | None, sequence: int) -> int:
    """Advance to a strictly greater sequence. A replay or regression is refused."""
    if type(sequence) is not int or sequence < 0:
        raise ValueError("invalid relay sequence")
    if current is None:
        return sequence
    if type(current) is not int or current < 0:
        raise ValueError("invalid relay cursor")
    if sequence <= current:
        raise ValueError("relay cursor must advance")
    return sequence
