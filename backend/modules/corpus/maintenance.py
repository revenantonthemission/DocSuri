"""U3 CorpusContent: staged ingestion/refresh/rebuild/retry, publication CAS,
ordered source-change facts and withdrawal replay.

One owner transaction per stage keeps each effect individually inspectable; a
run cannot complete or advance its watermark past unverified work, and only a
verified generation publishes (BR2.1-2.4, BR3.1-3.2). Sources come from an
injected provider so tests exercise the real owner code with fixture inputs at
the adapter boundary only.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from backend.transactions import Authority, guard
from backend.u3_policy import (
    CHANGE_KINDS,
    CORPUS_POLICY,
    ELIGIBILITY_POLICY,
    MAX_EFFECTS_PER_RUN,
    MAX_RUN_BATCH,
    MAX_RUN_RETRIES,
    PROJECTION_COMPATIBILITY,
    RUN_OPERATIONS,
    WORKSPACE_BYTES,
    bounded_int,
    require_policy,
)
from psycopg.types.json import Jsonb


def intent_digest(value: dict) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


class SourceUnavailable(RuntimeError):
    """The declared source scope cannot be resolved; the run stays explicit."""


class CorpusMaintenance:
    def __init__(self, transactions, files, sources):
        self.transactions = transactions
        self.files = files
        self.sources = sources

    # --- W1 acceptance ---------------------------------------------------------

    def accept(self, authority: Authority, operation: UUID, request: dict) -> dict:
        """Durable acceptance: same key and input return the same run, changed input conflicts."""
        operation_request = {
            "operation": request.get("operation"),
            "sourceScopeIds": request.get("sourceScopeIds"),
            "authoritativeInputRevision": request.get("authoritativeInputRevision"),
            "inputManifestHash": request.get("inputManifestHash"),
        }
        if operation_request["operation"] not in RUN_OPERATIONS:
            raise ValueError("unknown corpus operation")
        scope = operation_request["sourceScopeIds"]
        if (
            not isinstance(scope, list)
            or not 1 <= len(scope) <= MAX_RUN_BATCH
            or any(not isinstance(item, str) or not 1 <= len(item) <= 160 for item in scope)
            or len(set(scope)) != len(scope)
        ):
            raise ValueError("source scope outside finite policy")
        manifest = operation_request["inputManifestHash"]
        if not isinstance(manifest, str) or not _is_sha256(manifest):
            raise ValueError("input manifest hash outside finite policy")
        require_policy(request.get("sourcePolicy"), CORPUS_POLICY, name="sourcePolicy")
        compatibility = request.get("compatibilityRevision")
        if compatibility != PROJECTION_COMPATIBILITY:
            raise ValueError("incompatible projection revision")
        digest = intent_digest(operation_request)

        def write(conn):
            guard(conn, authority)
            self._require_maintenance(conn, authority)
            prior = conn.execute(
                "SELECT * FROM corpus.run WHERE idempotency_key=%s", (operation,)
            ).fetchone()
            if prior:
                if prior["intent_hash"] != digest:
                    raise ValueError("changed intent under the same operation key")
                return self._run_view(conn, prior)
            row = conn.execute(
                "INSERT INTO corpus.run(id,operation,source_scope,source_policy,"
                "compatibility_revision,authoritative_input_revision,input_manifest_hash,"
                "intent_hash,idempotency_key) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "RETURNING *",
                (
                    uuid4(),
                    operation_request["operation"],
                    Jsonb(scope),
                    Jsonb(CORPUS_POLICY),
                    compatibility,
                    str(operation_request["authoritativeInputRevision"]),
                    manifest,
                    digest,
                    operation,
                ),
            ).fetchone()
            return self._run_view(conn, row)

        return self.transactions.run("corpus", write)

    def retry(self, authority: Authority, operation: UUID, request: dict) -> dict:
        """Retry/reprocess: reconciled retryable stages of one original intended run."""
        original_id = UUID(str(request.get("retryOf")))
        digest = intent_digest(
            {
                "operation": request.get("operation"),
                "sourceScopeIds": request.get("sourceScopeIds"),
                "authoritativeInputRevision": request.get("authoritativeInputRevision"),
                "inputManifestHash": request.get("inputManifestHash"),
            }
        )

        def write(conn):
            guard(conn, authority)
            self._require_maintenance(conn, authority)
            original = conn.execute(
                "SELECT * FROM corpus.run WHERE id=%s FOR UPDATE", (original_id,)
            ).fetchone()
            if not original:
                raise ValueError("unknown original run")
            if original["intent_hash"] != digest:
                raise ValueError("retry inputs differ from the original intended run")
            if original["state"] not in ("failed", "unknown", "running"):
                raise ValueError("only a failed, unknown or interrupted run is reconcilable")
            if original["state"] == "running":
                conn.execute(
                    "UPDATE corpus.run SET state='failed',revision=gen_random_uuid(),"
                    "dispatch_pending=false WHERE id=%s AND state='running'",
                    (original_id,),
                )
            chain = 1
            ancestor = original
            while ancestor["retry_of"] is not None:
                if chain >= MAX_RUN_RETRIES:
                    raise ValueError("retry attempt allocation exhausted")
                ancestor = conn.execute(
                    "SELECT * FROM corpus.run WHERE id=%s", (ancestor["retry_of"],)
                ).fetchone()
                if ancestor is None:
                    break
                chain += 1
            prior = conn.execute(
                "SELECT * FROM corpus.run WHERE idempotency_key=%s", (operation,)
            ).fetchone()
            if prior:
                if prior["intent_hash"] != digest or prior["retry_of"] != original["id"]:
                    raise ValueError("changed intent under the same operation key")
                return self._run_view(conn, prior)
            row = conn.execute(
                "INSERT INTO corpus.run(id,operation,source_scope,source_policy,"
                "compatibility_revision,authoritative_input_revision,input_manifest_hash,"
                "intent_hash,idempotency_key,retry_of) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
                (
                    uuid4(),
                    original["operation"],
                    Jsonb(original["source_scope"]),
                    Jsonb(original["source_policy"]),
                    original["compatibility_revision"],
                    original["authoritative_input_revision"],
                    original["input_manifest_hash"],
                    digest,
                    operation,
                    original["id"],
                ),
            ).fetchone()
            # Carry only reconciled retryable effects forward; committed effects
            # remain authoritative on the original run.
            conn.execute(
                "INSERT INTO corpus.run_effect(run_id,stage,subject,state,error_code) "
                "SELECT %s,stage,subject,state,error_code FROM corpus.run_effect "
                "WHERE run_id=%s AND state IN ('failed','unknown','pending')",
                (row["id"], original["id"]),
            )
            return self._run_view(conn, row)

        return self.transactions.run("corpus", write)

    def rebuild(self, authority: Authority, operation: UUID, request: dict) -> dict:
        """Rebuild from named authoritative inputs; never assumes the index is the data.

        The accepted run re-derives every covered effect from the declared source
        scope; previously committed stages of other runs are not reused.
        """
        return self.accept(authority, operation, dict(request, operation="rebuild"))

    # --- W1 execution ----------------------------------------------------------

    def pending_runs(self, limit: int = 1) -> list[dict]:
        limit = bounded_int(limit, low=1, high=4, name="run pass bound")

        def read(conn):
            return conn.execute(
                "SELECT * FROM corpus.run WHERE state IN ('accepted','running') "
                "ORDER BY accepted_at, id LIMIT %s",
                (limit,),
            ).fetchall()

        return self.transactions.run("corpus", read)

    def execute(self, run_id: UUID, *, limit: int = MAX_RUN_BATCH) -> dict:
        """One bounded execution pass over a single accepted or running run."""
        run_id = UUID(str(run_id))
        limit = bounded_int(limit, low=1, high=MAX_RUN_BATCH, name="run batch bound")
        claim = self._claim(run_id)
        if claim is None:
            return {"state": "not-claimable", "runId": str(run_id)}
        scope = [str(item) for item in claim["source_scope"]][:limit]
        retryable = claim["state_effects"] if claim["retry_of"] else None
        failures = 0
        for source_id in scope:
            try:
                self._apply_source(claim, source_id, retry_only=retryable)
            except SourceUnavailable:
                self._record_failure(claim, "source", source_id, "source-unavailable")
                failures += 1
            except ValueError as error:
                self._record_failure(
                    claim, "content", source_id, _safe_error_code(error)
                )
                failures += 1
        return self._finish(claim, failed=bool(failures))

    def _claim(self, run_id: UUID) -> dict | None:
        def write(conn):
            row = conn.execute(
                "SELECT * FROM corpus.run WHERE id=%s FOR UPDATE", (run_id,)
            ).fetchone()
            if not row or row["state"] not in ("accepted", "running"):
                return None
            if row["state"] == "accepted":
                row = conn.execute(
                    "UPDATE corpus.run SET state='running',revision=gen_random_uuid(),"
                    "attempts=least(attempts+1,2),dispatch_pending=false WHERE id=%s "
                    "RETURNING *",
                    (run_id,),
                ).fetchone()
            effects = conn.execute(
                "SELECT stage,subject,state FROM corpus.run_effect WHERE run_id=%s",
                (run_id,),
            ).fetchall()
            return {
                "id": row["id"],
                "operation": row["operation"],
                "source_scope": [str(item) for item in row["source_scope"]],
                "retry_of": row["retry_of"],
                "state_effects": {
                    (effect["stage"], effect["subject"]): effect["state"] for effect in effects
                },
            }

        return self.transactions.run("corpus", write)

    def _apply_source(self, claim: dict, source_id: str, *, retry_only: dict | None) -> None:
        record = self.sources.read(source_id)
        if record is None:
            raise SourceUnavailable(source_id)
        normalized = _normalize_source(record)
        if retry_only is not None:
            # Only reconciled retryable stages re-execute; committed stages of
            # the original intended run stay authoritative.
            if retry_only.get(("content", normalized["versionId"])) == "committed" and (
                retry_only.get(("projection", normalized["versionId"])) == "committed"
            ):
                return
        parsed = normalized["content"]
        if len(json.dumps(parsed, separators=(",", ":")).encode()) > WORKSPACE_BYTES:
            raise ValueError("parsed source exceeds the finite workspace allocation")
        if normalized["permission"] != "permitted":
            raise ValueError("source permission unresolved")
        chunks = parsed["chunks"]
        projection_hash = hashlib.sha256(
            json.dumps(
                [
                    {key: chunk[key] for key in ("anchor", "section", "text", "textHash")}
                    for chunk in chunks
                ],
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()

        artifact = None
        if self.files is not None and normalized["raw"] is not None:
            artifact = self.files.publish(normalized["raw"])

        def write(conn):
            # Stage: source — canonical resolution receipt (dedup identity).
            _effect(
                conn,
                claim["id"],
                "source",
                source_id,
                "committed",
                evidence=normalized["identityHash"],
            )
            # Stage: control — canonical paper/version identity, staged ineligible.
            conn.execute(
                "INSERT INTO corpus.paper(id,title,authors,published_on,metadata) "
                "VALUES(%s,%s,%s,%s,%s) ON CONFLICT(id) DO NOTHING",
                (
                    normalized["paperId"],
                    normalized["title"],
                    Jsonb(normalized["authors"]),
                    normalized["publishedOn"],
                    Jsonb({"canonicalReferences": normalized["references"]}),
                ),
            )
            metadata = conn.execute(
                "SELECT title,authors FROM corpus.paper WHERE id=%s FOR UPDATE",
                (normalized["paperId"],),
            ).fetchone()
            if metadata != {"title": normalized["title"], "authors": normalized["authors"]}:
                raise ValueError("immutable paper metadata conflict")
            existing = conn.execute(
                "SELECT * FROM corpus.version WHERE id=%s FOR UPDATE",
                (normalized["versionId"],),
            ).fetchone()
            if existing:
                if (
                    existing["paper_id"] != normalized["paperId"]
                    or existing["version_label"] != normalized["versionLabel"]
                    or existing["source_hash"] != normalized["contentHash"]
                ):
                    raise ValueError("immutable source identity conflict")
                if existing["content"] == parsed and existing["eligible"]:
                    # Duplicate/re-imported record: the same canonical identity is
                    # acknowledged once, with no new searchable chunks.
                    for stage, evidence in (
                        ("control", normalized["identityHash"]),
                        ("content", normalized["contentHash"]),
                        ("projection", projection_hash),
                    ):
                        _effect(
                            conn,
                            claim["id"],
                            stage,
                            normalized["versionId"],
                            "committed",
                            evidence=evidence,
                        )
                    _claim_batch(
                        conn,
                        claim["id"],
                        normalized["versionId"],
                        projection_hash,
                        len(chunks),
                    )
                    return
                if existing["content"] != parsed and existing["eligible"]:
                    raise ValueError("immutable parsed content conflict")
            _effect(
                conn,
                claim["id"],
                "control",
                normalized["versionId"],
                "committed",
                evidence=normalized["identityHash"],
            )
            # Stage: content — parsed representation and provenance.
            provenance = dict(
                normalized["provenance"],
                byteLength=artifact.size if artifact else len(normalized["raw"] or b""),
                permission="permitted",
                compatibilityRevision=PROJECTION_COMPATIBILITY,
                projectionHash=projection_hash,
            )
            row = conn.execute(
                "INSERT INTO corpus.version(id,paper_id,source_url,source_hash,version_label,"
                "private_path,eligible,purpose,provenance,content) "
                "VALUES(%s,%s,%s,%s,%s,%s,false,'local-research',%s,%s) "
                "ON CONFLICT (id) DO UPDATE SET provenance=excluded.provenance,"
                "content=excluded.content WHERE corpus.version.eligible=false "
                "RETURNING *",
                (
                    normalized["versionId"],
                    normalized["paperId"],
                    normalized["sourceUrl"],
                    normalized["contentHash"],
                    normalized["versionLabel"],
                    artifact.name if artifact else "fixture-inline",
                    Jsonb(provenance),
                    Jsonb(parsed),
                ),
            ).fetchone()
            _effect(
                conn,
                claim["id"],
                "content",
                normalized["versionId"],
                "committed",
                evidence=normalized["contentHash"],
            )
            # Stage: projection — derived chunks with their batch receipt.
            conn.execute(
                "DELETE FROM corpus.projection WHERE version_id=%s", (row["id"],)
            )
            for ordinal, chunk in enumerate(chunks):
                conn.execute(
                    "INSERT INTO corpus.projection(version_id,ordinal,content_hash,anchor,"
                    "section,text_content,embedding,vector_policy) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        row["id"],
                        ordinal,
                        normalized["contentHash"],
                        chunk["anchor"],
                        chunk["section"],
                        chunk["text"],
                        chunk.get("embedding"),
                        chunk.get("vectorPolicy"),
                    ),
                )
            _claim_batch(
                conn,
                claim["id"],
                normalized["versionId"],
                projection_hash,
                len(chunks),
            )
            _effect(
                conn,
                claim["id"],
                "projection",
                normalized["versionId"],
                "committed",
                evidence=projection_hash,
            )

        self.transactions.run("corpus", write)

    def _record_failure(self, claim: dict, stage: str, subject: str, code: str) -> None:
        def write(conn):
            row = conn.execute(
                "SELECT * FROM corpus.run WHERE id=%s", (claim["id"],)
            ).fetchone()
            if not row or row["state"] in ("completed", "failed"):
                return
            conn.execute(
                "INSERT INTO corpus.run_effect(run_id,stage,subject,state,error_code) "
                "VALUES(%s,%s,%s,'failed',%s) ON CONFLICT (run_id,stage,subject) DO UPDATE "
                "SET state='failed',error_code=excluded.error_code,revision="
                "corpus.run_effect.revision+1,recorded_at=clock_timestamp()",
                (claim["id"], stage, subject, code[:64]),
            )

        self.transactions.run("corpus", write)

    def _finish(self, claim: dict, *, failed: bool) -> dict:
        run_id = claim["id"]

        def write(conn):
            conn.execute("SELECT singleton FROM corpus.publication FOR UPDATE")
            run = conn.execute(
                "SELECT * FROM corpus.run WHERE id=%s FOR UPDATE", (run_id,)
            ).fetchone()
            if not run or run["state"] in ("completed", "failed"):
                return {"state": run["state"] if run else "missing", "runId": str(run_id)}
            effects = conn.execute(
                "SELECT stage,subject,state,evidence_hash FROM corpus.run_effect "
                "WHERE run_id=%s ORDER BY stage,subject LIMIT %s",
                (run_id, MAX_EFFECTS_PER_RUN + 1),
            ).fetchall()
            outstanding = [e for e in effects if e["state"] != "committed"]
            if failed or outstanding:
                for effect in outstanding:
                    if effect["state"] == "pending":
                        conn.execute(
                            "UPDATE corpus.run_effect SET state='unknown',"
                            "error_code=coalesce(error_code,'interrupted') "
                            "WHERE run_id=%s AND stage=%s AND subject=%s",
                            (run_id, effect["stage"], effect["subject"]),
                        )
                conn.execute(
                    "UPDATE corpus.run SET state='failed',revision=gen_random_uuid() "
                    "WHERE id=%s",
                    (run_id,),
                )
                return {
                    "state": "failed",
                    "runId": str(run_id),
                    "outstanding": [
                        {"stage": e["stage"], "subject": e["subject"], "state": e["state"]}
                        for e in effects
                        if e["state"] != "committed"
                    ],
                }
            # Publication: verified generation publish or refuse.
            versions = sorted(
                {
                    e["subject"]
                    for e in effects
                    if e["stage"] == "content" and e["state"] == "committed"
                }
            )
            compatibility_ok = run["compatibility_revision"] == PROJECTION_COMPATIBILITY
            if not versions or not compatibility_ok:
                conn.execute(
                    "UPDATE corpus.run SET state='failed',revision=gen_random_uuid() "
                    "WHERE id=%s",
                    (run_id,),
                )
                return {
                    "state": "failed",
                    "runId": str(run_id),
                    "outstanding": [
                        {
                            "stage": "publication",
                            "subject": "verification",
                            "state": "failed",
                        }
                    ],
                }
            generation = uuid4()
            manifest = _manifest(conn, versions)
            conn.execute(
                "INSERT INTO corpus.generation(id,manifest_hash,compatibility_revision) "
                "VALUES(%s,%s,%s)",
                (generation, manifest, run["compatibility_revision"]),
            )
            batches = conn.execute(
                "SELECT count(*) AS count FROM corpus.projection_batch "
                "WHERE generation_id=%s",
                (run_id,),
            ).fetchone()["count"]
            receipts = conn.execute(
                "SELECT count(*) AS count FROM corpus.run_effect WHERE run_id=%s "
                "AND stage='projection' AND state='committed'",
                (run_id,),
            ).fetchone()["count"]
            if batches != receipts:
                conn.execute(
                    "UPDATE corpus.generation SET state='failed' WHERE id=%s", (generation,)
                )
                conn.execute(
                    "UPDATE corpus.run SET state='failed',revision=gen_random_uuid() "
                    "WHERE id=%s",
                    (run_id,),
                )
                return {
                    "state": "failed",
                    "runId": str(run_id),
                    "reasonKey": "batch-receipts-missing",
                }
            conn.execute(
                "UPDATE corpus.generation SET state='verified' WHERE id=%s", (generation,)
            )
            publication = conn.execute(
                "SELECT * FROM corpus.publication WHERE singleton FOR UPDATE"
            ).fetchone()
            updated = conn.execute(
                "UPDATE corpus.publication SET generation_id=%s,published_generation=%s,"
                "revision=gen_random_uuid(),manifest_hash=%s,published_at=clock_timestamp() "
                "WHERE singleton AND generation_id=%s RETURNING revision",
                (generation, generation, manifest, publication["generation_id"]),
            ).fetchone()
            if updated is None:
                # A competing publication won; the previous generation remains.
                conn.execute(
                    "UPDATE corpus.generation SET state='failed' WHERE id=%s", (generation,)
                )
                conn.execute(
                    "UPDATE corpus.run SET state='failed',revision=gen_random_uuid() "
                    "WHERE id=%s",
                    (run_id,),
                )
                return {
                    "state": "failed",
                    "runId": str(run_id),
                    "reasonKey": "publication-cas-conflict",
                }
            # Only now do the covered versions become eligible for readers.
            for version in versions:
                conn.execute(
                    "UPDATE corpus.version SET eligible=true WHERE id=%s AND NOT eligible",
                    (version,),
                )
            conn.execute(
                "UPDATE corpus.generation SET state='published' WHERE id=%s", (generation,)
            )
            _effect(
                conn,
                run_id,
                "publication",
                str(generation),
                "committed",
                evidence=manifest,
            )
            watermark = {
                "generationId": str(generation),
                "manifestHash": manifest,
                "publishedAt": datetime.now(UTC).isoformat(),
            }
            conn.execute(
                "UPDATE corpus.run SET state='completed',watermark=%s,"
                "revision=gen_random_uuid(),dispatch_pending=false WHERE id=%s",
                (Jsonb(watermark), run_id),
            )
            return {"state": "completed", "runId": str(run_id), "generationId": str(generation)}

        return self.transactions.run("corpus", write)

    # --- W1 read ---------------------------------------------------------------

    def read_run(self, authority: Authority, run_id: UUID) -> dict:
        def read(conn):
            guard(conn, authority)
            self._require_maintenance(conn, authority)
            row = conn.execute(
                "SELECT * FROM corpus.run WHERE id=%s", (UUID(str(run_id)),)
            ).fetchone()
            if not row:
                raise PermissionError("run unavailable")
            return self._run_view(conn, row)

        return self.transactions.run("corpus", read)

    def _run_view(self, conn, row) -> dict:
        effects = conn.execute(
            "SELECT stage,subject,state,evidence_hash,error_code,recorded_at "
            "FROM corpus.run_effect WHERE run_id=%s ORDER BY stage,subject "
            "LIMIT %s",
            (row["id"], MAX_EFFECTS_PER_RUN + 1),
        ).fetchall()
        if len(effects) > MAX_EFFECTS_PER_RUN:
            raise ValueError("run effects exceed the finite inspection allocation")
        return {
            "runId": str(row["id"]),
            "operation": row["operation"],
            "state": row["state"],
            "revision": str(row["revision"]),
            "attempts": row["attempts"],
            "retryOf": str(row["retry_of"]) if row["retry_of"] else None,
            "acceptedAt": row["accepted_at"].isoformat(),
            "completedAt": row["completed_at"].isoformat() if row["completed_at"] else None,
            "watermark": row["watermark"],
            "inputManifestHash": row["input_manifest_hash"],
            "effects": [
                {
                    "stage": effect["stage"],
                    "subject": effect["subject"],
                    "state": effect["state"],
                    "evidenceHash": effect["evidence_hash"],
                    "error": effect["error_code"],
                }
                for effect in effects
            ],
        }

    # --- W3 source change ------------------------------------------------------

    def record_change(self, authority: Authority, change: dict) -> dict:
        """Persist an authoritative eligibility revision and an ordered change fact."""
        if not isinstance(change, dict):
            raise ValueError("change must be a bounded object")
        kind = change.get("changeKind")
        if kind not in CHANGE_KINDS:
            raise ValueError("unknown source-change kind")
        disposition = change.get("disposition")
        if disposition not in ("eligible", "withdrawn", "restricted", "unavailable"):
            raise ValueError("unknown eligibility disposition")
        require_policy(change.get("policy"), ELIGIBILITY_POLICY, name="eligibility policy")
        paper_id = change.get("paperId")
        version_id = change.get("versionId")
        if not isinstance(paper_id, str) or not 1 <= len(paper_id) <= 160:
            raise ValueError("paper identity outside finite policy")
        if version_id is not None and (
            not isinstance(version_id, str) or not 1 <= len(version_id) <= 160
        ):
            raise ValueError("version identity outside finite policy")

        def write(conn):
            guard(conn, authority)
            self._require_maintenance(conn, authority)
            paper = conn.execute(
                "SELECT * FROM corpus.paper WHERE id=%s FOR UPDATE", (paper_id,)
            ).fetchone()
            if not paper:
                raise ValueError("unknown paper identity")
            if version_id is not None:
                version = conn.execute(
                    "SELECT * FROM corpus.version WHERE id=%s AND paper_id=%s FOR UPDATE",
                    (version_id, paper_id),
                ).fetchone()
                if not version:
                    raise ValueError("unknown version identity")
            conn.execute(
                "SELECT * FROM corpus.change_sequence FOR UPDATE"
            )
            position = conn.execute(
                "UPDATE corpus.change_sequence SET fact_position=fact_position+1 "
                "WHERE singleton RETURNING fact_position"
            ).fetchone()["fact_position"]
            revision = conn.execute(
                "SELECT gen_random_uuid() AS revision"
            ).fetchone()["revision"]
            scope = "id=%s" if version_id is not None else "paper_id=%s"
            scope_value = version_id if version_id is not None else paper_id
            if disposition == "withdrawn":
                conn.execute(
                    "UPDATE corpus.paper SET withdrawn=true,revision=gen_random_uuid() "
                    "WHERE id=%s",
                    (paper_id,),
                )
                conn.execute(
                    "UPDATE corpus.version SET eligible=false,eligibility_revision=%s "
                    f"WHERE paper_id=%s AND ({scope})",
                    (revision, paper_id, scope_value),
                )
                conn.execute(
                    "DELETE FROM corpus.projection WHERE version_id IN "
                    "(SELECT id FROM corpus.version WHERE paper_id=%s)",
                    (paper_id,),
                )
            elif disposition in ("restricted", "unavailable"):
                conn.execute(
                    "UPDATE corpus.version SET eligible=false,eligibility_revision=%s "
                    f"WHERE paper_id=%s AND ({scope})",
                    (revision, paper_id, scope_value),
                )
            elif disposition == "eligible":
                if version_id is None:
                    raise ValueError("eligibility grant requires an exact version")
                conn.execute(
                    "UPDATE corpus.version SET eligible=true,eligibility_revision=%s "
                    "WHERE id=%s",
                    (revision, version_id),
                )
            fact = conn.execute(
                "INSERT INTO corpus.change_fact(id,paper_id,version_id,change_kind,"
                "eligibility_revision,fact_position,detail) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING *",
                (
                    uuid4(),
                    paper_id,
                    version_id,
                    kind,
                    revision,
                    position,
                    Jsonb(
                        {
                            "disposition": disposition,
                            "reasonKey": str(change.get("reasonKey", ""))[:64],
                        }
                    ),
                ),
            ).fetchone()
            _advance_manifest(conn)
            return {
                "factId": str(fact["id"]),
                "position": fact["fact_position"],
                "eligibilityRevision": str(fact["eligibility_revision"]),
                "paperId": paper_id,
                "versionId": version_id,
                "changeKind": kind,
                "disposition": disposition,
            }

        return self.transactions.run("corpus", write)

    def read_changes(self, after: int, limit: int = 50) -> list[dict]:
        after = bounded_int(after, low=0, high=2**62, name="change boundary")
        limit = bounded_int(limit, low=1, high=100, name="change page bound")

        def read(conn):
            rows = conn.execute(
                "SELECT * FROM corpus.read_change_facts(%s,%s)", (after, limit)
            ).fetchall()
            return [
                {
                    "factId": str(row["fact_id"]),
                    "paperId": row["paper_id"],
                    "versionId": row["version_id"],
                    "changeKind": row["change_kind"],
                    "eligibilityRevision": str(row["eligibility_revision"]),
                    "position": row["fact_position"],
                    "recordedAt": row["recorded_at"].isoformat(),
                    "detail": row["detail"],
                }
                for row in rows
            ]

        return self.transactions.run("corpus", read)

    def restore_replay(self, marker: str, versions: list[str]) -> dict:
        """Restore rehearsal: replay current withdrawal boundaries before serving.

        A restored snapshot never resurrects prohibited content: every version in
        the restored set is re-checked against the authoritative eligibility and
        left unservable when the current revision forbids it.
        """
        if not isinstance(marker, str) or not 1 <= len(marker) <= 160:
            raise ValueError("quarantine marker outside finite policy")
        if (
            not isinstance(versions, list)
            or not 1 <= len(versions) <= 64
            or any(not isinstance(item, str) or not 1 <= len(item) <= 160 for item in versions)
        ):
            raise ValueError("restored version set outside finite policy")

        def write(conn):
            conn.execute(
                "INSERT INTO corpus.quarantine(marker,target) VALUES(%s,'restore-rehearsal') "
                "ON CONFLICT (marker) DO NOTHING",
                (marker,),
            )
            results = []
            for version in sorted(versions):
                row = conn.execute(
                    "SELECT * FROM corpus.current_eligibility(%s)", (version,)
                ).fetchone()
                disposition = row["disposition"]
                results.append(
                    {
                        "versionId": version,
                        "disposition": disposition,
                        "servable": disposition == "available",
                        "eligibilityRevision": str(row["eligibility_revision"])
                        if row["eligibility_revision"]
                        else None,
                    }
                )
            return {
                "marker": marker,
                "replayed": len(results),
                "refused": sum(1 for item in results if not item["servable"]),
                "versions": results,
            }

        return self.transactions.run("corpus", write)

    # --- helpers ---------------------------------------------------------------

    @staticmethod
    def _require_maintenance(conn, authority: Authority) -> None:
        row = conn.execute(
            "SELECT 1 FROM corpus.maintenance_actor WHERE account_id=%s",
            (authority.account_id,),
        ).fetchone()
        if row is None:
            raise PermissionError("corpus maintenance authority required")


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _safe_error_code(error: ValueError) -> str:
    return str(error)[:64] or "invalid-source"


def _effect(conn, run_id, stage, subject, state, *, evidence=None, error=None) -> None:
    conn.execute(
        "INSERT INTO corpus.run_effect(run_id,stage,subject,state,evidence_hash,error_code) "
        "VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT (run_id,stage,subject) DO UPDATE SET "
        "state=excluded.state,evidence_hash=excluded.evidence_hash,"
        "error_code=excluded.error_code,revision=corpus.run_effect.revision+1,"
        "recorded_at=clock_timestamp()",
        (run_id, stage, subject, state, evidence, error),
    )


def _batch_id(run_id: UUID, version_id: str) -> UUID:
    """Deterministic batch identity: duplicate batch id and hash acknowledge once."""
    return uuid5(NAMESPACE_URL, f"u3-batch:{run_id}:{version_id}")


def _claim_batch(conn, run_id: UUID, version_id: str, projection_hash: str, chunks: int) -> None:
    """Idempotent batch receipt: the same id and hash acknowledge once, a
    changed hash conflicts."""
    batch_id = _batch_id(run_id, version_id)
    receipt = {
        "batchId": str(batch_id),
        "versionId": version_id,
        "chunks": chunks,
        "projectionHash": projection_hash,
    }
    claimed = conn.execute(
        "INSERT INTO corpus.projection_batch(id,generation_id,batch_hash,receipt) "
        "VALUES(%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING RETURNING id",
        (batch_id, run_id, projection_hash, Jsonb(receipt)),
    ).fetchone()
    if claimed is None:
        prior = conn.execute(
            "SELECT batch_hash FROM corpus.projection_batch WHERE id=%s", (batch_id,)
        ).fetchone()
        if prior["batch_hash"] != projection_hash:
            raise ValueError("projection batch hash conflict")


def _normalize_source(record: dict) -> dict:
    """Validate one provider record into canonical, bounded fields."""
    required = ("paperId", "versionLabel", "title", "authors", "sourceUrl", "identity", "content")
    if not isinstance(record, dict) or any(key not in record for key in required):
        raise ValueError("malformed source record")
    paper_id, label = record["paperId"], record["versionLabel"]
    if not isinstance(paper_id, str) or not 1 <= len(paper_id) <= 160:
        raise ValueError("paper identity outside finite policy")
    if not isinstance(label, str) or not 1 <= len(label) <= 64:
        raise ValueError("version label outside finite policy")
    if not isinstance(record["title"], str) or not 1 <= len(record["title"]) <= 400:
        raise ValueError("title outside finite policy")
    authors = record["authors"]
    if (
        not isinstance(authors, list)
        or not 1 <= len(authors) <= 64
        or any(not isinstance(author, str) or not 1 <= len(author) <= 200 for author in authors)
    ):
        raise ValueError("authors outside finite policy")
    source_url = record["sourceUrl"]
    if not isinstance(source_url, str) or not source_url.startswith(("https://", "http://")):
        raise ValueError("source URL outside finite policy")
    content = record["content"]
    if (
        not isinstance(content, dict)
        or not isinstance(content.get("document"), dict)
        or not isinstance(content.get("chunks"), list)
        or not 1 <= len(content["chunks"]) <= 256
    ):
        raise ValueError("parsed document model missing")
    for chunk in content["chunks"]:
        if (
            not isinstance(chunk, dict)
            or not isinstance(chunk.get("anchor"), str)
            or not 1 <= len(chunk["anchor"]) <= 100
            or not isinstance(chunk.get("section"), str)
            or not isinstance(chunk.get("text"), str)
            or not chunk["text"].strip()
            or not isinstance(chunk.get("textHash"), str)
            or not _is_sha256(chunk["textHash"])
            or hashlib.sha256(chunk["text"].encode()).hexdigest() != chunk["textHash"]
        ):
            raise ValueError("malformed projection chunk")
    identity = record["identity"]
    if not isinstance(identity, dict) or not identity.get("system") or not identity.get("recordId"):
        raise ValueError("source identity incomplete")
    version_id = f"{paper_id}:{label}"
    if len(version_id) > 160:
        raise ValueError("canonical version identity outside finite policy")
    raw = record.get("raw")
    if raw is not None and not isinstance(raw, bytes):
        raise ValueError("raw source must be bytes")
    content_hash = hashlib.sha256(
        json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    identity_hash = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "paperId": paper_id,
        "versionId": version_id,
        "versionLabel": label,
        "title": record["title"],
        "authors": authors,
        "sourceUrl": source_url,
        "publishedOn": record.get("publishedOn"),
        "references": [identity],
        "identityHash": identity_hash,
        "contentHash": content_hash,
        "permission": record.get("permission", "unresolved"),
        "provenance": dict(
            identity,
            checksum=content_hash,
            retrievedAt=record.get("retrievedAt"),
        ),
        "content": content,
        "raw": raw,
    }


def _manifest(conn, versions: list[str]) -> str:
    rows = conn.execute(
        "SELECT v.id,v.source_hash,v.eligibility_revision,v.eligible,p.withdrawn,"
        "count(c.ordinal) AS chunks FROM corpus.version v "
        "JOIN corpus.paper p ON p.id=v.paper_id LEFT JOIN corpus.projection c "
        "ON c.version_id=v.id GROUP BY v.id,p.withdrawn ORDER BY v.id"
    ).fetchall()
    return hashlib.sha256(
        json.dumps(rows, sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()


def _advance_manifest(conn) -> None:
    """Eligibility changes alter the observable publication; record the boundary."""
    manifest = _manifest(conn, [])
    conn.execute(
        "UPDATE corpus.publication SET revision=gen_random_uuid(),manifest_hash=%s,"
        "published_at=clock_timestamp() WHERE singleton",
        (manifest,),
    )
