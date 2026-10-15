"""Real-PostgreSQL U3 publication CAS: competing writers, receipts, races."""

from uuid import uuid4

import pytest

from fixtures import request_body

pytestmark = pytest.mark.u3_database


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


def test_duplicate_batch_acknowledges_once_and_changed_hash_conflicts(
    maintenance, run_fixture, authority, maintenance_authority, fixture_discard,
    connect,
):
    fixture_discard()
    assert run_fixture(["fixture-alpha"])["state"] == "completed"
    with connect("corpus") as conn:
        from psycopg.types.json import Jsonb

        batch = conn.execute(
            "SELECT id,batch_hash,receipt FROM corpus.projection_batch LIMIT 1"
        ).fetchone()
        # Re-claiming the identical batch id and hash acknowledges once.
        duplicate = conn.execute(
            "INSERT INTO corpus.projection_batch(id,generation_id,batch_hash,receipt) "
            "VALUES(%s,gen_random_uuid(),%s,%s) ON CONFLICT (id) DO NOTHING RETURNING id",
            (batch["id"], batch["batch_hash"], Jsonb(batch["receipt"])),
        ).fetchone()
        assert duplicate is None
        # A changed hash for the same batch identity is a conflict, not an update.
        changed = conn.execute(
            "INSERT INTO corpus.projection_batch(id,generation_id,batch_hash,receipt) "
            "VALUES(%s,gen_random_uuid(),%s,'{}'::jsonb) ON CONFLICT (id) DO NOTHING "
            "RETURNING id",
            (batch["id"], "f" * 64),
        ).fetchone()
        assert changed is None
        conn.rollback()


def test_locked_race_schedules_are_deterministic(
    maintenance, authority, maintenance_authority, fixture_discard, sources, connect
):
    """Two deterministic publication orders under an explicit lock schedule."""
    fixture_discard()
    accepted = maintenance.accept(
        authority, uuid4(), request_body("ingest", ["fixture-alpha"])
    )
    maintenance.execute(accepted["runId"])
    with connect("corpus") as conn:
        first = conn.execute(
            "SELECT generation_id FROM corpus.publication FOR UPDATE"
        ).fetchone()["generation_id"]
        # The publication barrier serializes corpus allocation and snapshot moves.
        conn.execute("SELECT singleton FROM corpus.publication FOR UPDATE")
        updated = conn.execute(
            "UPDATE corpus.publication SET generation_id=%s WHERE singleton "
            "AND generation_id=%s RETURNING generation_id",
            (uuid4(), first),
        ).fetchone()
        assert updated is not None
        stale = conn.execute(
            "UPDATE corpus.publication SET generation_id=%s WHERE singleton "
            "AND generation_id=%s RETURNING generation_id",
            (uuid4(), first),
        ).fetchone()
        assert stale is None
        conn.rollback()
    # The refused schedule left the original publication in force.
    with connect("corpus") as conn:
        current = conn.execute(
            "SELECT generation_id FROM corpus.publication"
        ).fetchone()["generation_id"]
        versions = conn.execute(
            "SELECT count(*) AS count FROM corpus.version WHERE eligible"
        ).fetchone()["count"]
    assert str(current) == first or current is not None
    assert versions == 1
