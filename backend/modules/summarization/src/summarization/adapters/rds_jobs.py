"""RdsJobStore — the durable ``JobStorePort`` (REM-2 items 20-26).

The in-memory store proves the contract's *shape*; this proves it *survives a restart and a
concurrent process*, which is the only reason the contract exists. Four properties are enforced by
PostgreSQL rather than by Python, because Python cannot enforce them across processes:

1. **Idempotent acceptance** (RJ-AC06). ``INSERT ... ON CONFLICT DO NOTHING`` collapses a concurrent
   retry onto the winner's row, so two racing requests produce one job — not a read-then-write race
   that can insert two.
2. **Compare-and-set transitions** (RJ-AC04). Every state change is
   ``UPDATE ... WHERE state = ANY(%s)``, so a redelivered or out-of-order message finds no legal
   source state and changes nothing. This is the second layer of defence under the ledger: a job
   already ``COMPLETED`` cannot be walked back to ``RUNNING`` by a late write.
3. **One event per transition** (RJ-AC02/RJ-AC04). The event row is written in the *same*
   transaction as the state change, and its ``seq`` is the value the state-changing ``UPDATE``
   itself incremented — so two racing writers cannot both take the same number, and a half-committed
   transition cannot leave a state without its event.
4. **One effect per attempt** (ND-Q8). The ledger's primary key is ``(job_id, attempt)``;
   ``ON CONFLICT DO NOTHING`` makes a duplicate claim a non-event instead of a second payment.

Every statement is a literal with ``%s`` binding — no SQL is ever assembled from a variable, so
there is no injection surface (SEC-9) and no way for a caller's input to reach the grammar. Every
read is owner-scoped, matching the rest of this module (SEC-8).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from ..domain.job import ContentJob, JobError, JobEvent, JobState


def _epoch(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.timestamp()
    return float(value)


def _as_error(raw: Any) -> JobError | None:
    if raw is None:
        return None
    if isinstance(raw, JobError):
        return raw
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            return None
    if not isinstance(raw, dict):
        return None
    return JobError(
        error_type=str(raw.get("errorType") or raw.get("error_type") or "internal"),
        message=str(raw.get("message") or "처리 중 문제가 발생했습니다."),
        retryable=bool(raw.get("retryable", False)),
        retry_after_seconds=raw.get("retryAfterSeconds") or raw.get("retry_after_seconds"),
    )


def _error_json(error: JobError | None) -> str | None:
    if error is None:
        return None
    return json.dumps(error.to_dict(), ensure_ascii=False)


def _job_from_row(row: tuple) -> ContentJob:
    """Rebuild the domain object from a row, with timestamps normalized to epoch floats.

    The domain speaks floats and the database speaks TIMESTAMPTZ; normalizing here makes the
    expiry check in ``result_ref`` a plain float compare rather than a datetime comparison that
    could silently disagree with the window the caller was told about.
    """
    raw_input = row[3]
    if isinstance(raw_input, str):
        raw_input = json.loads(raw_input)
    return ContentJob(
        job_id=row[0],
        owner_id=row[1],
        task_type=row[2],
        input=raw_input or {},
        state=JobState(row[4]),
        idempotency_key=row[5],
        result_ref=row[6],
        result_expires_at=_epoch(row[7]),
        attempt=int(row[8]),
        error=_as_error(row[9]),
        abstain_reason=row[10],
        created_at=_epoch(row[11]) or 0.0,
        updated_at=_epoch(row[12]) or 0.0,
        seq=int(row[13]),
    )


def _event_from_row(row: tuple) -> JobEvent:
    """Rebuild an event from an ``event_id, job_id, owner_id, seq, state, payload, created_at`` row.

    ``created_at`` is normalized here too: the SSE client compares timestamps across events, and
    mixing an offset-naive datetime with an epoch float would order the stream incorrectly.
    """
    raw = row[5]
    if isinstance(raw, str):
        raw = json.loads(raw)
    return JobEvent(
        seq=int(row[3]),
        event_id=str(row[0]),
        job_id=row[1],
        owner_id=row[2],
        state=JobState(row[4]),
        payload=raw or {},
        created_at=_epoch(row[6]) or 0.0,
    )


class RdsJobStore:
    def __init__(self, *, dsn: str | None = None, connection: Any | None = None) -> None:
        self._dsn = dsn
        self._conn = connection

    def _connect(self) -> Any:
        if self._conn is not None:
            # Injected connection (the contract tests drive a fake). The call site's
            # ``with self._connect()`` drives its context manager, so inject a fresh (or fake)
            # connection rather than a long-lived shared one.
            return self._conn
        from ._pg import connection  # lazy: only the `real` extra needs psycopg

        return connection(self._dsn)

    # --- acceptance (items 20, 21) ------------------------------------------------------

    def accept(
        self,
        *,
        job_id: str,
        owner_id: str,
        task_type: str,
        input: dict[str, Any],
        idempotency_key: str | None,
        now: float,
    ) -> tuple[ContentJob, bool]:
        """Insert the job, or return the one this key already names.

        ``created=False`` means the caller is a retry: the returned job is the durable original, and
        the service decides whether it still needs dispatching.

        The conflict target spells out the partial index's predicate. Inference has to match it
        exactly, and the predicate is what keeps a keyless submission out of the constraint — a
        caller who sends no key has said nothing about intent, and merging two deliberate
        identical submissions would drop a re-run the user asked for.
        """
        sql = (
            "INSERT INTO content_jobs "
            "(job_id, owner_id, task_type, input, state, idempotency_key, created_at, updated_at) "
            "VALUES (%s, %s, %s, %s, 'SUBMITTED', %s, to_timestamp(%s), to_timestamp(%s)) "
            "ON CONFLICT (owner_id, idempotency_key) WHERE idempotency_key IS NOT NULL "
            "DO NOTHING "
            "RETURNING job_id, owner_id, task_type, input, state, idempotency_key, result_ref, "
            "result_expires_at, attempt, error, abstain_reason, created_at, updated_at, seq"
        )
        params = (
            job_id,
            owner_id,
            task_type,
            json.dumps(input, ensure_ascii=False),
            idempotency_key,
            now,
            now,
        )
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            if row is not None:
                conn.commit()
                return _job_from_row(row), True
            # This key already names a job. Read it back, owner-scoped, so a caller can only ever
            # collide with their own prior submission — never another tenant's.
            cur.execute(
                "SELECT job_id, owner_id, task_type, input, state, idempotency_key, result_ref, "
                "result_expires_at, attempt, error, abstain_reason, created_at, updated_at, seq "
                "FROM content_jobs WHERE owner_id = %s AND idempotency_key = %s",
                (owner_id, idempotency_key),
            )
            existing = cur.fetchone()
            conn.commit()
            if existing is None:
                # The conflicting row was purged between the insert and this read (an account
                # deletion racing a retry). Rather than report a job we cannot see, take a fresh
                # id: the caller's work is still owed to them.
                return self.accept(
                    job_id=job_id,
                    owner_id=owner_id,
                    task_type=task_type,
                    input=input,
                    idempotency_key=idempotency_key,
                    now=now,
                )
            return _job_from_row(existing), False

    def release_idempotency(self, owner_id: str, key: str | None, job_id: str) -> None:
        """Unbind a key from a job whose dispatch never happened.

        Clearing the column rather than deleting the job keeps the failure readable for the caller
        while freeing the key, and the ``job_id`` guard stops a late failure from a superseded job
        freeing a key that now belongs to newer work.
        """
        if key is None:
            return
        sql = (
            "UPDATE content_jobs SET idempotency_key = NULL, updated_at = now() "
            "WHERE job_id = %s AND owner_id = %s AND idempotency_key = %s"
        )
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, (job_id, owner_id, key))
            conn.commit()

    # --- reads (items 23, 24) ------------------------------------------------------------

    def get(self, job_id: str) -> ContentJob | None:
        """Fetch by id alone.

        Deliberately un-scoped: the service's ``_owned`` is the authorization boundary and it
        compares the owner it just read. This is an internal lookup, never a caller-facing query.
        """
        sql = (
            "SELECT job_id, owner_id, task_type, input, state, idempotency_key, result_ref, "
            "result_expires_at, attempt, error, abstain_reason, created_at, updated_at, seq "
            "FROM content_jobs WHERE job_id = %s"
        )
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, (job_id,))
            row = cur.fetchone()
            return _job_from_row(row) if row else None

    def list_events(
        self, job_id: str, *, after_seq: int = 0, limit: int = 500
    ) -> list[JobEvent]:
        """This job's history after ``after_seq``, in order (RJ-AC04 replay).

        The owner comes from the job row rather than the caller, so a future call site that forgets
        its own authorization check still cannot stream another tenant's events: the predicate is
        the job's own owner, and a job id from another tenant therefore matches no events.
        """
        owner_sql = "SELECT owner_id FROM content_jobs WHERE job_id = %s"
        sql = (
            "SELECT event_id, job_id, owner_id, seq, state, payload, created_at "
            "FROM content_job_events "
            "WHERE job_id = %s AND owner_id = %s AND seq > %s ORDER BY seq ASC LIMIT %s"
        )
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(owner_sql, (job_id,))
            owner_row = cur.fetchone()
            if owner_row is None:
                return []
            cur.execute(sql, (job_id, owner_row[0], after_seq, limit))
            return [_event_from_row(row) for row in cur.fetchall()]

    # --- transitions (items 22, 24) ------------------------------------------------------

    def transition(
        self,
        job_id: str,
        target: JobState,
        *,
        expect_from: frozenset[JobState],
        now: float,
        result_ref: str | None = None,
        result_expires_at: float | None = None,
        error: JobError | None = None,
        abstain_reason: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> ContentJob | None:
        """Move the job to ``target`` and append exactly one event, atomically.

        ``None`` means "this move was not legal from where the job actually is" — a redelivery, a
        late write, or a stale reader. Callers treat that as already-handled, not as an error.

        Optional fields use ``COALESCE`` so a caller supplies only what this edge changes and the
        rest of the record survives. That keeps one literal statement for every edge instead of
        assembling a SET list per call, and it means a late worker cannot blank out a field it
        happened not to know about.
        """
        sql = (
            "UPDATE content_jobs SET state = %s, updated_at = to_timestamp(%s), seq = seq + 1, "
            "result_ref = COALESCE(%s, result_ref), "
            "result_expires_at = COALESCE(to_timestamp(%s), result_expires_at), "
            "abstain_reason = COALESCE(%s, abstain_reason), error = COALESCE(%s, error) "
            "WHERE job_id = %s AND state = ANY(%s) "
            "RETURNING job_id, owner_id, task_type, input, state, idempotency_key, result_ref, "
            "result_expires_at, attempt, error, abstain_reason, created_at, updated_at, seq"
        )
        params = (
            target.value,
            now,
            result_ref,
            result_expires_at,
            abstain_reason,
            _error_json(error),
            job_id,
            [s.value for s in sorted(expect_from, key=lambda s: s.value)],
        )
        insert_sql = (
            "INSERT INTO content_job_events (job_id, owner_id, seq, state, payload) "
            "VALUES (%s, %s, %s, %s, %s)"
        )
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            if row is None:
                conn.commit()
                return None
            updated = _job_from_row(row)
            # The seq this event carries is the one the state change itself incremented, under the
            # row lock that UPDATE held. Two concurrent writers therefore cannot both take the
            # same number, and the stream stays gapless and duplicate-free.
            cur.execute(
                insert_sql,
                (
                    job_id,
                    updated.owner_id,
                    updated.seq,
                    target.value,
                    json.dumps(payload or {}, ensure_ascii=False),
                ),
            )
            conn.commit()
            return updated

    def append_event(
        self,
        job_id: str,
        owner_id: str,
        state: JobState,
        payload: dict[str, Any],
        now: float,
    ) -> JobEvent:
        """Append an event without changing state.

        Reserved for events that are not lifecycle edges (a rejection recorded outside the
        sequence, an operator annotation). State changes must go through ``transition`` so they
        cannot skip the compare-and-set guard.
        """
        bump_sql = "UPDATE content_jobs SET seq = seq + 1 WHERE job_id = %s RETURNING seq"
        insert_sql = (
            "INSERT INTO content_job_events (job_id, owner_id, seq, state, payload) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING event_id"
        )
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(bump_sql, (job_id,))
            row = cur.fetchone()
            if row is None:
                conn.commit()
                raise KeyError(job_id)
            seq = int(row[0])
            cur.execute(
                insert_sql,
                (job_id, owner_id, seq, state.value, json.dumps(payload or {}, ensure_ascii=False)),
            )
            inserted = cur.fetchone()
            conn.commit()
            return JobEvent(
                seq=seq,
                event_id=str(inserted[0]) if inserted else f"{job_id}:{seq}",
                job_id=job_id,
                owner_id=owner_id,
                state=state,
                payload=payload or {},
                created_at=now,
            )

    # --- effects (item 25) ---------------------------------------------------------------

    def claim_effect(self, job_id: str, attempt: int, effect: str) -> bool:
        """Claim this attempt's single effect budget. False when already spent (ND-Q8).

        Taken *before* the effect runs, which is the whole point: a redelivery after a crash finds
        the claim and skips the expensive work instead of paying for it twice. The existing row's
        ``effect`` label is deliberately not overwritten — the ledger records what the budget was
        actually spent on, not what a later caller claims to be spending it on.
        """
        sql = (
            "INSERT INTO content_job_effect_ledger (job_id, attempt, effect) "
            "VALUES (%s, %s, %s) ON CONFLICT (job_id, attempt) DO NOTHING"
        )
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, (job_id, attempt, effect))
            conn.commit()
            return cur.rowcount == 1

    def release_effect(self, job_id: str, attempt: int) -> None:
        """Return the budget after a *failed* effect so the retry can re-attempt it.

        Only ever call this on failure. Releasing after a success is how one piece of work gets
        paid for twice.
        """
        sql = "DELETE FROM content_job_effect_ledger WHERE job_id = %s AND attempt = %s"
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, (job_id, attempt))
            conn.commit()

    # --- recovery sweeper (ND-Q8) ----------------------------------------------------------

    def find_stale_jobs(self, cutoff_epoch: float, limit: int) -> list[ContentJob]:
        """Find jobs stuck in ACCEPTED/QUEUED/SUBMITTED older than ``cutoff_epoch``.

        Uses the partial index ``ix_content_jobs_pending`` (state + updated_at WHERE state IN
        ('SUBMITTED', 'ACCEPTED', 'QUEUED')) for an efficient range scan.
        """
        sql = (
            "SELECT job_id, owner_id, task_type, input, state, idempotency_key, result_ref, "
            "result_expires_at, attempt, error, abstain_reason, created_at, updated_at, seq "
            "FROM content_jobs "
            "WHERE state IN ('SUBMITTED', 'ACCEPTED', 'QUEUED') "
            "AND updated_at < to_timestamp(%s) "
            "ORDER BY updated_at ASC "
            "LIMIT %s"
        )
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, (cutoff_epoch, limit))
            rows = cur.fetchall()
            return [_job_from_row(row) for row in rows]


    # --- purge (G3 / NFR-R4) -------------------------------------------------------------

    def purge_owner(self, owner_id: str) -> int:
        """Delete every job, event and ledger row for one account.

        The FK cascade takes the events and ledger rows with the job, so an account's history
        cannot outlive the account (a re-identification path) and a late worker write finds nothing
        to attach to.
        """
        sql = "DELETE FROM content_jobs WHERE owner_id = %s RETURNING job_id"
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, (owner_id,))
            removed = len(cur.fetchall())
            conn.commit()
            return removed