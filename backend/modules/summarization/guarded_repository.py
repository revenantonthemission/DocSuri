"""Durable PA admission, execution and publication under current owner authority."""

from __future__ import annotations

import hashlib
import json
from uuid import UUID, uuid4

from backend.artifacts import Artifact, PrivateArtifacts
from backend.transactions import Authority, OwnerTransactions, guard
from psycopg.types.json import Jsonb


def intent_digest(value: dict) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


class GuardedAssistanceRepository:
    def __init__(self, transactions: OwnerTransactions, files: PrivateArtifacts):
        self.transactions = transactions
        self.files = files

    def prepare(self, authority: Authority, operation: UUID, payload: dict) -> dict:
        hashed = intent_digest(payload)

        def write(conn):
            guard(conn, authority, version=payload["versionId"])
            existing = conn.execute(
                "SELECT * FROM assistance.admission WHERE operation_id=%s FOR UPDATE", (operation,)
            ).fetchone()
            if existing:
                if (
                    existing["account_id"] != authority.account_id
                    or existing["intent_hash"] != hashed
                ):
                    raise ValueError("operation identity conflict")
                return existing
            counts = conn.execute(
                "SELECT count(*) AS total,count(*) FILTER(WHERE account_id=%s) AS own FROM "
                "assistance.admission WHERE disposition='open' OR operation_id IN (SELECT id "
                "FROM assistance.job WHERE state IN ('accepted','running'))",
                (authority.account_id,),
            ).fetchone()
            if counts["total"] >= 4 or counts["own"] >= 2:
                raise ValueError("finite admission capacity reached")
            return conn.execute(
                "INSERT INTO assistance.admission(operation_id,account_id,intent_hash,intent,"
                "disposition) VALUES(%s,%s,%s,%s,'open') RETURNING *",
                (operation, authority.account_id, hashed, Jsonb(payload)),
            ).fetchone()

        return self.transactions.run("assistance", write)

    def accept(self, authority: Authority, operation: UUID, reservation: UUID) -> dict:
        def write(conn):
            # Read identities first; guard lock order remains account/source/target.
            intent = conn.execute(
                "SELECT * FROM assistance.admission WHERE operation_id=%s", (operation,)
            ).fetchone()
            if not intent or intent["account_id"] != authority.account_id:
                raise PermissionError("admission unavailable")
            authority_revision = guard(conn, authority, version=intent["intent"]["versionId"])
            intent = conn.execute(
                "SELECT * FROM assistance.admission WHERE operation_id=%s FOR UPDATE", (operation,)
            ).fetchone()
            if intent["disposition"] == "accepted":
                if intent["reservation_id"] != reservation:
                    raise ValueError("reservation identity conflict")
                return conn.execute(
                    "SELECT * FROM assistance.job WHERE id=%s", (operation,)
                ).fetchone()
            if intent["disposition"] != "open":
                raise ValueError("admission closed before acceptance")
            glossary = conn.execute(
                "SELECT * FROM assistance.read_glossary(%s)", (authority.account_id,)
            ).fetchone()
            row = conn.execute(
                "INSERT INTO assistance.job(id,account_id,authority_revision,version_id,"
                "source_hash,input_hash,payload,glossary_revision,glossary_snapshot,"
                "reservation_id) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
                (
                    operation,
                    authority.account_id,
                    authority_revision,
                    intent["intent"]["versionId"],
                    intent["intent"]["sourceHash"],
                    intent["intent_hash"],
                    Jsonb(intent["intent"]),
                    glossary["revision"],
                    Jsonb(glossary["snapshot"]),
                    reservation,
                ),
            ).fetchone()
            conn.execute(
                "UPDATE assistance.admission SET disposition='accepted',reservation_id=%s,"
                "revision=gen_random_uuid() WHERE operation_id=%s",
                (reservation, operation),
            )
            return row

        return self.transactions.run("assistance", write)

    def reject_open(self, authority: Authority, operation: UUID) -> dict:
        def write(conn):
            guard(conn, authority)
            row = conn.execute(
                "SELECT * FROM assistance.admission WHERE operation_id=%s AND account_id=%s "
                "FOR UPDATE",
                (operation, authority.account_id),
            ).fetchone()
            if not row:
                raise PermissionError("admission unavailable")
            if row["disposition"] == "accepted":
                raise ValueError("accepted work cannot be rejected")
            return conn.execute(
                "UPDATE assistance.admission SET disposition='rejected',"
                "revision=gen_random_uuid() WHERE operation_id=%s RETURNING *",
                (operation,),
            ).fetchone()

        return self.transactions.run("assistance", write)

    def pending(self, limit: int = 4) -> list[dict]:
        if not 1 <= limit <= 4:
            raise ValueError("invalid dispatch bound")
        return self.transactions.run(
            "assistance",
            lambda conn: conn.execute(
                "SELECT id FROM assistance.job WHERE state IN ('accepted','running') AND "
                "(lease_expires_at IS NULL OR lease_expires_at<=clock_timestamp()) ORDER BY "
                "accepted_at,id LIMIT %s",
                (limit,),
            ).fetchall(),
        )

    def claim(self, job: UUID, worker: UUID) -> dict:
        return self.transactions.run(
            "assistance",
            lambda conn: conn.execute(
                "SELECT * FROM assistance.acquire_claim(%s,%s)", (job, worker)
            ).fetchone(),
        )

    def renew(self, claim: dict) -> dict:
        return self.transactions.run(
            "assistance",
            lambda conn: conn.execute(
                "SELECT * FROM assistance.renew_claim(%s,%s,%s,%s,%s)",
                (
                    claim["id"],
                    claim["worker_id"],
                    claim["lease_id"],
                    claim["fence"],
                    claim["lease_revision"],
                ),
            ).fetchone(),
        )

    @staticmethod
    def _claim(conn, claim: dict) -> dict:
        return conn.execute(
            "SELECT * FROM assistance.guard_claim(%s,%s,%s,%s)",
            (claim["id"], claim["worker_id"], claim["lease_id"], claim["fence"]),
        ).fetchone()

    def payload(self, claim: dict) -> dict:
        return self.transactions.run("assistance", lambda conn: self._claim(conn, claim)["payload"])

    def complete(
        self, claim: dict, fact: UUID, content: bytes, coverage: dict, provenance: dict
    ) -> dict:
        # Publication is bounded and outside authorization transactions. Orphan
        # bytes after a denied/unknown commit remain private for reconciliation.
        artifact = self.files.publish(content)
        submitted = {
            "hash": artifact.sha256,
            "size": artifact.size,
            "coverage": coverage,
            "provenance": provenance,
            "job": str(claim["id"]),
            "worker": str(claim["worker_id"]),
            "lease": str(claim["lease_id"]),
            "fence": claim["fence"],
            "revision": str(claim["revision"]),
        }
        hashed = intent_digest(submitted)

        def write(conn):
            job = conn.execute(
                "SELECT * FROM assistance.job WHERE id=%s", (claim["id"],)
            ).fetchone()
            if not job:
                raise PermissionError("job unavailable")
            conn.execute(
                "SELECT accounts.guard_execution(%s,%s)",
                (job["account_id"], job["authority_revision"]),
            )
            conn.execute(
                "SELECT corpus.guard_version(%s,%s)", (job["version_id"], "local-research")
            )
            prior = conn.execute(
                "SELECT * FROM assistance.receipt WHERE account_id=%s AND kind='completion' "
                "AND key=%s",
                (job["account_id"], fact),
            ).fetchone()
            if prior:
                if prior["intent_hash"] != hashed:
                    raise ValueError("completion fact conflict")
                return prior["outcome"]
            job = self._claim(conn, claim)
            if job["revision"] != claim["revision"]:
                raise ValueError("stale progress revision")
            result_id = uuid4()
            conn.execute(
                "INSERT INTO assistance.result(id,job_id,account_id,version_id,input_hash,"
                "source_hash,output_hash,private_path,byte_length,coverage,provenance,"
                "availability) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'retained')",
                (
                    result_id,
                    job["id"],
                    job["account_id"],
                    job["version_id"],
                    job["input_hash"],
                    job["source_hash"],
                    artifact.sha256,
                    artifact.name,
                    artifact.size,
                    Jsonb(coverage),
                    Jsonb(provenance),
                ),
            )
            conn.execute(
                "UPDATE assistance.job SET state='succeeded',phase='complete',"
                "revision=gen_random_uuid(),sequence=sequence+1,settlement_pending=true WHERE "
                "id=%s",
                (job["id"],),
            )
            outcome = {
                "jobId": str(job["id"]),
                "resultId": str(result_id),
                "outputHash": artifact.sha256,
            }
            conn.execute(
                "INSERT INTO assistance.receipt(account_id,kind,key,intent_hash,outcome) "
                "VALUES(%s,'completion',%s,%s,%s)",
                (job["account_id"], fact, hashed, Jsonb(outcome)),
            )
            return outcome

        return self.transactions.run("assistance", write)

    def history(self, authority: Authority, limit: int = 20) -> list[dict]:
        if not 1 <= limit <= 100:
            raise ValueError("invalid history bound")

        def read(conn):
            guard(conn, authority)
            rows = conn.execute(
                "SELECT id,version_id,accepted_at,state,revision,sequence FROM assistance.job "
                "WHERE account_id=%s ORDER BY accepted_at DESC,id DESC LIMIT %s",
                (authority.account_id, limit),
            ).fetchall()
            for row in rows:
                row["availability"] = conn.execute(
                    "SELECT corpus.reference_availability(%s) AS disposition",
                    (row["version_id"],),
                ).fetchone()["disposition"]
            return rows

        return self.transactions.run("assistance", read)

    def snapshot(self, authority: Authority, job: UUID) -> dict:
        def read(conn):
            guard(conn, authority)
            row = conn.execute(
                "SELECT * FROM assistance.job WHERE id=%s AND account_id=%s",
                (job, authority.account_id),
            ).fetchone()
            if not row:
                raise PermissionError("job unavailable")
            guard(conn, authority, version=row["version_id"])
            return row

        return self.transactions.run("assistance", read)

    def events(self, authority: Authority, job: UUID, after: int) -> list[dict]:
        if after < 0:
            raise ValueError("invalid progress cursor")

        def read(conn):
            guard(conn, authority)
            row = conn.execute(
                "SELECT version_id FROM assistance.job WHERE id=%s AND account_id=%s",
                (job, authority.account_id),
            ).fetchone()
            if not row:
                raise PermissionError("job unavailable")
            guard(conn, authority, version=row["version_id"])
            return conn.execute(
                "SELECT sequence,snapshot FROM assistance.event WHERE job_id=%s AND "
                "sequence>%s ORDER BY sequence LIMIT 100",
                (job, after),
            ).fetchall()

        return self.transactions.run("assistance", read)

    def fail(self, claim: dict, fact: UUID, reason: str) -> dict:
        if reason not in (
            "insufficient-result",
            "dependency-unavailable",
            "invalid-source",
            "deadline-exceeded",
        ):
            raise ValueError("unsupported safe failure code")
        hashed = intent_digest(
            {
                "job": str(claim["id"]),
                "worker": str(claim["worker_id"]),
                "lease": str(claim["lease_id"]),
                "fence": claim["fence"],
                "reason": reason,
                "revision": str(claim["revision"]),
            }
        )

        def write(conn):
            row = conn.execute(
                "SELECT * FROM assistance.job WHERE id=%s", (claim["id"],)
            ).fetchone()
            if not row:
                raise PermissionError("job unavailable")
            conn.execute(
                "SELECT accounts.guard_execution(%s,%s)",
                (row["account_id"], row["authority_revision"]),
            )
            conn.execute(
                "SELECT corpus.guard_version(%s,%s)", (row["version_id"], "local-research")
            )
            prior = conn.execute(
                "SELECT * FROM assistance.receipt WHERE account_id=%s AND kind='failure' AND "
                "key=%s",
                (row["account_id"], fact),
            ).fetchone()
            if prior:
                if prior["intent_hash"] != hashed:
                    raise ValueError("failure fact conflict")
                return prior["outcome"]
            row = self._claim(conn, claim)
            if row["revision"] != claim["revision"]:
                raise ValueError("stale progress revision")
            conn.execute(
                "UPDATE assistance.job SET state='failed',phase='failed',failure_code=%s,"
                "revision=gen_random_uuid(),sequence=sequence+1,settlement_pending=true WHERE "
                "id=%s",
                (reason, row["id"]),
            )
            outcome = {"jobId": str(row["id"]), "state": "failed", "reason": reason}
            conn.execute(
                "INSERT INTO assistance.receipt(account_id,kind,key,intent_hash,outcome) "
                "VALUES(%s,'failure',%s,%s,%s)",
                (row["account_id"], fact, hashed, Jsonb(outcome)),
            )
            return outcome

        return self.transactions.run("assistance", write)

    def result(self, authority: Authority, result: UUID) -> bytes:
        def read(conn):
            guard(conn, authority)
            row = conn.execute(
                "SELECT * FROM assistance.result WHERE id=%s AND account_id=%s",
                (result, authority.account_id),
            ).fetchone()
            if not row or row["availability"] != "retained":
                raise PermissionError("result unavailable")
            guard(conn, authority, version=row["version_id"])
            return self.files.read(
                Artifact(row["private_path"], row["output_hash"], row["byte_length"])
            )

        return self.transactions.run("assistance", read)

    def unsettled(self, limit: int = 4) -> list[dict]:
        if not 1 <= limit <= 4:
            raise ValueError("invalid reconciliation bound")
        return self.transactions.run(
            "assistance",
            lambda conn: conn.execute(
                "SELECT id,account_id,reservation_id,state FROM assistance.job WHERE "
                "settlement_pending ORDER BY accepted_at,id LIMIT %s",
                (limit,),
            ).fetchall(),
        )

    def confirm_settlement(self, job: UUID, receipt: dict) -> None:
        def write(conn):
            row = conn.execute(
                "SELECT * FROM assistance.job WHERE id=%s FOR UPDATE", (job,)
            ).fetchone()
            if (
                not row
                or receipt.get("operationId") != str(job)
                or receipt.get("reservationId") != str(row["reservation_id"])
                or row["state"] not in ("succeeded", "failed")
                or receipt.get("disposition")
                != ("committed" if row["state"] == "succeeded" else "released")
            ):
                raise ValueError("settlement receipt binding mismatch")
            if row["settlement_receipt"] is not None and row["settlement_receipt"] != receipt:
                raise ValueError("settlement receipt conflict")
            conn.execute(
                "UPDATE assistance.job SET settlement_pending=false,settlement_receipt=%s "
                "WHERE id=%s",
                (Jsonb(receipt), job),
            )

        self.transactions.run("assistance", write)
