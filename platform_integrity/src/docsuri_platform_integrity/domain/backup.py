"""Backup and restore evidence. A missing condition is unready, never a partial success.

Every one of these signals is a reason a backup has *not* been proven: an absent archive, an
unverified off-host copy, a locked clock or key, or a writer that has not resolved. None of them
may be folded into a warning on an otherwise successful restore.
"""

from ..contracts.models import U64, Digest, Ref, Value
from .retention import DAY_US


class BackupEvidence(Value):
    """One backup attempt. Fields are observations, not claims the caller may omit."""

    cut_us: U64
    generation: Digest
    archive: Digest | None = None
    archive_encrypted: bool = False
    remote_copy_verified: bool = False
    restored_incarnation: Ref | None = None
    writer_resolved: bool = False
    clock_trusted: bool = False
    key_unlocked: bool = False
    rpo_us: U64 | None = None
    rto_us: U64 | None = None


def evaluate_backup(evidence: BackupEvidence, *, now_us: int) -> tuple[str, tuple[str, ...]]:
    """Return (verdict, reasons). Verdict is INCOMPLETE unless every condition is observed."""
    if type(now_us) is not int or now_us < 0:
        raise ValueError("invalid now")
    reasons = []
    if evidence.archive is None:
        reasons.append("archive_missing")
    elif not evidence.archive_encrypted:
        reasons.append("archive_not_encrypted")
    if not evidence.remote_copy_verified:
        # A backup that exists on exactly the disk that may fail is not a backup.
        reasons.append("no_verified_remote_copy")
    if not evidence.writer_resolved:
        # The cut is not a true snapshot while a writer can still append.
        reasons.append("writer_unresolved")
    if not evidence.clock_trusted:
        reasons.append("clock_untrusted")
    if not evidence.key_unlocked:
        reasons.append("key_locked")
    if evidence.restored_incarnation is None:
        reasons.append("restore_not_performed")
    cut = int(evidence.cut_us)
    if now_us < cut:
        reasons.append("cut_in_future")
    if evidence.rpo_us is not None and int(evidence.rpo_us) > max(0, now_us - cut) + DAY_US:
        reasons.append("rpo_outside_window")
    if evidence.rto_us is not None and int(evidence.rto_us) > 7 * DAY_US:
        reasons.append("rto_outside_window")
    return ("INCOMPLETE", tuple(sorted(set(reasons)))) if reasons else ("VERIFIED", ())


def cut_is_exact(cut_us: int, *, writer_epoch: str, observed_epoch: str) -> bool:
    """The cut belongs to one writer epoch. A rotation across the cut is not an exact cut."""
    if type(cut_us) is not int or cut_us < 0:
        raise ValueError("invalid cut")
    return isinstance(writer_epoch, str) and writer_epoch == observed_epoch
