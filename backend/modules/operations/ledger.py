"""The operations ledger's file layer (U8 plan Step 7; BR4.6, BR6.10, NFR4.3).

A ledger is a folder holding three files:

- `ledger.jsonl`: one entry per line, `{seq, prev, kind, at, record}` in RFC 8785
  canonical JSON, each entry chained to the one before it by the SHA-256 of that
  entry's canonical bytes (`prev` of the first entry is 64 zeros);
- `head.json`: `{count, head}`, the number of entries the ledger vouches for and the
  digest of the last of them;
- `.lock`: the file lock every writer takes.

An append writes and syncs the line first, then replaces the head atomically
(temporary file, sync, rename, folder sync), so a crash between the two leaves a valid
entry beyond the head. On open, and before every append, the chain is verified up to
the head: valid entries beyond the head that chain from it are adopted, a torn last
line (bytes after the final newline) is discarded, and each recovery is itself recorded
as an entry. Anything else raises `LedgerDamaged`, which carries no record content.

The chain mechanism is `ChainedLog`, which the backup agent's catalogue reuses with its
own file names, so both follow the same head, adoption and torn-entry rules. See:
`aidlc/spaces/default/intents/261016-finish-v2-rebuild/construction/u8-service-operations-integration/code-generation/code-generation-plan.md`.
"""

from __future__ import annotations

import datetime as dt
import fcntl
import hashlib
import json
import os
import re
import signal
import stat
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

import rfc8785

from .errors import LedgerDamaged

ZERO = "0" * 64
KIND = re.compile(r"[a-z][a-z0-9.-]{0,63}")
DIGEST = re.compile(r"[0-9a-f]{64}")
MAX_ENTRY_BYTES = 64 * 1024
COPY_CHUNK = 64 * 1024
FOLDER_MODE = 0o700
FILE_MODE = 0o600
ENTRY_FIELDS = frozenset({"seq", "prev", "kind", "at", "record"})
ADOPTED = "ledger.adopted"
DISCARDED = "ledger.discarded"
REPAIRED = "ledger.repaired"
# Beside the ledger's own files: the first finding of damage, which a damaged ledger
# cannot hold itself (BR6.10). The repair records the incident from it.
DAMAGE_MARKER = "damage.json"

Clock = Callable[[], dt.datetime]


@dataclass(frozen=True)
class LogEntry:
    seq: int
    prev: str
    kind: str
    at: str
    record: dict
    digest: str


@dataclass(frozen=True)
class LogHead:
    count: int
    head: str


def canonical(value: object) -> bytes:
    return rfc8785.dumps(value)


def entry_digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def utc_text(moment: dt.datetime) -> str:
    """One fixed timestamp form: UTC, milliseconds, `Z`."""
    if moment.tzinfo is None:
        raise ValueError("the clock must give an aware time")
    return moment.astimezone(dt.UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _write_private(path: Path, payload: bytes) -> None:
    """Write `payload` to a new temporary file, sync it, rename it over `path`, sync
    the folder."""
    pending = path.with_name(path.name + ".pending")
    descriptor = os.open(
        pending, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, FILE_MODE
    )
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(pending, path)
    finally:
        pending.unlink(missing_ok=True)
    _sync_folder(path.parent)


def _sync_folder(folder: Path) -> None:
    descriptor = os.open(folder, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _require_private(path: Path, *, folder: bool) -> None:
    info = path.lstat()
    kind_ok = stat.S_ISDIR(info.st_mode) if folder else stat.S_ISREG(info.st_mode)
    mode = FOLDER_MODE if folder else FILE_MODE
    if not kind_ok or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != mode:
        raise LedgerDamaged("custody-differs")


# --- The first finding of damage (your decision of 2026-10-22, BR6.10) ------------------


def read_damage(folder: Path) -> dict | None:
    """The damage marker beside the ledger, or None when there is none. A marker that is
    not a private regular file of this account, or not of its one form, is ignored: the
    repair then records its own finding instead."""
    marker = folder / DAMAGE_MARKER
    try:
        _require_private(marker, folder=False)
        value = json.loads(marker.read_bytes())
    except (FileNotFoundError, LedgerDamaged, ValueError):
        return None
    if (
        not isinstance(value, dict) or set(value) != {"category", "foundAt"}
        or not isinstance(value["category"], str) or KIND.fullmatch(value["category"]) is None
        or not isinstance(value["foundAt"], str)
    ):
        return None
    try:
        dt.datetime.fromisoformat(value["foundAt"].replace("Z", "+00:00"))
    except ValueError:
        return None
    return value


def record_damage(folder: Path, category: str, found_at: dt.datetime) -> dict:
    """Keep the first finding of damage beside the ledger. The first writer wins across
    processes (`O_EXCL`), so the marker always holds the earliest time; the marker that
    is kept is returned. When the folder cannot take the marker, the finding is returned
    unrecorded and the repair records its own."""
    value = {"category": category, "foundAt": utc_text(found_at)}
    try:
        descriptor = os.open(
            folder / DAMAGE_MARKER, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            FILE_MODE,
        )
    except FileExistsError:
        return read_damage(folder) or value
    except OSError:
        return value
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(canonical(value))
        stream.flush()
        os.fsync(stream.fileno())
    _sync_folder(folder)
    return value


def _file_identity(path: Path) -> tuple | None:
    try:
        info = path.lstat()
    except OSError:
        return None
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)


class ChainedLog:
    """An append-only, digest-chained file with a head and a file lock."""

    def __init__(
        self, folder: Path, *, clock: Clock, log_name: str, head_name: str,
        lock_name: str = ".lock",
    ):
        self.folder = folder
        self.clock = clock
        self.log_path = folder / log_name
        self.head_path = folder / head_name
        self.lock_path = folder / lock_name
        self._mutex = threading.Lock()
        self._lock_fd: int | None = None
        self._head = LogHead(0, ZERO)
        self._offset = 0  # bytes of the log covered by the head
        self._entries: list[LogEntry] = []
        self.recoveries: list[LogEntry] = []

    # --- opening and verification ---------------------------------------------------

    def open(self) -> ChainedLog:
        _require_private(self.folder, folder=True)
        self._lock_fd = os.open(
            self.lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, FILE_MODE
        )
        try:
            _require_private(self.lock_path, folder=False)
            with self._locked():
                self._initialise()
                self._refresh()
        except BaseException:
            self.close()
            raise
        return self

    def close(self) -> None:
        if self._lock_fd is not None:
            os.close(self._lock_fd)
            self._lock_fd = None

    def _locked(self):
        log = self

        class _Guard:
            def __enter__(self):
                log._mutex.acquire()
                try:
                    if log._lock_fd is None:
                        raise LedgerDamaged("closed")
                    fcntl.flock(log._lock_fd, fcntl.LOCK_EX)
                except BaseException:
                    log._mutex.release()
                    raise
                return self

            def __exit__(self, *exc):
                try:
                    if log._lock_fd is not None:
                        fcntl.flock(log._lock_fd, fcntl.LOCK_UN)
                finally:
                    log._mutex.release()

        return _Guard()

    def _initialise(self) -> None:
        """A new log is an empty file and a zero head; a head without its log, or a log
        without its head, is damage."""
        has_log = self.log_path.exists() or self.log_path.is_symlink()
        has_head = self.head_path.exists() or self.head_path.is_symlink()
        if not has_log and not has_head:
            descriptor = os.open(
                self.log_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, FILE_MODE
            )
            os.fsync(descriptor)
            os.close(descriptor)
            _write_private(self.head_path, canonical({"count": 0, "head": ZERO}))
            return
        if not has_log:
            raise LedgerDamaged("log-missing")
        if not has_head:
            raise LedgerDamaged("head-missing")

    def _read_head(self) -> LogHead:
        _require_private(self.head_path, folder=False)
        try:
            raw = self.head_path.read_bytes()
            value = json.loads(raw)
        except (OSError, ValueError):
            raise LedgerDamaged("head-unreadable") from None
        if (
            not isinstance(value, dict)
            or set(value) != {"count", "head"}
            or type(value["count"]) is not int
            or value["count"] < 0
            or not isinstance(value["head"], str)
            or DIGEST.fullmatch(value["head"]) is None
            or canonical(value) != raw
        ):
            raise LedgerDamaged("head-unreadable")
        return LogHead(value["count"], value["head"])

    def _parse(self, raw: bytes, seq: int, prev: str) -> LogEntry:
        try:
            value = json.loads(raw)
        except ValueError:
            raise LedgerDamaged("entry-unreadable") from None
        if (
            not isinstance(value, dict)
            or set(value) != ENTRY_FIELDS
            or canonical(value) != raw
            or value["seq"] != seq
            or value["prev"] != prev
            or not isinstance(value["kind"], str)
            or KIND.fullmatch(value["kind"]) is None
            or not isinstance(value["at"], str)
            or not isinstance(value["record"], dict)
        ):
            raise LedgerDamaged("chain-break")
        return LogEntry(seq, prev, value["kind"], value["at"], value["record"], entry_digest(raw))

    def _refresh(self) -> None:
        """Bring the in-memory chain up to the files: verify up to the head, adopt valid
        entries beyond it, discard a torn last line, and record each recovery."""
        head = self._read_head()
        _require_private(self.log_path, folder=False)
        if head.count < self._head.count:
            raise LedgerDamaged("head-regressed")
        if self.log_path.stat().st_size < self._offset:
            # Bytes this process already verified are gone: cut back underneath it.
            raise LedgerDamaged("truncated")
        with open(self.log_path, "rb") as stream:
            stream.seek(self._offset)
            tail = stream.read()
        complete, _, torn = tail.rpartition(b"\n")
        lines = complete.split(b"\n") if complete else []
        entries = list(self._entries)
        offset = self._offset
        prev = entries[-1].digest if entries else ZERO
        for line in lines:
            if len(line) > MAX_ENTRY_BYTES:
                raise LedgerDamaged("entry-unreadable")
            entry = self._parse(line, len(entries) + 1, prev)
            entries.append(entry)
            prev = entry.digest
            offset += len(line) + 1
        if len(entries) < head.count:
            raise LedgerDamaged("truncated")
        if head.count and entries[head.count - 1].digest != head.head:
            raise LedgerDamaged("head-mismatch")
        if not head.count and head.head != ZERO:
            raise LedgerDamaged("head-mismatch")
        self._entries, self._offset = entries, offset
        adopted = len(entries) - head.count
        self._head = LogHead(len(entries), entries[-1].digest if entries else ZERO)
        if torn:
            # Only bytes after the final newline: an append that never completed.
            with open(self.log_path, "r+b") as stream:
                stream.truncate(offset)
                stream.flush()
                os.fsync(stream.fileno())
            self._append_locked(DISCARDED, {"bytes": len(torn), "atCount": len(entries)})
        if adopted:
            _write_private(self.head_path, canonical(self._head_value()))
            self._append_locked(ADOPTED, {"from": head.count, "to": head.count + adopted})

    def _head_value(self) -> dict:
        return {"count": self._head.count, "head": self._head.head}

    # --- appending ----------------------------------------------------------------------

    def append(self, kind: str, record: dict) -> LogEntry:
        if not isinstance(kind, str) or KIND.fullmatch(kind) is None:
            raise ValueError("entry kind outside the registered form")
        if not isinstance(record, dict):
            raise ValueError("an entry's record must be a mapping")
        with self._locked():
            self._refresh()
            return self._append_locked(kind, record)

    def _append_locked(self, kind: str, record: dict) -> LogEntry:
        seq = self._head.count + 1
        value = {
            "seq": seq, "prev": self._head.head, "kind": kind,
            "at": utc_text(self.clock()), "record": record,
        }
        try:
            raw = canonical(value)
        except (rfc8785.CanonicalizationError, TypeError, ValueError) as error:
            raise ValueError("an entry's record must be canonical JSON") from error
        if len(raw) > MAX_ENTRY_BYTES:
            raise ValueError("entry exceeds its bounded size")
        self._write_line(raw)
        entry = LogEntry(seq, value["prev"], kind, value["at"], record, entry_digest(raw))
        self._entries.append(entry)
        self._offset += len(raw) + 1
        self._head = LogHead(seq, entry.digest)
        self._replace_head()
        if kind in (ADOPTED, DISCARDED):
            self.recoveries.append(entry)
        return entry

    def _write_line(self, raw: bytes) -> None:
        descriptor = os.open(self.log_path, os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW)
        try:
            os.write(descriptor, raw + b"\n")
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def _replace_head(self) -> None:
        _write_private(self.head_path, canonical(self._head_value()))

    # --- reading ------------------------------------------------------------------------

    @property
    def head(self) -> LogHead:
        with self._locked():
            self._refresh()
            return self._head

    def entries(self) -> list[LogEntry]:
        with self._locked():
            self._refresh()
            return list(self._entries)

    def verify(self) -> LogHead:
        """Re-read the whole chain from the start; raises on any damage."""
        with self._locked():
            self._entries, self._offset, self._head = [], 0, LogHead(0, ZERO)
            self._refresh()
            return self._head

    def copy(self, sink: BinaryIO | Callable[[bytes], object]) -> dict:
        """Stream the log up to the head to `sink`, with the stream's SHA-256."""
        write = sink.write if hasattr(sink, "write") else sink
        with self._locked():
            self._refresh()
            remaining, digest, sent = self._offset, hashlib.sha256(), 0
            with open(self.log_path, "rb") as stream:
                while remaining:
                    chunk = stream.read(min(COPY_CHUNK, remaining))
                    if not chunk:
                        raise LedgerDamaged("truncated")
                    write(chunk)
                    digest.update(chunk)
                    remaining -= len(chunk)
                    sent += len(chunk)
            return {
                "count": self._head.count, "head": self._head.head,
                "sha256": digest.hexdigest(), "bytes": sent,
            }

    def iterate(self) -> Iterator[LogEntry]:
        yield from self.entries()

    def entries_after(self, count: int) -> list[LogEntry]:
        """The entries after the first `count`, once the chain is brought up to the
        files; the component folds only what it has not seen."""
        with self._locked():
            self._refresh()
            return list(self._entries[count:])

    @contextmanager
    def transaction(self) -> Iterator[LockedLog]:
        """Hold the lock across a read and the appends that depend on it, so a check
        and its append are one step for every process (BR6.10)."""
        with self._locked():
            self._refresh()
            yield LockedLog(self)


class LockedLog:
    """The log while its lock is held: reads and appends without re-locking."""

    def __init__(self, log: ChainedLog):
        self._log = log

    def entries_after(self, count: int) -> list[LogEntry]:
        return list(self._log._entries[count:])

    def append(self, kind: str, record: dict) -> LogEntry:
        if not isinstance(kind, str) or KIND.fullmatch(kind) is None:
            raise ValueError("entry kind outside the registered form")
        if not isinstance(record, dict):
            raise ValueError("an entry's record must be a mapping")
        return self._log._append_locked(kind, record)

    @property
    def head(self) -> LogHead:
        return self._log._head


class LedgerStore(ChainedLog):
    """The operations ledger in `profile/ledger/` (production) or a test folder."""

    LOG = "ledger.jsonl"
    HEAD = "head.json"

    @classmethod
    def open(cls, folder: Path, *, clock: Clock) -> LedgerStore:  # type: ignore[override]
        store = cls(folder, clock=clock, log_name=cls.LOG, head_name=cls.HEAD)
        ChainedLog.open(store)
        return store

    def append_entry(self, kind: str, record: dict) -> LogEntry:
        """The file layer's append; the component (`Ledger`) adds schemas and revisions."""
        return ChainedLog.append(self, kind, record)


# --- The component (U8 plan Step 13) ----------------------------------------------------


@dataclass(frozen=True)
class Appended:
    """One appended version: its kind, entity key, revision (version count) and entry."""

    kind: str
    key: tuple
    revision: int
    record: dict
    seq: int


class Ledger:
    """ServiceOperations' ledger component: typed records over the file layer.

    `append(kind, record, expect_revision=n)` validates the record against its schema
    and compares the entity's current revision under the file lock, so a stale writer in
    any process appends nothing. A receipt-bearing record is admitted only when every
    receipt it cites has its binding facts (`receipt-facts`) in the ledger already or in
    the same append; whether PlatformControl confirms them is the fixed command's check
    (`ledger_cli`). Each entity's state is the fold of its versions, kept in memory and
    caught up from the chain on every read and append.

    Damage (a chain that no longer verifies up to its head) is sticky: from then on every
    dependent write is refused with `LedgerDamaged` and `check()` reports
    `operations.ledger` unavailable, until the operator repairs the ledger. The first
    finding is kept beside the ledger (`record_damage`), because a damaged ledger cannot
    hold its own incident; the repair records the incident from it. Once the files have
    been replaced by a repair (a `ledger.repaired` entry this process has not seen),
    `check()` reopens the repaired ledger, so a running process recovers without a
    restart."""

    def __init__(self, store: LedgerStore, *, clock: Clock):
        from .ledger_records import Fold

        self.store, self.clock = store, clock
        self._fold = Fold()
        self._folded = 0
        self._mutex = threading.Lock()
        self._local = threading.local()
        self.damaged: str | None = None
        self.damage_found_at: dt.datetime | None = None
        self._damaged_identity: tuple | None = None
        self._repairs_at_damage = 0

    @classmethod
    def open(cls, folder: Path, *, clock: Clock) -> Ledger:
        store = LedgerStore.open(folder, clock=clock)
        ledger = cls(store, clock=clock)
        try:
            ledger._catch_up(store.entries_after(0))
        except BaseException:
            store.close()
            raise
        return ledger

    def close(self) -> None:
        self.store.close()

    # --- damage ----------------------------------------------------------------------

    def _mark(self, category: str) -> None:
        """Damage is sticky from its first finding; that finding is kept beside the
        ledger with its time."""
        if self.damaged is not None:
            return
        self.damaged = category
        if category == "closed":
            return  # a closed ledger in this process is not damage to the files
        self.damage_found_at = self.clock()
        self._damaged_identity = _file_identity(self.store.log_path)
        self._repairs_at_damage = len(self._fold.events.get(REPAIRED, []))
        record_damage(self.store.folder, category, self.damage_found_at)

    def _recover(self) -> bool:
        """Reopen the ledger once a repair has replaced its files: the log is a different
        file, it verifies from the start, and it holds a `ledger.repaired` entry beyond
        the ones this process had folded when the damage was found."""
        from .ledger_records import Fold, RecordRefused

        if self.damaged in (None, "closed"):
            return False
        identity = _file_identity(self.store.log_path)
        if identity is None or identity == self._damaged_identity:
            return False
        try:
            store = LedgerStore.open(self.store.folder, clock=self.clock)
        except LedgerDamaged:
            self._damaged_identity = identity  # these files are damaged too
            return False
        try:
            entries = store.entries_after(0)
            repaired = sum(1 for entry in entries if entry.kind == REPAIRED)
            if repaired <= self._repairs_at_damage:
                raise LedgerDamaged("not-repaired")
            fold = Fold()
            for entry in entries:
                fold.apply(entry.kind, entry.record)
        except (LedgerDamaged, RecordRefused):
            store.close()
            self._damaged_identity = identity
            return False
        with self._mutex:
            previous, self.store = self.store, store
            self._fold, self._folded = fold, len(entries)
            self.damaged, self.damage_found_at, self._damaged_identity = None, None, None
        previous.close()
        return True

    # --- folding -------------------------------------------------------------------

    def _catch_up(self, entries: list[LogEntry]) -> None:
        from .ledger_records import RecordRefused

        with self._mutex:
            for entry in entries:
                if entry.seq <= self._folded:
                    continue  # already folded by a concurrent reader
                if entry.seq != self._folded + 1:
                    self._mark("fold-gap")
                    raise LedgerDamaged("fold-gap")
                try:
                    self._fold.apply(entry.kind, entry.record)
                except RecordRefused:
                    self._mark("record-invalid")
                    raise LedgerDamaged("record-invalid") from None
                self._folded = entry.seq

    def _sync(self) -> None:
        if getattr(self._local, "inside", False):
            # The lock is not re-entrant: a step reads through its view instead.
            raise RuntimeError("a ledger step must read through its locked view")
        if self.damaged is not None:
            raise LedgerDamaged(self.damaged)
        try:
            self._catch_up(self.store.entries_after(self._folded))
        except LedgerDamaged as error:
            self._mark(error.category)
            raise

    # --- reading -------------------------------------------------------------------

    def get(self, kind: str, key) -> dict | None:
        self._sync()
        return self._fold.get(kind, _key(key))

    def revision(self, kind: str, key) -> int:
        self._sync()
        return self._fold.revision(kind, _key(key))

    def records(self, kind: str) -> list[dict]:
        self._sync()
        return self._fold.records(kind)

    def events(self, kind: str) -> list[dict]:
        self._sync()
        return list(self._fold.events.get(kind, []))

    @property
    def head(self) -> LogHead:
        self._sync()
        return self.store.head

    def check(self) -> dict:
        """The `operations.ledger` check: the whole chain is re-read and must reach its
        head; a break anywhere, even in bytes read earlier, is damage from then on. A
        damaged ledger whose files a repair has replaced is reopened here."""
        if self.damaged is not None:
            self._recover()
        try:
            self._sync()
            head = self.store.verify()
        except LedgerDamaged as error:
            self._mark(error.category)
            return {"status": "unavailable", "reasonKey": "ledger-damaged",
                    "category": self.damaged}
        return {"status": "available", "count": head.count, "head": head.head}

    def copy(self, sink) -> dict:
        self._sync()
        return self.store.copy(sink)

    # --- appending -----------------------------------------------------------------

    def append(self, kind: str, record: dict, *, expect_revision: int,
               receipts: tuple[dict, ...] | list[dict] = ()) -> Appended:
        """Append one version of an entity whose current revision is `expect_revision`
        (0 for a new one), with any receipt facts it cites."""
        return self.atomic(
            lambda view: view.append(kind, record, expect_revision=expect_revision,
                                     receipts=receipts)
        )

    def atomic(self, step):
        """Run `step(view)` while the lock is held: its reads see every process's
        appends, and its appends follow them with nothing in between."""
        if self.damaged is not None:
            raise LedgerDamaged(self.damaged)
        if getattr(self._local, "inside", False):
            raise RuntimeError("ledger steps do not nest")
        try:
            with self.store.transaction() as locked:
                self._catch_up(locked.entries_after(self._folded))
                self._local.inside = True
                try:
                    return step(_LockedView(self, locked))
                finally:
                    self._local.inside = False
        except LedgerDamaged as error:
            if error.category != "closed":
                self._mark(error.category)
            raise


def _key(key) -> tuple:
    return tuple(key) if isinstance(key, (tuple, list)) else (key,)


HELD_SIGNALS = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)


@contextmanager
def signals_held() -> Iterator[None]:
    """SIGINT, SIGTERM and SIGHUP held back while a batch is written, so none of them
    lands between two of its writes; a signal that arrives meanwhile is delivered once
    the block ends (review finding, Minor, R18). Python delivers signals to the main
    thread, so only there is anything to hold back."""
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    previous = signal.pthread_sigmask(signal.SIG_BLOCK, HELD_SIGNALS)
    try:
        yield
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, previous)


class _LockedView:
    """The ledger while its lock is held; reads are current for every process."""

    def __init__(self, ledger: Ledger, locked: LockedLog):
        self._ledger, self._locked = ledger, locked

    @property
    def _fold(self):
        return self._ledger._fold

    def get(self, kind: str, key) -> dict | None:
        return self._fold.get(kind, _key(key))

    def revision(self, kind: str, key) -> int:
        return self._fold.revision(kind, _key(key))

    def records(self, kind: str) -> list[dict]:
        return self._fold.records(kind)

    def head(self) -> LogHead:
        """The chain's head while the lock is held: what every read of this step saw."""
        return self._locked.head

    def append_all(self, items) -> list[Appended]:
        """Several appends as one step (review findings, Major, R14; Minor, R18): each
        `(kind, record, expect_revision, receipts)` is checked first, in order, on a
        trial copy of the fold that takes every earlier one (its revision, its version
        rule, its receipt facts, its entry's size), and only when every one passes are
        they written, still under this one lock, with SIGINT, SIGTERM and SIGHUP held
        back until the last is written (`signals_held`). So a refusal of any of them
        writes none, and a signal cannot stop the batch between two writes. What the
        file layer does not promise: each entry is its own write and head update (the
        chain's crash rule), so a disk error between two writes leaves the earlier
        entries committed, a valid prefix the next open adopts; the caller then reads
        the chain again rather than assuming the batch was not written."""
        items = list(items)
        trial = _TrialView(self._ledger, self._locked)
        for kind, record, expected, receipts in items:
            trial.append(kind, record, expect_revision=expected, receipts=receipts)
        with signals_held():
            return [self.append(kind, record, expect_revision=expected, receipts=receipts)
                    for kind, record, expected, receipts in items]

    def append(self, kind: str, record: dict, *, expect_revision: int,
               receipts=()) -> Appended:
        from .errors import OperationsError
        from .ledger_records import RECOVERY_KINDS, RecordRefused, schema_of

        schema = schema_of(kind)
        if kind in RECOVERY_KINDS or not schema.keyed:
            raise RecordRefused("event-kind-not-appendable")
        if type(expect_revision) is not int or expect_revision < 0:
            raise ValueError("expect_revision must be a non-negative integer")
        schema.validate(record)
        key = schema.key_of(record)
        current = self.get(kind, key)
        revision = self.revision(kind, key)
        if revision != expect_revision:
            raise OperationsError("STALE_REVISION", current={"revision": revision})
        if revision + 1 > schema.max_versions:
            raise RecordRefused("version-bound")
        schema.validate_version(current, record)
        if "revision" in schema.fields and kind in ("service-incident", "recovery-request"):
            if record.get("revision") != revision + 1:
                raise RecordRefused("revision-differs", "revision")
        facts = self._receipt_facts(schema, record, receipts)
        for item in facts:
            self._write("receipt-facts", item)
        entry = self._write(kind, record)
        return Appended(kind, key, revision + 1, record, entry.seq)

    def _receipt_facts(self, schema, record: dict, receipts) -> list[dict]:
        """The receipt facts this append must add: every cited receipt needs its facts,
        already in the ledger or given here and identical to any recorded ones."""
        from .ledger_records import RECEIPT_FACTS, RecordRefused

        given = {}
        for item in receipts:
            RECEIPT_FACTS.validate(item)
            given[item["receiptId"]] = item
        adding = []
        for ref in schema.cited_receipts(record):
            known = self.get("receipt-facts", ref)
            if known is not None:
                if ref in given and {
                    k: v for k, v in given[ref].items() if k != "confirmedAt"
                } != {k: v for k, v in known.items() if k != "confirmedAt"}:
                    raise RecordRefused("receipt-facts-differ")
                continue
            if ref not in given:
                raise RecordRefused("receipt-facts-missing")
            adding.append(given[ref])
        return adding

    def _write(self, kind: str, record: dict) -> LogEntry:
        entry = self._locked.append(kind, record)
        self._ledger._catch_up([entry])
        return entry


class _TrialView(_LockedView):
    """`append_all`'s trial: the same checks as an append, on a copy of the fold that
    each trial append updates, and nothing written. The fold's records are never changed
    in place (each version replaces the last), so copying its maps is enough."""

    def __init__(self, ledger: Ledger, locked: LockedLog):
        from .ledger_records import Fold

        super().__init__(ledger, locked)
        fold = ledger._fold
        self._copy = Fold(current=dict(fold.current), revisions=dict(fold.revisions),
                          events={kind: list(items) for kind, items in fold.events.items()},
                          by_kind={kind: dict(items) for kind, items in fold.by_kind.items()})
        self._count, self._head = locked.head.count, locked.head.head

    @property
    def _fold(self):
        return self._copy

    def _write(self, kind: str, record: dict) -> LogEntry:
        # The entry as `_append_locked` would write it, so its form and bounded size are
        # refused here rather than half way through the batch.
        value = {"seq": self._count + 1, "prev": self._head, "kind": kind,
                 "at": utc_text(self._ledger.clock()), "record": record}
        try:
            raw = canonical(value)
        except (rfc8785.CanonicalizationError, TypeError, ValueError) as error:
            raise ValueError("an entry's record must be canonical JSON") from error
        if len(raw) > MAX_ENTRY_BYTES:
            raise ValueError("entry exceeds its bounded size")
        self._copy.apply(kind, record)
        self._count, self._head = self._count + 1, entry_digest(raw)
        return LogEntry(self._count, value["prev"], kind, value["at"], record, self._head)
