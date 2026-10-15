"""Real-PostgreSQL U3 corpus constraints: identity, ordering, watermark, CAS."""

from uuid import uuid4

import pytest

from fixtures import request_body, source_record
from backend.modules.corpus.maintenance import CorpusMaintenance

pytestmark = pytest.mark.u3_database


def test_canonical_identity_dedup_across_reordered_records(
    maintenance, run_fixture, fixture_discard, connect
):
    fixture_discard()
    first = run_fixture(["fixture-alpha"])
    assert first["state"] == "completed", first["effects"]

    with connect("corpus") as conn:
        version = conn.execute(
            "SELECT v.id,v.source_hash,p.id AS paper_id,count(c.ordinal) AS chunks "
            "FROM corpus.version v JOIN corpus.paper p ON p.id=v.paper_id "
            "LEFT JOIN corpus.projection c ON c.version_id=v.id GROUP BY v.id,p.id"
        ).fetchone()
    assert version["id"] == "paper-alpha:v1"
    assert version["chunks"] == 2

    # A second run over the same source resolves the same identity without new chunks.
    second = run_fixture(["fixture-alpha"], operation="incremental-refresh")
    assert second["state"] == "completed"
    with connect("corpus") as conn:
        count = conn.execute(
            "SELECT count(*) AS versions FROM corpus.version"
        ).fetchone()["versions"]
        chunks = conn.execute(
            "SELECT count(*) AS chunks FROM corpus.projection"
        ).fetchone()["chunks"]
    assert count == 1 and chunks == 2


def test_new_version_label_creates_distinct_version_under_same_paper(
    maintenance, authority, maintenance_authority, sources, fixture_discard, connect
):
    fixture_discard()

    def run(scope):
        accepted = maintenance.accept(authority, uuid4(), request_body("ingest", scope))
        maintenance.execute(accepted["runId"])
        return maintenance.read_run(authority, accepted["runId"])

    sources.records["fixture-alpha-v2"] = source_record(
        "fixture-alpha-v2", paper_id="paper-alpha", version_label="v2"
    )
    assert run(["fixture-alpha"])["state"] == "completed"
    assert run(["fixture-alpha-v2"])["state"] == "completed"
    with connect("corpus") as conn:
        rows = conn.execute(
            "SELECT id,version_label FROM corpus.version ORDER BY id"
        ).fetchall()
    assert [(row["id"], row["version_label"]) for row in rows] == [
        ("paper-alpha:v1", "v1"),
        ("paper-alpha:v2", "v2"),
    ]


def test_watermark_cannot_advance_past_outstanding_effects(
    maintenance, authority, maintenance_authority, fixture_discard, connect
):
    fixture_discard()
    accepted = maintenance.accept(
        authority, uuid4(), request_body("ingest", ["fixture-alpha"])
    )
    run_id = accepted["runId"]
    with connect("corpus") as conn:
        # The dispatch effect is pending until execution commits it.
        with pytest.raises(Exception) as denial:
            conn.execute(
                "UPDATE corpus.run SET watermark='{\"window\":\"x\"}'::jsonb WHERE id=%s",
                (run_id,),
            )
            conn.commit()
        assert "watermark cannot advance" in str(denial.value)
        conn.rollback()


def test_change_facts_are_ordered_and_append_only(
    maintenance, run_fixture, authority, maintenance_authority, fixture_discard, connect
):
    fixture_discard()
    assert run_fixture(["fixture-alpha"])["state"] == "completed"
    first = maintenance.record_change(
        authority,
        {
            "paperId": "paper-alpha",
            "versionId": "paper-alpha:v1",
            "changeKind": "license-change",
            "disposition": "restricted",
            "reasonKey": "license-changed",
            "policy": {"policyId": "u3-source-eligibility", "revision": "1"},
        },
    )
    second = maintenance.record_change(
        authority,
        {
            "paperId": "paper-alpha",
            "versionId": "paper-alpha:v1",
            "changeKind": "withdrawal",
            "disposition": "withdrawn",
            "reasonKey": "publisher-withdrawal",
            "policy": {"policyId": "u3-source-eligibility", "revision": "1"},
        },
    )
    assert second["position"] == first["position"] + 1
    facts = maintenance.read_changes(0)
    assert [fact["position"] for fact in facts] == [first["position"], second["position"]]
    with connect("corpus") as conn:
        with pytest.raises(Exception) as denial:
            conn.execute(
                "UPDATE corpus.change_fact SET detail='{}'::jsonb WHERE id=%s",
                (first["factId"],),
            )
            conn.commit()
        assert "append-only" in str(denial.value)
        conn.rollback()
        eligible = conn.execute(
            "SELECT eligible FROM corpus.version WHERE id='paper-alpha:v1'"
        ).fetchone()["eligible"]
        assert eligible is False


def test_withdrawal_removes_projection_and_denies_guarded_read(
    maintenance, run_fixture, authority, maintenance_authority, fixture_discard, connect
):
    fixture_discard()
    assert run_fixture(["fixture-alpha"])["state"] == "completed"
    maintenance.record_change(
        authority,
        {
            "paperId": "paper-alpha",
            "changeKind": "withdrawal",
            "disposition": "withdrawn",
            "reasonKey": "publisher-withdrawal",
            "policy": {"policyId": "u3-source-eligibility", "revision": "1"},
        },
    )
    with connect("corpus") as conn:
        chunks = conn.execute(
            "SELECT count(*) AS chunks FROM corpus.projection"
        ).fetchone()["chunks"]
        assert chunks == 0
        with pytest.raises(Exception):
            conn.execute(
                "SELECT corpus.guard_version('paper-alpha:v1','local-research')"
            )


def test_competing_publication_cas_preserves_previous_generation(
    maintenance, authority, maintenance_authority, fixture_discard, sources, connect
):
    fixture_discard()
    # Publish the first generation.
    first = maintenance.accept(
        authority, uuid4(), request_body("ingest", ["fixture-alpha"])
    )
    maintenance.execute(first["runId"])
    assert maintenance.read_run(authority, first["runId"])["state"] == "completed"
    with connect("corpus") as conn:
        published = conn.execute(
            "SELECT generation_id,published_generation FROM corpus.publication"
        ).fetchone()
    assert published["generation_id"] == published["published_generation"]

    # A competing publication moves the CAS target; a stale CAS refuses.
    with connect("corpus") as conn:
        stale = conn.execute(
            "SELECT generation_id FROM corpus.publication"
        ).fetchone()["generation_id"]
    with connect("corpus") as conn:
        refreshed = conn.execute(
            "UPDATE corpus.publication SET generation_id=%s,revision=gen_random_uuid() "
            "WHERE singleton AND generation_id=%s RETURNING generation_id",
            (uuid4(), stale),
        ).fetchone()
        assert refreshed is not None
        conn.commit()
    with connect("corpus") as conn:
        refused = conn.execute(
            "UPDATE corpus.publication SET generation_id=%s,revision=gen_random_uuid() "
            "WHERE singleton AND generation_id=%s RETURNING generation_id",
            (uuid4(), stale),
        ).fetchone()
        assert refused is None
        conn.rollback()


def test_run_idempotency_same_key_same_input_and_conflict(
    maintenance, authority, maintenance_authority, fixture_discard
):
    fixture_discard()
    key = uuid4()
    body = request_body("ingest", ["fixture-alpha"])
    first = maintenance.accept(authority, key, body)
    replay = maintenance.accept(authority, key, body)
    assert replay["runId"] == first["runId"]
    with pytest.raises(ValueError):
        maintenance.accept(authority, key, request_body("rebuild", ["fixture-alpha"]))


def test_retry_carries_only_reconcilable_effects(
    maintenance, authority, maintenance_authority, fixture_discard, sources, connect
):
    fixture_discard()

    class FailingSources:
        def __init__(self, records):
            self.records = records
            self.fail = True

        def read(self, source_id):
            if self.fail:
                raise RuntimeError("provider down")
            return self.records.get(source_id)

    failure_maintenance = CorpusMaintenance(
        maintenance.transactions, maintenance.files, FailingSources(sources.records)
    )
    body = request_body("ingest", ["fixture-alpha"])
    key = uuid4()
    accepted = failure_maintenance.accept(authority, key, body)
    with pytest.raises(RuntimeError):
        failure_maintenance.execute(accepted["runId"])
    # The interrupted run is reclaimed by a bounded retry with the same inputs.
    retry_key = uuid4()
    retry = maintenance.retry(authority, retry_key, {**body, "retryOf": accepted["runId"]})
    assert retry["runId"] != accepted["runId"]
    with connect("corpus") as conn:
        row = conn.execute(
            "SELECT retry_of,attempts FROM corpus.run WHERE id=%s", (retry["runId"],)
        ).fetchone()
    assert str(row["retry_of"]) == accepted["runId"] and row["attempts"] == 0
    outcome = maintenance.execute(retry["runId"])
    assert outcome["state"] == "completed"
    with connect("corpus") as conn:
        attempts = conn.execute(
            "SELECT attempts FROM corpus.run WHERE id=%s", (retry["runId"],)
        ).fetchone()["attempts"]
    assert attempts == 1


def test_foreign_owner_cannot_record_change(
    maintenance, identities, connect, fixture_discard
):
    """Account membership alone is insufficient: the actor must hold explicit authority."""
    fixture_discard()
    from backend.transactions import Authority

    # Owner B holds a valid session but no corpus-maintenance authority.
    with connect("accounts") as conn:
        conn.execute(
            "INSERT INTO accounts.session(id,account_id,token_hash,csrf_hash,"
            "authority_revision,expires_at) "
            "VALUES(gen_random_uuid(),%s,'u3-db-b-session','u3-db-b-csrf',%s,"
            "clock_timestamp()+interval '30 minutes')",
            (identities["b"], identities["revision"]),
        )
        session = conn.execute(
            "SELECT id FROM accounts.session WHERE account_id=%s", (identities["b"],)
        ).fetchone()["id"]
    foreign = Authority(identities["b"], session)
    with pytest.raises(PermissionError):
        maintenance.record_change(
            foreign,
            {
                "paperId": "paper-alpha",
                "changeKind": "withdrawal",
                "disposition": "withdrawn",
                "reasonKey": "probe",
                "policy": {"policyId": "u3-source-eligibility", "revision": "1"},
            },
        )
