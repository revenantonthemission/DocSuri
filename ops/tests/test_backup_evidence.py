"""Backup evidence must never read as a partial success, and must never claim operator data.

Each missing condition gets its own test, because the failure mode this guards against is a
condition quietly being absorbed into an otherwise-passing verdict.
"""

from __future__ import annotations

import os
import stat
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import pytest
from docsuri_platform_integrity.domain.retention import RetentionPolicy

from docsuri_ops.adapters.backup import (
    LocalDriveArchive,
    LocalKeyLock,
    LocalRestoreTarget,
    ProcessObservation,
    ProcessTreeSampler,
    filevault_encrypted,
)
from docsuri_ops.backup_evidence import (
    MANAGED_MARKER,
    BackupCut,
    LocalHostLock,
    ManagedPath,
    collect_backup_evidence,
    collect_expired_backups,
    digest_file,
    iter_backup_candidates,
)

DAY_US = 86_400 * 1_000_000
# A realistic instant: a synthetic far-future microsecond value overflows what a
# filesystem will actually store for mtime, which would silently invalidate the aging tests.
NOW = int(time.time() * 1_000_000)
PINNED = "sha256:" + "a" * 64


@dataclass
class FakeArchive:
    available_result: tuple[bool, str] = (True, "mounted")
    write_result: tuple[str | None, bool, str] | None = None
    remote_result: tuple[bool, str] = (True, "confirmed")

    def available(self):
        return self.available_result

    def write_archive(self, source, *, name):
        if self.write_result is not None:
            return self.write_result
        return PINNED, True, f"{name}.archive"

    def verify_remote_copy(self, digest):
        return self.remote_result


@dataclass
class FakeRestore:
    incarnation_id: str = "incarnation-two"
    restore_result: tuple[bool, str] = (True, "restored")

    def incarnation(self):
        return self.incarnation_id

    def restore(self, archive):
        return self.restore_result


@dataclass
class FakeLock:
    key: bool = True
    clock: bool = True

    def key_unlocked(self):
        return self.key

    def clock_trusted(self):
        return self.clock


def cut(tmp_path: Path) -> BackupCut:
    source = tmp_path / "source.dump"
    source.write_bytes(b"payload")
    return BackupCut(
        cut_us=NOW - DAY_US, generation=PINNED,
        writer_epoch="epoch-a", source=source,
    )


def gather(tmp_path, **overrides):
    kwargs = dict(
        archive=FakeArchive(), restore=FakeRestore(), key_lock=FakeLock(),
        now_us=NOW, managed_root=tmp_path / "managed",
    )
    kwargs.update(overrides)
    return collect_backup_evidence(cut(tmp_path), **kwargs)


# -- the happy path, and each way it fails --------------------------------


def test_a_fully_observed_backup_verifies(tmp_path):
    report = gather(tmp_path)
    assert report.verified
    assert report.verdict == "VERIFIED" and report.reasons == ()
    assert report.evidence.restored_incarnation == "incarnation-two"


def test_a_missing_drive_is_incomplete(tmp_path):
    report = gather(tmp_path, archive=FakeArchive(available_result=(False, "not mounted")))
    assert not report.verified
    assert "archive_missing" in report.reasons
    assert any("not mounted" in note for note in report.notes)


def test_a_backup_with_no_verified_remote_copy_is_incomplete(tmp_path):
    report = gather(tmp_path, archive=FakeArchive(remote_result=(False, "no off-host copy")))
    assert not report.verified
    assert "no_verified_remote_copy" in report.reasons


def test_an_unencrypted_archive_is_incomplete(tmp_path):
    report = gather(tmp_path, archive=FakeArchive(write_result=(PINNED, False, "plain")))
    assert not report.verified
    assert "archive_not_encrypted" in report.reasons


def test_a_locked_key_is_incomplete(tmp_path):
    report = gather(tmp_path, key_lock=FakeLock(key=False))
    assert not report.verified
    assert "key_locked" in report.reasons


def test_an_untrusted_clock_is_incomplete(tmp_path):
    report = gather(tmp_path, key_lock=FakeLock(clock=False))
    assert not report.verified
    assert "clock_untrusted" in report.reasons


def test_an_unresolved_writer_is_incomplete(tmp_path):
    report = gather(tmp_path, writer_resolved=False)
    assert not report.verified
    assert "writer_unresolved" in report.reasons


def test_an_archive_write_that_yields_no_digest_is_incomplete(tmp_path):
    report = gather(tmp_path, archive=FakeArchive(write_result=(None, False, "ENOSPC")))
    assert not report.verified
    assert "archive_missing" in report.reasons


# -- the new-incarnation rule ---------------------------------------------


def test_restoring_onto_the_cut_incarnation_proves_nothing(tmp_path):
    report = gather(tmp_path, restore=FakeRestore(incarnation_id="epoch-a"))
    assert not report.verified
    assert "restore_not_performed" in report.reasons
    assert any("not a new one" in note for note in report.notes)


def test_a_failed_restore_is_incomplete(tmp_path):
    report = gather(tmp_path, restore=FakeRestore(restore_result=(False, "corrupt archive")))
    assert not report.verified
    assert "restore_not_performed" in report.reasons


# -- exact cut -------------------------------------------------------------


def test_a_cut_spanning_a_writer_rotation_is_not_exact(tmp_path):
    report = gather(tmp_path, observed_writer_epoch="epoch-b")
    assert not report.verified
    assert "writer_unresolved" in report.reasons
    assert any("rotation" in note for note in report.notes)


# -- retention must not touch pre-existing data ---------------------------


def test_managed_paths_are_marked_and_recorded(tmp_path):
    managed = tmp_path / "managed"
    report = gather(tmp_path)
    assert managed.is_dir()
    assert (managed / MANAGED_MARKER).is_file()
    assert report.managed_paths == [managed]


def test_claim_marker_is_owner_only_readable(tmp_path):
    managed = ManagedPath(tmp_path / "m").claim()
    mode = stat.S_IMODE((managed / MANAGED_MARKER).stat().st_mode)
    assert mode == 0o600
    assert stat.S_IMODE(managed.stat().st_mode) == 0o700


def test_claim_is_idempotent_and_never_rewrites_the_marker(tmp_path):
    managed = ManagedPath(tmp_path / "m")
    first = managed.claim()
    marker = first / MANAGED_MARKER
    marker.write_text("operator edited\n", encoding="utf-8")
    second = managed.claim()
    assert first == second
    assert (second / MANAGED_MARKER).read_text(encoding="utf-8") == "operator edited\n"


def test_pre_existing_backups_are_never_marked_managed(tmp_path):
    """Enabling retention must not reach into an operator's own backup directory."""
    root = tmp_path / "backups"
    preexisting = root / "hand-made-2020.tar.gz"
    preexisting.parent.mkdir(parents=True)
    preexisting.write_bytes(b"not ours")
    managed = root / "rem1-2026"
    managed.mkdir()
    (managed / MANAGED_MARKER).write_text("x", encoding="utf-8")

    entries = list(iter_backup_candidates(root))
    assert preexisting in entries and managed in entries
    # Enumerating is fine; only the marker distinguishes ownership, and the operator's entry
    # has none.
    assert not ManagedPath.is_managed(preexisting)
    assert ManagedPath.is_managed(managed)


def test_missing_root_enumerates_nothing(tmp_path):
    assert list(iter_backup_candidates(tmp_path / "absent")) == []


# -- report shape ----------------------------------------------------------


def test_report_serialises_without_leaking_material(tmp_path):
    payload = gather(tmp_path).as_dict()
    assert payload["state"] == "VERIFIED"
    assert set(payload) >= {
        "verdict", "reasons", "cutUs", "archive", "remoteCopyVerified",
        "restoredIncarnation", "managedPaths",
    }
    serialised = repr(payload).lower()
    for secret in ("passphrase", "private key", "password", "secret"):
        assert secret not in serialised


def test_state_is_incomplete_when_the_verdict_is(tmp_path):
    report = gather(tmp_path, key_lock=FakeLock(key=False))
    assert report.as_dict()["state"] == "INCOMPLETE"


# -- digest helper ---------------------------------------------------------


def test_digest_is_stable_and_differs_by_content(tmp_path):
    payload = tmp_path / "big"
    payload.write_bytes(b"a" * (3 << 20))
    other = tmp_path / "other"
    other.write_bytes(b"b" * (3 << 20))
    assert digest_file(payload) == digest_file(payload)
    assert digest_file(payload).startswith("sha256:")
    assert digest_file(payload) != digest_file(other)


# -- local adapters --------------------------------------------------------


def test_unmounted_drive_is_reported_unavailable(tmp_path):
    archive = LocalDriveArchive(mount=tmp_path / "absent")
    available, reason = archive.available()
    assert not available and "not a mounted directory" in reason


def test_drive_write_refuses_to_silently_replace_an_existing_archive(tmp_path):
    drive = tmp_path / "drive"
    drive.mkdir()
    source = tmp_path / "s.dump"
    source.write_bytes(b"x")
    archive = LocalDriveArchive(mount=drive, encryption_probe="false")
    (drive / "g.archive").write_bytes(b"pre-existing")
    digest, encrypted, detail = archive.write_archive(source, name="g")
    assert digest is None and encrypted is False and "already exists" in detail


def test_drive_without_an_encryption_probe_report_is_unavailable(tmp_path):
    drive = tmp_path / "drive"
    drive.mkdir()
    archive = LocalDriveArchive(mount=drive, encryption_probe="false")
    available, reason = archive.available()
    assert not available and "encrypted" in reason


def test_remote_copy_without_a_verifier_is_never_verified(tmp_path):
    drive = tmp_path / "drive"
    drive.mkdir()
    os.environ.pop("DOCSURI_REMOTE_COPY_VERIFIER", None)
    ok, reason = LocalDriveArchive(mount=drive).verify_remote_copy(PINNED)
    assert not ok and "no remote copy verifier" in reason


def test_restore_refuses_to_overwrite_an_existing_incarnation(tmp_path):
    target = LocalRestoreTarget(root=tmp_path, incarnation_id="inc")
    (tmp_path / "inc").mkdir()
    archive = tmp_path / "a.archive"
    archive.write_bytes(b"x")
    ok, detail = target.restore(archive)
    assert not ok and "already exists" in detail


def test_restore_refuses_a_missing_archive(tmp_path):
    target = LocalRestoreTarget(root=tmp_path, incarnation_id="inc2")
    ok, detail = target.restore(tmp_path / "absent.archive")
    assert not ok and "missing" in detail


def test_locked_key_file_is_reported_locked(tmp_path):
    key = tmp_path / "key"
    key.write_bytes(b"k")
    key.chmod(0o000)
    try:
        assert LocalKeyLock(key_path=key).key_unlocked() is False
    finally:
        key.chmod(0o600)
    assert LocalKeyLock(key_path=key).key_unlocked() is True


def test_absent_key_is_reported_locked(tmp_path):
    assert LocalKeyLock(key_path=tmp_path / "absent").key_unlocked() is False
    assert LocalKeyLock().key_unlocked() is False


def test_clock_is_untrusted_without_a_trusted_quality_and_evidence(tmp_path):
    assert LocalKeyLock().clock_trusted() is False
    evidence = tmp_path / "clock.json"
    evidence.write_text("{}", encoding="utf-8")
    assert LocalKeyLock(clock_evidence=evidence).clock_trusted() is False
    assert LocalKeyLock(
        clock_evidence=evidence, clock_quality="trusted"
    ).clock_trusted() is True


# -- process observation ---------------------------------------------------


def test_process_tree_totals_include_children():
    tree = ProcessObservation(
        pid=1, rss_bytes=100,
        children=[ProcessObservation(pid=2, rss_bytes=20,
                                     children=[ProcessObservation(pid=3, rss_bytes=5)])],
    )
    assert tree.total_rss_bytes() == 125
    assert tree.pids() == [1, 2, 3]
    assert tree.as_dict()["totalRssBytes"] == 125


def test_sampler_reads_the_real_process_tree():
    tree = ProcessTreeSampler().sample(os.getpid())
    assert tree.pid == os.getpid()
    assert tree.total_rss_bytes() > 0


def test_sampler_reports_a_missing_process_rather_than_zero():
    with pytest.raises(RuntimeError):
        ProcessTreeSampler().sample(2**30)


def test_locked_host_clock_port_defaults_to_unproven(tmp_path):
    """The documented host lock adapter must not report a usable key/clock by default."""
    lock = LocalHostLock()
    assert lock.key_unlocked() is False
    assert lock.clock_trusted() is False


# -- executable collection: the guarantee, not just the marker -------------


def _aged(root: Path, name: Path, days: int) -> None:
    # ns= is required: passing float seconds loses precision at this magnitude and APFS clamps
    # the result, which would silently age the entry to something uncollectable.
    old_ns = (NOW - days * DAY_US) * 1000
    os.utime(root / name, ns=(old_ns, old_ns))


def test_a_pre_existing_backup_survives_collection(tmp_path):
    """The central guarantee: an old, unmanaged, operator-made backup is never collected."""
    root = tmp_path / "backups"
    root.mkdir()
    (root / "hand-made.tar.gz").write_bytes(b"operator data")
    _aged(root, "hand-made.tar.gz", 3650)

    result = collect_expired_backups(
        root, now_us=NOW, policy=RetentionPolicy(), approved=True, dry_run=False
    )
    assert result.removed == []
    assert (root / "hand-made.tar.gz").read_bytes() == b"operator data"
    assert result.retained[0][1] == "unmanaged"


def test_a_fresh_managed_backup_is_retained(tmp_path):
    root = tmp_path / "backups"
    managed = ManagedPath(root / "rem1").claim()
    (managed / "a.archive").write_bytes(b"x")
    result = collect_expired_backups(
        root, now_us=NOW, policy=RetentionPolicy(), dry_run=False
    )
    assert result.removed == []
    assert (root / "rem1").exists()


def test_an_expired_managed_backup_is_collected(tmp_path):
    root = tmp_path / "backups"
    managed = ManagedPath(root / "rem1").claim()
    (managed / "a.archive").write_bytes(b"x")
    _aged(root, "rem1", 20)
    result = collect_expired_backups(
        root, now_us=NOW, policy=RetentionPolicy(), dry_run=False
    )
    assert result.removed == [root / "rem1"]
    assert not (root / "rem1").exists()


def test_critical_managed_backup_needs_approval(tmp_path):
    root = tmp_path / "backups"
    managed = ManagedPath(root / "rem1").claim()
    (managed / "critical").write_text("", encoding="utf-8")
    _aged(root, "rem1", 400)

    without = collect_expired_backups(
        root, now_us=NOW, policy=RetentionPolicy(), approved=False, dry_run=False
    )
    assert without.removed == [] and (root / "rem1").exists()

    with_approval = collect_expired_backups(
        root, now_us=NOW, policy=RetentionPolicy(), approved=True, dry_run=False
    )
    assert with_approval.removed == [root / "rem1"]


def test_dry_run_reports_without_deleting(tmp_path):
    root = tmp_path / "backups"
    ManagedPath(root / "rem1").claim()
    _aged(root, "rem1", 20)
    result = collect_expired_backups(
        root, now_us=NOW, policy=RetentionPolicy(), dry_run=True
    )
    assert result.removed == [root / "rem1"]
    assert (root / "rem1").exists()
    assert result.as_dict()["dryRun"] is True


def test_an_unresolved_writer_blocks_collection(tmp_path):
    """An appending writer is not safe to collect from, regardless of age or approval."""
    root = tmp_path / "backups"
    ManagedPath(root / "rem1").claim()
    _aged(root, "rem1", 400)
    result = collect_expired_backups(
        root, now_us=NOW, policy=RetentionPolicy(), approved=True,
        writer_resolved=False, dry_run=False,
    )
    assert result.removed == []
    assert (root / "rem1").exists()
    assert result.retained[0][1] == "writer_unresolved"


def test_a_resolved_writer_allows_the_same_collection(tmp_path):
    root = tmp_path / "backups"
    ManagedPath(root / "rem1").claim()
    _aged(root, "rem1", 20)
    result = collect_expired_backups(
        root, now_us=NOW, policy=RetentionPolicy(), writer_resolved=True, dry_run=False
    )
    assert result.removed == [root / "rem1"]


# -- encryption detection on the real platform -----------------------------


def _fake_diskutil(monkeypatch, *, stdout: bytes, returncode: int = 0):
    completed = subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=b""
    )
    monkeypatch.setattr(
        "docsuri_ops.adapters.backup.subprocess.run", lambda *a, **k: completed
    )


def test_filevault_probe_reads_the_volume_plist(monkeypatch, tmp_path):
    _fake_diskutil(monkeypatch, stdout=b"<plist><dict><key>FileVault</key><true/></dict></plist>")
    assert filevault_encrypted(tmp_path) is True


def test_filevault_probe_reports_a_plain_volume_as_unencrypted(monkeypatch, tmp_path):
    _fake_diskutil(monkeypatch, stdout=b"<plist><dict><key>FileVault</key><false/></dict></plist>")
    assert filevault_encrypted(tmp_path) is False


def test_filevault_probe_fails_closed_on_diskutil_failure(monkeypatch, tmp_path):
    _fake_diskutil(monkeypatch, stdout=b"", returncode=1)
    assert filevault_encrypted(tmp_path) is False


def test_filevault_probe_fails_closed_on_unparseable_output(monkeypatch, tmp_path):
    _fake_diskutil(monkeypatch, stdout=b"cryptutil: command not found")
    assert filevault_encrypted(tmp_path) is False


def test_the_default_probe_is_filevault_not_a_missing_cryptutil(monkeypatch, tmp_path):
    """A missing `cryptutil` must never be read as "this volume is unencrypted"."""
    _fake_diskutil(monkeypatch, stdout=b"<plist><dict><key>FileVault</key><true/></dict></plist>")
    assert LocalDriveArchive(mount=tmp_path).encrypted() is True


def test_an_encryption_probe_that_raises_is_treated_as_unencrypted(tmp_path):
    def boom(_mount):
        raise RuntimeError("probe exploded")

    assert LocalDriveArchive(mount=tmp_path, encryption_probe=boom).encrypted() is False


def test_a_callable_encryption_probe_is_honoured(tmp_path):
    assert LocalDriveArchive(mount=tmp_path, encryption_probe=lambda m: True).encrypted() is True


def test_an_unwritable_drive_is_unavailable_even_when_encrypted(tmp_path):
    drive = tmp_path / "drive"
    drive.mkdir()
    drive.chmod(0o500)
    try:
        archive = LocalDriveArchive(mount=drive, encryption_probe=lambda m: True)
        ok, reason = archive.available()
        assert ok is False
        assert "not writable" in reason
    finally:
        drive.chmod(0o700)


# -- the marker means "this subtree", not "this exact entry" --------------


def test_an_archive_file_inside_a_managed_root_is_managed(tmp_path):
    root = ManagedPath(tmp_path / "archives")
    root.claim()
    archive = root.path / "cut-2026-09-29.archive"
    archive.write_bytes(b"payload")

    # A marker cannot exist inside a regular file, so an entry-only test would call this
    # unmanaged -- and the system could not retain the backups it just wrote.
    assert (archive / MANAGED_MARKER).exists() is False
    assert ManagedPath.is_managed(archive) is True


def test_the_managed_root_itself_is_managed(tmp_path):
    root = ManagedPath(tmp_path / "archives")
    root.claim()
    assert ManagedPath.is_managed(root.path) is True


def test_a_nested_archive_inherits_the_marker(tmp_path):
    root = ManagedPath(tmp_path / "archives")
    root.claim()
    nested = root.path / "2026" / "09"
    nested.mkdir(parents=True)
    assert ManagedPath.is_managed(nested / "cut.archive") is True


def test_operator_data_outside_a_managed_root_stays_unmanaged(tmp_path):
    outside = tmp_path / "operator-notes"
    outside.mkdir()
    (outside / "important.txt").write_text("do not delete", encoding="utf-8")

    root = ManagedPath(tmp_path / "archives")
    root.claim()
    (root.path / "cut.archive").write_bytes(b"payload")

    candidates = set(iter_backup_candidates(root.path))
    # Enumeration is scoped to the managed root, so operator data beside it is never a candidate.
    assert (outside / "important.txt") not in candidates
    assert ManagedPath.is_managed(outside / "important.txt") is False
    assert (root.path / "cut.archive") in candidates
    assert ManagedPath.is_managed(root.path / "cut.archive") is True
    assert (outside / "important.txt").read_text() == "do not delete"
