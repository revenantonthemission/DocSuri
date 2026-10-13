"""The owned U7 synthetic-local environment profile.

Never resolve ambient service settings: the operator reads one private manifest
whose ownership marker binds its exact bytes, and a separate runtime credential
record. A U7 process never inherits production credentials.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import time
from dataclasses import dataclass
from pathlib import Path

RUN = Path("/tmp/docsuri-u7-run").resolve()
ENVIRONMENT_FILE = RUN / "environment.json"

_RUN_ID = re.compile(r"docsuri-u7-[0-9a-f]{16}")


def private_bytes(path: Path, *, maximum: int = 65536) -> bytes:
    """Read an owned regular file without blocking on a substituted FIFO/device."""
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(descriptor)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_size > maximum
        ):
            raise ValueError("private record must be a bounded owned regular file")
        raw = os.read(descriptor, maximum + 1)
        if len(raw) > maximum:
            raise ValueError("private record exceeds allocation")
        return raw
    finally:
        os.close(descriptor)


@dataclass(frozen=True)
class PlatformProfile:
    root: Path
    run_id: str
    database_port: int
    database_name: str
    database_image: str
    source_sha: str
    expires_at: float
    target_root: Path

    def runtime_credentials(self) -> dict:
        return self._credentials("runtime-credentials.json", "runtime")

    def provisioner_credentials(self) -> dict:
        return self._credentials("provisioner-credentials.json", "provisioner")

    def _credentials(self, name: str, role: str) -> dict:
        path = self.root / name
        value = json.loads(private_bytes(path))
        if (
            value.get("runId") != self.run_id
            or value.get("role") != role
            or not isinstance(value.get("password"), str)
        ):
            raise ValueError("owned credential record identity mismatch")
        return value

    @classmethod
    def load(cls, manifest: Path | None = None) -> PlatformProfile:
        expected = ENVIRONMENT_FILE
        requested = (manifest or expected).resolve()
        if requested != expected or (manifest or expected).is_symlink():
            raise ValueError("explicit owned synthetic manifest required")
        for path in (RUN, expected, RUN / "ownership.json"):
            info = path.lstat()
            if (
                stat.S_ISLNK(info.st_mode)
                or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) & 0o077
            ):
                raise ValueError("private synthetic environment ownership mismatch")
        raw = private_bytes(expected)
        value = json.loads(raw)
        marker = json.loads(private_bytes(RUN / "ownership.json"))
        if marker != {
            "runId": value.get("runId"),
            "manifestSha256": hashlib.sha256(raw).hexdigest(),
        }:
            raise ValueError("manifest identity mismatch")
        repo_root = Path(__file__).resolve().parents[4]
        if value.get("profile") != "synthetic-local" or value.get("repository") != str(
            repo_root
        ):
            raise ValueError("wrong synthetic profile/repository")
        if "databaseAdminPassword" in value:
            raise ValueError("runtime manifest must not carry migration credentials")
        if not _RUN_ID.fullmatch(value.get("runId", "")):
            raise ValueError("invalid resource ownership identity")
        if value["expiresAt"] <= time.time():
            raise ValueError("synthetic retention expired")
        return cls(
            root=RUN,
            run_id=value["runId"],
            database_port=int(value["databasePort"]),
            database_name=value["database"],
            database_image=value["databaseImage"],
            source_sha=value.get("sourceSha", "unknown"),
            expires_at=float(value["expiresAt"]),
            target_root=Path(value["targetRoot"]).resolve(),
        )
