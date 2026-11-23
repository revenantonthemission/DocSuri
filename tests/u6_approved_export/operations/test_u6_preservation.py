"""The destructive archive (D14; cicd-pipeline §4.4) against a controlled context.

Every helper the runner hands in is either the runner's own filesystem helper or a
recorded stand-in for Docker, the port, open files and the database stop, so the key
unlink, its refusals and the first-key staging pair are exercised on real files without
touching any environment folder. The database reads run against the realm: the archive's
identity and client checks read the realm's own identity row and client backends through
an administrative `connect_raw` session with tuple rows, as the runner's `connect_admin`
returns them (L3-3).
"""

import dataclasses
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

import pytest
from psycopg.rows import tuple_row

from backend import local_profile
from backend.modules.export.token_keyring import (
    KEY_FILE,
    LOCK_FILE,
    MARKER_FILE,
    STAGING_PREFIX,
)
from scripts import u6_preservation as preservation
from scripts import verify_docsuri_u6 as runner

KEY_BYTES = b'{"synthetic": "key record"}'
FOREIGN_RUN_ID = "docsuri-u6-fedcba9876543210"
OTHER_CLIENTS = (
    "SELECT count(*) FROM pg_stat_activity WHERE pid<>pg_backend_pid() "
    "AND backend_type='client backend'"
)
CLIENT_WAIT_SECONDS = 5


def private(path: Path, data: bytes) -> None:
    path.write_bytes(data)
    path.chmod(0o600)


@pytest.fixture
def owned(tmp_path, monkeypatch, realm, connect_raw):
    """An owned U6 folder with a key file, its marker and lock, and a context over it."""
    monkeypatch.setattr(local_profile, "RUN_PARENT", tmp_path)
    run = tmp_path / "docsuri-u6-run"
    run.mkdir(mode=0o700)
    monkeypatch.setattr(runner, "RUN", run)
    keys = run / runner.KEY_FOLDER
    keys.mkdir(mode=0o700)
    private(keys / KEY_FILE, KEY_BYTES)
    private(keys / MARKER_FILE, b"")
    private(keys / LOCK_FILE, b"")
    state = {"stopped": False, "resources": 0, "extra_client": False, "admin_reads": 0}

    def connect_admin(value):
        """The realm's administrative login with tuple rows, once no other client remains."""
        conn = connect_raw()
        conn.row_factory = tuple_row
        deadline = time.monotonic() + CLIENT_WAIT_SECONDS
        while True:
            others = conn.execute(OTHER_CLIENTS).fetchone()[0]
            conn.rollback()  # PostgreSQL keeps one activity snapshot per transaction
            if others == 0:
                break
            if time.monotonic() >= deadline:
                pytest.fail("another database client stayed connected to the realm")
            time.sleep(0.1)
        if state["extra_client"]:
            connect_raw()
        state["admin_reads"] += 1
        return conn

    def write_manifest(*, expired: bool, run_id: str = realm.run_id):
        created = time.time() - (90000 if expired else 60)
        value = {
            "unit": runner.UNIT,
            "profile": "synthetic-local",
            "repository": str(runner.ROOT),
            "runId": run_id,
            "container": run_id,
            "volume": run_id + "-pgdata",
            "databaseImage": runner.IMAGE,
            "database": runner.DATABASE,
            "realm": runner.REALM,
            "databasePort": runner.DATABASE_PORT,
            "applicationPort": runner.APPLICATION_PORT,
            "createdAt": created,
            "expiresAt": created + 86400,
            "policy": runner.POLICY,
        }
        raw = json.dumps(value).encode()
        private(run / "environment.json", raw)
        private(
            run / "ownership.json",
            json.dumps(
                {"runId": run_id, "manifestSha256": hashlib.sha256(raw).hexdigest()}
            ).encode(),
        )
        return value

    def resources(value):
        state["resources"] += 1

    def stop_database(value):
        state["stopped"] = True

    context = preservation.ArchiveContext(
        run=run,
        key_folder=keys,
        database=runner.DATABASE,
        refused=runner.Refused,
        identity=runner.archive_identity,
        resources=resources,
        idle_port=lambda: None,
        open_files=lambda root: subprocess.CompletedProcess(["lsof"], 1, ""),
        inventory=runner.inventory_entries,
        connect_admin=connect_admin,
        stop_database=stop_database,
        sync=runner.fsync_directory,
    )
    write_manifest(expired=False)
    return {
        "run": run,
        "keys": keys,
        "state": state,
        "context": context,
        "write": write_manifest,
        "run_id": realm.run_id,
    }


def archive(owned) -> dict:
    return preservation.archive(owned["run"] / "environment.json", owned["context"])


def assert_intact(owned) -> None:
    keys = owned["keys"]
    assert owned["run"].is_dir()
    assert (keys / KEY_FILE).read_bytes() == KEY_BYTES
    assert (keys / MARKER_FILE).exists() and (keys / LOCK_FILE).exists()


def test_a_completed_archive_leaves_no_key_file(owned):
    result = archive(owned)
    destination = Path(result["path"])
    assert result["keyDeleted"] is True and result["keyFileFound"] is True
    assert result["keyFolderRemoved"] is True and result["containerStopped"] is True
    run_id = owned["run_id"]
    assert result["runId"] == run_id and result["volumePreserved"] == run_id + "-pgdata"
    assert destination.name.startswith(f"docsuri-u6-preserved-{run_id}-")
    assert not owned["run"].exists() and destination.is_dir()
    assert not (destination / runner.KEY_FOLDER).exists()
    assert not list(destination.rglob(KEY_FILE))
    assert (destination / "environment.json").is_file()
    assert owned["state"]["stopped"] is True and owned["state"]["resources"] == 2
    assert owned["state"]["admin_reads"] == 1


def fail(*_args):
    raise runner.Refused("controlled refusal")


@pytest.mark.parametrize(
    "check",
    [
        "identity",
        "resources",
        "port",
        "open-files",
        "file-mode",
        "folder-mode",
        "extra-link",
        "foreign-staging-link",
        "two-staging-links",
        "database-identity",
        "active-client",
        "destination",
        "stop",
    ],
)
def test_a_refusal_at_any_check_leaves_the_key_folder_intact(owned, monkeypatch, check):
    context, keys, run, state = owned["context"], owned["keys"], owned["run"], owned["state"]
    staging = keys / (STAGING_PREFIX + "a" * 32)
    match = None
    if check == "identity":
        (run / "environment.json").write_bytes(b"{}")
    elif check == "resources":
        context = dataclasses.replace(context, resources=fail)
    elif check == "port":
        context = dataclasses.replace(context, idle_port=fail)
    elif check == "open-files":
        context = dataclasses.replace(
            context, open_files=lambda root: subprocess.CompletedProcess(["lsof"], 0, "python")
        )
    elif check == "file-mode":
        (keys / MARKER_FILE).chmod(0o644)
    elif check == "folder-mode":
        keys.chmod(0o750)
    elif check == "extra-link":
        os.link(run / "ownership.json", run / "ownership-copy.json")
    elif check == "foreign-staging-link":
        os.link(keys / MARKER_FILE, staging)
    elif check == "two-staging-links":
        os.link(keys / KEY_FILE, staging)
        os.link(keys / KEY_FILE, keys / (STAGING_PREFIX + "b" * 32))
    elif check == "database-identity":
        assert FOREIGN_RUN_ID != owned["run_id"]
        owned["write"](expired=False, run_id=FOREIGN_RUN_ID)
        match = "preservation database identity differs"
    elif check == "active-client":
        state["extra_client"] = True
        match = "other database clients prevent safe preservation"
    elif check == "destination":
        monkeypatch.setattr(preservation.secrets, "token_hex", lambda size: "deadbeef")
        run.with_name(f"docsuri-u6-preserved-{owned['run_id']}-deadbeef").mkdir()
    else:
        context = dataclasses.replace(context, stop_database=fail)
    with pytest.raises((runner.Refused, ValueError), match=match):
        preservation.archive(run / "environment.json", context)
    if check == "folder-mode":
        keys.chmod(0o700)
    if check == "file-mode":
        (keys / MARKER_FILE).chmod(0o600)
    assert_intact(owned)
    assert state["stopped"] is False


@pytest.mark.parametrize("expired", [False, True], ids=["live", "expired"])
def test_a_key_still_linked_by_its_first_key_staging_name_is_archived(owned, expired):
    if expired:
        owned["write"](expired=True)
    staging = owned["keys"] / (STAGING_PREFIX + "c" * 32)
    os.link(owned["keys"] / KEY_FILE, staging)
    assert (owned["keys"] / KEY_FILE).stat().st_nlink == 2
    result = archive(owned)
    destination = Path(result["path"])
    assert result["keyDeleted"] is True and result["keyFileFound"] is True
    assert not list(destination.rglob(KEY_FILE))
    assert not list(destination.rglob(STAGING_PREFIX + "*"))
    assert (result["expiresAt"] < time.time()) is expired


def test_an_unremovable_staging_file_refuses_before_the_key_unlink(owned, monkeypatch):
    staging = owned["keys"] / (STAGING_PREFIX + "d" * 32)
    os.link(owned["keys"] / KEY_FILE, staging)
    removed = []

    def remove(path):
        if path.name.startswith(STAGING_PREFIX):
            raise PermissionError("controlled")
        removed.append(path.name)
        os.unlink(path)

    monkeypatch.setattr(preservation, "remove", remove)
    with pytest.raises(runner.Refused, match="key is untouched"):
        archive(owned)
    assert removed == []
    assert staging.exists()
    assert_intact(owned)
    assert owned["state"]["stopped"] is True


def test_a_failed_key_unlink_refuses_with_the_key_in_place(owned, monkeypatch):
    def remove(path):
        if path.name == KEY_FILE:
            raise PermissionError("controlled")
        os.unlink(path)

    monkeypatch.setattr(preservation, "remove", remove)
    with pytest.raises(runner.Refused, match="untouched"):
        archive(owned)
    assert_intact(owned)


def test_the_rest_of_the_key_folder_may_stay_once_the_key_is_gone(owned, monkeypatch):
    def remove(path):
        if path.name == MARKER_FILE:
            raise PermissionError("controlled")
        os.unlink(path)

    monkeypatch.setattr(preservation, "remove", remove)
    result = archive(owned)
    destination = Path(result["path"])
    assert result["keyDeleted"] is True and result["keyFolderRemoved"] is False
    assert not (destination / runner.KEY_FOLDER / KEY_FILE).exists()
    assert (destination / runner.KEY_FOLDER / MARKER_FILE).exists()


def test_a_failed_rename_refuses_with_the_environment_stopped_without_its_key(
    owned, monkeypatch
):
    def rename(source, target):
        raise PermissionError("controlled")

    monkeypatch.setattr(preservation.os, "rename", rename)
    with pytest.raises(runner.Refused, match="without its key"):
        archive(owned)
    assert owned["run"].is_dir()
    assert not (owned["keys"] / KEY_FILE).exists()
    assert owned["state"]["stopped"] is True


def test_an_environment_that_never_held_a_key_is_archived(owned):
    (owned["keys"] / KEY_FILE).unlink()
    result = archive(owned)
    assert result["keyDeleted"] is True and result["keyFileFound"] is False


def test_an_environment_without_a_key_folder_is_archived(owned):
    for entry in owned["keys"].iterdir():
        entry.unlink()
    owned["keys"].rmdir()
    result = archive(owned)
    assert result["keyFileFound"] is False and result["keyFolderRemoved"] is True


def test_the_runner_builds_the_context_from_its_own_helpers(owned):
    context = runner.preservation_context()
    assert context.run == owned["run"]
    assert context.key_folder == owned["run"] / runner.KEY_FOLDER
    assert context.refused is runner.Refused and context.database == runner.DATABASE
    assert context.identity is runner.archive_identity
    assert context.inventory is runner.inventory_entries
