"""The backup agent's volume check (U8 plan Step 25; BR6.6, Workflow 19 step 1).

`check` passes only when all of these hold:

- the backup account owns the volume, and the volume enforces ownership;
- U8's folder is writable by the agent;
- free space is at or above the backup floor (64 GiB);
- the catalogue verifies;
- no folder from U8's folder up to `/` carries the earlier tool's cleanup marker
  `.docsuri-rem1-managed`, so that tool's age-based cleanup never treats U8's files as
  its own;
- the volume is encrypted, asked of its mount point through the earlier tool's archive
  adapter (`adapters/backup.py`'s `available()`).

It reports the volume's identity. Writing stops on any failure; deletion still runs
when low free space is the only one, because deleting is what frees space.

Two volume adapters answer the volume-level facts: `MacVolume` asks `diskutil` on this
Mac; `StandinVolume`, in the composed realm, stands in for the two answers a folder
cannot give (enforced ownership and encryption) and says so in every status
(`standin: true`).

`EvidenceStatus` is how the service account sees the agent's status: through
PlatformControl's evidence reader, never by running the agent (BR6.6, NFR1.5).
"""

from __future__ import annotations

import os
import plistlib
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from docsuri_ops.adapters.backup import LocalDriveArchive, filevault_encrypted

from .catalogue import Catalogue, CatalogueDamaged
from .config import BACKUP_FLOOR_BYTES, AgentConfig

MARKER = ".docsuri-rem1-managed"
__all__ = ["BACKUP_FLOOR_BYTES"]
DISKUTIL = "/usr/sbin/diskutil"
LOW_SPACE = "backup-volume-low"


@dataclass(frozen=True)
class VolumeFacts:
    identity: str | None
    owner_uid: int | None
    ownership_enforced: bool
    encrypted: bool
    standin: bool = False


def diskutil_info(mount: Path, *, run: Callable = subprocess.run) -> dict:
    """`diskutil info -plist <mount>`, parsed; empty when the tool does not answer."""
    try:
        completed = run([DISKUTIL, "info", "-plist", str(mount)], capture_output=True,
                        timeout=10, check=False)
    except (OSError, subprocess.SubprocessError):
        return {}
    if completed.returncode != 0:
        return {}
    try:
        value = plistlib.loads(completed.stdout)
    except Exception:  # noqa: BLE001 - an unreadable answer is no answer
        return {}
    return value if isinstance(value, dict) else {}


class MacVolume:
    """The real backup volume: its identity, owner, ownership mode and encryption."""

    def __init__(self, *, info: Callable[[Path], dict] = diskutil_info,
                 encrypted: Callable[[Path], bool] = filevault_encrypted):
        self._info, self._encrypted = info, encrypted

    def facts(self, mount: Path) -> VolumeFacts:
        info = self._info(mount)
        try:
            owner = mount.stat().st_uid
        except OSError:
            owner = None
        return VolumeFacts(
            identity=info.get("VolumeUUID"), owner_uid=owner,
            ownership_enforced=info.get("GlobalPermissionsEnabled") is True,
            encrypted=bool(self._encrypted(mount)),
        )

    def encrypted(self, mount: Path) -> bool:
        return bool(self._encrypted(mount))


class StandinVolume:
    """The composed realm's folder standing in for the backup volume: the configured
    identity, the folder's own owner, and the two volume-level answers a folder cannot
    give, each reported as a stand-in."""

    def __init__(self, identity: str):
        self.identity = identity

    def facts(self, mount: Path) -> VolumeFacts:
        try:
            owner = mount.stat().st_uid
        except OSError:
            owner = None
        return VolumeFacts(identity=self.identity, owner_uid=owner, ownership_enforced=True,
                           encrypted=True, standin=True)

    def encrypted(self, mount: Path) -> bool:
        return True


def volume_for(config: AgentConfig):
    return StandinVolume(config.volume_identity) if config.kind == "realm" else MacVolume()


def marker_above(folder: Path) -> bool:
    """The earlier tool's marker in U8's folder or any folder above it, up to `/`."""
    current = folder
    while True:
        if (current / MARKER).exists() or (current / MARKER).is_symlink():
            return True
        if current.parent == current:
            return False
        current = current.parent


def is_folder(path: Path) -> bool:
    """A folder the agent can see; one it cannot read is not there for it."""
    try:
        return path.is_dir()
    except OSError:
        return False


def free_bytes(path: Path) -> int:
    stats = os.statvfs(path)
    return stats.f_bavail * stats.f_frsize


def check(config: AgentConfig, *, clock, volume=None,
          free: Callable[[Path], int] = free_bytes, backup_uid: int | None = None) -> dict:
    """The status: `available` only when every check passes; the findings name each
    failure, and `deletionAllowed` is true when low free space is the only one."""
    volume = volume or volume_for(config)
    uid = os.getuid() if backup_uid is None else backup_uid
    facts = volume.facts(config.mount)
    findings: list[str] = []
    if not is_folder(config.mount):
        findings.append("backup-volume-unavailable")
    if facts.identity != config.volume_identity:
        findings.append("backup-volume-mismatch")
    if facts.owner_uid != uid or not facts.ownership_enforced:
        findings.append("backup-volume-ownership")
    if not facts.encrypted:
        findings.append("backup-volume-unencrypted")
    writable = is_folder(config.u8_folder) and os.access(config.u8_folder, os.W_OK | os.X_OK)
    if not writable:
        findings.append("backup-volume-unwritable")
    try:
        marker = marker_above(config.u8_folder)
    except OSError:
        # A volume the agent cannot read is not fit: the check fails closed, it never
        # leaves the caller without an answer (found by the cutover journeys).
        marker = False
        findings.append("backup-volume-unreadable")
    if marker:
        findings.append("backup-volume-shared-cleanup")
    catalogue, catalogued = catalogue_listing(config, clock) if writable else (
        "unavailable", [])
    if catalogue == "damaged":
        findings.append("backup-catalogue-damaged")
    space = free(config.mount) if is_folder(config.mount) else 0
    if space < config.space_floor_bytes:
        findings.append(LOW_SPACE)
    if writable:
        # The earlier tool's own check: the archives folder writable and encrypted.
        ready, _ = LocalDriveArchive(config.archives, encryption_probe=volume.encrypted).available()
        if not ready:
            findings.append("backup-volume-unwritable")
    return {
        "available": not findings,
        "deletionAllowed": not [item for item in findings if item != LOW_SPACE],
        "findings": list(dict.fromkeys(findings)),
        "volumeIdentity": facts.identity,
        "freeBytes": space,
        "sharedCleanupMarker": marker,
        "catalogue": catalogue,
        "catalogued": catalogued,
        "standin": facts.standin,
    }


def catalogue_state(config: AgentConfig, clock) -> str:
    """`intact` when the catalogue verifies, else `damaged`."""
    return catalogue_listing(config, clock)[0]


def listed(entry) -> dict:
    """One undisposed catalogued file as the status lists it (L1-51): its record, its
    place (`archives` or `staging`, never its path) and its disposal point, absent only
    for an entry begun before writing entries carried one (U8 plan Step 62(a))."""
    item = {"recordId": entry.record_id, "recordKind": entry.record_kind,
            "place": entry.path.split("/", 1)[0]}
    if entry.dispose_after is not None:
        item["disposeAfter"] = entry.dispose_after
    return item


def catalogue_listing(config: AgentConfig, clock) -> tuple[str, list[dict]]:
    """`intact` with every catalogue entry not yet disposed of (`writing`, `written` or
    `held`), sorted by record id, then place; `damaged` with an empty list."""
    try:
        catalogue = Catalogue.open(config.u8_folder, clock=clock)
    except (CatalogueDamaged, OSError):
        return "damaged", []
    try:
        files = catalogue.files()
    except CatalogueDamaged:
        return "damaged", []
    finally:
        catalogue.close()
    entries = [listed(entry) for entry in files.values() if entry.state != "disposed"]
    return "intact", sorted(entries, key=lambda item: (item["recordId"], item["place"]))


class EvidenceStatus:
    """The agent's latest status as the service account sees it: the observations the
    standing job recorded for the backup volume through PlatformControl, read through
    PlatformControl's bounded evidence reader (`latest(target)`)."""

    TARGET = "backup-volume"

    def __init__(self, latest: Callable[[str], dict | None]):
        self._latest = latest

    def __call__(self) -> dict:
        evidence = self._latest(self.TARGET)
        if not evidence:
            raise LookupError("no backup volume status is recorded")
        observations = evidence.get("observations") or {}
        if not isinstance(observations, dict) or "available" not in observations:
            raise LookupError("the recorded status is not the agent's")
        return observations
