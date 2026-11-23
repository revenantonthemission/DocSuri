"""Production's wiring (U8 plan Steps 37–38; BR6.10, BR9.17, D4, D5).

The ledger client is driven against the real ledger component (`ledger_cli`) run in this
process behind a stand-in for `sudo -k|-n -u _docsuri_v2 docsuri-ledger <word>`, on a
ledger in the test's folder. The operators, the standing job's parts, the recovery
procedures and the cutover's platform are built from installer-shaped files under a
temporary prefix; nothing reaches this Mac's arrangement, sudo or the network.
"""

from __future__ import annotations

import datetime as dt
import io
import json
import os
import secrets
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.modules.operations.errors import OperationsError
from backend.modules.operations.ledger_cli import LedgerCommand
from docsuri_ops import production_wiring as wiring
from docsuri_ops.arrangement.paths import ArrangementPaths
from docsuri_ops.platform_control import enums
from docsuri_ops.release import Refused
from docsuri_ops.u8_platform.drivers import input_hash
from tests.u8_service_operations_integration import recovery_flows as rf

NOW = dt.datetime(2026, 10, 23, 2, 0, tzinfo=dt.UTC)


class Receipts:
    """PlatformControl's receipt reader for the ledger component: it confirms the facts
    it was told about."""

    def __init__(self):
        self.known = {}

    def read(self, operation_id):
        return self.known[operation_id]


class FakeSudo:
    """`sudo -u _docsuri_v2 docsuri-ledger <word>`, run here: the real component on a
    ledger folder; `before_append` runs just before an append reaches it."""

    def __init__(self, folder: Path, evidence: Path):
        self.receipts = Receipts()
        self.command = LedgerCommand(folder, evidence, self.receipts, clock=lambda: NOW)
        self.argvs: list[list[str]] = []
        self.before_append = None

    def __call__(self, argv, *, input, capture_output, timeout, check):
        self.argvs.append(argv)
        word = argv[-1]
        if word == "append" and self.before_append is not None:
            hook, self.before_append = self.before_append, None
            hook()
        stdout, stderr = io.BytesIO(), io.BytesIO()
        code = self.command.run(word, io.BytesIO(input), stdout, stderr)
        return SimpleNamespace(returncode=code, stdout=stdout.getvalue(),
                               stderr=stderr.getvalue())


@pytest.fixture
def ledger_folder(tmp_path):
    ledger = rf.open_ledger(tmp_path, lambda: NOW)
    folder = Path(ledger.store.folder) if hasattr(ledger.store, "folder") else tmp_path / "ledger"
    ledger.close()
    return folder


def client(tmp_path, ledger_folder, via="in-person"):
    sudo = FakeSudo(ledger_folder, tmp_path / "evidence")
    paths = ArrangementPaths.under(tmp_path / "Library" / "DocSuri")
    return wiring.LedgerClient(via=via, clock=lambda: NOW, run=sudo, paths=paths), sudo


def stub_ledger():
    """A ledger that holds nothing, for parts that only need to be put together."""
    return SimpleNamespace(records=lambda kind: [], get=lambda kind, key: None,
                           revision=lambda kind, key: 0, close=lambda: None,
                           clock=lambda: NOW)


def incident(revision: int = 1, **fields) -> dict:
    return {"incidentId": fields.pop("incidentId", str(uuid4())), "environment": "live",
            "revision": revision, "capabilities": ["storage.capacity"], "correlationIds": [],
            "state": "open", "openedAt": "2026-10-23T02:00:00.000Z", "openedBy": "operator",
            "recoveryRequestIds": [], "evidenceRefs": [], **fields}


# --- the ledger through its fixed command --------------------------------------------------------


def test_the_client_reads_a_copy_and_writes_through_the_component(tmp_path, ledger_folder):
    ledger, sudo = client(tmp_path, ledger_folder)
    record = incident()
    assert ledger.records("service-incident") == []
    ledger.append("service-incident", record, expect_revision=0)
    assert ledger.get("service-incident", record["incidentId"]) == record
    assert ledger.revision("service-incident", record["incidentId"]) == 1
    with pytest.raises(OperationsError) as stale:
        ledger.append("service-incident", {**record, "revision": 2, "state": "investigating",
                                           "diagnosisKey": "disk"}, expect_revision=0)
    assert stale.value.code == "STALE_REVISION"
    with pytest.raises(OperationsError) as refused:
        ledger.append("service-incident", {"unknown": 1}, expect_revision=0)
    assert refused.value.code == "CONFLICT"
    words = [argv[-1] for argv in sudo.argvs]
    assert set(words) <= {"copy", "append"} and "append" in words
    assert sudo.argvs[0][:4] == ["/usr/bin/sudo", "-k", "-u", "_docsuri_v2"]
    assert sudo.argvs[0][4].endswith("/release/ops/bin/docsuri-ledger")
    copy = io.BytesIO()
    assert ledger.copy(copy)["ok"] is True and copy.getvalue()
    ledger.close()


def test_the_standing_authority_reaches_it_without_a_password(tmp_path, ledger_folder):
    ledger, sudo = client(tmp_path, ledger_folder, via="standing")
    ledger.records("service-incident")
    assert sudo.argvs[0][1] == "-n"
    with pytest.raises(ValueError):
        wiring.LedgerClient(via="ssh")


def test_an_atomic_step_retries_on_a_fresh_copy_when_it_lost_the_race(tmp_path, ledger_folder):
    ledger, sudo = client(tmp_path, ledger_folder)
    first = incident()
    ledger.append("service-incident", first, expect_revision=0)

    def racing() -> None:  # another writer appends a version between the copy and the send
        other = wiring.LedgerClient(via="in-person", clock=lambda: NOW, run=sudo,
                                    paths=ledger.paths)
        other.append("service-incident", {**first, "revision": 2, "correlationIds": ["x"]},
                     expect_revision=1)
        other.close()

    sudo.before_append = racing
    attempts = []

    def step(view):
        attempts.append(1)
        revision = view.revision("service-incident", first["incidentId"])
        current = view.get("service-incident", first["incidentId"])
        view.append("service-incident", {**current, "revision": revision + 1,
                                         "evidenceRefs": ["checked"]}, expect_revision=revision)
        return revision

    assert ledger.atomic(step) == 2 and len(attempts) == 2
    final = ledger.get("service-incident", first["incidentId"])
    assert final["correlationIds"] == ["x"] and final["evidenceRefs"] == ["checked"]


def moved(record: dict, view, **fields) -> None:
    """The record's next version, from the revision the step's view reads."""
    revision = view.revision("service-incident", record["incidentId"])
    current = view.get("service-incident", record["incidentId"])
    view.append("service-incident", {**current, "revision": revision + 1, **fields},
                expect_revision=revision)


def test_a_steps_appends_reach_the_ledger_as_one_batch(tmp_path, ledger_folder):
    """Review finding (Major, R14): a step's appends are one `docsuri-ledger append`, one
    transaction under one lock, so no process reads the step half applied."""
    ledger, sudo = client(tmp_path, ledger_folder)
    a, b = incident(), incident()
    ledger.append("service-incident", a, expect_revision=0)
    ledger.append("service-incident", b, expect_revision=0)
    before = [argv[-1] for argv in sudo.argvs].count("append")
    ledger.atomic(lambda view: (moved(a, view, evidenceRefs=["1"]),
                                moved(b, view, evidenceRefs=["2"])))
    assert [argv[-1] for argv in sudo.argvs].count("append") == before + 1
    assert ledger.revision("service-incident", a["incidentId"]) == 2
    assert ledger.get("service-incident", b["incidentId"])["evidenceRefs"] == ["2"]


def test_an_interleaved_append_refuses_the_whole_batch_and_the_step_reruns_cleanly(
        tmp_path, ledger_folder):
    """Review finding (Major, R14): someone else moves `b` between the step's copy and its
    batch. The batch is refused `stale-head` and none of it is written, `a`'s version
    included (before, `a` was kept and `b` refused, the step torn); the step runs again
    on a fresh copy and both versions land once, on top of the other writer's."""
    ledger, sudo = client(tmp_path, ledger_folder)
    a, b = incident(), incident()
    ledger.append("service-incident", a, expect_revision=0)
    ledger.append("service-incident", b, expect_revision=0)
    original, batches = sudo.command.append, []

    def append(document):
        if "appends" in document:
            batches.append(document)
            if len(batches) == 1:  # someone else moves `b` before the batch's turn
                original({"kind": "service-incident", "record": {**b, "revision": 2,
                                                                 "evidenceRefs": ["z"]},
                          "expectRevision": 1, "receipts": []})
        return original(document)

    sudo.command.append = append
    attempts = []

    def step(view):
        attempts.append(view.revision("service-incident", a["incidentId"]))
        moved(a, view, evidenceRefs=["1"])
        moved(b, view, correlationIds=["2"])

    ledger.atomic(step)
    assert len(batches) == 2 and attempts == [1, 1]  # `a` never moved by the refused batch
    assert ledger.revision("service-incident", a["incidentId"]) == 2
    final = ledger.get("service-incident", b["incidentId"])
    assert ledger.revision("service-incident", b["incidentId"]) == 3
    assert final["evidenceRefs"] == ["z"] and final["correlationIds"] == ["2"]


def test_a_batch_one_of_whose_appends_is_refused_writes_none_of_them(tmp_path,
                                                                     ledger_folder):
    """The component checks every append of a batch before writing any: the second one's
    stale revision refuses the batch, and the first is not written either."""
    ledger, sudo = client(tmp_path, ledger_folder)
    a, b = incident(), incident()
    first = ledger.append("service-incident", a, expect_revision=0)
    ledger.append("service-incident", b, expect_revision=0)
    head = ledger.refresh().head
    stdout = io.BytesIO()
    code = sudo.command.run("append", io.BytesIO(json.dumps({
        "expectHead": {"count": head.count, "head": head.head}, "appends": [
            {"kind": "service-incident", "record": {**a, "revision": 2, "evidenceRefs": ["1"]},
             "expectRevision": 1, "receipts": []},
            {"kind": "service-incident", "record": {**b, "revision": 2, "evidenceRefs": ["2"]},
             "expectRevision": 0, "receipts": []}]}).encode()), stdout, io.BytesIO())
    assert code == 1 and json.loads(stdout.getvalue())["reason"] == "stale-revision"
    ledger.refresh()
    assert ledger.revision("service-incident", a["incidentId"]) == 1
    assert ledger.refresh().head.count == head.count and first["ok"] is True
    # A record its schema refuses later in the batch refuses it as well.
    code = sudo.command.run("append", io.BytesIO(json.dumps({"appends": [
        {"kind": "service-incident", "record": {**a, "revision": 2, "evidenceRefs": ["1"]},
         "expectRevision": 1, "receipts": []},
        {"kind": "service-incident", "record": {"unknown": 1}, "expectRevision": 0,
         "receipts": []}]}).encode()), stdout, io.BytesIO())
    assert code == 1 and ledger.refresh().head.count == head.count
    # The same batch with the right revisions lands whole, in order.
    code = sudo.command.run("append", io.BytesIO(json.dumps({
        "expectHead": {"count": head.count, "head": head.head}, "appends": [
            {"kind": "service-incident", "record": {**a, "revision": 2, "evidenceRefs": ["1"]},
             "expectRevision": 1, "receipts": []},
            {"kind": "service-incident", "record": {**a, "revision": 3, "evidenceRefs": ["2"]},
             "expectRevision": 2, "receipts": []}]}).encode()), stdout, io.BytesIO())
    answer = json.loads(stdout.getvalue().splitlines()[-1])
    assert code == 0 and answer["count"] == 2
    assert (answer["first"]["revision"], answer["last"]["revision"]) == (2, 3)
    assert ledger.refresh().get("service-incident", a["incidentId"])["evidenceRefs"] == ["2"]


def test_a_batch_at_its_bound_lands_and_answers_within_what_the_client_reads(tmp_path,
                                                                             ledger_folder):
    """Review finding (Major, R15): a step of `MAX_BATCH` appends reaches the real
    component through the client and lands, and the answer stays one short line, well
    inside the 64 KiB the client reads (before, one item per append put its start out of
    reach past about 2,400 appends: written, then answered as no result). One more than
    the bound is refused by the client before anything is sent."""
    from backend.modules.operations.ledger_cli import MAX_BATCH

    ledger, sudo = client(tmp_path, ledger_folder)
    records = [incident() for _ in range(MAX_BATCH)]
    answers = []
    original = sudo.command.append

    def append(document):
        answer = original(document)
        answers.append(answer)
        return answer

    sudo.command.append = append

    def step(view):
        for record in records:
            view.append("service-incident", record, expect_revision=0)

    ledger.atomic(step)
    (answer,) = answers
    assert answer["ok"] is True and answer["count"] == MAX_BATCH
    assert len(json.dumps(answer)) < 1024 < wiring.MAX_RESULT
    assert len(ledger.records("service-incident")) == MAX_BATCH
    before = ledger.refresh().head.count

    def too_many(view):
        for _ in range(MAX_BATCH + 1):
            view.append("service-incident", incident(), expect_revision=0)

    with pytest.raises(OperationsError) as refused:
        ledger.atomic(too_many)
    assert refused.value.current == {"reasonKey": "ledger-batch-too-large"}
    assert len(answers) == 1 and ledger.refresh().head.count == before
    ledger.close()


def test_a_run_with_more_misfits_than_one_batch_holds_records_them_all(tmp_path,
                                                                       ledger_folder):
    """Review finding (Major, R15): a dry run over v1's corpus can name more misfits than
    one batch holds (one per paper, say). They are written in chunks, each one ledger
    step through the client and the real component; a call stopped between chunks
    completes on its rerun, and a rerun of a complete call writes nothing."""
    from backend.modules.operations.ledger_cli import MAX_BATCH
    from backend.modules.operations.migration_records import MISFIT, MISFIT_CHUNK, MigrationRuns

    ledger, sudo = client(tmp_path, ledger_folder)
    total = MAX_BATCH + 500
    misfits = [("paper", f"v1-paper:{index}", "embedding-provenance-unproven")
               for index in range(total)]
    run = uuid4()
    original, sizes = sudo.command.append, []

    def append(document):
        if "appends" in document:
            sizes.append(len(document["appends"]))
            if len(sizes) == 3:
                raise RuntimeError("stopped between chunks")
        return original(document)

    sudo.command.append = append
    runs = MigrationRuns(ledger, clock=lambda: NOW)
    with pytest.raises(RuntimeError):
        runs.record_misfits(run, misfits)
    assert len(ledger.records(MISFIT)) == 2 * MISFIT_CHUNK  # the first two chunks landed
    sudo.command.append = original
    added = runs.record_misfits(run, misfits)
    assert added == total - 2 * MISFIT_CHUNK
    assert len(ledger.records(MISFIT)) == total
    assert max(sizes) <= MISFIT_CHUNK < MAX_BATCH
    sent = len([argv for argv in sudo.argvs if argv[-1] == "append"])
    assert runs.record_misfits(run, misfits) == 0
    assert len([argv for argv in sudo.argvs if argv[-1] == "append"]) == sent
    ledger.close()


def interleaving(sudo, *, times: int) -> list[dict]:
    """Another writer's unrelated append (an incident) just before each of the first
    `times` batches reaches the component; the batches seen are returned."""
    original, batches = sudo.command.append, []

    def append(document):
        if "appends" in document:
            batches.append(document)
            if len(batches) <= times:
                original({"kind": "service-incident", "record": incident(),
                          "expectRevision": 0, "receipts": []})
        return original(document)

    sudo.command.append = append
    return batches


def held_and_successor(ledger_folder) -> tuple[str, str]:
    """A production restore `held`, and its successor admitted (`awaiting-operator`),
    recorded through the machine on the ledger directly."""
    from backend.modules.operations.ledger import Ledger
    from backend.modules.operations.recovery import RecoveryRequests
    from backend.u8_policy import SYNTHETIC_OPERATIONS
    from tests.u8_service_operations_integration.component.test_recovery_requests import (
        production,
    )

    direct = Ledger.open(ledger_folder, clock=lambda: NOW)
    try:
        requests = RecoveryRequests(direct, SYNTHETIC_OPERATIONS, clock=lambda: NOW,
                                    mfa_current=lambda account, at: True)
        backup = rf.set_record(direct, now=NOW)
        held, approval = production(requests, direct, lambda: NOW, backup)
        identity = held["recoveryRequestId"]
        requests.admit(identity, approval_id=approval["approvalId"])
        requests.start(identity)
        requests.advance(identity, "held", allowed_from=("running",))
        successor, decision = production(requests, direct, lambda: NOW, backup)
        requests.admit(successor["recoveryRequestId"], approval_id=decision["approvalId"],
                       predecessor_id=identity)
    finally:
        direct.close()
    return identity, successor["recoveryRequestId"]


def operator_requests(ledger):
    from backend.modules.operations.recovery import RecoveryRequests
    from backend.u8_policy import SYNTHETIC_OPERATIONS

    return RecoveryRequests(ledger, SYNTHETIC_OPERATIONS, clock=lambda: NOW,
                            mfa_current=lambda account, at: True)


def test_a_successors_start_with_an_interleaved_append_takes_over_its_predecessor_whole(
        tmp_path, ledger_folder):
    """Review finding (Major, R14): `start` of a successor appends `predecessor failed`
    and `successor running` in one step. Another writer's append lands between the copy
    and the batch: the whole batch is refused, so the held predecessor is never failed
    alone (which left every retry `predecessor-not-held`); the step runs again and both
    land together."""
    held, successor = held_and_successor(ledger_folder)
    ledger, sudo = client(tmp_path, ledger_folder)
    batches = interleaving(sudo, times=1)
    started = operator_requests(ledger).start(successor)
    assert started["state"] == "running" and len(batches) == 2
    ended = ledger.get("recovery-request", held)
    assert ended["state"] == "failed" and ended["successorRequestId"] == successor


def test_a_successors_start_that_cannot_land_leaves_its_predecessor_held(tmp_path,
                                                                        ledger_folder):
    """Every attempt's batch meets an interleaved append: the start is refused
    (`ledger-contended`) with nothing of it written, the predecessor still `held` and the
    successor still waiting, so the start can be run again."""
    held, successor = held_and_successor(ledger_folder)
    ledger, sudo = client(tmp_path, ledger_folder)
    batches = interleaving(sudo, times=wiring.ATTEMPTS)
    with pytest.raises(OperationsError) as refused:
        operator_requests(ledger).start(successor)
    assert refused.value.current == {"reasonKey": "ledger-contended"}
    assert len(batches) == wiring.ATTEMPTS
    assert ledger.get("recovery-request", held)["state"] == "held"
    assert ledger.get("recovery-request", successor)["state"] == "awaiting-operator"
    # The other writer has stopped (it interleaved only the first batches): run again.
    assert operator_requests(ledger).start(successor)["state"] == "running"
    assert ledger.get("recovery-request", held)["state"] == "failed"


def final_ready(ledger_folder) -> None:
    """Two misfit decisions, an accepted dry run under them and a switching cutover, on
    the ledger directly: a final run may start, freezing both decisions in its step."""
    from backend.modules.operations.ledger import Ledger
    from backend.modules.operations.migration_records import MigrationRuns, MisfitDecisions
    from tests.u8_service_operations_integration.component import test_misfit_decisions as md

    direct = Ledger.open(ledger_folder, clock=lambda: NOW)
    try:
        runs = MigrationRuns(direct, clock=lambda: NOW)
        decisions = MisfitDecisions(direct, clock=lambda: NOW)
        md.decide(direct, decisions, lambda: NOW, "account", "no-email")
        md.decide(direct, decisions, lambda: NOW, "account", "closed-in-v1")
        md.accept(runs, direct, lambda: NOW, md.reported(runs, direct, lambda: NOW))
        md.switching(direct)
    finally:
        direct.close()


def test_a_final_runs_freeze_and_start_land_together_or_not_at_all(tmp_path,
                                                                   ledger_folder):
    """Review finding (Major, R14): the final run's start freezes every misfit decision
    and records the run in one step. Interleaved on every attempt, it is refused with no
    decision frozen and no run recorded; interleaved once, it runs again and lands
    whole."""
    from backend.modules.operations.migration_records import MigrationRuns

    final_ready(ledger_folder)
    ledger, sudo = client(tmp_path, ledger_folder)
    original = sudo.command.append
    batches = interleaving(sudo, times=wiring.ATTEMPTS)
    with pytest.raises(OperationsError) as refused:
        MigrationRuns(ledger, clock=lambda: NOW).start("final", tool_commit="1" * 40)
    assert refused.value.current == {"reasonKey": "ledger-contended"}, refused.value.current
    assert len(batches) == wiring.ATTEMPTS and len(batches[0]["appends"]) == 3
    assert not any(item["frozen"] for item in ledger.records("misfit-decision"))
    assert [run["kind"] for run in ledger.records("migration-run")] == ["dry"]
    sudo.command.append = original
    batches = interleaving(sudo, times=1)
    final = MigrationRuns(ledger, clock=lambda: NOW).start("final", tool_commit="1" * 40)
    assert final["state"] == "preparing" and len(batches) == 2
    decisions = ledger.records("misfit-decision")
    assert len(decisions) == 2 and all(item["frozen"] for item in decisions)
    assert sorted(run["kind"] for run in ledger.records("migration-run")) == ["dry", "final"]


def test_an_install_begun_after_an_admissions_copy_refuses_the_admission(tmp_path,
                                                                         ledger_folder):
    """Review finding (Major, R12): the scheduler's live backup admission reads a copy
    with no install; an install appends `installing` before the admission's append
    reaches the ledger. The append carries the head the admission read, so it is refused
    `stale-head`, the step runs again on a fresh copy, and the admission is refused for
    the install, leaving the request waiting. Before, both appends succeeded."""
    from backend.modules.operations.recovery import RecoveryRequests
    from backend.modules.operations.release_records import ReleaseRecords
    from backend.u8_policy import SYNTHETIC_OPERATIONS

    scheduler, sudo = client(tmp_path, ledger_folder, via="standing")
    requests = RecoveryRequests(scheduler, SYNTHETIC_OPERATIONS, clock=lambda: NOW,
                                mfa_current=lambda account, at: True)
    request = requests.request(origin="schedule", operation="backup.create",
                               environment="live", target_id="docsuri_u8",
                               expected_revision=requests.backup_revision("live"),
                               submission_id=uuid4())
    installer = wiring.LedgerClient(via="in-person", clock=lambda: NOW, run=sudo,
                                    paths=scheduler.paths)
    began = []
    sudo.before_append = lambda: began.append(ReleaseRecords(installer, clock=lambda: NOW)
                                              .begin("v2.0.0", "a" * 40, previous_tag=None))
    with pytest.raises(OperationsError) as refused:
        requests.admit(request["recoveryRequestId"])
    assert began and refused.value.code == "CONFLICT"
    assert refused.value.current["reasonKey"] == "release-install-active"
    assert scheduler.get("recovery-request", request["recoveryRequestId"])["state"] == (
        "requested")
    assert ReleaseRecords(scheduler, clock=lambda: NOW).get("v2.0.0")["state"] == "installing"


def test_two_dry_run_starts_from_the_same_copy_start_one_run(tmp_path, ledger_folder):
    """Review finding (Major, R12): two `start`s of a dry run whose copies both show no
    active run; the second's append is refused `stale-head`, its step runs again and
    is refused `run-active`."""
    from backend.modules.operations.ledger import Ledger
    from backend.modules.operations.migration_records import MigrationRuns

    direct = Ledger.open(ledger_folder, clock=lambda: NOW)
    approval = rf.approval_record(direct, "dry-run-go-ahead", "dry-run", now=NOW)
    direct.close()
    first, sudo = client(tmp_path, ledger_folder)
    second = wiring.LedgerClient(via="in-person", clock=lambda: NOW, run=sudo,
                                 paths=first.paths)
    started = []
    sudo.before_append = lambda: started.append(MigrationRuns(second, clock=lambda: NOW).start(
        "dry", tool_commit="b" * 40, go_ahead=approval["approvalId"]))
    with pytest.raises(OperationsError) as refused:
        MigrationRuns(first, clock=lambda: NOW).start(
            "dry", tool_commit="b" * 40, go_ahead=approval["approvalId"])
    assert started and refused.value.current == {"reasonKey": "run-active"}
    runs = first.records("migration-run")
    assert [run["runId"] for run in runs] == [started[0]["runId"]]


def test_an_append_naming_an_old_head_is_refused_stale_head(tmp_path, ledger_folder):
    ledger, sudo = client(tmp_path, ledger_folder)
    record = incident()
    first = ledger.append("service-incident", record, expect_revision=0)
    other = incident()
    stdout = io.BytesIO()
    code = sudo.command.run("append", io.BytesIO(json.dumps({
        "kind": "service-incident", "record": other, "expectRevision": 0, "receipts": [],
        "expectHead": {"count": 0, "head": "0" * 64}}).encode()), stdout, io.BytesIO())
    answer = json.loads(stdout.getvalue())
    assert code == 1 and answer["reason"] == "stale-head"
    assert answer["current"] == first["head"]
    assert ledger.get("service-incident", other["incidentId"]) is None
    code = sudo.command.run("append", io.BytesIO(json.dumps({
        "kind": "service-incident", "record": other, "expectRevision": 0, "receipts": [],
        "expectHead": first["head"]}).encode()), io.BytesIO(), io.BytesIO())
    ledger.refresh()  # the append went straight to the component: read a fresh copy
    assert code == 0 and ledger.get("service-incident", other["incidentId"]) == other


# --- the profile's state from the latest profile receipt ---------------------------------------


def receipt_facts(ledger, operation: str, inputs: dict) -> None:
    """One profile change's receipt facts, as the cutover tool's records add them."""
    facts = rf.receipt(operation, "profile", now=NOW)
    facts["inputHash"] = input_hash(inputs)
    ledger.atomic(lambda view: view._write("receipt-facts", facts))


def test_the_profiles_state_is_read_from_the_latest_profile_receipt(tmp_path):
    ledger = rf.open_ledger(tmp_path, lambda: NOW)
    try:
        assert wiring.ledger_profile_state(ledger) == wiring.DEFAULTS
        name = "docsuri_v2_rehearsal_" + "ab" * 6
        from backend.modules.operations.retained_copies import RetainedCopies
        from backend.u8_policy import PRODUCTION_OPERATIONS

        RetainedCopies(ledger, PRODUCTION_OPERATIONS).record("rehearsal-database", "run:x",
                                                             [f"database/{name}"])
        receipt_facts(ledger, "platform.profile.rehearsal-database",
                      {"field": "rehearsalDatabase", "value": name})
        receipt_facts(ledger, "platform.profile.mode", {"field": "mode", "value": "live"})
        approval = rf.approval_record(ledger, "admission-opening", "cutover", now=NOW)
        receipt_facts(ledger, "platform.profile.admission",
                      {"field": "admission", "value": "open",
                       "approvalId": approval["approvalId"]})
        assert wiring.ledger_profile_state(ledger) == {
            "mode": "live", "admission": "open", "rehearsalDatabase": name}
        receipt_facts(ledger, "platform.profile.rehearsal-database",
                      {"field": "rehearsalDatabase", "value": None})
        assert wiring.ledger_profile_state(ledger)["rehearsalDatabase"] is None
        receipt_facts(ledger, "platform.profile.mode", {"field": "mode", "value": "planted"})
        assert wiring.ledger_profile_state(ledger)["mode"] == "unknown"
        facts = wiring.production_facts(ledger, clock=lambda: NOW)()
        assert facts.names.production == "docsuri_v2" and facts.mode == "unknown"
        assert "org.docsuri.v2.host" in facts.labels
    finally:
        ledger.close()


# --- the operators --------------------------------------------------------------------------------


def installed(tmp_path) -> ArrangementPaths:
    paths = ArrangementPaths.under(tmp_path / "Library" / "DocSuri")
    paths.control.mkdir(parents=True)
    (paths.control / "platform-authorities.json").write_text(json.dumps({
        "actors": {"operator": "revenantonthemission", "scheduler": "_docsuri_v2_sched",
                   "service": "_docsuri_v2"},
        "authorities": {name: str(uuid4()) for name in (
            "operatorRoutine", "operatorDestructive", "schedulerRoutine", "schedulerRestore",
            "schedulerRemoval", "serviceReader")}}))
    paths.scheduler.mkdir(parents=True)
    descriptor = os.open(paths.scheduler_credentials, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        # The two logins' passwords, sixty-four hex digits each, generated per run (L1-36).
        json.dump({"database": {"user": "docsuri_scheduler", "password": os.urandom(32).hex()},
                   "platform": {"user": "docsuri_platform_scheduler",
                                "password": os.urandom(32).hex()},
                   "actor": "_docsuri_v2_sched",
                   "authorities": {"schedulerRoutine": str(uuid4()),
                                   "schedulerRestore": str(uuid4()),
                                   "schedulerRemoval": str(uuid4())}}, stream)
    descriptor = os.open(paths.healthchecks, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump({check: f"https://hc-ping.com/{check}" for check in (
            "heartbeat", "backup", "verification")}, stream)
    for actor in ("operator", "scheduler"):
        folder = paths.effects / actor
        folder.mkdir(parents=True)
        (folder / "driver.json").write_text(json.dumps({
            "kind": "arrangement", "production": True, "actor": actor, "databasePort": 15432,
            "v1Stores": {"v1-stores/database": str(tmp_path / "v1-db")},
            "schedulerCredentials": str(paths.scheduler_credentials)}))
    return paths


def test_the_operator_in_person_releases_its_store_login(tmp_path):
    paths = installed(tmp_path)
    released = bytearray(secrets.token_hex(32).encode())
    asked = []

    def release(login):
        asked.append(login)
        return released

    operator = wiring.production_operator(SimpleNamespace(), paths=paths, release=release,
                                          actor="revenantonthemission", clock=lambda: NOW)
    assert asked == ["platform"] and set(released) == {0}
    assert operator.actor == "revenantonthemission" and operator.standing is False
    assert set(operator.authorities) == {enums.CLASS_ROUTINE, enums.CLASS_DESTRUCTIVE}
    assert operator.profile.effects_root == paths.effects / "operator"
    assert operator.store.role == "docsuri_platform_operator"
    with pytest.raises(wiring.WiringRefused, match="not-the-installed-operator"):
        wiring.production_operator(SimpleNamespace(), paths=paths, release=release,
                                   actor="someone-else")
    with pytest.raises(wiring.WiringRefused, match="platform-authorities-not-installed"):
        wiring.production_operator(SimpleNamespace(), paths=ArrangementPaths.under(
            tmp_path / "empty"), release=release, actor="revenantonthemission")


def test_the_in_person_operator_is_the_account_its_release_named(tmp_path, monkeypatch):
    """Step 120(c) (D4, security-design § 5.3 and § 5.5; L2-6): the operator tool binds
    the account its credential release authenticated, never its own process's account;
    the release command reads its own `SUDO_UID` through the checked authority read."""
    import inspect

    paths = installed(tmp_path)
    authorities = paths.control / "platform-authorities.json"
    os.chmod(authorities, 0o644)
    installed_operator = json.loads(authorities.read_bytes())["actors"]["operator"]
    # Patched user identifiers: this process's own account is never the operator.
    monkeypatch.setattr(wiring.pwd, "getpwuid",
                        lambda uid: SimpleNamespace(pw_name="process-account"))
    released = bytearray(secrets.token_hex(32).encode())  # generated per run (L1-36)
    asked = []

    def released_as(name: str):
        def release(login):
            asked.append(login)
            return released, name

        return release

    operator = wiring.production_operator(SimpleNamespace(), paths=paths,
                                          released_as=released_as(installed_operator),
                                          clock=lambda: NOW)
    assert operator.actor == installed_operator and asked == ["platform"]
    assert set(released) == {0}
    assert operator.store.role == "docsuri_platform_operator"

    other = bytearray(secrets.token_hex(32).encode())

    def release_other(login):
        return other, "someone-else"

    with pytest.raises(wiring.WiringRefused, match="not-the-installed-operator"):
        wiring.production_operator(SimpleNamespace(), paths=paths, released_as=release_other,
                                   clock=lambda: NOW)
    assert set(other) == {0}

    spied = []
    with pytest.raises(wiring.WiringRefused, match="platform-authorities-not-installed"):
        wiring.production_operator(SimpleNamespace(), paths=ArrangementPaths.under(
            tmp_path / "empty"), released_as=lambda login: spied.append(login))
    assert spied == []

    accounts = {501: installed_operator, 502: "someone-else"}

    def lookup(uid: int):
        if uid not in accounts:
            raise KeyError(uid)
        return SimpleNamespace(pw_name=accounts[uid])

    def actor(environ, **options):
        return wiring.in_person_actor(paths, environ, lookup=lookup,
                                      **{"owner_uid": os.getuid(), **options})

    assert actor({"SUDO_UID": "501"}) == installed_operator
    for environ in ({}, {"SUDO_UID": "x"}):
        with pytest.raises(wiring.WiringRefused, match="in-person-actor-refused"):
            actor(environ)
    with pytest.raises(wiring.WiringRefused, match="not-the-installed-operator"):
        actor({"SUDO_UID": "502"})
    os.chmod(authorities, 0o664)
    with pytest.raises(wiring.WiringRefused, match="authorities-file-refused"):
        actor({"SUDO_UID": "501"})
    os.chmod(authorities, 0o644)
    kept = tmp_path / "kept-authorities.json"
    authorities.rename(kept)
    authorities.symlink_to(kept)
    with pytest.raises(wiring.WiringRefused, match="authorities-file-refused"):
        actor({"SUDO_UID": "501"})
    authorities.unlink()
    kept.rename(authorities)
    with pytest.raises(wiring.WiringRefused, match="authorities-file-refused"):
        actor({"SUDO_UID": "501"}, owner_uid=0)

    source = inspect.getsource(wiring.release_platform)
    assert "in_person_actor(paths, os.environ)" in source
    assert "probe=signed_out_probe" in source
    assert '_authorities(paths)["actors"]["operator"]' not in source


def test_a_refused_release_is_a_wiring_refusal_in_both_branches(tmp_path):
    """The maintainer's decision of 2026-11-16 ("Fix the test and answer refusals"): a
    release that refuses is `credential-not-released`, a wiring refusal every word
    answers, whether the actor was named first or read from the release."""
    from docsuri_ops.u8_platform.credential_release import ReleaseRefused

    paths = installed(tmp_path)
    installed_operator = json.loads(
        (paths.control / "platform-authorities.json").read_bytes())["actors"]["operator"]
    asked = []

    def refused(login):
        asked.append(login)
        raise ReleaseRefused("the credential was not released")

    with pytest.raises(wiring.WiringRefused, match="^credential-not-released$") as caught:
        wiring.production_operator(SimpleNamespace(), paths=paths, released_as=refused,
                                   clock=lambda: NOW)
    assert caught.value.__cause__ is None and caught.value.__suppress_context__
    with pytest.raises(wiring.WiringRefused, match="^credential-not-released$") as caught:
        wiring.production_operator(SimpleNamespace(), paths=paths, release=refused,
                                   actor=installed_operator, clock=lambda: NOW)
    assert caught.value.__cause__ is None and caught.value.__suppress_context__
    assert asked == ["platform", "platform"]


def test_the_standing_authority_uses_the_schedulers_own_file(tmp_path):
    paths = installed(tmp_path)
    operator = wiring.standing_operator(SimpleNamespace(), paths=paths, clock=lambda: NOW)
    assert operator.standing is True and operator.actor == "_docsuri_v2_sched"
    assert operator.profile.effects_root == paths.effects / "scheduler"
    assert operator.store.role == "docsuri_platform_scheduler"
    # Its three grants: the routine and removal grants by class, and the restore grant
    # for the restore alone (the person's decision of 2026-10-26).
    granted = json.loads(paths.scheduler_credentials.read_bytes())["authorities"]
    assert operator.authorities == {enums.CLASS_ROUTINE: granted["schedulerRoutine"],
                                    enums.CLASS_DESTRUCTIVE: granted["schedulerRemoval"]}
    assert operator.operation_grants == {"platform.database.restore":
                                         granted["schedulerRestore"]}
    os.chmod(paths.scheduler_credentials, 0o644)
    with pytest.raises(wiring.WiringRefused, match="scheduler-credentials-unavailable"):
        wiring.standing_operator(SimpleNamespace(), paths=paths)


def test_the_standing_jobs_production_parts(tmp_path):
    from docsuri_ops.standing.main import build_lanes

    paths = installed(tmp_path)
    parts = wiring.production_parts(stub_ledger(), paths=paths, clock=lambda: NOW)
    lanes = build_lanes(parts)
    assert list(lanes.lanes) == ["heartbeat", "agent-status", "isolation", "backup",
                                 "verification", "housekeeping"]
    assert set(parts.checks.addresses.values()) == {
        f"https://hc-ping.com/{name}" for name in ("heartbeat", "backup", "verification")}
    assert parts.recovery.procedures.platform.production == "docsuri_v2"
    assert parts.recovery.procedures.platform.scratch_name().startswith("docsuri_v2_scratch_")
    # The pass and the standing job's requests read one function (L1-65).
    assert parts.recovery.disposal.__self__.platform.environment is parts.recovery.environment
    # The production policy and the 5-minute record (U8 plan Step 67(g)).
    from backend.u8_policy import PRODUCTION_OPERATIONS

    assert parts.policy is PRODUCTION_OPERATIONS
    assert (parts.policy.backup_hour_seoul, parts.policy.verification_hour_seoul,
            parts.policy.verification_weekday) == (4, 5, 6)
    assert parts.slot_seconds == 300 == parts.heartbeat.record.slot_seconds
    assert parts.heartbeat.record.folder == paths.availability
    assert ArrangementPaths().availability == Path("/Library/DocSuri/availability")
    # The start record's watch (Step 66(e)) and the agent status's ledger identities.
    assert parts.start_watch.folder == paths.scheduler / "evidence" / "starts"
    assert parts.agent.identities is not None
    # The start record stays out of the 0755 availability folder (Step 66(e), 67(e)): the
    # watch writes its line in the wiring's starts folder, after a heartbeat slot line,
    # and the availability folder still holds only month files.
    import re

    from docsuri_ops.standing.heartbeat import Answer, StartWatch

    parts.heartbeat.record.append(NOW, True, "ok")
    StartWatch(parts.start_watch.folder, lambda: Answer("answered", 200),
               lambda: NOW).watch()
    assert all(re.fullmatch(r"\d{4}-\d{2}\.jsonl", item.name)
               for item in paths.availability.iterdir())
    [day] = list(parts.start_watch.folder.iterdir())
    assert json.loads(day.read_text())["readyAt"] is not None


def test_the_standing_jobs_parts_read_the_ledger_client_itself(tmp_path, ledger_folder):
    """Review finding (Minor, batch 4 re-review): production's parts hold the
    `LedgerClient` itself, unwrapped, so the schedule's `fresh()` and the disposal pass's
    own fresh read drop its copy; what another process records then reaches them."""
    from backend.modules.operations.ledger import Ledger
    from tests.u8_service_operations_integration import cutover_flows as cf
    from tests.u8_service_operations_integration.conftest import Clock

    clock = Clock(NOW)
    paths = installed(tmp_path)
    ledger, _ = client(tmp_path, ledger_folder, via="standing")
    other = Ledger.open(ledger_folder, clock=clock)
    try:
        parts = wiring.production_parts(ledger, paths=paths, clock=clock,
                                        send=lambda url, seconds: 200)
        disposal = parts.recovery.disposal.__self__
        assert parts.recovery.ledger is ledger and parts.recovery.requests.ledger is ledger
        assert parts.recovery.procedures.ledger is ledger
        assert disposal.ledger is ledger and parts.agent.disposal.__self__ is disposal
        assert parts.recovery.environment() == "rehearsal"  # the client's copy is taken
        # Another process: a switch's profile receipt.
        facts = rf.receipt("platform.profile.mode", "profile", now=clock())
        facts["inputHash"] = input_hash({"field": "mode", "value": "live"})
        other.atomic(lambda view: view._write("receipt-facts", facts))
        parts.recovery.fresh()
        assert parts.recovery.environment() == "live"
        # Another process begins a switch: the passed-again pass's own fresh read holds
        # it, before the pass would reach the agent.
        cf.switching(other, clock)
        disposal.fresh()
        assert disposal.blocked() == "live-exclusion-held"
        assert parts.agent.disposal() == {"ran": False, "reason": "live-exclusion-held"}
    finally:
        other.close()
        ledger.close()


def test_the_production_lanes_follow_the_lane_table(tmp_path):
    """U8 plan Step 67(g): the lane table on production's parts, over a private ledger on
    a literal clock. No profile receipt is held, so the environment reads rehearsal."""
    from backend.modules.operations.recovery import RecoveryRequests
    from backend.modules.operations.tombstones import Tombstones
    from backend.u8_policy import PRODUCTION_OPERATIONS
    from docsuri_ops.standing.main import build_lanes
    from tests.u8_service_operations_integration.conftest import Clock

    at = dt.datetime(2026, 10, 22, 19, 7, 31, tzinfo=dt.UTC)
    clock = Clock(at)
    paths = installed(tmp_path)
    ledger = rf.open_ledger(tmp_path, clock)
    try:
        parts = wiring.production_parts(ledger, paths=paths, clock=clock,
                                        send=lambda url, seconds: 200)
        lanes = build_lanes(parts).lanes
        five = dt.datetime(2026, 10, 22, 19, 5, tzinfo=dt.UTC)
        for name in ("heartbeat", "agent-status", "isolation"):
            assert lanes[name].latest(at) == five, name
        isolation = lanes["isolation"].latest
        assert isolation(dt.datetime(2026, 10, 22, 19, 9, 59, tzinfo=dt.UTC)) == five
        ten = dt.datetime(2026, 10, 22, 19, 10, tzinfo=dt.UTC)
        assert isolation(ten) == ten
        hour = dt.datetime(2026, 10, 22, 19, tzinfo=dt.UTC)
        assert lanes["backup"].latest(at) == hour and lanes["housekeeping"].latest(at) == hour
        assert lanes["verification"].latest(at) == dt.datetime(2026, 10, 17, 20, tzinfo=dt.UTC)
        clock.now = dt.datetime(2026, 10, 21, 10, tzinfo=dt.UTC)
        Tombstones(ledger).claim(uuid4(), uuid4())
        clock.now = at
        assert lanes["verification"].latest(at) == dt.datetime(2026, 10, 21, 20, tzinfo=dt.UTC)
        assert parts.recovery.environment() == "rehearsal"
        rf.set_record(ledger, environment="rehearsal", now=at - dt.timedelta(hours=23, minutes=59))
        assert not parts.recovery.backup_overdue(at)
        assert parts.recovery.backup_overdue(at + dt.timedelta(minutes=1, seconds=1))
        # Housekeeping expires a request 24 h + 1 s old and keeps 13 months of records.
        requests = RecoveryRequests(ledger, PRODUCTION_OPERATIONS, clock=clock)
        clock.now = at - dt.timedelta(hours=24, seconds=1)
        old = requests.request(origin="schedule", operation="backup.create",
                               environment="rehearsal", target_id="docsuri_v2",
                               expected_revision=1, submission_id=uuid4())
        clock.now = at
        paths.availability.mkdir(parents=True, exist_ok=True)
        for month in ("2025-08", "2025-09"):
            (paths.availability / f"{month}.jsonl").write_text("")
        report = parts.housekeeping.run(at)
        assert report["expiredRequests"] == 1
        assert requests.get(old["recoveryRequestId"])["state"] == "expired"
        assert sorted(item.name for item in paths.availability.iterdir()) == ["2025-09.jsonl"]
        assert lanes["isolation"].work is parts.isolation
    finally:
        ledger.close()


def test_the_production_heartbeat_probes_both_ready_routes(tmp_path, monkeypatch):
    from docsuri_ops.standing import heartbeat as heartbeats

    probed, pinged = [], []

    def probe(url, *, seconds):
        probed.append((url, seconds))
        return heartbeats.Answer("answered", 200)

    monkeypatch.setattr(heartbeats, "probe", probe)
    parts = wiring.production_parts(stub_ledger(), paths=installed(tmp_path),
                                    clock=lambda: NOW,
                                    send=lambda url, seconds: pinged.append(url) or 200)
    assert parts.heartbeat.run(NOW) == "ok"
    assert probed == [("https://docsuri.rvnnt.dev/health/ready", 10),
                      ("http://127.0.0.1:18200/health/ready", 10)]
    assert pinged == ["https://hc-ping.com/heartbeat"]


def test_the_recovery_procedures_reach_the_restore_evaluation_through_the_tool(tmp_path,
                                                                             monkeypatch):
    from docsuri_ops import production_tool

    paths = installed(tmp_path)
    seen = []
    monkeypatch.setattr(production_tool, "invoke", lambda word, document, **options: (
        seen.append((word, document, options.get("login"))) or {"result": {"surviving": 0}}))

    driver = SimpleNamespace(agent_word=lambda word, document, *, via: {"word": word})
    operator = SimpleNamespace(facts=lambda: SimpleNamespace(current_rehearsal=None))
    procedures = wiring.production_procedures(
        stub_ledger(), operator,
        role="operator", paths=paths, driver=driver,
        release=lambda login: bytearray(secrets.token_hex(32).encode())
    ).procedures
    platform = procedures.platform
    assert platform.restore_evaluate("docsuri_v2", ["a"]) == {"surviving": 0}
    assert seen == [("restore-evaluate", {"database": "docsuri_v2", "accounts": ["a"]},
                     "restore")]
    with pytest.raises(ValueError):
        platform.drop_scratch("docsuri_v2")
    assert platform.agent("status", {}, via="in-person") == {"word": "status"}


def test_the_in_person_ledger_copy_runs_the_component_then_the_agent(tmp_path, ledger_folder):
    """The in-person procedures' ledger copy (review finding, Critical, R15): the ledger
    component's `copy` through the client (`sudo -k -u _docsuri_v2`), then those bytes
    into the agent's `ledger-copy` (`sudo -k -u _docsuri_r1t_backup`), one after the
    other, each asking for the password on its own; the agent's result is read from its
    standard error, and a refusal raises."""
    from docsuri_ops.u8_platform.drivers import DriverRefused
    from docsuri_ops.u8_platform.drivers.arrangement import ArrangementDriver

    ledger, sudo = client(tmp_path, ledger_folder)
    ledger.append("service-incident", incident(), expect_revision=0)
    agent_calls = []
    answer = {"ok": True, "recordId": str(uuid4()), "location": "u8/ledger-copy-x.archive",
              "stagingLocation": "staging/x", "sha256": "a" * 64,
              "disposeAfter": "2026-11-06T02:00:00.000Z", "integrity": "passed"}

    def agent_run(argv, *, input, capture_output, timeout, check):
        agent_calls.append((argv, input))
        return SimpleNamespace(returncode=0 if answer["ok"] else 1, stdout=b"",
                               stderr=json.dumps(answer).encode() + b"\n")

    paths = installed(tmp_path)
    driver = ArrangementDriver(json.loads((paths.effects / "operator" / "driver.json")
                                          .read_bytes()), run=agent_run)
    operator = SimpleNamespace(facts=lambda: SimpleNamespace(current_rehearsal=None))
    platform = wiring.production_procedures(
        ledger, operator, role="operator", paths=paths, driver=driver,
        release=lambda login: bytearray(secrets.token_hex(32).encode())).procedures.platform
    expected = io.BytesIO()
    head = ledger.copy(expected)
    copied = platform.ledger_copy()
    assert copied["agent"]["recordId"] == answer["recordId"]
    assert copied["head"]["count"] == head["count"] >= 1
    assert copied["head"]["head"] == head["head"]
    assert sudo.argvs[-1][:4] == [wiring.SUDO, "-k", "-u", "_docsuri_v2"]
    assert sudo.argvs[-1][-1] == "copy"
    ((argv, sent),) = agent_calls
    assert argv == [wiring.SUDO, "-k", "-u", "_docsuri_r1t_backup",
                    "/Library/DocSuri/release/ops/bin/docsuri-backup-agent", "ledger-copy"]
    assert sent == expected.getvalue()  # the component's copy, byte for byte
    answer.update(ok=False, reason="volume-check-failed")
    with pytest.raises(DriverRefused, match="volume-check-failed"):
        platform.ledger_copy()
    ledger.close()


def test_the_switchs_first_live_backup_answers_a_failed_ledger_copy_as_its_step(
        tmp_path, monkeypatch):
    """A set recorded whose ledger copy failed is the procedures' `ProcedureFailed`, which
    the switch's first live backup turns into its step's failure (the switch aborts);
    nothing escapes after the set was recorded (review finding, Critical, R15)."""
    from backend.modules.operations.recovery_procedures import ProcedureFailed
    from docsuri_ops.cutover.tool import StepFailed

    taken = []

    def take(environment, trigger, **options):
        taken.append((environment, trigger, options["owner_key"]))
        raise ProcedureFailed("ledger-copy-failed")

    monkeypatch.setattr(wiring, "production_procedures", lambda *args, **options:
                        SimpleNamespace(procedures=SimpleNamespace(take=take)))
    operator = SimpleNamespace(facts=lambda: SimpleNamespace(current_rehearsal=None))
    platform = wiring.production_cutover_platform(
        stub_ledger(), operator, paths=installed(tmp_path), clock=lambda: NOW,
        release=lambda login: bytearray(secrets.token_hex(32).encode()))
    with pytest.raises(StepFailed, match="ledger-copy-failed"):
        platform.first_backup("cutover:first-live-backup:1")
    assert taken == [("live", "first-live", "cutover:first-live-backup:1")]


def test_the_cutover_platform_on_this_mac(tmp_path):
    paths = installed(tmp_path)
    operator = SimpleNamespace(facts=lambda: SimpleNamespace(current_rehearsal=None))
    platform = wiring.production_cutover_platform(
        stub_ledger(), operator, paths=paths,
        clock=lambda: NOW, release=lambda login: bytearray(secrets.token_hex(32).encode()))
    assert platform.v1_labels == ("dev.docsuri.api", "dev.docsuri.web",
                                  "dev.docsuri.worker-purge", "dev.docsuri.heartbeat")
    assert platform.v2_labels == ("org.docsuri.v2.host", "org.docsuri.v2.workers",
                                  "org.docsuri.v2.scheduler")
    assert platform.production == "docsuri_v2"
    assert platform.evidence_folder == paths.effects / "operator" / "evidence"
    assert platform.v1_store_present("v1-stores/database") is False
    (tmp_path / "v1-db").mkdir()
    assert platform.v1_store_present("v1-stores/database") is True
    with pytest.raises(wiring.WiringRefused):
        platform.v1_store_present("v1-stores/elsewhere")


# --- the migration's import phases on this Mac -------------------------------------------------


def import_header(**changes) -> dict:
    return {"login": {"password": os.urandom(32).hex()}, "runId": str(uuid4()),  # L1-36
            "importDatabase": "docsuri_v2_import_" + "1" * 12,
            "targetDatabase": "docsuri_v2_rehearsal_" + "2" * 12, "decisions": [],
            "final": False, "required": [], "archives": {"index": 0, "objects": 0},
            "toWrite": 0, **changes}


def test_the_import_runner_refuses_before_anything_runs():
    for header, reason in (
        ({**import_header(), "extra": 1}, "header-refused"),
        (import_header(login={"user": "x"}), "released-login-required"),
        (import_header(importDatabase="docsuri_v2"), "database-refused"),
        (import_header(targetDatabase="docsuri_v2_import_" + "3" * 12), "database-refused"),
        (import_header(archives={"index": 5, "objects": 0}), "archives-refused"),
    ):
        with pytest.raises(ValueError, match=reason):
            wiring.production_import("import", header, b"",
                                     profile=SimpleNamespace(is_production=True))
    with pytest.raises(ValueError, match="production-profile-only"):
        wiring.production_import("import", import_header(), b"",
                                 profile=SimpleNamespace(is_production=False))


def test_the_import_runner_checks_the_archives_against_their_manifests():
    from backend.modules.operations.migration.v1_source import LISTING_MEMBER, encode_listing
    from docsuri_ops.backup_agent import archives

    index = archives.pack({"documents.jsonl": b'{"id": "d1"}\n'})
    entry = {"key": "uploads/evidence/u/a/a/paper.pdf", "size": 12, "etag": '"e"'}
    objects = archives.pack({"objects/a.pdf": b"%PDF fixture",
                             LISTING_MEMBER: encode_listing([entry])})
    header = import_header(archives={"index": len(index), "objects": len(objects)})
    parsed = wiring._archives(header, index + objects)
    # The reserved listing member is taken out of the objects and parsed (Step 68(c)).
    assert parsed == {"index_documents": [{"id": "d1"}],
                      "objects": {"objects/a.pdf": b"%PDF fixture"}, "listing": [entry]}
    # A member whose bytes changed after the manifest recorded its checksum.
    tampered = archives.pack({"documents.jsonl": b'{"id": "d2"}\n'}).replace(
        b'{"id": "d2"}', b'{"id": "d3"}')
    with pytest.raises(ValueError, match="archive-member-checksum-differs"):
        wiring._archives({**header, "archives": {"index": len(tampered), "objects": 0}},
                         tampered)


def test_the_production_disk_readers_give_f_bavail_times_f_frsize(tmp_path, monkeypatch):
    """Step 69(b) (S3): production's one free-space reader, `f_bavail × f_frsize`."""
    import os

    paths = installed(tmp_path)
    driver = SimpleNamespace(agent_word=lambda word, document, *, via: {"word": word})
    operator = SimpleNamespace(facts=lambda: SimpleNamespace(current_rehearsal=None))
    platform = wiring.production_procedures(
        stub_ledger(), operator, role="operator", paths=paths, driver=driver,
        release=lambda login: bytearray(secrets.token_hex(32).encode())).procedures.platform
    monkeypatch.setattr(os, "statvfs", lambda path: SimpleNamespace(
        f_bsize=1048576, f_frsize=4096, f_blocks=10000, f_bfree=5000, f_bavail=1000))
    assert wiring.free_space(paths) == 4_096_000
    assert platform.free_bytes() == 4_096_000


# Step 90(a) (L1-35): the import runner on the real owners is, in
# `integration/test_production_import_runner.py`, the test
# `test_the_import_runner_composes_the_real_owners_on_the_production_stand_in`.


# --- the release command's readers -------------------------------------------------------------


def test_the_github_reader_tells_annotated_tags_and_main(tmp_path):
    answers = {
        "/git/ref/tags/v2.0.0": {"object": {"type": "tag", "sha": "t" * 40}},
        "/git/tags/" + "t" * 40: {"object": {"sha": "c" * 40}},
        "/git/ref/tags/v2.0.1": {"object": {"type": "commit", "sha": "d" * 40}},
        f"/compare/{'c' * 40}...main": {"status": "behind"},
        f"/compare/{'d' * 40}...main": {"status": "diverged"},
        "/releases/tags/v2.0.0": {"assets": [{"name": "x.tar.gz",
                                              "browser_download_url": "https://dl/x"}]},
    }

    def fetch(url):
        if url == "https://dl/x":
            return b"asset"
        path = url.removeprefix("https://api.github.com/repos/o/r")
        if path not in answers:
            raise OSError("404")
        return json.dumps(answers[path]).encode()

    reader = wiring.GitHubReader(fetch, "o/r")
    assert reader.tag("v2.0.0") == {"sha": "c" * 40, "annotated": True}
    assert reader.tag("v2.0.1") == {"sha": "d" * 40, "annotated": False}
    assert reader.tag("v9.9.9") is None
    assert reader.on_main("c" * 40) is False and reader.on_main("d" * 40) is False
    answers[f"/compare/{'c' * 40}...main"] = {"status": "ahead"}
    assert reader.on_main("c" * 40) is True
    assert reader.asset("v2.0.0", "x.tar.gz") == b"asset"
    with pytest.raises(wiring.WiringRefused):
        reader.asset("v2.0.0", "missing")


def test_the_github_reader_lists_every_check_run_with_its_app_and_refuses_a_partial_list():
    """The infrastructure re-check's R-13: GitHub's reader asks for `filter=latest` on one
    page of up to 100, keeps each run's app, and refuses a page that does not hold every
    run (`check-runs-incomplete`)."""
    runs = [
        {"name": "U8 complete / browser", "status": "completed", "conclusion": "success",
         "id": 1, "app": {"slug": "github-actions", "id": 15368},
         "output": {"title": "passed", "summary": ""}},
        {"name": "frontend", "status": "completed", "conclusion": "failure", "id": 2,
         "app": {"slug": "github-actions"}},
        {"name": "U8 complete / frontend", "status": "completed", "conclusion": "success",
         "id": 3},
    ]
    answer = {"total_count": 3, "check_runs": runs}
    requested = []

    def fetch(url):
        requested.append(url)
        path = url.removeprefix("https://api.github.com/repos/o/r")
        if not path.startswith(f"/commits/{'c' * 40}/check-runs"):
            raise OSError("404")
        return json.dumps(answer).encode()

    reader = wiring.GitHubReader(fetch, "o/r")
    assert reader.check_runs("c" * 40) == [
        {"name": "U8 complete / browser", "status": "completed", "conclusion": "success",
         "id": 1, "app": "github-actions"},
        {"name": "frontend", "status": "completed", "conclusion": "failure", "id": 2,
         "app": "github-actions"},
        {"name": "U8 complete / frontend", "status": "completed", "conclusion": "success",
         "id": 3, "app": None},
    ]
    assert requested == ["https://api.github.com/repos/o/r/commits/" + "c" * 40
                         + "/check-runs?filter=latest&per_page=100"]
    for partial in ({"total_count": 4, "check_runs": runs}, {"check_runs": runs}):
        answer = partial
        with pytest.raises(Refused) as raised:
            reader.check_runs("c" * 40)
        assert raised.value.reason == "check-runs-incomplete"


def latency_lines(*minutes_ago: int) -> str:
    """Latency summaries of 30 requests each, `minutes_ago` before NOW."""
    return "".join(json.dumps({"window": (NOW - dt.timedelta(minutes=minutes)).isoformat()
                               .replace("+00:00", "Z"), "class": "read", "count": 30}) + "\n"
                   for minutes in minutes_ago)


def test_the_request_rate_and_the_latest_isolation_result(tmp_path):
    folder = tmp_path / "latency"
    folder.mkdir()
    window = (NOW - dt.timedelta(minutes=3)).isoformat()
    outside_form = [
        "not json", "[1]", "{\"window\": 3}",
        # The re-review of 2026-11-10: each of these used to escape `request_rate` and end
        # the release's preflight; each now counts 0, though its window is inside the 15
        # minutes and, but for the one field, the line is one the rate counts.
        json.dumps({"window": window.replace("+00:00", ""), "count": 30}),  # no offset
        f'{{"window": "{window}", "count": Infinity}}',
        f'{{"window": "{window}", "count": 1e999}}',
        json.dumps({"window": window, "count": -30}),
        json.dumps({"window": window, "count": "30"}),
        # The batch-7 review: a whole count past any float, which `total / minutes`
        # used to turn into OverflowError.
        f'{{"window": "{window}", "count": {10**400}}}',
        json.dumps({"window": window, "count": wiring.LATENCY_COUNT_MAX + 1}),
        "[" * 200_000 + "]" * 200_000,  # nests past the decoder's recursion limit
    ]
    (folder / f"{NOW:%Y-%m-%d}.jsonl").write_text(
        latency_lines(2, 7, 12, 40) + "".join(line + "\n" for line in outside_form))
    assert wiring.request_rate(folder, now=NOW, base=tmp_path) == 90 / 15
    accepted = json.dumps({"window": window, "count": 30})
    assert wiring._latency_count(accepted, NOW - dt.timedelta(minutes=15)) == 30
    largest = json.dumps({"window": window, "count": wiring.LATENCY_COUNT_MAX})
    assert wiring._latency_count(largest, NOW - dt.timedelta(minutes=15)) == (
        wiring.LATENCY_COUNT_MAX)
    isolation = tmp_path / "isolation"
    assert wiring.latest_isolation(isolation) is None
    isolation.mkdir()
    (isolation / "20261023T010000Z.json").write_text(json.dumps({"passed": False}))
    (isolation / "20261023T015500Z.json").write_text(json.dumps({"passed": True}))
    assert wiring.latest_isolation(isolation) == {"passed": True}


def test_the_release_preflights_request_rate_reads_only_the_service_accounts_own_day_file(
        tmp_path, monkeypatch):
    """The review of the sweep (2026-11-10): the release command, run as root, reads
    `profile/evidence/latency/<day>.jsonl` at preflight, in the service account's folder.
    A link at the day file, a second name of another file and a FIFO there, a link in
    place of `latency`, and the service account's day file given to another owner each
    count as no lines, although every planted file holds 90 requests the rate would
    otherwise count; none of them is read, and the FIFO answers at once. The service
    account's own regular file is counted. The release platform passes the prefix and the
    service account (`release_platform`'s `request_rate`)."""
    import inspect
    import threading

    from tests.u8_service_operations_integration import arrangement_flows as af

    prefix = tmp_path / "prefix"
    folder = prefix / "profile" / "evidence" / "latency"
    folder.mkdir(parents=True)
    day = folder / f"{NOW:%Y-%m-%d}.jsonl"
    mine = (os.getuid(),)
    other = tmp_path / "another-file"
    other.write_text(latency_lines(2, 7, 12))
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    decoy = elsewhere / day.name
    decoy.write_text(latency_lines(2, 7, 12))
    marks = {path: (path.read_bytes(), path.stat().st_mode, path.stat().st_ino)
             for path in (other, decoy)}

    def rate(owners=mine):
        return wiring.request_rate(folder, now=NOW, base=prefix, owners=owners)

    inodes = af.reads_recorded(monkeypatch)
    for plant in (lambda: day.symlink_to(other), lambda: os.link(other, day)):
        plant()
        assert rate() == 0
        day.unlink()
    os.mkfifo(day)
    answers: list[float] = []
    worker = threading.Thread(target=lambda: answers.append(rate()), daemon=True)
    worker.start()
    worker.join(10)
    stalled = worker.is_alive()
    if stalled:  # release the blocked reader before failing
        os.close(os.open(day, os.O_WRONLY | os.O_NONBLOCK))
    assert not stalled and answers == [0]
    day.unlink()
    kept = tmp_path / "kept-latency"
    folder.rename(kept)
    folder.symlink_to(elsewhere)
    assert rate() == 0
    folder.unlink()
    kept.rename(folder)
    assert not {mark[2] for mark in marks.values()} & set(inodes)
    day.write_text(latency_lines(2, 7, 12))
    assert rate(owners=(os.getuid() + 1,)) == 0
    assert rate() == 90 / 15
    assert {path: (path.read_bytes(), path.stat().st_mode, path.stat().st_ino)
            for path in marks} == marks
    source = inspect.getsource(wiring.release_platform)
    assert "base=paths.prefix" in source and "owners=(Accounts.standard().service.uid,)" in source


# --- Step 164(b): the operator tool's and the standing job's connections (NFR3.3; L4-12) ----


def _name_v1_sources(paths, tmp_path) -> None:
    """The operator's environment file with v1's stores named, as the migration tool reads
    it; nothing is ever opened at these addresses here."""
    descriptor = os.open(tmp_path / "objects.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:  # both values made per run (L1-36)
        json.dump({"accessKey": secrets.token_hex(8), "secretKey": secrets.token_hex(16)},
                  stream)
    file = paths.effects / "operator" / "driver.json"
    file.write_text(json.dumps({**json.loads(file.read_bytes()), "v1Sources": {
        "database": {"host": "127.0.0.1", "port": 15510, "database": "docsuri_v1"},
        "index": {"url": "http://127.0.0.1:19209", "name": "papers"},
        "objects": {"url": "http://127.0.0.1:19009", "bucket": "docsuri-papers",
                    "credentials": str(tmp_path / "objects.json")}}}))


def test_every_connection_of_the_operator_tool_and_the_standing_job_requires_scram(
        tmp_path, monkeypatch):
    """Each connection is asked of the driver at 127.0.0.1:15432 with its own login, its
    database and `require_auth=scram-sha-256`. The driver's `connect` is a raise-only spy
    that refuses before any connection and carries what it was asked for."""
    import psycopg

    from docsuri_ops.migration.production import production_migration_tool
    from tests.u8_service_operations_integration.operations.test_scram_sites import (
        Reached,
        demanded,
        refusing_connect,
    )

    monkeypatch.setattr(psycopg, "connect", refusing_connect)
    paths = installed(tmp_path)
    _name_v1_sources(paths, tmp_path)
    scratch, imported = "docsuri_v2_scratch_" + "0a" * 6, "docsuri_v2_import_" + "0b" * 6

    def release(login):
        return bytearray(secrets.token_hex(32).encode())

    def asked(call) -> tuple:
        with pytest.raises(Reached) as reached:
            call()
        options = reached.value.options
        assert options["password"] and options["connect_timeout"] == 5
        return demanded(options)

    def reading(platform, name):
        with platform.import_reader(name):
            raise AssertionError("no connection is opened here")

    driver = SimpleNamespace(agent_word=lambda word, document, *, via: {"word": word})
    operator = SimpleNamespace(facts=lambda: SimpleNamespace(current_rehearsal=None))
    standing = wiring.production_procedures(
        stub_ledger(), operator, role="scheduler", paths=paths, driver=driver,
    ).procedures.platform
    in_person = wiring.production_procedures(
        stub_ledger(), operator, role="operator", paths=paths, driver=driver, release=release,
    ).procedures.platform
    cutover = wiring.production_cutover_platform(
        stub_ledger(), operator, paths=paths, clock=lambda: NOW, release=release)
    migration = production_migration_tool(
        stub_ledger(), operator, clock=lambda: NOW, paths=paths, release=release).platform
    scram, here = "scram-sha-256", ("127.0.0.1", 15432)
    assert {
        "the scheduler's scratch checks": asked(lambda: standing.scratch_checks(scratch, [])),
        "the scheduler's drop": asked(lambda: standing.drop_scratch(scratch)),
        "the operator's disposable login": asked(
            lambda: in_person.scratch_checks(scratch, [])),
        "the operator's drop": asked(lambda: in_person.drop_scratch(scratch)),
        "the restore login": asked(lambda: in_person.production_integrity("docsuri_v2")),
        "the rollback's outcomes": asked(lambda: cutover.lifecycle_outcomes(NOW)),
        "the rollback's writes": asked(lambda: cutover.v2_writes(NOW)),
        "the migration tool's size read": asked(lambda: migration.database_bytes(imported)),
        "the migration tool's import read": asked(lambda: reading(migration, imported)),
    } == {
        "the scheduler's scratch checks": (*here, "docsuri_scheduler", scratch, scram),
        "the scheduler's drop": (*here, "docsuri_scheduler", "postgres", scram),
        "the operator's disposable login": (*here, "docsuri_operator", scratch, scram),
        "the operator's drop": (*here, "docsuri_operator", "postgres", scram),
        "the restore login": (*here, "docsuri_restore", "docsuri_v2", scram),
        "the rollback's outcomes": (*here, "docsuri_operator", "docsuri_v2", scram),
        "the rollback's writes": (*here, "docsuri_operator", "docsuri_v2", scram),
        "the migration tool's size read": (*here, "docsuri_operator", "postgres", scram),
        "the migration tool's import read": (*here, "docsuri_operator", imported, scram),
    }
