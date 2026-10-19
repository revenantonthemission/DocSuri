"""Real-send evidence retention against the owned store (simulated attempts only).

No adapter is bound here; rows are created through the checked admission or,
for an already-elapsed bound, inserted with a backdated attempt time.
"""

import datetime as dt
from uuid import uuid4

import psycopg
import pytest
from backend.modules.topics.errors import TopicsError
from backend.modules.topics.repository import TopicsRepository


def prepared(transactions, authority, start=dt.date(2026, 2, 1)):
    repository = TopicsRepository(transactions)
    topic = repository.follow(authority, str(uuid4()), "Retention")["topic"]["id"]
    run, _ = repository.prepare_run(
        topic,
        start,
        start + dt.timedelta(days=6),
        1,
        [{"title": "Original title", "publishedOn": start.isoformat()}],
    )
    return repository, run


def spent(repository):
    return repository.system(
        lambda conn: conn.execute(
            "SELECT count(*) AS n FROM topics.send_log_entry WHERE path_kind='real'"
        ).fetchone()["n"]
    )


def log_of(repository, run_id):
    return repository.system(
        lambda conn: conn.execute(
            "SELECT * FROM topics.send_log_entry WHERE run_id=%s", (run_id,)
        ).fetchone()
    )


def elapsed_real_attempt(repository, run, *, days=31, retained=30):
    """A sending run whose real attempt happened `days` ago, bound `retained` days."""

    def write(conn):
        conn.execute(
            "UPDATE topics.digest_run SET state='sending',updated_at=clock_timestamp() WHERE id=%s",
            (run["id"],),
        )
        conn.execute(
            "INSERT INTO topics.send_log_entry"
            "(id,run_id,path_kind,attempted_at,evidence_retain_until) "
            "SELECT %s,%s,'real',c.at,c.at + make_interval(days => %s) "
            "FROM (SELECT clock_timestamp() - make_interval(days => %s) AS at) c",
            (uuid4(), run["id"], retained, days),
        )

    repository.system(write)


def test_real_admission_requires_and_stamps_a_bounded_retention(transactions, authority):
    repository, run = prepared(transactions, authority)
    limit = spent(repository) + 1
    for days in (None, 0, 31, "30"):
        with pytest.raises(TopicsError):
            repository.begin_send(
                run["id"], "real", real_send_limit=limit, evidence_retention_days=days
            )
    with pytest.raises(TopicsError):
        repository.begin_send(run["id"], "local-sink", evidence_retention_days=30)
    sending = repository.begin_send(
        run["id"], "real", real_send_limit=limit, evidence_retention_days=30
    )
    assert sending is not None
    log = log_of(repository, run["id"])
    assert log["evidence_retain_until"] - log["attempted_at"] == dt.timedelta(days=30)
    assert log["evidence_expired_at"] is None
    repository.finish_send(run["id"], "failed", failure_reason="delivery-path-refused")


def test_local_sink_attempts_carry_no_retention_bound(transactions, authority):
    repository, run = prepared(transactions, authority)
    assert repository.begin_send(run["id"], "local-sink") is not None
    assert log_of(repository, run["id"])["evidence_retain_until"] is None
    repository.finish_send(run["id"], "sent")


def test_receipt_cannot_be_cleared_before_its_bound(transactions, authority):
    repository, run = prepared(transactions, authority)
    repository.begin_send(
        run["id"], "real", real_send_limit=spent(repository) + 1, evidence_retention_days=30
    )
    repository.finish_send(
        run["id"],
        "sent",
        transport_receipt=str(uuid4()),
        acknowledged_at=dt.datetime.now(dt.UTC),
    )
    assert log_of(repository, run["id"])["id"] not in repository.expire_real_evidence(50)
    with pytest.raises(psycopg.errors.CheckViolation):
        repository.system(
            lambda conn: conn.execute(
                "UPDATE topics.send_log_entry SET transport_receipt=NULL,"
                "evidence_expired_at=clock_timestamp() WHERE run_id=%s",
                (run["id"],),
            )
        )
    assert log_of(repository, run["id"])["transport_receipt"] is not None


def test_settled_evidence_expires_without_replenishing_the_allocation(transactions, authority):
    repository, run = prepared(transactions, authority)
    elapsed_real_attempt(repository, run)
    acknowledged = dt.datetime.now(dt.UTC) - dt.timedelta(days=31)
    repository.finish_send(
        run["id"], "sent", transport_receipt=str(uuid4()), acknowledged_at=acknowledged
    )
    before = spent(repository)
    log = log_of(repository, run["id"])
    expired = []
    while True:
        batch = repository.expire_real_evidence(50)
        expired.extend(batch)
        if log["id"] in expired or not batch:
            break
    assert log["id"] in expired
    after = log_of(repository, run["id"])
    assert after["transport_receipt"] is None and after["evidence_expired_at"] is not None
    assert after["acknowledged_at"] == acknowledged and after["path_kind"] == "real"
    assert spent(repository) == before
    with pytest.raises(psycopg.errors.CheckViolation):
        repository.system(
            lambda conn: conn.execute(
                "UPDATE topics.send_log_entry SET transport_receipt='again' WHERE run_id=%s",
                (run["id"],),
            )
        )


def test_unresolved_unknown_keeps_evidence_until_settled(transactions, authority):
    repository, run = prepared(transactions, authority)
    elapsed_real_attempt(repository, run)
    repository.finish_send(run["id"], "unknown")
    log = log_of(repository, run["id"])
    assert log["id"] not in repository.expire_real_evidence(50)
    assert repository.reconcile_run(run["id"], "failed") is not None
    expired = []
    for _ in range(10):
        batch = repository.expire_real_evidence(50)
        expired.extend(batch)
        if log["id"] in expired or not batch:
            break
    assert log["id"] in expired


def test_database_refuses_retention_beyond_thirty_days(transactions, authority):
    repository, run = prepared(transactions, authority)
    with pytest.raises(psycopg.errors.CheckViolation):
        elapsed_real_attempt(repository, run, days=1, retained=31)
    with pytest.raises(TopicsError):
        repository.expire_real_evidence(0)
