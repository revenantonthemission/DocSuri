from __future__ import annotations

from psycopg.rows import dict_row
import pytest

from backend.artifacts import PrivateArtifacts
from backend.transactions import Authority, OwnerTransactions
from backend.modules.library.repository.guarded import GuardedLibraryRepository
from backend.modules.summarization.guarded_repository import GuardedAssistanceRepository
from backend.modules.plans.guarded_repository import GuardedUsageRepository


@pytest.fixture
def repositories(realm, connect, identities):
    """Close only recognizable diagnostic jobs; never normal accepted work.

    DB-layer fixtures used empty payloads/hash-a with no result or reservation.
    Repository cases mark every intended operation with this exact test family.
    Synthetic byte fixtures prove storage only, never useful model output.
    """
    with connect("assistance") as conn:
        conn.row_factory = dict_row
        rows = conn.execute(
            "SELECT id,payload,source_hash,reservation_id FROM assistance.job WHERE account_id=%s",
            (identities["a"],),
        ).fetchall()
    permitted = []
    for row in rows:
        with connect("usage") as usage:
            reservation = usage.execute(
                "SELECT id FROM usage.reservation WHERE operation_id=%s", (row["id"],)
            ).fetchone()
        with connect("assistance") as assistance:
            result = assistance.execute(
                "SELECT provenance FROM assistance.result WHERE job_id=%s", (row["id"],)
            ).fetchone()
        if row["payload"] == {} and row["source_hash"] == "a" * 64:
            if reservation or result:
                raise AssertionError("DB fixture unexpectedly has accounting/result; reset refused")
        elif row["payload"].get("fixtureFamily") == "repository-boundary":
            if result and result[0] != {"testBoundary": True}:
                raise AssertionError("normal model result; reset refused")
        else:
            raise AssertionError("unknown accepted work; phase reset refused")
        permitted.append(row["id"])
    with connect("assistance") as conn:
        for job in permitted:
            conn.execute(
                "UPDATE assistance.job SET state=CASE WHEN state IN ('accepted','running') THEN 'failed' ELSE state END,failure_code=CASE WHEN state IN ('accepted','running') THEN 'diagnostic-fixture-complete' ELSE failure_code END,settlement_pending=false WHERE id=%s",
                (job,),
            )
        conn.execute(
            "UPDATE assistance.admission SET disposition='rejected' WHERE account_id=%s AND disposition='open' AND intent->>'fixtureFamily'='repository-boundary'",
            (identities["a"],),
        )
        known = conn.execute(
            "SELECT operation_id FROM assistance.admission WHERE account_id=%s AND intent->>'fixtureFamily'='repository-boundary'",
            (identities["a"],),
        ).fetchall()
    with connect("usage") as conn:
        for row in known:
            conn.execute(
                "DELETE FROM usage.reservation WHERE operation_id=%s AND account_id=%s",
                (row[0], identities["a"]),
            )
        conn.execute(
            "INSERT INTO usage.entitlement(account_id,allocation,policy) VALUES(%s,4,'synthetic-four-no-reset') ON CONFLICT DO NOTHING",
            (identities["a"],),
        )
    tx = OwnerTransactions(realm[0])
    files = PrivateArtifacts(realm[0].root / "assistance-files")
    authority = Authority(identities["a"], identities["session"])
    yield {
        "tx": tx,
        "files": files,
        "authority": authority,
        "ids": identities,
        "library": GuardedLibraryRepository(tx),
        "pa": GuardedAssistanceRepository(tx, files),
        "usage": GuardedUsageRepository(tx),
    }
    tx.close()
