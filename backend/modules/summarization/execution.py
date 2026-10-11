"""Canonical worker claims over the single PaperAssistance transaction owner.

The immutable accepted operation allocates both its input revision and payload
reference. They never follow mutable job/progress revisions. Legacy unbound
repository helpers remain diagnostic seams and are not mounted as C14.
"""

from __future__ import annotations

from uuid import UUID

from backend.modules.summarization.guarded_repository import GuardedAssistanceRepository
from docsuri_shared.workspace import execution as wire


class ExecutionClaims:
    def __init__(self, repository: GuardedAssistanceRepository):
        self.repository = repository

    @staticmethod
    def binding(job: dict) -> dict:
        return wire.ExecutionBinding.model_validate(
            {
                "ownerComponent": "PaperAssistance",
                "operationId": str(job["id"]),
                "inputRevision": str(job["id"]),
                "inputHash": job["input_hash"],
                "payloadRef": str(job["id"]),
            }
        ).model_dump(mode="json")

    @classmethod
    def result(cls, job: dict) -> dict:
        return wire.ExecutionClaimResult.model_validate(
            {
                "claim": {
                    "binding": cls.binding(job),
                    "workerId": str(job["worker_id"]),
                    "leaseId": str(job["lease_id"]),
                    "fence": job["fence"],
                    "leaseRevision": str(job["lease_revision"]),
                    "expiresAt": job["lease_expires_at"].isoformat(),
                },
                "jobRevision": str(job["revision"]),
                "acceptedAt": job["accepted_at"].isoformat(),
            }
        ).model_dump(mode="json")

    @classmethod
    def _bound(cls, conn, binding: dict) -> dict:
        normalized = wire.ExecutionBinding.model_validate(binding).model_dump(mode="json")
        job = conn.execute(
            "SELECT * FROM assistance.job WHERE id=%s", (UUID(normalized["operationId"]),)
        ).fetchone()
        if not job:
            raise PermissionError("execution unavailable")
        conn.execute(
            "SELECT accounts.guard_execution(%s,%s)", (job["account_id"], job["authority_revision"])
        )
        conn.execute("SELECT corpus.guard_version(%s,'local-research')", (job["version_id"],))
        if normalized != cls.binding(job):
            raise ValueError("immutable execution binding mismatch")
        return conn.execute(
            "SELECT * FROM assistance.job WHERE id=%s FOR UPDATE", (job["id"],)
        ).fetchone()

    def acquire(self, binding: dict, worker: UUID, *, previous_fence: int | None = None) -> dict:
        worker = UUID(str(worker))
        if previous_fence is not None and (type(previous_fence) is not int or previous_fence < 1):
            raise ValueError("reclaim requires a positive previous fence")

        def write(conn):
            job = self._bound(conn, binding)
            now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            live = job["lease_expires_at"] is not None and job["lease_expires_at"] > now
            if previous_fence is None:
                if job["state"] == "running" and live and job["worker_id"] == worker:
                    # Exact still-current recovery: no lease, seq or deadline mutation.
                    return self.result(job)
                if job["state"] != "accepted" or job["fence"] != 0:
                    raise ValueError("claim conflict; expired work requires explicit reclaim")
            elif job["fence"] != previous_fence or live or job["state"] != "running":
                raise ValueError("previous fence or expired-claim precondition mismatch")
            job = conn.execute(
                "SELECT * FROM assistance.acquire_claim(%s,%s)", (job["id"], worker)
            ).fetchone()
            return self.result(job)

        return self.repository.transactions.run("assistance", write)

    def _current(self, conn, claim: dict) -> dict:
        claim = wire.ExecutionClaim.model_validate(claim).model_dump(mode="json")
        self._bound(conn, claim["binding"])
        return conn.execute(
            "SELECT * FROM assistance.guard_claim(%s,%s,%s,%s)",
            (
                UUID(claim["binding"]["operationId"]),
                UUID(claim["workerId"]),
                UUID(claim["leaseId"]),
                claim["fence"],
            ),
        ).fetchone()

    def renew(self, claim: dict, *, expected_lease_revision: str) -> dict:
        def write(conn):
            job = self._current(conn, claim)
            if claim["leaseRevision"] != expected_lease_revision:
                raise ValueError("claim and expected lease revision differ")
            renewed = conn.execute(
                "SELECT * FROM assistance.renew_claim(%s,%s,%s,%s,%s)",
                (
                    job["id"],
                    job["worker_id"],
                    job["lease_id"],
                    job["fence"],
                    UUID(expected_lease_revision),
                ),
            ).fetchone()
            return self.result(renewed)

        return self.repository.transactions.run("assistance", write)

    def read_input(self, claim: dict) -> dict:
        """Internal accepted data; CorpusContent supplies permitted section bytes later."""

        def read(conn):
            job = self._current(conn, claim)
            now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            return {
                "binding": self.binding(job),
                "payload": job["payload"],
                "acceptedAt": job["accepted_at"],
                "startedAt": job["started_at"],
                "remainingSeconds": max(
                    0,
                    min(
                        90 - (now - job["started_at"]).total_seconds(),
                        300 - (now - job["accepted_at"]).total_seconds(),
                    ),
                ),
                "reservationId": job["reservation_id"],
                "jobRevision": job["revision"],
            }

        return self.repository.transactions.run("assistance", read)

    def proposal(self, claim: dict, *, input_hash: str, expected_job_revision: str) -> dict:
        """Bind a fact before staging bytes; repository rechecks authority at commit.

        Do not require nonterminal state here: exact durable completion receipt
        replay is resolved by the repository after current authority checks.
        """
        normalized = wire.ExecutionClaim.model_validate(claim).model_dump(mode="json")
        if input_hash != normalized["binding"]["inputHash"]:
            raise ValueError("fact input hash mismatch")
        self.repository.transactions.run(
            "assistance", lambda conn: self._bound(conn, normalized["binding"])
        )
        return {
            "id": UUID(normalized["binding"]["operationId"]),
            "worker_id": UUID(normalized["workerId"]),
            "lease_id": UUID(normalized["leaseId"]),
            "fence": normalized["fence"],
            "revision": UUID(expected_job_revision),
        }
