"""Versioned private encryption custody for local account-control material.

Rotation retains decrypt-only prior keys. Removing one requires separate evidence
that no retained proof, factor or backup needs it; this module offers no removal.
The existing verifier-derived key is imported only as the legacy u2-v1 version.

The private-file mechanics live in the shared helper `backend.key_custody` (security
design §4.2, D1); this keyring is a thin setting of it. Its configuration stays at class
level, and `root`, `run_id` and `legacy_key` stay the only state of each instance, so
`ControlKeyring.__new__` followed by setting those three attributes still builds a
working keyring.
"""

from __future__ import annotations

import base64
import secrets
from pathlib import Path
from uuid import uuid4

from backend import key_custody
from backend.modules.accounts.control_policy import PolicyUnavailable


class ControlKeyring:
    filename = "account-control-keyring.json"
    custody = key_custody.CustodySettings(
        filename="account-control-keyring.json",
        lock_name="account-control-keyring.lock",
        marker_name="account-control-keyring.initialized",
        staging_prefix=".control-key-",
        version_pattern=r"u2-(?:v1|[0-9a-f]{32})",
        generation_min=1,
        generation_max=3,
        error=PolicyUnavailable,
        lock_message="account-control lock custody unavailable",
        custody_message="account-control encryption custody unavailable",
        missing_key_message="required retained encryption key unavailable",
    )

    def __init__(self, root: Path, run_id: str, legacy_key: bytes):
        if root.resolve() != Path("/tmp/docsuri-u2-run").resolve() or len(legacy_key) != 32:
            raise ValueError("owned account-control key allocation required")
        self.root, self.run_id, self.legacy_key = root, run_id, legacy_key
        self.read()

    def _lock(self):
        return key_custody.exclusive_lock(self.custody, self.root)

    def read(self) -> dict:
        if (
            not (self.root / self.filename).exists()
            and not (self.root / self.filename).is_symlink()
        ):
            if (self.root / self.custody.marker_name).exists():
                raise PolicyUnavailable(self.custody.custody_message)
            # Compatibility reads create no files. Only the trusted rotation command
            # establishes independently retained encryption-key custody.
            return {
                "runId": self.run_id,
                "active": "u2-v1",
                "generation": 1,
                "keys": {"u2-v1": base64.b64encode(self.legacy_key).decode()},
            }
        return key_custody.read_record(self.custody, self.root, self.run_id)

    def _write(self, value):
        key_custody.write(self.custody, self.root, value)

    @property
    def active_version(self):
        return self.read()["active"]

    def key(self, version: str) -> bytes:
        return key_custody.retained_key(self.custody, self.read(), version)

    def rotate(self) -> dict:
        """Trusted local operator only; caller stops writers and retains backup custody."""
        with self._lock():
            record = self.read()
            if len(record["keys"]) >= 3:
                raise PolicyUnavailable("keyring retention capacity requires an explicit decision")
            version = "u2-" + uuid4().hex
            record["keys"][version] = base64.b64encode(secrets.token_bytes(32)).decode()
            record["active"] = version
            record["generation"] += 1
            if not (self.root / self.custody.marker_name).exists():
                key_custody.create_marker(self.custody, self.root, self.run_id)
            # Marker first: a crash before the atomic ring write fails closed.
            self._write(record)
            return {
                "activeVersion": version,
                "generation": record["generation"],
                "retainedVersions": sorted(record["keys"]),
            }
