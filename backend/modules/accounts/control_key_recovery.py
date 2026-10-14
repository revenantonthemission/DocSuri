"""Explicit same-disk synthetic key custody; never an automatic startup repair."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import stat
from pathlib import Path

from backend.modules.accounts.control_keys import ControlKeyring
from backend.modules.accounts.control_policy import PolicyUnavailable


def _read(path: Path, maximum: int) -> bytes:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_size > maximum
        ):
            raise PolicyUnavailable("private recovery custody unavailable")
        return stream.read(maximum + 1)


def _directory(root: Path) -> Path:
    target = root / "account-key-recovery"
    target.mkdir(mode=0o700, exist_ok=True)
    info = target.lstat()
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o700
    ):
        raise PolicyUnavailable("private recovery directory unavailable")
    return target


def _write_missing(path: Path, content: bytes):
    if path.exists() or path.is_symlink():
        if _read(path, 8192) != content:
            raise PolicyUnavailable("refusing to replace divergent current custody")
        return
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def capture(ring: ControlKeyring) -> dict:
    """Caller holds the stopped-writer run lock; snapshots are immutable."""
    with ring._lock():
        record = ring.read()
        verifier = _read(ring.root / "account-verifier.key", 32)
        expected = hmac.new(verifier, b"encryption\0u2-controls-v1", hashlib.sha256).digest()
        if len(verifier) != 32 or not hmac.compare_digest(expected, ring.key("u2-v1")):
            raise PolicyUnavailable("verifier and retained encryption custody disagree")
        marker = _read(ring.root / "account-control-keyring.initialized", 128)
        if marker != ring.run_id.encode():
            raise PolicyUnavailable("key initialization run mismatch")
        value = {
            "version": 1,
            "runId": ring.run_id,
            "generation": record["generation"],
            "keyring": record,
            "verifier": base64.b64encode(verifier).decode(),
        }
        data = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        digest = hashlib.sha256(data).hexdigest()
        _write_missing(_directory(ring.root) / (digest + ".json"), data)
        return {"runId": ring.run_id, "generation": record["generation"], "digest": digest}


def recover(root: Path, run_id: str, *, expected_digest: str, expected_generation: int) -> dict:
    """Explicit trusted operator recovery with externally retained exact identity.

    Existing custody must already match byte-for-byte. Only absent files can be
    recreated; old snapshots can never overwrite a newer live keyring.
    """
    if root.resolve() != Path("/tmp/docsuri-u2-run").resolve():
        raise ValueError("owned recovery root required")
    return _recover(root, run_id, expected_digest, expected_generation)


def _recover(root, run_id, digest, generation):
    if (
        not re.fullmatch("[0-9a-f]{64}", digest)
        or type(generation) is not int
        or not 1 <= generation <= 3
    ):
        raise PolicyUnavailable("exact recovery identity required")
    data = _read(_directory(root) / (digest + ".json"), 8192)
    if not hmac.compare_digest(hashlib.sha256(data).hexdigest(), digest):
        raise PolicyUnavailable("recovery digest mismatch")
    value = json.loads(data)
    if (
        set(value) != {"version", "runId", "generation", "keyring", "verifier"}
        or value["version"] != 1
        or value["runId"] != run_id
        or value["generation"] != generation
    ):
        raise PolicyUnavailable("recovery version or run mismatch")
    record = value["keyring"]
    verifier = base64.b64decode(value["verifier"], validate=True)
    if len(verifier) != 32 or record["runId"] != run_id or record["generation"] != generation:
        raise PolicyUnavailable("recovery material binding mismatch")
    expected = hmac.new(verifier, b"encryption\0u2-controls-v1", hashlib.sha256).digest()
    if not hmac.compare_digest(base64.b64decode(record["keys"]["u2-v1"], validate=True), expected):
        raise PolicyUnavailable("recovery verifier binding mismatch")
    ring = ControlKeyring.__new__(ControlKeyring)
    ring.root, ring.run_id, ring.legacy_key = root, run_id, expected
    with ring._lock():
        outputs = {
            "account-control-keyring.json": json.dumps(record).encode(),
            "account-control-keyring.initialized": run_id.encode(),
            "account-verifier.key": verifier,
        }
        # Validate all existing files before repairing any missing member.
        for name, content in outputs.items():
            path = root / name
            if path.exists() or path.is_symlink():
                actual = _read(path, 8192)
                matches = (
                    json.loads(actual) == record if name.endswith(".json") else actual == content
                )
                if not matches:
                    raise PolicyUnavailable("refusing to replace divergent current custody")
        for name, content in outputs.items():
            if not (root / name).exists():
                _write_missing(root / name, content)
        ring.read()
    return {"runId": run_id, "generation": generation, "digest": digest, "recovered": True}
