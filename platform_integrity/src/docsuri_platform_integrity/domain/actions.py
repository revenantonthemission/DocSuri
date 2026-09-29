"""The closed R1R action and role vocabulary.

The helper never accepts a shell string, a free-form path, SQL text or a signing request. Every
request is a name drawn from a closed set, and every action is a name drawn from a closed set, so
"run this command" and "sign this blob" are not representable at the boundary at all.

This module is pure: it decides what is permitted. Provisioning, authority and I/O live elsewhere.
"""

ACTIONS = ("check", "plan", "verify", "apply", "reconcile", "backup")
ROLES = ("generator", "scanner", "publisher", "signer", "auditor", "backup", "reader")

# Least privilege. Each role receives only what its own duty needs; no role holds the union.
ROLE_ACTIONS: dict[str, frozenset[str]] = {
    "generator": frozenset({"check", "plan"}),
    "scanner": frozenset({"check", "verify"}),
    "publisher": frozenset({"check", "plan", "apply"}),
    "signer": frozenset({"check", "verify"}),
    "auditor": frozenset({"check", "reconcile"}),
    "backup": frozenset({"check", "backup"}),
    "reader": frozenset({"check"}),
}

# Every action the helper can perform, including the five readonly ones.
READONLY_ACTIONS = frozenset({"check", "plan", "verify", "reconcile", "backup"})

# Requests are names, not payloads. Anything outside these vocabularies is unrepresentable.
REQUEST_KINDS = ("schema", "audit", "capabilities", "generation", "target", "receipt")
REQUESTS: dict[str, frozenset[str]] = {
    "schema": frozenset({"closure", "drift"}),
    "audit": frozenset({"supply-chain"}),
    "capabilities": frozenset({"report"}),
    "generation": frozenset({"current", "verify"}),
    "target": frozenset({"reconcile"}),
    "receipt": frozenset({"verify"}),
}

# Naming a request family requires holding the action that family belongs to. Naming a
# generation is a read of publication state, so it is the `check` duty, not `verify`.
REQUEST_ACTION: dict[str, str] = {
    "schema": "check",
    "capabilities": "check",
    "generation": "check",
    "audit": "verify",
    "receipt": "verify",
    "target": "reconcile",
}

# Categories that are refused unconditionally, named here so a rejection can be reported
# without echoing the offending value back to the caller.
FORBIDDEN_REQUEST_KINDS = ("shell", "path", "sql", "sign", "exec", "argv")

NON_SUCCESS = ("BLOCKED", "INCOMPLETE", "REFUSED")


def authorize(role: str, action: str) -> str:
    """Return the action when the role may perform it, otherwise refuse by name."""
    if role not in ROLES:
        raise PermissionError("unknown role")
    if action not in ACTIONS:
        raise ValueError("unknown action")
    if action not in ROLE_ACTIONS[role]:
        raise PermissionError(f"role {role} may not {action}")
    return action


def resolve_request(role: str, kind: str, name: str) -> tuple[str, str]:
    """Validate a named request for a role. A forbidden kind never reaches a lookup."""
    if kind in FORBIDDEN_REQUEST_KINDS:
        raise PermissionError("request kind is never accepted")
    if kind not in REQUEST_KINDS:
        raise ValueError("unknown request kind")
    if name not in REQUESTS[kind]:
        raise ValueError("unknown request")
    if kind in REQUEST_ACTION and REQUEST_ACTION[kind] not in ROLE_ACTIONS[role]:
        # A role may only name a request family whose action it also holds.
        raise PermissionError("role may not request this family")
    return kind, name


def is_readonly(action: str) -> bool:
    if action not in ACTIONS:
        raise ValueError("unknown action")
    return action in READONLY_ACTIONS


def non_success(state: str, reason: str, **extra) -> dict:
    """A machine-readable failure. There is no partial-PASS representation."""
    if state not in NON_SUCCESS:
        raise ValueError("non-success state required")
    return {"state": state, "reason": reason, **extra}
