"""U3 bounded-profile operations: finite limits, reserves and clean refusals."""

from uuid import uuid4

import pytest

from backend.modules.corpus.maintenance import CorpusMaintenance
from backend.u3_policy import limits_document
from fixtures import MemorySources, request_body

pytestmark = pytest.mark.u3_operations


def test_finite_limits_are_declared_and_enforced(
    maintenance, authority, maintenance_authority, fixture_discard
):
    fixture_discard()
    document = limits_document()
    assert document["maxRunBatch"] >= 1 and document["maxCitationNodes"] <= 64
    with pytest.raises(ValueError):
        maintenance.execute(uuid4(), limit=document["maxRunBatch"] + 1)
    with pytest.raises(ValueError):
        maintenance.pending_runs(limit=99)


def test_exhausted_scope_allocation_rejects_cleanly(
    transactions, authority, maintenance_authority, fixture_discard, realm
):
    """A scope beyond the finite batch bound is refused before any work."""
    fixture_discard()
    from backend.artifacts import PrivateArtifacts

    maintenance = CorpusMaintenance(
        transactions,
        PrivateArtifacts(realm[0].root / "corpus-files", maximum_bytes=2097152),
        MemorySources({}),
    )
    with pytest.raises(ValueError):
        maintenance.accept(
            authority,
            uuid4(),
            request_body("ingest", [f"fixture-{index}" for index in range(9)]),
        )


def test_retry_allocation_is_exhausted_explicitly(
    maintenance, authority, maintenance_authority, fixture_discard, sources, connect
):
    """Repeated retries stop at the declared finite retry allocation."""
    fixture_discard()

    class Failing(MemorySources):
        def read(self, source_id):
            raise RuntimeError("provider down")

    failing = CorpusMaintenance(
        maintenance.transactions,
        maintenance.files,
        Failing(sources.records),
    )
    body = request_body("ingest", ["fixture-alpha"])
    first = failing.accept(authority, uuid4(), body)
    with pytest.raises(RuntimeError):
        failing.execute(first["runId"])
    previous = first["runId"]
    for _ in range(2):
        retry = maintenance.retry(
            authority, uuid4(), {**body, "retryOf": previous}
        )
        previous = retry["runId"]
        with connect("corpus") as conn:
            conn.execute(
                "UPDATE corpus.run SET state='failed' WHERE id=%s", (previous,)
            )
            conn.commit()
    with pytest.raises(ValueError):
        maintenance.retry(authority, uuid4(), {**body, "retryOf": previous})


def test_missing_owner_relation_is_a_failed_prerequisite(
    realm, fixture_discard
):
    """A missing required store fails loudly instead of an in-memory substitute."""
    fixture_discard()
    import psycopg

    from backend.transactions import OwnerTransactions

    transactions = OwnerTransactions(realm[0])
    try:
        with pytest.raises(psycopg.errors.UndefinedTable):
            transactions.run(
                "corpus", lambda conn: conn.execute("SELECT 1 FROM corpus.no_such_table")
            )
    finally:
        transactions.close()


def test_capacity_refusal_is_explicit_and_preserves_committed_state(
    maintenance, authority, maintenance_authority, fixture_discard
):
    """Exhaustion refuses new effects; already committed rows stay intact."""
    fixture_discard()
    accepted = maintenance.accept(
        authority, uuid4(), request_body("ingest", ["fixture-alpha"])
    )
    with pytest.raises(ValueError):
        maintenance.execute(accepted["runId"], limit=0)
    run = maintenance.read_run(authority, accepted["runId"])
    assert run["state"] in ("accepted", "running")
    assert run["watermark"] is None
