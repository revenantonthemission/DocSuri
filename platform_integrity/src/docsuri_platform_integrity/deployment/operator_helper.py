"""Protected operator-helper assembly; no ambient database, clock or authorization fallback."""

import math
import time

from ..adapters.command_authority import PostgresCommandAuthority
from ..adapters.nts import ProtectedClock
from ..adapters.operator_authority import PostgresOperatorAuthority
from ..adapters.postgres_tls import PostgresTLS
from ..adapters.scoped_run import ScopedPostgresRunStore
from ..adapters.target_effect import PostgresTargetExecutor
from ..application.dispatch import RunDispatcher
from ..contracts.codec import canonical, digest
from ..contracts.models import ApprovalBinding, ExecutionPlan, TargetFence
from ..contracts.ports import RunControlPort


def build_operator_dispatcher(
    store: RunControlPort, *, plan: ExecutionPlan, step: str, approval: ApprovalBinding,
    fence: TargetFence, command_grants: dict[str, ApprovalBinding],
    operator_database: PostgresTLS, authority_database: PostgresTLS,
    clock: ProtectedClock, deadline: float,
) -> RunDispatcher:
    """Assemble one frozen step using native identities and the original attempt deadline.

    The control store is a separately protected coordination port. Its write credential is not
    passed to the target helper. The returned dispatcher is internal, not an unguarded HTTP/CLI API.
    """
    if not isinstance(clock, ProtectedClock):
        raise ValueError("protected clock provider required")
    remaining = deadline - time.monotonic()
    if not math.isfinite(remaining) or not 0 < remaining <= 1800:
        raise ValueError("original bounded attempt deadline required")
    planned = next((item for item in plan.steps if item.step == step), None)
    plan_digest = digest(canonical(plan.model_dump(mode="json")))
    if planned is None or (
        approval.purpose, approval.target, approval.plan, approval.artifact, approval.policy,
    ) != ("apply", plan.target, plan_digest, plan.artifact_digest, plan.policy_digest):
        raise ValueError("helper approval does not match the frozen execution plan")
    if fence.target != plan.target:
        raise ValueError("helper fence names another target")
    # The source validates the live mapping too; role names here come from the TLS target, not
    # a caller's actorRole claim. Missing/unhealthy time fails before a connection is opened.
    clock()
    authority = PostgresOperatorAuthority(
        approval, fence, actor_role=operator_database.target.user,
        definitions={planned.step: planned.definition_digest}, clock=clock, deadline=deadline,
    )
    current = PostgresCommandAuthority(
        lambda: authority_database.open(readonly=True, autocommit=True), command_grants,
        actor_role=authority_database.target.user, clock=clock, deadline=deadline,
    )
    target = PostgresTargetExecutor(
        None, authority, identity=planned.step, planned_effect=planned,
        connection_factory=lambda: operator_database.open(readonly=False, autocommit=True),
    )
    return RunDispatcher(store, target, authorize=current)


def build_scoped_operator_dispatcher(
    *, plan: ExecutionPlan, step: str, approval: ApprovalBinding, fence: TargetFence,
    command_grants: dict[str, ApprovalBinding], operator_database: PostgresTLS,
    control_database: PostgresTLS, clock: ProtectedClock, deadline: float,
) -> RunDispatcher:
    """Co-located native profile: command-only coordination and mandatory preparation proof."""
    if (operator_database.target.database, operator_database.target.port) != (
        control_database.target.database, control_database.target.port,
    ) or operator_database.target.user == control_database.target.user:
        raise ValueError("co-located database with separate control/target identities required")
    store = ScopedPostgresRunStore(
        lambda: control_database.open(readonly=False, autocommit=True), command_grants,
        actor_role=control_database.target.user, clock=clock, deadline=deadline,
    )
    dispatcher = build_operator_dispatcher(
        store, plan=plan, step=step, approval=approval, fence=fence,
        command_grants={key: command_grants[key] for key in ("run", "reconcile")},
        operator_database=operator_database, authority_database=control_database,
        clock=clock, deadline=deadline,
    )
    dispatcher.target.require_preparation = True
    return dispatcher
