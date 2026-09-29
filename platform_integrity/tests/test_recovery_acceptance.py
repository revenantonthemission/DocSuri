"""Disposable PG dump/restore drill. Physical encrypted/off-host acceptance is separate."""

import os
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

import psycopg
import pytest
from evidence_support import SUBJECT, request, result, verified_context
from run_support import context

from docsuri_platform_integrity.adapters.postgres import (
    PostgresEvidenceReader,
    PostgresEvidenceStore,
)
from docsuri_platform_integrity.contracts.models import GateVerdict
from docsuri_platform_integrity.domain.gate import evaluate

DSN = os.environ.get("REM1_TEST_PG_DSN")
CONTAINER = os.environ.get("REM1_TEST_CONTAINER")
pytestmark = pytest.mark.skipif(
    not DSN or not CONTAINER, reason="explicit disposable recovery realm required"
)


def test_restore_preserves_history_but_new_incarnation_cannot_reuse_old_pass():
    parsed = urlsplit(DSN)
    assert parsed.hostname == "127.0.0.1" and parsed.port == 15439 and parsed.path == "/rem1_test"
    assert CONTAINER == "rem1-test-pg-20260924"
    migrations = Path(__file__).resolve().parents[1] / "migrations"
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("DROP SCHEMA IF EXISTS r1_control CASCADE")
        conn.execute("DROP SCHEMA IF EXISTS r1_audit CASCADE")
        for name in (
            "001_control.sql", "002_run_protocol.sql", "003_verification_protocol.sql",
            "004_operator_authority.sql",
        ):
            conn.execute((migrations / name).read_text())
        conn.execute("DROP DATABASE IF EXISTS rem1_restore_test WITH (FORCE)")
        conn.execute("CREATE DATABASE rem1_restore_test")
    store = PostgresEvidenceStore(DSN)
    record = result(store.reserve(request(), expected_revision="0", context=context("verify")))
    store.resolve(record, context=context("verify"))
    dumped = subprocess.run(
        ["docker", "exec", CONTAINER, "pg_dump", "-U", "rem1_test", "-d", "rem1_test",
         "-Fc", "--schema=r1_control", "--schema=r1_audit"],
        capture_output=True, timeout=30, check=True,
    ).stdout
    assert 0 < len(dumped) < 16 * 1024**2
    subprocess.run(
        ["docker", "exec", "-i", CONTAINER, "pg_restore", "-U", "rem1_test", "-d",
         "rem1_restore_test", "--no-owner"],
        input=dumped, capture_output=True, timeout=30, check=True,
    )
    restored_dsn = DSN.rsplit("/", 1)[0] + "/rem1_restore_test"
    heads, records = PostgresEvidenceReader(restored_dsn).snapshot(SUBJECT.subject)
    assert records == (record,)
    fresh_subject = SUBJECT.model_copy(update={"incarnation": "restored-install"})
    evaluated = evaluate(
        fresh_subject, ("schema",), heads, records, lower=100, upper=100, trusted=True,
        current=verified_context(fresh_subject, records),
    )
    assert evaluated.verdict == GateVerdict.STALE and not evaluated.eligible
    with psycopg.connect(restored_dsn) as conn:
        assert conn.execute("SELECT count(*) FROM r1_audit.events").fetchone()[0] == 2
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("DROP DATABASE rem1_restore_test WITH (FORCE)")
