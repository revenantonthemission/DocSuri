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


@dataclass(frozen=True)
class LocalProfile:
    root: Path
    run_id: str
    origin: str
    database_port: int
    expires_at: float

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
        raw = expected.read_bytes()
        if len(raw) > 16384:
            raise ValueError("manifest too large")
        value = json.loads(raw)
        marker = json.loads((expected.parent / "ownership.json").read_text())
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
