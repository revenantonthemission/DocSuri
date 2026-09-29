"""Actual control publication/reader transactions, with synthetic producer/authority facts."""

import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from threading import Barrier
from urllib.parse import urlsplit

import psycopg
import pytest
from evidence_support import SUBJECT, request, result, verified_context
from psycopg.types.json import Jsonb
from run_support import context

from docsuri_platform_integrity.adapters.postgres import (
    ControlUnavailable,
    PostgresEvidenceReader,
    PostgresEvidenceStore,
)
from docsuri_platform_integrity.contracts.codec import canonical, digest
from docsuri_platform_integrity.contracts.models import GateVerdict
from docsuri_platform_integrity.domain.gate import evaluate, reserve_selection

DSN = os.environ.get("REM1_TEST_PG_DSN")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not DSN, reason="isolated REM1_TEST_PG_DSN required"),
]
MIGRATIONS = ("001_control.sql", "002_run_protocol.sql", "003_verification_protocol.sql")
ROOT = Path(__file__).resolve().parents[1] / "migrations"


@pytest.fixture
def store():
    parts = urlsplit(DSN)
    assert parts.hostname == "127.0.0.1" and parts.port == 15439 and parts.path == "/rem1_test"
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("DROP SCHEMA IF EXISTS r1_control CASCADE")
        conn.execute("DROP SCHEMA IF EXISTS r1_audit CASCADE")
        for name in MIGRATIONS:
            conn.execute((ROOT / name).read_text())
    return PostgresEvidenceStore(DSN)


def reserve(store, identity, revision="0"):
    return store.reserve(request(identity), expected_revision=revision, context=context("verify"))


def assert_gate(verdict):
    heads, records = PostgresEvidenceReader(DSN).snapshot(SUBJECT.subject)
    assert evaluate(
        SUBJECT, ("schema",), heads, records, lower=100, upper=100, trusted=True,
        current=verified_context(SUBJECT, records),
    ).verdict == verdict


def test_late_pass_is_retained_but_never_replaces_pending_or_failed_recheck(store):
    first = reserve(store, "first")
    second = reserve(store, "second", "1")
    passed = result(first)
    late = store.resolve(passed, context=context("verify"))
    assert not late.selected and late.head_revision == "2"
    assert_gate(GateVerdict.INCOMPLETE)
    failure = result(second, outcome="FAIL")
    assert store.resolve(failure, context=context("verify")).selected
    assert_gate(GateVerdict.BLOCKED)
    assert not store.resolve(passed, context=context("verify")).selected
    assert_gate(GateVerdict.BLOCKED)
    with psycopg.connect(DSN) as conn:
        assert conn.execute("SELECT count(*) FROM r1_control.evidence").fetchone()[0] == 2
        assert conn.execute("SELECT count(*) FROM r1_audit.events").fetchone()[0] == 4
        assert conn.execute("SELECT count(*) FROM r1_control.outbox").fetchone()[0] == 4


def test_concurrent_reservations_have_one_winner_and_no_orphan_request(store):
    barrier = Barrier(2)

    def contender(identity):
        barrier.wait(timeout=5)
        try:
            return reserve(PostgresEvidenceStore(DSN), identity)
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(contender, ("first", "second")))
    assert sum(outcome is not None for outcome in outcomes) == 1
    with psycopg.connect(DSN) as conn:
        assert conn.execute("SELECT count(*) FROM r1_control.verifications").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM r1_audit.events").fetchone()[0] == 1


def test_reservation_retry_and_old_retry_do_not_advance_or_restore_head(store):
    first = reserve(store, "first")
    assert reserve(store, "first") == first
    second = reserve(store, "second", "1")
    assert reserve(store, "first") == first
    head, _ = PostgresEvidenceReader(DSN).snapshot(SUBJECT.subject)
    assert head[0].verification_id == second.request.verification_id
    with pytest.raises(ValueError, match="meaning"):
        store.reserve(
            request("first").model_copy(update={"inputs": digest(b"changed")}),
            expected_revision="0", context=context("verify"),
        )


@pytest.mark.parametrize("during_resolution", [False, True])
def test_outbox_failure_rolls_back_the_entire_publication_command(store, during_resolution):
    reservation = reserve(store, "first") if during_resolution else None
    with psycopg.connect(DSN) as conn:
        conn.execute(
            "ALTER TABLE r1_control.outbox ADD CONSTRAINT reject_test_insert CHECK(false) NOT VALID"
        )
    with pytest.raises(ControlUnavailable):
        if reservation:
            store.resolve(result(reservation), context=context("verify"))
        else:
            reserve(store, "first")
    with psycopg.connect(DSN) as conn:
        expected = int(during_resolution)
        count = conn.execute("SELECT count(*) FROM r1_control.verifications").fetchone()[0]
        assert count == expected
        assert conn.execute("SELECT count(*) FROM r1_audit.events").fetchone()[0] == expected
        assert conn.execute("SELECT count(*) FROM r1_control.evidence").fetchone()[0] == 0
    assert_gate(GateVerdict.INCOMPLETE)


def test_lost_reservation_commit_ack_is_recovered_by_exact_identity(store):
    class LoseReply(PostgresEvidenceStore):
        @contextmanager
        def _transaction(self):
            with super()._transaction() as conn:
                yield conn
            raise ControlUnavailable("injected reply loss after commit")

    with pytest.raises(ControlUnavailable):
        reserve(LoseReply(DSN), "first")
    recovered = reserve(store, "first")
    assert recovered.revision == "1"
    with psycopg.connect(DSN) as conn:
        assert conn.execute("SELECT count(*) FROM r1_audit.events").fetchone()[0] == 1


def test_conflicting_terminal_result_and_wrong_purpose_are_rejected(store):
    reservation = reserve(store, "first")
    passed = result(reservation)
    store.resolve(passed, context=context("verify"))
    reserve(store, "second", "1")
    with pytest.raises(ValueError, match="conflict"):
        store.resolve(passed.model_copy(update={"outcome": "FAIL"}), context=context("verify"))
    with pytest.raises(PermissionError):
        store.resolve(passed, context=context("run"))
    assert_gate(GateVerdict.INCOMPLETE)


def test_database_rejects_head_rollback_and_same_revision_reset(store):
    first = reserve(store, "first")
    passed = result(first)
    store.resolve(passed, context=context("verify"))
    second = reserve(store, "second", "1")
    store.resolve(result(second, outcome="FAIL"), context=context("verify"))
    with psycopg.connect(DSN, autocommit=True) as conn:
        with pytest.raises(psycopg.errors.RaiseException):
            conn.execute(
                "UPDATE r1_control.heads SET revision=1,verification_id='first',evidence_id=%s",
                (passed.evidence_id,),
            )
        with pytest.raises(psycopg.errors.RaiseException):
            conn.execute("UPDATE r1_control.heads SET state='PENDING',evidence_id=NULL")
    assert_gate(GateVerdict.BLOCKED)


def test_database_requires_reservation_and_pending_head_in_the_same_commit(store):
    value = request()
    payload = value.model_dump(mode="json")
    with pytest.raises(psycopg.errors.RaiseException):
        with psycopg.connect(DSN) as conn:
            conn.execute(
                "INSERT INTO r1_control.verifications(verification_id,subject,slot,revision,"
                "previous_revision,request,digest) VALUES (%s,%s,%s,1,0,%s,%s)",
                (value.verification_id, value.subject.subject, value.slot,
                 Jsonb(payload), digest(canonical(payload))),
            )
    with psycopg.connect(DSN) as conn:
        assert conn.execute("SELECT count(*) FROM r1_control.verifications").fetchone()[0] == 0


def test_legacy_evidence_survives_upgrade_without_invented_binding(store):
    legacy = result(reserve_selection(request(), None, expected_revision="0"))
    legacy = legacy.model_copy(update={"verification_id": None})
    payload = legacy.model_dump(mode="json")
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("DROP SCHEMA r1_control CASCADE")
        conn.execute("DROP SCHEMA r1_audit CASCADE")
        for name in MIGRATIONS[:2]:
            conn.execute((ROOT / name).read_text())
        conn.execute(
            "INSERT INTO r1_control.evidence(evidence_id,subject,payload,digest) "
            "VALUES (%s,%s,%s,%s)",
            (legacy.evidence_id, SUBJECT.subject, Jsonb(payload), digest(canonical(payload))),
        )
        conn.execute(
            "INSERT INTO r1_control.heads(subject,slot,revision,state,evidence_id) "
            "VALUES (%s,'schema',1,'RESOLVED',%s)", (SUBJECT.subject, legacy.evidence_id),
        )
        conn.execute((ROOT / MIGRATIONS[2]).read_text())
    heads, records = PostgresEvidenceReader(DSN).snapshot(SUBJECT.subject)
    assert records == (legacy,) and heads[0].verification_id is None
    assert_gate(GateVerdict.INCOMPLETE)
    with pytest.raises(ValueError, match="unbound"):
        reserve(store, "new", "1")


def test_signed_store_to_read_service_uses_current_head_without_read_side_writes(store):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    from docsuri_platform_integrity.adapters.authority import (
        CurrentEvidenceVerifier,
        CurrentReadAuthority,
        EvidenceVerificationKey,
        ReadGrant,
    )
    from docsuri_platform_integrity.application.evidence import EvidenceService
    from docsuri_platform_integrity.contracts.codec import sign
    from docsuri_platform_integrity.contracts.models import ValidityWindow

    record = result(reserve(store, "first"))
    store.resolve(record, context=context("verify"))
    private = Ed25519PrivateKey.generate()
    key = EvidenceVerificationKey(
        "synthetic-key", private.public_key(), frozenset({SUBJECT.subject}), "current-1",
        ValidityWindow(valid_from="0", valid_until="1000"), False,
    )
    envelope = sign(
        record.model_dump(mode="json"), kind="evidence", purpose="attest",
        key_id=key.key_id, key=private,
    )
    grant = ReadGrant("cert", frozenset({SUBJECT.subject}), 1000)
    service = EvidenceService(
        PostgresEvidenceReader(DSN),
        CurrentReadAuthority(lambda _: grant, lambda: (100, 100)), lambda: (100, 100),
        {SUBJECT.subject: (SUBJECT, ("schema",))},
        current=CurrentEvidenceVerifier(lambda _: SUBJECT, lambda _: envelope, lambda *_: key),
    )
    assert service.read("cert", SUBJECT.subject).eligible
    reserve(store, "second", "1")
    assert service.read("cert", SUBJECT.subject).verdict == GateVerdict.INCOMPLETE
    with psycopg.connect(DSN) as conn:
        assert conn.execute("SELECT count(*) FROM r1_audit.events").fetchone()[0] == 3
        assert conn.execute("SELECT count(*) FROM r1_control.evidence").fetchone()[0] == 1
