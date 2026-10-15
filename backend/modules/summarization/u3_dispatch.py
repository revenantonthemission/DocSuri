"""U3 PaperAssistance dispatch: accepted work really reaches an executor.

The mounted acceptance path commits an immutable binding with dispatch
responsibility; this bounded dispatch pass claims each pending job through the
canonical claim/fence path and executes it through the injected executor. A
crash between acceptance and dispatch is recovered by the same pass, never by a
silent no-op enqueue (closing the recorded Q-03 defect through real execution).
"""

from __future__ import annotations

from uuid import UUID, uuid4

from backend.modules.corpus.repository import CorpusRepository
from backend.modules.plans.guarded_repository import GuardedUsageRepository
from backend.modules.summarization.admission import AssistanceAdmission
from backend.modules.summarization.execution import ExecutionClaims
from backend.modules.summarization.guarded_repository import GuardedAssistanceRepository
from backend.modules.summarization.payload import ExecutionPayloads
from backend.modules.summarization.worker import (
    ExecutionInterrupted,
    PaperWorker,
    WorkerIntervention,
)
from backend.u3_policy import bounded_int


class AssistanceDispatch:
    def __init__(self, transactions, files, executor, *, worker_id: UUID | None = None):
        self.transactions = transactions
        self.repository = GuardedAssistanceRepository(transactions, files)
        self.usage = GuardedUsageRepository(transactions)
        self.admission = AssistanceAdmission(self.repository, self.usage)
        self.claims = ExecutionClaims(self.repository)
        self.payloads = ExecutionPayloads(
            self.claims, CorpusRepository(transactions, files=None)
        )
        self.executor = executor
        self.worker_id = worker_id or uuid4()

    def run_once(self, limit: int = 1) -> dict:
        """One finite pass over pending accepted work; errors stay durable."""
        limit = bounded_int(limit, low=1, high=4, name="dispatch bound")
        executed, deferred = 0, 0
        for row in self.repository.pending(limit):
            job = self._job(row["id"])
            worker = PaperWorker(
                self.worker_id,
                self.claims,
                self.admission,
                self.executor,
                payloads=self.payloads,
            )
            try:
                worker.run(self.claims.binding(job))
                executed += 1
            except ExecutionInterrupted:
                deferred += 1  # owner recovery decides; the row stays durable
            except WorkerIntervention:
                deferred += 1  # executor stop unconfirmed; do not replace work
            except (ValueError, PermissionError):
                deferred += 1  # not claimable or authority changed; remains inspectable
        return {"executed": executed, "deferred": deferred}

    def _job(self, job_id: UUID) -> dict:
        return self.transactions.run(
            "assistance",
            lambda conn: conn.execute(
                "SELECT * FROM assistance.job WHERE id=%s", (job_id,)
            ).fetchone(),
        )
