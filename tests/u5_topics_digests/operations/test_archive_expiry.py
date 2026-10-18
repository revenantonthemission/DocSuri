"""Expired realms may be preserved, but never reopened for normal execution."""

import hashlib
import json
import subprocess
import time
from pathlib import Path

import pytest

from backend import local_profile
from backend.local_profile import LocalProfile
from scripts import verify_docsuri_u5 as runner


@pytest.fixture
def profile_factory(tmp_path, monkeypatch):
    monkeypatch.setattr(local_profile, "RUN_PARENT", tmp_path)

    def create(unit="u5", *, expires=None):
        root = tmp_path / f"docsuri-{unit}-run"
        root.mkdir(mode=0o700)
        index = int(unit[1:])
        ports = {1: (18039, 15439), 2: (18049, 15449), 3: (18059, 15459),
                 4: (18079, 15479), 5: (18089, 15489)}
        realms = {
            "u1": ("u1-integrated-paper-journey", "diagnostic"),
            "u2": ("u2-account-personal-controls", "account-controls"),
            "u3": ("u3-paper-corpus-capabilities", "corpus-maintenance"),
            "u4": ("u4-research-novelty", "research-workspace"),
            "u5": (runner.UNIT, runner.REALM),
        }
        run_id = f"docsuri-{unit}-0123456789abcdef"
        created = time.time() - 90000
        value = {
            "runId": run_id, "profile": "synthetic-local",
            "repository": str(runner.ROOT), "unit": realms[unit][0],
            "realm": realms[unit][1], "database": f"docsuri_{unit}",
            "applicationPort": ports[index][0], "databasePort": ports[index][1],
            "createdAt": created, "expiresAt": created + 86400 if expires is None else expires,
            "databaseImage": runner.IMAGE, "policy": runner.POLICY,
            "container": run_id, "volume": run_id + "-pgdata",
        }
        path = root / "environment.json"

        def save():
            raw = json.dumps(value).encode()
            path.write_bytes(raw)
            path.chmod(0o600)
            marker = root / "ownership.json"
            marker.write_text(json.dumps({
                "runId": run_id, "manifestSha256": hashlib.sha256(raw).hexdigest(),
            }))
            marker.chmod(0o600)

        save()
        return path, value, save

    return create


@pytest.mark.parametrize("unit", ["u1", "u2", "u3", "u4", "u5"])
def test_expired_normal_profiles_remain_refused(profile_factory, unit):
    path, value, _ = profile_factory(unit)
    with pytest.raises(ValueError, match="retention expired"):
        LocalProfile.load(path)
    metadata = LocalProfile.preservation_identity(path)
    assert isinstance(metadata, dict)
    assert metadata["expiresAt"] == value["expiresAt"] < time.time()


@pytest.mark.parametrize("unit", ["u2", "u3", "u4", "u5"])
def test_normal_profiles_retain_the_future_retention_bound(profile_factory, unit):
    path, value, save = profile_factory(unit, expires=time.time() + 90000)
    with pytest.raises(ValueError, match="finite retention"):
        LocalProfile.load(path)
    value["expiresAt"] = time.time() + 3600
    save()
    assert LocalProfile.load(path).expires_at == value["expiresAt"]


@pytest.mark.parametrize("changes", [
    {"createdAt": float("nan")}, {"expiresAt": float("inf")},
    {"createdAt": True}, {"expiresAt": "expired"},
    {"createdAt": -1}, {"createdAt": 2000000000},
    {"createdAt": 1000, "expiresAt": 1000},
    {"createdAt": 1000, "expiresAt": 87401},
])
def test_preservation_requires_finite_original_retention(profile_factory, changes):
    path, value, save = profile_factory()
    value.update(changes)
    save()
    with pytest.raises(ValueError, match="finite original retention"):
        LocalProfile.preservation_identity(path)


@pytest.fixture
def archival_boundary(profile_factory, monkeypatch):
    path, value, save = profile_factory()
    monkeypatch.setattr(runner, "RUN", path.parent)
    boundary = {"stopped": False, "clients": 0, "databaseRunId": value["runId"],
                "containerLabel": value["runId"], "volumeLabel": value["runId"]}

    def require(args, **kwargs):
        if args[:3] == ["docker", "container", "inspect"]:
            record = {
                "Config": {"Image": runner.IMAGE,
                           "Labels": {runner.LABEL: boundary["containerLabel"]}},
                "HostConfig": {
                    "Memory": runner.DB_MEMORY, "MemorySwap": runner.DB_MEMORY,
                    "NanoCpus": 1_000_000_000, "PidsLimit": 64, "ReadonlyRootfs": True,
                    "PortBindings": {"5432/tcp": [{"HostIp": "127.0.0.1",
                                                   "HostPort": str(runner.DATABASE_PORT)}]},
                },
                "State": {"Running": not boundary["stopped"]},
                "Mounts": [{"Type": "volume", "Name": value["volume"],
                            "Destination": "/var/lib/postgresql/data"}],
            }
            assert args[3] == value["container"]
            return subprocess.CompletedProcess(args, 0, json.dumps([record]))
        if args[:3] == ["docker", "volume", "inspect"]:
            assert args[3] == value["volume"]
            return subprocess.CompletedProcess(args, 0, json.dumps([
                {"Labels": {runner.LABEL: boundary["volumeLabel"]}},
            ]))
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


def test_expired_owned_idle_realm_is_preserved_without_renewal(archival_boundary):
    path, value, _, boundary = archival_boundary
    original = path.read_bytes()
    result = runner.archive_owned(path)
    preserved = Path(result["path"])
    assert boundary["stopped"] is True
    assert not path.parent.exists()
    assert (preserved / "environment.json").read_bytes() == original
    assert result["expiresAt"] == value["expiresAt"] < time.time()
    assert result["volumePreserved"] == value["volume"]


@pytest.mark.parametrize("defect", [
    "hash", "custody", "symlink", "unit", "port", "image", "policy",
    "container-name", "volume-name", "container-label", "volume-label",
    "database-identity", "active-client",
])
def test_invalid_or_busy_expired_realms_never_stop_or_move(archival_boundary, defect):
    path, value, save, boundary = archival_boundary
    if defect == "hash":
        path.write_text(path.read_text() + " ")
    elif defect == "custody":
        path.chmod(0o644)
    elif defect == "symlink":
        target = path.with_name("saved.json")
        path.rename(target)
        path.symlink_to(target)
    elif defect in {"unit", "port", "image", "policy", "container-name", "volume-name"}:
        field = {"unit": "unit", "port": "databasePort", "image": "databaseImage",
                 "policy": "policy", "container-name": "container", "volume-name": "volume"}[defect]
        value[field] = "foreign"
        save()
    elif defect == "container-label":
        boundary["containerLabel"] = "foreign"
    elif defect == "volume-label":
        boundary["volumeLabel"] = "foreign"
    elif defect == "database-identity":
        boundary["databaseRunId"] = "foreign"
    else:
        boundary["clients"] = 1
    with pytest.raises((ValueError, runner.Refused)):
        runner.archive_owned(path)
    assert not boundary["stopped"]
    assert path.parent.is_dir()
