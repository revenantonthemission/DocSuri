"""Deleting on the backup volume (U8 plan Step 25; BR9.17, NFR3.12, NFR3.13; Workflow 19
steps 8–10).

`dispose-due` (unattended) deletes a file only when all of these hold:

- it is a regular file, with one link, directly inside U8's archives folder, which the
  catalogue lists for its record;
- it is reached with `openat` and `O_NOFOLLOW` from the archives folder, itself reached
  without following a link;
- its digest still matches the catalogue's;
- its earliest disposal time, recorded when the agent wrote it, has passed;
- the retention floor does not hold it: the newest passed set of each database
  incarnation that still exists, and the newest verified ledger copy.

The caller's ledger facts never move a time: the pass takes the paths the ledger has
records for and the disposal points it claims, only to report. A due file the ledger has
no record of is deleted all the same and reported (`unrecorded`, for an incident); a
claim the catalogue does not show is refused and reported (`refusedClaims`). The pass
also sweeps staging files, and partial archives of a failed write, older than the
staging backstop of one day.

The in-person commands are the only other ways to delete or re-time a file:
`dispose-event` (a dry-run snapshot when its run ends, a rehearsal set once its
rehearsal database is removed), `set-date` (your decision brings a date forward, never
below 14 days after the copy was written), `dispose-mismatch` (a file whose digest no
longer matches, after you were shown the mismatch) and `rebuild-catalogue`.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import os
import re
import stat
from collections.abc import Callable
from pathlib import Path

from .catalogue import Catalogue, CatalogueFile, check_path
from .config import ARCHIVES, AgentConfig
from .writing import CHUNK, AgentRefused, Decided

SETS = ("live-set", "rehearsal-set")
EVENTS = {"run-ended": "dry-run-snapshot", "rehearsal-database-removed": "rehearsal-set"}
MAX_PATHS = 4096


def _instant(text: str) -> dt.datetime:
    return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))


_ARCHIVE_NAME = re.compile(rf"{ARCHIVES}/([a-z]+(?:-[a-z]+)*)-\d{{8}}T\d{{6}}-")


def _kind(entry: CatalogueFile) -> str | None:
    """The copy kind the agent wrote into the file's name (`writing.ArchiveWriter`)."""
    match = _ARCHIVE_NAME.match(entry.path)
    return match.group(1) if match else None


class Folder:
    """U8's archives folder, opened once without following a link at any step."""

    def __init__(self, config: AgentConfig):
        for path in (config.u8_folder, config.archives):
            if not stat.S_ISDIR(path.lstat().st_mode):
                raise AgentRefused("archives-folder-refused")
        self.fd = os.open(config.archives, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)

    def close(self) -> None:
        os.close(self.fd)

    def regular(self, name: str) -> os.stat_result | None:
        try:
            info = os.stat(name, dir_fd=self.fd, follow_symlinks=False)
        except FileNotFoundError:
            return None
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise AgentRefused("not-a-regular-file", path=name)
        return info

    def digest(self, name: str) -> str:
        accumulator = hashlib.sha256()
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=self.fd)
        with os.fdopen(descriptor, "rb") as stream:
            while block := stream.read(CHUNK):
                accumulator.update(block)
        return accumulator.hexdigest()

    def unlink(self, name: str) -> None:
        os.unlink(name, dir_fd=self.fd)


def _checked(path: str) -> str:
    """A catalogue path, or the command's `path-refused`."""
    try:
        return check_path(path)
    except ValueError:
        raise AgentRefused("path-refused") from None


def _name(path: str) -> str:
    parts = _checked(path).split("/")
    if len(parts) != 2 or parts[0] != ARCHIVES:
        raise AgentRefused("path-refused")
    return parts[1]


class Disposal:
    def __init__(self, config: AgentConfig, catalogue: Catalogue, *,
                 clock: Callable[[], dt.datetime],
                 incarnations: Callable[[], set[str]]):
        self.config, self.catalogue, self.clock = config, catalogue, clock
        self.incarnations = incarnations

    # --- the retention floor ------------------------------------------------------------

    def floor(self, files: dict[str, CatalogueFile]) -> set[str]:
        """The newest passed set of each incarnation that still exists, and the newest
        verified ledger copy."""
        living = self.incarnations()
        kept: dict[str, CatalogueFile] = {}
        for entry in files.values():
            if entry.state not in ("written", "held") or entry.integrity != "passed":
                continue
            kind = _kind(entry)
            if kind in SETS and entry.incarnation in living:
                key = f"set:{entry.incarnation}"
            elif kind == "ledger-copy":
                key = "ledger-copy"
            else:
                continue
            if key not in kept or entry.path > kept[key].path:
                kept[key] = entry
        return {entry.path for entry in kept.values()}

    # --- the unattended pass -----------------------------------------------------------

    def dispose_due(self, document: dict) -> dict:
        ledger_paths, claims = self._ledger_facts(document)
        now = self.clock()
        files = self.catalogue.files()
        floor = self.floor(files)
        report = {"disposed": [], "held": [], "released": [], "unrecorded": [],
                  "mismatched": [], "refused": [], "refusedClaims": [], "swept": 0}
        for entry in files.values():
            if entry.state == "held" and entry.path not in floor:
                self.catalogue.release(entry.path)
                report["released"].append(entry.path)
        folder = Folder(self.config)
        try:
            for entry in self.catalogue.due(now):
                if entry.path in floor:
                    self.catalogue.hold(entry.path, since=now)
                    report["held"].append(entry.path)
                    continue
                outcome = self._delete(folder, entry)
                report[outcome].append(entry.path)
                if outcome == "disposed" and entry.path not in ledger_paths:
                    report["unrecorded"].append(entry.path)
            report["swept"] = self._sweep(folder, now)
        finally:
            folder.close()
        files = self.catalogue.files()
        for claim in claims:
            listed = files.get(claim["path"])
            if listed is None or listed.dispose_after is None or _instant(
                listed.dispose_after
            ) > _instant(claim["disposeAfter"]):
                report["refusedClaims"].append(claim["path"])
        return report

    @staticmethod
    def _ledger_facts(document: dict) -> tuple[set[str], list[dict]]:
        if not isinstance(document, dict) or not set(document) <= {"ledgerPaths", "claims"}:
            raise AgentRefused("input-field-refused")
        paths = document.get("ledgerPaths", [])
        claims = document.get("claims", [])
        if not isinstance(paths, list) or not isinstance(claims, list) or (
            len(paths) > MAX_PATHS or len(claims) > MAX_PATHS
        ):
            raise AgentRefused("input-field-refused")
        checked = []
        for claim in claims:
            if not isinstance(claim, dict) or set(claim) != {"path", "disposeAfter"}:
                raise AgentRefused("input-field-refused")
            try:
                check_path(claim["path"])
                _instant(str(claim["disposeAfter"]))
            except ValueError:
                raise AgentRefused("input-field-refused") from None
            checked.append(claim)
        return {str(path) for path in paths}, checked

    def _delete(self, folder: Folder, entry: CatalogueFile) -> str:
        """`disposed`, `mismatched` (the digest changed) or `refused` (not a regular
        file with one link: nothing is followed, read or deleted)."""
        name = _name(entry.path)
        try:
            present = folder.regular(name)
        except AgentRefused:
            return "refused"
        if present is None:
            self.catalogue.dispose(entry.path)  # already gone: record it
            return "disposed"
        if folder.digest(name) != entry.sha256:
            return "mismatched"
        folder.unlink(name)
        self.catalogue.dispose(entry.path)
        return "disposed"

    def _sweep(self, folder: Folder, now: dt.datetime) -> int:
        """Staging files, and partial archives of a failed write, past the backstop."""
        cutoff = (now - dt.timedelta(seconds=self.config.retention.staging_backstop_seconds)
                  ).timestamp()
        files = self.catalogue.files()
        swept = 0
        staging = self.config.staging
        if stat.S_ISDIR(staging.lstat().st_mode):
            descriptor = os.open(staging, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                for name in os.listdir(descriptor):
                    info = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
                    if not stat.S_ISREG(info.st_mode) or info.st_mtime > cutoff:
                        continue
                    os.unlink(name, dir_fd=descriptor)
                    swept += 1
                    listed = files.get(f"staging/{name}")
                    if listed is not None and listed.state == "writing":
                        self.catalogue.dispose(listed.path)
            finally:
                os.close(descriptor)
        for entry in files.values():
            if entry.state != "writing" or not entry.path.startswith(f"{ARCHIVES}/"):
                continue
            name = _name(entry.path)
            try:
                info = folder.regular(name)
            except AgentRefused:
                continue  # never followed or deleted; reported by the due pass
            if info is None or info.st_mtime <= cutoff:
                if info is not None:
                    folder.unlink(name)
                    swept += 1
                self.catalogue.dispose(entry.path)
        return swept

    # --- the in-person commands ------------------------------------------------------------

    def _written(self, path: str) -> CatalogueFile:
        listed = self.catalogue.files().get(_checked(path))
        if listed is None or listed.state not in ("written", "held"):
            raise AgentRefused("not-catalogued")
        return listed

    def dispose_event(self, path: str, event: str) -> dict:
        if event not in EVENTS:
            raise AgentRefused("event-refused")
        entry = self._written(path)
        if _kind(entry) != EVENTS[event]:
            raise AgentRefused("event-refused")
        if entry.path in self.floor(self.catalogue.files()):
            raise AgentRefused("held-by-retention-floor")
        folder = Folder(self.config)
        try:
            outcome = self._delete(folder, entry)
        finally:
            folder.close()
        if outcome != "disposed":
            raise AgentRefused("digest-mismatch" if outcome == "mismatched"
                               else "not-a-regular-file")
        return {"disposed": entry.path, "event": event}

    def set_date(self, path: str, decided: Decided) -> dict:
        """Bring a written file's disposal time forward on your decision, with its
        receipt recorded; never later, and never below the kind's minimum."""
        entry = self._written(path)
        if entry.dispose_after is None or entry.written_at is None:
            raise AgentRefused("not-catalogued")
        minimum = _instant(entry.written_at) + dt.timedelta(
            seconds=self.config.retention.decided_minimum_seconds)
        if decided.date < minimum:
            raise AgentRefused("decided-date-too-early")
        if decided.date >= _instant(entry.dispose_after):
            raise AgentRefused("decided-date-not-earlier")
        self.catalogue.date(entry.path, dispose_after=decided.date,
                            decision_receipt=decided.receipt)
        return {"path": entry.path, "disposeAfter": decided.date.isoformat(),
                "decisionReceipt": decided.receipt}

    def dispose_mismatch(self, path: str) -> dict:
        """Delete a file the catalogue can no longer vouch for: only when its digest
        really differs from the catalogue's."""
        entry = self._written(path)
        folder = Folder(self.config)
        try:
            name = _name(entry.path)
            if folder.regular(name) is None or folder.digest(name) == entry.sha256:
                raise AgentRefused("digest-matches")
            folder.unlink(name)
        finally:
            folder.close()
        self.catalogue.dispose(entry.path)
        return {"disposed": entry.path, "reason": "digest-mismatch"}


def present_files(config: AgentConfig) -> list[tuple[str, int, str]]:
    """Every regular file in the archives folder, with its size and digest."""
    folder = Folder(config)
    try:
        found = []
        for name in sorted(os.listdir(folder.fd)):
            info = folder.regular(name)
            if info is not None:
                found.append((f"{ARCHIVES}/{name}", info.st_size, folder.digest(name)))
        return found
    finally:
        folder.close()


def rebuild_catalogue(config: AgentConfig, document: dict, *, clock) -> dict:
    """A catalogue that does not verify, rebuilt in person from the files present and
    their ledger records, keeping each file's later disposal time."""
    records = document.get("records") if isinstance(document, dict) else None
    if not isinstance(records, dict) or set(document) != {"records"} or len(records) > MAX_PATHS:
        raise AgentRefused("input-field-refused")
    rebuilt = Catalogue.rebuild(config.u8_folder, clock=clock, present=present_files(config),
                                ledger_records=records)
    try:
        return {"files": len(rebuilt.files()), "unrecorded": rebuilt.unrecorded}
    finally:
        rebuilt.close()


def prepare_volume(mount: Path, *, clock) -> dict:
    """U8's folder on a replacement volume: `docsuri-v2` with `archives/` and
    `staging/`, each 0700, refused under the earlier tool's cleanup marker."""
    from .config import STAGING, U8_FOLDER
    from .status import marker_above

    if not mount.is_absolute() or not stat.S_ISDIR(mount.lstat().st_mode):
        raise AgentRefused("mount-refused")
    folder = mount / U8_FOLDER
    if marker_above(folder):
        raise AgentRefused("backup-volume-shared-cleanup")
    created = []
    for path in (folder, folder / ARCHIVES, folder / STAGING):
        if path.exists() or path.is_symlink():
            if not stat.S_ISDIR(path.lstat().st_mode):
                raise AgentRefused("mount-refused")
            continue
        os.mkdir(path, 0o700)
        created.append(str(path.relative_to(mount)))
    Catalogue.open(folder, clock=clock).close()
    return {"prepared": str(folder), "created": created}
