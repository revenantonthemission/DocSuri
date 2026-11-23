"""The production profile's loader and the operations policy (U8 plan Step 10; A9, BR6.1).

The loader runs against a profile root built in a private temporary folder, never the
real `/Library/DocSuri/profile`; the service account's identity is the test's own user
identifier, passed in as the loader's `service_uid` (an allowed double).
"""

from __future__ import annotations

import dataclasses
import json
import math
import os
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest

from backend import local_profile, u8_policy
from backend.local_profile import (
    KEY_FOLDERS,
    PORTS,
    PUBLIC_ORIGINS,
    LocalProfile,
    key_folder,
    public_origin,
    verifier_key_path,
)
from backend.u8_policy import (
    DAY,
    GIB,
    HOUR,
    MIB,
    MINUTE,
    PRODUCTION_OPERATIONS,
    SYNTHETIC_OPERATIONS,
    require_policy,
)
from backend.u8_profile import ProductionProfile, ProfileRefused, listen_port, public_authority

REHEARSAL = "docsuri_v2_rehearsal_" + "a1" * 6


def manifest(**changes) -> dict:
    value = {
        "profile": "production",
        "runId": "docsuri-v2-" + "0" * 16,
        "mode": "rehearsal",
        "admission": "maintainer-only",
        "database": REHEARSAL,
        "rehearsalDatabase": REHEARSAL,
        "databasePort": 15432,
        "publicOrigin": "https://docsuri.rvnnt.dev",
        "listenPort": 18200,
        "maintenancePort": 18201,
        "backupVolume": {"mountPoint": "/Volumes/DocSuri_Backup", "identity": str(uuid4())},
        "maintainerAccount": str(uuid4()),
        "accounts": {
            "service": "_docsuri_v2", "scheduler": "_docsuri_v2_sched",
            "backup": "_docsuri_r1t_backup", "database": "_docsuri_v2_db",
            "models": "_docsuri_models", "tunnel": "_docsuri_tunnel",
        },
        "keyFolders": list(KEY_FOLDERS),
        "createdAt": 1_792_000_000,
    }
    value.update(changes)
    return value


def write_private(path: Path, payload: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload)


def build_root(parent: Path, value: dict | None = None) -> Path:
    root = parent / "profile"
    root.mkdir(mode=0o700)
    os.chmod(root, 0o700)
    for name in (*KEY_FOLDERS, "ledger"):
        (root / name).mkdir(mode=0o700)
        os.chmod(root / name, 0o700)
    write_private(root / "environment.json", json.dumps(value or manifest()).encode())
    return root


@pytest.fixture
def root(tmp_path) -> Path:
    assert not str(tmp_path.resolve()).startswith(("/tmp/", "/private/tmp/")), (
        "these tests need a temporary folder outside /tmp (set TMPDIR)"
    )
    return build_root(tmp_path)


def refusal(root: Path, *, uid: int | None = None) -> str:
    with pytest.raises(ProfileRefused) as raised:
        ProductionProfile.load(root / "environment.json", service_uid=uid or os.getuid())
    return raised.value.check


def test_the_loader_accepts_a_private_durable_root(root):
    profile = ProductionProfile.load(root / "environment.json", service_uid=os.getuid())
    assert profile.is_production and profile.realm == "production"
    assert profile.database_name == REHEARSAL and profile.rehearsal_database == REHEARSAL
    assert profile.origin == "https://docsuri.rvnnt.dev"
    assert public_authority(profile) == "docsuri.rvnnt.dev"
    assert (listen_port(profile), profile.maintenance_port, profile.database_port) == (
        18200, 18201, 15432,
    )
    # No expiry: the owner transactions' retention check never ends it.
    assert profile.expires_at == math.inf
    assert key_folder(profile, "export-keys") == root / "export-keys"
    assert verifier_key_path(profile) == root / "verifier-key" / "account-verifier.key"
    assert dict(profile.accounts)["service"] == "_docsuri_v2"


def test_the_loader_refuses_a_root_under_tmp():
    parent = Path(tempfile.mkdtemp(prefix="docsuri-u8-profile-test-", dir="/tmp"))
    try:
        assert refusal(build_root(parent)) == "root-under-tmp"
    finally:
        shutil.rmtree(parent)


def test_the_loader_refuses_a_root_that_is_a_link(root, tmp_path):
    link = tmp_path / "linked"
    link.mkdir(mode=0o700)
    (link / "profile").symlink_to(root)
    assert refusal(link / "profile") == "root-link"


def test_the_loader_refuses_the_wrong_owner(root):
    assert refusal(root, uid=os.getuid() + 1) == "root-owner"


def test_the_loader_refuses_a_0755_root(root):
    os.chmod(root, 0o755)
    assert refusal(root) == "root-mode"


def test_the_loader_refuses_a_0644_file(root):
    os.chmod(root / "environment.json", 0o644)
    assert refusal(root) == "file-mode"
    os.chmod(root / "environment.json", 0o600)
    write_private(root / "ledger" / "ledger.jsonl", b"")
    os.chmod(root / "ledger" / "ledger.jsonl", 0o644)
    assert refusal(root) == "file-mode"


def test_the_loader_refuses_a_link_inside_the_root(root):
    (root / "ledger" / "elsewhere").symlink_to("/etc/hosts")
    assert refusal(root) == "file-link"


@pytest.mark.parametrize(
    "changes",
    [
        {"admission": "open"},
        {"mode": "live"},
        {"database": "docsuri_v2", "mode": "rehearsal"},
        {"publicOrigin": "https://127.0.0.1:18110"},
        {"listenPort": 18109},
        {"keyFolders": ["export-keys"]},
        {"rehearsalDatabase": "docsuri_v2_scratch_" + "b2" * 6},
        {"unexpected": True},
    ],
)
def test_the_loader_refuses_a_manifest_outside_the_profile(tmp_path, changes):
    assert refusal(build_root(tmp_path, manifest(**changes))) == "manifest"


def test_live_mode_runs_on_the_production_database(tmp_path):
    root = build_root(
        tmp_path, manifest(mode="live", admission="open", database="docsuri_v2")
    )
    profile = ProductionProfile.load(root / "environment.json", service_uid=os.getuid())
    assert (profile.mode, profile.admission, profile.database_name) == (
        "live", "open", "docsuri_v2",
    )


def test_the_synthetic_loader_is_unchanged(realm):
    again = LocalProfile.load(Path(os.environ["DOCSURI_U8_ENVIRONMENT_FILE"]))
    assert again == realm and type(again) is LocalProfile and not again.is_production
    assert realm.origin == "https://127.0.0.1:18110" and listen_port(realm) == 18109
    # The production loader and the listener are U8's; U2's profile no longer holds them.
    for name in ("ProductionProfile", "ProfileRefused", "custody_failure"):
        assert not hasattr(local_profile, name)
    assert not hasattr(LocalProfile, "listen_port")
    assert not hasattr(LocalProfile, "public_authority")
    assert math.isfinite(realm.expires_at)
    # The composed realm keeps its keys in the key folders; an earlier realm at its root.
    assert key_folder(realm, "control-keys") == realm.root / "control-keys"
    earlier = dataclasses.replace(realm, realm="account-controls")
    assert key_folder(earlier, "control-keys") == realm.root
    assert verifier_key_path(earlier) == realm.root / "account-verifier.key"
    with pytest.raises(ValueError):
        key_folder(realm, "elsewhere")


def test_every_earlier_unit_keeps_its_own_origin():
    """Only the composed realm's origin is its public stand-in (decision "Allowlist
    sites", row 1); U2 to U6 resolve to their own application port."""
    assert PUBLIC_ORIGINS == {"u8": "https://127.0.0.1:18110"}
    for unit in ("u2", "u3", "u4", "u5", "u6"):
        assert public_origin(unit) == f"https://127.0.0.1:{PORTS[unit][0]}"
    assert public_origin("u8") == "https://127.0.0.1:18110"


@pytest.mark.parametrize("unit", ["u2", "u3", "u4", "u5", "u6"])
def test_each_earlier_synthetic_profile_listens_on_its_application_port(unit, tmp_path):
    """U6's re-check: for the synthetic profiles u2 to u6 the host's listen port is the
    unit's application port, as each earlier assembly binds it."""
    application, database = PORTS[unit]
    profile = LocalProfile(tmp_path, f"docsuri-{unit}-0123456789abcdef", public_origin(unit),
                           database, 0.0)
    assert listen_port(profile) == application


def synthetic_run(parent: Path) -> Path:
    """An owned synthetic U8 run root under `parent`, as the realm tool writes one: its
    manifest and its ownership marker, both 0600 in a 0700 folder."""
    import hashlib

    run = parent / "docsuri-u8-run"
    run.mkdir(mode=0o700)
    raw = json.dumps({"runId": "docsuri-u8-" + "0" * 16, "profile": "synthetic-local"}).encode()
    write_private(run / "environment.json", raw)
    write_private(run / "ownership.json", json.dumps({
        "runId": "docsuri-u8-" + "0" * 16,
        "manifestSha256": hashlib.sha256(raw).hexdigest()}).encode())
    return run


@pytest.mark.parametrize("change", ["link", "owner", "mode"])
def test_both_loaders_refuse_a_linked_foreign_or_group_readable_manifest(
        root, tmp_path, monkeypatch, change):
    """Step 44's gap: the synthetic loader keeps U2's built custody check and the
    production loader its named one; each refuses the three custody failures."""
    parent = tmp_path / "synthetic"
    parent.mkdir(mode=0o700)
    run = synthetic_run(parent)
    monkeypatch.setattr(local_profile, "RUN_PARENT", parent)
    production = root / "environment.json"
    if change == "link":
        for manifest_path in (run / "environment.json", production):
            target = manifest_path.with_name("moved.json")
            manifest_path.rename(target)
            manifest_path.symlink_to(target)
        expected = "file-link"
    elif change == "mode":
        os.chmod(run / "environment.json", 0o640)
        os.chmod(production, 0o640)
        expected = "file-mode"
    else:
        expected = "root-owner"
    uid = os.getuid() + 1 if change == "owner" else os.getuid()
    if change == "owner":
        monkeypatch.setattr(local_profile.os, "getuid", lambda: uid)
    with pytest.raises(ValueError):
        LocalProfile.load(run / "environment.json")
    monkeypatch.undo()
    assert refusal(root, uid=uid) == expected


# --- The operations policy (Step 1's rows) ---------------------------------------------

PRODUCTION_ROWS = {
    # observability-design § 3.2
    "required_renewal_seconds": 60, "required_stale_seconds": 180,
    "required_incident_seconds": 10 * MINUTE,
    "provider_renewal_seconds": 5 * MINUTE, "provider_stale_seconds": 15 * MINUTE,
    "cutover_renewal_seconds": 5 * MINUTE, "cutover_stale_seconds": 15 * MINUTE,
    "cutover_incident_seconds": 15 * MINUTE,
    "isolation_renewal_seconds": 5 * MINUTE, "isolation_stale_seconds": 15 * MINUTE,
    "isolation_incident_seconds": 15 * MINUTE,
    # observability-design § 3.1 and § 4
    "observation_buffer": 60, "observation_retention_seconds": 14 * DAY,
    "dashboard_refresh_seconds": 30, "job_list_refresh_seconds": 5,
    "export_degraded_after_seconds": 24 * HOUR, "digest_late_seconds": 2 * HOUR,
    "error_rate_window_seconds": 24 * HOUR,
    # reliability-design § 6-8
    "backup_hour_seoul": 4, "verification_hour_seoul": 5, "verification_weekday": 6,
    "backup_catch_up_seconds": 24 * HOUR,
    "daily_set_retention_seconds": 14 * DAY, "sunday_set_retention_seconds": 56 * DAY,
    "erasure_verification_start_seconds": 24 * HOUR,
    "verification_completion_seconds": 60 * MINUTE,
    "restore_route_and_stop_seconds": 5 * MINUTE, "restore_pre_backup_seconds": 25 * MINUTE,
    "restore_recreate_and_restore_seconds": 45 * MINUTE,
    "restore_replay_and_integrity_seconds": 10 * MINUTE,
    "restore_post_backup_seconds": 25 * MINUTE, "restore_start_and_route_seconds": 10 * MINUTE,
    "restore_total_seconds": 2 * HOUR, "recovery_start_seconds": 24 * HOUR,
    # scalability-design § 3.2-3.4 and § 4
    "footprint_budget_bytes": 8 * GIB, "footprint_warning_ratio": 0.8,
    "footprint_headroom_bytes": 256 * MIB,
    "internal_disk_threshold_bytes": 20 * GIB, "internal_disk_critical_bytes": 10 * GIB,
    "first_rehearsal_estimate_bytes": 4 * GIB,
    "production_databases": 1, "rehearsal_databases": 2, "import_databases": 1,
    "scratch_databases": 1, "backup_volume_floor_bytes": 64 * GIB,
    # NFR3.12, NFR3.13, security-design § 6.7
    "dry_run_copy_backstop_seconds": 14 * DAY, "import_database_backstop_seconds": 14 * DAY,
    "rehearsal_database_backstop_seconds": 60 * DAY,
    "scratch_restore_backstop_seconds": DAY,
    "final_snapshot_disposal_seconds": 30 * DAY, "final_snapshot_backstop_seconds": 120 * DAY,
    "v1_stores_disposal_seconds": 90 * DAY, "v1_stores_backstop_seconds": 180 * DAY,
    "rolled_back_disposal_seconds": 30 * DAY, "rolled_back_backstop_seconds": 90 * DAY,
    "staging_file_backstop_seconds": DAY, "decided_date_minimum_seconds": 14 * DAY,
    "internal_disk_tail_seconds": 24 * HOUR,
    # security-design § 13
    "digest_daily_limit": 60, "account_mail_daily_limit": 90, "mail_monthly_limit": 2700,
    # reliability-design § 12
    "soak_clean_seconds": 7 * DAY, "restart_rehearsal_seconds": 7 * DAY,
    "consumer_window_seconds": 14 * DAY, "isolation_freshness_seconds": 15 * MINUTE,
    "switch_bound_seconds": 4 * HOUR, "rollback_window_seconds": 14 * DAY,
    # your decision of 2026-11-01 (L1-21, "Within 24 h of the switch")
    "inventory_recency_seconds": 24 * HOUR,
    # the arrangement row
    "stop_record_bound_seconds": 14 * DAY, "availability_slot_seconds": 5 * MINUTE,
    "probe_limit_seconds": 10, "availability_retention_months": 13,
    "latency_window_seconds": 5 * MINUTE, "latency_retention_seconds": 14 * DAY,
    "route_classes": (
        "health", "navigation", "read", "search", "accept", "stream", "asset", "static",
        "administration",
    ),
    # performance-design § 3.3
    "search_model_keep_alive": -1, "search_model_repin_seconds": 60,
    "embedding_bound_seconds": 2.0, "embedding_batch_chunks": 16, "model_job_lane": 1,
    # performance-design § 3.3, the research model (your decision of 2026-10-24)
    "research_model_keep_alive_seconds": 300,
    # performance-design § 3.1
    "host_connections": 12, "worker_connections": 8, "observation_connections": 2,
    "maintenance_connections": 2, "scheduler_connections": 3, "backup_agent_connections": 3,
    "operator_tool_connections": 2, "migration_tool_connections": 4,
}


def test_production_operations_equals_its_source_rows_field_by_field():
    fields = {field.name for field in dataclasses.fields(PRODUCTION_OPERATIONS)} - {"name"}
    assert fields == set(PRODUCTION_ROWS)
    for name, expected in PRODUCTION_ROWS.items():
        assert getattr(PRODUCTION_OPERATIONS, name) == expected, name
    assert PRODUCTION_OPERATIONS.name == "production"


def test_each_profile_accepts_only_its_own_operations_policy():
    assert require_policy(PRODUCTION_OPERATIONS, production=True) is PRODUCTION_OPERATIONS
    assert require_policy(SYNTHETIC_OPERATIONS, production=False) is SYNTHETIC_OPERATIONS
    with pytest.raises(ValueError, match="synthetic profile refuses"):
        require_policy(PRODUCTION_OPERATIONS, production=False)
    with pytest.raises(ValueError, match="production profile accepts only"):
        require_policy(SYNTHETIC_OPERATIONS, production=True)


def test_the_policy_refuses_a_value_that_is_not_finite_and_positive():
    with pytest.raises(ValueError):
        dataclasses.replace(PRODUCTION_OPERATIONS, host_connections=0)
    with pytest.raises(ValueError):
        dataclasses.replace(PRODUCTION_OPERATIONS, embedding_bound_seconds=math.inf)
    assert u8_policy.SYNTHETIC_OPERATIONS.host_connections == 12
