"""Synthetic, domain-shaped run fixtures/strategies; never a production authority provider."""

from hypothesis import strategies as st

from docsuri_platform_integrity.contracts.codec import digest
from docsuri_platform_integrity.contracts.models import (
    CommandContext,
    ExecutionPlan,
    PlannedEffect,
    RunAttempt,
    TargetFence,
    TargetRef,
    ValidityWindow,
)

D = digest(b"frozen-test-artifact")


def plan(*, incarnation="test-install-1", count=2):
    return ExecutionPlan(
        action="migrate",
        target=TargetRef(target_id="test-db", namespace="public", incarnation=incarnation),
        registry_digest=D,
        artifact_digest=D,
        policy_digest=D,
        recovery_digest=D,
        steps=tuple(
            PlannedEffect(
                step=f"owner:step-{i}",
                definition_digest=digest(f"sql-{i}".encode()),
                expected_before=digest(f"state-{i}".encode()),
                expected_after=digest(f"state-{i + 1}".encode()),
            )
            for i in range(count)
        ),
    )


@st.composite
def plans(draw):
    """Same-basename, ordered effect plans across distinct target incarnations/artifacts."""
    value = plan(
        incarnation=f"test-install-{draw(st.integers(1, 100))}",
        count=draw(st.integers(1, 8)),
    )
    return value.model_copy(update={"artifact_digest": digest(draw(st.binary(max_size=32)))})


def context(purpose="run", *, instant="100"):
    return CommandContext(
        actor="test-operator", purpose=purpose, correlation="test-request",
        recorded_at=instant, time_quality="unknown",
    )


def attempt(run_id="r1", number=1):
    return RunAttempt(
        run_id=run_id, attempt_id=f"a{number}", ordinal=number, outcome="RUNNING",
        actor="test-operator", approval=f"test-approval-{number}",
        invocation=f"test-invocation-{number}", started_at="100",
    )


def fence(value, number=1):
    return TargetFence(
        target=value.target, epoch=str(number), holder=f"a{number}",
        validity=ValidityWindow(valid_from="0", valid_until="1000"),
    )
