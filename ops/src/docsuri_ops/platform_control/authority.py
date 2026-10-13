"""Independent operator authority: local actor identity and admission logic.

The actor is always the verified local OS user, never a value the caller
supplies. Application-administrator status is never operator authority, and a
routine grant can never cover a destructive-release effect. The same admission
logic is enforced in the guarded-store SQL; this module is the pre-flight and
component-testable projection of it.
"""

from __future__ import annotations

import getpass
import re
from dataclasses import dataclass, field

from . import enums
from .errors import FORBIDDEN, INVALID_INPUT, ControlError

TARGET_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_WILDCARDS = {"*", "all", "any", "%"}


def local_actor() -> str:
    """The server-derived actor: the verified local OS user identity."""
    try:
        actor = getpass.getuser()
    except (KeyError, OSError):
        actor = ""
    if not actor or len(actor) > 128:
        raise ControlError(FORBIDDEN, "no verified local operator identity")
    return actor


@dataclass(frozen=True)
class Grant:
    authority_id: str
    actor_reference: str
    target_scope: tuple[str, ...] = field(default_factory=tuple)
    permitted_operation: tuple[str, ...] = field(default_factory=tuple)
    authority_class: str = enums.CLASS_ROUTINE
    revocation: str = "active"


def explicit_scope(scope: list[str]) -> tuple[str, ...]:
    """BR2.3: an explicit, non-empty target scope; wildcard/implicit-all is invalid."""
    if not scope:
        raise ControlError(INVALID_INPUT, "authority scope must be non-empty")
    for target in scope:
        invalid = (
            not isinstance(target, str)
            or target in _WILDCARDS
            or not TARGET_PATTERN.fullmatch(target)
        )
        if invalid:
            raise ControlError(
                INVALID_INPUT, "authority scope contains a wildcard or invalid target"
            )
    return tuple(scope)


def authority_admits(
    grant: Grant,
    *,
    actor: str,
    operation: str,
    target: str,
    requested_class: str,
    execute: bool,
) -> None:
    """Raise FORBIDDEN unless the grant admits this actor/operation/target."""
    if grant.revocation != "active":
        raise ControlError(FORBIDDEN, "authority is revoked")
    if grant.actor_reference != actor:
        raise ControlError(FORBIDDEN, "authority actor mismatch")
    if target not in grant.target_scope:
        raise ControlError(FORBIDDEN, "target outside authority scope")
    if execute:
        if grant.authority_class not in (enums.CLASS_ROUTINE, enums.CLASS_DESTRUCTIVE):
            raise ControlError(FORBIDDEN, "evidence-reader grant cannot authorize an effect")
        if grant.authority_class != requested_class:
            raise ControlError(FORBIDDEN, "authority class does not cover the operation")
        if operation not in grant.permitted_operation:
            raise ControlError(FORBIDDEN, "operation outside authority scope")
