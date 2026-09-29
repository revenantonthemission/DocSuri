from contextlib import AbstractContextManager
from typing import Protocol

from .models import (
    ApprovalBinding,
    BoundCheckpoint,
    CheckpointReceipt,
    CommandContext,
    CurrentEvidenceContext,
    EffectBinding,
    EffectObservation,
    EvidenceHeadSelection,
    ExecutionPlan,
    RunAttempt,
    RunRecord,
    SubjectSnapshot,
    TargetFence,
    VerificationAttestation,
)


class AuthorityPort(Protocol):
    def guard(self, binding: ApprovalBinding) -> AbstractContextManager[None]:
        """Serializes current revocation with finalization; unsupported providers must deny."""
        ...


class EvidenceReadPort(Protocol):
    def snapshot(
        self, subject: str
    ) -> tuple[tuple[EvidenceHeadSelection, ...], tuple[VerificationAttestation, ...]]: ...

    def healthy(self) -> bool: ...


class CurrentEvidencePort(Protocol):
    def inspect(
        self, subject: SubjectSnapshot, records: tuple[VerificationAttestation, ...],
        *, deadline: float,
    ) -> CurrentEvidenceContext | None:
        """Non-renewing current owner/key/exception observation within the caller's budget."""
        ...


class RunControlPort(Protocol):
    def read(self, run_id: str) -> RunRecord: ...

    def attempt(self, run_id: str, attempt_id: str) -> RunAttempt: ...

    def latest(self, run_id: str, step: str) -> BoundCheckpoint | None: ...

    def prepare(
        self, run_id: str, *, attempt_id: str, step: str, fence: TargetFence,
        expected_revision: str, context: CommandContext,
    ) -> CheckpointReceipt:
        """Return only after UNKNOWN, critical audit and outbox commit are acknowledged."""
        ...

    def reconcile(
        self, run_id: str, *, step: str, observation: EffectObservation,
        expected_revision: str, context: CommandContext,
    ) -> CheckpointReceipt: ...


class TargetEffectPort(Protocol):
    def validate_attempt(
        self, attempt: RunAttempt, plan: ExecutionPlan, fence: TargetFence,
    ) -> None:
        """Refuse a mismatch between the frozen run and the configured live authority."""
        ...

    def apply(self, binding: EffectBinding, *, preparation: CheckpointReceipt | None = None) -> str:
        """Return an exact ledger digest only after guarded native commit acknowledgement."""
        ...

    def observe(self, binding: EffectBinding) -> EffectObservation:
        """Observe native facts read-only; never assume authorization from ledger existence."""
        ...
