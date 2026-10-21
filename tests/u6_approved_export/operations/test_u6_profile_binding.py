"""The U6 environment's identity: its manifest, its origin and its preservation identity."""

import hashlib
import json
import sys
import time
from dataclasses import replace
from pathlib import Path

import pytest
from backend import local_profile as profiles
from scripts import verify_docsuri_u6 as runner

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "ops/src"))
from docsuri_ops.local_transport import inspect_transport  # noqa: E402

UNOWNED_ORIGIN = "https://127.0.0.1:18069"


def private_record(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value))
    path.chmod(0o600)


@pytest.fixture
def manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(profiles, "RUN_PARENT", tmp_path)
    root = tmp_path / "docsuri-u6-run"
    root.mkdir(mode=0o700)
    path = root / "environment.json"
    created = time.time() - 60
    value = {
        "unit": "u6-approved-export",
        "profile": "synthetic-local",
        "repository": str(Path(profiles.__file__).resolve().parents[1]),
        "runId": "docsuri-u6-0123456789abcdef",
        "database": "docsuri_u6",
        "realm": "approved-export",
        "applicationPort": 18099,
        "databasePort": 15499,
        "createdAt": created,
        "expiresAt": created + 86400,
    }

    def save(**changes):
        private_record(path, dict(value, **changes))
        private_record(
            root / "ownership.json",
            {
                "runId": changes.get("runId", value["runId"]),
                "manifestSha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            },
        )
        return path

    save()
    return path, save, value


def test_a_u6_manifest_loads_with_its_ports_and_realm(manifest):
    profile = profiles.LocalProfile.load(manifest[0])
    assert (profile.database_name, profile.realm, profile.database_port, profile.origin) == (
        "docsuri_u6",
        "approved-export",
        15499,
        "https://127.0.0.1:18099",
    )


def test_the_owned_realm_is_the_u6_environment(realm):
    assert (realm.realm, realm.database_name, realm.origin) == (
        "approved-export",
        "docsuri_u6",
        "https://127.0.0.1:18099",
    )
    assert realm.root == runner.RUN


@pytest.mark.parametrize(
    "changes",
    [
        {"applicationPort": 18069},
        {"applicationPort": 18089},
        {"databasePort": 15489},
        {"realm": "topics-digests"},
        {"database": "docsuri_u5"},
        {"unit": "u5-topics-digests"},
        {"runId": "docsuri-u5-0123456789abcdef"},
    ],
)
def test_a_cross_unit_or_unowned_identity_is_refused(manifest, changes):
    with pytest.raises(ValueError):
        profiles.LocalProfile.load(manifest[1](**changes))


def test_18069_is_still_refused_as_an_unowned_origin(realm):
    from backend.local_browser import EXPORT_ORIGIN, boundary_route
    from fastapi import APIRouter, FastAPI
    from fastapi.testclient import TestClient

    assert EXPORT_ORIGIN == "https://127.0.0.1:18099"
    with pytest.raises(ValueError, match="unowned browser origin"):
        boundary_route(UNOWNED_ORIGIN)
    router = APIRouter(route_class=boundary_route(EXPORT_ORIGIN))

    @router.get("/private-boundary")
    def observed():
        return {"observed": True}

    app = FastAPI()
    app.include_router(router)
    with TestClient(app, base_url=EXPORT_ORIGIN) as client:
        assert client.get("/private-boundary").status_code == 200
        refused = client.get("/private-boundary", headers={"Host": "127.0.0.1:18069"})
        assert refused.status_code == 403
    with pytest.raises(ValueError):
        inspect_transport(replace(realm, origin=UNOWNED_ORIGIN))


def test_an_expired_environment_keeps_its_preservation_identity(manifest, monkeypatch):
    path, save, value = manifest
    created = time.time() - 90000
    save(createdAt=created, expiresAt=created + 86400)
    with pytest.raises(ValueError, match="retention expired"):
        profiles.LocalProfile.load(path)
    identity = profiles.LocalProfile.preservation_identity(path)
    assert identity["runId"] == value["runId"]
    assert identity["expiresAt"] < time.time()
    monkeypatch.setattr(runner, "RUN", path.parent)
    save(
        createdAt=created,
        expiresAt=created + 86400,
        databaseImage=runner.IMAGE,
        policy=runner.POLICY,
        container=value["runId"],
        volume=value["runId"] + "-pgdata",
    )
    assert runner.archive_identity(path)["unit"] == "u6-approved-export"
    save(createdAt=created, expiresAt=created + 86400, policy="u5-synthetic-v1")
    with pytest.raises(runner.Refused):
        runner.archive_identity(path)
