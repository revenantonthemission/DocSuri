"""Fenced ResearchWorkspace C14 codec and recoverable local execution."""

import json
from datetime import UTC, datetime
from uuid import UUID, uuid4, uuid5

from docsuri_shared.workspace import execution as execution_wire
from psycopg.errors import InsufficientPrivilege
from psycopg.types.json import Jsonb
from pydantic import ValidationError

from backend.modules.plans.guarded_repository import GuardedUsageRepository
from backend.transactions import Authority
from backend.u4_policy import SYNTHETIC_RESEARCH

from .admission import ResearchAdmission
from .errors import ResearchError
from .evidence import SyntheticResearchProvider, validate_output
from .jobs import ResearchJobs
from .repository import digest
from .service import artifact_dto


def binding(row):
    return {
        "ownerComponent": "ResearchWorkspace",
        "operationId": str(row["id"]),
        "inputRevision": "1",
        "inputHash": row["input_hash"],
        "payloadRef": str(row["id"]),
    }


def claim_dto(row):
    return {
        "binding": binding(row),
        "workerId": str(row["worker_id"]),
        "leaseId": str(row["lease_id"]),
        "fence": row["fence"],
        "leaseRevision": str(row["fence"]),
        "expiresAt": row["lease_until"].isoformat(),
    }


class ResearchExecution(ResearchJobs):
    # Assembly turns this on only once the concrete codec is installed. Its
    # correctness remains subject to the real C14 boundary verification lane.
    enabled = False

    def __init__(self, transactions, corpus, *, policy=SYNTHETIC_RESEARCH):
        super().__init__(transactions)
        self.corpus = corpus
        self.policy = policy
        self.usage = GuardedUsageRepository(transactions)
        self.admission = ResearchAdmission(transactions)
        self.provider = SyntheticResearchProvider()
        self.worker_id = uuid4()

    def accept(self, authority, operation, value, kind):
        return self.admission.accept_with_usage(
            authority,
            str(operation),
            value,
            kind,
            self.usage,
            ResearchJobs(self.transactions),
            queue_limit=self.policy.queue_depth,
        )

    def locked(self, conn, authority, job_id):
        row = conn.execute(
            "SELECT * FROM research.job WHERE id=%s AND owner_id=%s FOR UPDATE",
            (job_id, authority.account_id),
        ).fetchone()
        if not row:
            raise ResearchError("NOT_FOUND")
        self.context(conn, authority, row["context_id"])
        if row["session_id"]:
            self.session(conn, authority, row["session_id"])
        if row["kind"] == "novelty-discussion":
            reference = row["input"]["source"]
            source = conn.execute(
                "SELECT * FROM research.artifact WHERE id=%s AND owner_id=%s "
                "AND context_id=%s AND availability='ready' AND expires_at>clock_timestamp()",
                (reference["artifactId"], authority.account_id, row["context_id"]),
            ).fetchone()
            if (
                not source
                or source["kind"] != "novelty-result"
                or str(source["revision"]) != reference["revision"]
                or source["content_hash"] != reference["contentHash"]
            ):
                raise ResearchError("SOURCE_INELIGIBLE")
        for paper in row["scope"]["publicPapers"]:
            eligibility = conn.execute(
                "SELECT corpus.guard_version(%s,'local-research') AS revision",
                (paper["versionId"],),
            ).fetchone()["revision"]
            if str(eligibility) != paper["eligibilityRevision"]:
                raise ResearchError("SOURCE_INELIGIBLE")
        return row

    def acquireExecutionClaim(self, authority, requested_binding, worker_id, previous_fence=None):
        def acquire(conn):
            row = self.locked(conn, authority, requested_binding["operationId"])
            if binding(row) != requested_binding:
                raise ResearchError("CONFLICT")
            if row["state"] not in {"accepted", "running", "cancel_requested"}:
                raise ResearchError("CONFLICT")
            live = row["lease_until"] is not None and row["lease_until"] > datetime.now(UTC)
            if live:
                if str(row["worker_id"]) != str(worker_id):
                    raise ResearchError("CONFLICT")
                return {
                    "claim": claim_dto(row),
                    "jobRevision": str(row["revision"]),
                    "acceptedAt": row["accepted_at"].isoformat(),
                }
            if row["fence"] and previous_fence != row["fence"]:
                raise ResearchError("CONFLICT")
            if row["attempts"] >= self.policy.retries + 1:
                raise ResearchError("CAPACITY_EXHAUSTED")
            row = conn.execute(
                "UPDATE research.job SET state=CASE WHEN state='accepted' THEN 'running' ELSE "
                "state END, "
                "lease_id=%s,worker_id=%s,fence=fence+1,lease_until=clock_timestamp()+%s*interv"
                "al '1 second',"
                "attempts=attempts+1,revision=revision+1,seq=seq+1 WHERE id=%s RETURNING *",
                (uuid4(), worker_id, self.policy.lease_seconds, row["id"]),
            ).fetchone()
            return {
                "claim": claim_dto(row),
                "jobRevision": str(row["revision"]),
                "acceptedAt": row["accepted_at"].isoformat(),
            }

        return self.run(authority, acquire)

    def validate_claim(self, row, claim, *, terminal=False):
        if claim != claim_dto(row):
            raise ResearchError("CONFLICT")
        if not terminal and row["lease_until"] <= datetime.now(UTC):
            raise ResearchError("CONFLICT")

    def readExecutionPayload(self, authority, claim):
        def read(conn):
            row = self.locked(conn, authority, claim["binding"]["operationId"])
            self.validate_claim(row, claim)
            if row["state"] not in {"running", "cancel_requested"}:
                raise ResearchError("CONFLICT")
            scope = row["scope"]
            return {
                "binding": binding(row),
                "acceptedAt": row["accepted_at"].isoformat(),
                "input": {
                    "kind": row["kind"],
                    "contextId": str(row["context_id"]),
                    "sessionId": str(row["session_id"]) if row["session_id"] else None,
                    "inputSnapshot": row["input"],
                    "inputHash": row["input_hash"],
                    "sourceScope": [p["versionId"] for p in scope["publicPapers"]],
                    "attachmentReferences": scope["attachmentIds"],
                    "draftRevision": (row["input"].get("submittedDraft") or {}).get("revision"),
                    "processingPolicy": row["policy"],
                },
                "evidenceScope": [p["versionId"] for p in scope["publicPapers"]],
                "usageRecordId": str(row["usage_id"]),
            }

        return self.run(authority, read)

    def sources(self, payload):
        result = []
        for paper in payload["input"]["inputSnapshot"]["scope"]["publicPapers"]:
            row = self.corpus.read(paper["versionId"])
            if row["paper_id"] != paper["paperId"]:
                raise ResearchError("SOURCE_INELIGIBLE")
            sections = row["content"].get("sections", [])
            for section in sections[:8]:
                text = section.get("text", "")
                if text and len(text.encode()) <= 32768:
                    result.append(
                        {
                            "sourceKind": "public-paper",
                            "sourceId": paper["paperId"],
                            "sourceVersion": paper["versionId"],
                            "sourceUrl": row["source_url"],
                            "location": section.get("anchor", "section"),
                            "text": text,
                        }
                    )
        return result

    def recordCompletion(self, authority, fact):
        try:
            execution_wire.DispatchFact.model_validate_json(json.dumps(fact), strict=True)
        except (ValidationError, ValueError, TypeError):
            raise ResearchError("INVALID_ARGUMENT") from None
        fact_hash = digest(fact)
        receipt_key = "completion:" + fact["messageId"]

        def replay(conn):
            row = self.locked(conn, authority, fact["operationId"])
            receipt = conn.execute(
                "SELECT * FROM research.receipt WHERE owner_id=%s AND operation_key=%s",
                (authority.account_id, receipt_key),
            ).fetchone()
            if receipt and receipt["input_hash"] != fact_hash:
                raise ResearchError("IDEMPOTENCY_CONFLICT")
            return row if receipt else None

        previous = self.run(authority, replay)
        if previous:
            self.reconcile(previous)
            return previous
        claim = fact["claim"]
        payload = self.readExecutionPayload(authority, claim)
        outcome = fact["outcome"]
        prepared = fact.get("prepared")
        if (
            fact["ownerComponent"] != "ResearchWorkspace"
            or fact["operationId"] != claim["binding"]["operationId"]
            or fact["inputHash"] != payload["input"]["inputHash"]
            or fact["kind"] != payload["input"]["kind"]
            or fact["usageRecordId"] != payload["usageRecordId"]
            or outcome not in {"succeeded", "failed", "cancelled"}
        ):
            raise ResearchError("CONFLICT")
        if outcome == "succeeded":
            if (
                not isinstance(prepared, dict)
                or fact["error"] is not None
                or fact["progress"] is not None
            ):
                raise ResearchError("INVALID_ARGUMENT")
            ref = prepared["artifact"]
            expected = {
                "resultId": ref["artifactId"],
                "revision": ref["revision"],
                "contentHash": ref["contentHash"],
                "mediaType": prepared["mediaType"],
            }
            kinds = {
                "research-turn": "research-answer",
                "novelty-analysis": "novelty-result",
                "novelty-discussion": "novelty-discussion",
            }
            if (
                fact["resultRef"] != expected
                or prepared["ownerId"] != str(authority.account_id)
                or prepared["contextId"] != payload["input"]["contextId"]
                or prepared["operationId"] != fact["operationId"]
                or prepared["kind"] != kinds[fact["kind"]]
                or ref["revision"] != "1"
                or ref["contentHash"] != digest(prepared["output"])
                or prepared["policy"] != payload["input"]["processingPolicy"]
                or prepared["mediaType"] != "application/json"
                or prepared["currentEligibilityRevision"] != "1"
            ):
                raise ResearchError("CONFLICT")
            validate_output(prepared["output"], self.sources(payload))
        elif prepared is not None or fact["resultRef"] is not None:
            raise ResearchError("INVALID_ARGUMENT")

        def complete(conn):
            row = self.locked(conn, authority, fact["operationId"])
            self.validate_claim(row, claim)
            if str(row["revision"]) != fact["expectedJobRevision"]:
                raise ResearchError("CONFLICT")
            if outcome == "cancelled" and (
                row["kind"] != "novelty-analysis" or row["state"] != "cancel_requested"
            ):
                raise ResearchError("CONFLICT")
            if outcome == "succeeded":
                conn.execute(
                    "INSERT INTO research.artifact(id,job_id,context_id,owner_id,content_hash,k"
                    "ind,output,policy,expires_at) "
                    "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,clock_timestamp()+%s*interval '1 second')",
                    (
                        ref["artifactId"],
                        row["id"],
                        row["context_id"],
                        row["owner_id"],
                        ref["contentHash"],
                        prepared["kind"],
                        Jsonb(prepared["output"]),
                        Jsonb(prepared["policy"]),
                        self.policy.artifact_seconds,
                    ),
                )
                for evidence in prepared["output"]["evidence"]:
                    conn.execute(
                        "INSERT INTO research.evidence(id,artifact_id,context_id,owner_id,recor"
                        "d) VALUES(%s,%s,%s,%s,%s)",
                        (
                            evidence["evidenceId"],
                            ref["artifactId"],
                            row["context_id"],
                            row["owner_id"],
                            Jsonb(evidence),
                        ),
                    )
                for assessment in prepared["output"].get("assessments", []):
                    conn.execute(
                        "INSERT INTO research.assessment(id,artifact_id,method_revision,record)"
                        " VALUES(%s,%s,%s,%s)",
                        (
                            uuid4(),
                            ref["artifactId"],
                            prepared["output"]["methodRevision"],
                            Jsonb(assessment),
                        ),
                    )
            result = conn.execute(
                "UPDATE research.job SET state=%s,artifact_id=%s,error_code=%s,revision=revisio"
                "n+1,seq=seq+1 WHERE id=%s RETURNING *",
                (
                    outcome,
                    ref["artifactId"] if outcome == "succeeded" else None,
                    (fact.get("error") or {}).get("code"),
                    row["id"],
                ),
            ).fetchone()
            conn.execute(
                "INSERT INTO research.receipt(owner_id,operation_key,input_hash,response) "
                "VALUES(%s,%s,%s,%s)",
                (
                    authority.account_id,
                    receipt_key,
                    fact_hash,
                    Jsonb({"jobId": str(row["id"]), "state": outcome}),
                ),
            )
            conn.execute(
                "UPDATE research.dispatch SET delivered=true WHERE job_id=%s", (row["id"],)
            )
            return result

        row = self.run(authority, complete)
        self.reconcile(row)
        return row

    def reconcile(self, row):
        if row["state"] not in {"succeeded", "failed", "cancelled"}:
            return
        disposition = "committed" if row["state"] == "succeeded" else "released"
        proof = digest(
            {
                "operationId": str(row["id"]),
                "state": row["state"],
                "artifactId": str(row["artifact_id"]),
            }
        )
        self.usage.settle(row["usage_id"], row["id"], disposition=disposition, proof_hash=proof)
        self.transactions.run(
            "research",
            lambda conn: conn.execute(
                "UPDATE research.job SET usage_state=%s WHERE id=%s AND usage_id=%s",
                (
                    "settled" if disposition == "committed" else "released",
                    row["id"],
                    row["usage_id"],
                ),
            ),
        )

    def step(self):
        self.admission.recover_prepared()
        # Rejected work has no job row. Its durable closure must still recover
        # quota after a failed release, process restart or browser revocation.
        self.admission.reconcile_release(self.usage)
        row = self.transactions.run(
            "research",
            lambda conn: conn.execute(
                "SELECT j.* FROM research.job j JOIN research.admission a ON a.operation_id=j.id "
                "WHERE a.state='accepted' AND j.state IN ('accepted','running','cancel_requested') "
                "AND (lease_until IS NULL OR lease_until<=clock_timestamp()) ORDER BY "
                "accepted_at,j.id LIMIT 1"
            ).fetchone(),
        )
        if not row:
            outstanding = self.transactions.run(
                "research",
                lambda conn: conn.execute(
                    "SELECT j.* FROM research.job j JOIN research.admission a ON "
                    "a.operation_id=j.id "
                    "WHERE a.state='accepted' AND j.state IN "
                    "('succeeded','failed','cancelled') AND usage_state='reserved' LIMIT "
                    "1"
                ).fetchone(),
            )
            if outstanding:
                self.reconcile(outstanding)
            return
        authority = Authority(row["owner_id"], row["authority_session"])
        try:
            acquired = self.acquireExecutionClaim(
                authority, binding(row), self.worker_id, row["fence"] or None
            )
        except (ResearchError, InsufficientPrivilege, PermissionError):
            # A durable obligation can be failed without releasing its private
            # payload. Fence against a concurrently acquired replacement first.
            closed = self.transactions.run(
                "research",
                lambda conn: conn.execute(
                    "UPDATE research.job SET state='failed',error_code='SOURCE_INELIGIBLE',revi"
                    "sion=revision+1,seq=seq+1 "
                    "WHERE id=%s AND fence=%s AND state IN "
                    "('accepted','running','cancel_requested') "
                    "AND (lease_until IS NULL OR lease_until<=clock_timestamp()) RETURNING *",
                    (row["id"], row["fence"]),
                ).fetchone(),
            )
            if closed:
                self.reconcile(closed)
            return
        payload = self.readExecutionPayload(authority, acquired["claim"])
        cancelled = row["state"] == "cancel_requested"
        if cancelled:
            self.recordCompletion(
                authority,
                {
                    "messageId": str(uuid4()),
                    "causationId": str(row["id"]),
                    "ownerComponent": "ResearchWorkspace",
                    "operationId": str(row["id"]),
                    "kind": row["kind"],
                    "outcome": "cancelled",
                    "resultRef": None,
                    "error": None,
                    "claim": acquired["claim"],
                    "expectedJobRevision": acquired["jobRevision"],
                    "inputHash": row["input_hash"],
                    "progress": None,
                    "prepared": None,
                    "usageRecordId": str(row["usage_id"]),
                },
            )
            return
        output = self.provider.run(self.sources(payload))
        artifact_id = uuid5(UUID(str(row["id"])), "research-result:1")
        prepared = artifact_dto(
            {
                "id": artifact_id,
                "revision": 1,
                "content_hash": digest(output),
                "owner_id": row["owner_id"],
                "context_id": row["context_id"],
                "job_id": row["id"],
                "kind": {
                    "research-turn": "research-answer",
                    "novelty-analysis": "novelty-result",
                    "novelty-discussion": "novelty-discussion",
                }[row["kind"]],
                "output": output,
                "eligibility_revision": 1,
                "policy": row["policy"],
            }
        )
        self.recordCompletion(
            authority,
            {
                "messageId": str(uuid4()),
                "causationId": str(row["id"]),
                "ownerComponent": "ResearchWorkspace",
                "operationId": str(row["id"]),
                "kind": row["kind"],
                "outcome": "succeeded",
                "resultRef": {
                    "resultId": str(artifact_id),
                    "revision": "1",
                    "contentHash": digest(output),
                    "mediaType": "application/json",
                },
                "error": None,
                "claim": acquired["claim"],
                "expectedJobRevision": acquired["jobRevision"],
                "inputHash": row["input_hash"],
                "progress": None,
                "prepared": prepared,
                "usageRecordId": str(row["usage_id"]),
            },
        )
