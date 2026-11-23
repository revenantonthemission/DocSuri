"""Log rotation's rules without root (U8 plan Step 36; D11, security-design § 7.3, R-20,
R-21).

These are the rotation's own rules, run on any system with the test's account standing in
for root and for every log account (patched user identifiers, as the arrangement tests
allow). The cases that need real root ownership (a link to a root-only folder, a folder
owned by the wrong account) are `arrangement/test_logrotate.py`'s, run with sudo in the
`macos-filesystem` job.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
import logging
import logging.handlers
import os
import stat
import time

import pytest

from docsuri_ops.arrangement.paths import Account, Accounts, ArrangementPaths
from docsuri_ops.logrotate import FOLDERS, LogFolder, LogRotation, RotationContext

NOW = dt.datetime(2026, 10, 23, 3, 0, tzinfo=dt.UTC)


def accounts(uid: int) -> Accounts:
    return Accounts(*(Account(name, uid) for name in (
        "_docsuri_v2", "_docsuri_v2_sched", "_docsuri_v2_db", "_docsuri_models",
        "_docsuri_tunnel", "_docsuri_r1t_backup")))


@pytest.fixture
def layout(tmp_path):
    paths = ArrangementPaths.under(tmp_path / "prefix")
    for folder in FOLDERS:
        (paths.prefix / folder.path).mkdir(parents=True, exist_ok=True)
    context = RotationContext(paths=paths, accounts=accounts(os.getuid()),
                              root_uid=os.getuid(), clock=lambda: NOW)
    return paths, context


def summary(paths) -> dict:
    return json.loads((paths.control_logs / "logrotate.jsonl").read_text().splitlines()[-1])


def test_a_linked_log_folder_and_a_linked_folder_above_it_are_skipped(layout, tmp_path):
    paths, context = layout
    target = tmp_path / "elsewhere"
    target.mkdir()
    secret = target / "host.log"
    secret.write_text("not a log of ours\n")
    before = secret.stat()
    logs = paths.profile / "logs"
    logs.rmdir()
    logs.symlink_to(target)  # the log folder itself is a link
    (paths.prefix / "models-state").rename(tmp_path / "models-moved")
    (paths.prefix / "models-state").symlink_to(tmp_path / "models-moved")  # one above it
    result = LogRotation(context).run()
    skips = {item["folder"]: item["reason"] for item in result["skips"]}
    assert skips == {"profile/logs": "folder-link-or-missing",
                     "models-state/logs": "folder-link-or-missing"}
    assert secret.read_text() == "not a log of ours\n"
    assert sorted(path.name for path in target.iterdir()) == ["host.log"]
    assert secret.stat().st_mtime_ns == before.st_mtime_ns
    assert summary(paths)["skips"] == result["skips"]


def test_a_fifo_under_a_logs_name_is_skipped_at_once(layout):
    paths, context = layout
    os.mkfifo(paths.tunnel_logs / "cloudflared.out.log")
    started = time.monotonic()
    result = LogRotation(context).run()
    assert time.monotonic() - started < 5
    assert {"folder": "tunnel/logs", "reason": "not-a-regular-file"} in result["skips"]


def test_a_hard_link_is_skipped(layout, tmp_path):
    paths, context = layout
    original = paths.backup_agent / "logs" / "agent.out.log"
    original.write_text("line\n")
    os.link(original, tmp_path / "second-name")
    result = LogRotation(context).run()
    assert {"folder": "backup-agent/logs", "reason": "hard-link"} in result["skips"]
    assert original.read_text() == "line\n"


def test_a_moved_v2_log_loses_no_line_written_around_the_move(layout):
    paths, context = layout
    log = paths.profile / "logs" / "host.log"
    handler = logging.handlers.WatchedFileHandler(log)
    logger = logging.getLogger(f"rotation-{id(handler)}")
    logger.addHandler(handler)
    logger.propagate = False
    logger.warning("before")
    LogRotation(context).run()
    logger.warning("after")
    handler.close()
    moved = paths.profile / "logs" / "host.log.20261023"
    assert moved.read_text() == "before\n" and log.read_text() == "after\n"


def test_copy_then_truncate_records_the_bytes_written_during_the_copy(layout):
    paths, context = layout
    held = paths.profile / "logs" / "org.docsuri.v2.host.err.log"
    held.write_bytes(b"x" * 200_000)
    late = b"written while it copied\n"
    appended = []

    def during(position: int) -> None:
        if not appended:
            with open(held, "ab") as stream:
                stream.write(late)
            appended.append(position)

    context.on_chunk = during
    result = LogRotation(context).run()
    copy = paths.profile / "logs" / "org.docsuri.v2.host.err.log.20261023"
    assert result["bytesDuringCopy"] == len(late) and result["copied"] == 1
    assert copy.read_bytes() == b"x" * 200_000 + late
    assert held.read_bytes() == b""  # truncated through the same descriptor
    assert stat.S_IMODE(copy.stat().st_mode) == 0o600 and copy.stat().st_uid == os.getuid()


def test_copies_and_dated_files_older_than_14_days_are_deleted(layout):
    paths, context = layout
    logs = paths.scheduler / "logs"
    old, recent = logs / "standing.log.20261005", logs / "standing.log.20261012"
    for path in (old, recent):
        path.write_text("kept lines\n")
        path.chmod(0o600)
    dated = paths.postgres_data / "log" / "postgresql-2026-10-01_000000.log"
    dated.write_text("server log\n")
    stamp = (NOW - dt.timedelta(days=15)).timestamp()
    os.utime(dated, (stamp, stamp))
    fresh = paths.postgres_data / "log" / "postgresql-2026-10-22_000000.log"
    fresh.write_text("today\n")
    result = LogRotation(context).run()
    assert not old.exists() and recent.exists()
    assert not dated.exists() and fresh.read_text() == "today\n"  # never copied or truncated
    assert result["deleted"] == 2 and result["folders"] == len(FOLDERS)
    assert stat.S_IMODE(recent.stat().st_mode) == 0o600


def test_a_folder_another_account_could_write_is_skipped(layout):
    paths, context = layout
    (paths.prefix / "control" / "logs").chmod(0o777)
    result = LogRotation(context).run()
    assert {"folder": "control/logs", "reason": "folder-owner-differs"} in result["skips"]
    context.folders = (LogFolder("missing/logs", "service", 0, "held"),)
    assert LogRotation(context).run()["skips"] == [{"folder": "missing/logs",
                                                     "reason": "folder-link-or-missing"}]


# --- U8 plan Step 77(d): eight cases without root, with patched user identifiers (the
# root-only cases are Step 103's) ------------------------------------------------------------


def state(path) -> tuple:
    """A file's bytes, size, modification time and inode, read without following a link."""
    info = path.lstat()
    return path.read_bytes(), info.st_size, info.st_mtime_ns, info.st_ino


def planted(path, content: bytes = b"a log line\n", *, mode: int = 0o600):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    path.chmod(mode)
    return path


def at(path, moment: dt.datetime) -> None:
    stamp = moment.timestamp()
    os.utime(path, (stamp, stamp))


def test_a_log_folder_owned_by_another_account_is_skipped_and_untouched(layout, monkeypatch):
    """Step 77(d) 1."""
    from docsuri_ops import logrotate

    paths, context = layout
    context.accounts = dataclasses.replace(
        context.accounts, tunnel=Account("_docsuri_tunnel", os.getuid() + 1))
    names = ("cloudflared.out.log", "cloudflared.err.log")
    files = [planted(paths.tunnel_logs / name, f"{name} bytes\n".encode()) for name in names]
    before = [state(path) for path in files]
    tunnel_logs = paths.tunnel_logs.stat().st_ino
    opened, listed = [], []
    real_open, real_listdir = os.open, os.listdir

    def open_spy(path, *args, **kwargs):
        opened.append(os.fspath(path))
        return real_open(path, *args, **kwargs)

    def listdir_spy(target=".", *args, **kwargs):
        if isinstance(target, int):
            listed.append(os.fstat(target).st_ino)
        return real_listdir(target, *args, **kwargs)

    monkeypatch.setattr(logrotate.os, "open", open_spy)
    monkeypatch.setattr(logrotate.os, "listdir", listdir_spy)
    result = LogRotation(context).run()
    monkeypatch.undo()
    expected = [{"folder": "tunnel/logs", "reason": "folder-owner-differs"}]
    assert result["skips"] == expected and summary(paths)["skips"] == expected
    assert [state(path) for path in files] == before
    assert not [path for path in paths.tunnel_logs.iterdir() if ".20261023" in path.name]
    assert not [name for name in opened if os.path.basename(name) in names]
    assert listed and tunnel_logs not in listed


def test_a_wrong_owner_above_a_log_folder_touches_nothing(layout):
    """Step 77(d) 2."""
    paths, context = layout
    files = [planted(paths.prefix / folder.path / name) for folder, name in zip(
        FOLDERS, ("host.log", "standing.log", "agent.out.log", "postgresql-2026-10-22_000000.log",
                  "postmaster.out.log", "ollama.err.log", "cloudflared.out.log",
                  "standing.err.log"), strict=True)]
    before = [(path.read_bytes(), path.lstat().st_ino) for path in files]
    context.root_uid = os.getuid() + 1
    result = LogRotation(context).run()
    assert result["skips"] == [{"folder": folder.path, "reason": "prefix-owner-differs"}
                               for folder in FOLDERS]
    assert result["folders"] == 0
    assert [(path.read_bytes(), path.lstat().st_ino) for path in files] == before
    context.root_uid = os.getuid()
    (paths.prefix / "tunnel").chmod(0o777)
    result = LogRotation(context).run()
    assert result["skips"] == [{"folder": "tunnel/logs", "reason": "folder-owner-differs"}]
    assert (paths.tunnel_logs / "cloudflared.out.log").read_bytes() == b"a log line\n"


def test_a_link_planted_under_a_logs_name_is_skipped_and_its_target_untouched(layout,
                                                                              tmp_path):
    """Step 77(d) 3."""
    paths, context = layout
    target = planted(tmp_path / "outside" / "kept.log", b"not a log of ours\n")
    before = state(target)
    moved, copied = paths.profile / "logs" / "host.log", paths.tunnel_logs / "cloudflared.out.log"
    moved.symlink_to(target)
    copied.symlink_to(target)
    result = LogRotation(context).run()
    assert result["skips"] == [{"folder": "profile/logs", "reason": "file-link-or-unopenable"},
                               {"folder": "tunnel/logs", "reason": "file-link-or-unopenable"}]
    assert state(target) == before
    assert moved.is_symlink() and copied.is_symlink()
    assert not (paths.profile / "logs" / "host.log.20261023").exists()
    assert not (paths.tunnel_logs / "cloudflared.out.log.20261023").exists()


def test_expiry_never_deletes_through_a_link_or_a_hard_linked_copy(layout, tmp_path):
    """Step 77(d) 4."""
    paths, context = layout
    logs = paths.scheduler / "logs"
    outside = planted(tmp_path / "outside" / "target.log", b"outside\n")
    link = logs / "standing.log.20261001"
    link.symlink_to(outside)
    hard = planted(logs / "standing.out.log.20261001", b"hard-linked copy\n")
    os.link(hard, tmp_path / "outside" / "second-name")
    plain = planted(logs / "standing.err.log.20261001", b"plain copy\n")
    result = LogRotation(context).run()
    assert result["skips"] == [{"folder": "scheduler/logs", "reason": "expiry-refused"}] * 2
    assert link.is_symlink() and outside.read_bytes() == b"outside\n"
    assert hard.read_bytes() == b"hard-linked copy\n" and hard.lstat().st_nlink == 2
    assert not plain.exists() and result["deleted"] == 1


def test_postgresqls_dated_files_are_only_deleted_after_14_days(layout):
    """Step 77(d) 5, at NOW 2026-10-23 03:00 UTC."""
    paths, context = layout
    folder = paths.postgres_data / "log"
    kept = {
        "postgresql-2026-10-09_040000.log": dt.datetime(2026, 10, 9, 4, 0, tzinfo=dt.UTC),
        "postgresql-2026-10-09_003000.log": dt.datetime(2026, 10, 9, 0, 30, tzinfo=dt.UTC),
    }
    for name, moment in kept.items():
        at(planted(folder / name), moment)
    assert NOW - kept["postgresql-2026-10-09_040000.log"] == dt.timedelta(days=13, hours=23)
    expired = planted(folder / "postgresql-2026-10-08_120000.log")
    at(expired, dt.datetime(2026, 10, 8, 12, 0, tzinfo=dt.UTC))
    today = planted(folder / "postgresql-2026-10-23_000000.log", b"today's lines\n")
    at(today, dt.datetime(2026, 10, 23, 2, 59, tzinfo=dt.UTC))
    before = {name: (*state(folder / name), (folder / name).lstat().st_mode) for name in kept}
    today_before = (today.lstat().st_ino, today.lstat().st_size)
    result = LogRotation(context).run()
    assert {name: (*state(folder / name), (folder / name).lstat().st_mode)
            for name in kept} == before
    assert not expired.exists()
    assert (today.lstat().st_ino, today.lstat().st_size) == today_before
    assert not (folder / "postgresql-2026-10-23_000000.log.20261023").exists()
    assert (result["deleted"], result["copied"], result["moved"]) == (1, 0, 0)


def test_only_the_fixed_folders_are_touched(layout):
    """Step 77(d) 6."""
    paths, context = layout
    assert FOLDERS == (
        LogFolder("profile/logs", "service", 0, "own"),
        LogFolder("scheduler/logs", "scheduler", 0, "own"),
        LogFolder("backup-agent/logs", "backup", 0, "held"),
        LogFolder("postgres/data/log", "database", 0, "dated"),
        LogFolder("postgres/logs", "database", 0, "held"),
        LogFolder("models-state/logs", "models", 0, "held"),
        LogFolder("tunnel/logs", "tunnel", 1, "held"),
        LogFolder("control/logs", "root", 0, "held"),
    )
    untouched = [planted(paths.prefix / relative) for relative in (
        "profile/ledger/ledger.jsonl", "availability/2026-10.jsonl",
        "profile/evidence/latency/2026-10-22.jsonl", "scheduler/healthchecks.json",
        "profile/stray.log", "models-state/ollama.log", "postgres/data/postmaster.log",
        "profile/logs/notes.txt")]
    before = [state(path) for path in untouched]
    dated = planted(paths.postgres_data / "log" / "postgresql-2026-10-22_000000.log")
    at(dated, NOW - dt.timedelta(hours=27))
    dated_before = state(dated)[1:]
    LogRotation(context).run()
    assert [state(path) for path in untouched] == before
    assert state(dated)[1:] == dated_before
    assert not (paths.postgres_data / "log" / "postgresql-2026-10-22_000000.log.20261023"
                ).exists()


def test_a_planted_folder_list_is_never_read(layout, capsys, monkeypatch):
    """Step 77(d) 7: neither a rotation whose context is built after the plant, nor the
    job's own entry, reads the list."""
    from docsuri_ops import logrotate
    from docsuri_ops.arrangement import render

    paths, fixture_context = layout
    # The list in the root job's own rendered form, with two more held folders of the
    # test's account appended: a run honouring it would rotate 10 folders.
    listed = json.loads(render.render_rotation(paths).content)
    listed["folders"] = [*listed["folders"], *(
        {"path": path, "account": "service", "ownedFrom": 0, "kind": "held"}
        for path in ("profile/ledger", "availability"))]
    planted(paths.logrotate_folders, json.dumps(listed, sort_keys=True).encode(), mode=0o666)
    # Files a read folder list would rotate: a held log in each named folder.
    files = [planted(paths.prefix / relative, b"would be copied\n") for relative in (
        "profile/ledger/ledger.jsonl", "profile/ledger/ledger.out.log",
        "availability/2026-10.jsonl", "availability/standing.out.log")]
    before = [(path.read_bytes(), path.lstat().st_ino) for path in files]

    def fresh_context() -> RotationContext:
        # Built after the plant and with no folders argument, so a read of the list
        # where a context is built would find the file.
        return RotationContext(paths=paths, accounts=fixture_context.accounts,
                               root_uid=fixture_context.root_uid,
                               clock=fixture_context.clock)

    result = LogRotation(fresh_context()).run()
    assert result["folders"] == len(FOLDERS) == 8
    assert [(path.read_bytes(), path.lstat().st_ino) for path in files] == before
    # The job's own entry, over the same layout, with the names it refuses removed.
    monkeypatch.setattr(logrotate, "RotationContext", fresh_context)
    for name in [name for name in os.environ
                 if name.startswith(("PYTHON", "DYLD_", "LD_"))]:
        monkeypatch.delenv(name)
    capsys.readouterr()
    assert logrotate.main([]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["ok"] is True and printed["folders"] == len(FOLDERS) == 8
    assert [(path.read_bytes(), path.lstat().st_ino) for path in files] == before
    assert logrotate.main(["profile/ledger"]) == 2
    assert capsys.readouterr().out == '{"ok": false, "reason": "invocation-refused"}\n'


def test_the_postmasters_launchd_output_is_rotated_as_decided(layout):
    """Step 77(d) 8 (L1-16)."""
    paths, context = layout
    logs = paths.prefix / "postgres" / "logs"
    held = {name: planted(logs / name, f"{name} lines\n".encode())
            for name in ("postmaster.out.log", "postmaster.err.log")}
    inodes = {name: path.lstat().st_ino for name, path in held.items()}
    old = planted(logs / "postmaster.out.log.20261005", b"an old copy\n")
    dated = planted(paths.postgres_data / "log" / "postgresql-2026-10-22_000000.log")
    result = LogRotation(context).run()
    for name, path in held.items():
        copy = logs / f"{name}.20261023"
        assert copy.read_bytes() == f"{name} lines\n".encode()
        assert stat.S_IMODE(copy.lstat().st_mode) == 0o600
        assert path.lstat().st_ino == inodes[name] and path.lstat().st_size == 0
    assert not old.exists()
    assert not (dated.parent / f"{dated.name}.20261023").exists()
    assert (result["copied"], result["deleted"]) == (2, 1)
