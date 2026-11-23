"""Reading a copy back (U8 plan Step 25; BR4.3, BR9.12, Workflow 19 step 7).

`stream-back` (in person) streams one catalogued file to the operation that asked: a
production restore, an import or a ledger repair. The caller names the file by its
catalogue entry (path and digest); the agent streams it only when its catalogue lists
that file as written with that digest and the file on the volume, reached without
following a link, still has it. The caller checks the digest against the record, and a
tar archive's member checksums against its manifest, before use.

A restore verification never uses this path: the agent restores the set itself, so
its unattended commands never hand a file to a caller.
"""

from __future__ import annotations

import hashlib
import os
import stat
from typing import BinaryIO

from .catalogue import Catalogue, check_path
from .config import AgentConfig
from .writing import CHUNK, AgentRefused, file_digest


def stream_back(config: AgentConfig, catalogue: Catalogue, entry: dict, sink: BinaryIO) -> dict:
    if not isinstance(entry, dict) or set(entry) != {"path", "sha256"}:
        raise AgentRefused("input-field-refused")
    try:
        path = check_path(entry["path"])
    except ValueError:
        raise AgentRefused("path-refused") from None
    if not path.startswith("archives/"):
        raise AgentRefused("path-refused")
    listed = catalogue.files().get(path)
    if listed is None or listed.state not in ("written", "held") or listed.sha256 != entry[
        "sha256"
    ]:
        raise AgentRefused("not-catalogued")
    archive = config.u8_folder / path
    info = archive.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise AgentRefused("not-a-regular-file")
    if file_digest(archive) != listed.sha256:
        raise AgentRefused("digest-mismatch")
    digest, sent = hashlib.sha256(), 0
    descriptor = os.open(archive, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as source:
        while block := source.read(CHUNK):
            sink.write(block)
            digest.update(block)
            sent += len(block)
    sink.flush()
    if digest.hexdigest() != listed.sha256:
        raise AgentRefused("digest-mismatch")
    return {"path": path, "sha256": listed.sha256, "size": sent,
            "recordId": listed.record_id, "recordKind": listed.record_kind}
