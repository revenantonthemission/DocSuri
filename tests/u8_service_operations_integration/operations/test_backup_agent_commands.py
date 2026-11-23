"""The backup agent's fixed command: its words, its callers and its inputs (U8 plan Step 26;
BR4.3, D6, NFR1.5; Workflow 19's table).

The sudo rules are the first gate and the program is the second: it reads the caller
from `SUDO_UID`, refuses the service account every word and the scheduler every
in-person word, refuses a word outside its set and a caller-set interpreter variable,
takes a copy's kind only from the command and its source, and refuses a database name
outside the scratch pattern before any connection is made (the person's decision of
2026-10-22).
Every connection the agent makes, its own and its programs', requires SCRAM (NFR3.3, D9).
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from docsuri_ops.backup_agent import cli
from tests.u8_service_operations_integration import agent_flows as af


@pytest.fixture
def rig(tmp_path, clock):
    return af.build(tmp_path, clock)


def test_the_kind_follows_the_command_and_its_source_never_the_caller(rig):
    # A caller-supplied kind is never used: the field is refused, and nothing is dumped.
    status, refused, _ = af.invoke(rig, "backup", {
        "database": "docsuri_u8", "recordId": str(uuid4()), "kind": "final-snapshot",
    }, caller=af.SCHEDULER)
    assert (status, refused["reason"]) == (1, "input-field-refused")
    assert not [call for call in rig.tools.calls if call[0] == "dump"]
    live = af.backed_up(rig, "docsuri_u8")
    rehearsal = af.backed_up(rig, "docsuri_u8_rehearsal_0123456789ab")
    assert (live["copyKind"], live["recordKind"]) == ("live-set", "BackupSet")
    assert (rehearsal["copyKind"], rehearsal["recordKind"]) == ("rehearsal-set", "BackupSet")
    assert live["location"].startswith("archives/live-set-")
    assert live["incarnation"] == "docsuri_u8:4242" and live["integrity"] == "passed"


@pytest.mark.parametrize("database", [
    "docsuri_u8_platform", "docsuri_u8_scratch_0123456789ab", "docsuri_u8_import_0123456789ab",
    "docsuri_v1", "postgres", "docsuri_u8; DROP DATABASE docsuri_u8",
])
def test_only_the_production_and_rehearsal_databases_are_dumped(rig, database):
    status, result, _ = af.invoke(rig, "backup", {"database": database,
                                                  "recordId": str(uuid4())},
                                  caller=af.SCHEDULER)
    assert (status, result["reason"]) == (1, "database-refused")
    assert rig.tools.calls == []  # refused before any connection


@pytest.mark.parametrize("word", cli.WORDS)
def test_the_service_account_is_refused_every_command(rig, word):
    status, result, _ = af.invoke(rig, word, {}, caller=af.SERVICE)
    assert (status, result) == (2, {"ok": False, "reason": "caller-refused"})
    assert rig.tools.calls == []


@pytest.mark.parametrize("word", cli.IN_PERSON)
def test_the_scheduler_is_refused_every_in_person_command(rig, word):
    status, result, _ = af.invoke(rig, word, {}, caller=af.SCHEDULER)
    assert (status, result) == (2, {"ok": False, "reason": "in-person-refused"})


def test_an_unknown_caller_and_a_missing_caller_are_refused(rig):
    assert af.invoke(rig, "status", caller=4242)[1]["reason"] == "caller-refused"
    status, result, _ = af.invoke(rig, "status", environ={"SUDO_UID": ""})
    assert (status, result["reason"]) == (2, "caller-unknown")
    # The scheduler's own unattended status passes.
    status, result, _ = af.invoke(rig, "status", caller=af.SCHEDULER)
    assert status == 0 and result["available"] is True and result["standin"] is True


def test_configure_writes_the_first_configuration_as_root_then_only_the_volume(rig, tmp_path):
    from docsuri_ops.backup_agent.config import CONFIG, ConfigRefused, load

    document = rig.config.as_document()
    (rig.context.folder / CONFIG).unlink()
    assert af.invoke(rig, "status")[1]["reason"] == "agent-not-configured"
    assert af.invoke(rig, "configure", document, caller=af.SCHEDULER)[1]["reason"] == (
        "agent-not-configured")
    status, result, _ = af.invoke(rig, "configure", document, caller=0)
    assert status == 0 and result["volumeIdentity"] == af.IDENTITY
    # Afterwards only the operator, and only the volume's mount point and identity.
    assert af.invoke(rig, "configure", document, caller=0)[1]["reason"] == "caller-refused"
    assert af.invoke(rig, "configure", document)[1]["reason"] == "input-field-refused"
    replacement = tmp_path / "replacement"
    status, result, _ = af.invoke(rig, "configure", {"mount": str(replacement),
                                                     "volumeIdentity": "replacement-0002"})
    assert status == 0 and load(rig.context.folder).mount == replacement
    for broken in ({"mount": "relative/path", "volumeIdentity": "x"},
                   {"mount": str(replacement), "volumeIdentity": "../bad"}):
        assert af.invoke(rig, "configure", broken)[1]["reason"] == "agent-config-refused"
    for field, value in (("kind", "cloud"), ("databasePrefix", "other"),
                         ("v2Login", {**document["v2Login"], "host": "10.0.0.1"}),
                         ("schedulerUid", af.OPERATOR), ("container", None)):
        changed = {key: item for key, item in {**document, field: value}.items()
                   if item is not None}
        with pytest.raises(ConfigRefused):
            type(rig.config).from_document(changed)
    (rig.context.folder / CONFIG).chmod(0o644)
    assert af.invoke(rig, "status")[1]["reason"] == "agent-config-refused"


def test_only_the_composed_realm_names_its_own_space_floor(rig):
    from dataclasses import replace

    from docsuri_ops.backup_agent.config import BACKUP_FLOOR_BYTES, ConfigRefused

    production = replace(rig.config, kind="production", container=None,
                         space_floor_bytes=BACKUP_FLOOR_BYTES)
    document = production.as_document()
    assert "spaceFloorBytes" not in document  # production's floor is never written down
    with pytest.raises(ConfigRefused, match="space floor"):
        type(rig.config).from_document({**document, "spaceFloorBytes": 1024})
    with pytest.raises(ConfigRefused, match="space floor"):
        replace(production, space_floor_bytes=1024**3)
    with pytest.raises(ConfigRefused, match="space floor"):
        replace(rig.config, space_floor_bytes=0)
    realm = replace(rig.config, kind="realm", container="docsuri-u8-0123456789abcdef",
                    space_floor_bytes=1024**3)
    again = type(rig.config).from_document(realm.as_document())
    assert again.space_floor_bytes == 1024**3 and again.as_document() == realm.as_document()


def test_a_realm_entry_serves_only_a_realm_configuration(tmp_path, capfdbinary):
    import json

    unconfigured = tmp_path / "agent"
    unconfigured.mkdir(mode=0o700)
    assert cli.main_realm([str(unconfigured), "status"]) == 2
    assert json.loads(capfdbinary.readouterr().out) == {"ok": False,
                                                        "reason": "realm-entry-refused"}
    assert cli.main_realm(["status"]) == 2
    assert json.loads(capfdbinary.readouterr().out)["reason"] == "word-refused"


@pytest.mark.parametrize("argv", [["shell"], ["status", "--extra"], [], ["../status"]])
def test_a_word_outside_the_set_is_refused(rig, argv):
    import io
    import json

    out = io.BytesIO()
    status = cli.run(argv, rig.context, environ={"SUDO_UID": str(af.OPERATOR)},
                     stdin=io.BytesIO(b"{}"), stdout=out, stderr=io.BytesIO())
    assert (status, json.loads(out.getvalue())["reason"]) == (2, "word-refused")


@pytest.mark.parametrize("variable", ["PYTHONPATH", "PYTHONSTARTUP", "DYLD_INSERT_LIBRARIES",
                                      "LD_PRELOAD"])
def test_a_caller_set_interpreter_variable_is_refused(rig, variable):
    status, result, _ = af.invoke(rig, "status", environ={variable: "/tmp/evil"})
    assert (status, result["reason"]) == (2, "environment-refused")


@pytest.mark.parametrize("name", [
    "docsuri_u8", "docsuri_u8_platform", "docsuri_u8_rehearsal_0123456789ab",
    "docsuri_u8_import_0123456789ab", "docsuri_u8_scratch_xyz", "docsuri_v2_scratch_0123456789ab",
    'x"; CREATE DATABASE evil; --', 42,
])
def test_a_name_outside_the_scratch_pattern_is_refused_before_any_connection(rig, name):
    """The person's decision of 2026-10-22: PostgreSQL cannot limit the names the agent's
    login creates while acting as the disposable-databases role, so its command refuses
    any other name, and makes no connection to do so."""
    af.backed_up(rig)
    rig.tools.calls.clear()
    status, result, _ = af.invoke(rig, "verify", {"scratchDatabase": name,
                                                  "setKind": "live-set"}, caller=af.SCHEDULER)
    assert (status, result["reason"]) == (1, "scratch-name-refused")
    assert rig.tools.calls == []


def test_verify_restores_the_newest_passed_set_as_the_disposable_role_and_hands_no_file(rig):
    af.backed_up(rig)
    rig.clock.advance(3600)
    newest = af.backed_up(rig, record_id=str(uuid4()))
    rig.tools.calls.clear()
    scratch = "docsuri_u8_scratch_0123456789ab"
    status, result, payload = af.invoke(rig, "verify", {"scratchDatabase": scratch,
                                                        "setKind": "live-set"},
                                        caller=af.SCHEDULER)
    assert status == 0 and payload == b""
    assert result["setPath"] == newest["location"] and result["scratchDatabase"] == scratch
    assert ("create", scratch, "docsuri_disposable") in rig.tools.calls
    assert [call[:3] for call in rig.tools.calls if call[0] == "restore"] == [
        ("restore", scratch, "docsuri_disposable")]


def _log_lines(rig) -> list[dict]:
    import json

    path = rig.context.folder / "logs" / "backup-agent.log"
    return [json.loads(line) for line in path.read_bytes().splitlines()]


def _tree(root) -> dict:
    """Every file and folder under `root`, with each regular file's bytes."""
    found = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file():
            found[str(path)] = None
        else:
            found[str(path)] = path.read_bytes()
    return found


def test_the_agent_writes_its_log_in_its_own_folder(rig, tmp_path):
    """NFR9.8: one line per run, refusals included, in the agent's own 0700 folder."""
    import io
    import logging
    import os
    import stat

    from backend import log_events

    outside_before = {key: value for key, value in _tree(tmp_path).items()
                      if not key.startswith((str(rig.context.folder), str(rig.volume)))}
    handlers, events = list(logging.getLogger().handlers), log_events.current()
    stdout, stderr = io.BytesIO(), io.BytesIO()
    status = cli.run(["status"], rig.context, environ={"SUDO_UID": str(af.SCHEDULER)},
                     stdin=io.BytesIO(b"{}"), stdout=stdout, stderr=stderr)
    assert status == 0 and stderr.getvalue() == b""
    assert logging.getLogger().handlers == handlers
    assert all(a is b for a, b in zip(logging.getLogger().handlers, handlers, strict=True))
    assert log_events.current() is events
    af.backed_up(rig)
    folder = rig.context.folder / "logs"
    log = folder / "backup-agent.log"
    assert stat.S_IMODE(folder.lstat().st_mode) == 0o700
    assert stat.S_IMODE(log.lstat().st_mode) == 0o600
    answered = _log_lines(rig)
    assert [line["state"] for line in answered] == ["status", "backup"]
    for line in answered:
        assert set(line) == {"ts", "level", "component", "event", "state", "durationMs"}
        assert (line["component"], line["event"]) == ("backup-agent", "command.answered")
        assert isinstance(line["durationMs"], int) and line["durationMs"] >= 0
    raw = log.read_bytes()
    for secret in (b"docsuri_u8", af.IDENTITY.encode(), b"/", str(rig.volume).encode()):
        assert secret not in raw
    # A refusal is logged too, with its key.
    assert af.invoke(rig, "dispose-event", {}, caller=af.SCHEDULER)[1]["reason"] == (
        "in-person-refused")
    refused = _log_lines(rig)[-1]
    assert set(refused) == {"ts", "level", "component", "event", "state", "durationMs",
                            "reason"}
    assert (refused["event"], refused["state"], refused["reason"]) == (
        "command.refused", "dispose-event", "in-person-refused")
    # A planted link is never followed: the word answers as before and writes no line.
    target = tmp_path / "outside-target.log"
    target.write_bytes(b"not the agent's\n")
    before = af.invoke(rig, "status", caller=af.SCHEDULER)[1]
    log.unlink()
    os.symlink(target, log)
    assert af.invoke(rig, "status", caller=af.SCHEDULER)[1] == before
    assert target.read_bytes() == b"not the agent's\n" and log.is_symlink()
    assert sorted(path.name for path in folder.iterdir()) == ["backup-agent.log"]
    outside_after = {key: value for key, value in _tree(tmp_path).items()
                     if not key.startswith((str(rig.context.folder), str(rig.volume)))
                     and key != str(target)}
    assert outside_after == outside_before


def test_the_status_lists_each_undisposed_catalogued_file(rig):
    """L1-51: every catalogued file not yet disposed of, by record, kind, place and
    disposal point; no disposed entry and no path."""
    from docsuri_ops.backup_agent.catalogue import Catalogue
    from docsuri_ops.backup_agent.writing import ArchiveWriter

    # Whole seconds: the catalogue records times to the millisecond, a receipt to the
    # microsecond.
    rig.clock.now = _instant("2026-11-03T03:00:00Z")
    backup = af.backed_up(rig)
    copy = af.invoke(rig, "ledger-copy", b"", caller=af.SCHEDULER)[1]

    class CutShort(BaseException):
        pass

    catalogue = Catalogue.open(rig.u8, clock=rig.clock)
    record = str(uuid4())

    def fill(sink):
        raise CutShort

    try:
        with pytest.raises(CutShort):
            ArchiveWriter(rig.config, catalogue, clock=rig.clock,
                          volume=rig.context.volume).write(
                "live-set", record_id=record, fill=fill, integrity=lambda archive: True)
        cut = {entry.path.split("/", 1)[0]: entry for entry in catalogue.files().values()
               if entry.record_id == record}
    finally:
        catalogue.close()
    status, result, _ = af.invoke(rig, "status", caller=af.SCHEDULER)
    assert status == 0
    expected = [
        {"recordId": backup["recordId"], "recordKind": "BackupSet", "place": "archives",
         "disposeAfter": backup["disposeAfter"]},
        {"recordId": copy["recordId"], "recordKind": "LedgerCopy", "place": "archives",
         "disposeAfter": copy["disposeAfter"]},
        {"recordId": record, "recordKind": "BackupSet", "place": "archives",
         "disposeAfter": cut["archives"].dispose_after},
        {"recordId": record, "recordKind": "BackupSet", "place": "staging",
         "disposeAfter": cut["staging"].dispose_after},
    ]
    listed = result["catalogued"]
    assert len(listed) == 4
    normal = [{**item, "disposeAfter": _instant(item["disposeAfter"])} for item in listed]
    assert normal == sorted(
        ({**item, "disposeAfter": _instant(item["disposeAfter"])} for item in expected),
        key=lambda item: (item["recordId"], item["place"]))
    for item in listed:
        assert set(item) == {"recordId", "recordKind", "place", "disposeAfter"}
        assert "/" not in item["place"]


def _instant(text: str):
    import datetime as dt

    return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))


def test_the_scratch_restore_times_the_hnsw_index_on_its_own(rig):
    """NFR9.4: a set whose table of contents holds the search projection's HNSW index
    restores in two passes, the second (the index alone) timed on the monotonic clock."""
    index = "4012; 1259 16923 INDEX corpus projection_embedding_hnsw docsuri_corpus"
    entries = [";", "; Archive created at 2026-11-10", "201; 1259 16100 TABLE accounts "
               "account docsuri_owner", "202; 1259 16200 TABLE corpus projection docsuri_corpus",
               index, "4013; 2606 16924 CONSTRAINT accounts account_pkey docsuri_owner"]
    rig.tools.toc = entries
    af.backed_up(rig)
    readings = iter([100.0, 106.2])
    restores_seen: list[int] = []

    def monotonic() -> float:
        # How many restores the tools had seen at each reading: the two readings must
        # bracket the second restore alone (review fix, batch 4).
        restores_seen.append(sum(1 for call in rig.tools.calls if call[0] == "restore"))
        return next(readings)

    rig.context.monotonic = monotonic
    rig.tools.calls.clear()
    scratch = "docsuri_u8_scratch_0123456789ab"
    status, result, _ = af.invoke(rig, "verify", {"scratchDatabase": scratch,
                                                  "setKind": "live-set"}, caller=af.SCHEDULER)
    assert status == 0, result
    assert result["hnswRebuildSeconds"] == 7  # 6.2 s, rounded up
    assert restores_seen == [1, 2]  # one restore before the first reading, two after
    restores =[call for call in rig.tools.calls if call[0] == "restore"]
    assert [call[1:3] for call in restores] == [(scratch, "docsuri_disposable")] * 2
    first, second = restores[0][4].splitlines(), restores[1][4].splitlines()
    assert first == [f";{line}" if line == index else line for line in entries]
    assert [line for line in first if not line.startswith(";")] == [
        line for line in entries if not line.startswith(";") and line != index]
    assert second == [index]
    # A set without that entry is restored once, with no list and no time.
    rig.tools.toc = [line for line in entries if line != index]
    rig.clock.advance(60)
    af.backed_up(rig, record_id=str(uuid4()))
    rig.tools.calls.clear()
    status, result, _ = af.invoke(rig, "verify", {"scratchDatabase": scratch,
                                                  "setKind": "live-set"}, caller=af.SCHEDULER)
    assert status == 0 and "hnswRebuildSeconds" not in result
    assert [call[4] for call in rig.tools.calls if call[0] == "restore"] == [None]


# --- Step 122(c): the agent's own critical floor (NFR7.18, NFR8.14) -------------------------

SCRATCH = "docsuri_u8_scratch_0123456789ab"
FLOOR = 10 * af.GIB


def _verify(rig):
    return af.invoke(rig, "verify", {"scratchDatabase": SCRATCH, "setKind": "live-set"},
                     caller=af.SCHEDULER)


def test_verify_below_the_critical_floor_is_refused_before_any_client_program(rig):
    af.backed_up(rig)
    rig.tools.calls.clear()
    rig.context.internal_free = lambda: FLOOR - 1
    status, result, _ = _verify(rig)
    assert (status, result["reason"]) == (1, "internal-disk-critical")
    assert "sessionsEnded" not in result
    assert rig.tools.calls == []  # no table of contents, no create, no restore
    assert _log_lines(rig)[-1]["reason"] == "internal-disk-critical"
    rig.context.internal_free = lambda: FLOOR
    status, result, _ = _verify(rig)
    assert status == 0, result


def test_a_floor_crossed_between_the_two_passes_stops_before_the_index(rig):
    rig.tools.toc = [
        ";", "201; 1259 16100 TABLE accounts account docsuri_owner",
        "202; 1259 16200 TABLE corpus projection docsuri_corpus",
        "4012; 1259 16923 INDEX corpus projection_embedding_hnsw docsuri_corpus",
    ]
    af.backed_up(rig)
    rig.tools.calls.clear()
    readings = iter([100 * af.GIB])
    rig.context.internal_free = lambda: next(readings, FLOOR - 1)
    status, result, _ = _verify(rig)
    assert (status, result["reason"]) == (1, "internal-disk-critical")
    assert "sessionsEnded" not in result
    assert len([call for call in rig.tools.calls if call[0] == "restore"]) == 1
    assert rig.tools.watches == [(SCRATCH, rig.context.disk_watch_seconds, "docsuri_u8")]
    assert rig.tools.ended == []


class _Sleeping:
    """Stands in for the client program (as `FakeTools` stands in for the client
    programs): a child that sleeps, or exits at once, marked so the test can find it."""

    def __init__(self, code: str):
        import uuid

        self.code, self.marker = code, f"docsuri-test-child-{uuid.uuid4().hex}"

    def tools(self):
        import sys

        from docsuri_ops.backup_agent import dumps
        from docsuri_ops.backup_agent.config import Login

        code, marker = self.code, self.marker

        class Tools(dumps.PgTools):
            def command(self, program, args):
                return [sys.executable, "-c", code, marker]

        return Tools(Login("127.0.0.1", 15509, "docsuri_backup_agent", "v2-login"), "unused")

    def alive(self) -> bool:
        import subprocess

        return subprocess.run(["pgrep", "-f", self.marker], capture_output=True,
                              check=False).returncode == 0

    def kill(self) -> None:
        import subprocess

        subprocess.run(["pkill", "-9", "-f", self.marker], capture_output=True, check=False)


def test_a_watched_client_is_ended_when_ending_its_sessions_does_not_end_it(
    tmp_path, monkeypatch,
):
    import subprocess
    import time

    from docsuri_ops.backup_agent import dumps
    from tests.u8_service_operations_integration.operations.test_drivers import bounded

    archive = tmp_path / "archive"
    archive.write_bytes(b"PGDMP")

    def restoring(child, watch):
        with archive.open("rb") as source:
            return child.tools().restore(source, SCRATCH, "docsuri_disposable", watch=watch)

    # A reason, and sessions whose ending does not end the client: SIGTERM ends it.
    sleeping = _Sleeping("import time; time.sleep(60)")
    ends: list[float] = []
    running: list[bool] = []

    def end() -> int:
        ends.append(time.monotonic())
        running.append(sleeping.alive())
        return 0

    watch = dumps.RestoreWatch(lambda: dumps.CRITICAL, end, 0.01, 0.2, "docsuri_u8")
    try:
        started = time.monotonic()
        outcome, error = bounded(lambda: restoring(sleeping, watch), 10.0)
        assert outcome == "raised", (outcome, error)
        assert isinstance(error, dumps.AgentRefused)
        assert (error.reason, error.facts) == ("internal-disk-critical", {"sessionsEnded": 0})
        assert not sleeping.alive()
        assert ends and ends[0] - started < watch.grace  # before the grace ran out
        assert len(ends) >= 2 and ends[-1] - ends[0] >= watch.grace  # once more after
        # 122(c): `end` runs while the client runs, and "once more after the kill".
        assert all(running[:-1]) and not running[-1], running
    finally:
        sleeping.kill()

    # A client that exits by itself first is answered as built; `end` is never called.
    exiting = _Sleeping("pass")
    ends.clear()
    patient = dumps.RestoreWatch(lambda: dumps.CRITICAL, end, 5, 0.2, "docsuri_u8")
    try:
        assert bounded(lambda: restoring(exiting, patient), 10.0) == ("answered", None)
        assert ends == []
    finally:
        exiting.kill()

    # No reason: the statement bound kills the client, as `subprocess.run`'s timeout did.
    monkeypatch.setattr(dumps, "STATEMENT_SECONDS", 0.3)
    bounded_child = _Sleeping("import time; time.sleep(60)")
    quiet = dumps.RestoreWatch(lambda: None, end, 0.05, 0.2, "docsuri_u8")
    try:
        outcome, error = bounded(lambda: restoring(bounded_child, quiet), 10.0)
        assert outcome == "raised" and isinstance(error, subprocess.TimeoutExpired), error
        assert not bounded_child.alive() and ends == []
    finally:
        bounded_child.kill()

    # SIGTERM comes before SIGKILL: the stand-in notes the gentle signal and exits. The
    # reason answers only once its handler is in place, and the statement bound is set
    # well above this case's time, so neither a startup race nor the bound decides it.
    monkeypatch.setattr(dumps, "STATEMENT_SECONDS", 8.0)
    note, ready = tmp_path / "sigterm-noted", tmp_path / "handler-ready"
    gentle = _Sleeping(
        "import pathlib, signal, sys, time\n"
        f"def noted(*_): pathlib.Path({str(note)!r}).touch(); sys.exit(0)\n"
        "signal.signal(signal.SIGTERM, noted)\n"
        f"pathlib.Path({str(ready)!r}).touch()\n"
        "time.sleep(60)\n"
    )
    signalled = dumps.RestoreWatch(lambda: dumps.CRITICAL if ready.exists() else None,
                                   lambda: 0, 0.01, 0.2, "docsuri_u8")
    try:
        outcome, error = bounded(lambda: restoring(gentle, signalled), 10.0)
        assert outcome == "raised", (outcome, error)
        assert isinstance(error, dumps.AgentRefused)
        assert (error.reason, error.facts) == ("internal-disk-critical", {"sessionsEnded": 0})
        assert note.exists()  # SIGTERM reached the client before any SIGKILL
        assert not gentle.alive()
    finally:
        gentle.kill()


# --- L3-8: every connection the agent makes requires SCRAM (NFR3.3, D9) -----------------------


def test_every_connection_of_the_agent_requires_scram(tmp_path):
    """NFR3.3: the agent's own statements refuse a listener that asks for cleartext, MD5
    or no authentication before any password is sent, and each connection string it
    hands `pg_dump` and `pg_restore` carries `require_auth=scram-sha-256`."""
    import secrets
    import sys

    import psycopg

    from docsuri_ops.backup_agent import dumps
    from docsuri_ops.backup_agent.config import Login
    from tests.u8_service_operations_integration.component.test_transactions_scram import (
        CLEARTEXT,
        MD5,
        STANDIN_PORT,
        TRUST,
        WeakAuthStandin,
    )

    login = Login("127.0.0.1", STANDIN_PORT, "docsuri_backup_agent", "v2-login")
    password = secrets.token_hex(8)  # generated per run (L1-36)
    for request in (CLEARTEXT, MD5, TRUST):
        with WeakAuthStandin(request) as standin:
            tools = dumps.RuntimeTools(login, password, bin_dir=tmp_path)
            with pytest.raises(psycopg.OperationalError, match="scram-sha-256"):
                tools.tables("docsuri_v2")
        assert standin.passwords_seen == 0, request

    recorded: list[tuple[str, list[str]]] = []

    class Recording(dumps.PgTools):
        def command(self, program, args):
            recorded.append((program, list(args)))
            return [sys.executable, "-c", "pass"]

    tools = Recording(login, password)
    with (tmp_path / "set.dump").open("wb") as sink:
        tools.dump("docsuri_v2", sink)
    with (tmp_path / "set.dump").open("rb") as source:
        tools.restore(source, SCRATCH, "docsuri_disposable")
    with (tmp_path / "set.dump").open("rb") as source:
        tools.restore(source, SCRATCH, "docsuri_disposable",
                      listing="201; 1259 16100 TABLE accounts account docsuri_owner\n",
                      beside=tmp_path)
    assert [program for program, _ in recorded] == ["pg_dump", "pg_restore", "pg_restore"]
    for (program, args), database in zip(recorded, ("docsuri_v2", SCRATCH, SCRATCH),
                                         strict=True):
        target = psycopg.conninfo.conninfo_to_dict(args[args.index("-d") + 1])
        assert target.get("require_auth") == "scram-sha-256", program
        assert target["dbname"] == database, program
