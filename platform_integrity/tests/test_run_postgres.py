"""Real control transactions on a guarded disposable DB; not native authority/target proof."""

import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from threading import Barrier
from urllib.parse import urlsplit

import psycopg
import pytest
from run_support import context, fence, plan

from docsuri_platform_integrity.adapters.postgres import ControlUnavailable, PostgresRunStore
from docsuri_platform_integrity.contracts.models import EffectAssurance, EffectObservation

DSN = os.environ.get("REM1_TEST_PG_DSN")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not DSN, reason="isolated REM1_TEST_PG_DSN required"),
]


@pytest.fixture
def store():
    parts = urlsplit(DSN)
    assert parts.hostname == "127.0.0.1" and parts.port == 15439 and parts.path == "/rem1_test"
    root = Path(__file__).resolve().parents[1] / "migrations"
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("DROP SCHEMA IF EXISTS r1_control CASCADE")
        conn.execute("DROP SCHEMA IF EXISTS r1_audit CASCADE")
        for name in ("001_control.sql", "002_run_protocol.sql"):
            conn.execute((root / name).read_text())
    return PostgresRunStore(DSN)


def start(store, value=None):
    value = value or plan()
    store.register(value, run_id="r1", submission_key="request-1", context=context("plan"))
    store.begin_attempt(
        "r1", attempt_id="a1", approval="approval-1", invocation="invocation-1", context=context(),
    )
    return value


def prepare(store, value, *, revision="0", number=1, step=None):
    return store.prepare(
        "r1", attempt_id=f"a{number}", step=step or value.steps[0].step,
        fence=fence(value, number), expected_revision=revision, context=context(),
    )


def native_fact(record, *, commit=True, verified=True):
    # Synthetic normalized observation; the control adapter does not authenticate this source.
    return EffectObservation(
        binding=record.binding, authoritative=True, receipt="test-native-receipt",
        committed=commit, aborted=not commit, quiescent=True,
        observed_state=record.binding.expected_after if commit else record.binding.expected_before,
        authorization_verified=verified, durability_verified=verified,
    )


def test_submission_keys_are_idempotent_but_cannot_change_meaning(store):
    first = store.register(plan(), run_id="r1", submission_key="key", context=context("plan"))
    replay = store.register(plan(), run_id="r2", submission_key="key", context=context("plan"))
    assert replay == first
    assert store.register(
        plan(), run_id="r3", submission_key="another-key", context=context("plan")
    ) == first
    with pytest.raises(ValueError, match="submission"):
        store.register(
            plan(incarnation="restored"), run_id="r2", submission_key="key", context=context("plan")
        )
    with psycopg.connect(DSN) as conn:
        assert conn.execute("SELECT count(*) FROM r1_control.runs").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM r1_control.submissions").fetchone()[0] == 2


def test_unknown_checkpoint_is_durable_with_audit_outbox_before_return(store):
    value = start(store)
    receipt = prepare(store, value)
    independent_reader = PostgresRunStore(DSN)
    assert independent_reader.latest("r1", value.steps[0].step) == receipt.record
    assert independent_reader.read("r1").state == "RECONCILE_REQUIRED"
    with psycopg.connect(DSN) as conn:
        assert conn.execute(
            "SELECT count(*) FROM r1_audit.events e JOIN r1_control.outbox o USING (event_id) "
            "WHERE e.event_id=%s", (receipt.event_id,),
        ).fetchone()[0] == 1
    with pytest.raises(ValueError):
        prepare(store, value, revision="1")


def test_lost_control_commit_ack_keeps_unknown_and_forbids_blind_retry(store):
    value = start(store)

    class LoseReply(PostgresRunStore):
        @contextmanager
        def _transaction(self):
            with super()._transaction() as conn:
                yield conn
            raise ControlUnavailable("injected acknowledgement loss after actual commit")

    with pytest.raises(ControlUnavailable):
        prepare(LoseReply(DSN), value)
    assert store.latest("r1", value.steps[0].step).checkpoint.assurance == EffectAssurance.UNKNOWN
    with pytest.raises(ValueError):
        prepare(store, value)
    with pytest.raises(ValueError, match="reconciliation"):
        store.begin_attempt(
            "r1", attempt_id="a2", approval="approval-2", invocation="invocation-2",
            context=context(),
        )


def test_outbox_failure_rolls_back_checkpoint_and_projection(store):
    value = start(store)
    with psycopg.connect(DSN) as conn:
        conn.execute(
            "ALTER TABLE r1_control.outbox ADD CONSTRAINT reject_test_insert CHECK(false) NOT VALID"
        )
    with pytest.raises(ControlUnavailable):
        prepare(store, value)
    assert store.latest("r1", value.steps[0].step) is None
    assert store.read("r1").revision == "0"
    assert store.read("r1").state == "RUNNING"
    with psycopg.connect(DSN) as conn:
        assert conn.execute("SELECT count(*) FROM r1_control.checkpoints").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM r1_audit.events").fetchone()[0] == 2


def test_two_control_writers_cannot_reserve_the_same_effect_twice(store):
    value = start(store)
    barrier = Barrier(2)

    def contender():
        barrier.wait(timeout=5)
        try:
            return prepare(PostgresRunStore(DSN), value)
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: contender(), range(2)))
    assert sum(result is not None for result in outcomes) == 1
    assert store.read("r1").revision == "1"


def test_partial_commit_abort_and_fresh_approval_resume_without_replaying_first_step(store):
    value = start(store)
    first = prepare(store, value)
    store.reconcile(
        "r1", step=value.steps[0].step, observation=native_fact(first.record),
        expected_revision="1", context=context("reconcile"),
    )
    second = prepare(store, value, revision="2", step=value.steps[1].step)
    store.reconcile(
        "r1", step=value.steps[1].step, observation=native_fact(second.record, commit=False),
        expected_revision="3", context=context("reconcile"),
    )
    assert store.read("r1").state == "PAUSED"
    original_intent = store.read("r1").intent
    resumed = store.begin_attempt(
        "r1", attempt_id="a2", approval="fresh-approval", invocation="new-invocation",
        context=context(),
    )
    assert resumed.ordinal == 2 and store.read("r1").intent == original_intent
    with pytest.raises(ValueError):
        prepare(store, value, revision="4", number=2)
    second = prepare(store, value, revision="4", number=2, step=value.steps[1].step)
    store.reconcile(
        "r1", step=value.steps[1].step, observation=native_fact(second.record),
        expected_revision="5", context=context("reconcile"),
    )
    assert store.read("r1").state == "SUCCEEDED"
    assert store.latest("r1", value.steps[0].step).binding.attempt_id == "a1"


def test_actual_commit_without_authorization_proof_is_not_run_success(store):
    value = start(store, plan(count=1))
    checkpoint = prepare(store, value)
    store.reconcile(
        "r1", step=value.steps[0].step,
        observation=native_fact(checkpoint.record, verified=False),
        expected_revision="1", context=context("reconcile"),
    )
    assert store.latest("r1", value.steps[0].step).checkpoint.assurance == EffectAssurance.COMMITTED
    assert store.read("r1").state == "PAUSED"


def test_read_is_nonmutating_and_checkpoint_history_is_immutable(store):
    value = start(store)
    prepare(store, value)
    before = store.read("r1")
    assert store.read("r1") == before
    with psycopg.connect(DSN, autocommit=True) as conn:
        assert conn.execute("SELECT count(*) FROM r1_audit.events").fetchone()[0] == 3
        for query in (
            "DELETE FROM r1_control.checkpoints",
            "UPDATE r1_control.attempts SET digest='changed'",
            "UPDATE r1_control.runs SET semantic_key='changed'",
        ):
            with pytest.raises(psycopg.errors.RaiseException):
                conn.execute(query)


def test_step_order_stale_revision_and_context_mismatch_are_rejected(store):
    value = start(store)
    with pytest.raises(ValueError, match="predecessor"):
        prepare(store, value, step=value.steps[1].step)
    with pytest.raises(ValueError):
        prepare(store, value, revision="01")
    with pytest.raises(ValueError):
        prepare(store, value, revision="1")
    with pytest.raises(PermissionError):
        store.prepare(
            "r1", attempt_id="a1", step=value.steps[0].step, fence=fence(value),
            expected_revision="0", context=context("reconcile"),
        )
    assert store.read("r1").revision == "0"


def test_attempt_replay_preserves_original_grant_and_start_time(store):
    start(store)
    replay = store.begin_attempt(
        "r1", attempt_id="a1", approval="approval-1", invocation="invocation-1",
        context=context(instant="200"),
    )
    assert replay.started_at == "100" and replay.ordinal == 1
    with pytest.raises(ValueError, match="identity conflict"):
        store.begin_attempt(
            "r1", attempt_id="a1", approval="renewed-approval", invocation="invocation-1",
            context=context(),
        )
    with psycopg.connect(DSN) as conn:
        assert conn.execute("SELECT count(*) FROM r1_audit.events").fetchone()[0] == 2


def test_terminal_commit_observation_is_idempotent_without_rewriting_history(store):
    value = start(store, plan(count=1))
    checkpoint = prepare(store, value)
    proof = native_fact(checkpoint.record)
    first = store.reconcile(
        "r1", step=value.steps[0].step, observation=proof,
        expected_revision="1", context=context("reconcile"),
    )
    assert store.reconcile(
        "r1", step=value.steps[0].step, observation=proof,
        expected_revision="2", context=context("reconcile", instant="300"),
    ) == first
    assert store.read("r1").revision == "2"


def test_unconfirmed_observation_and_other_actor_cannot_make_run_dispatchable(store):
    value = start(store)
    with pytest.raises(PermissionError, match="actor"):
        store.prepare(
            "r1", attempt_id="a1", step=value.steps[0].step, fence=fence(value),
            expected_revision="0", context=context().model_copy(update={"actor": "other"}),
        )
    checkpoint = prepare(store, value)
    store.reconcile(
        "r1", step=value.steps[0].step,
        observation=native_fact(checkpoint.record).model_copy(update={"authoritative": False}),
        expected_revision="1", context=context("reconcile"),
    )
    assert store.read("r1").state == "RECONCILE_REQUIRED"
    assert store.latest("r1", value.steps[0].step).checkpoint.assurance == EffectAssurance.UNKNOWN


def test_control_store_does_not_bootstrap_on_missing_schema_or_missing_run(store):
    with pytest.raises(ValueError, match="not found"):
        store.read("absent")
    with psycopg.connect(DSN) as conn:
        conn.execute("DROP SCHEMA r1_control CASCADE")
    with pytest.raises(ControlUnavailable):
        store.read("absent")
    with psycopg.connect(DSN) as conn:
        assert conn.execute("SELECT to_regnamespace('r1_control')").fetchone()[0] is None


def test_run_id_cannot_be_reused_for_a_different_target(store):
    start(store)
    with pytest.raises(ValueError, match="another intent"):
        store.register(
            plan(incarnation="restored"), run_id="r1", submission_key="new-key",
            context=context("plan"),
        )


def test_missing_checkpoint_tail_blocks_resume_even_with_a_paused_projection(store):
    value = start(store)
    prepare(store, value)
    # Fault injection by the disposable-DB owner, representing an inconsistent restored cut.
    with psycopg.connect(DSN) as conn:
        conn.execute("ALTER TABLE r1_control.checkpoints DISABLE TRIGGER immutable_checkpoint")
        conn.execute("DELETE FROM r1_control.checkpoints")
        conn.execute("ALTER TABLE r1_control.checkpoints ENABLE TRIGGER immutable_checkpoint")
        conn.execute("UPDATE r1_control.runs SET state='PAUSED' WHERE run_id='r1'")
    with pytest.raises(ValueError, match="history gap"):
        store.begin_attempt(
            "r1", attempt_id="a2", approval="fresh", invocation="fresh", context=context(),
        )
