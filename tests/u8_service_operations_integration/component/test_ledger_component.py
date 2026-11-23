"""The ledger component: typed records, folding, revisions and damage (U8 plan Step 14).

Each test uses a real ledger folder in a private temporary folder; nothing is mocked.
"""

from __future__ import annotations

import os
from uuid import uuid4

import pytest

from backend.modules.operations.errors import LedgerDamaged, OperationsError
from backend.modules.operations.ledger import Ledger, LedgerStore
from backend.modules.operations.ledger_records import (
    RECEIPT_BEARING,
    RECOVERY_KINDS,
    SCHEMAS,
    RecordRefused,
)

T = "2026-10-22T03:00:00.000Z"
LATER = "2026-11-05T03:00:00.000Z"
DIGEST = "b" * 64


def ident() -> str:
    return str(uuid4())


def receipt_facts(receipt_id: str, operation: str = "platform.database.backup") -> dict:
    return {
        "receiptId": receipt_id, "operationId": ident(), "operation": operation,
        "targetId": "docsuri_u8", "inputHash": "c" * 64, "outcome": "succeeded",
        "confirmedAt": T,
    }


def samples() -> dict[str, dict]:
    """One valid first version of every keyed kind."""
    receipt = ident()
    return {
        "service-incident": {
            "incidentId": ident(), "environment": "live", "revision": 1,
            "capabilities": ["export"], "correlationIds": [], "state": "open", "openedAt": T,
            "openedBy": "tolerance-exceeded", "recoveryRequestIds": [], "evidenceRefs": [],
        },
        "recovery-request": {
            "recoveryRequestId": ident(), "revision": 1, "environment": "live",
            "origin": "schedule", "operation": "backup.create", "targetId": "docsuri_u8",
            "expectedRevision": 0, "submissionId": ident(), "idempotencyKey": DIGEST,
            "state": "requested", "evidenceRefs": [], "createdAt": T, "updatedAt": T,
        },
        "backup-set": {
            "backupId": ident(), "environment": "live", "revision": 1, "trigger": "scheduled",
            "takenAt": T, "checksum": DIGEST, "sizeBytes": 1024, "sourceDatabaseBytes": 4096,
            "location": "archives/live-1.dump", "databaseIncarnation": "cluster:docsuri_u8:1",
            "stagingLocation": "staging/live-1.dump", "retainUntil": LATER,
            "integrity": "passed", "operatorReceiptRef": receipt,
        },
        "restore-verification": {
            "verificationId": ident(), "environment": "live", "backupId": ident(),
            "startedAt": T, "registerHeadSequence": 0, "registerHeadDigest": "0" * 64,
            "evidenceRef": "evidence/verification-1.json",
        },
        "restore-tombstone": {
            "sequence": 1, "accountId": ident(), "lifecycleRequestId": ident(),
            "appendedAt": T, "previousDigest": "0" * 64, "digest": DIGEST,
        },
        "ledger-copy": {
            "ledgerCopyId": ident(), "takenAt": T, "location": "archives/ledger-1.jsonl",
            "stagingLocation": "staging/ledger-1.jsonl", "digest": DIGEST, "headSequence": 3,
            "headDigest": DIGEST, "retainUntil": LATER, "operatorReceiptRef": receipt,
        },
        "retained-copy": {
            "copyId": ident(), "kind": "import-database", "sourceRef": ident(),
            "createdAt": T, "locations": ["db:docsuri_u8_import_0123456789ab"],
            "disposeAfter": LATER,
        },
        "provider-activation": {
            "provider": "resend", "outward": True, "state": "held", "limitations": [],
        },
        "consumer-inventory": {
            "inventoryId": ident(), "observedFrom": T, "observedUntil": LATER,
            "consumers": [{"clientRef": "client-1", "routesUsed": ["/api/papers"],
                           "source": "observed"}],
            "complete": False,
        },
        "cutover-record": {
            "cutoverId": ident(), "releaseTag": "v2.0.0", "state": "preparing",
            "soakPeriodSeconds": 604800, "soakClean": False, "switchTimeBoundSeconds": 14400,
            "rollbackWindowSeconds": 1209600, "effectReceipts": [], "approvals": [],
        },
        "maintainer-approval": {
            "approvalId": ident(), "step": "dry-run-go-ahead", "subjectRef": ident(),
            "subjectDigest": DIGEST, "decision": "approved", "recordedAt": T,
            "operatorReceiptRef": receipt,
        },
        "migration-run": {
            "runId": ident(), "kind": "dry", "target": "rehearsal", "toolCommit": "a" * 40,
            "decisionsDigest": DIGEST, "state": "preparing", "startedAt": T,
        },
        "misfit-record": {
            "runId": ident(), "kind": "account", "sourceId": "v1-account-17",
            "reasonKey": "no-email", "newInFinal": False,
        },
        "misfit-decision": {
            "kind": "account", "reasonKey": "no-email", "decision": "archive-only",
            "decidedAt": T, "approvalId": ident(), "frozen": False,
        },
        "parity-report": {
            "runId": ident(), "reportRef": "evidence/parity/run-1.json",
            "reportDigest": DIGEST, "kinds": 19, "reconciles": True, "recordedAt": T,
        },
        "email-allowance": {
            "reservationId": ident(), "mailKind": "digest", "messageKey": ident(),
            "day": "2026-10-22", "month": "2026-10", "state": "reserved", "reservedAt": T,
            "updatedAt": T,
        },
        "release-record": {
            "releaseTag": "v2.0.0", "releaseCommit": "d" * 40, "state": "installed",
            "installedAt": T, "updatedAt": T,
        },
        "receipt-facts": receipt_facts(ident()),
        "lifecycle-evidence": {
            "requestId": ident(), "scope": "backups", "action": "erase", "state": "waiting",
            "reasonKey": "backup-schedule-inactive", "recordedAt": T,
        },
    }


def receipts_for(kind: str, record: dict) -> list[dict]:
    schema = SCHEMAS[kind]
    return [receipt_facts(ref) for ref in schema.cited_receipts(record)]


@pytest.fixture
def component(tmp_path, clock):
    folder = tmp_path / "ledger"
    folder.mkdir(mode=0o700)
    ledger = Ledger.open(folder, clock=clock)
    yield ledger
    ledger.close()


KEYED = sorted(kind for kind, schema in SCHEMAS.items() if schema.keyed)


def test_every_keyed_kind_has_a_sample_and_the_unkeyed_ones_are_recovery_records():
    assert set(samples()) == set(KEYED)
    assert {kind for kind, schema in SCHEMAS.items() if not schema.keyed} == RECOVERY_KINDS


@pytest.mark.parametrize("kind", KEYED)
def test_each_kind_refuses_an_unregistered_field_and_free_text(component, kind):
    record = samples()[kind]
    with pytest.raises(RecordRefused) as unregistered:
        component.append(kind, {**record, "note": "anything"}, expect_revision=0)
    assert unregistered.value.category == "unregistered-field"
    assert "anything" not in str(unregistered.value)
    text_fields = [
        name for name, value in record.items()
        if isinstance(value, str) and name not in SCHEMAS[kind].key
    ] or [name for name, value in record.items() if isinstance(value, str)]
    for name in text_fields:
        for value in ("Private words with spaces", "person@example.com"):
            with pytest.raises(RecordRefused) as free:
                component.append(kind, {**record, name: value}, expect_revision=0)
            assert free.value.category == "field-form" and value not in str(free.value)
    assert component.head.count == 0


@pytest.mark.parametrize("kind", KEYED)
def test_each_sample_appends_with_its_receipt_facts(component, kind):
    record = samples()[kind]
    appended = component.append(kind, record, expect_revision=0,
                                receipts=receipts_for(kind, record))
    assert appended.revision == 1
    assert component.get(kind, SCHEMAS[kind].key_of(record)) == record


def test_a_batch_holds_signals_back_so_an_interrupt_lands_after_its_last_write(component,
                                                                            monkeypatch):
    """Review finding (Minor, R18): a batch's writes run with SIGINT, SIGTERM and SIGHUP
    held back, so a signal that arrives between two of its writes is delivered once the
    last is written: every append of the batch is in the ledger, none is lost, and the
    interruption still reaches the caller afterwards. A refusal inside the batch still
    writes nothing, as built."""
    import os
    import signal

    from backend.modules.operations.ledger import ChainedLog

    first, second = samples()["service-incident"], samples()["backup-set"]
    receipts = receipts_for("backup-set", second)
    writes = []
    write_line = ChainedLog._write_line

    def signalled(self, raw):
        writes.append(raw)
        if len(writes) == 1:
            os.kill(os.getpid(), signal.SIGINT)  # between the first write and the second
        write_line(self, raw)

    monkeypatch.setattr(ChainedLog, "_write_line", signalled)
    with pytest.raises(KeyboardInterrupt):
        component.atomic(lambda view: view.append_all([
            ("service-incident", first, 0, ()), ("backup-set", second, 0, receipts)]))
    assert component.get("service-incident", first["incidentId"]) == first
    assert component.get("backup-set", second["backupId"]) == second
    assert signal.pthread_sigmask(signal.SIG_BLOCK, set()) == set()  # nothing left held
    # A refused batch writes nothing, before any signal is held.
    before = component.head.count
    with pytest.raises(OperationsError):
        component.atomic(lambda view: view.append_all([
            ("service-incident", {**first, "incidentId": ident()}, 0, ()),
            ("backup-set", second, 0, receipts)]))  # stale: revision 1 now
    assert component.head.count == before


def test_folding_rebuilds_each_entity_after_a_reopen(tmp_path, clock):
    folder = tmp_path / "ledger"
    folder.mkdir(mode=0o700)
    ledger = Ledger.open(folder, clock=clock)
    incident = samples()["service-incident"]
    ledger.append("service-incident", incident, expect_revision=0)
    investigating = {**incident, "revision": 2, "state": "investigating",
                     "diagnosisKey": "store-unavailable"}
    ledger.append("service-incident", investigating, expect_revision=1)
    backup = samples()["backup-set"]
    ledger.append("backup-set", backup, expect_revision=0,
                  receipts=receipts_for("backup-set", backup))
    disposed = {**backup, "disposedAt": LATER}
    ledger.append("backup-set", disposed, expect_revision=1)
    ledger.close()

    reopened = Ledger.open(folder, clock=clock)
    try:
        key = (incident["incidentId"],)
        assert reopened.get("service-incident", key) == investigating
        assert reopened.revision("service-incident", key) == 2
        assert reopened.get("backup-set", backup["backupId"]) == disposed
        assert reopened.revision("backup-set", backup["backupId"]) == 2
        assert len(reopened.records("receipt-facts")) == 1
        assert reopened.head.count == 5
    finally:
        reopened.close()


def test_a_stale_expect_revision_is_a_conflict_and_appends_nothing(component):
    incident = samples()["service-incident"]
    component.append("service-incident", incident, expect_revision=0)
    head = component.head
    with pytest.raises(OperationsError) as raised:
        component.append("service-incident", {**incident, "revision": 2,
                                              "state": "investigating"}, expect_revision=0)
    assert raised.value.code == "STALE_REVISION" and raised.value.current == {"revision": 1}
    with pytest.raises(OperationsError):
        component.append("service-incident", incident, expect_revision=0)
    assert component.head == head


def test_a_writer_in_another_process_is_seen_before_the_revision_compares(tmp_path, clock):
    folder = tmp_path / "ledger"
    folder.mkdir(mode=0o700)
    first, second = Ledger.open(folder, clock=clock), Ledger.open(folder, clock=clock)
    try:
        incident = samples()["service-incident"]
        first.append("service-incident", incident, expect_revision=0)
        with pytest.raises(OperationsError):
            second.append("service-incident", incident, expect_revision=0)
        assert second.revision("service-incident", incident["incidentId"]) == 1
    finally:
        first.close()
        second.close()


def test_the_machines_immutable_fields_and_cited_receipts_are_enforced(component):
    incident = samples()["service-incident"]
    component.append("service-incident", incident, expect_revision=0)
    with pytest.raises(RecordRefused) as transition:
        component.append("service-incident", {**incident, "revision": 2, "state": "recovering"},
                         expect_revision=1)
    assert transition.value.category == "state-transition"
    with pytest.raises(RecordRefused) as immutable:
        component.append("service-incident", {**incident, "revision": 2, "environment":
                                              "rehearsal"}, expect_revision=1)
    assert immutable.value.category == "immutable-field"
    with pytest.raises(RecordRefused) as resolved:
        component.append("service-incident", {**incident, "revision": 2, "state": "resolved"},
                         expect_revision=1)
    assert resolved.value.category == "rule"
    backup = samples()["backup-set"]
    with pytest.raises(RecordRefused) as missing:
        component.append("backup-set", backup, expect_revision=0)
    assert missing.value.category == "receipt-facts-missing"
    assert "backup-set" in RECEIPT_BEARING and "service-incident" not in RECEIPT_BEARING


def test_damage_refuses_dependent_writes_and_marks_the_check_unavailable(tmp_path, clock):
    folder = tmp_path / "ledger"
    folder.mkdir(mode=0o700)
    ledger = Ledger.open(folder, clock=clock)
    try:
        for _ in range(3):
            ledger.append("service-incident", samples()["service-incident"], expect_revision=0)
        assert ledger.check()["status"] == "available"
        # Another writer forges the middle entry, keeping every length and the head.
        path = folder / LedgerStore.LOG
        lines = path.read_bytes().split(b"\n")
        lines[1] = lines[1].replace(b'"export"', b'"search"')
        forged = b"\n".join(lines)
        descriptor = os.open(path, os.O_WRONLY | os.O_TRUNC)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(forged)
        with pytest.raises(LedgerDamaged):
            Ledger.open(folder, clock=clock)
        assert ledger.check() == {"status": "unavailable", "reasonKey": "ledger-damaged",
                                  "category": "chain-break"}
        with pytest.raises(LedgerDamaged):
            ledger.append("service-incident", samples()["service-incident"],
                          expect_revision=0)
        with pytest.raises(LedgerDamaged):
            ledger.records("service-incident")
        assert path.read_bytes() == forged
    finally:
        ledger.close()


def test_a_truncated_ledger_refuses_every_append_from_then_on(tmp_path, clock):
    folder = tmp_path / "ledger"
    folder.mkdir(mode=0o700)
    ledger = Ledger.open(folder, clock=clock)
    try:
        ledger.append("service-incident", samples()["service-incident"], expect_revision=0)
        ledger.append("service-incident", samples()["service-incident"], expect_revision=0)
        path = folder / LedgerStore.LOG
        first = path.read_bytes().split(b"\n")[0] + b"\n"
        descriptor = os.open(path, os.O_WRONLY | os.O_TRUNC)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(first)
        with pytest.raises(LedgerDamaged):
            ledger.append("service-incident", samples()["service-incident"],
                          expect_revision=0)
        assert ledger.damaged is not None
        assert ledger.check()["status"] == "unavailable"
        with pytest.raises(LedgerDamaged):
            ledger.get("service-incident", ident())
    finally:
        ledger.close()


def test_an_unregistered_record_in_the_chain_is_damage_on_open(tmp_path, clock):
    folder = tmp_path / "ledger"
    folder.mkdir(mode=0o700)
    store = LedgerStore.open(folder, clock=clock)
    store.append_entry("not-a-kind", {"anything": 1})
    store.close()
    with pytest.raises(LedgerDamaged) as raised:
        Ledger.open(folder, clock=clock)
    assert raised.value.category == "record-invalid"
