"""Owned U4 identity and credential separation, without provisioning a database."""

import hashlib
import json
import time
from pathlib import Path

import pytest

from backend import local_profile as profiles
from backend import transactions as tx


def private_record(path, value):
    path.write_text(json.dumps(value))
    path.chmod(0o600)


@pytest.fixture
def manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(profiles, "RUN_PARENT", tmp_path)
    root = tmp_path / "docsuri-u4-run"
    root.mkdir(mode=0o700)
    path = root / "environment.json"
    value = {
        "unit": "u4-research-novelty", "profile": "synthetic-local",
        "repository": str(Path(profiles.__file__).resolve().parents[1]),
        "runId": "docsuri-u4-0123456789abcdef", "database": "docsuri_u4",
        "realm": "research-workspace", "applicationPort": 18079,
        "databasePort": 15479, "expiresAt": time.time() + 3600,
    }

    def save(**changes):
        private_record(path, dict(value, **changes))
        private_record(root / "ownership.json", {
            "runId": changes.get("runId", value["runId"]),
            "manifestSha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })
        return path

    save()
    return path, save


def test_loads_only_the_new_owned_research_realm(manifest):
    profile = profiles.LocalProfile.load(manifest[0])
    assert (profile.database_name, profile.realm, profile.database_port, profile.origin) == (
        "docsuri_u4", "research-workspace", 15479, "https://127.0.0.1:18079",
    )


@pytest.mark.parametrize("changes", [
    {"unit": "u3-paper-corpus-capabilities"},
    {"database": "docsuri_u3"},
    {"realm": "corpus-maintenance"},
    {"databasePort": 15469},
    {"applicationPort": 18069},
    {"runId": "docsuri-u3-0123456789abcdef"},
    {"databaseAdminPassword": "not-permitted-in-runtime-manifest"},
    {"expiresAt": 1},
])
def test_rejects_cross_unit_or_unsafe_identity(manifest, changes):
    path = manifest[1](**changes)
    with pytest.raises(ValueError):
        profiles.LocalProfile.load(path)


def test_does_not_extend_retention(manifest):
    path = manifest[1](expiresAt=time.time() + 172800)
    with pytest.raises(ValueError, match="finite retention"):
        profiles.LocalProfile.load(path)


def test_refuses_changed_manifest_without_matching_owner_receipt(manifest):
    path = manifest[0]
    value = json.loads(path.read_text())
    value["expiresAt"] += 1
    private_record(path, value)
    with pytest.raises(ValueError, match="identity mismatch"):
        profiles.LocalProfile.load(path)


def test_refuses_manifest_symlink_and_world_readable_record(manifest):
    path = manifest[0]
    target = path.with_name("saved.json")
    path.rename(target)
    path.symlink_to(target)
    with pytest.raises(ValueError):
        profiles.LocalProfile.load(path)
    path.unlink()
    target.rename(path)
    path.chmod(0o644)
    with pytest.raises(ValueError, match="ownership mismatch"):
        profiles.LocalProfile.load(path)


class Pool:
    """No connection opened; these checks concern pool allocation, not SQL."""

    def __init__(self, **options):
        self.kwargs = options["kwargs"]
        self.options = options
        self.closed = False

    def close(self):
        self.closed = True


def test_research_owner_keeps_shared_normal_and_recovery_budgets(manifest, monkeypatch):
    profile = profiles.LocalProfile.load(manifest[0])
    private_record(profile.root / "owner-credentials.json", {
        "runId": profile.run_id,
        "roles": {name: "synthetic-test" for name in tx.OWNERS | {"research"}},
    })
    monkeypatch.setattr(tx, "NullConnectionPool", Pool)
    api = tx.OwnerTransactions(profile)
    worker = tx.OwnerTransactions(profile, process="worker")
    recovery = tx.OwnerTransactions(profile, process="observation")
    try:
        assert set(api._pools) == tx.OWNERS | {"research"}
        assert api._gate is worker._gate
        assert api._recovery_gate is recovery._gate
        assert api._pools["research"].kwargs["dbname"] == "docsuri_u4"
        assert api._pools["research"].kwargs["user"] == "docsuri_research"
        assert api._transaction_seconds == 5
        assert api._queue_seconds == 1
        for _ in range(5):
            assert api._gate.acquire(blocking=False)
        assert not api._gate.acquire(blocking=False)
        for _ in range(5):
            api._gate.release()
    finally:
        for connection_set in (api, worker, recovery):
            connection_set.close()
    assert all(pool.closed for pool in (*api._pools.values(), *api._recovery_pools.values()))


@pytest.mark.parametrize("database,realm,research_in_credentials", [
    ("docsuri_u4", "research-workspace", False),
    ("docsuri_u3", "corpus-maintenance", True),
    ("docsuri_u2", "account-controls", True),
])
def test_research_credentials_do_not_widen_legacy_owner_sets(
    tmp_path, monkeypatch, database, realm, research_in_credentials,
):
    monkeypatch.setattr(tx, "NullConnectionPool", Pool)
    profile = profiles.LocalProfile(
        tmp_path, "identity-test", "https://127.0.0.1:18079", 15479,
        time.time() + 100, database, realm,
    )
    owners = tx.OWNERS | {"research"} if research_in_credentials else tx.OWNERS
    private_record(tmp_path / "owner-credentials.json", {
        "runId": profile.run_id, "roles": {name: "synthetic-test" for name in owners},
    })
    with pytest.raises(ValueError, match="credential identity mismatch"):
        tx.OwnerTransactions(profile)


def test_research_browser_origin_is_explicit_and_host_bound():
    from fastapi import APIRouter, FastAPI
    from fastapi.testclient import TestClient

    from backend.local_browser import RESEARCH_ORIGIN, boundary_route

    router = APIRouter(route_class=boundary_route(RESEARCH_ORIGIN))

    @router.get("/private-boundary")
    def observed():
        return {"observed": True}

    app = FastAPI()
    app.include_router(router)
    with TestClient(app, base_url=RESEARCH_ORIGIN) as client:
        assert client.get("/private-boundary").status_code == 200
        assert client.get("/private-boundary", headers={"Origin": "https://evil.invalid"}).status_code == 403
        assert client.get("/private-boundary", headers={"Host": "127.0.0.1:18069"}).status_code == 403
    with pytest.raises(ValueError, match="unowned browser origin"):
        boundary_route("https://127.0.0.1:18069")
