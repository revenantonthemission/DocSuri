"""Log rotation as root on macOS (U8 plan Steps 36 and 103(a); security-design § 15 "Logs
(D11)", R-20, R-21).

Run only in `ci.yml`'s `macos-filesystem` job, or through the tool's `arrangement` phase on
this Mac, as root under sudo (`DOCSURI_U8_ARRANGEMENT=1`); the conftest collects this
folder nowhere else. The prefix is a temporary folder made root-owned, each log folder is
given to its account's UID from security-design § 5.1, and a root-only folder stands for
what a planted link could point at.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import logging.handlers
import os
import re
import stat
import sys
import time
from pathlib import Path

import pytest

from docsuri_ops.arrangement.paths import Accounts, ArrangementPaths
from docsuri_ops.logrotate import FOLDERS, LogRotation, RotationContext

NOW = dt.datetime(2026, 10, 23, 3, 0, tzinfo=dt.UTC)
ACCOUNTS = Accounts.standard()


@pytest.fixture(scope="module", autouse=True)
def as_root_on_macos():
    if sys.platform != "darwin" or os.geteuid() != 0:
        pytest.fail("the arrangement tests run as root on macOS (the macos-filesystem job)")


def uid_of(folder) -> int:
    return 0 if folder.account == "root" else getattr(ACCOUNTS, folder.account).uid


@pytest.fixture
def layout(tmp_path):
    prefix = tmp_path / "prefix"
    prefix.mkdir()
    os.chown(tmp_path, 0, 0)
    os.chown(prefix, 0, 0)
    paths = ArrangementPaths.under(prefix)
    for folder in FOLDERS:
        current = prefix
        for index, part in enumerate(folder.path.split("/")):
            current = current / part
            current.mkdir(mode=0o755, exist_ok=True)
            os.chown(current, uid_of(folder) if index >= folder.owned_from else 0, 0)
    root_only = tmp_path / "root-only"
    root_only.mkdir(mode=0o700)
    secret = root_only / "host.log"
    secret.write_text("root's own file\n")
    secret.chmod(0o600)
    return paths, RotationContext(paths=paths, accounts=ACCOUNTS, clock=lambda: NOW), secret


def owned_file(path: Path, uid: int, text: str = "line\n") -> Path:
    path.write_text(text)
    os.chown(path, uid, 0)
    path.chmod(0o600)
    return path


def test_a_linked_folder_and_a_linked_folder_above_it_touch_nothing_in_the_target(layout):
    paths, context, secret = layout
    before = secret.stat()
    logs = paths.profile / "logs"
    logs.rmdir()
    logs.symlink_to(secret.parent)
    os.lchown(logs, ACCOUNTS.service.uid, 0)
    tunnel = paths.prefix / "tunnel"
    for child in tunnel.iterdir():
        child.rmdir()
    tunnel.rmdir()
    tunnel.symlink_to(secret.parent)
    result = LogRotation(context).run()
    skips = {item["folder"]: item["reason"] for item in result["skips"]}
    assert skips["profile/logs"] == "folder-link-or-missing"
    assert skips["tunnel/logs"] == "folder-link-or-missing"
    after = secret.stat()
    assert secret.read_text() == "root's own file\n"
    assert (after.st_size, after.st_mtime_ns, after.st_ino) == (
        before.st_size, before.st_mtime_ns, before.st_ino)
    assert sorted(path.name for path in secret.parent.iterdir()) == ["host.log"]


def test_a_folder_owned_by_the_wrong_account_is_skipped(layout):
    paths, context, _ = layout
    os.chown(paths.scheduler / "logs", ACCOUNTS.service.uid, 0)
    owned_file(paths.scheduler / "logs" / "standing.log", ACCOUNTS.service.uid)
    result = LogRotation(context).run()
    assert {"folder": "scheduler/logs", "reason": "folder-owner-differs"} in result["skips"]
    assert (paths.scheduler / "logs" / "standing.log").exists()


def test_a_fifo_under_a_logs_name_is_skipped_without_stalling(layout):
    paths, context, _ = layout
    fifo = paths.models_state / "logs" / "ollama.out.log"
    os.mkfifo(fifo)
    os.chown(fifo, ACCOUNTS.models.uid, 0)
    started = time.monotonic()
    result = LogRotation(context).run()
    assert time.monotonic() - started < 5
    assert {"folder": "models-state/logs", "reason": "not-a-regular-file"} in result["skips"]


def test_a_hard_link_is_skipped(layout, tmp_path):
    paths, context, secret = layout
    planted = paths.backup_agent / "logs" / "agent.err.log"
    os.link(secret, planted)  # root's file under a log's name
    result = LogRotation(context).run()
    assert {"folder": "backup-agent/logs", "reason": "hard-link"} in result["skips"]
    assert secret.read_text() == "root's own file\n"


def test_a_moved_v2_log_loses_no_line_written_during_the_move(layout):
    paths, context, _ = layout
    log = owned_file(paths.profile / "logs" / "host.log", ACCOUNTS.service.uid, "")
    handler = logging.handlers.WatchedFileHandler(log)
    logger = logging.getLogger("arrangement-rotation")
    logger.addHandler(handler)
    logger.propagate = False
    logger.warning("before")
    LogRotation(context).run()
    logger.warning("after")
    handler.close()
    moved = paths.profile / "logs" / "host.log.20261023"
    assert moved.read_text() == "before\n" and log.read_text() == "after\n"
    assert moved.stat().st_uid == ACCOUNTS.service.uid


def test_copy_then_truncate_records_the_bytes_written_during_the_copy(layout):
    paths, context, _ = layout
    held = owned_file(paths.tunnel_logs / "cloudflared.err.log", ACCOUNTS.tunnel.uid,
                      "y" * 300_000)
    late = b"arrived during the copy\n"
    context.on_chunk = lambda position: position == 65_536 and held.open("ab").write(late)
    result = LogRotation(context).run()
    copy = paths.tunnel_logs / "cloudflared.err.log.20261023"
    assert result["bytesDuringCopy"] == len(late)
    assert copy.read_bytes() == b"y" * 300_000 + late and held.read_bytes() == b""


def last_summary(paths) -> dict:
    return json.loads((paths.control_logs / "logrotate.jsonl").read_text().splitlines()[-1])


def test_a_log_another_account_owns_is_skipped_untouched(layout):
    """Step 103(a): a log owned by another account than its folder's is left as it is on
    the move, the copy and the expiry paths (R-21)."""
    paths, context, _ = layout
    profile = paths.profile / "logs"
    scheduler = paths.scheduler / "logs"
    moved = owned_file(scheduler / "standing.log", ACCOUNTS.service.uid, "standing\n")
    copied = owned_file(profile / "host.err.log", ACCOUNTS.scheduler.uid, "held\n")
    expired = owned_file(profile / "host.log.20261002", ACCOUNTS.scheduler.uid, "expired\n")
    long_ago = (NOW - dt.timedelta(days=21)).timestamp()
    os.utime(expired, (long_ago, long_ago))
    planted = (moved, copied, expired)
    before = {path: (path.read_bytes(), path.stat().st_uid, path.stat().st_mtime_ns)
              for path in planted}
    result = LogRotation(context).run()
    expected = [
        {"folder": "profile/logs", "reason": "file-owner-differs"},
        {"folder": "profile/logs", "reason": "expiry-refused"},
        {"folder": "scheduler/logs", "reason": "file-owner-differs"},
    ]
    assert result["skips"] == expected
    assert last_summary(paths)["skips"] == expected
    for path in planted:
        assert (path.read_bytes(), path.stat().st_uid, path.stat().st_mtime_ns) == before[path]
    assert not (scheduler / "standing.log.20261023").exists()
    assert not (profile / "host.err.log.20261023").exists()


# Step 103(a): one launchd output file in each folder of the fixed list but the dated
# `postgres/data/log`, owned by the folder's account; and the built workers output.
LAUNCHD_OUTPUT = (
    ("profile/logs", "host.err.log", ACCOUNTS.service.uid),
    ("scheduler/logs", "standing.err.log", ACCOUNTS.scheduler.uid),
    ("postgres/logs", "postmaster.err.log", ACCOUNTS.database.uid),
    ("models-state/logs", "ollama.err.log", ACCOUNTS.models.uid),
    ("tunnel/logs", "cloudflared.err.log", ACCOUNTS.tunnel.uid),
    ("backup-agent/logs", "agent.err.log", ACCOUNTS.backup.uid),
    ("control/logs", "logrotate.err.log", 0),
    ("profile/logs", "org.docsuri.v2.workers.out.log", ACCOUNTS.service.uid),
)
DAY_SUFFIX = re.compile(r"\.(\d{8})(?:-\d+)?$")


def test_no_copy_older_than_14_days_remains_and_each_keeps_owner_and_0600(layout):
    paths, context, _ = layout
    logs = paths.profile / "logs"
    old = owned_file(logs / "workers.log.20261001", ACCOUNTS.service.uid)
    kept = owned_file(logs / "workers.log.20261015", ACCOUNTS.service.uid)
    for folder, name, uid in LAUNCHD_OUTPUT:
        owned_file(paths.prefix / folder / name, uid, f"{name}\n")
    host = owned_file(logs / "host.log", ACCOUNTS.service.uid, "host\n")
    inode = host.stat().st_ino
    result = LogRotation(context).run()
    for folder, name, uid in LAUNCHD_OUTPUT:
        copy = paths.prefix / folder / f"{name}.20261023"
        info = copy.stat()
        assert copy.read_text() == f"{name}\n"
        assert info.st_uid == uid and stat.S_IMODE(info.st_mode) == 0o600
        assert (paths.prefix / folder / name).read_bytes() == b""
    moved = logs / "host.log.20261023"
    assert moved.stat().st_ino == inode and moved.stat().st_uid == ACCOUNTS.service.uid
    assert moved.read_text() == "host\n" and not host.exists()
    assert not old.exists() and kept.exists()
    oldest = (NOW - dt.timedelta(days=14)).date()
    for folder in FOLDERS:
        for path in (paths.prefix / folder.path).iterdir():
            day = DAY_SUFFIX.search(path.name)
            if day is not None:
                assert dt.datetime.strptime(day.group(1), "%Y%m%d").date() >= oldest, path
    for line in (result, last_summary(paths)):
        assert (line["copied"], line["moved"], line["deleted"]) == (8, 1, 1)
