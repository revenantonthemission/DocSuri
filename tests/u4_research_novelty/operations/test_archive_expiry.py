"""U4's expired realm may be preserved by archive-owned, but never reopened for execution."""

import hashlib
import json
import subprocess
import time
from pathlib import Path

import pytest

from backend import local_profile
from scripts import verify_docsuri_u4 as runner

RUN_ID = "docsuri-u4-0123456789abcdef"


@pytest.fixture
def expired_realm(tmp_path, monkeypatch):
    """A custody-correct U4 manifest whose original 24-hour retention has passed."""
    monkeypatch.setattr(local_profile, "RUN_PARENT", tmp_path)
    root = tmp_path / "docsuri-u4-run"
    root.mkdir(mode=0o700)
    monkeypatch.setattr(runner, "RUN", root)
    created = time.time() - 90000
    value = {
        "runId": RUN_ID,
        "profile": "synthetic-local",
        "repository": str(runner.ROOT),
        "unit": runner.UNIT,
        "realm": runner.REALM,
        "database": runner.DATABASE,
        "applicationPort": runner.APPLICATION_PORT,
        "databasePort": runner.DATABASE_PORT,
        "createdAt": created,
        "expiresAt": created + 86400,
        "databaseImage": runner.IMAGE,
        "policy": runner.POLICY,
        "container": RUN_ID,
        "volume": RUN_ID + "-pgdata",
    }
    path = root / "environment.json"

    def save():
        raw = json.dumps(value).encode()
        path.write_bytes(raw)
        path.chmod(0o600)
        marker = root / "ownership.json"
        marker.write_text(
            json.dumps({"runId": RUN_ID, "manifestSha256": hashlib.sha256(raw).hexdigest()})
        )
        marker.chmod(0o600)

    save()
    evidence = root / "coverage-evidence.json"
    evidence.write_text('{"failed": true}')
    evidence.chmod(0o600)
    return path, value, save


@pytest.fixture
def archival_boundary(expired_realm, monkeypatch):
    """Docker, lsof and the database replaced by a recorder that only answers."""
    path, value, save = expired_realm
    boundary = {
        "running": True,
        "stopped": False,
        "clients": 0,
        "databaseRunId": value["runId"],
        "containerLabel": value["runId"],
        "volumeLabel": value["runId"],
        "calls": [],
    }

    def require(args, **kwargs):
        boundary["calls"].append(args)
        if args[:3] == ["docker", "container", "inspect"]:
            assert args[3] == value["container"]
            record = {
                "Config": {
                    "Image": runner.IMAGE,
                    "Labels": {runner.LABEL: boundary["containerLabel"]},
                },
                "HostConfig": {
                    "Memory": runner.DB_MEMORY,
                    "MemorySwap": runner.DB_MEMORY,
                    "NanoCpus": 1_000_000_000,
                    "PidsLimit": 64,
                    "ReadonlyRootfs": True,
                    "PortBindings": {
                        "5432/tcp": [
                            {"HostIp": "127.0.0.1", "HostPort": str(runner.DATABASE_PORT)}
                        ]
                    },
                },
                "State": {"Running": boundary["running"] and not boundary["stopped"]},
                "Mounts": [
                    {
                        "Type": "volume",
                        "Name": value["volume"],
                        "Destination": "/var/lib/postgresql/data",
                    }
                ],
            }
            return subprocess.CompletedProcess(args, 0, json.dumps([record]))
        if args[:3] == ["docker", "volume", "inspect"]:
            assert args[3] == value["volume"]
            return subprocess.CompletedProcess(
                args, 0, json.dumps([{"Labels": {runner.LABEL: boundary["volumeLabel"]}}])
            )
        assert args == ["docker", "stop", "--time", "10", value["container"]]
        boundary["stopped"] = True
        return subprocess.CompletedProcess(args, 0, value["container"])

    def command(args, **kwargs):
        assert args == ["lsof", "+D", str(path.parent)]
        return subprocess.CompletedProcess(args, 1, "")

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, sql):
            if "docsuri_local_identity" in sql:
                self.result = (boundary["databaseRunId"], runner.DATABASE)
            else:
                assert "pg_stat_activity" in sql and "pid<>pg_backend_pid()" in sql
                self.result = (boundary["clients"],)
            return self

        def fetchone(self):
            return self.result

    monkeypatch.setattr(runner, "require", require)
    monkeypatch.setattr(runner, "command", command)
    monkeypatch.setattr(runner, "connect_admin", lambda metadata: Connection())
    monkeypatch.setattr(runner, "require_stopped", lambda: None)
    return path, value, save, boundary


def test_expired_realm_is_refused_for_execution_but_identified_for_preservation(
    expired_realm,
):
    path, value, _ = expired_realm
    with pytest.raises(ValueError, match="retention expired"):
        runner.manifest(path)
    assert runner.preservation_manifest(path) == value


def test_expired_owned_idle_realm_is_preserved_without_renewal(archival_boundary):
    path, value, _, boundary = archival_boundary
    before = {item.name: item.read_bytes() for item in path.parent.iterdir()}
    result = runner.archive_owned(path)
    preserved = Path(result["path"])
    assert boundary["stopped"] is True
    assert not path.parent.exists()
    assert preserved.parent == path.parent.parent
    assert preserved.name.startswith(f"docsuri-u4-preserved-{RUN_ID}-")
    assert {item.name: item.read_bytes() for item in preserved.iterdir()} == before
    assert result["expiresAt"] == value["expiresAt"] < time.time()
    assert result["volumePreserved"] == value["volume"]
    assert result["containerStopped"] is True
    assert all("rm" not in call and "prune" not in call for call in boundary["calls"])
    assert ["docker", "stop", "--time", "10", value["container"]] in boundary["calls"]


@pytest.mark.parametrize(
    "defect",
    [
        "hash",
        "custody",
        "symlink",
        "unit",
        "realm",
        "database",
        "port",
        "image",
        "policy",
        "container-name",
        "volume-name",
        "container-label",
        "volume-label",
        "already-stopped",
        "database-identity",
        "active-client",
        "unbounded-retention",
    ],
)
def test_foreign_tampered_or_busy_expired_realms_never_stop_or_move(
    archival_boundary, defect
):
    path, value, save, boundary = archival_boundary
    if defect == "hash":
        path.write_text(path.read_text() + " ")
    elif defect == "custody":
        path.chmod(0o644)
    elif defect == "symlink":
        target = path.with_name("saved.json")
        path.rename(target)
        path.symlink_to(target)
    elif defect in {
        "unit", "realm", "database", "port", "image", "policy", "container-name", "volume-name"
    }:
        field = {
            "unit": "unit",
            "realm": "realm",
            "database": "database",
            "port": "databasePort",
            "image": "databaseImage",
            "policy": "policy",
            "container-name": "container",
            "volume-name": "volume",
        }[defect]
        value[field] = "foreign"
        save()
    elif defect == "container-label":
        boundary["containerLabel"] = "foreign"
    elif defect == "volume-label":
        boundary["volumeLabel"] = "foreign"
    elif defect == "already-stopped":
        boundary["running"] = False
    elif defect == "database-identity":
        boundary["databaseRunId"] = "foreign"
    elif defect == "active-client":
        boundary["clients"] = 1
    else:
        value["expiresAt"] = value["createdAt"] + 90000
        save()
    before = {item.name: item.read_bytes() for item in path.parent.iterdir()}
    with pytest.raises((ValueError, runner.Refused)):
        runner.archive_owned(path)
    assert not boundary["stopped"]
    assert path.parent.is_dir()
    assert {item.name: item.read_bytes() for item in path.parent.iterdir()} == before


def test_another_units_valid_expired_manifest_is_never_preserved_by_u4(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(local_profile, "RUN_PARENT", tmp_path)
    monkeypatch.setattr(runner, "RUN", tmp_path / "docsuri-u4-run")
    root = tmp_path / "docsuri-u5-run"
    root.mkdir(mode=0o700)
    run_id = "docsuri-u5-0123456789abcdef"
    created = time.time() - 90000
    raw = json.dumps(
        {
            "runId": run_id,
            "profile": "synthetic-local",
            "repository": str(runner.ROOT),
            "unit": "u5-topics-digests",
            "realm": "topics-digests",
            "database": "docsuri_u5",
            "applicationPort": 18089,
            "databasePort": 15489,
            "createdAt": created,
            "expiresAt": created + 86400,
            "databaseImage": runner.IMAGE,
            "policy": runner.POLICY,
            "container": run_id,
            "volume": run_id + "-pgdata",
        }
    ).encode()
    path = root / "environment.json"
    path.write_bytes(raw)
    path.chmod(0o600)
    marker = root / "ownership.json"
    marker.write_text(
        json.dumps({"runId": run_id, "manifestSha256": hashlib.sha256(raw).hexdigest()})
    )
    marker.chmod(0o600)
    assert local_profile.LocalProfile.preservation_identity(path)["runId"] == run_id
    with pytest.raises(runner.Refused, match="its own explicit realm"):
        runner.preservation_manifest(path)
    assert path.read_bytes() == raw
