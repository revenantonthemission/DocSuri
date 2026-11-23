"""A restore verification on the composed realm (U8 plan Step 30; BR4.5, BR4.6, BR2.6, BR6.6,
Workflow 6).

The standing scheduler runs it with the realm driver: `platform.database.backup` takes a
live set of `docsuri_u8` onto the realm's stand-in volume, the agent's unattended
`verify` restores it into a new scratch database, the scheduler's database login checks
it (every table present with its rows, the tombstones up to the recorded head replayed,
every tombstoned owner absent) and drops it. The ledger is the test's own, so the
realm's live ledger never changes; the free-disk reading is injected, because the guard
compares numbers and this Mac's own free space is not the test's subject.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.modules.operations.lifecycle import covering_verification
from backend.modules.operations.recovery import RecoveryRequests
from backend.modules.operations.tombstones import Tombstones
from backend.u8_policy import SYNTHETIC_OPERATIONS
from docsuri_ops.u8_platform.recovery_words import realm_procedures
from tests.u8_service_operations_integration import platform_flows as pf
from tests.u8_service_operations_integration import recovery_flows as rf
from tests.u8_service_operations_integration.conftest import Clock

ROOM = 100 * rf.GIB


@pytest.fixture(scope="module")
def setting(tmp_path_factory, realm):
    """One ledger and one live set for the module: each test runs its own request."""
    from uuid import uuid4

    tmp = tmp_path_factory.mktemp("verification")
    clock = Clock()
    ledger = rf.open_ledger(tmp, clock)
    # The realm driver's lone ledger copy copies this module's ledger (Step 90(b)).
    journey = pf.journey(tmp, realm, mode="live", admission="open",
                         ledgerFolder=str(tmp / "operations-ledger"))
    wiring = realm_procedures(journey.profile, ledger, clock=clock, role="scheduler",
                              ready=lambda: True, free_bytes=lambda: ROOM)
    procedures = wiring.procedures
    requests = procedures.requests
    request = requests.request(origin="schedule", operation="backup.create", environment="live",
                               target_id="docsuri_u8", expected_revision=0,
                               submission_id=uuid4())
    requests.admit(request["recoveryRequestId"])
    done = procedures.backup(request["recoveryRequestId"])
    assert done["state"] == "succeeded", done
    backup = next(item for item in ledger.records("backup-set")
                  if item["recoveryRequestId"] == request["recoveryRequestId"])
    yield {"ledger": ledger, "procedures": procedures, "backup": backup, "clock": clock,
           "journey": journey}
    ledger.close()


def verification(setting, **platform):
    """Request, admit and run one verification of the module's set."""
    from uuid import uuid4

    procedures = setting["procedures"]
    for name, value in platform.items():
        setattr(procedures.platform, name, value)
    requests: RecoveryRequests = procedures.requests
    backup = setting["backup"]
    request = requests.request(origin="schedule", operation="restore.verify",
                               environment="live", target_id=backup["backupId"],
                               expected_revision=setting["ledger"].revision("backup-set",
                                                                            backup["backupId"]),
                               submission_id=uuid4())
    requests.admit(request["recoveryRequestId"])
    return procedures.verify(request["recoveryRequestId"])


def result_of(setting, request) -> dict:
    identity = [ref.removeprefix("verification:") for ref in request["evidenceRefs"]
                if ref.startswith("verification:")]
    return setting["ledger"].get("restore-verification", identity[-1])


def test_the_set_and_its_ledger_copy_are_recorded(setting):
    backup = setting["backup"]
    assert backup["integrity"] == "passed" and backup["trigger"] == "scheduled"
    assert backup["databaseIncarnation"].startswith("docsuri_u8:")
    assert backup["sourceDatabaseBytes"] > 0 and backup["stagingRemovedAt"]
    [copy] = [item for item in setting["ledger"].records("ledger-copy")
              if item["backupId"] == backup["backupId"]]
    assert copy["verifiedAt"] and copy["headSequence"] > 0
    assert copy["operatorReceiptRef"] == backup["operatorReceiptRef"]


DAY = 86_400


def seconds_between(record: dict, start: str, end: str) -> float:
    from backend.modules.operations.retained_copies import _parse

    return (_parse(record[end]) - _parse(record[start])).total_seconds()


def open_scratch_copies(ledger, scratch: str) -> list[dict]:
    return [item for item in ledger.records("retained-copy")
            if item["kind"] == "scratch-restore" and "disposedAt" not in item
            and item["locations"] == [f"database/{scratch}"]]


class ScratchRecordedFirst:
    """The realm's operator behind a delegating spy (U8 plan Step 90(b), L1-2): at a
    scratch restore it first asserts what the module's ledger already holds, then
    delegates."""

    def __init__(self, operator, ledger):
        self.operator, self.ledger, self.seen = operator, ledger, []

    def __getattr__(self, name):
        return getattr(self.operator, name)

    def execute(self, operation, target, inputs, *, key, **options):
        if operation == "platform.database.restore" and inputs.get("mode") == "scratch":
            [copy] = open_scratch_copies(self.ledger, inputs["scratchDatabase"])
            assert seconds_between(copy, "createdAt", "disposeAfter") == DAY
            self.seen.append(copy)
        return self.operator.execute(operation, target, inputs, key=key, **options)


def test_an_erased_owner_is_not_revived(setting, sign_in_account):
    authority, _ = sign_in_account("sign-in-member")
    tombstones = Tombstones(setting["ledger"])
    from uuid import uuid4

    tombstones.claim(authority.account_id, uuid4())
    # Without the replay the copy would revive the owner: the check finds it.
    original = setting["procedures"].platform.scratch_checks

    def without_replay(database, accounts):
        checked = original(database, [])
        return {**checked, "surviving": 1 if accounts else 0}

    unreplayed = verification(setting, scratch_checks=without_replay)
    assert unreplayed["state"] == "failed"
    assert result_of(setting, unreplayed)["erasedOwnersSurviving"] == 1
    operator = setting["procedures"].platform.operator
    spy = ScratchRecordedFirst(operator, setting["ledger"])
    try:
        replayed = verification(setting, scratch_checks=original, operator=spy)
    finally:
        setting["procedures"].platform.operator = operator
    assert replayed["state"] == "succeeded", replayed
    record = result_of(setting, replayed)
    assert record["result"] == "verified" and record["erasedOwnersSurviving"] == 0
    assert record["integrity"] == "passed"
    # The scratch copy recorded before the restore is closed by a version citing the
    # verification, at the verification's `scratchRemovedAt`.
    [seen] = spy.seen
    closed = setting["ledger"].get("retained-copy", seen["copyId"])
    assert closed["disposedAt"] == record["scratchRemovedAt"]
    assert closed["disposalVerificationRef"] == f"verification:{record['verificationId']}"
    assert seen["sourceRef"] == f"verification:{record['verificationId']}"


def test_a_failed_day_leaves_one_standalone_ledger_copy_on_the_volume(setting, realm):
    """U8 plan Step 90(b) (L1-5): a day whose scheduled set failed still gets one ledger
    copy of its own, through `platform.ledger.copy`."""
    import datetime as dt

    ledger, procedures = setting["ledger"], setting["procedures"]
    requests: RecoveryRequests = procedures.requests
    operator = procedures.platform.operator
    faulty = rf.FaultyOperator(operator, {("platform.database.backup", ""): 10})
    sets_before = len(ledger.records("backup-set"))
    # The realm's PlatformControl store outlives this module (`restore-paths` runs this
    # file again on the same realm), and the standing copy's key names its Seoul day, so
    # a day whose copy this realm already took would replay that earlier receipt, of
    # another module's ledger. The failed day is therefore the first day from today
    # whose standing copy this realm has not taken; the module's clock is moved to it for
    # this test and moved back afterwards.
    seoul_zone = dt.timezone(dt.timedelta(hours=9))
    days = 0
    while store_rows(realm, setting["journey"], (
            "SELECT 1 FROM platform_control.operation WHERE idempotency_key LIKE %s"),
            (f"standing-ledger-copy:live:"
             f"{(setting['clock']() + dt.timedelta(days=days)).astimezone(seoul_zone):%Y%m%d}%",)):
        days += 1
    setting["clock"].advance(days * 86_400)
    try:
        lone, copy, owner_key = failed_day_copy(setting, realm, requests, procedures,
                                                operator, faulty, sets_before, seoul_zone)
    finally:
        setting["clock"].advance(-days * 86_400)
    # The same day's second call adds none.
    again = procedures.ledger_copy_alone("live", owner_key=owner_key, via="standing")
    assert again["ledgerCopyId"] == copy["ledgerCopyId"]
    assert [item for item in ledger.records("ledger-copy") if "backupId" not in item] == lone


def failed_day_copy(setting, realm, requests, procedures, operator, faulty, sets_before,
                    seoul_zone):
    """The failed scheduled set, then that day's lone ledger copy and its checks."""
    from uuid import uuid4

    from docsuri_ops.backup_agent.catalogue import Catalogue
    from docsuri_ops.backup_agent.config import load

    ledger = setting["ledger"]
    procedures.platform.operator = faulty
    try:
        request = requests.request(origin="schedule", operation="backup.create",
                                   environment="live", target_id="docsuri_u8",
                                   expected_revision=requests.backup_revision("live"),
                                   submission_id=uuid4())
        requests.admit(request["recoveryRequestId"])
        failed = procedures.backup(request["recoveryRequestId"])
    finally:
        procedures.platform.operator = operator
    assert failed["state"] == "failed", failed
    assert any(name == "platform.database.backup" for name, _ in faulty.calls)
    assert len(ledger.records("backup-set")) == sets_before  # no dump was taken

    seoul = setting["clock"]().astimezone(seoul_zone)
    owner_key = f"standing-ledger-copy:live:{seoul:%Y%m%d}"
    head = ledger.head
    copy = procedures.ledger_copy_alone("live", owner_key=owner_key, via="standing")
    lone = [item for item in ledger.records("ledger-copy") if "backupId" not in item]
    assert lone == [ledger.get("ledger-copy", copy["ledgerCopyId"])]
    assert (lone[0]["headSequence"], lone[0]["headDigest"]) == (head.count, head.head)
    assert lone[0]["verifiedAt"]
    facts = ledger.get("receipt-facts", lone[0]["operatorReceiptRef"])
    assert facts["operation"] == "platform.ledger.copy" and facts["outcome"] == "succeeded"
    # The receipt in the realm's PlatformControl store carries the agent's record id.
    [(name, refs)] = store_rows(realm, setting["journey"], (
        "SELECT o.operation_name, r.effect_refs FROM platform_control.operation o JOIN "
        "platform_control.receipt r USING (operation_id) WHERE o.operation_id = %s"),
        (facts["operationId"],))
    assert name == "platform.ledger.copy"
    assert f"fact:recordId={lone[0]['ledgerCopyId']}" in refs
    # The realm agent's own catalogue (it keeps earlier copies too): one written,
    # undisposed file under that record id, found by the id.
    agent = load(Path(setting["journey"].config["agentFolder"]))
    catalogue = Catalogue.open(agent.u8_folder, clock=setting["clock"])
    try:
        files = [item for item in catalogue.files().values()
                 if item.record_id == lone[0]["ledgerCopyId"] and item.state == "written"]
    finally:
        catalogue.close()
    assert len(files) == 1 and (agent.u8_folder / files[0].path).is_file()
    return lone, copy, owner_key


def store_rows(realm, journey, query: str, params: tuple) -> list[tuple]:
    """Rows of PlatformControl's own tables, read as the instance's administrator."""
    import json

    import psycopg

    from backend.local_profile import private_bytes

    password = json.loads(private_bytes(Path(realm.root) / "migration-credentials.json"))[
        "databaseAdminPassword"]
    with psycopg.connect(host="127.0.0.1", port=journey.profile.port,
                         dbname=journey.profile.database, user="postgres", password=password,
                         autocommit=True, connect_timeout=5) as conn:
        return conn.execute(query, params).fetchall()


def test_the_scratch_database_is_dropped_and_its_removal_recorded(setting, realm):
    names = []
    original = setting["procedures"].platform.scratch_name

    def named():
        names.append(original())
        return names[-1]

    done = verification(setting, scratch_name=named)
    assert done["state"] == "succeeded", done
    record = result_of(setting, done)
    assert record["scratchRemovedAt"] >= record["startedAt"]
    assert not rf.database_exists(realm, names[-1])
    setting["procedures"].platform.scratch_name = original
    # The agent's timed HNSW step (Step 62(d), recorded by Step 64(i)) and its projection
    # to the 8 GiB footprint budget (Step 60(d)): ceil(seconds x budget / source bytes).
    seconds = record["hnswRebuildSeconds"]
    assert type(seconds) is int and seconds >= 0
    assert SYNTHETIC_OPERATIONS.footprint_budget_bytes == 8 * 1024**3
    source = setting["ledger"].get("backup-set", record["backupId"])["sourceDatabaseBytes"]
    assert source > 0
    assert record["hnswProjectedSeconds"] == -(-seconds * 8 * 1024**3 // source)


def test_a_failed_drop_becomes_a_retained_copy_and_fails_the_verification(setting, realm):
    original = setting["procedures"].platform.drop_scratch
    kept = []

    def refused(database):
        kept.append(database)
        raise PermissionError("the drop failed")

    try:
        failed = verification(setting, drop_scratch=refused)
    finally:
        setting["procedures"].platform.drop_scratch = original
        for database in kept:
            original(database)
    assert failed["state"] == "failed"
    record = result_of(setting, failed)
    assert record["result"] == "failed" and "scratchRemovedAt" not in record
    [copy] = [item for item in setting["ledger"].records("retained-copy")
              if item["sourceRef"] == f"verification:{record['verificationId']}"]
    assert copy["kind"] == "scratch-restore" and copy["locations"] == [f"database/{kept[0]}"]
    # Its backstop is one day (NFR3.12), and it stays open: the one open copy.
    from backend.modules.operations.retained_copies import _parse

    assert (_parse(copy["disposeAfter"]) - _parse(copy["createdAt"])).total_seconds() == (
        SYNTHETIC_OPERATIONS.scratch_restore_backstop_seconds) == DAY
    assert "disposedAt" not in copy and open_scratch_copies(setting["ledger"], kept[0]) == [copy]
    incidents = [item for item in setting["ledger"].records("service-incident")
                 if "storage.capacity" in item["capabilities"]]
    assert incidents and incidents[-1]["state"] != "resolved"
    # While the kept scratch database is recorded, NFR8.15's one scratch database is
    # taken: the next verification's restore is refused before anything is restored.
    blocked = verification(setting)
    assert blocked["state"] == "failed", blocked
    # The refusal is recorded under its own key, not as a failed restore.
    assert blocked["evidenceRefs"][-1] == "failed:scratch-database-limit", blocked
    refused_at_first_check(setting, blocked)
    # The test removed the kept database itself above (`original(database)`); its copy is
    # disposed on that removal, as the disposal pass disposes it, and the slot is free.
    from backend.modules.operations.retained_copies import RetainedCopies

    removal = rf.receipt("platform.database.remove", "database-scratch",
                         now=setting["clock"]())
    RetainedCopies(setting["ledger"], SYNTHETIC_OPERATIONS,
                   clock=setting["clock"]).disposed(copy["copyId"], removal)
    assert verification(setting)["state"] == "succeeded"


def refused_at_first_check(setting, blocked: dict) -> None:
    """A verification Step 64(d) refused at its first check: its RestoreVerification has
    no `scratchRemovedAt`, and no scratch copy cites it."""
    record = failed_result(setting, blocked)
    assert record is not None and "scratchRemovedAt" not in record
    cited = f"verification:{record['verificationId']}"
    assert not [item for item in setting["ledger"].records("retained-copy")
                if item["kind"] == "scratch-restore" and item["sourceRef"] == cited]


class RestoreFailsAfterCreate:
    """The realm's operator, with the scratch restore failing after its database was
    created, as a pg_restore that fails part-way leaves it: the scratch database is made
    in the realm's instance (owned by the disposable role, as the agent makes it), then
    the restore's receipt is bound failed through U7's injected permission fault. Before
    it, it asserts that the open scratch copy naming that database is already in the
    module's ledger (Step 64(d))."""

    def __init__(self, operator, realm, ledger):
        self.operator, self.realm, self.ledger, self.created = operator, realm, ledger, []

    def __getattr__(self, name):
        return getattr(self.operator, name)

    def execute(self, operation, target, inputs, *, key):
        if operation == "platform.database.restore" and inputs.get("mode") == "scratch":
            from psycopg import sql

            name = inputs["scratchDatabase"]
            assert len(open_scratch_copies(self.ledger, name)) == 1
            with rf.admin(self.realm) as conn:
                conn.execute(sql.SQL("CREATE DATABASE {} OWNER docsuri_disposable "
                                     "TEMPLATE template1").format(sql.Identifier(name)))
            self.created.append(name)
            return self.operator.execute(operation, target, inputs, key=key,
                                         injected_fault="permission")
        return self.operator.execute(operation, target, inputs, key=key)


def failed_result(setting, request) -> dict:
    """A verification that failed before its checks: its record, by the id `verify`
    derives from the request (the failed request carries no `verification:` ref)."""
    from uuid import NAMESPACE_URL, uuid5

    identity = uuid5(NAMESPACE_URL, f"docsuri-verification:{request['recoveryRequestId']}")
    return setting["ledger"].get("restore-verification", str(identity))


def test_a_restore_that_fails_after_creating_the_scratch_database_leaves_none_unrecorded(
    setting, realm,
):
    """The restore fails after its scratch database exists: it is dropped as a finished
    one is, so nothing is left; when that drop fails too, it is recorded as a retained
    copy, so the next verification counts it (NFR8.15) and the disposal pass removes it."""
    from backend.modules.operations.retained_copies import RetainedCopies

    platform = setting["procedures"].platform
    operator, drop = platform.operator, platform.drop_scratch
    failing = RestoreFailsAfterCreate(operator, realm, setting["ledger"])
    kept: list[str] = []
    try:
        failed = verification(setting, operator=failing)
        assert failed["state"] == "failed", failed
        assert failed["evidenceRefs"][-1] == "failed:scratch-restore-failed"
        record = failed_result(setting, failed)
        assert record["result"] == "failed" and "scratchRemovedAt" in record
        assert failing.created and not rf.database_exists(realm, failing.created[-1])
        # Recorded before its restore, closed by its drop (Step 64(d)).
        from docsuri_ops.u8_platform.u8_protocols import recorded_databases

        cited = f"verification:{record['verificationId']}"
        [first] = [item for item in setting["ledger"].records("retained-copy")
                   if item["sourceRef"] == cited]
        assert first["disposedAt"] and first["disposalVerificationRef"] == cited
        assert failing.created[-1] not in recorded_databases(setting["ledger"])()

        def refused(database):
            kept.append(database)
            raise PermissionError("the drop failed")

        failed = verification(setting, operator=failing, drop_scratch=refused)
        assert failed["state"] == "failed", failed
        record = failed_result(setting, failed)
        assert "scratchRemovedAt" not in record
        assert rf.database_exists(realm, kept[-1])  # left in place, and recorded
        [copy] = [item for item in setting["ledger"].records("retained-copy")
                  if item["sourceRef"] == f"verification:{record['verificationId']}"]
        assert copy["kind"] == "scratch-restore" and copy["locations"] == [
            f"database/{kept[-1]}"]
        # After the failed drop, the copy recorded before the restore stays open with its
        # one-day backstop.
        assert "disposedAt" not in copy and seconds_between(
            copy, "createdAt", "disposeAfter") == DAY
        # The next verification counts it: refused before anything is restored.
        blocked = verification(setting, operator=operator, drop_scratch=drop)
        assert blocked["evidenceRefs"][-1] == "failed:scratch-database-limit", blocked
        refused_at_first_check(setting, blocked)
    finally:
        platform.operator, platform.drop_scratch = operator, drop
        for database in kept:
            drop(database)
        for name in failing.created:
            rf.drop_database(realm, name)
    removal = rf.receipt("platform.database.remove", "database-scratch",
                         now=setting["clock"]())
    RetainedCopies(setting["ledger"], SYNTHETIC_OPERATIONS,
                   clock=setting["clock"]).disposed(copy["copyId"], removal)
    assert verification(setting)["state"] == "succeeded"


def test_the_disk_guard_refuses_with_internal_disk_low(setting):
    backup = setting["backup"]
    free = backup["sourceDatabaseBytes"] + 20 * 1024**3
    assert SYNTHETIC_OPERATIONS.internal_disk_threshold_bytes == 20 * 1024**3
    original = setting["procedures"].platform.free_bytes
    try:
        refused = verification(setting, free_bytes=lambda: free)
        # One byte more and the verification runs.
        passed = verification(setting, free_bytes=lambda: free + 1)
    finally:
        setting["procedures"].platform.free_bytes = original
    assert refused["state"] == "refused"
    assert refused["evidenceRefs"] == ["refused:internal-disk-low"]
    assert passed["state"] == "succeeded", passed


def test_the_evidence_covers_the_tombstones_up_to_its_head(setting):
    from uuid import uuid4

    tombstones = Tombstones(setting["ledger"])
    covered = tombstones.claim(uuid4(), uuid4())
    done = verification(setting)
    assert done["state"] == "succeeded", done
    record = result_of(setting, done)
    head = tombstones.verify()
    assert record["registerHeadSequence"] == covered["sequence"] == head["sequence"]
    assert record["registerHeadDigest"] == head["digest"]
    assert covering_verification(setting["ledger"], covered)["registerHeadSequence"] >= (
        covered["sequence"])
    later = tombstones.claim(uuid4(), uuid4())
    covering = covering_verification(setting["ledger"], later)
    assert covering is None


# --- Step 122(e): a running verification stops below the critical floor (L2-8) ------------

CRITICAL_FLOOR = SYNTHETIC_OPERATIONS.internal_disk_critical_bytes


class StoppedBelowTheFloor(RestoreFailsAfterCreate):
    """As `RestoreFailsAfterCreate` (the scratch database made, the restore's receipt
    bound failed through U7's injected fault), answered with the agent's refusal below the
    critical floor, `internal-disk-critical`."""

    def execute(self, operation, target, inputs, *, key):
        receipt = super().execute(operation, target, inputs, key=key)
        if operation == "platform.database.restore" and inputs.get("mode") == "scratch":
            return {**receipt, "refusal": "internal-disk-critical"}
        return receipt


class NotesTheRestore:
    """The realm's operator behind a delegating spy that notes when the scratch restore
    has run (an observer: it answers the operator's own receipt)."""

    def __init__(self, operator):
        self.operator, self.restored = operator, False

    def __getattr__(self, name):
        return getattr(self.operator, name)

    def execute(self, operation, target, inputs, *, key, **options):
        receipt = self.operator.execute(operation, target, inputs, key=key, **options)
        if operation == "platform.database.restore" and inputs.get("mode") == "scratch":
            self.restored = True
        return receipt


def test_a_verification_stopped_below_the_critical_floor_drops_its_scratch_and_records_why(
    setting, realm,
):
    platform = setting["procedures"].platform
    operator, free, checks, scratch_name = (platform.operator, platform.free_bytes,
                                            platform.scratch_checks, platform.scratch_name)
    stopped = StoppedBelowTheFloor(operator, realm, setting["ledger"])
    noting = NotesTheRestore(operator)
    names: list[str] = []
    checked: list[str] = []

    def named():
        names.append(scratch_name())
        return names[-1]

    def spied(database, accounts):
        checked.append(database)
        return checks(database, accounts)

    try:
        # The agent's refusal, settled into the restore's receipt.
        failed = verification(setting, operator=stopped)
        assert failed["state"] == "failed", failed
        assert failed["evidenceRefs"][-1] == "failed:internal-disk-critical"
        record = failed_result(setting, failed)
        assert (record["result"], record["integrity"]) == ("failed", "failed")
        assert "scratchRemovedAt" in record
        assert stopped.created and not rf.database_exists(realm, stopped.created[-1])
        cited = f"verification:{record['verificationId']}"
        [copy] = [item for item in setting["ledger"].records("retained-copy")
                  if item["sourceRef"] == cited]
        assert copy["disposedAt"] and copy["disposalVerificationRef"] == cited
        # The boundary: the floor crossed while the set was restored; no check runs.
        boundary = verification(
            setting, operator=noting, scratch_name=named, scratch_checks=spied,
            free_bytes=lambda: CRITICAL_FLOOR - 1 if noting.restored else ROOM)
        assert boundary["state"] == "failed", boundary
        assert boundary["evidenceRefs"][-1] == "failed:internal-disk-critical"
        assert noting.restored and checked == []
        record = failed_result(setting, boundary)
        assert record["result"] == "failed" and "scratchRemovedAt" in record
        assert not rf.database_exists(realm, names[-1])
    finally:
        platform.operator, platform.free_bytes = operator, free
        platform.scratch_checks, platform.scratch_name = checks, scratch_name
        for name in stopped.created:
            rf.drop_database(realm, name)
    # The next one: the stops left no open scratch copy to block it (NFR8.15).
    assert verification(setting)["state"] == "succeeded"


STAND_IN_AGENT = '''"""A stand-in for the backup agent's realm entry (U8 plan Step 122(e)):
every word answers the agent's refusal below the critical floor and exits 1."""

import json
import sys


def main_realm(argv):
    refusal = {"ok": False, "reason": "internal-disk-critical", "sessionsEnded": 1}
    sys.stdout.write(json.dumps(refusal) + "\\n")
    sys.stdout.flush()
    return 1
'''


def test_the_agents_critical_refusal_reaches_the_receipt_through_the_realm_driver(
    setting, realm, tmp_path,
):
    """L2-8: the realm driver runs the agent's realm entry from its repository folder, so
    a stand-in agent there (found before the repository's own package, `-c` putting the
    working directory first) answers the refusal line; the real chain carries its key to
    the request: the driver's `_agent_result`, the adapter's not-applied settlement, U7's
    settlement and the operator's `refusal`."""
    repository = tmp_path / "stand-in-repository"
    package = repository / "docsuri_ops" / "backup_agent"
    package.mkdir(parents=True)
    (repository / "docsuri_ops" / "__init__.py").write_text("")
    (package / "__init__.py").write_text("")
    (package / "cli.py").write_text(STAND_IN_AGENT)
    journey = pf.journey(tmp_path, realm, mode="live", admission="open",
                         repository=str(repository))
    wiring = realm_procedures(journey.profile, setting["ledger"], clock=setting["clock"],
                              role="scheduler", ready=lambda: True, free_bytes=lambda: ROOM)
    failed = verification({**setting, "procedures": wiring.procedures})
    assert failed["state"] == "failed", failed
    assert failed["evidenceRefs"][-1] == "failed:internal-disk-critical"
    record = failed_result(setting, failed)
    assert (record["result"], record["integrity"]) == ("failed", "failed")
    assert "scratchRemovedAt" in record  # DROP DATABASE IF EXISTS of a name never made
