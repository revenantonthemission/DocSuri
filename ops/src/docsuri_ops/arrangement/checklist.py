"""The by-hand steps and the installation log (U8 plan Step 37; Workflow 20,
infrastructure-specification § 4, NFR3.9).

- **The checklist.** Every step that needs your eyes or a login (Cloudflare's
  dashboard, healthchecks.io, a restart) is an item the installer waits on: it shows the
  item's instruction, waits for your confirmation and records only the item and its
  outcome, never anything you typed. An item that needs a value (the healthchecks.io
  ping addresses) takes it through `ask_secret`, hands it straight to the step that
  writes its holder's file, and records only that it was entered.
- **The installation log** (`profile/evidence/installation-log.jsonl`): one JSON line per
  step, with only registered fields, each a fixed key, a path, a version, a count or a
  digest, so it can never hold a password, passphrase, token or certificate content.
"""

from __future__ import annotations

import datetime as dt
import errno
import json
import os
import re
import stat
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

ITEMS = {
    "other-tunnel-without-certificate": "Move the Cloudflare certificate aside, restart "
    "dev.rvnnt.tunnel and confirm it connects by name with its credentials file.",
    "old-certificate-revoked": "In Cloudflare's dashboard, delete the API token of the "
    "certificate your login account holds, and confirm a tunnel listing made with it is "
    "refused.",
    "new-certificate-issued": "As root, issue the new certificate into the root-only folder "
    "the installer named (cloudflared tunnel login).",
    "hostnames-routed": "Move docsuri.rvnnt.dev and ssh.rvnnt.dev to the new tunnel.",
    "old-tunnel-deleted": "Delete the old tunnel at Cloudflare and confirm, with the new "
    "certificate, that it is gone.",
    "new-certificate-revoked": "Revoke the new certificate's API token and confirm a "
    "listing made with it is refused.",
    "no-certificate-token-left": "Confirm in the dashboard that neither certificate's API "
    "token remains.",
    "hostname-settings": "Set Always Use HTTPS, minimum TLS 1.2, and turn off Rocket "
    "Loader, Email Address Obfuscation, Web Analytics and Zaraz for docsuri.rvnnt.dev.",
    "healthchecks-created": "Create the three healthchecks.io checks (heartbeat: 5 minutes "
    "with 5 minutes' grace; backup: 1 day with 2 hours; verification: 7 days with 6 hours).",
    "v1-model-calls-answer": "Confirm v1's model calls answer at 127.0.0.1:11434 from the "
    "system job.",
    "volume-passphrase-changed": "Run `diskutil apfs changePassphrase DocSuri_Backup -user "
    "disk`, entering the old passphrase and, as the new one, the passphrase `sudo security "
    "find-generic-password -s DocSuri_Backup -w` shows.",
    "volume-passphrase-saved": "Save the backup volume's new passphrase in your password "
    "manager.",
    "login-keychain-item-deleted": "Delete the backup volume's item from your login "
    "keychain.",
    "v2-stopped-in-person": "Stop org.docsuri.v2.host, .workers and .scheduler in person "
    "with the operator tool's service control, once per label: `echo '{}' | "
    "/Library/DocSuri/release/.venv/bin/python -I -m docsuri_ops.u8_platform service stop "
    "<label> --production`. PlatformControl binds each stop's receipt before the stop "
    "record is written, and the record cites it.",
    "maintenance-routed": "Route the public address to the maintenance server.",
    "authorized-restart": "Restart this Mac with an authorized restart (fdesetup "
    "authrestart) and log in once every job is back.",
    "v1-answers-again": "Confirm v1's health answers locally, then route the public "
    "address back to v1.",
    "first-rehearsal-database": "Run `echo '{}' | /Library/DocSuri/release/.venv/bin/python "
    "-I -m docsuri_ops.u8_platform cutover begin --production`, which creates the "
    "rehearsal database the first manifest names and restarts v2 on it.",
}
OUTCOMES = ("confirmed", "declined")
LOG_FIELDS = {"ts", "phase", "step", "outcome", "target", "version", "count", "sha256",
              "reason", "item", "actor"}
_KEY = re.compile(r"[a-z0-9][a-z0-9.:_-]{0,79}")
_DIGEST = re.compile(r"[0-9a-f]{64}")
_TARGET = re.compile(r"[A-Za-z0-9/._ -]{1,240}")


class NotConfirmed(RuntimeError):
    """A by-hand step was not confirmed; the installer stops there."""

    def __init__(self, item: str):
        super().__init__(item)
        self.item = item


class LogRefused(OSError):
    """The installation log's place holds a link (or another file than the log): nothing
    was written and nothing was given to anyone. The message is a fixed key."""


LOG_IS_A_LINK = "installation-log-is-a-link"
LOG_FOLDER_IS_A_LINK = "installation-log-folder-is-a-link"
LOG_NOT_ITS_OWN_FILE = "installation-log-not-its-own-file"
_LINK_ERRORS = (errno.ELOOP, errno.ENOTDIR)


class InstallationLog:
    """Append-only JSON lines in the profile's evidence folder; refuses any field or value
    outside its registered forms, so nothing secret can be written to it.

    The log lies in a folder its holder (the service account) owns, so the holder could
    put a link at the log's name or at a folder on the way. The log is therefore reached
    only through folder descriptors, for writing and for reading alike: `base` (the
    root-owned prefix, always given) is opened, every folder below it is opened with
    `O_NOFOLLOW`, and the file is created relative to the last one with
    `O_EXCL | O_NOFOLLOW`, or read from it with `O_NOFOLLOW | O_NONBLOCK`. Only a file
    this call created is given to its holder, through its own descriptor, before it is
    closed. A link at the name or at any folder below `base`, and a file that is not a
    regular file with one name (a hard link, a FIFO, a socket, a device), are refused with
    `LogRefused`, nothing read, written or given."""

    def __init__(self, path: Path, *, clock: Callable[[], dt.datetime], base: Path,
                 owner: Callable[[int], None] | None = None):
        """`base` is the root-owned folder the no-link walk starts from; it has no
        default, so no caller can lose the walk by leaving it out. `owner(descriptor)`
        gives a newly created log to its holder (the service account, whose profile it
        sits in, so the production loader's custody check holds), through the new file's
        own descriptor; it never follows a path."""
        self.path, self.clock, self.owner, self.base = path, clock, owner, base
        self._folders = path.parent.relative_to(self.base).parts

    @staticmethod
    def _check(name: str, value: object) -> None:
        if name not in LOG_FIELDS:
            raise ValueError("unregistered installation-log field")
        if name in ("count", "version"):
            if type(value) is not int or value < 0:
                raise ValueError("installation-log number outside its form")
        elif name == "sha256":
            if not isinstance(value, str) or not _DIGEST.fullmatch(value):
                raise ValueError("installation-log digest outside its form")
        elif name == "target":
            if not isinstance(value, str) or not _TARGET.fullmatch(value):
                raise ValueError("installation-log target outside its form")
        elif name != "ts":
            if not isinstance(value, str) or not _KEY.fullmatch(value):
                raise ValueError("installation-log key outside its form")

    def write(self, phase: str, step: str, outcome: str, **fields) -> dict:
        line = {"ts": self.clock().astimezone(dt.UTC).isoformat(timespec="seconds"),
                "phase": phase, "step": step, "outcome": outcome, **fields}
        for name, value in line.items():
            self._check(name, value)
        data = json.dumps(line, sort_keys=True).encode() + b"\n"
        folder = self._open_folder()
        try:
            descriptor, created = self._open_file(folder)
        finally:
            os.close(folder)
        try:
            if created and self.owner is not None:
                self.owner(descriptor)
            _write_all(descriptor, data)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        return line

    def _open_folder(self, *, create: bool = True) -> int:
        """The log's folder as a descriptor: `base` is opened (made when missing and
        `create`, as the root-owned prefix), then each folder below it (made when missing
        and `create`) is opened relative to its parent with `O_NOFOLLOW`, so a link at
        any of them is refused. Without `create`, a missing folder raises
        `FileNotFoundError`."""
        if create:
            self.base.mkdir(parents=True, exist_ok=True)
        current = os.open(self.base, os.O_RDONLY | os.O_DIRECTORY)
        try:
            for name in self._folders:
                if create:
                    try:
                        os.mkdir(name, 0o777, dir_fd=current)
                    except FileExistsError:
                        pass
                try:
                    child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                    dir_fd=current)
                except OSError as error:
                    if error.errno in _LINK_ERRORS:
                        raise LogRefused(LOG_FOLDER_IS_A_LINK) from None
                    raise
                os.close(current)
                current = child
        except BaseException:
            os.close(current)
            raise
        return current

    def _open_file(self, folder: int) -> tuple[int, bool]:
        """The log relative to its folder's descriptor: created new at 0600 (`O_EXCL`,
        which never follows a link), or, only when that reports it exists, the existing
        file opened without following a link. Either must be a regular file with one name;
        `created` comes from `O_EXCL`, never from a separate look at the path."""
        flags = os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW
        name = self.path.name
        try:
            descriptor = os.open(name, flags | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=folder)
            created = True
        except FileExistsError:
            try:
                # O_NONBLOCK: a planted FIFO is refused at once instead of waiting.
                descriptor = os.open(name, flags | os.O_NONBLOCK, dir_fd=folder)
            except OSError as error:
                raise _refusal(error) from None
            created = False
        _own_file_or_close(descriptor)
        return descriptor, created

    def lines(self) -> list[dict]:
        """Every line of the log, read through the same no-link folder walk as `write`
        and an `O_RDONLY | O_NOFOLLOW | O_NONBLOCK` open relative to the folder's
        descriptor; a link, or a file that is not a regular file with one name, is refused
        with the same keys and never read. No log (or no folder yet) reads as none."""
        try:
            folder = self._open_folder(create=False)
        except FileNotFoundError:
            return []
        try:
            try:
                descriptor = os.open(self.path.name,
                                     os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                                     dir_fd=folder)
            except FileNotFoundError:
                return []
            except OSError as error:
                raise _refusal(error) from None
        finally:
            os.close(folder)
        _own_file_or_close(descriptor)  # closes it when it refuses
        try:
            raw = _read_all(descriptor).decode("utf-8")
        finally:
            os.close(descriptor)
        return [json.loads(line) for line in raw.splitlines() if line.strip()]


# A UNIX-domain socket answers open(2) with ENXIO on Linux and EOPNOTSUPP on macOS; a FIFO
# opened for writing without a reader answers ENXIO; a folder answers EISDIR.
_NOT_ITS_OWN_FILE_ERRORS = (errno.ENXIO, errno.EISDIR, errno.EOPNOTSUPP)


def _refusal(error: OSError) -> OSError:
    """The fixed refusal for an open of the log's name that met another thing than the
    log, or the error itself when it is none of those."""
    if error.errno == errno.ELOOP:
        return LogRefused(LOG_IS_A_LINK)
    if error.errno in _NOT_ITS_OWN_FILE_ERRORS:
        return LogRefused(LOG_NOT_ITS_OWN_FILE)
    return error


def _own_file_or_close(descriptor: int) -> None:
    """Refuse (closing the descriptor) anything but a regular file with exactly one name."""
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise LogRefused(LOG_NOT_ITS_OWN_FILE)
    except BaseException:
        os.close(descriptor)
        raise


def _write_all(descriptor: int, data: bytes) -> None:
    """Write every byte: `os.write` may write fewer (a full disk partway through), and a
    cut line would join the next one."""
    view = memoryview(data)
    while view:
        written = os.write(descriptor, view)
        if written <= 0:
            raise OSError(errno.EIO, "installation-log-short-write")
        view = view[written:]


def _read_all(descriptor: int) -> bytes:
    chunks = []
    while chunk := os.read(descriptor, 65536):
        chunks.append(chunk)
    return b"".join(chunks)


@dataclass
class Checklist:
    """`ask(item, instruction) -> bool` waits for your confirmation; `ask_secret(item,
    instruction) -> str` takes a value without echo. Neither answer is ever logged."""

    log: InstallationLog
    ask: Callable[[str, str], bool]
    ask_secret: Callable[[str, str], str] | None = None
    done: set | None = None

    def __post_init__(self) -> None:
        if self.done is None:
            self.done = {line["item"] for line in self.log.lines()
                         if line.get("step") == "checklist" and line.get("outcome") == "confirmed"
                         and "item" in line}

    def is_done(self, item: str) -> bool:
        return item in self.done

    def wait(self, phase: str, item: str) -> None:
        """Wait for one item; a declined item stops the installer (the next run asks
        again). An item confirmed in an earlier run is not asked again."""
        if item not in ITEMS:
            raise ValueError("unknown checklist item")
        if item in self.done:
            return
        confirmed = bool(self.ask(item, ITEMS[item]))
        self.log.write(phase, "checklist", OUTCOMES[0] if confirmed else OUTCOMES[1], item=item)
        if not confirmed:
            raise NotConfirmed(item)
        self.done.add(item)

    def value(self, phase: str, item: str, instruction: str) -> str:
        """A value only you have (a ping address): taken without echo, recorded only as
        entered."""
        if self.ask_secret is None:
            raise NotConfirmed(item)
        value = self.ask_secret(item, instruction)
        self.log.write(phase, "checklist-value", "entered" if value else "declined", item=item)
        if not value:
            raise NotConfirmed(item)
        return value
