"""Tar archives carrying a manifest of their members' checksums (U8 plan Step 31; BR4.3,
BR8.11, Workflow 19 step 3).

A directory tree reaches the backup agent as one tar archive: the search index's
exported documents, or the selected objects with their manifest. Its first member is
`manifest.json`, `{"members": {<name>: <sha256>}}`, naming every other member with the
SHA-256 of its bytes. `pack` builds one in memory; `verify` is the agent's integrity
check and the reader's check before use: every member is a regular file with a safe
relative name, the manifest lists exactly the other members, and each digest matches.
`unpack` returns the members' bytes only after `verify` passed.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import tarfile
from collections.abc import Mapping
from pathlib import Path

MANIFEST = "manifest.json"
MAX_MEMBERS = 100_000
MAX_MEMBER = 64 * 1024 * 1024
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,511}")


class ArchiveRefused(ValueError):
    """An archive whose members do not match its manifest; the message is fixed."""


def _safe(name: str) -> bool:
    return (_NAME.fullmatch(name) is not None and ".." not in name.split("/")
            and not name.startswith("/") and name != MANIFEST)


def pack(members: Mapping[str, bytes]) -> bytes:
    """A tar archive of `members` with its manifest first, deterministically ordered."""
    if not all(_safe(name) for name in members):
        raise ArchiveRefused("member name outside the archive's form")
    manifest = {"members": {name: hashlib.sha256(members[name]).hexdigest()
                            for name in sorted(members)}}
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for name, payload in [(MANIFEST, json.dumps(manifest, sort_keys=True).encode()),
                              *[(name, members[name]) for name in sorted(members)]]:
            info = tarfile.TarInfo(name)
            info.size, info.mode, info.mtime = len(payload), 0o600, 0
            archive.addfile(info, io.BytesIO(payload))
    return buffer.getvalue()


def _read(archive: tarfile.TarFile) -> tuple[dict, dict[str, bytes]]:
    members: dict[str, bytes] = {}
    manifest = None
    for count, info in enumerate(archive, start=1):
        if count > MAX_MEMBERS + 1 or not info.isreg() or info.size > MAX_MEMBER:
            raise ArchiveRefused("archive member outside its form")
        handle = archive.extractfile(info)
        payload = handle.read() if handle is not None else b""
        if info.name == MANIFEST:
            if manifest is not None:
                raise ArchiveRefused("archive manifest repeated")
            try:
                manifest = json.loads(payload)
            except ValueError:
                raise ArchiveRefused("archive manifest unreadable") from None
            continue
        if not _safe(info.name) or info.name in members:
            raise ArchiveRefused("archive member name outside its form")
        members[info.name] = payload
    if not isinstance(manifest, dict) or not isinstance(manifest.get("members"), dict):
        raise ArchiveRefused("archive manifest missing")
    return manifest["members"], members


def unpack_bytes(payload: bytes) -> dict[str, bytes]:
    """The members, once every one matches the manifest."""
    try:
        with tarfile.open(fileobj=io.BytesIO(payload), mode="r:") as archive:
            listed, members = _read(archive)
    except tarfile.TarError:
        raise ArchiveRefused("archive unreadable") from None
    if set(listed) != set(members):
        raise ArchiveRefused("archive members differ from the manifest")
    for name, payload_bytes in members.items():
        if hashlib.sha256(payload_bytes).hexdigest() != listed[name]:
            raise ArchiveRefused("archive member checksum differs")
    return members


def verify(path: Path) -> bool:
    """The agent's integrity check of a written tar archive."""
    try:
        unpack_bytes(path.read_bytes())
    except ArchiveRefused:
        return False
    return True
