"""Local (single-host) adapters for backup evidence collection.

Every adapter here is deliberately explicit about failure. A backup that silently degrades --
unmounted drive, unwritable target, restored onto itself -- is reported as a failure rather than
folded into a successful-looking result.
"""

from __future__ import annotations

import os
import plistlib
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from ..backup_evidence import digest_file, free_bytes


def filevault_encrypted(mount: Path) -> bool:
    """Whether macOS reports ``mount`` as a FileVault-encrypted volume.

    ``cryptutil status`` is not a macOS tool -- it does not exist on the platform, so probing with
    it silently reports every volume as unencrypted, including genuinely encrypted ones. The
    supported check is ``diskutil info -plist``, whose ``FileVault`` key is the authoritative
    volume-level answer. Anything unexpected fails closed.
    """
    try:
        completed = subprocess.run(
            ["/usr/sbin/diskutil", "info", "-plist", str(mount)],
            capture_output=True, timeout=10, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if completed.returncode != 0:
        return False
    try:
        return bool(plistlib.loads(completed.stdout).get("FileVault"))
    except Exception:
        return False


@dataclass
class LocalDriveArchive:
    """An encrypted removable drive, written as a filesystem-encrypted destination directory.

    Encryption is asserted by the mount, not by this code: we verify the volume reports as an
    encrypted APFS/other volume and writable, and we never claim encryption we did not observe.
    """

    mount: Path
    encryption_probe: Callable[[Path], bool] | str | None = None
    minimum_free_bytes: int = 0

    def available(self) -> tuple[bool, str]:
        if not self.mount.is_dir():
            return False, f"{self.mount} is not a mounted directory"
        if not os.access(self.mount, os.W_OK):
            return False, f"{self.mount} is not writable"
        if self.minimum_free_bytes and free_bytes(self.mount) < self.minimum_free_bytes:
            return False, f"{self.mount} has insufficient free space"
        if not self.encrypted():
            return False, f"{self.mount} does not report an encrypted volume"
        return True, "mounted, writable and encrypted"

    def encrypted(self) -> bool:
        """Fail closed: an undeterminable volume is reported as not encrypted."""
        probe = self.encryption_probe
        if probe is None:
            return filevault_encrypted(self.mount)
        if callable(probe):
            try:
                return bool(probe(self.mount))
            except Exception:
                return False
        try:
            completed = subprocess.run(
                [probe, str(self.mount)],
                capture_output=True, text=True, timeout=10, check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return completed.returncode == 0 and "encrypted" in completed.stdout.lower()

    def write_archive(self, source: Path, *, name: str) -> tuple[str | None, bool, str]:
        if not source.is_file():
            return None, False, f"source {source} is not a file"
        destination = self.mount / f"{name}.archive"
        try:
            with source.open("rb") as reader, destination.open("xb") as writer:
                shutil.copyfileobj(reader, writer, length=1 << 20)
        except FileExistsError:
            # Never silently replace an existing archive; a reused name must be an operator error.
            return None, False, f"{destination} already exists"
        except OSError as error:
            return None, False, f"{type(error).__name__}: {error}"
        return digest_file(destination), self.encrypted(), str(destination)

    def verify_remote_copy(self, digest: str) -> tuple[bool, str]:
        """Off-host confirmation. A copy on the disk that may fail is not a copy."""
        verifier = os.environ.get("DOCSURI_REMOTE_COPY_VERIFIER")
        if not verifier:
            return False, "no remote copy verifier configured"
        try:
            completed = subprocess.run(
                [verifier, digest], capture_output=True, text=True, timeout=60, check=False,
            )
        except (OSError, subprocess.SubprocessError) as error:
            return False, f"{type(error).__name__}: {error}"
        if completed.returncode != 0:
            return False, completed.stderr.strip() or "verifier reported failure"
        return digest in completed.stdout, "verifier did not confirm the digest"


@dataclass
class LocalRestoreTarget:
    """A restore destination identified by a NEW incarnation id."""

    root: Path
    incarnation_id: str
    required_free_bytes: int = 0

    def incarnation(self) -> str:
        return self.incarnation_id

    def restore(self, archive: Path) -> tuple[bool, str]:
        """Copy the archive file into the new incarnation directory.

        The archive is the exact dump produced by the cut. Restoring means placing it in the
        isolated target directory so it can be loaded by the acceptance test. The caller owns
        loading; this adapter only proves the file reached the new incarnation.
        """
        target = self.root / self.incarnation_id
        if not archive.is_file():
            return False, f"archive {archive} is missing"
        if target.exists():
            return False, f"restore target {target} already exists"
        if self.required_free_bytes and free_bytes(self.root) < self.required_free_bytes:
            return False, "insufficient free space for an isolated restore"
        try:
            target.mkdir(parents=True, exist_ok=False, mode=0o700)
        except OSError as error:
            return False, f"{type(error).__name__}: {error}"
        destination = target / f"{archive.stem}{archive.suffix}"
        try:
            shutil.copy2(archive, destination)
        except OSError as error:
            return False, f"copy failed: {type(error).__name__}: {error}"
        if not destination.is_file():
            return False, "archive not present after copy"
        return True, f"restored {archive.name} into {target}"


@dataclass
class LocalKeyLock:
    """Reports key and clock usability. Absent evidence is reported unusable, never assumed."""

    key_path: Path | None = None
    clock_evidence: Path | None = None
    clock_quality: str = "unknown"

    def key_unlocked(self) -> bool:
        if self.key_path is None or not self.key_path.is_file():
            return False
        try:
            with self.key_path.open("rb") as handle:
                handle.read(1)
        except PermissionError:
            return False
        except OSError:
            return False
        return True

    def clock_trusted(self) -> bool:
        if self.clock_quality != "trusted" or self.clock_evidence is None:
            return False
        return self.clock_evidence.is_file()


@dataclass
class ProcessObservation:
    """A sampled process tree: resident memory of the listener and every descendant."""

    pid: int
    rss_bytes: int
    children: list[ProcessObservation] = field(default_factory=list)

    def total_rss_bytes(self) -> int:
        return self.rss_bytes + sum(child.total_rss_bytes() for child in self.children)

    def pids(self) -> list[int]:
        found = [self.pid]
        for child in self.children:
            found.extend(child.pids())
        return found

    def as_dict(self) -> dict:
        return {
            "pid": self.pid,
            "rssBytes": self.rss_bytes,
            "totalRssBytes": self.total_rss_bytes(),
            "children": [child.as_dict() for child in self.children],
        }


class ProcessTreeSampler:
    """Samples a process tree's RSS via ``ps``, which needs no third-party dependency.

    ``ps`` is used rather than /proc because the acceptance host is macOS.
    """

    def __init__(self, *, ps_binary: str = "ps") -> None:
        self._ps = ps_binary

    def _table(self) -> dict[int, tuple[int, int]]:
        completed = subprocess.run(
            [self._ps, "-Ao", "pid=,ppid=,rss="],
            capture_output=True, text=True, timeout=15, check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError("process table unavailable")
        table: dict[int, tuple[int, int]] = {}
        for line in completed.stdout.splitlines():
            fields = line.split()
            if len(fields) != 3:
                continue
            try:
                pid, ppid, rss = (int(value) for value in fields)
            except ValueError:
                continue
            # ps reports RSS in KiB on both macOS and Linux.
            table[pid] = (ppid, rss * 1024)
        return table

    def sample(self, pid: int) -> ProcessObservation:
        table = self._table()
        if pid not in table:
            raise RuntimeError(f"process {pid} is not running")

        def build(target: int) -> ProcessObservation:
            _, rss = table[target]
            children = [
                build(child)
                for child, (parent, _) in table.items()
                if parent == target and child != target
            ]
            return ProcessObservation(pid=target, rss_bytes=rss, children=children)

        return build(pid)
