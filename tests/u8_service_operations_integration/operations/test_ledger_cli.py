"""`docsuri-ledger`, the ledger component's fixed command (U8 plan Step 14).

The command runs against a real ledger folder. PlatformControl's receipt reader is a
recorded stand-in for most cases; the receipt-bearing cases run again (`realm`) against
the composed realm's PlatformControl store, with receipts its operator really bound and
the service account's reader confirming them (Step 28).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest

from backend.modules.operations.ledger import Ledger, LedgerStore
from backend.modules.operations.ledger_cli import (
    DECISION_OPERATION,
    UNATTENDED_WORDS,
    WORDS,
    LedgerCommand,
    ReceiptUnavailable,
    UnboundReceiptReader,
    run,
)

ROOT = Path(__file__).resolve().parents[3]
T = "2026-10-22T03:00:00.000Z"
LATER = "2026-11-05T03:00:00.000Z"
# The recorded stand-in's in-person grant (your routine grant).
IN_PERSON = str(uuid4())


class RecordedReceipts:
    """PlatformControl's receipts as `readReceipt` would project them, each bound under
    your in-person grant."""

    def __init__(self):
        self.receipts: dict[str, dict] = {}

    def add(self, operation: str, *, outcome: str = "succeeded", inputs: dict | None = None,
            authority: str = IN_PERSON) -> dict:
        """`inputs` are a decision's own: the receipt binds their hash, as PlatformControl's
        operator does; `authority` is the grant it was bound under."""
        from docsuri_ops.u8_platform.drivers import input_hash

        receipt = {
            "receiptId": str(uuid4()), "operationId": str(uuid4()), "operation": operation,
            "targetId": "docsuri_u8",
            "inputHash": input_hash(inputs) if inputs is not None else hashlib.sha256(
                os.urandom(8)).hexdigest(),
            "outcome": outcome, "authorityRef": authority,
        }
        self.receipts[receipt["operationId"]] = receipt
        return receipt

    def read(self, operation_id: str) -> dict:
        if operation_id not in self.receipts:
            raise ReceiptUnavailable("unknown receipt")
        return self.receipts[operation_id]


@pytest.fixture
def folders(tmp_path):
    ledger, evidence = tmp_path / "ledger", tmp_path / "evidence"
    ledger.mkdir(mode=0o700)
    evidence.mkdir(mode=0o700)
    return ledger, evidence


@pytest.fixture
def receipts(request, tmp_path):
    """The recorded stand-in, or (`realm`) the composed realm's PlatformControl store
    read through the service account's receipt reader (Step 28)."""
    if getattr(request, "param", "recorded") == "recorded":
        return RecordedReceipts()
    from docsuri_ops.u8_platform.u8_protocols import readers_for
    from tests.u8_service_operations_integration import platform_flows as pf

    realm = request.getfixturevalue("realm")
    return pf.RealmReceipts(pf.journey(tmp_path / "platform", realm), readers_for(realm)[0])


SOURCES = pytest.mark.parametrize("receipts", ["recorded", "realm"], indirect=True)


@pytest.fixture
def command(request, folders, receipts, clock):
    """The command, with your in-person grants: the recorded stand-in's, or the realm's
    from its authority record."""
    from backend.modules.operations.ledger_cli import in_person_authorities

    if isinstance(receipts, RecordedReceipts):
        held = frozenset({IN_PERSON})
    else:
        realm = request.getfixturevalue("realm")
        held = in_person_authorities(Path(realm.root) / "platform-authorities.json")
    return LedgerCommand(folder=folders[0], evidence=folders[1], receipts=receipts, clock=clock,
                         environment="live", decision_authorities=held)


def call(command, word: str, payload: bytes = b"", *, environ=None):
    stdout, stderr = io.BytesIO(), io.BytesIO()
    status = run([word], command, environ=environ or {}, stdin=io.BytesIO(payload),
                 stdout=stdout, stderr=stderr)
    return status, stdout.getvalue(), stderr.getvalue()


def result(raw: bytes) -> dict:
    return json.loads(raw.decode().strip().splitlines()[-1])


def backup_set(receipt: dict) -> dict:
    return {
        "backupId": str(uuid4()), "environment": "live", "revision": 1, "trigger": "scheduled",
        "takenAt": T, "checksum": "b" * 64, "sizeBytes": 10, "sourceDatabaseBytes": 20,
        "location": "archives/live.dump", "databaseIncarnation": "cluster:docsuri_u8:1",
        "stagingLocation": "staging/live.dump", "retainUntil": LATER, "integrity": "passed",
        "operatorReceiptRef": receipt["receiptId"],
    }


def decision_inputs(step: str = "production-restore") -> dict:
    """A decision's inputs, as `Decisions.record` hands them to `platform.decision.record`."""
    return {"step": step, "subjectRef": str(uuid4()), "subjectDigest": "e" * 64,
            "decision": "approved"}


def approval(receipt: dict, inputs: dict | None = None) -> dict:
    """The MaintainerApproval of `inputs` (a fresh decision's when none are given)."""
    return {
        "approvalId": str(uuid4()), **(inputs or decision_inputs()), "recordedAt": T,
        "operatorReceiptRef": receipt["receiptId"],
    }


def facts(receipt: dict) -> dict:
    return {name: receipt[name] for name in (
        "receiptId", "operationId", "operation", "targetId", "inputHash", "outcome")
    } | {"confirmedAt": T}


def incident() -> dict:
    return {
        "incidentId": str(uuid4()), "environment": "live", "revision": 1,
        "capabilities": ["export"], "correlationIds": [], "state": "open", "openedAt": T,
        "openedBy": "operator", "recoveryRequestIds": [], "evidenceRefs": [],
    }


def append_payload(kind: str, record: dict, *, revision: int = 0, receipts=()) -> bytes:
    return json.dumps({"kind": kind, "record": record, "expectRevision": revision,
                       "receipts": list(receipts)}).encode()


# --- 1. The fixed shape ------------------------------------------------------------------


def test_a_word_outside_the_set_and_a_caller_environment_are_refused(command, folders):
    for word in ("delete", "append extra", "", "APPEND"):
        status, out, _ = call(command, word)
        assert status == 2 and result(out) == {"ok": False, "reason": "word-refused"}
    for environ in ({"PYTHONPATH": "/tmp"}, {"DYLD_INSERT_LIBRARIES": "/tmp/x.dylib"},
                    {"LD_PRELOAD": "/tmp/x.so"}, {"PYTHONSTARTUP": "/tmp/x.py"}):
        status, out, _ = call(command, "verify", environ=environ)
        assert status == 2 and result(out) == {"ok": False, "reason": "environment-refused"}
    stdout = io.BytesIO()
    assert run(["append", "verify"], command, environ={}, stdin=io.BytesIO(b"{}"),
               stdout=stdout, stderr=io.BytesIO()) == 2
    assert list(folders[0].iterdir()) == []  # nothing was opened
    assert set(UNATTENDED_WORDS) == set(WORDS) - {"repair"}


def test_the_installed_entry_checks_its_environment_and_word_in_its_own_process():
    environment = {"PATH": os.environ["PATH"], "PYTHONPATH": "/tmp/elsewhere"}
    entry = [sys.executable, "-c", "from backend.modules.operations.ledger_cli import "
             "main_fixed; raise SystemExit(main_fixed())"]
    refused = subprocess.run([*entry, "verify"], cwd=ROOT, env=environment,
                             capture_output=True, timeout=60)
    assert refused.returncode == 2
    assert json.loads(refused.stdout) == {"ok": False, "reason": "environment-refused"}
    clean = {"PATH": os.environ["PATH"]}
    word = subprocess.run([*entry, "erase"], cwd=ROOT, env=clean, capture_output=True,
                          timeout=60)
    assert word.returncode == 2
    assert json.loads(word.stdout) == {"ok": False, "reason": "word-refused"}
    program = (ROOT / "ops/bin/docsuri-ledger").read_text().splitlines()
    assert program[0] == "#!/Library/DocSuri/release/.venv/bin/python -I"


def test_input_beyond_its_bound_or_outside_its_fields_is_refused(command):
    from backend.modules.operations import ledger_cli

    status, out, _ = call(command, "read", b"{" + b" " * (70 * 1024) + b"}")
    assert status == 2 and result(out)["reason"] == "input-too-large"
    # `append` takes one step's appends as one batch, under a bound of its own.
    status, out, _ = call(command, "append",
                          b"{" + b" " * (ledger_cli.MAX_APPEND_INPUT + 1) + b"}")
    assert status == 2 and result(out)["reason"] == "input-too-large"
    status, out, _ = call(command, "append", json.dumps({"appends": []}).encode())
    assert result(out)["reason"] == "input-field-refused"
    status, out, _ = call(command, "append", json.dumps(
        {"appends": [{}], "kind": "service-incident"}).encode())
    assert result(out)["reason"] == "input-field-refused"
    status, out, _ = call(command, "append", b"not json")
    assert result(out)["reason"] == "input-not-json"
    status, out, _ = call(command, "append", json.dumps({"kind": "service-incident",
                                                         "extra": 1}).encode())
    assert result(out)["reason"] == "input-field-refused"
    for kind in ("ledger.adopted", "receipt-facts", "unknown-kind"):
        status, out, _ = call(command, "append", append_payload(kind, {}))
        assert status != 0 and result(out)["ok"] is False


# --- 2. Receipt-bearing records --------------------------------------------------------


@SOURCES
def test_append_refuses_a_receipt_that_does_not_verify(command, receipts):
    receipt = receipts.add("platform.database.backup")
    record = backup_set(receipt)
    status, out, _ = call(command, "append", append_payload("backup-set", record))
    assert result(out) == {"ok": False, "reason": "receipt-unconfirmed"}
    forged = {**facts(receipt), "inputHash": "0" * 64}
    status, out, _ = call(command, "append",
                          append_payload("backup-set", record, receipts=[forged]))
    assert status == 1 and result(out) == {"ok": False, "reason": "receipt-unconfirmed"}
    unknown = {**facts(receipt), "operationId": str(uuid4())}
    status, out, _ = call(command, "append",
                          append_payload("backup-set", record, receipts=[unknown]))
    assert result(out)["reason"] == "receipt-unconfirmed"
    status, out, _ = call(command, "append",
                          append_payload("backup-set", record, receipts=[facts(receipt)]))
    assert status == 0 and result(out)["ok"] is True and result(out)["revision"] == 1
    # A later version citing the same receipt needs no facts again.
    status, out, _ = call(command, "append", append_payload(
        "backup-set", {**record, "disposedAt": LATER}, revision=1))
    assert status == 0 and result(out)["revision"] == 2


@SOURCES
def test_an_unbound_reader_confirms_nothing(folders, clock, receipts):
    command = LedgerCommand(folder=folders[0], evidence=folders[1],
                            receipts=UnboundReceiptReader(), clock=clock)
    receipt = receipts.add("platform.database.backup")
    status, out, _ = call(command, "append", append_payload(
        "backup-set", backup_set(receipt), receipts=[facts(receipt)]))
    assert result(out) == {"ok": False, "reason": "receipt-unconfirmed"}


@SOURCES
def test_a_maintainer_approval_needs_a_succeeded_decision_receipt(command, receipts):
    other = receipts.add("platform.database.backup")
    status, out, _ = call(command, "append", append_payload(
        "maintainer-approval", approval(other), receipts=[facts(other)]))
    assert result(out) == {"ok": False, "reason": "decision-receipt-required"}
    inputs = decision_inputs()
    failed = receipts.add(DECISION_OPERATION, outcome="failed", inputs=inputs)
    status, out, _ = call(command, "append", append_payload(
        "maintainer-approval", approval(failed, inputs), receipts=[facts(failed)]))
    assert result(out) == {"ok": False, "reason": "decision-receipt-required"}
    decision = receipts.add(DECISION_OPERATION, inputs=inputs)
    status, out, _ = call(command, "append", append_payload(
        "maintainer-approval", approval(decision, inputs), receipts=[facts(decision)]))
    assert status == 0 and result(out)["ok"] is True


# --- 2b. A decision receipt is its own approval's, once (review finding, Major, R17) ------


def admitted(command, receipts, inputs: dict) -> tuple[dict, dict]:
    """One approval admitted on a fresh decision receipt of `inputs`."""
    decision = receipts.add(DECISION_OPERATION, inputs=inputs)
    record = approval(decision, inputs)
    status, out, _ = call(command, "append", append_payload(
        "maintainer-approval", record, receipts=[facts(decision)]))
    assert status == 0 and result(out)["ok"] is True, result(out)
    return decision, record


def approvals(folders, clock) -> list[dict]:
    ledger = Ledger.open(folders[0], clock=clock)
    try:
        return ledger.records("maintainer-approval")
    finally:
        ledger.close()


@SOURCES
def test_an_approval_whose_step_or_subject_differs_from_its_receipt_is_refused(
        command, receipts, folders, clock):
    """The receipt binds the hash of {step, subjectRef, subjectDigest, decision}: an
    approval naming another step, subject, digest or decision than the one decided is
    refused, and nothing is appended."""
    inputs = decision_inputs()
    decision = receipts.add(DECISION_OPERATION, inputs=inputs)
    for change in ({"step": "abort-review"}, {"subjectRef": str(uuid4())},
                   {"subjectDigest": "f" * 64}, {"decision": "declined"}):
        status, out, _ = call(command, "append", append_payload(
            "maintainer-approval", approval(decision, {**inputs, **change}),
            receipts=[facts(decision)]))
        assert status == 1 and result(out) == {"ok": False,
                                               "reason": "decision-receipt-mismatch"}, change
    assert approvals(folders, clock) == []
    status, out, _ = call(command, "append", append_payload(
        "maintainer-approval", approval(decision, inputs), receipts=[facts(decision)]))
    assert status == 0 and result(out)["ok"] is True


@SOURCES
def test_a_decision_receipt_another_approval_cites_is_refused(command, receipts, folders,
                                                              clock):
    """A receipt of yours that an approval already cites is never cited again: not by a
    second approval of the same decision, nor by the unattended scheduler's append (the
    same command, holding `docsuri-ledger append` without a password) citing it for the
    same step and subject, with or without the facts again."""
    inputs = decision_inputs("abort-review")
    decision, first = admitted(command, receipts, inputs)
    for given in ([facts(decision)], []):
        status, out, _ = call(command, "append", append_payload(
            "maintainer-approval", approval(decision, inputs), receipts=given))
        assert status == 1 and result(out) == {"ok": False,
                                               "reason": "decision-receipt-reused"}
    assert [item["approvalId"] for item in approvals(folders, clock)] == [first["approvalId"]]
    # Nor twice within one batch.
    again = decision_inputs()
    second = receipts.add(DECISION_OPERATION, inputs=again)
    status, out, _ = call(command, "append", json.dumps({"appends": [
        {"kind": "maintainer-approval", "record": approval(second, again), "expectRevision": 0,
         "receipts": [facts(second)]},
        {"kind": "maintainer-approval", "record": approval(second, again), "expectRevision": 0,
         "receipts": []}]}).encode())
    assert result(out) == {"ok": False, "reason": "decision-receipt-reused"}
    assert len(approvals(folders, clock)) == 1


def test_a_decision_receipt_already_in_the_ledger_is_checked_in_person_again(folders, clock):
    """A decision receipt the ledger already holds (cited first by another kind of record,
    written past the command) is read again from PlatformControl when an approval cites
    it: one bound under the scheduler's grant is refused, and one PlatformControl no
    longer confirms is refused; one bound under yours is admitted."""
    receipts = RecordedReceipts()
    command = LedgerCommand(folder=folders[0], evidence=folders[1], receipts=receipts,
                            clock=clock, environment="live",
                            decision_authorities=frozenset({IN_PERSON}))
    scheduler = str(uuid4())

    def stored(authority: str) -> tuple[dict, dict]:
        inputs = decision_inputs()
        decision = receipts.add(DECISION_OPERATION, inputs=inputs, authority=authority)
        ledger = Ledger.open(folders[0], clock=clock)
        try:
            ledger.append("backup-set", backup_set(decision), expect_revision=0,
                          receipts=(facts(decision),))
        finally:
            ledger.close()
        return decision, inputs

    theirs, inputs = stored(scheduler)
    status, out, _ = call(command, "append", append_payload(
        "maintainer-approval", approval(theirs, inputs)))
    assert result(out) == {"ok": False, "reason": "decision-receipt-not-in-person"}
    forgotten, forgotten_inputs = stored(IN_PERSON)
    del receipts.receipts[forgotten["operationId"]]
    status, out, _ = call(command, "append", append_payload(
        "maintainer-approval", approval(forgotten, forgotten_inputs)))
    assert result(out) == {"ok": False, "reason": "receipt-unconfirmed"}
    yours, own_inputs = stored(IN_PERSON)
    status, out, _ = call(command, "append", append_payload(
        "maintainer-approval", approval(yours, own_inputs)))
    assert status == 0 and result(out)["ok"] is True
    assert len(approvals(folders, clock)) == 1


def test_the_commands_decision_hash_is_the_operators_input_hash():
    """The command's `decision_input_hash` is PlatformControl's operator's `input_hash` of
    the inputs `Decisions.record` binds."""
    from backend.modules.operations.ledger_cli import decision_input_hash
    from docsuri_ops.u8_platform.drivers import input_hash

    inputs = {**decision_inputs(), "subjectRef": "cutover:ü-1"}
    assert decision_input_hash({**inputs, "approvalId": "x", "recordedAt": T}) == (
        input_hash(inputs))


def test_a_stale_revision_and_a_refused_record_append_nothing(command, folders):
    record = incident()
    assert call(command, "append", append_payload("service-incident", record))[0] == 0
    size = (folders[0] / LedgerStore.LOG).stat().st_size
    status, out, _ = call(command, "append", append_payload("service-incident", record))
    assert status == 1 and result(out) == {"ok": False, "reason": "stale-revision",
                                           "current": {"revision": 1}}
    status, out, _ = call(command, "append", append_payload(
        "service-incident", {**record, "diagnosisKey": "Free text here"}, revision=1))
    assert result(out) == {"ok": False, "reason": "record-refused", "category": "field-form"}
    assert (folders[0] / LedgerStore.LOG).stat().st_size == size


def test_read_answers_a_bounded_query(command):
    records = [incident() for _ in range(3)]
    for record in records:
        call(command, "append", append_payload("service-incident", record))
    status, out, _ = call(command, "read", json.dumps({
        "kind": "service-incident", "key": [records[0]["incidentId"]]}).encode())
    assert status == 0 and result(out) == {"ok": True, "records": [records[0]], "revision": 1}
    status, out, _ = call(command, "read", json.dumps({"kind": "service-incident",
                                                       "limit": 2}).encode())
    answer = result(out)
    assert answer["total"] == 3 and len(answer["records"]) == 2
    status, out, _ = call(command, "read", json.dumps({"kind": "service-incident",
                                                       "limit": 101}).encode())
    assert status == 2 and result(out)["reason"] == "input-field-refused"


# --- 3. copy ---------------------------------------------------------------------------


def test_copys_digest_equals_the_files_up_to_the_head(command, folders):
    for _ in range(4):
        call(command, "append", append_payload("service-incident", incident()))
    status, stream, report = call(command, "copy")
    assert status == 0
    answer = result(report)
    raw = (folders[0] / LedgerStore.LOG).read_bytes()
    assert stream == raw and answer["sha256"] == hashlib.sha256(raw).hexdigest()
    assert answer["count"] == 4 and answer["bytes"] == len(raw)
    status, out, _ = call(command, "verify", b"{}")
    assert status == 0 and result(out)["count"] == 4


# --- 4. repair -------------------------------------------------------------------------


def test_repair_from_a_verified_copy_restores_the_chain_and_keeps_the_damage_aside(
    command, folders, clock,
):
    ledger_folder, evidence = folders
    for _ in range(3):
        call(command, "append", append_payload("service-incident", incident()))
    _, copy, _ = call(command, "copy")
    status, out, _ = call(command, "repair", copy)
    assert status == 1 and result(out)["reason"] == "ledger-not-damaged"
    call(command, "append", append_payload("service-incident", incident()))
    log = ledger_folder / LedgerStore.LOG
    damaged = log.read_bytes().replace(b'"operator"', b'"Operator"', 1)
    descriptor = os.open(log, os.O_WRONLY | os.O_TRUNC)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(damaged)
    status, out, _ = call(command, "verify", b"{}")
    assert status == 1 and result(out)["reason"] == "ledger-damaged"
    status, out, _ = call(command, "repair", b"not a ledger copy\n")
    assert result(out)["reason"] == "copy-refused"
    status, out, _ = call(command, "repair", copy)
    answer = result(out)
    # The copy's 3 entries, the repair's record and the damage's own incident.
    assert status == 0 and answer["ok"] is True and answer["count"] == 5
    aside = evidence / answer["aside"].removeprefix("evidence/")
    assert (aside / LedgerStore.LOG).read_bytes() == damaged
    assert (aside / LedgerStore.HEAD).exists()
    reopened = Ledger.open(ledger_folder, clock=clock)
    try:
        assert reopened.check()["status"] == "available"
        assert len(reopened.records("service-incident")) == 4
        assert reopened.get("service-incident", answer["incidentId"])["openedBy"] == (
            "ledger-damaged")
        assert reopened.events("ledger.repaired")[0]["copySha256"] == hashlib.sha256(
            copy).hexdigest()
    finally:
        reopened.close()


# --- 5. Without a v2 process ------------------------------------------------------------


def test_append_works_while_no_v2_process_runs(folders, tmp_path):
    with socket.socket() as probe:
        assert probe.connect_ex(("127.0.0.1", 18109)) != 0  # the realm's host is stopped
    script = tmp_path / "append.py"
    descriptor = os.open(script, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write(
            "import io, sys\n"
            "from pathlib import Path\n"
            "from backend.modules.operations.ledger_cli import LedgerCommand, "
            "UnboundReceiptReader, run\n"
            "command = LedgerCommand(folder=Path(sys.argv[1]), evidence=Path(sys.argv[2]), "
            "receipts=UnboundReceiptReader())\n"
            "raise SystemExit(run(['append'], command, environ={}, stdin=sys.stdin.buffer, "
            "stdout=sys.stdout.buffer, stderr=sys.stderr.buffer))\n"
        )
    record = incident()
    # The interpreter finds the source tree as the release's .pth would give it; the
    # command itself is handed an untouched environment, as sudo's env_reset gives it.
    done = subprocess.run(
        [sys.executable, str(script), str(folders[0]), str(folders[1])], cwd=ROOT,
        env={"PATH": os.environ["PATH"], "PYTHONPATH": f"{ROOT}:{ROOT / 'ops/src'}"},
        input=append_payload("service-incident", record), capture_output=True, timeout=60,
    )
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout)["seq"] == 1
    ledger = Ledger.open(folders[0], clock=lambda: dt.datetime.now(dt.UTC))
    try:
        assert ledger.get("service-incident", record["incidentId"]) == record
    finally:
        ledger.close()
