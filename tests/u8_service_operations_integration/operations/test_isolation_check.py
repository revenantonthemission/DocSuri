"""The runtime isolation check with recorded tool output (U8 plan Step 36; D10, BR6.12,
NFR3.8, NFR7.19, NFR8.10, NFR9.9, security-design § 6.8).

The arrangement is built under the test's own temporary prefix (`ArrangementPaths.under`),
with the test's account standing in for root as the owner of every root-owned file. Every
macOS tool answers from recorded output through `isolation_macos.MacTools`, so the
adapter's parsing and the check's decisions are both exercised; a tool can also be made to
hang, to show the item recorded as unknown and the check ending within its bound.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from docsuri_ops import isolation_check
from docsuri_ops.arrangement.paths import Accounts, ArrangementPaths
from docsuri_ops.isolation_check import BOOT_LABELS, ITEMS, CheckContext, IsolationCheck
from docsuri_ops.isolation_macos import MacTools, parse_otool, rules_digest

NOW = dt.datetime(2026, 10, 23, 1, 0, tzinfo=dt.UTC)
RULES = ("pass in quick on lo0 proto tcp from any to 127.0.0.1 port = 18200 user = 610\n"
         "block return in quick on lo0 proto tcp from any to 127.0.0.1 port = 18200\n")
RUNNING = "system/{label} = {{\n\tactive count = 1\n\tstate = running\n\tpid = 412\n}}\n"
UNLOCKED = ("   Device Identifier:         disk4s1\n   Volume Name:               "
            "DocSuri_Backup\n   FileVault:                 Yes\n   Locked:                    No\n")
LSOF = ("COMMAND  PID     USER   FD   TYPE DEVICE SIZE/OFF NODE NAME\n"
        "postgres  90 _docsuri    7u  IPv4 0x1         0t0  TCP 127.0.0.1:15432 (LISTEN)\n")
OTOOL = ("{path}:\n\t/usr/lib/libSystem.B.dylib (compatibility version 1.0.0, current "
         "version 1345.0.0)\n\t@rpath/libpq.5.dylib (compatibility version 5.0.0, current "
         "version 5.16.0)\n")


class Done:
    def __init__(self, stdout: str, returncode: int = 0, stderr: str = ""):
        self.stdout, self.returncode = stdout.encode(), returncode
        # Step 74(d) found diskutil's missing-volume line on standard error (Step 77(a)).
        self.stderr = stderr.encode()


class Tools:
    """Recorded tool output by command; `answers` replaces the answer of every call whose
    argv starts with a key (consulted before `override`), `override` replaces one tool's
    answer and `hang` makes one tool wait until released. Every call's argv is recorded."""

    def __init__(self, accounts: Accounts):
        self.accounts = accounts
        self.answers: dict[tuple[str, ...], Done] = {}
        self.override: dict[str, Done] = {}
        self.hang: set[str] = set()
        self.release = threading.Event()
        self.calls: list[list[str]] = []
        # Each call's options beyond the ones every tool gets (the run-as account).
        self.options: list[dict] = []
        # The server's answers to `SHOW hba_file` and `SHOW ident_file`: the pinned files.
        self.hba_file = ""
        self.ident_file = ""

    def __call__(self, argv, **options):
        self.calls.append(list(argv))
        self.options.append({key: value for key, value in options.items()
                             if key not in ("capture_output", "timeout", "check")})
        tool = Path(argv[0]).name
        if tool in self.hang:
            self.release.wait(10)
        for prefix in sorted(self.answers, key=len, reverse=True):
            if tuple(argv[:len(prefix)]) == prefix:
                return self.answers[prefix]
        if tool in self.override:
            return self.override[tool]
        if tool == "launchctl":
            if argv[1] == "print-disabled":
                return Done('disabled services = {\n\t"org.docsuri.v2.host" => enabled\n}\n')
            return Done(RUNNING.format(label=argv[2].split("/", 1)[1]))
        if tool == "pfctl":
            return Done(RULES if "-a" in argv else "Status: Enabled for 0 days 01:02:03\n")
        if tool == "diskutil":
            return Done(UNLOCKED)
        if tool == "tmutil":
            return Done(f"[Excluded]    {argv[2]}\n")
        if tool == "otool":
            if argv[2].endswith("docsuri-ledger"):
                return Done(f"{argv[2]}: is not an object file\n", 1)
            return Done(OTOOL.format(path=argv[2]))
        if tool == "lsof":
            return Done(LSOF)
        if tool == "psql":
            return Done(f"{self.ident_file if argv[-1] == 'SHOW ident_file' else self.hba_file}\n")
        if tool == "dscl":
            name = argv[3].rsplit("/", 1)[1]
            account = next(item for item in (self.accounts.service, self.accounts.scheduler,
                                             self.accounts.database, self.accounts.models,
                                             self.accounts.tunnel, self.accounts.backup)
                           if item.name == name)
            return Done(f"UniqueID: {account.uid}\nUserShell: /usr/bin/false\n")
        raise AssertionError(argv)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Arrangement:
    def __init__(self, tmp_path: Path):
        self.paths = ArrangementPaths.under(tmp_path / "prefix")
        self.accounts = Accounts.for_tests()
        self.tools = Tools(self.accounts)
        self.hba = self.paths.postgres_rules / "pg_hba.conf"
        self.ident = self.paths.postgres_rules / "pg_ident.conf"
        self.tools.hba_file, self.tools.ident_file = str(self.hba), str(self.ident)
        self.etc = tmp_path / "etc"
        self.program = self.paths.release / "ops/bin/docsuri-ledger"
        self.runtime = self.paths.runtimes / "postgresql-16.14/bin/postgres"
        self.anchor = self.etc / "pf.anchors/org.docsuri.v2"
        self.sudoers = self.etc / "sudoers.d/docsuri"
        for path, text in (
            (self.program, f"#!{self.paths.release / '.venv/bin/python'} -I\nprint('x')\n"),
            (self.runtime, "machine code"), (self.anchor, RULES),
            (self.sudoers, "Defaults timestamp_timeout=0\n"),
            (self.hba, "host all all 127.0.0.1/32 scram-sha-256\n"),
            (self.ident, "docsuri_superuser _docsuri_v2_db postgres\n"),
            (self.paths.postgres_data / "PG_VERSION", "16\n"),
        ):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        self.write_manifest()
        self.check_context = CheckContext(
            paths=self.paths, accounts=self.accounts, tools=MacTools(self.tools),
            clock=lambda: NOW, owner_uid=os.getuid())

    def write_manifest(self) -> None:
        manifest = {"version": 1, "files": [
            {"path": "release/ops/bin/docsuri-ledger", "kind": "program",
             "sha256": sha(self.program)},
            {"path": "runtimes/postgresql-16.14/bin/postgres", "kind": "program",
             "sha256": sha(self.runtime), "root": "runtimes/postgresql-16.14"},
            {"path": str(self.anchor), "kind": "rule", "sha256": sha(self.anchor)},
            {"path": str(self.sudoers), "kind": "rule", "sha256": sha(self.sudoers)},
        ], "pgHbaSha256": sha(self.hba), "pgIdentSha256": sha(self.ident),
            "filterRulesSha256": rules_digest(RULES)}
        self.paths.control.mkdir(parents=True, exist_ok=True)
        (self.paths.control / "arrangement-manifest.json").write_text(json.dumps(manifest))

    def amend_manifest(self, change) -> None:
        """The recorded manifest, changed in place by `change(manifest)` (Step 77(a))."""
        path = self.paths.control / "arrangement-manifest.json"
        manifest = json.loads(path.read_bytes())
        change(manifest)
        path.write_text(json.dumps(manifest))

    def run(self) -> dict:
        return IsolationCheck(self.check_context).run()


def items(result: dict) -> dict:
    return {item["item"]: item for item in result["items"]}


@pytest.fixture
def arrangement(tmp_path) -> Arrangement:
    return Arrangement(tmp_path)


def test_every_item_passes_on_the_installed_arrangement(arrangement):
    result = arrangement.run()
    assert [item["item"] for item in result["items"]] == list(ITEMS)
    assert result["passed"] is True, result["items"]
    assert result["stopRecords"] == [] and result["changeInProgress"] is False
    assert len(result["digest"]) == 64 and result["checkedAt"] == NOW.isoformat()


FAILURES = {
    "programs": ("otool", Done("x:\n\t/opt/homebrew/lib/libssl.3.dylib (compat)\n"),
                 "program-loads-outside"),
    "accounts": ("dscl", Done("UniqueID: 610\nUserShell: /bin/zsh\n"), "account-can-log-in"),
    "database": ("lsof", Done(LSOF.replace("127.0.0.1:15432", "*:15432")),
                 "database-listens-beyond-loopback"),
    "filter": ("pfctl", Done("Status: Disabled\n"), "filter-disabled"),
    "volume": ("diskutil", Done(UNLOCKED.replace("Locked:                    No",
                                                 "Locked:                    Yes")),
               "volume-locked"),
    "backups": ("tmutil", Done("[Included]    /Library/DocSuri/\n"), "isolation-backups"),
    "boot": ("launchctl", Done("system/x = {\n\tstate = not running\n}\n"), "boot-item-lapsed"),
}


@pytest.mark.parametrize("item", sorted(FAILURES))
def test_each_item_fails_on_its_own_fixture_and_names_itself(arrangement, item):
    tool, answer, reason = FAILURES[item]
    arrangement.tools.override[tool] = answer
    result = arrangement.run()
    found = items(result)
    assert found[item] == {"item": item, "passed": False, "reason": reason}
    assert result["passed"] is False
    others = {name for name, value in found.items() if not value["passed"]} - {item}
    # pfctl answers both filter calls; an otool answer of another program's libraries
    # stays within the programs item.
    assert others <= ({"filter"} if tool == "pfctl" else set())


def test_a_changed_program_or_rule_file_fails_its_item(arrangement):
    original = arrangement.program.read_text()
    arrangement.program.write_text(original + "print('replaced')\n")
    assert items(arrangement.run())["programs"]["reason"] == "program-digest"
    arrangement.write_manifest()  # the installer recorded the new program
    arrangement.sudoers.write_text("ALL ALL=(ALL) NOPASSWD: ALL\n")
    found = items(arrangement.run())
    assert found["programs"]["passed"] is True
    assert found["files"] == {"item": "files", "passed": False, "reason": "file-differs"}
    arrangement.hba.write_text("host all all 0.0.0.0/0 trust\n")
    assert items(arrangement.run())["database"]["reason"] == "database-hba-differs"


def test_a_hung_item_is_unknown_and_the_check_ends_within_its_bound(arrangement):
    arrangement.tools.hang.add("tmutil")
    arrangement.check_context.item_seconds = {**isolation_check.ITEM_SECONDS, "backups": 0.3}
    started = time.monotonic()
    result = arrangement.run()
    elapsed = time.monotonic() - started
    arrangement.tools.release.set()
    assert items(result)["backups"] == {"item": "backups", "passed": False,
                                        "reason": "item-timed-out"}
    assert elapsed < 5 and result["durationMs"] < 5000
    assert isolation_check.TOTAL_SECONDS == 60
    assert all(value["passed"] for name, value in items(result).items() if name != "backups")


def test_every_item_hanging_still_ends_within_sixty_seconds(arrangement, monkeypatch):
    """U8 plan Step 67(h): every item hangs. The threads are stand-ins that never run and
    whose `join(limit)` advances the injected clock by `limit`, so no real wait happens:
    programs take 40 s, files the remaining 20 s, and every later item 0 s."""
    moment = {"now": NOW}

    class Hanging:
        def __init__(self, *, target, name, daemon):
            self.name = name

        def start(self) -> None:
            return None

        def join(self, limit: float) -> None:
            moment["now"] += dt.timedelta(seconds=limit)

        def is_alive(self) -> bool:
            return True

    monkeypatch.setattr(isolation_check, "threading", SimpleNamespace(Thread=Hanging))
    monkeypatch.setattr(isolation_check, "_now", lambda: moment["now"])
    assert arrangement.check_context.item_seconds == isolation_check.ITEM_SECONDS
    result = arrangement.run()
    assert [(item["item"], item["passed"], item["reason"]) for item in result["items"]] == [
        (name, False, "item-timed-out") for name in ITEMS]
    assert result["durationMs"] == 60_000
    assert moment["now"] - NOW == dt.timedelta(seconds=60)
    assert isolation_check.TOTAL_SECONDS == 60


def test_a_removed_time_machine_exclusion_fails_isolation_backups(arrangement):
    arrangement.tools.override["tmutil"] = Done("[Included]    /Users/x/Group Containers/\n")
    assert items(arrangement.run())["backups"]["reason"] == "isolation-backups"


def stop_record(arrangement, label: str, *, expires: dt.datetime | None = None,
                body: str | None = None, mode: int = 0o644) -> Path:
    path = arrangement.paths.control_stops / f"{label}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    stopped = NOW - dt.timedelta(days=1)
    value = {"label": label, "receiptId": "7f9c2ba4-e88f-4f6a-9fd1-0b6c1e8f7a10",
             "stoppedAt": stopped.isoformat(),
             "expiresAt": (expires or stopped + dt.timedelta(days=14)).isoformat()}
    path.write_text(body if body is not None else json.dumps(value))
    path.chmod(mode)
    return path


RECEIPT = "7f9c2ba4-e88f-4f6a-9fd1-0b6c1e8f7a10"


class Receipts:
    """The ledger component's receipt reader over the receipts a case states."""

    def __init__(self, *held: dict):
        self.held = {receipt["operationId"]: receipt for receipt in held}
        self.asked: list[str] = []

    def read(self, operation_id: str) -> dict:
        from backend.modules.operations.ledger_cli import ReceiptUnavailable

        self.asked.append(operation_id)
        if operation_id not in self.held:
            raise ReceiptUnavailable("no receipt")
        return self.held[operation_id]


def service_receipt(label: str, *, outcome: str = "succeeded",
                    operation: str = "platform.service.control", action: str = "stop",
                    recorded: dt.datetime | None = None) -> dict:
    """A receipt as `ReceiptReader.read` answers it: by default a succeeded stop of
    `label`, recorded a second before `stop_record`'s `stoppedAt`."""
    from docsuri_ops.u8_platform.drivers import input_hash

    moment = recorded or NOW - dt.timedelta(days=1, seconds=1)
    return {"operationId": RECEIPT, "receiptId": "r-1", "targetId": label,
            "inputHash": input_hash({"label": label, "action": action}),
            "outcome": outcome, "operation": operation, "recordedAt": moment.isoformat()}


def test_a_valid_stop_record_covers_its_stopped_job(arrangement):
    label = "org.docsuri.v2.host"
    stop_record(arrangement, label)
    arrangement.tools.override["launchctl"] = Done("system/x = {\n\tstate = not running\n}\n")
    arrangement.check_context.boot_labels = (label,)
    reader = Receipts(service_receipt(label))
    arrangement.check_context.receipt_held = isolation_check.receipt_held_by(reader)
    result = arrangement.run()
    assert items(result)["boot"]["passed"] is True
    # NFR9.9: each stop record keeps its expiry, in the result and in the file it writes.
    stopped = NOW - dt.timedelta(days=1)
    expected = [{"label": label, "receiptId": RECEIPT, "stoppedAt": stopped.isoformat(),
                 "expiresAt": (stopped + dt.timedelta(days=14)).isoformat()}]
    assert result["stopRecords"] == expected
    written = IsolationCheck(arrangement.check_context).write_result(result)
    assert json.loads(written.read_text())["stopRecords"] == expected
    assert reader.asked == [RECEIPT]


@pytest.mark.parametrize("case", ["a-start", "another-labels-stop", "recorded-after-the-stop",
                                  "no-recorded-time", "a-naive-recorded-time",
                                  "an-old-receipt-fresh-dates"])
def test_a_stop_record_is_planned_only_by_a_stop_of_its_label_recorded_before_it(
        arrangement, case):
    """The review's fix of 2026-10-26: the receipt must be a stop of the record's own label
    (its bound input's hash), recorded no later than the record's `stoppedAt` (within the
    named clock skew). A start receipt, a stop of another label under this label's target,
    or a receipt recorded after the record's stop time plans nothing."""
    from docsuri_ops.u8_platform.drivers import input_hash

    label = "org.docsuri.v2.host"
    stop_record(arrangement, label)
    arrangement.tools.override["launchctl"] = Done("system/x = {\n\tstate = not running\n}\n")
    arrangement.check_context.boot_labels = (label,)
    stopped = NOW - dt.timedelta(days=1)
    receipt = {
        "a-start": service_receipt(label, action="start"),
        "another-labels-stop": {**service_receipt(label), "inputHash": input_hash(
            {"label": "org.docsuri.v2.workers", "action": "stop"})},
        "recorded-after-the-stop": service_receipt(
            label, recorded=stopped + isolation_check.RECEIPT_CLOCK_SKEW
            + dt.timedelta(seconds=1)),
        "no-recorded-time": {**service_receipt(label), "recordedAt": None},
        "a-naive-recorded-time": {**service_receipt(label),
                                  "recordedAt": stopped.replace(tzinfo=None).isoformat()},
        # The planted case (the review's fix of 2026-10-26): an old stop receipt of the
        # same label, cited by a record with fresh dates, bound before the window opens.
        "an-old-receipt-fresh-dates": service_receipt(
            label, recorded=stopped - isolation_check.SERVICE_CONTROL_DEADLINE
            - isolation_check.RECEIPT_CLOCK_SKEW - dt.timedelta(seconds=1)),
    }[case]
    arrangement.check_context.receipt_held = isolation_check.receipt_held_by(Receipts(receipt))
    result = arrangement.run()
    assert items(result)["boot"]["reason"] == "boot-item-lapsed"
    assert result["stopRecords"] == []
    # At either edge of the window, the same stop is planned.
    record = {"receiptId": RECEIPT, "label": label, "stoppedAt": stopped.isoformat()}
    for edge in (stopped + isolation_check.RECEIPT_CLOCK_SKEW,
                 stopped - isolation_check.SERVICE_CONTROL_DEADLINE
                 - isolation_check.RECEIPT_CLOCK_SKEW):
        within = service_receipt(label, recorded=edge)
        assert isolation_check.receipt_held_by(Receipts(within))(record) is True


def test_the_windows_deadline_is_the_service_controls_own():
    """The window's lower bound is `platform.service.control`'s deadline as the inventory
    names it, so the two cannot drift apart."""
    from docsuri_ops.u8_platform.u8_protocols import load_revision

    protocol = load_revision().by_name("platform.service.control")
    assert isolation_check.SERVICE_CONTROL_DEADLINE == dt.timedelta(
        seconds=protocol.deadline_seconds)


@pytest.mark.parametrize("case", ["not-held", "failed", "another-label", "another-operation",
                                  "no-reader", "store-unreadable"])
def test_a_stop_record_whose_receipt_the_store_does_not_hold_is_not_planned(arrangement, case):
    """The person's decision of 2026-10-25 ("Add an in-person stop command"): a stop
    record counts as planned only when the platform store holds its receipt, a succeeded
    `platform.service.control` on its own label; otherwise the stopped job is a lapse."""
    label = "org.docsuri.v2.host"
    stop_record(arrangement, label)
    arrangement.tools.override["launchctl"] = Done("system/x = {\n\tstate = not running\n}\n")
    arrangement.check_context.boot_labels = (label,)
    held = {"not-held": Receipts(), "failed": Receipts(service_receipt(label, outcome="failed")),
            "another-label": Receipts(service_receipt("org.docsuri.v2.workers")),
            "another-operation": Receipts(service_receipt(
                label, operation="platform.isolation.check")),
            "no-reader": None}
    if case == "store-unreadable":
        def unreadable(record):
            raise OSError("store gone")

        arrangement.check_context.receipt_held = unreadable
    else:
        arrangement.check_context.receipt_held = isolation_check.receipt_held_by(held[case])
    result = arrangement.run()
    assert items(result)["boot"] == {"item": "boot", "passed": False,
                                     "reason": "boot-item-lapsed"}
    assert result["stopRecords"] == []


def test_without_a_reader_binding_production_holds_no_stop(arrangement):
    """Production's default reads the service account's reader binding; with none
    installed, no stop record is planned (fail closed)."""
    label = "org.docsuri.v2.host"
    stop_record(arrangement, label)
    arrangement.tools.override["launchctl"] = Done("system/x = {\n\tstate = not running\n}\n")
    arrangement.check_context.boot_labels = (label,)
    held = isolation_check.production_receipt_held(
        arrangement.paths, owner_uid=arrangement.accounts.service.uid)
    assert held({"receiptId": RECEIPT, "label": label}) is False
    # A binding with a looser mode, or another owner than the service account, is refused
    # by the root-run read, so it plans nothing either.
    binding = arrangement.paths.profile / "platform-reader.json"
    binding.parent.mkdir(parents=True, exist_ok=True)
    binding.write_text(json.dumps({"authorityId": "7f9c2ba4-e88f-4f6a-9fd1-0b6c1e8f7a10",
                                   "actor": "_docsuri_v2",
                                   "password": os.urandom(8).hex()}))  # per run (L1-36)
    binding.chmod(0o644)
    assert isolation_check.production_receipt_held(
        arrangement.paths, owner_uid=os.getuid())({"receiptId": RECEIPT, "label": label}) is False
    binding.chmod(0o600)
    assert isolation_check.production_receipt_held(
        arrangement.paths, owner_uid=os.getuid() + 1)({"receiptId": RECEIPT,
                                                       "label": label}) is False
    assert items(arrangement.run())["boot"]["reason"] == "boot-item-lapsed"


@pytest.mark.parametrize("case", ["malformed", "not-roots", "past-its-bound"])
def test_a_stop_record_that_is_malformed_not_roots_or_past_its_bound_is_a_lapse(arrangement,
                                                                                case):
    label = "org.docsuri.v2.host"
    if case == "malformed":
        stop_record(arrangement, label, body="{not json")
    elif case == "not-roots":
        stop_record(arrangement, label, mode=0o666)  # another account could rewrite it
    else:
        stop_record(arrangement, label, expires=NOW - dt.timedelta(minutes=1))
    arrangement.check_context.boot_labels = (label,)
    result = arrangement.run()
    assert items(result)["boot"]["reason"] == "boot-item-lapsed"
    assert result["stopRecords"] == []


def marker(arrangement, started: dt.datetime) -> None:
    (arrangement.paths.control / "arrangement-in-progress.json").write_text(json.dumps(
        {"startedAt": started.isoformat(), "reason": "installer-phase"}))


def test_an_in_progress_marker_reports_a_change_and_an_old_one_covers_nothing(arrangement):
    arrangement.sudoers.write_text("changed by the installer\n")
    marker(arrangement, NOW - dt.timedelta(minutes=30))
    result = arrangement.run()
    assert items(result)["files"]["passed"] is True and result["changeInProgress"] is True
    marker(arrangement, NOW - dt.timedelta(minutes=61))
    result = arrangement.run()
    assert items(result)["files"]["reason"] == "file-differs"
    assert result["changeInProgress"] is False


def test_results_are_written_for_every_account_and_kept_14_days(arrangement):
    from docsuri_ops.arrangement.phases import FOLDERS

    # Step 77(c): the results' fixed folder, root-owned and readable by every account.
    assert ArrangementPaths().isolation_evidence == Path("/Library/DocSuri/evidence/isolation")
    assert ("evidence/isolation", "root", 0o755) in FOLDERS
    check = IsolationCheck(arrangement.check_context)
    result = check.run()
    written = check.write_result(result)
    assert written.name == "20261023T010000Z.json"
    assert oct(written.stat().st_mode & 0o777) == "0o644"
    assert json.loads(written.read_bytes())["resultId"] == result["resultId"]
    folder = arrangement.paths.isolation_evidence
    (folder / "20261008T005959Z.json").write_text("{}")  # 15 days old
    (folder / "20261010T000000Z.json").write_text("{}")  # 13 days old
    (folder / "notes.txt").write_text("not a result")
    assert check.prune() == ["20261008T005959Z.json"]
    assert sorted(path.name for path in folder.iterdir()) == [
        "20261010T000000Z.json", "20261023T010000Z.json", "notes.txt"]


def test_the_otool_result_is_kept_per_program_digest(arrangement):
    original = arrangement.program.read_text()
    arrangement.run()
    cache = json.loads((arrangement.paths.control / "isolation-otool.json").read_bytes())
    assert cache[sha(arrangement.runtime)][0] == "/usr/lib/libSystem.B.dylib"
    assert cache[sha(arrangement.program)] is None  # a script: its interpreter is checked
    arrangement.program.write_text("#!/opt/homebrew/bin/python3\n")
    arrangement.write_manifest()
    assert items(arrangement.run())["programs"]["reason"] == "program-loads-outside"
    arrangement.program.write_text(original)
    arrangement.write_manifest()
    calls = []
    arrangement.tools.override["otool"] = Done("")
    original = arrangement.tools.__call__

    def counting(argv, **options):
        calls.append(argv[0])
        return original(argv, **options)

    arrangement.check_context.tools = MacTools(counting)
    assert items(arrangement.run())["programs"]["passed"] is True
    assert "/usr/bin/otool" not in calls  # both digests were cached


DOCSURI = "/Library/DocSuri/"
ORBSTACK = "/Users/revenantonthemission/Library/Group Containers/HUAQ24HBR6.dev.orbstack/"
TMUTIL = "/usr/bin/tmutil"


def failure_cases() -> list[tuple[str, str, object, str]]:
    """Step 77(a)'s table: (item, case, set-up, reason), one case per way an item fails."""
    true = Path("/usr/bin/true")

    def system_program(arrangement: Arrangement) -> None:
        # A real program, root-owned in a root-owned folder, with its real digest: so it
        # fails on its owner alone (the check's owner here is the test's account).
        info, folder = true.lstat(), true.parent.lstat()
        assert (info.st_uid, folder.st_uid) == (0, 0)
        assert not (info.st_mode | folder.st_mode) & 0o022
        arrangement.amend_manifest(lambda manifest: manifest["files"].append(
            {"path": str(true), "kind": "program", "sha256": sha(true)}))

    def rule_owner(arrangement: Arrangement) -> None:
        def change(manifest: dict) -> None:
            for entry in manifest["files"]:
                if entry["path"] == str(arrangement.sudoers):
                    entry["ownerUid"] = os.getuid() + 1

        arrangement.amend_manifest(change)

    def config_changed(arrangement: Arrangement) -> None:
        config = arrangement.paths.postgres_data / "postgresql.conf"
        config.write_text("listen_addresses = '127.0.0.1'\n")
        arrangement.amend_manifest(lambda manifest: manifest["files"].append(
            {"path": "postgres/data/postgresql.conf", "kind": "config", "sha256": sha(config)}))
        assert items(arrangement.run())["files"]["passed"] is True  # accepted as recorded
        config.write_text("listen_addresses = '*'\n")

    def answer(prefix: tuple[str, ...], done: Done):
        def set_up(arrangement: Arrangement) -> None:
            arrangement.tools.answers[prefix] = done

        return set_up

    def psql(done: Done):
        def set_up(arrangement: Arrangement) -> None:
            arrangement.tools.override["psql"] = done

        return set_up

    return [
        ("programs", "a system program", system_program, "program-custody"),
        ("programs", "the ledger program at 0666", lambda a: a.program.chmod(0o666),
         "program-custody"),
        ("programs", "the ledger's folder at 0777", lambda a: a.program.parent.chmod(0o777),
         "program-custody"),
        ("files", "the sudoers rules at 0666", lambda a: a.sudoers.chmod(0o666),
         "file-differs"),
        ("files", "a rule of another owner", rule_owner, "file-differs"),
        ("files", "a changed configuration", config_changed, "file-differs"),
        ("accounts", "dscl exits 1", answer(("/usr/bin/dscl",), Done("", 1)),
         "account-missing"),
        ("accounts", "another UID", answer(("/usr/bin/dscl",), Done(
            "UniqueID: 999\nUserShell: /usr/bin/false\n")), "account-uid-differs"),
        ("database", "lsof prints nothing", answer(("/usr/sbin/lsof",), Done("", 1)),
         "database-not-listening"),
        ("database", "psql refused", psql(Done("", 2)), "database-hba-file-differs"),
        ("database", "another rule file in force", psql(Done("/tmp/trust/pg_hba.conf\n")),
         "database-hba-file-differs"),
        ("database", "a relative answer", psql(Done("pg_hba.conf\n")),
         "database-hba-file-differs"),
        ("filter", "other rules loaded", answer(
            ("/sbin/pfctl", "-a", "com.apple/org.docsuri.v2", "-s", "rules"),
            Done("pass in quick on lo0 all\n")), "filter-rules-differ"),
        ("volume", "diskutil prints garbage", answer(("/usr/sbin/diskutil",), Done("garbage")),
         "volume-unreadable"),
        ("backups", "only OrbStack included", answer((TMUTIL, "isexcluded", ORBSTACK), Done(
            f"[Included]    {ORBSTACK}\n")), "isolation-backups"),
        ("boot", "the host disabled", answer(("/bin/launchctl", "print-disabled", "system"), Done(
            'disabled services = {\n\t"org.docsuri.v2.host" => disabled\n}\n')),
         "boot-item-lapsed"),
    ]


def test_every_way_each_item_can_fail_names_itself(tmp_path):
    """Step 77(a): in each case only the named item fails, with exactly that reason."""
    assert os.getuid() != 0
    assert "org.docsuri.v2.host" in BOOT_LABELS
    for index, (item, case, set_up, reason) in enumerate(failure_cases()):
        arrangement = Arrangement(tmp_path / f"case-{index}")
        set_up(arrangement)
        result = arrangement.run()
        found = items(result)
        assert found[item] == {"item": item, "passed": False, "reason": reason}, case
        assert [name for name, value in found.items() if not value["passed"]] == [item], case
        assert result["passed"] is False, case
    # A missing volume is no failure: the item, and the whole check, pass.
    missing = Arrangement(tmp_path / "missing-volume")
    missing.tools.answers[("/usr/sbin/diskutil",)] = Done(
        "Could not find disk: DocSuri_Backup\n", 1)
    result = missing.run()
    assert items(result)["volume"] == {"item": "volume", "passed": True}
    assert result["passed"] is True
    assert ["/usr/sbin/diskutil", "info", "DocSuri_Backup"] in missing.tools.calls


def test_a_missing_volume_on_standard_error_reads_absent(arrangement):
    """Step 77(a), as Step 74(d) found: `diskutil info` writes a missing volume's line to
    standard error with exit 1."""
    seen: list[list[str]] = []
    line = "Could not find disk: DocSuri_Backup\n"

    def run(argv, **options):
        seen.append(list(argv))
        return Done("", 1, stderr=line)

    assert MacTools(run).volume("DocSuri_Backup") == {"present": False}
    assert seen == [["/usr/sbin/diskutil", "info", "DocSuri_Backup"]]
    # Standard error is read only on exit 1: the same line with exit 0 is unreadable.
    assert MacTools(lambda argv, **options: Done("", 0, stderr=line)).volume(
        "DocSuri_Backup") is None
    arrangement.tools.answers[("/usr/sbin/diskutil", "info")] = Done("", 1, stderr=line)
    result = arrangement.run()
    assert items(result)["volume"] == {"item": "volume", "passed": True}
    assert result["passed"] is True


def test_each_time_machine_exclusion_alone_fails_isolation_backups(tmp_path):
    """Step 77(b)."""
    from backend.modules.operations.producers import IsolationProducer, Observed

    passing = Arrangement(tmp_path / "passing")
    assert passing.run()["passed"] is True
    assert [argv for argv in passing.tools.calls if argv[0] == TMUTIL] == [
        [TMUTIL, "isexcluded", DOCSURI], [TMUTIL, "isexcluded", ORBSTACK]]
    answers = {"included": lambda path: Done(f"[Included]    {path}\n"),
               "exit-1": lambda path: Done("", 1),
               "unparsable": lambda path: Done(f"Excluded? {path}\n")}
    for index, (path, other) in enumerate(((DOCSURI, ORBSTACK), (ORBSTACK, DOCSURI))):
        for name, answer in answers.items():
            arrangement = Arrangement(tmp_path / f"{name}-{index}")
            arrangement.tools.answers[(TMUTIL, "isexcluded", path)] = answer(path)
            arrangement.tools.answers[(TMUTIL, "isexcluded", other)] = Done(
                f"[Excluded]    {other}\n")
            check = IsolationCheck(arrangement.check_context)
            result = check.run()
            found = items(result)
            assert found["backups"] == {"item": "backups", "passed": False,
                                        "reason": "isolation-backups"}, (path, name)
            assert [item for item, value in found.items() if not value["passed"]] == [
                "backups"], (path, name)
            check.write_result(result)
            assert IsolationProducer(arrangement.paths.isolation_evidence).observe(NOW) == (
                Observed("unavailable", "runtime-isolation-lapsed", ("isolation-backups",),
                         observed_at=NOW)), (path, name)


def test_the_database_hba_is_read_only_through_its_folders_descriptors(tmp_path):
    """Your answer of 2026-11-10 ("Fix both and sweep the rest"): the database account
    owns `postgres/` and `postgres/data`. With `postgres/data` renamed and a link to a
    folder holding the recorded `pg_hba.conf` put in its place, the check never reads
    the recorded copy (a by-path read would, and would pass); a link at the file's own
    name is refused too. The real folder's file is read."""
    from docsuri_ops.isolation_check import _digest, _digest_within

    prefix = tmp_path / "prefix"
    data = prefix / "postgres" / "data"
    data.mkdir(parents=True)
    hba = data / "pg_hba.conf"
    hba.write_bytes(b"host all all 0.0.0.0/0 trust\n")
    pristine = tmp_path / "pristine"
    pristine.mkdir()
    (pristine / "pg_hba.conf").write_bytes(b"local all all peer\n")
    recorded = hashlib.sha256(b"local all all peer\n").hexdigest()
    assert _digest_within(prefix, hba) == hashlib.sha256(
        b"host all all 0.0.0.0/0 trust\n").hexdigest()
    real = prefix / "postgres" / "real-data"
    data.rename(real)
    data.symlink_to(pristine)
    assert _digest(hba) == recorded  # what a by-path read would have compared
    assert _digest_within(prefix, hba) is None
    data.unlink()
    real.rename(data)
    hba.unlink()
    hba.symlink_to(pristine / "pg_hba.conf")
    assert _digest_within(prefix, hba) is None
    outside = tmp_path / "system-root" / "rule"
    outside.parent.mkdir()
    outside.write_bytes(b"rule\n")
    assert _digest_within(prefix, outside) == hashlib.sha256(b"rule\n").hexdigest()


def test_the_database_and_files_items_never_pass_on_a_decoy_behind_a_link(tmp_path):
    """The review of the sweep (2026-11-10): `IsolationCheck.database()` and `files()`
    themselves, not only their helper. With `postgres/data` swapped for a link to a folder
    holding the recorded copy of `postgresql.conf` (so a by-path read would pass it),
    `files` fails with `file-differs`. Since your answer of 2026-11-11 ("Map the login, root
    rules") the rule files are in the root-owned `postgres-rules`: that folder swapped for a
    link to the recorded copies fails `database` with `database-rules-folder-custody`; a
    second name of the recorded copy at `pg_hba.conf` fails with `database-hba-differs`, a
    link at it with `database-rule-file-custody`, and a manifest whose `pgHbaSha256` is
    absent fails too, the real file in place (no read may match a missing digest)."""
    arrangement = Arrangement(tmp_path / "case")
    data, rules = arrangement.paths.postgres_data, arrangement.paths.postgres_rules
    config = data / "postgresql.conf"
    config.write_text("listen_addresses = '127.0.0.1'\n")
    arrangement.amend_manifest(lambda manifest: manifest["files"].append(
        {"path": "postgres/data/postgresql.conf", "kind": "config", "sha256": sha(config)}))
    assert {name: value["passed"] for name, value in items(arrangement.run()).items()
            if name in ("database", "files")} == {"database": True, "files": True}
    pristine = tmp_path / "pristine"
    pristine.mkdir()
    for folder, name in ((rules, "pg_hba.conf"), (rules, "pg_ident.conf"),
                         (data, "postgresql.conf")):
        (pristine / name).write_bytes((folder / name).read_bytes())
    arrangement.hba.write_text("host all all 0.0.0.0/0 trust\n")
    config.write_text("listen_addresses = '*'\n")
    real_data, real_rules = data.parent / "real-data", rules.parent / "real-rules"
    data.rename(real_data)
    data.symlink_to(pristine)
    rules.rename(real_rules)
    rules.symlink_to(pristine)
    found = items(arrangement.run())
    assert found["database"] == {"item": "database", "passed": False,
                                 "reason": "database-rules-folder-custody"}
    assert found["files"] == {"item": "files", "passed": False, "reason": "file-differs"}
    data.unlink()
    real_data.rename(data)
    rules.unlink()
    real_rules.rename(rules)
    arrangement.hba.unlink()
    os.link(pristine / "pg_hba.conf", arrangement.hba)
    assert items(arrangement.run())["database"]["reason"] == "database-hba-differs"
    arrangement.hba.unlink()
    arrangement.hba.symlink_to(pristine / "pg_hba.conf")
    assert items(arrangement.run())["database"]["reason"] == "database-rule-file-custody"
    arrangement.hba.unlink()
    arrangement.hba.write_bytes((pristine / "pg_hba.conf").read_bytes())
    assert items(arrangement.run())["database"]["passed"] is True
    arrangement.amend_manifest(lambda manifest: manifest.update(pgHbaSha256=None))
    assert items(arrangement.run())["database"]["reason"] == "database-hba-differs"


def test_the_database_item_holds_the_server_to_the_pinned_hba_file(tmp_path):
    """Your answer of 2026-11-11 ("Pin them on the command line"): the database account
    writes `hba_file` into `postgresql.auto.conf`, naming a trust file of its own, while
    the checked `pg_hba.conf` keeps its recorded digest. The check never reads
    postgresql.auto.conf: it asks the server, as the database account over the private
    socket, which rule file is in force. The launch job's `-c hba_file=` outranks every
    configuration file, so the server answers the pinned file and the item passes; a
    server that followed postgresql.auto.conf answers the trust file, and the item fails
    on that alone. Since your answer of 2026-11-11 ("Map the login, root rules") the pinned
    file is the root-owned rules folder's, the item asks for `ident_file` too, and the
    login it asks through is `render.SUPERUSER`, mapped from the database account."""
    from docsuri_ops.arrangement import render
    from docsuri_ops.isolation_check import _digest_within

    arrangement = Arrangement(tmp_path / "case")
    paths = arrangement.paths
    pinned = paths.postgres_rules / "pg_hba.conf"
    decoy = tmp_path / "decoy" / "pg_hba.conf"
    decoy.parent.mkdir()
    decoy.write_text("local all all trust\nhost all all 0.0.0.0/0 trust\n")
    (paths.postgres_data / "postgresql.auto.conf").write_text(f"hba_file = '{decoy}'\n")

    result = arrangement.run()
    assert items(result)["database"] == {"item": "database", "passed": True}
    assert result["passed"] is True, result["items"]
    psql = str(paths.postgres_runtime / "bin" / "psql")
    asked = [index for index, argv in enumerate(arrangement.tools.calls) if argv[0] == psql]
    assert len(asked) == 2
    assert render.SUPERUSER == "postgres"
    for index, setting in zip(asked, ("hba_file", "ident_file"), strict=True):
        assert arrangement.tools.calls[index] == [
            psql, "-X", "-w", "-At", "-h", str(paths.postgres_socket), "-p", "15432", "-U",
            render.SUPERUSER, "-d", "postgres", "-c", f"SHOW {setting}"]
        uid = arrangement.accounts.database.uid
        assert arrangement.tools.options[index] == {"user": uid, "group": uid,
                                                    "extra_groups": []}

    arrangement.tools.hba_file = str(decoy)  # what a server without the pin would answer
    manifest = json.loads((paths.control / "arrangement-manifest.json").read_bytes())
    assert _digest_within(paths.prefix, pinned) == manifest["pgHbaSha256"]
    result = arrangement.run()
    found = items(result)
    assert found["database"] == {"item": "database", "passed": False,
                                 "reason": "database-hba-file-differs"}
    assert [name for name, value in found.items() if not value["passed"]] == ["database"]
    assert result["passed"] is False


def test_the_database_item_refuses_rule_files_the_database_account_could_change(tmp_path):
    """Your answer of 2026-11-11 ("Map the login, root rules"): `pg_hba.conf` and
    `pg_ident.conf` are root's in a root-owned folder, which the database account can read
    but neither write nor replace. Each case keeps the files' recorded bytes, so only the
    custody, the map's digest or the server's `ident_file` answer can fail it, and only
    the `database` item fails, with its own fixed reason."""
    def chmod(path_of, mode):
        return lambda arrangement: path_of(arrangement).chmod(mode)

    cases = [
        ("the rules folder writable by its group",
         chmod(lambda a: a.paths.postgres_rules, 0o775), "database-rules-folder-custody"),
        ("the rules folder writable by every account",
         chmod(lambda a: a.paths.postgres_rules, 0o757), "database-rules-folder-custody"),
        ("pg_hba.conf writable by its group", chmod(lambda a: a.hba, 0o664),
         "database-rule-file-custody"),
        ("pg_ident.conf writable by every account", chmod(lambda a: a.ident, 0o646),
         "database-rule-file-custody"),
        ("a wider map", lambda a: a.ident.write_text(
            "docsuri_superuser /^(.*)$ postgres\n"), "database-ident-differs"),
        ("no recorded map digest", lambda a: a.amend_manifest(
            lambda manifest: manifest.update(pgIdentSha256=None)), "database-ident-differs"),
        ("another map file in force", lambda a: setattr(
            a.tools, "ident_file", "/tmp/elsewhere/pg_ident.conf"),
         "database-ident-file-differs"),
        ("psql refused for ident_file alone", lambda a: a.tools.answers.update(
            {(str(a.paths.postgres_runtime / "bin" / "psql"), "-X", "-w", "-At", "-h",
              str(a.paths.postgres_socket), "-p", "15432", "-U", "postgres", "-d", "postgres",
              "-c", "SHOW ident_file"): Done("", 2)}), "database-ident-file-differs"),
    ]
    for index, (case, set_up, reason) in enumerate(cases):
        arrangement = Arrangement(tmp_path / f"case-{index}")
        assert items(arrangement.run())["database"]["passed"] is True, case
        set_up(arrangement)
        found = items(arrangement.run())
        assert found["database"] == {"item": "database", "passed": False,
                                     "reason": reason}, case
        assert [name for name, value in found.items() if not value["passed"]] == [
            "database"], case


def test_an_entry_the_installer_could_not_read_never_passes_the_files_item(tmp_path):
    """The re-review of 2026-11-10 (Major): the installer keeps a rendered file it could
    not read through the walk (a second name held while the manifest was recorded) with
    `manifest.UNREAD_DIGEST`. `IsolationCheck.files()` answers `file-differs` for that
    entry whatever the file holds afterwards, its second name gone: the bytes the entry
    would otherwise have recorded, and changed bytes. The same entry with the file's real
    digest passes, so nothing else fails the item."""
    from docsuri_ops.arrangement import manifest as arrangement_manifest

    arrangement = Arrangement(tmp_path / "case")
    config = arrangement.paths.postgres_data / "postgresql.conf"
    config.write_text("listen_addresses = '127.0.0.1'\n")

    def files_with(digest: str) -> dict:
        def entry(manifest: dict) -> None:
            manifest["files"] = [item for item in manifest["files"]
                                 if item["path"] != "postgres/data/postgresql.conf"]
            manifest["files"].append({"path": "postgres/data/postgresql.conf",
                                      "kind": "config", "sha256": digest})
        arrangement.amend_manifest(entry)
        return items(arrangement.run())["files"]

    assert files_with(sha(config))["passed"] is True
    differs = {"item": "files", "passed": False, "reason": "file-differs"}
    assert files_with(arrangement_manifest.UNREAD_DIGEST) == differs
    config.write_text("listen_addresses = '*'\n")
    assert files_with(arrangement_manifest.UNREAD_DIGEST) == differs
    assert files_with(sha(config))["passed"] is True


def test_the_installed_program_takes_no_argument():
    assert isolation_check.main(["elsewhere"]) == 2
    assert parse_otool("x: is not an object file") is None
    assert BOOT_LABELS and all(label.startswith("org.docsuri.") for label in BOOT_LABELS)
