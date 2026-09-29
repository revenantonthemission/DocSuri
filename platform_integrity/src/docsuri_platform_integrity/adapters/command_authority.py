"""Current operator-source authorization for run/reconcile, separate from mutation approval."""

import math
import time
from types import MappingProxyType

from ..contracts.models import ApprovalBinding, CommandContext, RunRecord
from .authority import MutationUnavailable
from .operator_authority import check_source, read_source


class PostgresCommandAuthority:
    def __init__(
        self, connection_factory, bindings: dict[str, ApprovalBinding], *, actor_role: str,
        clock, deadline: float,
    ):
        if (
            set(bindings) != {"run", "reconcile"}
            or any(binding.purpose != purpose for purpose, binding in bindings.items())
            or not actor_role or not math.isfinite(deadline)
        ):
            raise ValueError("separate run and reconcile source grants required")
        self._connect = connection_factory
        self.bindings = MappingProxyType(dict(bindings))
        self.actor_role, self.clock, self.deadline = actor_role, clock, deadline

    def __call__(self, context: CommandContext, run: RunRecord) -> None:
        from psycopg.pq import TransactionStatus

        binding = self.bindings.get(context.purpose)
        if binding is None or (
            context.actor, run.plan.target, run.intent.plan,
            run.plan.artifact_digest, run.plan.policy_digest,
        ) != (binding.actor, binding.target, binding.plan, binding.artifact, binding.policy):
            raise MutationUnavailable("control command differs from approved scope")
        remaining = int((self.deadline - time.monotonic()) * 1000)
        if remaining <= 0:
            raise MutationUnavailable("control authority deadline expired")
        connection = self._connect()
        try:
            if (
                not connection.autocommit
                or connection.info.transaction_status != TransactionStatus.IDLE
            ):
                raise MutationUnavailable("dedicated idle authority connection required")
            connection.execute("SELECT set_config('statement_timeout',%s,false)",
                               (str(min(2000, remaining)),))
            with connection.transaction():
                connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                if connection.execute("SELECT session_user").fetchone()[0] != self.actor_role:
                    raise MutationUnavailable("native control caller role mismatch")
                row = read_source(connection, binding.approval_id)
                check_source(binding, row, self.clock, purpose=context.purpose)
            if time.monotonic() >= self.deadline:
                raise MutationUnavailable("control authority deadline expired")
        finally:
            connection.close()
