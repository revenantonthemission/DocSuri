import os
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from evidence_support import SUBJECT, request, result
from run_support import context

from docsuri_platform_integrity.adapters.postgres import (
    PostgresEvidenceReader,
    PostgresEvidenceStore,
)

DSN = os.environ.get("REM1_TEST_PG_DSN")
pytestmark = pytest.mark.skipif(not DSN, reason="isolated REM1_TEST_PG_DSN required")


def test_control_cas_and_audit_share_transaction():
    import psycopg

    parts = urlsplit(DSN)
    assert parts.hostname == "127.0.0.1" and parts.port == 15439 and parts.path == "/rem1_test"
    root = Path(__file__).resolve().parents[1] / "migrations"
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("DROP SCHEMA IF EXISTS r1_control CASCADE")
        conn.execute("DROP SCHEMA IF EXISTS r1_audit CASCADE")
        for name in ("001_control.sql", "002_run_protocol.sql", "003_verification_protocol.sql"):
            conn.execute((root / name).read_text())
    store = PostgresEvidenceStore(DSN)
    reservation = store.reserve(request(), expected_revision="0", context=context("verify"))
    record = result(reservation)
    with pytest.raises(ValueError):
        store.resolve(record.model_copy(update={"revision": "2"}), context=context("verify"))
    with psycopg.connect(DSN) as conn:
        assert conn.execute("SELECT count(*) FROM r1_control.evidence").fetchone()[0] == 0
    assert store.resolve(record, context=context("verify")).selected
    with psycopg.connect(DSN, autocommit=True) as conn:
        assert conn.execute("SELECT count(*) FROM r1_audit.events").fetchone()[0] == 2
        assert conn.execute("SELECT count(*) FROM r1_control.outbox").fetchone()[0] == 2
        with pytest.raises(psycopg.errors.RaiseException):
            conn.execute("DELETE FROM r1_audit.events")
    heads, records = PostgresEvidenceReader(DSN).snapshot(SUBJECT.subject)
    assert heads[0].evidence_id == record.evidence_id and records == (record,)
