"""Allowlisted observation projection. Error text is never an observation field."""

from ..contracts.models import SafeObservation

REASONS = frozenset({
    "ready", "unavailable", "denied", "busy", "deadline", "invalid_input", "effect_unknown",
    "evidence_stale", "verification_failed", "backup_incomplete", "audit_unavailable",
})


def safe_observation(
    *, event_time, time_quality, role, correlation, reason, started_ns=None, ended_ns=None
):
    if reason not in REASONS:
        reason = "unavailable"
    duration = None
    if (
        type(started_ns) is int and type(ended_ns) is int
        and 0 <= started_ns <= ended_ns and ended_ns - started_ns <= (2**53 - 1) * 1_000_000
    ):
        duration = (ended_ns - started_ns) // 1_000_000
    return SafeObservation(
        event_time=event_time, time_quality=time_quality,
        level="info" if reason == "ready" else "warning", code=reason, role=role,
        correlation=correlation, duration_ms=duration,
    )


def health_projection(
    *, alive: bool, dependencies: dict[str, bool | None], subject_eligible: bool | None
):
    # Empty or unknown dependency evidence must never imply service readiness.
    ready = (
        alive is True and bool(dependencies)
        and all(value is True for value in dependencies.values())
    )
    return {"alive": alive, "ready": ready, "subjectEligible": subject_eligible}
