"""Required schema execution; registry/admission is not real database proof."""

from __future__ import annotations

import hashlib

import pytest
from psycopg.errors import CheckViolation, UniqueViolation

from backend.migrations import _atomic_sql
from backend.migrations.registry import registry


def test_registered_additive_authority_script_follows_unchanged_002() -> None:
    definitions = registry(owners={"summarization"})
    assert [item.local_id for item in definitions] == [
        "001_create_user_glossary.sql", "002_create_content_jobs.sql",
        "003_content_job_authority_prepared.sql",
    ]
    for definition in definitions:
        digest = "sha256:" + hashlib.sha256(definition.path.read_bytes()).hexdigest()
        assert definition.digest == digest


def test_historical_002_retains_the_coordinators_prewrite_bytes_not_head() -> None:
    historical = registry(owners={"summarization"})[1].path.read_bytes()
    # Coordinator's immutable dirty-source snapshot, manifest entry for 002.
    # This deliberately does not compare against the Git-tracked version.
    assert len(historical) == 5753
    assert hashlib.sha256(historical).hexdigest() == (
        "8f47c5582aadff04afe2f4cac0f39ad1e9e8985f411dd809528d9a8571a07f7f"
    )


def test_registered_authority_script_is_admitted_by_the_actual_migration_runner() -> None:
    definition = registry(owners={"summarization"})[-1]
    # Exact pinned actual definition only. This check does not execute the script
    # or substitute for the independent source review and protected real realm.
    payload = definition.path.read_bytes()
    assert _atomic_sql(payload, definition).encode() == payload


def test_schema_has_all_three_eligibility_indexes_and_cleanup_progress(authority_schema) -> None:
    indexes = {row[0] for row in authority_schema.execute(
        "SELECT indexname FROM pg_indexes WHERE schemaname='public'"
    ).fetchall()}
    assert {"ix_content_job_first_dispatch", "ix_content_job_ambiguous_dispatch",
            "ix_content_job_expired_execution", "ix_content_job_payload_cleanup",
            "ix_content_job_maintenance_due"} <= indexes


def test_legacy_rows_never_acquire_default_authority(authority_schema) -> None:
    connection = authority_schema
    connection.execute("INSERT INTO accounts(id,email,password_hash,status) VALUES(%s,%s,%s,%s)",
                       ("owner", "synthetic@example.invalid", "synthetic", "ACTIVE"))
    connection.execute(
        "INSERT INTO content_jobs(job_id,owner_id,task_type,state) VALUES(%s,%s,%s,%s)",
        ("legacy", "owner", "summarize", "RUNNING"),
    )
    row = connection.execute(
        "SELECT authority_version,input_identity,prepared_result_id "
        "FROM content_jobs WHERE job_id=%s",
        ("legacy",),
    ).fetchone()
    assert row == (None, None, None)
    classification = connection.execute(
        "SELECT classification FROM content_job_legacy_classification WHERE job_id=%s", ("legacy",)
    ).fetchone()
    assert classification == ("legacy_active_unverified",)
    count = connection.execute("SELECT count(*) FROM content_job_submission_bindings").fetchone()
    assert count == (0,)


def test_v1_job_requires_binding_at_commit_not_only_a_decorative_marker(authority_schema) -> None:
    connection = authority_schema
    connection.execute("INSERT INTO accounts(id,email,password_hash,status) VALUES(%s,%s,%s,%s)",
                       ("owner", "synthetic@example.invalid", "synthetic", "ACTIVE"))
    with pytest.raises(CheckViolation, match="submission_binding_required"):
        with connection.transaction():
            connection.execute(
                "INSERT INTO content_jobs"
                "(job_id,owner_id,task_type,state,authority_version,input_identity) "
                "VALUES(%s,%s,%s,%s,1,%s)", ("job", "owner", "summarize", "SUBMITTED", "a" * 64),
            )
            connection.execute("SET CONSTRAINTS ALL IMMEDIATE")


def test_retained_key_uniqueness_and_distinct_keyless_jobs(authority_schema) -> None:
    connection = authority_schema
    connection.execute("INSERT INTO accounts(id,email,password_hash,status) VALUES(%s,%s,%s,%s)",
                       ("owner", "synthetic@example.invalid", "synthetic", "ACTIVE"))
    for number in range(2):
        job = f"job-{number}"
        connection.execute(
            "INSERT INTO content_jobs"
            "(job_id,owner_id,task_type,state,authority_version,input_identity) "
            "VALUES(%s,%s,%s,%s,1,%s)", (job, "owner", "summarize", "SUBMITTED", "a" * 64),
        )
        connection.execute(
            "INSERT INTO content_job_submission_bindings"
            "(binding_id,job_id,owner_id,dispatch_id,input_identity) VALUES(%s,%s,%s,%s,%s)",
            (f"binding-{number}", job, "owner", f"dispatch-{number}", "a" * 64),
        )
    count = connection.execute("SELECT count(*) FROM content_job_submission_bindings").fetchone()
    assert count == (2,)
    connection.execute("SET CONSTRAINTS ALL IMMEDIATE")
    with pytest.raises(UniqueViolation):
        with connection.transaction():
            connection.execute("UPDATE content_job_submission_bindings SET idempotency_key='same'")


def test_completed_v1_cannot_advertise_an_unbound_coarse_reference(authority_schema) -> None:
    connection = authority_schema
    connection.execute("INSERT INTO accounts(id,email,password_hash,status) VALUES(%s,%s,%s,%s)",
                       ("owner", "synthetic@example.invalid", "synthetic", "ACTIVE"))
    with pytest.raises(CheckViolation):
        with connection.transaction():
            connection.execute(
                "INSERT INTO content_jobs(job_id,owner_id,task_type,state,result_ref,"
                "authority_version,input_identity) VALUES(%s,%s,%s,%s,%s,1,%s)",
                ("job", "owner", "summarize", "COMPLETED", "coarse/paper", "a" * 64),
            )
