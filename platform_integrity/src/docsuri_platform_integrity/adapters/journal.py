"""Explicit bootstrap journal. A missing/truncated acknowledged tail is an error."""

import fcntl
import os
from pathlib import Path

from ..contracts.codec import canonical, decode, digest
from .filesystem import flush_directory, read_regular


class BootstrapJournal:
    def __init__(self, path: Path):
        self.path = path

    def inspect(self, *, expected_tail: str | None = None) -> tuple[dict, ...]:
        try:
            raw = read_regular(self.path, 64 * 1024**2)
        except FileNotFoundError:
            if expected_tail:
                raise ValueError("acknowledged journal missing") from None
            return ()
        if raw and not raw.endswith(b"\n"):
            raise ValueError("torn journal tail")
        records = []
        previous = None
        for index, line in enumerate(raw.splitlines()):
            frame = decode(line, max_bytes=256 * 1024)
            if (
                not isinstance(frame, dict)
                or set(frame) != {"sequence", "previous", "record"}
                or frame["sequence"] != str(index)
                or frame["previous"] != previous
            ):
                raise ValueError("journal gap or chain mismatch")
            previous = digest(canonical(frame))
            records.append(frame)
        if expected_tail is not None and previous != expected_tail:
            raise ValueError("acknowledged journal floor mismatch")
        return tuple(records)

    def append(self, record: dict, *, expected_tail: str | None) -> str:
        fd = os.open(self.path, os.O_CREAT | os.O_APPEND | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            existing = self.inspect(expected_tail=expected_tail)
            previous = digest(canonical(existing[-1])) if existing else None
            if previous != expected_tail:
                raise ValueError("journal tail changed")
            frame = {"sequence": str(len(existing)), "previous": previous, "record": record}
            payload = canonical(frame)
            if len(payload) > 256 * 1024:
                raise ValueError("journal frame limit")
            view = memoryview(payload + b"\n")
            while view:
                written = os.write(fd, view)
                if not written:
                    raise OSError("journal append incomplete")
                view = view[written:]
            os.fsync(fd)
            if hasattr(fcntl, "F_FULLFSYNC"):
                fcntl.fcntl(fd, fcntl.F_FULLFSYNC)
            flush_directory(self.path.parent)
            return digest(payload)
        finally:
            os.close(fd)
