"""RdsJobStore — the durability properties the in-memory store cannot prove.

REM-2 corrective, Phase 5 (items 20–26). The in-memory contract tests prove the job *shape*; these
prove the properties that only exist once the state lives in PostgreSQL and more than one process
can touch it:

  * one key, one job, enforced by the database rather than by a read-then-write;
  * a state change and its event land together or not at all;
  * a redelivered message cannot buy a second effect;
  * no statement is ever assembled from a variable, so no input reaches the SQL grammar.

The adapter takes an injected connection, so these run without a live database by asserting on the
statements and the rows the fake returns. A test that only reads SQL strings proves nothing about
behaviour, so each case drives the real code path through a fake that mimics the two behaviours
that matter: ``ON CONFLICT DO NOTHING`` returns no row, and ``rowcount`` reports whether an INSERT
actually wrote.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from summarization.adapters.rds_jobs import RdsJobStore
from summarization.domain.job import JobError, JobState

_COLS = (
    "job_id, owner_id, task_type, input, state, idempotency_key, result_ref, result_expires_at, "
    "attempt, error, abstain_reason, created_at, updated_at, seq"
)


def _row(
    job_id: str = "j1",
    owner_id: str = "u1",
    state: str = "SUBMITTED",
    *,
    seq: int = 0,
    result_ref: str | None = None,
    result_expires_at: datetime | None = None,
    error: dict | None = None,
    abstain_reason: str | None = None,
    idempotency_key: str | None = None,
    attempt: int = 1,
) -> tuple:
    return (
        job_id,
        owner_id,
        "summarize",
        {"paperId": "2401.1"},
        state,
        idempotency_key,
        result_ref,
        result_expires_at,
        attempt,
        error,
        abstain_reason,
        datetime(2026, 1, 1, tzinfo=UTC),
        datetime(2026, 1, 1, tzinfo=UTC),
        seq,
    )


class _FakeCursor:
    """Replays queued rows per statement, so ``fetchone`` reflects the write's real outcome."""

    def __init__(self, conn: _FakeConn) -> None:
        self._conn = conn
        self.rowcount = 0

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self._conn.statements.append((sql, params))
        scripted = self._conn.scripted.pop(0) if self._conn.scripted else []
        self._rows = list(scripted)
        # An INSERT that reports a row wrote something; DO NOTHING that conflicts wrote nothing.
        self.rowcount = 1 if ("INSERT" in sql and self._rows) else 0

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)


class _FakeConn:
    def __init__(self, scripted: list[list[tuple]] | None = None) -> None:
        self.scripted = scripted or []
        self.statements: list[tuple[str, object]] = []
        self.commits = 0

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def cursor(self):
        return _FakeCursor(self)

    def commit(self):
        self.commits += 1


def _store(*scripted: list[tuple]) -> tuple[RdsJobStore, _FakeConn]:
    """One argument per statement: the rows that statement is scripted to return."""
    conn = _FakeConn([list(rows) for rows in scripted])
    return RdsJobStore(connection=conn), conn


# --- acceptance (items 20, 21 / RJ-AC06) ---------------------------------------------------


def test_accepting_inserts_with_the_partial_unique_index_as_the_conflict_target() -> None:
    store, conn = _store([_row()])

    job, created = store.accept(
        job_id="j1", owner_id="u1", task_type="summarize", input={}, idempotency_key="k", now=1.0
    )

    sql = conn.statements[0][0]
    # The predicate has to be spelled out: PostgreSQL's conflict inference matches the partial
    # index only if the statement carries the same predicate, and getting this wrong would fail at
    # runtime on the very first duplicate — i.e. the exact moment idempotency is needed.
    assert "ON CONFLICT (owner_id, idempotency_key) WHERE idempotency_key IS NOT NULL" in sql
    assert "DO NOTHING" in sql
    assert created is True
    assert job.state is JobState.SUBMITTED


def test_a_conflicting_key_returns_the_winner_instead_of_inserting_a_second_job() -> None:
    # INSERT ... DO NOTHING returns no row; the adapter then reads the job this key already names.
    store, conn = _store([], [_row(job_id="original", state="RUNNING", seq=3, idempotency_key="k")])

    job, created = store.accept(
        job_id="j-new", owner_id="u1", task_type="summarize", input={}, idempotency_key="k", now=1.0
    )

    assert created is False
    assert job.job_id == "original"
    assert job.state is JobState.RUNNING


def test_the_read_back_after_a_conflict_is_owner_scoped() -> None:
    # Reading the winner by key alone would hand a caller another tenant's job whenever their key
    # happened to collide. The owner is part of the predicate, not an afterthought.
    store, conn = _store([], [_row(job_id="original", idempotency_key="k")])

    store.accept(
        job_id="j-new", owner_id="u1", task_type="summarize", input={}, idempotency_key="k", now=1.0
    )

    read_sql, read_params = conn.statements[1]
    assert "WHERE owner_id = %s AND idempotency_key = %s" in read_sql
    assert read_params == ("u1", "k")


def test_no_statement_ever_embeds_a_value_in_the_sql() -> None:
    # SEC-9. If any of this ever concatenates a value into the query text, that value reaches the
    # grammar; keeping every one of them in %s params is the only version of this adapter that is
    # safe to reason about.
    store, conn = _store([_row(state="RUNNING", seq=2)])

    store.transition(
        "j1",
        JobState.COMPLETED,
        expect_from=frozenset({JobState.RUNNING}),
        now=2.0,
        result_ref="summary/2401.1/v1",
    )

    for sql, params in conn.statements:
        # The caller's own values — the paper id and the job id — must appear only in the params.
        assert "'2401.1" not in sql
        assert "summary/2401.1/v1" not in sql
        assert params is not None


# --- transitions (items 22, 24 / RJ-AC04) ---------------------------------------------------


def test_a_transition_is_a_compare_and_set_against_the_expected_source_states() -> None:
    store, conn = _store([_row(state="RUNNING", seq=4)])

    store.transition(
        "j1", JobState.COMPLETED, expect_from=frozenset({JobState.RUNNING}), now=2.0
    )

    sql, params = conn.statements[0]
    assert "WHERE job_id = %s AND state = ANY(%s)" in sql
    assert params[-1] == ["RUNNING"]


def test_an_illegal_transition_writes_nothing_and_returns_none() -> None:
    # The UPDATE matched no row: no state change, and crucially no event — a redelivered message
    # must not append a duplicate history entry.
    store, conn = _store([])

    result = store.transition(
        "j1", JobState.RUNNING, expect_from=frozenset({JobState.QUEUED}), now=2.0
    )

    assert result is None
    assert len(conn.statements) == 1  # no event INSERT


def test_a_successful_transition_writes_its_event_in_the_same_commit() -> None:
    store, conn = _store([_row(state="RUNNING", seq=7)])

    job = store.transition(
        "j1", JobState.COMPLETED, expect_from=frozenset({JobState.RUNNING}), now=2.0
    )

    assert job is not None
    insert_sql, insert_params = conn.statements[1]
    assert "INSERT INTO content_job_events" in insert_sql
    # The event's seq is the one the state change itself took, so two concurrent writers cannot
    # both mint the same number and the replay stream cannot develop a hole.
    assert insert_params[2] == job.seq == 7
    assert conn.commits == 1


def test_optional_fields_are_coalesced_so_a_late_writer_cannot_blank_the_record() -> None:
    # A worker that knows nothing about result_ref must not erase it by supplying NULL. COALESCE is
    # what makes one statement serve every edge.
    store, conn = _store([_row(state="RUNNING", seq=2, result_ref="summary/v1")])

    store.transition(
        "j1", JobState.ABSTAINED, expect_from=frozenset({JobState.RUNNING}), now=2.0
    )

    sql = conn.statements[0][0]
    assert "result_ref = COALESCE(%s, result_ref)" in sql
    assert "abstain_reason = COALESCE(%s, abstain_reason)" in sql
    assert "error = COALESCE(%s, error)" in sql


def test_the_state_is_checked_against_the_declared_lifecycle_in_the_database() -> None:
    # The adapter and the CHECK constraint are two independent guards; both must name the same
    # seven states, or the durable store will accept a state the domain would refuse.
    sql = (
        open(
            __file__.rsplit("/tests/", 1)[0] + "/migrations/002_create_content_jobs.sql",
            encoding="utf-8",
        ).read()
    )
    for state in JobState:
        assert f"'{state.value}'" in sql
    assert "ck_content_jobs_state" in sql


# --- events (RJ-AC02 / RJ-AC04) -------------------------------------------------------------


def test_replay_returns_events_after_the_cursor_in_order() -> None:
    store, conn = _store(
        [("u1",)],  # the owner lookup that scopes the replay
        # event_id, job_id, owner_id, seq, state, payload, created_at
        [("e3", "j1", "u1", 3, "RUNNING", {}, datetime(2026, 1, 1, tzinfo=UTC))],
    )

    events = store.list_events("j1", after_seq=2, limit=10)

    assert [e.seq for e in events] == [3]
    assert events[0].job_id == "j1" and events[0].owner_id == "u1"
    replay_sql, replay_params = conn.statements[1]
    assert "seq > %s" in replay_sql and "ORDER BY seq ASC" in replay_sql
    assert replay_params == ("j1", "u1", 2, 10)


def test_an_unknown_job_replays_nothing_without_a_second_query() -> None:
    store, conn = _store([])

    assert store.list_events("nope") == []
    assert len(conn.statements) == 1


# --- effects (item 25 / ND-Q8) ---------------------------------------------------------------


def test_an_effect_claim_is_a_single_insert_that_a_conflict_defeats() -> None:
    store, conn = _store([])
    store.claim_effect("j1", 1, "generate")

    sql, params = conn.statements[0]
    assert "ON CONFLICT (job_id, attempt) DO NOTHING" in sql
    assert params == ("j1", 1, "generate")


def test_a_duplicate_claim_reports_that_the_budget_was_already_spent() -> None:
    # An INSERT ... DO NOTHING that conflicts writes no row, and that is exactly the signal the
    # worker needs: the effect is already paid for, so skip it instead of buying it again.
    spent, _ = _store([])
    assert spent.claim_effect("j1", 1, "generate") is False

    fresh, _ = _store([_row()])  # the insert returned a row: the budget was actually claimed
    assert fresh.claim_effect("j1", 1, "generate") is True


def test_releasing_a_budget_targets_the_exact_attempt() -> None:
    store, conn = _store([])

    store.release_effect("j1", 2)

    sql, params = conn.statements[0]
    assert sql.startswith("DELETE FROM content_job_effect_ledger")
    assert params == ("j1", 2)


# --- expiry and purge (items 24, 26 / RJ-AC07, G3) ------------------------------------------


def test_a_completed_job_carries_its_result_window_and_error_both_survive() -> None:
    store, _ = _store(
        [
            _row(
                state="COMPLETED",
                seq=6,
                result_ref="summary/2401.1/v1",
                result_expires_at=datetime(2026, 1, 1, 1, 0, tzinfo=UTC),
                error={"errorType": "internal", "message": "x", "retryable": True},
            )
        ]
    )

    job = store.get("j1")

    assert job is not None
    assert job.result_ref == "summary/2401.1/v1"
    # TIMESTAMPTZ is normalized to a float so the expiry compare is a plain number compare.
    assert isinstance(job.result_expires_at, float)
    assert job.error is not None and job.error.retryable is True


def test_a_malformed_error_column_does_not_become_a_crash_on_read() -> None:
    store, _ = _store([_row(error={"message": "no type"})])

    job = store.get("j1")

    assert job is not None
    assert job.error is not None and job.error.error_type == "internal"


def test_purging_an_owner_deletes_the_jobs_and_cascades_the_rest() -> None:
    store, conn = _store([("a",), ("b",)])

    removed = store.purge_owner("u1")

    sql, params = conn.statements[0]
    assert "DELETE FROM content_jobs WHERE owner_id = %s" in sql
    assert params == ("u1",)
    assert removed == 2


def test_releasing_a_key_is_guarded_by_the_job_it_unbinds() -> None:
    # Without the job_id guard, a late failure from a superseded job would free a key that now
    # belongs to newer work — and the next retry would silently fork the caller's request.
    store, conn = _store([])

    store.release_idempotency("u1", "k", "j-old")

    sql, params = conn.statements[0]
    assert "WHERE job_id = %s AND owner_id = %s AND idempotency_key = %s" in sql
    assert params == ("j-old", "u1", "k")


def test_releasing_an_absent_key_is_a_no_op() -> None:
    store, conn = _store()

    store.release_idempotency("u1", None, "j1")

    assert conn.statements == []


@pytest.mark.parametrize(
    "raw",
    [
        None,
        '{"errorType": "timeout", "message": "m", "retryable": false}',
        {"errorType": "abstain", "message": "m"},
    ],
)
def test_the_error_column_round_trips_through_jsonb(raw) -> None:
    store, _ = _store([_row(error=raw)])

    job = store.get("j1")

    assert job is not None
    if raw is None:
        assert job.error is None
    else:
        assert job.error is not None
        assert job.error.message == "m"


def test_a_json_error_is_serialized_with_the_camel_case_shape_the_client_reads() -> None:
    store, conn = _store([_row(state="FAILED", seq=2)])

    store.transition(
        "j1",
        JobState.FAILED,
        expect_from=frozenset({JobState.RUNNING}),
        now=2.0,
        error=JobError("timeout", "시간이 초과되었습니다.", True, retry_after_seconds=30),
    )

    payload = conn.statements[0][1][5]
    assert json.loads(payload) == {
        "errorType": "timeout",
        "message": "시간이 초과되었습니다.",
        "retryable": True,
        "retryAfterSeconds": 30,
    }