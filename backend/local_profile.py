"""Explicit synthetic environment identity; never resolve ambient service settings."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import time
from dataclasses import dataclass
from pathlib import Path


def private_bytes(path: Path, *, maximum: int = 16384) -> bytes:
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
class LocalProfile:
    root: Path
    run_id: str
    origin: str
    database_port: int
    expires_at: float
    database_name: str = "docsuri_u1"
    realm: str = "diagnostic"

    def journey(self) -> LocalProfile:
        """Select only the explicitly provisioned second owned database."""
        path = self.root / "journey-database.json"
        value = json.loads(private_bytes(path))
        if (
            value.get("runId") != self.run_id
            or value.get("database") != "docsuri_u1_journey"
            or value.get("realm") != "journey"
            or value.get("state") != "ready"
        ):
            raise ValueError("journey database is not an established owned realm")
        return LocalProfile(
            self.root,
            self.run_id,
            self.origin,
            self.database_port,
            self.expires_at,
            "docsuri_u1_journey",
            "journey",
        )

    @classmethod
    def load(cls, manifest: Path) -> LocalProfile:
        expected = Path("/tmp/docsuri-u1-run").resolve() / "environment.json"
        if manifest.is_symlink() or manifest.resolve() != expected:
            raise ValueError("explicit owned synthetic manifest required")
        for path in (expected.parent, expected, expected.parent / "ownership.json"):
            info = path.lstat()
            if (
                stat.S_ISLNK(info.st_mode)
                or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) & 0o077
            ):
                raise ValueError("private synthetic environment ownership mismatch")
        raw = private_bytes(expected)
        if len(raw) > 16384:
            raise ValueError("manifest too large")
        value = json.loads(raw)
        marker = json.loads(private_bytes(expected.parent / "ownership.json"))
        if marker != {
            "runId": value.get("runId"),
            "manifestSha256": hashlib.sha256(raw).hexdigest(),
        }:
            raise ValueError("manifest identity mismatch")
        if value.get("profile") != "synthetic-local" or value.get("repository") != str(
            Path(__file__).resolve().parents[1]
        ):
            raise ValueError("wrong synthetic profile/repository")
        if "databaseAdminPassword" in value or not re.fullmatch(
            r"docsuri-u1-[0-9a-f]{16}", value.get("runId", "")
        ):
            raise ValueError("runtime manifest must not carry migration credentials")
        if value["expiresAt"] <= time.time():
            raise ValueError("synthetic retention expired")
        if value["applicationPort"] != 18039 or value["databasePort"] != 15439:
            raise ValueError("unexpected owned listener")
        return cls(
            expected.parent, value["runId"], "http://127.0.0.1:18039", 15439, value["expiresAt"]
        )
