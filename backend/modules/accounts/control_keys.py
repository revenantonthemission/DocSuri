"""Versioned private encryption custody for local account-control material.

Rotation retains decrypt-only prior keys. Removing one requires separate evidence
that no retained proof, factor or backup needs it; this module offers no removal.
The existing verifier-derived key is imported only as the legacy u2-v1 version.
"""

from __future__ import annotations

import base64
import fcntl
import json
import os
import re
import secrets
import stat
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from backend.modules.accounts.control_policy import PolicyUnavailable


class ControlKeyring:
    filename = "account-control-keyring.json"

    def __init__(self, root: Path, run_id: str, legacy_key: bytes):
        if root.resolve() != Path("/tmp/docsuri-u2-run").resolve() or len(legacy_key) != 32:
            raise ValueError("owned account-control key allocation required")
        self.root, self.run_id, self.legacy_key = root, run_id, legacy_key
        self.read()

    @contextmanager
    def _lock(self):
        fd = os.open(
            self.root / "account-control-keyring.lock",
            os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW,
            0o600,
        )
        try:
            info = os.fstat(fd)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600
            ):
                raise PolicyUnavailable("account-control lock custody unavailable")
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield
        finally:
            os.close(fd)

    def read(self) -> dict:
        if (
            not (self.root / self.filename).exists()
            and not (self.root / self.filename).is_symlink()
        ):
            if (self.root / "account-control-keyring.initialized").exists():
                raise PolicyUnavailable("account-control encryption custody unavailable")
            # Compatibility reads create no files. Only the trusted rotation command
            # establishes independently retained encryption-key custody.
            return {
                "runId": self.run_id,
                "active": "u2-v1",
                "generation": 1,
                "keys": {"u2-v1": base64.b64encode(self.legacy_key).decode()},
            }
        try:
            fd = os.open(self.root / self.filename, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd) as stream:
                info = os.fstat(stream.fileno())
                if (
                    not stat.S_ISREG(info.st_mode)
                    or info.st_uid != os.getuid()
                    or stat.S_IMODE(info.st_mode) != 0o600
                    or info.st_size > 4096
                ):
                    raise ValueError("private key custody mismatch")

                def unique(pairs):
                    record = {}
                    for key, item in pairs:
                        if key in record:
                            raise ValueError("duplicate key custody field")
                        record[key] = item
                    return record

                value = json.load(stream, object_pairs_hook=unique)
            if (
                set(value) != {"runId", "active", "generation", "keys"}
                or value["runId"] != self.run_id
                or type(value["generation"]) is not int
                or not isinstance(value["keys"], dict)
                or not 1 <= value["generation"] <= 3
                or not 1 <= len(value["keys"]) <= 3
                or value["active"] not in value["keys"]
            ):
                raise ValueError("keyring identity mismatch")
            for version, encoded in value["keys"].items():
                if (
                    not re.fullmatch(r"u2-(?:v1|[0-9a-f]{32})", version)
                    or len(base64.b64decode(encoded, validate=True)) != 32
                ):
                    raise ValueError("bounded encryption key version required")
            return value
        except (OSError, ValueError, TypeError, KeyError) as error:
            raise PolicyUnavailable("account-control encryption custody unavailable") from error

    def _write(self, value):
        path = self.root / self.filename
        staging = self.root / (".control-key-" + uuid4().hex)
        fd = os.open(staging, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(fd, "w") as stream:
                json.dump(value, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(staging, path)
            directory = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            staging.unlink(missing_ok=True)

    @property
    def active_version(self):
        return self.read()["active"]

    def key(self, version: str) -> bytes:
        record = self.read()
        if version not in record["keys"]:
            raise PolicyUnavailable("required retained encryption key unavailable")
        return base64.b64decode(record["keys"][version], validate=True)

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
            marker = self.root / "account-control-keyring.initialized"
            if not marker.exists():
                fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                with os.fdopen(fd, "w") as stream:
                    stream.write(self.run_id)
                    stream.flush()
                    os.fsync(stream.fileno())
                directory = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
            # Marker first: a crash before the atomic ring write fails closed.
            self._write(record)
            return {
                "activeVersion": version,
                "generation": record["generation"],
                "retainedVersions": sorted(record["keys"]),
            }
