"""Explicit synthetic environment identity; never resolve ambient service settings."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat
import time
from dataclasses import dataclass
from pathlib import Path

RUN_PARENT = Path("/tmp")


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
        if self.realm == "account-controls" and self.database_name == "docsuri_u2":
            return self
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
            "https://127.0.0.1:18039",
            self.database_port,
            self.expires_at,
            "docsuri_u1_journey",
            "journey",
        )

    @staticmethod
    def _identity(manifest: Path) -> tuple[Path, str, dict]:
        """Validate custody and realm identity without granting runtime use."""
        profiles = {
            (RUN_PARENT / f"docsuri-{unit}-run").resolve() / "environment.json": unit
            for unit in ("u1", "u2", "u3", "u4", "u5")
        }
        expected = manifest.resolve()
        unit = profiles.get(expected)
        if manifest.is_symlink() or manifest.parent.is_symlink() or unit is None:
            raise ValueError("explicit owned synthetic manifest required")
        if (RUN_PARENT / f"docsuri-{unit}-run").is_symlink():
            raise ValueError("owned run root cannot be a symbolic link")
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
            rf"docsuri-{unit}-[0-9a-f]{{16}}", value.get("runId", "")
        ):
            raise ValueError("runtime manifest must not carry migration credentials")
        ports = {
            "u1": (18039, 15439), "u2": (18049, 15449),
            "u3": (18059, 15459), "u4": (18079, 15479),
            "u5": (18089, 15489),
        }
        application_port, database_port = ports[unit]
        if value["applicationPort"] != application_port or value["databasePort"] != database_port:
            raise ValueError("unexpected owned listener")
        realms = {
            "u2": ("u2-account-personal-controls", "account-controls"),
            "u3": ("u3-paper-corpus-capabilities", "corpus-maintenance"),
            "u4": ("u4-research-novelty", "research-workspace"),
            "u5": ("u5-topics-digests", "topics-digests"),
        }
        if unit in realms:
            unit_name, realm = realms[unit]
            if (
                value.get("unit") != unit_name
                or value.get("database") != f"docsuri_{unit}"
                or value.get("realm") != realm
            ):
                raise ValueError(f"wrong {unit.upper()} owned realm")
        return expected, unit, value

    @classmethod
    def preservation_identity(cls, manifest: Path) -> dict:
        """Return validated finite metadata for preservation, never a runtime profile.

        Expiry prevents execution but must not prevent preserving an idle realm.
        There is no runtime-input flag to relax load(), and all custody and realm
        checks are shared with it. The caller must still prove resource ownership
        and idleness before any stop or move.
        """
        _, _, value = cls._identity(manifest)
        created, expires = value.get("createdAt"), value.get("expiresAt")
        if (
            type(created) not in (int, float)
            or type(expires) not in (int, float)
            or not math.isfinite(created)
            or not math.isfinite(expires)
            or not 0 < created <= time.time()
            or not created < expires <= created + 86400
        ):
            raise ValueError("preservation requires finite original retention")
        return value

    @classmethod
    def load(cls, manifest: Path) -> LocalProfile:
        expected, unit, value = cls._identity(manifest)
        now = time.time()
        if value["expiresAt"] <= now:
            raise ValueError("synthetic retention expired")
        if unit != "u1":
            if not now < value["expiresAt"] <= now + 86400:
                raise ValueError(f"wrong {unit.upper()} finite retention")
            return cls(
                expected.parent, value["runId"],
                f"https://127.0.0.1:{value['applicationPort']}",
                value["databasePort"], value["expiresAt"],
                value["database"], value["realm"],
            )
        return cls(
            expected.parent, value["runId"], "http://127.0.0.1:18039", 15439, value["expiresAt"]
        )
