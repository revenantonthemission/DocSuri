"""Coordinate owner receipts without treating a timeout as a business outcome.

Every step is independently durable. Repeating the original intent reconciles
the same preparation/reservation/acceptance, and never invents another job.
These are trusted internal application methods, not browser control surfaces.
"""

from __future__ import annotations

from uuid import UUID

from backend.modules.plans.guarded_repository import GuardedUsageRepository, UsageQuotaExceeded
from backend.modules.summarization.guarded_repository import GuardedAssistanceRepository
from backend.transactions import Authority


class AssistanceAdmission:
    def __init__(self, assistance: GuardedAssistanceRepository, usage: GuardedUsageRepository):
        self.assistance = assistance
        self.usage = usage

    def accept(self, authority: Authority, operation: UUID, bound_input: dict) -> dict:
        admission = self.assistance.prepare(authority, operation, bound_input)
        if admission["disposition"] == "rejected":
            raise ValueError("original admission was rejected; no automatic restart")
        try:
            reservation = self.usage.reserve(authority, operation, admission["intent_hash"])
        except UsageQuotaExceeded:
            # Definite refusal may close an open preparation. If revocation or a
            # crash prevents this write, the owner sweep retains the obligation.
            self.assistance.reject_open(authority, operation)
            raise
        # Any failure/unknown reply propagates. In particular, no finally block
        # releases the reservation while acceptance might already be durable.
        return self.assistance.accept(authority, operation, reservation["id"])

    def release_rejected(self, authority: Authority, operation: UUID) -> dict | None:
        """Reconcile only an already-authoritative pre-acceptance rejection.

        This method cannot reject or cancel accepted work. An absent reservation
        is a read outcome, not permission to create one merely to release it.
        """
        proof = self.assistance.rejected_admission_proof(authority, operation)
        self.usage.reject_operation(proof)
        self.assistance.confirm_rejection(proof)
        reservation = self.usage.reservation(authority, operation)
        if reservation is None:
            return None
        if reservation["intent_hash"] != proof["intentHash"]:
            raise ValueError("reservation does not match rejected input")
        return self.usage.settle(
            reservation["id"], operation, disposition="released", proof_hash=proof["proofHash"]
        )

    def settle_terminal(self, job: UUID) -> dict:
        proof = self.assistance.settlement_proof(job)
        receipt = self.usage.settle(
            proof["reservation"],
            proof["operation"],
            disposition=proof["disposition"],
            proof_hash=proof["proofHash"],
        )
        self.assistance.confirm_settlement(job, receipt)
        return receipt

    def reconcile_terminal(self, *, limit: int = 4) -> list[dict]:
        """One finite pass; errors remain visible and obligations stay durable."""
        return [self.settle_terminal(row["id"]) for row in self.assistance.unsettled(limit)]

    def reconcile_admissions(self, *, limit: int = 4) -> int:
        proofs = self.assistance.reject_abandoned(limit=limit)
        for proof in proofs:
            self.usage.reject_operation(proof)
            self.assistance.confirm_rejection(proof)
        return len(proofs)
