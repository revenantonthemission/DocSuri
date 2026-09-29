"""Operator-source authority on the target PostgreSQL connection.

This adapter serializes source grant/target-fence changes with finalization. A protected
authenticated clock provider and native role provisioning are mandatory dependencies.
It is not an alternate login, a stored-approval bearer token, or a production-ready default.
"""

import time
from contextlib import contextmanager
from datetime import UTC, datetime

from ..contracts.models import ApprovalBinding, TargetFence
from .authority import MutationUnavailable, check_binding


def _instant(value: datetime) -> int:
    if value.tzinfo is None:
        raise MutationUnavailable("authority timestamp has no timezone")
    delta = value.astimezone(UTC) - datetime(1970, 1, 1, tzinfo=UTC)
    return (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds


def read_source(connection, approval_id: str, *, finalizing: bool = False):
    """The scoped native port owns login mapping and SHARE-lock privileges."""
    import psycopg

    try:
        return connection.execute(
            "SELECT * FROM r1_control.read_operator_authority(%s,%s)",
            (approval_id, finalizing),
        ).fetchone()
    except psycopg.Error as error:
        if error.sqlstate == "R1T02":
            raise MutationUnavailable("current operator authority rejected") from error
        raise


def check_source(binding: ApprovalBinding, row, clock, *, purpose: str) -> tuple[int, int]:
    if row is None or row[9] is None or row[6] is None or row[7] is None:
        raise MutationUnavailable("current operator authority is unproven")
    # No wall-clock/DB-time fallback and no sliding refresh of the source grant.
    lower, upper = clock()
    if type(lower) is not int or type(upper) is not int or not 0 <= lower <= upper < 2**64:
        raise MutationUnavailable("authenticated clock window invalid")
    if row[:8] != (
        binding.actor, binding.purpose, binding.target.target_id, binding.target.namespace,
        binding.target.incarnation, binding.plan, binding.artifact, binding.policy,
    ) or not _instant(row[9]) <= lower <= upper < _instant(row[10]):
        raise MutationUnavailable("operator authority scope or target changed")
    check_binding(
        binding, target=binding.target, plan=binding.plan, artifact=binding.artifact,
        policy=binding.policy, revision=str(row[8]), lower=lower, upper=upper,
        revoked=row[11], purpose=purpose,
    )
    return lower, upper


class PostgresOperatorAuthority:
    def __init__(
        self, binding: ApprovalBinding, fence: TargetFence, *, actor_role: str,
        definitions: dict[str, str], clock, deadline: float,
    ):
        self.binding = binding
        self.fence = fence
        self.actor_role = actor_role
        self.definitions = dict(definitions)
        self.clock = clock
        self.deadline = deadline

    def _current(self, connection, *, purpose: str, finalizing=False):
        if time.monotonic() >= self.deadline:
            raise MutationUnavailable("operator attempt deadline expired")
        if connection.execute("SELECT session_user").fetchone()[0] != self.actor_role:
            raise MutationUnavailable("native caller role mismatch")
        row = read_source(connection, self.binding.approval_id, finalizing=finalizing)
        lower, upper = check_source(self.binding, row, self.clock, purpose=purpose)
        if (
            row[12:] != (self.fence.target.incarnation, int(self.fence.epoch))
            or self.binding.target != self.fence.target
            or not self.fence.validity.contains(lower, upper)
        ):
            raise MutationUnavailable("operator authority scope or target changed")
        if time.monotonic() >= self.deadline:
            raise MutationUnavailable("operator finalization deadline expired")
        return lower, upper

    @contextmanager
    def guard(self, connection, identity, definition_digest):
        from psycopg.pq import TransactionStatus

        if (
            not connection.autocommit
            or connection.info.transaction_status != TransactionStatus.IDLE
        ):
            raise MutationUnavailable("dedicated idle autocommit connection required")
        if self.definitions.get(identity) != definition_digest:
            raise MutationUnavailable("effect is outside the frozen operator plan")
        purpose = "adopt" if identity == "registry:adopt" else "apply"
        self._current(connection, purpose=purpose)
        finalized = False
        authority = self

        class Finalization:
            def before_commit(self):
                nonlocal finalized
                if connection.info.transaction_status != TransactionStatus.INTRANS:
                    raise MutationUnavailable("finalization requires the target transaction")
                window = authority._current(connection, purpose=purpose, finalizing=True)
                finalized = True
                return window

        yield Finalization()
        if not finalized or connection.info.transaction_status != TransactionStatus.IDLE:
            raise MutationUnavailable("native finalization boundary was not entered")


def revoke_operator_grant(connection, approval_id: str):
    """Source-owner transaction; its UPDATE serializes with the finalizer's short SHARE lock."""
    from psycopg.types.json import Jsonb

    from ..contracts.codec import canonical, digest

    with connection.transaction():
        row = connection.execute(
            "UPDATE r1_control.authority SET revoked=true,revision=revision+1 WHERE binding_id=%s "
            "RETURNING revision", (approval_id,),
        ).fetchone()
        if row is None:
            raise MutationUnavailable("operator grant not found")
        actor = connection.execute("SELECT session_user").fetchone()[0]
        payload = {"code": "operator_grant_revoked", "approval": approval_id,
                   "revision": str(row[0]), "actorRole": actor}
        event = digest(canonical(payload))
        connection.execute(
            "INSERT INTO r1_audit.events(event_id,payload,digest) VALUES (%s,%s,%s)",
            (event, Jsonb(payload), event),
        )
        connection.execute("INSERT INTO r1_control.outbox(event_id) VALUES (%s)", (event,))
