"""Shared private-file mechanics for local key custody (security design §4.2, D1).

This module holds only the mechanics U2's built keyring already had, moved here with no
change in behaviour so that U2's keyring and U6's token keyring share one implementation:

- the guarded read of a key record;
- the non-blocking exclusive lock;
- the staged write;
- publishing by atomic replace, with a folder sync;
- the exclusive creation of the initialized marker.

Each keyring configures it with a frozen `CustodySettings`. The helper offers no first
key, no re-sealing and no retirement: those decisions belong to each keyring.
"""

from __future__ import annotations

import base64
import fcntl
import json
import os
import re
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

RECORD_FIELDS = frozenset({"runId", "active", "generation", "keys"})
KEY_BYTES = 32


@dataclass(frozen=True)
class CustodySettings:
    """One keyring's file names, limits and refusal type.

    `error` is the exception type the helper raises for a custody fault; each message is
    the fixed text (or category token) it is raised with.
    """

    filename: str
    lock_name: str
    marker_name: str
    staging_prefix: str
    version_pattern: str
    generation_min: int
    generation_max: int
    error: type[Exception]
    lock_message: str
    custody_message: str
    missing_key_message: str
    max_versions: int = 3
    max_bytes: int = 4096

    def __post_init__(self):
        for name in (self.filename, self.lock_name, self.marker_name, self.staging_prefix):
            if not name or "/" in name or name in {".", ".."}:
                raise ValueError("custody file names must be plain names")
        if not 1 <= self.generation_min <= self.generation_max:
            raise ValueError("custody generation range required")
        if self.max_versions < 1 or self.max_bytes <= 0:
            raise ValueError("custody bounds required")
        re.compile(self.version_pattern)


def sync_folder(root: Path) -> None:
    """Make a rename, link, create or unlink inside `root` durable."""
    directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


@contextmanager
def exclusive_lock(settings: CustodySettings, root: Path) -> Iterator[None]:
    """The lock file, created without following links, checked, then a non-blocking flock.

    A held lock raises the operating system's `BlockingIOError` unchanged; a lock file
    with the wrong type, owner or mode raises the configured custody error.
    """
    fd = os.open(root / settings.lock_name, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
        ):
            raise settings.error(settings.lock_message)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(fd)


def _unique_fields(pairs):
    record = {}
    for key, item in pairs:
        if key in record:
            raise ValueError("duplicate key custody field")
        record[key] = item
    return record


def _check_record(settings: CustodySettings, value, run_id: str) -> None:
    if (
        set(value) != RECORD_FIELDS
        or value["runId"] != run_id
        or type(value["generation"]) is not int
        or not isinstance(value["keys"], dict)
        or not settings.generation_min <= value["generation"] <= settings.generation_max
        or not 1 <= len(value["keys"]) <= settings.max_versions
        or value["active"] not in value["keys"]
    ):
        raise ValueError("keyring identity mismatch")
    for version, encoded in value["keys"].items():
        if (
            not re.fullmatch(settings.version_pattern, version)
            or len(base64.b64decode(encoded, validate=True)) != KEY_BYTES
        ):
            raise ValueError("bounded encryption key version required")


def read_record(settings: CustodySettings, root: Path, run_id: str) -> dict:
    """The guarded read of an existing key file.

    It requires a regular file reached without following a link, owned by this user, at
    mode 0600 and within the size bound; no duplicate JSON field; the run id; one to
    `max_versions` 32-byte keys whose versions match the pattern; and a generation in
    range. Any fault raises the configured custody error, chained from its cause.
    """
    try:
        fd = os.open(root / settings.filename, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd) as stream:
            info = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_size > settings.max_bytes
            ):
                raise ValueError("private key custody mismatch")
            value = json.load(stream, object_pairs_hook=_unique_fields)
        _check_record(settings, value, run_id)
        return value
    except (OSError, ValueError, TypeError, KeyError) as error:
        raise settings.error(settings.custody_message) from error


def retained_key(settings: CustodySettings, record: dict, version: str) -> bytes:
    """One retained key of a record that already passed the guarded read."""
    if version not in record["keys"]:
        raise settings.error(settings.missing_key_message)
    return base64.b64decode(record["keys"][version], validate=True)


def stage(settings: CustodySettings, root: Path, value: dict) -> Path:
    """Write `value` to a fresh staging file (exclusive, 0600) and sync it.

    The caller publishes the staging file and always removes the staging name.
    """
    staging = root / (settings.staging_prefix + uuid4().hex)
    fd = os.open(staging, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        staging.unlink(missing_ok=True)
        raise
    return staging


def write(settings: CustodySettings, root: Path, value: dict) -> None:
    """The staged write, published by atomic replace and a folder sync."""
    staging = stage(settings, root, value)
    try:
        os.replace(staging, root / settings.filename)
        sync_folder(root)
    finally:
        staging.unlink(missing_ok=True)


def create_marker(settings: CustodySettings, root: Path, content: str) -> None:
    """Create the initialized marker exclusively, sync it, then sync the folder.

    An existing marker raises `FileExistsError`; callers that create it only when absent
    check first.
    """
    marker = root / settings.marker_name
    fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    sync_folder(root)
