"""U7 stable error vocabulary and the guarded-store SQLSTATE mapping.

C10 fixes the operator error vocabulary; the CLI never invents a code. The
guarded functions raise failures with a small set of SQLSTATEs that map onto
that vocabulary, so a database denial and a CLI-level refusal share one
projection.
"""

from __future__ import annotations

from typing import Any

# C10's stable operator error vocabulary.
INVALID_INPUT = "INVALID_INPUT"
UNAUTHENTICATED = "UNAUTHENTICATED"
FORBIDDEN = "FORBIDDEN"
NOT_FOUND = "NOT_FOUND"
CONFLICT = "CONFLICT"
POLICY_UNRESOLVED = "POLICY_UNRESOLVED"
DEPENDENCY_UNAVAILABLE = "DEPENDENCY_UNAVAILABLE"
UNKNOWN_OUTCOME = "UNKNOWN_OUTCOME"

WIRE_ERROR_CODES = (
    INVALID_INPUT,
    UNAUTHENTICATED,
    FORBIDDEN,
    NOT_FOUND,
    CONFLICT,
    POLICY_UNRESOLVED,
    DEPENDENCY_UNAVAILABLE,
    UNKNOWN_OUTCOME,
)

# Guard-function SQLSTATEs. Standard codes cover privilege/constraint failures;
# U7xxx codes carry the U7-specific semantic so the mapping stays unambiguous.
SQLSTATE_FORBIDDEN = "42501"
SQLSTATE_UNIQUE = "23505"
SQLSTATE_FK_VIOLATION = "23503"
SQLSTATE_NO_DATA = "02000"
SQLSTATE_INVALID_PARAMETER = "22023"
SQLSTATE_PREREQUISITE = "55000"
SQLSTATE_SERIALIZATION = "40001"
SQLSTATE_POLICY_UNRESOLVED = "U7001"
SQLSTATE_PRECONDITION_CONFLICT = "U7002"
SQLSTATE_BAD_INPUT = "U7003"
SQLSTATE_MISSING = "U7004"
SQLSTATE_INDETERMINATE = "U7005"

_SQLSTATE_TO_CODE = {
    SQLSTATE_FORBIDDEN: FORBIDDEN,
    SQLSTATE_UNIQUE: CONFLICT,
    SQLSTATE_FK_VIOLATION: NOT_FOUND,
    SQLSTATE_NO_DATA: NOT_FOUND,
    SQLSTATE_INVALID_PARAMETER: INVALID_INPUT,
    SQLSTATE_PREREQUISITE: CONFLICT,
    SQLSTATE_SERIALIZATION: CONFLICT,
    SQLSTATE_POLICY_UNRESOLVED: POLICY_UNRESOLVED,
    SQLSTATE_PRECONDITION_CONFLICT: CONFLICT,
    SQLSTATE_BAD_INPUT: INVALID_INPUT,
    SQLSTATE_MISSING: NOT_FOUND,
    SQLSTATE_INDETERMINATE: UNKNOWN_OUTCOME,
}


class ControlError(Exception):
    """A bounded U7 refusal carrying a C10 error code; never a silent failure."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        request_id: str | None = None,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        if code not in WIRE_ERROR_CODES:
            raise ValueError(f"error code outside the C10 vocabulary: {code!r}")
        super().__init__(message)
        self.code = code
        self.message = message
        self.request_id = request_id
        self.retryable = retryable
        self.details = details or {}

    def as_wire_error(self) -> dict[str, Any]:
        """Project onto C10's ``Error`` shape (code/requestId/retryable/messageKey)."""
        field_names = sorted(self.details.get("fieldNames", []))
        return {
            "code": self.code,
            "requestId": self.request_id or "unknown",
            "retryable": self.retryable,
            "messageKey": self.details.get("messageKey", self.code.lower()),
            "details": {"fieldNames": field_names},
        }


def code_for_sqlstate(sqlstate: str | None) -> str:
    """Map a guarded-store SQLSTATE onto the C10 vocabulary."""
    if sqlstate is None:
        return DEPENDENCY_UNAVAILABLE
    return _SQLSTATE_TO_CODE.get(sqlstate, DEPENDENCY_UNAVAILABLE)
