"""Platform evidence: classification and the projection onto C10's wire type.

Evidence is an input to a precondition only: it never grants authority and never
declares application readiness. Four states are always distinguished —
``current``, ``stale``, ``mismatched`` and ``missing`` — and none but ``current``
authorizes an effect.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from . import enums

NONE_SENTINEL = "evidence:none"


def parse_generation(value: Any) -> int:
    """The wire carries a decimal revision string; the store keeps an integer."""
    try:
        generation = int(str(value))
    except (TypeError, ValueError) as exc:
        from .errors import INVALID_INPUT, ControlError

        raise ControlError(INVALID_INPUT, "requiredGeneration is not a valid generation") from exc
    if generation < 1:
        from .errors import INVALID_INPUT, ControlError

        raise ControlError(INVALID_INPUT, "requiredGeneration must be a positive integer")
    return generation


def _check(name: str, outcome: str, reference: str) -> dict[str, str]:
    return {"name": name, "outcome": outcome, "evidenceRef": reference}


def classify(
    *,
    evidence: dict[str, Any] | None,
    target: str,
    input_hash: str,
    environment: str,
    required_generation: int,
    now: datetime | None = None,
) -> tuple[str, list[dict[str, str]]]:
    """Return (internal compatibility, wire checks) for one inspection."""
    moment = now or datetime.now(UTC)
    if evidence is None:
        return enums.COMPATIBILITY_MISSING, [_check("observation", "unknown", NONE_SENTINEL)]
    reference = str(evidence["evidenceId"])
    if (
        evidence["targetId"] != target
        or evidence["inputHash"] != input_hash
        or evidence["environmentBinding"] != environment
        or int(evidence["generation"]) != required_generation
    ):
        return enums.COMPATIBILITY_MISMATCHED, [_check("binding", "fail", reference)]
    observed_at = evidence["observedAt"]
    if isinstance(observed_at, str):
        observed_at = datetime.fromisoformat(observed_at)
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=UTC)
    window = int(evidence["maxAgeSeconds"])
    if (moment - observed_at).total_seconds() > window:
        return enums.COMPATIBILITY_STALE, [_check("staleness", "fail", reference)]
    return enums.COMPATIBILITY_CURRENT, [_check("binding", "pass", reference)]


def to_wire_evidence(
    *,
    evidence: dict[str, Any] | None,
    target: str,
    input_hash: str,
    required_generation: int,
    internal: str,
    checks: list[dict[str, str]],
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build an ``OperatorEvidence``; an absent observation stays honestly unknown."""
    moment = now or datetime.now(UTC)
    if evidence is None:
        evidence_id = NONE_SENTINEL
        generation = str(required_generation)
        observed_at = moment
    else:
        evidence_id = str(evidence["evidenceId"])
        generation = str(evidence["generation"])
        observed_at = evidence["observedAt"]
        if isinstance(observed_at, str):
            observed_at = datetime.fromisoformat(observed_at)
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=UTC)
    return {
        "evidenceId": evidence_id,
        "targetId": target,
        "inputHash": input_hash,
        "generation": generation,
        "observedAt": observed_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "compatibility": enums.wire_compatibility(internal),
        "checks": checks,
    }
