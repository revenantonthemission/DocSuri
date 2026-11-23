"""The runtime isolation check (U8 plan Step 35; D10, BR6.12, NFR3.8, NFR8.10, NFR9.9,
security-design § 6.8, observability-design § 8).

`docsuri-isolation-check`, run as root with no argument (the scheduler account reaches
it only through PlatformControl's `platform.isolation.check`, every 5 minutes). Its items,
each in a thread of its own with its own time limit, so an item that hangs is recorded as
`item-timed-out` and the whole check ends within 60 seconds:

- `programs`: every program the manifest lists is a regular file, root-owned, writable by
  no other account, with its recorded digest, and loads only its own folder's and the
  system's libraries (`otool -L`, kept per program digest); a script runs the release's
  own interpreter;
- `files`: every rule and configuration file the manifest lists has its owner, a mode no
  other account can write and its digest. While a valid in-progress marker (written by
  the installer, at most 60 minutes old) exists, a difference is reported as a change in
  progress instead of a failure; a marker past its 60 minutes covers nothing;
- `accounts`: each account of security-design § 5.1 present, with its UID and no login
  shell;
- `database`: v2's instance listens on loopback only; the root-owned rules folder and its
  `pg_hba.conf` and `pg_ident.conf` are root's, writable by no other account, each with
  its digest; and the server's effective `hba_file` and `ident_file` (`SHOW`) are those
  same files;
- `filter`: the packet filter is enabled, with the anchor's rules loaded at their digest;
- `volume`: the backup volume is unlocked whenever it is present;
- `backups` (`isolation-backups`): both fixed Time Machine exclusions hold;
- `boot`: every job set to start at boot is running, unless a valid stop record covers
  it; a stop record that is malformed, not root's or past its 14 days is a lapse, and so
  is one whose receipt the platform store does not hold (a stop is planned only through
  PlatformControl's service control, the person's decision of 2026-10-25).

Each run writes one JSON file, named by its UTC start, into `evidence/isolation/`
(root-owned, readable by every account), and deletes its own files older than 14 days.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import stat
import sys
import threading
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from docsuri_ops.arrangement.paths import Accounts, ArrangementPaths
from docsuri_ops.u8_platform.fixed import read_stop_record
from docsuri_ops.u8_platform.platform_profile import PRODUCTION_LABELS

ITEMS = ("programs", "files", "accounts", "database", "filter", "volume", "backups", "boot")
ITEM_SECONDS = {"programs": 40, "files": 20, "accounts": 15, "database": 15, "filter": 15,
                "volume": 15, "backups": 15, "boot": 30}
TOTAL_SECONDS = 60
RETENTION = dt.timedelta(days=14)
MARKER_BOUND = dt.timedelta(minutes=60)
# How far the platform store's clock may read ahead of the fixed program's when a stop
# record's `stoppedAt` is compared with its receipt's recorded time.
RECEIPT_CLOCK_SKEW = dt.timedelta(minutes=5)
# `platform.service.control`'s deadline (inventory.json): the fixed program writes the
# stop record within it after PlatformControl binds the receipt, so a receipt bound
# earlier than that before `stoppedAt` (less the skew) is not this record's. The driver
# holds the program to it: it runs every program of an effect under what is left of a
# bound below the deadline and ends it there (`drivers.arrangement.program_bound`,
# `run_program`; review findings, Minor, R16, and Major, R21), so no stop record is
# written after its receipt settled.
SERVICE_CONTROL_DEADLINE = dt.timedelta(seconds=120)
MANIFEST = "arrangement-manifest.json"
MARKER = "arrangement-in-progress.json"
OTOOL_CACHE = "isolation-otool.json"
VOLUME = "DocSuri_Backup"
DATABASE_PORT = 15432
EXCLUSIONS = ("/Library/DocSuri/",
              "/Users/revenantonthemission/Library/Group Containers/HUAQ24HBR6.dev.orbstack/")
SYSTEM_LIBRARIES = ("/usr/lib/", "/System/Library/")
RELATIVE_LIBRARIES = ("@rpath/", "@loader_path/", "@executable_path/")
NO_LOGIN = "/usr/bin/false"
# Every long-running job set to start at boot: the org.docsuri.* jobs service control acts
# on, and the standing job, which no service control stops (U8 plan Step 37's templates).
BOOT_LABELS = tuple(label for label in PRODUCTION_LABELS if label.startswith("org.docsuri.")) + (
    "org.docsuri.v2.standing",)
RESULT_NAME = re.compile(r"\d{8}T\d{6}Z\.json")
MAX_FILE = 4 * 1024 * 1024


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _digest_within(prefix: Path, path: Path) -> str | None:
    """A file's digest, reached through the no-link walk when it lies under the prefix
    (your answer of 2026-11-10, "Fix both and sweep the rest"): `postgres/` and
    `postgres/data` belong to the database account, which could otherwise put a link in
    place of a folder on the way and have the check read a pristine copy while the
    server reads another. A link at a folder or at the file, a second name of another
    file, or another thing than a regular file, answers None (a difference) and is never
    read. Paths outside the prefix (the system's rule files) are read as before."""
    from docsuri_ops.arrangement import safe_fs

    if prefix not in path.parents:
        return _digest(path)
    return safe_fs.sha256_at(prefix, path)


def _digest(path: Path) -> str | None:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return None
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            return None
        accumulator = hashlib.sha256()
        while block := os.read(descriptor, 1 << 20):
            accumulator.update(block)
        return accumulator.hexdigest()
    finally:
        os.close(descriptor)


class ItemFailed(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass
class CheckContext:
    """Where and as whom the check runs: the arrangement's paths (a test prefix in
    tests), the accounts table, the tools, the clock and the account that must own
    every root-owned file (root)."""

    paths: ArrangementPaths = field(default_factory=ArrangementPaths)
    accounts: Accounts = field(default_factory=Accounts)
    tools: object = None
    clock: Callable[[], dt.datetime] = _now
    owner_uid: int = 0
    boot_labels: tuple[str, ...] = BOOT_LABELS
    exclusions: tuple[str, ...] = EXCLUSIONS
    item_seconds: dict = field(default_factory=lambda: dict(ITEM_SECONDS))
    # Whether the platform store holds a stop record's receipt (`receipt_held`); None
    # reads production's store through the service account's reader binding.
    receipt_held: Callable[[dict], bool] | None = None

    def resolve(self, path: str) -> Path:
        return Path(path) if path.startswith("/") else self.paths.prefix / path


def _read_json(path: Path) -> dict | None:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return None
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            return None
        value = json.loads(os.read(descriptor, MAX_FILE))
    except (OSError, ValueError):
        return None
    finally:
        os.close(descriptor)
    return value if isinstance(value, dict) else None


def _owned(path: Path, owner: int, *, kind: Callable[[int], bool] = stat.S_ISREG) -> bool:
    try:
        info = path.lstat()
    except OSError:
        return False
    return kind(info.st_mode) and info.st_uid == owner and not info.st_mode & 0o022


class IsolationCheck:
    def __init__(self, context: CheckContext):
        self.context = context
        if context.tools is None:
            from .isolation_macos import MacTools

            context.tools = MacTools()
        self.tools = context.tools
        self.stop_records: list[dict] = []
        self.change_in_progress = False

    # --- the manifest and the marker ------------------------------------------------------

    def manifest(self) -> dict:
        path = self.context.paths.control / MANIFEST
        if not _owned(path, self.context.owner_uid):
            raise ItemFailed("manifest-refused")
        value = _read_json(path)
        if value is None or not isinstance(value.get("files"), list):
            raise ItemFailed("manifest-refused")
        return value

    def marker_valid(self) -> bool:
        path = self.context.paths.control / MARKER
        if not _owned(path, self.context.owner_uid):
            return False
        value = _read_json(path) or {}
        try:
            started = dt.datetime.fromisoformat(str(value.get("startedAt")).replace("Z", "+00:00"))
        except ValueError:
            return False
        return started.tzinfo is not None and dt.timedelta(0) <= (
            self.context.clock() - started) <= MARKER_BOUND

    def _entries(self, manifest: dict, kinds: Iterable[str]) -> list[dict]:
        wanted = set(kinds)
        return [item for item in manifest["files"] if isinstance(item, dict)
                and item.get("kind") in wanted]

    # --- the items ----------------------------------------------------------------------

    def programs(self) -> None:
        manifest = self.manifest()
        cache_path = self.context.paths.control / OTOOL_CACHE
        cache = _read_json(cache_path) or {}
        interpreter = f"#!{self.context.paths.release / '.venv/bin/python'} -I"
        for entry in self._entries(manifest, ("program",)):
            path = self.context.resolve(str(entry.get("path", "")))
            if not _owned(path, self.context.owner_uid) or not _owned(
                path.parent, self.context.owner_uid, kind=stat.S_ISDIR
            ):
                raise ItemFailed("program-custody")
            digest = _digest(path)
            if digest != entry.get("sha256"):
                raise ItemFailed("program-digest")
            if digest not in cache:  # a script's `None` is kept too
                cache[digest] = self.tools.libraries(str(path))
            libraries = cache[digest]
            if libraries is None:
                with open(path, "rb") as stream:
                    first = stream.readline(256).decode("utf-8", "replace").strip()
                if first != interpreter:
                    raise ItemFailed("program-loads-outside")
                continue
            own = str(self.context.resolve(str(entry.get("root", path.parent))))
            for library in libraries:
                if not (library.startswith(own.rstrip("/") + "/")
                        or library.startswith(SYSTEM_LIBRARIES + RELATIVE_LIBRARIES)):
                    raise ItemFailed("program-loads-outside")
        self._write_private(cache_path, cache)

    def files(self) -> None:
        manifest = self.manifest()
        differs = False
        for entry in self._entries(manifest, ("rule", "config")):
            path = self.context.resolve(str(entry.get("path", "")))
            owner = entry.get("ownerUid", self.context.owner_uid)
            if not _owned(path, owner) or _digest_within(
                self.context.paths.prefix, path
            ) != entry.get("sha256"):
                differs = True
        if differs:
            if self.marker_valid():
                self.change_in_progress = True
                return
            raise ItemFailed("file-differs")

    def accounts(self) -> None:
        table = self.context.accounts
        for account in (table.service, table.scheduler, table.database, table.models,
                        table.tunnel, table.backup):
            found = self.tools.account(account.name)
            if found is None:
                raise ItemFailed("account-missing")
            if found["uid"] != account.uid:
                raise ItemFailed("account-uid-differs")
            if found["shell"] != NO_LOGIN:
                raise ItemFailed("account-can-log-in")

    def database(self) -> None:
        listeners = self.tools.listeners(DATABASE_PORT)
        if listeners is None or not listeners:
            raise ItemFailed("database-not-listening")
        for _user, address in listeners:
            if address not in (f"127.0.0.1:{DATABASE_PORT}", f"[::1]:{DATABASE_PORT}"):
                raise ItemFailed("database-listens-beyond-loopback")
        manifest = self.manifest()
        paths, owner = self.context.paths, self.context.owner_uid
        rules = paths.postgres_rules
        # Your answer of 2026-11-11 ("Map the login, root rules"): the rule files live in a
        # root-owned folder the database account can read but neither write nor replace.
        # The folder is under the root-owned prefix, so its own entry and its files'
        # entries are read by path; a link, another owner or a group or other write bit
        # is refused before any digest.
        if not _owned(rules, owner, kind=stat.S_ISDIR):
            raise ItemFailed("database-rules-folder-custody")
        hba, ident = rules / "pg_hba.conf", rules / "pg_ident.conf"
        for path, key, reason in ((hba, "pgHbaSha256", "database-hba-differs"),
                                  (ident, "pgIdentSha256", "database-ident-differs")):
            if not _owned(path, owner):
                raise ItemFailed("database-rule-file-custody")
            # No recorded digest is a difference too: the installer leaves it out when the
            # walk refused the file, and a refused read (None) must never match it.
            recorded = manifest.get(key)
            if recorded is None or _digest_within(paths.prefix, path) != recorded:
                raise ItemFailed(reason)
        # Your answer of 2026-11-11 ("Pin them on the command line"): the database account
        # owns `postgres/data` and could name another rule file in postgresql.auto.conf;
        # the launch job pins `hba_file` and `ident_file` with `-c`, and the server's own
        # answers must be the files whose digests were just checked. No answer is a
        # difference too.
        psql, socket = str(paths.postgres_runtime / "bin" / "psql"), str(paths.postgres_socket)
        uid = self.context.accounts.database.uid
        if self.tools.hba_file(psql, socket, uid) != str(hba):
            raise ItemFailed("database-hba-file-differs")
        if self.tools.ident_file(psql, socket, uid) != str(ident):
            raise ItemFailed("database-ident-file-differs")

    def filter(self) -> None:
        if self.tools.filter_enabled() is not True:
            raise ItemFailed("filter-disabled")
        if self.tools.anchor_digest() != self.manifest().get("filterRulesSha256"):
            raise ItemFailed("filter-rules-differ")

    def volume(self) -> None:
        found = self.tools.volume(VOLUME)
        if found is None:
            raise ItemFailed("volume-unreadable")
        if found["present"] and found.get("locked"):
            raise ItemFailed("volume-locked")

    def backups(self) -> None:
        for path in self.context.exclusions:
            if self.tools.excluded(path) is not True:
                raise ItemFailed("isolation-backups")

    def boot(self) -> None:
        now = self.context.clock()
        self.stop_records = []
        lapsed = False
        disabled = self.tools.disabled()
        for label in self.context.boot_labels:
            path = self.context.paths.control_stops / f"{label}.json"
            present = path.exists() or path.is_symlink()
            record = read_stop_record(path, owner_uid=self.context.owner_uid, now=now)
            if record is not None and not self._receipt_held(record):
                # Planned only when PlatformControl bound its receipt (the person's
                # decision of 2026-10-25, "Add an in-person stop command").
                record = None
            if present and record is None:
                lapsed = True  # malformed, not root's, past its bound, or unreceipted
                continue
            if record is not None:
                self.stop_records.append(record)
                continue
            job = self.tools.job(label)
            if job is None or job["state"] != "running" or disabled.get(label):
                lapsed = True
        if lapsed:
            raise ItemFailed("boot-item-lapsed")

    def _receipt_held(self, record: dict) -> bool:
        """Whether the platform store holds the stop's receipt: a succeeded
        `platform.service.control` on the record's own label. Anything unreadable is
        not held, so the record covers nothing."""
        held = self.context.receipt_held
        if held is None:
            held = self.context.receipt_held = production_receipt_held(
                self.context.paths, owner_uid=self.context.accounts.service.uid)
        try:
            return bool(held(record))
        except Exception:  # noqa: BLE001 - a store that cannot answer holds nothing
            return False

    # --- the run ------------------------------------------------------------------------

    def _run_item(self, name: str) -> dict:
        outcome: dict = {}

        def work() -> None:
            try:
                getattr(self, name)()
                outcome.update(passed=True)
            except ItemFailed as failure:
                outcome.update(passed=False, reason=failure.reason)
            except Exception:  # noqa: BLE001 - an item that cannot finish fails
                outcome.update(passed=False, reason="item-failed")

        thread = threading.Thread(target=work, name=f"isolation-{name}", daemon=True)
        thread.start()
        return {"thread": thread, "outcome": outcome}

    def run(self) -> dict:
        started = self.context.clock()
        running = {name: self._run_item(name) for name in ITEMS}
        deadline = dt.timedelta(seconds=TOTAL_SECONDS)
        items = []
        begin = _now()
        for name in ITEMS:
            remaining = max(0.0, (deadline - (_now() - begin)).total_seconds())
            limit = min(float(self.context.item_seconds[name]), remaining)
            running[name]["thread"].join(limit)
            outcome = running[name]["outcome"]
            if running[name]["thread"].is_alive() or "passed" not in outcome:
                items.append({"item": name, "passed": False, "reason": "item-timed-out"})
            elif outcome["passed"]:
                items.append({"item": name, "passed": True})
            else:
                items.append({"item": name, "passed": False, "reason": outcome["reason"]})
        result = {
            "resultId": str(uuid4()), "checkedAt": started.isoformat(),
            "durationMs": int((_now() - begin).total_seconds() * 1000),
            "items": items, "stopRecords": list(self.stop_records),
            "changeInProgress": self.change_in_progress,
            "passed": all(item["passed"] for item in items),
        }
        result["digest"] = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()
        return result

    # --- evidence -----------------------------------------------------------------------

    def _write_private(self, path: Path, value: dict) -> None:
        self._write(path, value, 0o600)

    def _write(self, path: Path, value: dict, mode: int) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        pending = path.with_name(path.name + ".pending")
        descriptor = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW,
                             mode)
        try:
            os.fchmod(descriptor, mode)
            os.write(descriptor, json.dumps(value, sort_keys=True).encode())
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.replace(pending, path)

    def write_result(self, result: dict) -> Path:
        folder = self.context.paths.isolation_evidence
        moment = dt.datetime.fromisoformat(result["checkedAt"]).astimezone(dt.UTC)
        path = folder / f"{moment:%Y%m%dT%H%M%SZ}.json"
        self._write(path, result, 0o644)
        return path

    def prune(self) -> list[str]:
        """The check's own result files older than 14 days; nothing else is touched."""
        folder = self.context.paths.isolation_evidence
        cutoff = self.context.clock() - RETENTION
        removed = []
        if not folder.is_dir() or folder.is_symlink():
            return removed
        for entry in os.scandir(folder):
            if not RESULT_NAME.fullmatch(entry.name) or entry.is_symlink() or not entry.is_file(
                follow_symlinks=False
            ):
                continue
            moment = dt.datetime.strptime(entry.name[:15], "%Y%m%dT%H%M%S").replace(
                tzinfo=dt.UTC)
            if moment < cutoff:
                os.unlink(folder / entry.name)
                removed.append(entry.name)
        return sorted(removed)


def stop_input_hash(label: str) -> str:
    """The bound input of a stop of `label` (`service_words.run_service`'s document)."""
    from docsuri_ops.u8_platform.drivers import input_hash

    return input_hash({"label": label, "action": "stop"})


def _receipt_time_fits(receipt: dict, record: dict) -> bool:
    """The receipt's bind time (`recordedAt`: PlatformControl records it when it binds the
    operation, before the fixed program runs) falls within the named window around the
    record's `stoppedAt`: no later than `stoppedAt` plus `RECEIPT_CLOCK_SKEW`, and no
    earlier than `stoppedAt` less `SERVICE_CONTROL_DEADLINE` and the skew. So an old stop
    receipt of the same label cannot back a record with fresh dates (the review's fix of
    2026-10-26). A receipt settles only after its record is written, so its settle time
    cannot be the bound."""
    try:
        recorded = dt.datetime.fromisoformat(str(receipt["recordedAt"]))
        stopped = dt.datetime.fromisoformat(str(record["stoppedAt"]))
    except (KeyError, TypeError, ValueError):
        return False
    if recorded.tzinfo is None or stopped.tzinfo is None:
        return False
    earliest = stopped - SERVICE_CONTROL_DEADLINE - RECEIPT_CLOCK_SKEW
    return earliest <= recorded <= stopped + RECEIPT_CLOCK_SKEW


def receipt_held_by(reader) -> Callable[[dict], bool]:
    """A stop record is planned when `reader` (the ledger component's receipt reader,
    `u8_protocols.ReceiptReader`) finds its receipt: a succeeded
    `platform.service.control` that was a stop of the record's own label (its bound
    input's hash), bound within the window around the record's `stoppedAt` (the review's
    fixes of 2026-10-26, `_receipt_time_fits`). A start receipt, another label's stop, a
    receipt bound after the record says the job stopped, or an old one cited by a record
    with fresh dates plans nothing."""

    def held(record: dict) -> bool:
        if reader is None:
            return False
        receipt = reader.read(str(record["receiptId"]))
        return (receipt.get("operation") == "platform.service.control"
                and receipt.get("targetId") == record["label"]
                and receipt.get("outcome") == "succeeded"
                and receipt.get("inputHash") == stop_input_hash(str(record["label"]))
                and _receipt_time_fits(receipt, record))

    return held


def production_receipt_held(paths: ArrangementPaths, *, owner_uid: int,
                            profile=None) -> Callable[[dict], bool]:
    """Production's store, read through the service account's reader binding in the
    profile; no binding, no planned stop.

    The check runs as root, and the installer writes the binding 0600 and owned by the
    service account (`write_secret_file(..., uid=service.uid)`), so the binding is read
    with that account named as its owner (`owner_uid`): a binding with any other owner,
    a looser mode or another form is refused, and then nothing is held. `profile` is
    production's platform profile unless a test names the realm's."""
    from docsuri_ops.u8_platform.platform_profile import U8PlatformProfile
    from docsuri_ops.u8_platform.u8_protocols import readers

    chosen = profile or U8PlatformProfile.production(control=paths.control)
    root = paths.profile if chosen.is_production else None
    try:
        found = readers(chosen, root=root, owner_uid=owner_uid)
    except Exception:  # noqa: BLE001 - no store: nothing is held
        found = None
    return receipt_held_by(None if found is None else found[0])


def main(argv: list[str] | None = None) -> int:
    """The installed program: no argument; one JSON result on standard output."""
    arguments = sys.argv[1:] if argv is None else argv
    if arguments or any(name.startswith(("PYTHON", "DYLD_", "LD_")) for name in os.environ):
        print(json.dumps({"ok": False, "reason": "invocation-refused"}))
        return 2
    check = IsolationCheck(CheckContext())
    result = check.run()
    check.write_result(result)
    check.prune()
    print(json.dumps({"ok": True, "passed": result["passed"], "resultId": result["resultId"]}))
    return 0
