"""Log rotation (U8 plan Step 35; D11, security-design § 7.3, observability-design § 7;
R-20, R-21).

`docsuri-logrotate`, the root job `org.docsuri.v2.logrotate` at 03:00, over the fixed list
of log folders below (part of the root-owned release). It keeps 14 days:

- **Reaching a folder.** Each folder is opened from the prefix one component at a time,
  with `O_DIRECTORY | O_NOFOLLOW`, and the owner is checked at each step: root above the
  account's folder, the account at and below it. A folder, or one above it, that is a
  link or has the wrong owner is skipped and recorded (R-20); nothing in it is read.
- **Opening a file.** Only relative to the folder's descriptor (`openat`), with
  `O_NOFOLLOW | O_NONBLOCK`, so a pipe planted under a log's name cannot make the open
  wait; then, through the descriptor, it must be a regular file with one link owned by
  the folder's account. Anything else is skipped and recorded (R-21).
- **v2's own logs** (`<process>.log`, written through `WatchedFileHandler`) are moved
  aside with `renameat` to `<name>.<YYYYMMDD>`; the process reopens a new file, so
  nothing written is lost.
- **Files launchd holds open** (each job's `.out.log` and `.err.log`, and the folders of
  the backup agent, the postgres job's launchd output (`postgres/logs/`, L1-16), the
  model runtime, the tunnel and the root jobs) are copied through
  the descriptor to the end into a new `<name>.<YYYYMMDD>` (`O_CREAT | O_EXCL |
  O_NOFOLLOW`, owner and mode 0600 set on the descriptor); the size is checked once more
  and whatever arrived during the copy is copied too and counted; then the file is
  truncated through the same descriptor after confirming it is still the same file
  (device and inode). The one call between that check and the truncation is the
  accepted loss nothing can count.
- **PostgreSQL's dated files** are never copied or truncated, only deleted after 14 days.
- **Expiry.** Moved files and copies older than 14 days are deleted under the same rules.

Each run writes one summary line to `control/logs/logrotate.jsonl`: the folders done, the
files moved and copied, the bytes written during copies, the files deleted, and each skip
with its folder and fixed reason key.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import stat
import sys
from collections.abc import Callable
from dataclasses import dataclass, field

from docsuri_ops.arrangement.paths import Accounts, ArrangementPaths

RETENTION = dt.timedelta(days=14)
CHUNK = 64 * 1024
SUMMARY = "logrotate.jsonl"
OWN_LOG = re.compile(r"(host|workers|scheduler|maintenance|standing)\.log")
HELD_LOG = re.compile(r"[A-Za-z0-9._-]+\.(out|err)\.log|[A-Za-z0-9_-]+\.log")
ROTATED = re.compile(r"(?P<base>[A-Za-z0-9._-]+\.log)\.(?P<day>\d{8})(?:-\d+)?")
DATED = re.compile(r"postgresql-\d{4}-\d{2}-\d{2}_\d{6}\.(log|csv|json)")


@dataclass(frozen=True)
class LogFolder:
    """One folder of the fixed list: its components from the prefix, the account that
    owns it, from which component that account owns the path, and its kind."""

    path: str
    account: str  # a field of `Accounts`, or "root"
    owned_from: int
    kind: str  # "own" (v2's own logs and launchd's), "held" (launchd's), "dated"


FOLDERS = (
    LogFolder("profile/logs", "service", 0, "own"),
    LogFolder("scheduler/logs", "scheduler", 0, "own"),
    LogFolder("backup-agent/logs", "backup", 0, "held"),
    LogFolder("postgres/data/log", "database", 0, "dated"),
    LogFolder("postgres/logs", "database", 0, "held"),
    LogFolder("models-state/logs", "models", 0, "held"),
    LogFolder("tunnel/logs", "tunnel", 1, "held"),
    LogFolder("control/logs", "root", 0, "held"),
)


class Skipped(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


@dataclass
class RotationContext:
    paths: ArrangementPaths = field(default_factory=ArrangementPaths)
    accounts: Accounts = field(default_factory=Accounts)
    root_uid: int = 0
    clock: Callable[[], dt.datetime] = _now
    folders: tuple[LogFolder, ...] = FOLDERS
    # Tests only: called after each chunk copied, so a write can land during the copy.
    on_chunk: Callable[[int], None] | None = None

    def uid_of(self, account: str) -> int:
        if account == "root":
            return self.root_uid
        return getattr(self.accounts, account).uid


@dataclass
class Summary:
    folders: int = 0
    moved: int = 0
    copied: int = 0
    bytes_during_copy: int = 0
    deleted: int = 0
    skips: list = field(default_factory=list)

    def as_dict(self, at: dt.datetime) -> dict:
        return {"ts": at.isoformat(timespec="seconds"), "folders": self.folders,
                "moved": self.moved, "copied": self.copied,
                "bytesDuringCopy": self.bytes_during_copy, "deleted": self.deleted,
                "skips": self.skips}


class LogRotation:
    def __init__(self, context: RotationContext):
        self.context = context
        self.summary = Summary()

    # --- reaching a folder (R-20) -----------------------------------------------------

    def open_folder(self, folder: LogFolder) -> int:
        """The folder's descriptor, reached one component at a time without following a
        link, the owner checked at every step."""
        account = self.context.uid_of(folder.account)
        root = self.context.root_uid
        descriptor = os.open(self.context.paths.prefix, os.O_RDONLY | os.O_DIRECTORY |
                             os.O_NOFOLLOW)
        try:
            if os.fstat(descriptor).st_uid != root:
                raise Skipped("prefix-owner-differs")
            for index, part in enumerate(folder.path.split("/")):
                try:
                    child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                    dir_fd=descriptor)
                except OSError:
                    raise Skipped("folder-link-or-missing") from None
                os.close(descriptor)
                descriptor = child
                expected = account if index >= folder.owned_from else root
                info = os.fstat(descriptor)
                if info.st_uid != expected or info.st_mode & 0o022:
                    raise Skipped("folder-owner-differs")
            return descriptor
        except BaseException:
            os.close(descriptor)
            raise

    # --- opening a file (R-21) ----------------------------------------------------------

    def open_log(self, folder_fd: int, name: str, owner: int, *, write: bool) -> int:
        flags = (os.O_RDWR if write else os.O_RDONLY) | os.O_NOFOLLOW | os.O_NONBLOCK
        try:
            descriptor = os.open(name, flags, dir_fd=folder_fd)
        except OSError:
            raise Skipped("file-link-or-unopenable") from None
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            os.close(descriptor)
            raise Skipped("not-a-regular-file")
        if info.st_nlink != 1:
            os.close(descriptor)
            raise Skipped("hard-link")
        if info.st_uid != owner:
            os.close(descriptor)
            raise Skipped("file-owner-differs")
        return descriptor

    def _target(self, folder_fd: int, name: str, day: str) -> str:
        candidate, index = f"{name}.{day}", 1
        while True:
            try:
                os.stat(candidate, dir_fd=folder_fd, follow_symlinks=False)
            except FileNotFoundError:
                return candidate
            candidate, index = f"{name}.{day}-{index}", index + 1

    # --- the three ways ---------------------------------------------------------------

    def move_aside(self, folder_fd: int, name: str, owner: int, day: str) -> None:
        descriptor = self.open_log(folder_fd, name, owner, write=False)
        os.close(descriptor)
        os.rename(name, self._target(folder_fd, name, day), src_dir_fd=folder_fd,
                  dst_dir_fd=folder_fd)
        self.summary.moved += 1

    def copy_truncate(self, folder_fd: int, name: str, owner: int, day: str) -> int:
        """Copy to the end, count what arrived during the copy, truncate the same file."""
        source = self.open_log(folder_fd, name, owner, write=True)
        try:
            start = os.fstat(source).st_size
            if start == 0:
                return 0
            target = os.open(self._target(folder_fd, name, day),
                             os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600,
                             dir_fd=folder_fd)
            try:
                os.fchmod(target, 0o600)
                if os.getuid() == 0:
                    os.fchown(target, owner, -1)
                copied = self._copy(source, target, 0)
                after = os.fstat(source).st_size
                if after > copied:
                    copied = self._copy(source, target, copied)
                os.fsync(target)
            finally:
                os.close(target)
            current = os.stat(name, dir_fd=folder_fd, follow_symlinks=False)
            mine = os.fstat(source)
            if (current.st_dev, current.st_ino) != (mine.st_dev, mine.st_ino):
                raise Skipped("file-replaced-during-copy")
            os.ftruncate(source, 0)
            during = copied - start
            self.summary.copied += 1
            self.summary.bytes_during_copy += during
            return during
        finally:
            os.close(source)

    def _copy(self, source: int, target: int, offset: int) -> int:
        position = offset
        while True:
            block = os.pread(source, CHUNK, position)
            if not block:
                return position
            os.write(target, block)
            position += len(block)
            if self.context.on_chunk is not None:
                self.context.on_chunk(position)

    def expire(self, folder_fd: int, owner: int, folder: LogFolder) -> None:
        today = self.context.clock().date()
        for name in sorted(os.listdir(folder_fd)):
            matched = ROTATED.fullmatch(name)
            dated = DATED.fullmatch(name) if folder.kind == "dated" else None
            if matched is None and dated is None:
                continue
            try:
                info = os.stat(name, dir_fd=folder_fd, follow_symlinks=False)
            except FileNotFoundError:
                continue
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != owner:
                self._skip(folder, "expiry-refused")
                continue
            if matched is not None:
                moment = dt.datetime.strptime(matched.group("day"), "%Y%m%d").date()
            else:
                moment = dt.datetime.fromtimestamp(info.st_mtime, dt.UTC).date()
            if today - moment > RETENTION:
                os.unlink(name, dir_fd=folder_fd)
                self.summary.deleted += 1

    # --- the run ------------------------------------------------------------------------

    def _skip(self, folder: LogFolder, reason: str) -> None:
        self.summary.skips.append({"folder": folder.path, "reason": reason})

    def rotate(self, folder: LogFolder) -> None:
        try:
            folder_fd = self.open_folder(folder)
        except Skipped as skipped:
            self._skip(folder, skipped.reason)
            return
        try:
            owner = self.context.uid_of(folder.account)
            day = self.context.clock().strftime("%Y%m%d")
            if folder.kind != "dated":
                for name in sorted(os.listdir(folder_fd)):
                    if name == SUMMARY or ROTATED.fullmatch(name):
                        continue
                    try:
                        if folder.kind == "own" and OWN_LOG.fullmatch(name):
                            self.move_aside(folder_fd, name, owner, day)
                        elif HELD_LOG.fullmatch(name):
                            self.copy_truncate(folder_fd, name, owner, day)
                    except Skipped as skipped:
                        self._skip(folder, skipped.reason)
            self.expire(folder_fd, owner, folder)
            self.summary.folders += 1
        finally:
            os.close(folder_fd)

    def run(self) -> dict:
        for folder in self.context.folders:
            self.rotate(folder)
        line = self.summary.as_dict(self.context.clock())
        self._write_summary(line)
        return line

    def _write_summary(self, line: dict) -> None:
        folder = self.context.paths.control_logs
        try:
            descriptor = os.open(folder / SUMMARY,
                                 os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
        except OSError:
            return  # the run still reports its line on standard output
        try:
            os.write(descriptor, json.dumps(line, sort_keys=True).encode() + b"\n")
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if arguments or any(name.startswith(("PYTHON", "DYLD_", "LD_")) for name in os.environ):
        print(json.dumps({"ok": False, "reason": "invocation-refused"}))
        return 2
    print(json.dumps({"ok": True, **LogRotation(RotationContext()).run()}))
    return 0
