"""U7 internal state machines and their explicit projection onto C10 wire enums.

The functional design uses richer internal state names than the C10 wire
enums. The wire contract is the interface and is unchanged; internal states
project onto it (see ``tech-stack-decisions.md`` in the NFR requirements). This
module is the single place that mapping lives.
"""

from __future__ import annotations

# --- PlatformEvidence.compatibility (internal) ---
COMPATIBILITY_CURRENT = "current"
COMPATIBILITY_STALE = "stale"
COMPATIBILITY_MISMATCHED = "mismatched"
COMPATIBILITY_MISSING = "missing"
COMPATIBILITIES = (
    COMPATIBILITY_CURRENT,
    COMPATIBILITY_STALE,
    COMPATIBILITY_MISMATCHED,
    COMPATIBILITY_MISSING,
)

# --- ControlledOperation.state (internal) ---
STATE_AUTHORIZED = "authorized"
STATE_EXECUTING = "executing"
STATE_COMPLETED = "completed"
STATE_FAILED = "failed"
STATE_UNKNOWN = "unknown"
OPERATION_STATES = (
    STATE_AUTHORIZED,
    STATE_EXECUTING,
    STATE_COMPLETED,
    STATE_FAILED,
    STATE_UNKNOWN,
)
TERMINAL_STATES = (STATE_COMPLETED, STATE_FAILED, STATE_UNKNOWN)

# --- ControlledOperation.effectDisposition ---
DISPOSITION_NOT_APPLIED = "not-applied"
DISPOSITION_APPLIED = "applied"
DISPOSITION_UNKNOWN = "unknown"
EFFECT_DISPOSITIONS = (
    DISPOSITION_NOT_APPLIED,
    DISPOSITION_APPLIED,
    DISPOSITION_UNKNOWN,
)

# --- OperationReceipt.reconciliationState (internal; no wire field) ---
RECON_PENDING = "pending"
RECON_NOT_APPLICABLE = "not-applicable"
RECON_UNRESOLVED = "unresolved"
RECON_APPLIED = "reconciled-applied"
RECON_NOT_APPLIED = "reconciled-not-applied"
RECONCILIATION_STATES = (
    RECON_PENDING,
    RECON_NOT_APPLICABLE,
    RECON_UNRESOLVED,
    RECON_APPLIED,
    RECON_NOT_APPLIED,
)

# --- OperatorAuthority.authorityClass ---
CLASS_ROUTINE = "routine"
CLASS_DESTRUCTIVE = "destructive-release"
CLASS_READER = "evidence-reader"
AUTHORITY_CLASSES = (CLASS_ROUTINE, CLASS_DESTRUCTIVE, CLASS_READER)

# --- Protocol disposition ---
DISPOSITION_RETAINED = "retained-local"
DISPOSITION_COMPATIBILITY = "compatibility-dependent"
DISPOSITION_NOT_IMPLEMENTED = "not-implemented-under-0"
PROTOCOL_DISPOSITIONS = (
    DISPOSITION_RETAINED,
    DISPOSITION_COMPATIBILITY,
    DISPOSITION_NOT_IMPLEMENTED,
)

# --- Native effect kinds ---
EFFECT_FILE_WRITE = "file-write"
EFFECT_FILE_PROBE = "file-probe"
EFFECT_CREDENTIAL_PRESENCE = "credential-presence"
EFFECT_KINDS = (EFFECT_FILE_WRITE, EFFECT_FILE_PROBE, EFFECT_CREDENTIAL_PRESENCE)

_COMPATIBILITY_TO_WIRE = {
    COMPATIBILITY_CURRENT: "compatible",
    COMPATIBILITY_STALE: "incompatible",
    COMPATIBILITY_MISMATCHED: "incompatible",
    COMPATIBILITY_MISSING: "unknown",
}

_STATE_TO_WIRE = {
    STATE_AUTHORIZED: "accepted",
    STATE_EXECUTING: "running",
    STATE_COMPLETED: "succeeded",
    STATE_FAILED: "failed",
    STATE_UNKNOWN: "unknown",
}

_DISPOSITION_TO_CHECK = {
    DISPOSITION_APPLIED: "pass",
    DISPOSITION_NOT_APPLIED: "fail",
    DISPOSITION_UNKNOWN: "unknown",
}


def wire_compatibility(internal: str) -> str:
    """Project an internal evidence compatibility onto ``OperatorEvidence``."""
    try:
        return _COMPATIBILITY_TO_WIRE[internal]
    except KeyError as exc:  # pragma: no cover - guard against a typo upstream
        raise ValueError(f"unknown internal compatibility: {internal!r}") from exc


def wire_outcome(state: str) -> str:
    """Project a ``ControlledOperation.state`` onto ``OperatorReceipt.outcome``."""
    try:
        return _STATE_TO_WIRE[state]
    except KeyError as exc:  # pragma: no cover
        raise ValueError(f"unknown internal operation state: {state!r}") from exc


def wire_check_outcome(disposition: str) -> str:
    """Project an effect disposition onto an ``OperatorEvidence.checks[].outcome``."""
    try:
        return _DISPOSITION_TO_CHECK[disposition]
    except KeyError as exc:  # pragma: no cover
        raise ValueError(f"unknown effect disposition: {disposition!r}") from exc
