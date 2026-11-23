"""The root jobs against recorded tool output (U8 plan Step 36; D10, NFR3.5, NFR3.8,
NFR7.3): the packet filter's loader (its anchor, then its enable sequence) and the backup
volume's unlock with its retry. Every tool answers from a recording; nothing reaches
`pfctl`, `diskutil` or the keychain of this Mac.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import secrets

import pytest

from docsuri_ops import backup_unlock, pf_loader
from docsuri_ops.arrangement.paths import ArrangementPaths

NOW = dt.datetime(2026, 10, 23, 0, 0, tzinfo=dt.UTC)
LOCKED = ("   Device Identifier:         disk4s1\n   Volume Name:               DocSuri_Backup\n"
          "   FileVault:                 Yes\n   Locked:                    Yes\n")
UNLOCKED = LOCKED.replace("Locked:                    Yes", "Locked:                    No")
ABSENT = "Could not find disk: DocSuri_Backup\n"
PASSPHRASE = secrets.token_hex(24).encode()  # L1-36: generated per run


class Done:
    def __init__(self, stdout: bytes | str = b"", returncode: int = 0,
                 stderr: bytes | str = b""):
        self.stdout = stdout.encode() if isinstance(stdout, str) else stdout
        self.stderr = stderr.encode() if isinstance(stderr, str) else stderr
        self.returncode = returncode


class Recorded:
    """Tool answers in order per tool, and every call kept (argv and input)."""

    def __init__(self, answers: dict[str, list[Done]]):
        self.answers = {name: list(items) for name, items in answers.items()}
        self.calls: list[tuple[list[str], bytes | None]] = []

    def __call__(self, argv, **options):
        self.calls.append((list(argv), options.get("input")))
        tool = os.path.basename(argv[0])
        key = f"{tool} {argv[1]}" if tool in ("pfctl", "diskutil") else tool
        queue = self.answers.get(key) or self.answers.get(tool)
        assert queue, argv
        return queue.pop(0) if len(queue) > 1 else queue[0]


@pytest.fixture
def clean_environment(monkeypatch):
    """The installed programs refuse an environment holding PYTHON*, DYLD_* or LD_*
    variables; a test runner may set some, so the programs' own runs clear them."""
    for name in list(os.environ):
        if name.startswith(("PYTHON", "DYLD_", "LD_")):
            monkeypatch.delenv(name)


@pytest.fixture
def anchor(tmp_path):
    path = tmp_path / "etc" / "pf.anchors" / "org.docsuri.v2"
    path.parent.mkdir(parents=True)
    path.write_text("block return in quick on lo0 proto tcp to 127.0.0.1 port 18200\n")
    return path


def test_the_loader_loads_the_anchor_under_com_apple_then_enables_the_filter(anchor):
    run = Recorded({"pfctl -a": [Done()], "pfctl -E": [Done("pf enabled\nToken : 1234\n")],
                    "pfctl -s": [Done("Status: Enabled for 0 days 00:00:01\n")]})
    done = pf_loader.load(run=run, anchor_file=anchor, owner_uid=os.getuid())
    assert done == ["anchor-checked", "anchor-loaded", "filter-enabled", "filter-confirmed"]
    assert [argv for argv, _ in run.calls] == [
        ["/sbin/pfctl", "-a", "com.apple/org.docsuri.v2", "-f", str(anchor)],
        ["/sbin/pfctl", "-E"], ["/sbin/pfctl", "-s", "info"]]


@pytest.mark.parametrize("case,reason", [
    ("load-refused", "anchor-refused"), ("enable-refused", "filter-refused"),
    ("still-disabled", "filter-not-enabled")])
def test_the_loader_stops_at_the_first_step_that_fails(anchor, case, reason):
    answers = {"pfctl -a": [Done(returncode=1 if case == "load-refused" else 0)],
               "pfctl -E": [Done(returncode=1 if case == "enable-refused" else 0)],
               "pfctl -s": [Done("Status: Disabled\n")]}
    run = Recorded(answers)
    with pytest.raises(pf_loader.LoadFailed) as caught:
        pf_loader.load(run=run, anchor_file=anchor, owner_uid=os.getuid())
    assert caught.value.reason == reason
    # U8 plan Step 75(g): the run stops at the failing step, and no step touches pf.conf,
    # flushes (-F) or disables (-d) the filter.
    sequence = [["/sbin/pfctl", "-a", "com.apple/org.docsuri.v2", "-f", str(anchor)],
                ["/sbin/pfctl", "-E"], ["/sbin/pfctl", "-s", "info"]]
    steps = {"load-refused": 1, "enable-refused": 2, "still-disabled": 3}[case]
    argvs = [argv for argv, _ in run.calls]
    assert argvs == sequence[:steps]
    for argv in argvs:
        assert "/etc/pf.conf" not in argv and "-F" not in argv and "-d" not in argv


def test_the_loader_refuses_an_anchor_another_account_could_write(anchor, tmp_path):
    anchor.chmod(0o666)
    with pytest.raises(pf_loader.LoadFailed, match="anchor-custody"):
        pf_loader.load(run=Recorded({}), anchor_file=anchor, owner_uid=os.getuid())
    with pytest.raises(pf_loader.LoadFailed, match="anchor-missing"):
        pf_loader.load(run=Recorded({}), anchor_file=tmp_path / "none", owner_uid=os.getuid())


def test_the_loaders_run_is_recorded_in_control_logs(anchor, tmp_path, capsys,
                                                     clean_environment):
    paths = ArrangementPaths.under(tmp_path / "prefix")
    paths.control_logs.mkdir(parents=True)
    run = Recorded({"pfctl -a": [Done()], "pfctl -E": [Done()],
                    "pfctl -s": [Done("Status: Enabled\n")]})
    assert pf_loader.main([], run=run, paths=paths, anchor_file=anchor, owner_uid=os.getuid(),
                          clock=lambda: NOW) == 0
    line = json.loads((paths.control_logs / "pf-load.jsonl").read_text())
    assert line["ok"] is True and line["steps"][-1] == "filter-confirmed"
    failing = Recorded({"pfctl -a": [Done(returncode=1)]})
    assert pf_loader.main([], run=failing, paths=paths, anchor_file=anchor,
                          owner_uid=os.getuid(), clock=lambda: NOW) == 1
    assert pf_loader.main(["elsewhere"]) == 2
    assert json.loads(capsys.readouterr().out.splitlines()[1])["reason"] == "anchor-refused"


def test_the_unlock_does_nothing_for_an_absent_or_unlocked_volume():
    assert backup_unlock.once(run=Recorded({"diskutil info": [Done(ABSENT, 1)]})) == "absent"
    run = Recorded({"diskutil info": [Done(UNLOCKED)]})
    assert backup_unlock.once(run=run) == "unlocked"
    assert all("security" not in argv[0] for argv, _ in run.calls)  # no passphrase read


def test_the_unlock_passes_the_passphrase_on_standard_input_only():
    run = Recorded({"diskutil info": [Done(LOCKED), Done(UNLOCKED)],
                    "security": [Done(PASSPHRASE + b"\n")],
                    "diskutil apfs": [Done("Unlocking any cryptographic user...\n")]})
    assert backup_unlock.once(run=run) == "unlocked-now"
    unlock = next((argv, given) for argv, given in run.calls if argv[1] == "apfs")
    assert unlock == (["/usr/sbin/diskutil", "apfs", "unlockVolume", "disk4s1",
                       "-stdinpassphrase"], PASSPHRASE)
    assert not any(PASSPHRASE.decode() in " ".join(argv) for argv, _ in run.calls)


def test_a_failed_unlock_is_retried_by_the_next_run(tmp_path, capsys, clean_environment):
    paths = ArrangementPaths.under(tmp_path / "prefix")
    paths.control_logs.mkdir(parents=True)
    refused = Recorded({"diskutil info": [Done(LOCKED)], "security": [Done(PASSPHRASE)],
                        "diskutil apfs": [Done("Error: wrong passphrase\n", 1)]})
    assert backup_unlock.main([], run=refused, paths=paths, clock=lambda: NOW) == 1
    retried = Recorded({"diskutil info": [Done(LOCKED), Done(UNLOCKED)],
                        "security": [Done(PASSPHRASE)], "diskutil apfs": [Done()]})
    assert backup_unlock.main([], run=retried, paths=paths, clock=lambda: NOW) == 0
    lines = [json.loads(line) for line in
             (paths.control_logs / "backup-unlock.jsonl").read_text().splitlines()]
    assert [line["outcome"] for line in lines] == ["unlock-refused", "unlocked-now"]
    assert PASSPHRASE.decode() not in capsys.readouterr().out


def test_the_unlock_reads_only_the_system_keychain_item():
    """U8 plan Step 75(g), L1-36: a passphrase generated per run; only the System
    keychain's item is read, and only for a present, locked volume."""
    passphrase = secrets.token_hex(24).encode()
    run = Recorded({"diskutil info": [Done(LOCKED), Done(UNLOCKED)],
                    "security": [Done(passphrase + b"\n")], "diskutil apfs": [Done()]})
    assert backup_unlock.once(run=run) == "unlocked-now"
    keychain = [argv for argv, _ in run.calls if argv[0].endswith("/security")]
    assert keychain == [["/usr/bin/security", "find-generic-password", "-s", "DocSuri_Backup",
                         "-w", "/Library/Keychains/System.keychain"]]
    home = os.path.expanduser("~")
    for argv, _ in run.calls:
        joined = " ".join(argv)
        assert "login.keychain" not in joined and home not in joined and "/Users/" not in joined
        assert passphrase.decode() not in joined
    for answer in (Done(ABSENT, 1), Done(UNLOCKED)):
        quiet = Recorded({"diskutil info": [answer]})
        assert backup_unlock.once(run=quiet) in ("absent", "unlocked")
        assert not [argv for argv, _ in quiet.calls if "security" in argv[0]]


def test_the_unlock_reads_a_missing_volume_on_standard_error():
    """U8 plan Step 74(d) found `diskutil info` writing `Could not find disk` to standard
    error with exit 1 on this Mac; the unlock reads it there, as absent."""
    run = Recorded({"diskutil info": [Done(b"", 1, ABSENT)]})
    assert backup_unlock.once(run=run) == "absent"
    assert [argv for argv, _ in run.calls] == [["/usr/sbin/diskutil", "info", "DocSuri_Backup"]]
    # The same line on standard error with exit 0 is not read: only exit 1 reads it.
    assert backup_unlock.once(run=Recorded({"diskutil info": [Done(b"", 0, ABSENT)]})) == (
        "volume-unreadable")


@pytest.mark.parametrize("answers,outcome", [
    ({"diskutil info": [Done("garbage")]}, "volume-unreadable"),
    ({"diskutil info": [Done(LOCKED.replace("Device Identifier", "Node"))]}, "device-unknown"),
    ({"diskutil info": [Done(LOCKED)], "security": [Done(b"", 44)]}, "passphrase-unavailable"),
    ({"diskutil info": [Done(LOCKED), Done(LOCKED)], "security": [Done(PASSPHRASE)],
      "diskutil apfs": [Done()]}, "still-locked"),
])
def test_each_way_an_unlock_can_fail_names_itself(answers, outcome):
    assert backup_unlock.once(run=Recorded(answers)) == outcome
