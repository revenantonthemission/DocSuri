"""The backup agent's volume check (U8 plan Step 26; BR6.6, Workflow 19 step 1 and its
error paths).

The check fails closed on the earlier tool's cleanup marker in U8's folder or any folder
above it, on the wrong owner, on a damaged catalogue and on a mismatched volume
identity. With low free space, writing stops and deletion still runs, because deleting
is what frees space. `MacVolume` reads this Mac's answers from `diskutil`, parsed here
from recorded output.
"""

from __future__ import annotations

import plistlib
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest

from docsuri_ops.backup_agent.status import (
    MARKER,
    EvidenceStatus,
    MacVolume,
    StandinVolume,
    check,
    diskutil_info,
)
from tests.u8_service_operations_integration import agent_flows as af


@pytest.fixture
def rig(tmp_path, clock):
    return af.build(tmp_path, clock)


def status_of(rig, **overrides) -> dict:
    options = {"clock": rig.clock, "volume": rig.context.volume,
               "free": rig.context.free, "backup_uid": rig.context.backup_uid, **overrides}
    return check(rig.config, **options)


def test_a_healthy_volume_passes_and_reports_its_identity(rig):
    status = status_of(rig)
    assert status["available"] and status["findings"] == []
    assert (status["volumeIdentity"], status["catalogue"]) == (af.IDENTITY, "intact")


@pytest.mark.parametrize("where", ["u8", "volume", "above"])
def test_the_cleanup_marker_in_u8s_folder_or_any_folder_above_fails_closed(rig, where):
    folder = {"u8": rig.u8, "volume": rig.volume, "above": rig.volume.parent}[where]
    (folder / MARKER).write_text("")
    status = status_of(rig)
    assert not status["available"] and status["sharedCleanupMarker"] is True
    assert "backup-volume-shared-cleanup" in status["findings"]
    assert not status["deletionAllowed"]
    code, result, _ = af.invoke(rig, "backup", {"database": "docsuri_u8",
                                                "recordId": str(uuid4())}, caller=af.SCHEDULER)
    assert (code, result["reason"]) == (1, "volume-check-failed")
    assert rig.tools.calls == []  # nothing written


def test_the_wrong_owner_and_an_unenforced_ownership_fail_closed(rig):
    assert "backup-volume-ownership" in status_of(rig, backup_uid=4242)["findings"]

    class Unenforced(StandinVolume):
        def facts(self, mount):
            facts = super().facts(mount)
            return type(facts)(facts.identity, facts.owner_uid, False, True, True)

    assert "backup-volume-ownership" in status_of(
        rig, volume=Unenforced(af.IDENTITY))["findings"]


def test_a_damaged_catalogue_fails_closed(rig):
    af.backed_up(rig)
    log = rig.u8 / "catalogue.jsonl"
    log.write_bytes(log.read_bytes().replace(b"live-set", b"live-sex", 1))
    status = status_of(rig)
    assert status["catalogue"] == "damaged" and "backup-catalogue-damaged" in status["findings"]
    code, result, _ = af.invoke(rig, "dispose-due", {}, caller=af.SCHEDULER)
    assert (code, result["reason"]) == (1, "volume-check-failed")


def test_a_mismatched_volume_identity_and_an_unencrypted_volume_fail_closed(rig):
    status = status_of(rig, volume=StandinVolume("another-volume"))
    assert status["volumeIdentity"] == "another-volume"
    assert "backup-volume-mismatch" in status["findings"]

    class Plain(StandinVolume):
        def facts(self, mount):
            facts = super().facts(mount)
            return type(facts)(facts.identity, facts.owner_uid, True, False, True)

        def encrypted(self, mount):
            return False

    status = status_of(rig, volume=Plain(af.IDENTITY))
    assert {"backup-volume-unencrypted", "backup-volume-unwritable"} <= set(status["findings"])


def test_low_space_stops_writing_and_deletion_still_runs(tmp_path, clock):
    rig = af.build(tmp_path, clock, free=1 * af.GIB)
    status = status_of(rig)
    assert status["findings"] == ["backup-volume-low"] and status["deletionAllowed"]
    code, result, _ = af.invoke(rig, "backup", {"database": "docsuri_u8",
                                                "recordId": str(uuid4())}, caller=af.SCHEDULER)
    assert (code, result["reason"], result["findings"]) == (
        1, "volume-check-failed", ["backup-volume-low"])
    code, result, _ = af.invoke(rig, "dispose-due", {}, caller=af.SCHEDULER)
    assert code == 0 and result["disposed"] == []


def test_an_absent_volume_is_unavailable(rig, tmp_path):
    from dataclasses import replace

    moved = replace(rig.config, mount=tmp_path / "gone")
    status = check(moved, clock=rig.clock, volume=StandinVolume(af.IDENTITY),
                   free=lambda path: 0, backup_uid=rig.context.backup_uid)
    assert not status["available"] and "backup-volume-unavailable" in status["findings"]
    assert status["catalogue"] == "unavailable"


def test_an_unreadable_volume_fails_closed_with_an_answer(rig):
    """A volume the agent cannot read (its permissions lost, or gone mid-run) answers
    unavailable with its finding; the check never raises (found by the cutover
    journeys)."""
    import os

    os.chmod(rig.volume, 0o000)
    try:
        status = status_of(rig)
    finally:
        os.chmod(rig.volume, 0o700)
    assert not status["available"] and not status["deletionAllowed"]
    assert "backup-volume-unreadable" in status["findings"]
    assert status_of(rig)["available"]


def recorded(payload: dict, returncode: int = 0):
    def run(args, **kwargs):
        assert args[:3] == ["/usr/sbin/diskutil", "info", "-plist"]
        return subprocess.CompletedProcess(args, returncode, plistlib.dumps(payload), b"")

    return run


def test_this_macs_volume_answers_are_parsed_from_diskutil(tmp_path):
    answer = {"VolumeUUID": "6D2A1C7E-0000-4B44-9A6E-0123456789AB",
              "GlobalPermissionsEnabled": True, "FileVault": True}
    volume = MacVolume(info=lambda mount: diskutil_info(mount, run=recorded(answer)),
                       encrypted=lambda mount: True)
    facts = volume.facts(tmp_path)
    assert facts.identity == answer["VolumeUUID"] and facts.ownership_enforced
    assert facts.encrypted and not facts.standin
    assert diskutil_info(tmp_path, run=recorded({}, returncode=1)) == {}

    def broken(args, **kwargs):
        return subprocess.CompletedProcess(args, 0, b"not a plist", b"")

    assert diskutil_info(tmp_path, run=broken) == {}

    def missing(args, **kwargs):
        raise FileNotFoundError(args[0])

    assert diskutil_info(Path("/nowhere"), run=missing) == {}
    assert MacVolume(info=lambda mount: {}, encrypted=lambda mount: False).facts(
        tmp_path / "absent").owner_uid is None


def test_the_service_account_reads_the_status_only_through_platform_evidence():
    recorded_status = {"available": True, "volumeIdentity": af.IDENTITY, "freeBytes": 1}
    reader = EvidenceStatus(lambda target: {"observations": recorded_status}
                            if target == "backup-volume" else None)
    assert reader() == recorded_status
    with pytest.raises(LookupError):
        EvidenceStatus(lambda target: None)()
    with pytest.raises(LookupError):
        EvidenceStatus(lambda target: {"observations": {"other": 1}})()
