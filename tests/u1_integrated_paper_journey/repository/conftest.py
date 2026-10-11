from __future__ import annotations

import hashlib

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
            "SELECT id,payload,source_hash,reservation_id FROM assistance.job WHERE account_id=%s LIMIT 1025",
            (identities["a"],),
        ).fetchall()
    if len(rows) > 1024:
        raise AssertionError("diagnostic history allocation exceeded; retain evidence and stop")
    identifiers = [row["id"] for row in rows]
    # Preserve all historical job/result evidence. Batch only owner-scoped reads;
    # every recognized record still passes the exact refusal rules below.
    with connect("usage") as usage:
        reservations = usage.execute(
            "SELECT operation_id,account_id FROM usage.reservation WHERE operation_id=ANY(%s)",
            (identifiers,),
        ).fetchall()
        if any(row[1] != identities["a"] for row in reservations):
            raise AssertionError("diagnostic reservation owner mismatch; reset refused")
        reserved = {row[0] for row in reservations}
    with connect("assistance") as assistance:
        published = assistance.execute(
            "SELECT job_id,provenance,output_hash,account_id FROM assistance.result WHERE job_id=ANY(%s)",
            (identifiers,),
        ).fetchall()
        if any(row[3] != identities["a"] for row in published):
            raise AssertionError("diagnostic result owner mismatch; reset refused")
        results = {row[0]: row[1:3] for row in published}
        known = assistance.execute(
            "SELECT operation_id FROM assistance.admission WHERE account_id=%s AND intent->>'fixtureFamily'='repository-boundary' LIMIT 1025",
            (identities["a"],),
        ).fetchall()
    if len(known) > 1024:
        raise AssertionError("diagnostic admission allocation exceeded; retain evidence and stop")
    permitted = []
    for row in rows:
        reservation = row["id"] in reserved
        result = results.get(row["id"])
        if row["payload"] == {} and row["source_hash"] == "a" * 64:
            if reservation or result:
                raise AssertionError("DB fixture unexpectedly has accounting/result; reset refused")
        elif row["payload"].get("fixtureFamily") == "repository-boundary":
            worker_fixture = (
                result
                and result[0]
                == {
                    "fixtureFamily": "repository-boundary",
                    "normalModelReadiness": False,
                }
                and result[1]
                == hashlib.sha256(b"diagnostic worker fixture, not a model answer").hexdigest()
            )
            if result and result[0] != {"testBoundary": True} and not worker_fixture:
                raise AssertionError("normal model result; reset refused")
        else:
            raise AssertionError("unknown accepted work; phase reset refused")
        permitted.append(row["id"])
    with connect("assistance") as conn:
        conn.execute(
            "UPDATE assistance.job SET state=CASE WHEN state IN ('accepted','running') THEN 'failed' ELSE state END,failure_code=CASE WHEN state IN ('accepted','running') THEN 'diagnostic-fixture-complete' ELSE failure_code END,settlement_pending=false WHERE account_id=%s AND id=ANY(%s)",
            (identities["a"], permitted),
        )
        conn.execute(
            "UPDATE assistance.admission SET disposition='rejected' WHERE account_id=%s AND disposition='open' AND intent->>'fixtureFamily'='repository-boundary'",
            (identities["a"],),
        )
    with connect("usage") as conn:
        conn.execute(
            "DELETE FROM usage.reservation WHERE operation_id=ANY(%s) AND account_id=%s",
            ([row[0] for row in known], identities["a"]),
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
