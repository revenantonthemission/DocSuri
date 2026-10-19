"""Rollback-only TEXT/metadata/constraint fixtures. Live tests MUST NOT run yet.

Requires focused independent final003/policy review and independently admitted
protected realm. No repository/service/HTTP/purger/production-ledger claim follows.
The first two tests are local source checks and never instantiate a SQL fixture.
"""

from __future__ import annotations

import json
import re
from datetime import timedelta

import pytest
from backend.migrations.registry import registry
from psycopg.errors import CheckViolation, ForeignKeyViolation

from summarization.domain.job_protocol import JobTask
from summarization.domain.prepared_result import PreparationIdentity, PreparedJobResult
from tests.test_u1_job_model import job_input, summary_payload, translation_payload
from tests.u1_integration.conftest import admitted_schema_statements


def test_local_registered_payload_column_is_opaque_text_with_no_json_payload_operations() -> None:
    sql = registry(owners={"summarization"})[-1].path.read_text()
    assert "prepared_content TEXT" in sql and "prepared_content JSONB" not in sql
    assert not re.search(r"prepared_content\s*(?:::|->|\?)", sql, re.I)
    assert not re.search(r"jsonb?_\w+\(\s*(?:NEW\.|OLD\.)?prepared_content", sql, re.I)
    assert "content_encoding = 'json-ascii'" in sql and "canonical_version = 2" in sql
    assert "length(prepared_content) = octet_length(prepared_content)" in sql
    assert "NEW.content_encoding, NEW.canonical_version" in sql


def test_local_full_schema_preadmission_retains_owner_immutable_and_lifecycle_guards() -> None:
    statements = admitted_schema_statements()
    assert len(statements) == 4
    sql = statements[-1]
    for guard in ("prepared_initial_payload_required", "prepared_content_immutable",
                  "prepared_expiry_immutable", "prepared_purge_immutable",
                  "content_job_owner_inactive", "effect_intent_deletion_refused",
                  "dispatch_binding_deletion_refused",
                  "job_history_immutable", "exact_prepared_binding_required",
                  "exact_prepared_expiry_required", "dispatch_release_refused",
                  "state_event_required"):
        assert guard in sql
    assert "OLD.expires_at <= clock_timestamp()" in sql
    assert "job.state = 'COMPLETED' AND job.result_expires_at = OLD.expires_at" in sql


def test_local_binding_delete_guard_keeps_live_v1_evidence_and_parent_cascade_exception() -> None:
    # Exact source assertions only. Actual deletion/reset/cascade fixtures are
    # authored in test_owner_lifecycle and remain uninvoked before realm admission.
    sql = admitted_schema_statements()[-1]
    body = re.search(
        r"CREATE FUNCTION public\.content_job_binding_guard\(\).*?AS \$\$(.*?)\$\$ LANGUAGE",
        sql, re.S,
    ).group(1)
    branch = body.split("IF TG_OP = 'DELETE' THEN", 1)[1].split("SELECT * INTO job", 1)[0]
    assert "WHERE job_id = OLD.job_id AND authority_version = 1" in branch
    assert "RAISE EXCEPTION 'dispatch_binding_deletion_refused'" in branch
    assert "RETURN OLD;" in branch
    assert "BEFORE INSERT OR UPDATE OR DELETE ON public.content_job_submission_bindings" in sql


def _running(connection, task):
    connection.execute("INSERT INTO accounts(id,email,password_hash,status) VALUES(%s,%s,%s,%s)",
                       ("owner", "synthetic@example.invalid", "synthetic", "ACTIVE"))
    connection.execute("INSERT INTO content_jobs(job_id,owner_id,task_type,state,"
                       "authority_version,input_identity,input) "
                       "VALUES(%s,%s,%s,'SUBMITTED',1,%s,%s::jsonb)",
                       ("job", "owner", task.value, "a" * 64,
                        json.dumps(job_input(task).to_dict())))
    connection.execute("INSERT INTO content_job_submission_bindings"
                       "(binding_id,job_id,owner_id,dispatch_id,input_identity) "
                       "VALUES('binding','job','owner','dispatch',%s)", ("a" * 64,))
    connection.execute("UPDATE content_job_submission_bindings SET dispatch_outcome='SENDING', "
                       "dispatch_fence=1,dispatch_started_at=clock_timestamp() WHERE job_id='job'")
    connection.execute("UPDATE content_job_submission_bindings SET dispatch_outcome='CONFIRMED' "
                       "WHERE job_id='job'")
    for seq, state in enumerate(("ACCEPTED", "QUEUED", "RUNNING"), 1):
        connection.execute("UPDATE content_jobs SET state=%s,seq=%s WHERE job_id='job'",
                           (state, seq))
        connection.execute("INSERT INTO content_job_events(job_id,owner_id,seq,state) "
                           "VALUES('job','owner',%s,%s)",
                           (seq, state))
    connection.execute("INSERT INTO content_job_effect_ledger(job_id,attempt,effect,"
                       "authority_version,owner_id,effect_status,fence,worker_id,lease_until) "
                       "VALUES('job',1,'generate',1,'owner', "
                       "'INTENT',1,'schema-fixture',clock_timestamp()+interval '90 seconds')")
    connection.execute("SET CONSTRAINTS ALL IMMEDIATE")
    connection.execute("SET CONSTRAINTS ALL DEFERRED")


def _prepared(connection, task, *, backdated=False, changes=None):
    payload = summary_payload() if task is JobTask.SUMMARIZE else translation_payload()
    if task is JobTask.SUMMARIZE:
        payload["summary"]["reproducibility"] = {"code": "\x00", "data": r"\u0000"}
    else:
        payload["translation"]["docModel"]["fullText"] = "\x00" + r"\u0000"
    at = connection.execute("SELECT clock_timestamp()").fetchone()[0]
    if backdated:
        at -= timedelta(hours=2)
    result = PreparedJobResult.capture(
        "job", "owner", task, payload, result_id="prepared", prepared_at=at.timestamp(),
        identity=PreparationIdentity(job_input(task)),
    )
    fields = {"owner": "owner", "encoding": result.content_encoding,
              "version": result.canonical_version, "payload": result.serialized_content,
              "purged_at": None, "expires_at": None, **(changes or {})}
    # ONLY private identity/input metadata have a JSON cast. Payload parameter is
    # plain TEXT: no driver JSON adapter, CAST, SQL parser or jsonb operation.
    connection.execute("INSERT INTO content_job_prepared_results"
                       "(prepared_result_id,job_id,owner_id,task_type,schema_version,content_digest,"
                       "prepared_content,content_encoding,canonical_version,"
                       "preparation_identity,prepared_at,content_purged_at,expires_at) "
                       "VALUES('prepared','job',%s,%s,1,%s,%s,%s,%s,%s::jsonb,%s,%s,%s)",
                       (fields["owner"], task.value, result.content_digest, fields["payload"],
                        fields["encoding"], fields["version"], result.serialized_identity, at,
                        fields["purged_at"], fields["expires_at"]))
    connection.execute("UPDATE content_job_effect_ledger SET effect_status='PREPARED',"
                       "prepared_result_id='prepared' "
                       "WHERE job_id='job'")
    connection.execute("UPDATE content_jobs SET prepared_result_id='prepared' WHERE job_id='job'")
    connection.execute("SET CONSTRAINTS ALL IMMEDIATE")
    connection.execute("SET CONSTRAINTS ALL DEFERRED")
    return result, at


def _completed(connection, at):
    expiry = at + timedelta(hours=1)
    connection.execute("UPDATE content_job_prepared_results SET expires_at=%s WHERE job_id='job'",
                       (expiry,))
    connection.execute("UPDATE content_jobs SET state='COMPLETED',seq=4,result_ref='prepared',"
                       "result_expires_at=%s "
                       "WHERE job_id='job'", (expiry,))
    connection.execute("UPDATE content_job_effect_ledger SET effect_status='TERMINAL' "
                       "WHERE job_id='job'")
    connection.execute("INSERT INTO content_job_events(job_id,owner_id,seq,state) "
                       "VALUES('job','owner',4,'COMPLETED')")
    connection.execute("SET CONSTRAINTS ALL IMMEDIATE")
    return expiry


@pytest.mark.parametrize("task", list(JobTask))
def test_live_text_preserves_canonical_characters_nul_and_typed_binding(
    authority_schema, task,
) -> None:
    connection = authority_schema
    _running(connection, task)
    result, _ = _prepared(connection, task)
    column = connection.execute(
        "SELECT data_type FROM information_schema.columns WHERE table_schema='public' "
        "AND table_name='content_job_prepared_results' AND column_name='prepared_content'",
    ).fetchone()
    assert column == ("text",)
    stored = connection.execute("SELECT prepared_content,content_digest,content_encoding,"
                                "canonical_version "
                                "FROM content_job_prepared_results WHERE job_id='job'").fetchone()
    assert stored == (result.serialized_content, result.content_digest, "json-ascii", 2)
    assert "\x00" not in stored[0] and r"\u0000" in stored[0] and r"\\u0000" in stored[0]


@pytest.mark.parametrize("changes", [
    {"encoding": "jsonb"}, {"encoding": None}, {"version": 1}, {"version": None},
    {"payload": ""}, {"payload": "한글"}, {"payload": None},
])
def test_live_encoding_text_presence_and_lifecycle_reject_invalid_rows(
    authority_schema, changes,
) -> None:
    from psycopg.errors import NotNullViolation

    _running(authority_schema, JobTask.SUMMARIZE)
    with pytest.raises((CheckViolation, NotNullViolation)):
        with authority_schema.transaction():
            _prepared(authority_schema, JobTask.SUMMARIZE, changes=changes)


def test_live_owner_identity_fk_cannot_bind_other_account_payload(authority_schema) -> None:
    _running(authority_schema, JobTask.SUMMARIZE)
    authority_schema.execute("INSERT INTO accounts(id,email,password_hash,status) "
                             "VALUES(%s,%s,%s,%s)",
                             ("other", "other@example.invalid", "synthetic", "ACTIVE"))
    with pytest.raises(ForeignKeyViolation):
        with authority_schema.transaction():
            _prepared(authority_schema, JobTask.SUMMARIZE, changes={"owner": "other"})


def test_live_prepared_content_metadata_time_and_identity_are_immutable(authority_schema) -> None:
    _running(authority_schema, JobTask.SUMMARIZE)
    _prepared(authority_schema, JobTask.SUMMARIZE)
    for statement in (
        "UPDATE content_job_prepared_results SET prepared_content='{}' WHERE job_id='job'",
        "UPDATE content_job_prepared_results SET canonical_version=1 WHERE job_id='job'",
        "UPDATE content_job_prepared_results SET prepared_at=prepared_at+interval '1 second' "
        "WHERE job_id='job'",
        "UPDATE content_job_prepared_results SET preparation_identity='{}'::jsonb "
        "WHERE job_id='job'",
    ):
        with pytest.raises(CheckViolation, match="immutable"):
            with authority_schema.transaction():
                authority_schema.execute(statement)


def test_live_future_expiry_and_noncompleted_payload_cannot_be_purged(authority_schema) -> None:
    _running(authority_schema, JobTask.SUMMARIZE)
    _, at = _prepared(authority_schema, JobTask.SUMMARIZE)
    statement = ("UPDATE content_job_prepared_results SET prepared_content=NULL,"
                 "preparation_identity='{}'::jsonb, "
                 "content_purged_at=clock_timestamp() WHERE job_id='job'")
    with pytest.raises(CheckViolation, match="immutable"):
        with authority_schema.transaction():
            authority_schema.execute(statement)
    _completed(authority_schema, at)
    with pytest.raises(CheckViolation, match="immutable"):
        with authority_schema.transaction():
            authority_schema.execute(statement)


def test_live_expired_purge_is_sql_null_and_cannot_resurrect(authority_schema) -> None:
    _running(authority_schema, JobTask.TRANSLATE)
    result, at = _prepared(authority_schema, JobTask.TRANSLATE, backdated=True)
    expiry = _completed(authority_schema, at)
    authority_schema.execute("UPDATE content_job_prepared_results SET prepared_content=NULL, "
                             "preparation_identity='{}'::jsonb,"
                             "content_purged_at=clock_timestamp() WHERE job_id='job'")
    row = authority_schema.execute(
        "SELECT prepared_content,expires_at,content_purged_at FROM content_job_prepared_results",
    ).fetchone()
    assert row[0] is None and row[1] == expiry and row[2] >= expiry
    with pytest.raises(CheckViolation, match="immutable"):
        with authority_schema.transaction():
            authority_schema.execute("UPDATE content_job_prepared_results SET prepared_content=%s, "
                                     "preparation_identity=%s::jsonb,content_purged_at=NULL "
                                     "WHERE job_id='job'",
                                     (result.serialized_content, result.serialized_identity))
