"""Refusal detail against the owned store: recorded once, bounded, refused-only.

Local-sink admissions only; no adapter is bound and no network is used.
"""

import datetime as dt
from uuid import uuid4

import psycopg
import pytest
from backend.modules.topics.errors import TopicsError
from backend.modules.topics.repository import TopicsRepository


def sending_run(transactions, authority, start=dt.date(2026, 5, 1)):
    repository = TopicsRepository(transactions)
    topic = repository.follow(authority, str(uuid4()), "Refusal detail")["topic"]["id"]
    run, _ = repository.prepare_run(
        topic,
        start,
        start + dt.timedelta(days=6),
        1,
        [{"title": "Original title", "publishedOn": start.isoformat()}],
    )
    assert repository.begin_send(run["id"], "local-sink") is not None
    return repository, run


def outcome_of(repository, run_id):
    return repository.system(
        lambda conn: conn.execute(
            "SELECT observed_state,failure_reason,provider_status,provider_error "
            "FROM topics.delivery_outcome WHERE run_id=%s",
            (run_id,),
        ).fetchone()
    )


def test_provider_refusal_detail_is_recorded_with_the_outcome(transactions, authority):
    repository, run = sending_run(transactions, authority)
    terminal = repository.finish_send(
        run["id"],
        "failed",
        failure_reason="delivery-path-refused",
        provider_status=403,
        provider_error="validation_error",
    )
    assert terminal["state"] == "failed"
    assert outcome_of(repository, run["id"]) == {
        "observed_state": "failed",
        "failure_reason": "delivery-path-refused",
        "provider_status": 403,
        "provider_error": "validation_error",
    }


def test_local_refusal_is_recorded_without_provider_detail(transactions, authority):
    repository, run = sending_run(transactions, authority)
    repository.finish_send(run["id"], "failed", failure_reason="recipient-not-permitted")
    recorded = outcome_of(repository, run["id"])
    assert recorded["failure_reason"] == "recipient-not-permitted"
    assert (recorded["provider_status"], recorded["provider_error"]) == (None, None)


@pytest.mark.parametrize(
    "state,reason,status,name",
    [
        ("unknown", None, 403, "validation_error"),
        ("failed", "recipient-not-permitted", 403, "validation_error"),
        ("failed", "delivery-path-refused", 500, "validation_error"),
        ("failed", "delivery-path-refused", 403, "Domain not verified for owner@x.invalid"),
        ("failed", "delivery-path-refused", 403, None),
        ("failed", "delivery-path-refused", None, "validation_error"),
    ],
)
def test_inconsistent_detail_is_refused_before_any_write(
    transactions, authority, state, reason, status, name
):
    repository, run = sending_run(transactions, authority)
    with pytest.raises(TopicsError):
        repository.finish_send(
            run["id"], state, failure_reason=reason, provider_status=status, provider_error=name
        )
    # Nothing was written: the run is still sending and can be closed normally.
    assert outcome_of(repository, run["id"]) is None
    repository.finish_send(run["id"], "failed", failure_reason="test-closed")


def test_schema_enforces_and_freezes_the_detail(transactions, authority):
    repository, run = sending_run(transactions, authority)
    repository.finish_send(
        run["id"],
        "failed",
        failure_reason="delivery-path-refused",
        provider_status=422,
        provider_error="name-unavailable",
    )
    for assignment in (
        "provider_status=403",
        "provider_error='validation_error'",
        "provider_status=NULL,provider_error=NULL",
    ):
        with pytest.raises(psycopg.errors.CheckViolation):
            repository.system(
                lambda conn, assignment=assignment: conn.execute(
                    "UPDATE topics.delivery_outcome SET " + assignment + " WHERE run_id=%s",
                    (run["id"],),
                )
            )
    assert outcome_of(repository, run["id"])["provider_status"] == 422


def test_schema_refuses_detail_outside_a_provider_refusal(transactions, authority):
    repository, run = sending_run(transactions, authority)
    repository.system(
        lambda conn: conn.execute(
            "UPDATE topics.digest_run SET state='failed',updated_at=clock_timestamp() WHERE id=%s",
            (run["id"],),
        )
    )
    for reason, status, name in (
        ("recipient-not-permitted", 403, "validation_error"),
        ("delivery-path-refused", 403, "Not Verified"),
        ("delivery-path-refused", 503, "validation_error"),
    ):
        with pytest.raises(psycopg.errors.CheckViolation):
            repository.system(
                lambda conn, values=(reason, status, name): conn.execute(
                    "INSERT INTO topics.delivery_outcome"
                    "(id,run_id,observed_state,failure_reason,provider_status,provider_error) "
                    "VALUES(%s,%s,'failed',%s,%s,%s)",
                    (uuid4(), run["id"], *values),
                )
            )
