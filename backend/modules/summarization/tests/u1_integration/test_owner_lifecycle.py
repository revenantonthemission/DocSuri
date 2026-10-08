"""Step 6 schema guards only. Full purger/T8 races follow the Step 15 bridge."""

import pytest
from psycopg.errors import CheckViolation


@pytest.mark.parametrize("status", ["DEACTIVATED", "PURGE_FAILED", "PENDING"])
def test_inactive_account_cannot_accumulate_content_jobs(authority_schema, status) -> None:
    connection = authority_schema
    connection.execute("INSERT INTO accounts(id,email,password_hash,status) VALUES(%s,%s,%s,%s)",
                       ("owner", "synthetic@example.invalid", "synthetic", status))
    with pytest.raises(CheckViolation, match="owner_inactive"):
        with connection.transaction():
            connection.execute("INSERT INTO content_jobs(job_id,owner_id,task_type,state) "
                               "VALUES(%s,%s,%s,%s)", ("job", "owner", "summarize", "SUBMITTED"))


def test_absent_owner_cannot_be_guessed_or_recreated(authority_schema) -> None:
    with pytest.raises(CheckViolation, match="owner_inactive"):
        with authority_schema.transaction():
            authority_schema.execute("INSERT INTO content_jobs(job_id,owner_id,task_type,state) "
                                     "VALUES(%s,%s,%s,%s)",
                                     ("job", "absent", "summarize", "SUBMITTED"))


def test_existing_legacy_job_is_deleted_by_current_account_foreign_key(authority_schema) -> None:
    connection = authority_schema
    connection.execute("INSERT INTO accounts(id,email,password_hash,status) VALUES(%s,%s,%s,%s)",
                       ("owner", "synthetic@example.invalid", "synthetic", "ACTIVE"))
    connection.execute(
        "INSERT INTO content_jobs(job_id,owner_id,task_type,state) VALUES(%s,%s,%s,%s)",
        ("job", "owner", "summarize", "SUBMITTED"),
    )
    connection.execute("DELETE FROM accounts WHERE id=%s", ("owner",))
    count = connection.execute(
        "SELECT count(*) FROM content_jobs WHERE job_id=%s", ("job",)
    ).fetchone()
    assert count == (0,)


def _submitted_dispatch(connection, outcome):
    """Source-only fixture helper until independent review/qualified realm admission."""
    connection.execute("INSERT INTO accounts(id,email,password_hash,status) VALUES(%s,%s,%s,%s)",
                       ("owner", "synthetic@example.invalid", "synthetic", "ACTIVE"))
    connection.execute(
        "INSERT INTO content_jobs(job_id,owner_id,task_type,state,authority_version,"
        "input_identity,idempotency_key) VALUES('job','owner','summarize','SUBMITTED',1,%s,%s)",
        ("a" * 64, "same-key"),
    )
    connection.execute(
        "INSERT INTO content_job_submission_bindings"
        "(binding_id,job_id,owner_id,dispatch_id,input_identity,idempotency_key) "
        "VALUES('original','job','owner','original-dispatch',%s,%s)", ("a" * 64, "same-key"),
    )
    connection.execute(
        "UPDATE content_job_submission_bindings SET dispatch_outcome='SENDING', "
        "dispatch_fence=1,dispatch_started_at=clock_timestamp() WHERE job_id='job'",
    )
    if outcome == "UNKNOWN":
        connection.execute(
            "UPDATE content_job_submission_bindings SET dispatch_outcome='UNKNOWN' "
            "WHERE job_id='job'",
        )
    # Flush earlier deferred checks: deletion must be guarded itself, not pass
    # accidentally because an unrelated pending validation catches a missing row.
    connection.execute("SET CONSTRAINTS ALL IMMEDIATE")
    connection.execute("SET CONSTRAINTS ALL DEFERRED")
    return _dispatch_row(connection)


def _dispatch_row(connection):
    return connection.execute(
        "SELECT binding_id,dispatch_id,dispatch_outcome,dispatch_fence,dispatch_started_at,"
        "input_identity,idempotency_key FROM content_job_submission_bindings WHERE job_id='job'",
    ).fetchone()


@pytest.mark.parametrize("outcome", ["SENDING", "UNKNOWN"])
def test_live_v1_dispatch_binding_cannot_be_deleted_while_job_remains(authority_schema, outcome):
    original = _submitted_dispatch(authority_schema, outcome)
    with pytest.raises(CheckViolation, match="dispatch_binding_deletion_refused"):
        with authority_schema.transaction():
            authority_schema.execute(
                "DELETE FROM content_job_submission_bindings WHERE job_id='job'",
            )
            authority_schema.execute("SET CONSTRAINTS ALL IMMEDIATE")
    assert _dispatch_row(authority_schema) == original


@pytest.mark.parametrize("outcome", ["SENDING", "UNKNOWN"])
def test_live_delete_reinsert_cannot_reset_dispatch_to_first_send(authority_schema, outcome):
    original = _submitted_dispatch(authority_schema, outcome)
    with pytest.raises(CheckViolation, match="dispatch_binding_deletion_refused"):
        with authority_schema.transaction():
            authority_schema.execute(
                "DELETE FROM content_job_submission_bindings WHERE job_id='job'",
            )
            authority_schema.execute(
                "INSERT INTO content_job_submission_bindings"
                "(binding_id,job_id,owner_id,dispatch_id,input_identity,idempotency_key) "
                "VALUES('replacement','job','owner','replacement-dispatch',%s,%s)",
                ("a" * 64, "same-key"),
            )
            authority_schema.execute("SET CONSTRAINTS ALL IMMEDIATE")
    assert _dispatch_row(authority_schema) == original
    assert original[2] == outcome and original[3] == 1 and original[4] is not None
    assert authority_schema.execute(
        "SELECT count(*) FROM content_job_submission_bindings WHERE binding_id='replacement'",
    ).fetchone() == (0,)


@pytest.mark.parametrize("outcome", ["SENDING", "UNKNOWN"])
def test_live_parent_job_deletion_cascades_ambiguous_binding(authority_schema, outcome):
    _submitted_dispatch(authority_schema, outcome)
    authority_schema.execute("DELETE FROM content_jobs WHERE job_id='job'")
    authority_schema.execute("SET CONSTRAINTS ALL IMMEDIATE")
    assert authority_schema.execute("SELECT count(*) FROM content_jobs").fetchone() == (0,)
    assert _dispatch_row(authority_schema) is None
    assert authority_schema.execute("SELECT count(*) FROM accounts").fetchone() == (1,)


@pytest.mark.parametrize("outcome", ["SENDING", "UNKNOWN"])
def test_live_parent_account_deletion_cascades_job_and_ambiguous_binding(authority_schema, outcome):
    _submitted_dispatch(authority_schema, outcome)
    authority_schema.execute("DELETE FROM accounts WHERE id='owner'")
    authority_schema.execute("SET CONSTRAINTS ALL IMMEDIATE")
    assert authority_schema.execute("SELECT count(*) FROM accounts").fetchone() == (0,)
    assert authority_schema.execute("SELECT count(*) FROM content_jobs").fetchone() == (0,)
    assert _dispatch_row(authority_schema) is None
