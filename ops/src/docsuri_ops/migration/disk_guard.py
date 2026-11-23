"""The internal-disk guard of a migration run (U8 plan Steps 31 and 68(a)-(b); BR6.6, S3,
Workflow 9 step 2).

Before the import restore and again before each import phase, the internal disk's free
space, less what the run still has to write (the snapshot's dumped database and the
estimate of the rehearsal database it builds, less what the run's target and import
databases already hold), must stay above the threshold (20 GiB,
`internal_disk_threshold_bytes`); otherwise the run is interrupted with
`internal-disk-low`.

A running import also stops at its next boundary (S3): `boundary` gives the check the
import phases call before each phase and before each paper. Below the critical floor
(10 GiB, `internal_disk_critical_bytes`) it stops at either kind of boundary with
`internal-disk-critical`; at a phase start it also applies the room rule above, reading
what the databases hold at that moment (`internal-disk-low`).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

LOW = "internal-disk-low"
CRITICAL = "internal-disk-critical"


def policy_critical_bytes() -> int:
    """The production policy's critical floor (`internal_disk_critical_bytes`, Step
    68(b)), read from the policy itself so a guard built without the argument follows
    any change to it."""
    from backend.u8_policy import PRODUCTION_OPERATIONS

    return PRODUCTION_OPERATIONS.internal_disk_critical_bytes


class DiskStopped(Exception):
    """A boundary found the disk too full to go on; `reason` is LOW or CRITICAL."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class DiskGuard:
    free_bytes: Callable[[], int]
    threshold_bytes: int
    critical_bytes: int = field(default_factory=policy_critical_bytes)

    def room(self, *, to_write: int, written: int = 0) -> bool:
        remaining = max(0, int(to_write) - int(written))
        return self.free_bytes() - remaining > self.threshold_bytes

    def boundary(self, *, to_write: int,
                 held: Callable[[], int]) -> Callable[[str], None]:
        """The import's boundary check: called with `"phase"` before each phase and with
        `"paper"` before each paper; it reads the free space once per call. A phase start
        reads what is held first, the order `room`'s callers use, so database growth
        between the two readings can only make the check stricter."""

        def check(kind: str) -> None:
            written = int(held()) if kind == "phase" else 0
            free = int(self.free_bytes())
            if free < self.critical_bytes:
                raise DiskStopped(CRITICAL)
            if kind == "phase":
                remaining = max(0, int(to_write) - written)
                if free - remaining <= self.threshold_bytes:
                    raise DiskStopped(LOW)

        return check
