"""The arrangement manifest and the in-progress marker (U8 plan Step 37; cicd-pipeline
§ 5.4 and § 9, security-design § 6.8).

- `control/arrangement-manifest.json` (root, 0644): the arrangement version the installer
  installed, and the digest of every file it put in place, as
  `files[{path, kind: program|rule|config, sha256, root?, ownerUid?}]`, with
  `pgHbaSha256` and `pgIdentSha256` (the database's `pg_hba.conf` and `pg_ident.conf`, in
  the root-owned `postgres-rules`) and `filterRulesSha256` (the loaded
  anchor's rules, as `pfctl` prints them). A path under the prefix is written relative
  to it; a system file (`/etc/…`, `/Library/LaunchDaemons/…`) as its absolute path. The
  isolation check compares the installed files with it every 5 minutes, whichever
  release runs (cicd-pipeline § 9).
- `control/arrangement-in-progress.json` (root, 0644): `{startedAt, reason}`, valid for
  60 minutes. While it is valid the isolation check reports a changed rule or
  configuration file as a change in progress, not a lapse; past its 60 minutes it covers
  nothing. `changing(...)` writes it and removes it on every way out, and the caller
  records the arrangement as it actually stands before it goes.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import stat
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from .paths import ArrangementPaths

KINDS = ("program", "rule", "config")
MARKER_BOUND = dt.timedelta(minutes=60)
MAX_MANIFEST = 4 * 1024 * 1024
REASON_FORM = frozenset("abcdefghijklmnopqrstuvwxyz0123456789-:.")
# The digest the installer records for a rendered file under the prefix that the no-link
# walk refused or did not find (a second name, a link at it or in place of a folder on the
# way, a FIFO, a file renamed away). No file's SHA-256 is 64 zeros in practice, so the
# entry never matches whatever is there later: the isolation check's `files` item keeps
# answering `file-differs` until an apply reads the file again (the re-review of 2026-11-10).
UNREAD_DIGEST = "0" * 64


class ManifestRefused(ValueError):
    """The manifest or marker is outside its form; the message is a fixed key."""


def sha256_file(path: Path) -> str:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ManifestRefused("not-a-regular-file")
        digest = hashlib.sha256()
        while block := os.read(descriptor, 1 << 20):
            digest.update(block)
        return digest.hexdigest()
    finally:
        os.close(descriptor)


@dataclass(frozen=True)
class Entry:
    path: str
    kind: str
    sha256: str
    root: str | None = None
    owner_uid: int | None = None

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ManifestRefused("entry-kind")
        if len(self.sha256) != 64 or any(c not in "0123456789abcdef" for c in self.sha256):
            raise ManifestRefused("entry-digest")
        if not self.path or ".." in Path(self.path).parts:
            raise ManifestRefused("entry-path")

    def as_dict(self) -> dict:
        value: dict = {"path": self.path, "kind": self.kind, "sha256": self.sha256}
        if self.root is not None:
            value["root"] = self.root
        if self.owner_uid is not None:
            value["ownerUid"] = self.owner_uid
        return value

    @classmethod
    def of(cls, value: dict) -> Entry:
        if not isinstance(value, dict) or not {"path", "kind", "sha256"} <= set(value) <= {
            "path", "kind", "sha256", "root", "ownerUid"
        }:
            raise ManifestRefused("entry-fields")
        return cls(str(value["path"]), str(value["kind"]), str(value["sha256"]),
                   value.get("root"), value.get("ownerUid"))


@dataclass(frozen=True)
class Manifest:
    version: int
    files: tuple[Entry, ...] = ()
    pg_hba_sha256: str | None = None
    filter_rules_sha256: str | None = None
    written_at: str | None = None
    extra: dict = field(default_factory=dict)
    # Your answer of 2026-11-11 ("Map the login, root rules"): the peer map's file.
    pg_ident_sha256: str | None = None

    def as_dict(self) -> dict:
        return {
            "version": self.version,
            "files": [entry.as_dict() for entry in sorted(self.files, key=lambda e: e.path)],
            "pgHbaSha256": self.pg_hba_sha256,
            "pgIdentSha256": self.pg_ident_sha256,
            "filterRulesSha256": self.filter_rules_sha256,
            "writtenAt": self.written_at,
        }

    def entry(self, path: str) -> Entry | None:
        return next((item for item in self.files if item.path == path), None)

    def with_entries(self, entries: Iterable[Entry]) -> Manifest:
        """The manifest with these entries put in (replacing any at the same path)."""
        given = {item.path: item for item in entries}
        kept = [item for item in self.files if item.path not in given]
        return Manifest(self.version, tuple(kept + list(given.values())), self.pg_hba_sha256,
                        self.filter_rules_sha256, self.written_at,
                        pg_ident_sha256=self.pg_ident_sha256)


def manifest_path(paths: ArrangementPaths, path: Path) -> str:
    """How the manifest names an installed file: relative under the prefix, otherwise
    absolute (the isolation check's `resolve` reads both)."""
    try:
        return str(path.relative_to(paths.prefix))
    except ValueError:
        return str(path)


def resolve(paths: ArrangementPaths, recorded: str) -> Path:
    return Path(recorded) if recorded.startswith("/") else paths.prefix / recorded


def entry_for(paths: ArrangementPaths, path: Path, kind: str, *, root: Path | None = None,
              owner_uid: int | None = None) -> Entry:
    return Entry(manifest_path(paths, path), kind, sha256_file(path),
                 None if root is None else manifest_path(paths, root), owner_uid)


def _write_root(path: Path, payload: bytes, *, mode: int, owner_uid: int) -> None:
    """Atomically, through a new file beside it, never through a link; root-owned."""
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + ".pending")
    if pending.is_symlink():
        pending.unlink()
    descriptor = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, mode)
    try:
        os.fchmod(descriptor, mode)
        if os.geteuid() == 0:
            os.fchown(descriptor, owner_uid, 0)
        os.write(descriptor, payload)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.replace(pending, path)


def write_manifest(paths: ArrangementPaths, manifest: Manifest, *,
                   clock: Callable[[], dt.datetime], owner_uid: int = 0) -> Path:
    stamped = Manifest(manifest.version, manifest.files, manifest.pg_hba_sha256,
                       manifest.filter_rules_sha256, clock().astimezone(dt.UTC).isoformat(),
                       pg_ident_sha256=manifest.pg_ident_sha256)
    payload = json.dumps(stamped.as_dict(), sort_keys=True, indent=1).encode()
    _write_root(paths.arrangement_manifest, payload, mode=0o644, owner_uid=owner_uid)
    return paths.arrangement_manifest


def read_manifest(paths: ArrangementPaths) -> Manifest | None:
    path = paths.arrangement_manifest
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return None
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ManifestRefused("manifest-not-a-file")
        raw = os.read(descriptor, MAX_MANIFEST + 1)
    finally:
        os.close(descriptor)
    try:
        value = json.loads(raw)
    except ValueError:
        raise ManifestRefused("manifest-unreadable") from None
    if not isinstance(value, dict) or type(value.get("version")) is not int or not isinstance(
        value.get("files"), list
    ):
        raise ManifestRefused("manifest-fields")
    return Manifest(value["version"], tuple(Entry.of(item) for item in value["files"]),
                    value.get("pgHbaSha256"), value.get("filterRulesSha256"),
                    value.get("writtenAt"), pg_ident_sha256=value.get("pgIdentSha256"))


def differences(paths: ArrangementPaths, manifest: Manifest | None) -> list[str]:
    """The recorded files that no longer hold their digest (or are gone)."""
    if manifest is None:
        return ["manifest-missing"]
    found = []
    for entry in manifest.files:
        try:
            digest = sha256_file(resolve(paths, entry.path))
        except (OSError, ManifestRefused):
            digest = None
        if digest != entry.sha256:
            found.append(entry.path)
    return found


# --- the in-progress marker ------------------------------------------------------------------


def begin_change(paths: ArrangementPaths, reason: str, *, clock: Callable[[], dt.datetime],
                 owner_uid: int = 0) -> dict:
    if not reason or len(reason) > 128 or set(reason) - REASON_FORM:
        raise ManifestRefused("marker-reason")
    value = {"startedAt": clock().astimezone(dt.UTC).isoformat(), "reason": reason}
    _write_root(paths.arrangement_marker, json.dumps(value, sort_keys=True).encode(),
                mode=0o644, owner_uid=owner_uid)
    return value


def end_change(paths: ArrangementPaths) -> bool:
    try:
        os.unlink(paths.arrangement_marker)
    except FileNotFoundError:
        return False
    return True


def marker(paths: ArrangementPaths) -> dict | None:
    try:
        value = json.loads(paths.arrangement_marker.read_bytes())
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) and set(value) == {"startedAt", "reason"} else None


def marker_valid(paths: ArrangementPaths, now: dt.datetime) -> bool:
    value = marker(paths)
    if value is None:
        return False
    try:
        started = dt.datetime.fromisoformat(str(value["startedAt"]))
    except ValueError:
        return False
    return started.tzinfo is not None and dt.timedelta(0) <= now - started <= MARKER_BOUND


@contextmanager
def changing(paths: ArrangementPaths, reason: str, *, clock: Callable[[], dt.datetime],
             record: Callable[[], object], owner_uid: int = 0) -> Iterator[dict]:
    """The marker for one change; on every way out the arrangement as it stands is
    recorded (`record`, which writes the manifest), then the marker goes."""
    value = begin_change(paths, reason, clock=clock, owner_uid=owner_uid)
    try:
        yield value
    finally:
        try:
            record()
        finally:
            end_change(paths)
