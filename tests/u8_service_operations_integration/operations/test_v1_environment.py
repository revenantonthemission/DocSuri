"""The synthetic v1's environment and supervised service control (U8 plan Step 43; the
person's safety rule of 2026-10-23).

v1's own code defaults to v1's real stores (its session store to the live site's Redis on
6379). Every place that runs v1's code in the realm takes its environment only from the
file `u8_synthetic_v1.wire_driver` writes, and only after
`docsuri_ops.u8_platform.v1_environment` has checked it: a missing file, a loose
file, or any address that is not the realm's own fails closed, before any v1 process
starts. These tests start no v1 process and open no connection.
"""

from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from docsuri_ops.u8_platform.drivers import DriverRefused
from docsuri_ops.u8_platform.drivers import realm as realm_driver
from docsuri_ops.u8_platform.drivers.realm import RealmDriver
from docsuri_ops.u8_platform.v1_environment import (
    V1_REAL_PORTS,
    V1EnvironmentRefused,
    load,
    require_realm_environment,
    runtime_environment,
)
from tests.u8_service_operations_integration.v1_flows import (
    realm_environment,
    write_environment,
)

ROOT = Path(__file__).resolve().parents[3]
RUN_ID = "docsuri-u8-0123456789abcdef"
LABEL = "dev.docsuri.u8.run.v1-api"


write_file = write_environment


def test_the_realm_environment_is_accepted_and_carries_only_its_addresses(tmp_path):
    written = realm_environment()
    path = write_file(tmp_path, written)
    checked = load(path, run_root=tmp_path)
    assert checked["REDIS_PORT"] == "16389"
    runtime = runtime_environment(checked, ROOT)
    assert set(runtime) - set(checked) <= {"PATH", "HOME", "LANG", "TMPDIR", "PYTHONPATH"}
    # A secret that merely contains a real port's digits is not an address.
    secret = runtime["AWS_SECRET_ACCESS_KEY"]
    assert secret == written["AWS_SECRET_ACCESS_KEY"]
    assert "6379" in secret and "5432" in secret


@pytest.mark.parametrize("port", sorted({6379, 5432, 9200, 9000, 3000}))
def test_every_real_v1_port_is_refused_wherever_it_appears(port):
    assert port in V1_REAL_PORTS
    cases = [
        {"REDIS_PORT": str(port)},
        {"DATABASE_URL": f"postgresql://docsuri:{secrets.token_hex(8)}@127.0.0.1:{port}/docsuri"},
        {"DOCSURI_OPENSEARCH_ENDPOINT": f"http://127.0.0.1:{port}"},
        {"AWS_ENDPOINT_URL_S3": f"http://127.0.0.1:{port}"},
        {"DOCSURI_GATEWAY_URL": f"http://127.0.0.1:{port}"},
        {"CORS_ORIGINS": f"http://localhost:{port}"},
    ]
    for change in cases:
        with pytest.raises(V1EnvironmentRefused):
            require_realm_environment({**realm_environment(), **change})


def test_a_missing_store_another_host_or_an_alternate_route_is_refused():
    base = realm_environment()
    for change, reason in (
        ({"REDIS_HOST": "localhost"}, "redis-not-realm"),
        ({"REDIS_HOST": "10.0.0.5"}, "redis-not-realm"),
        ({"DATABASE_URL": "sqlite:///./docsuri-dev.db"}, "store-not-realm"),
        ({"AWS_ENDPOINT_URL_S3": "http://192.0.2.1:19009"}, "store-not-realm"),
        ({"DB_HOST": "127.0.0.1"}, "alternate-route"),
        ({"AWS_ENDPOINT_URL": "http://127.0.0.1:19009"}, "alternate-route"),
        ({"REDIS_URL": "redis://127.0.0.1:16389"}, "alternate-route"),
    ):
        with pytest.raises(V1EnvironmentRefused, match=reason):
            require_realm_environment({**base, **change})
    for key in ("DATABASE_URL", "DOCSURI_OPENSEARCH_ENDPOINT", "AWS_ENDPOINT_URL_S3"):
        partial = {name: value for name, value in base.items() if name != key}
        with pytest.raises(V1EnvironmentRefused, match="store-missing"):
            require_realm_environment(partial)


def test_the_file_fails_closed_when_missing_loose_or_elsewhere(tmp_path):
    with pytest.raises(V1EnvironmentRefused, match="unconfigured"):
        load(None, run_root=tmp_path)
    with pytest.raises(V1EnvironmentRefused, match="missing"):
        load(tmp_path / "v1" / "environment.json", run_root=tmp_path)
    loose = write_file(tmp_path, realm_environment(), mode=0o644)
    with pytest.raises(V1EnvironmentRefused, match="custody"):
        load(loose, run_root=tmp_path)
    elsewhere = tmp_path / "other" / "environment.json"
    elsewhere.parent.mkdir()
    elsewhere.write_text(json.dumps(realm_environment()))
    with pytest.raises(V1EnvironmentRefused, match="outside-the-run"):
        load(elsewhere, run_root=tmp_path)
    linked = tmp_path / "v1" / "environment.json"
    linked.unlink()
    linked.symlink_to(elsewhere)
    with pytest.raises(V1EnvironmentRefused, match="unreadable"):
        load(linked, run_root=tmp_path)


def driver(tmp_path: Path, **config) -> RealmDriver:
    return RealmDriver({"kind": "realm", "runRoot": str(tmp_path),
                        "stateRoot": str(tmp_path / "state"), "runId": RUN_ID,
                        "v1Checkout": str(ROOT), "v1Runtime": [sys.executable], **config})


def test_the_lifecycle_apply_never_starts_v1_without_the_checked_file(tmp_path, monkeypatch):
    started = []
    monkeypatch.setattr(realm_driver.subprocess, "run",
                        lambda *args, **kwargs: started.append(args) or None)
    inputs = {"outcomes": [], "accounts": []}
    with pytest.raises(DriverRefused, match="v1-environment-unconfigured"):
        driver(tmp_path).effect("v1-lifecycle-apply", inputs, context={})
    real = write_file(tmp_path, {**realm_environment(), "REDIS_PORT": "6379"})
    with pytest.raises(DriverRefused, match="redis-not-realm"):
        driver(tmp_path, v1EnvironmentFile=str(real)).effect("v1-lifecycle-apply", inputs,
                                                             context={})
    assert started == []


def test_the_lifecycle_apply_runs_v1_with_the_checked_environment_only(tmp_path, monkeypatch):
    seen = {}

    def run(argv, **kwargs):
        seen.update(argv=argv, env=kwargs["env"], cwd=kwargs["cwd"])
        return subprocess.CompletedProcess(argv, 0, b'{"ok": true}', b"")

    monkeypatch.setattr(realm_driver.subprocess, "run", run)
    monkeypatch.setenv("REDIS_HOST", "localhost")
    monkeypatch.setenv("DATABASE_URL", "postgresql://docsuri@127.0.0.1:5432/docsuri")
    path = write_file(tmp_path, realm_environment())
    refs = driver(tmp_path, v1EnvironmentFile=str(path)).effect(
        "v1-lifecycle-apply", {"outcomes": [], "accounts": []}, context={})
    assert refs == ["v1/lifecycle"]
    assert seen["env"]["REDIS_PORT"] == "16389" and seen["env"]["REDIS_HOST"] == "127.0.0.1"
    assert ":15510/" in seen["env"]["DATABASE_URL"]
    assert seen["argv"][-1] == "backend.modules.accounts.services.v2_rollback_apply"


def test_the_synthetic_v1_starts_its_api_only_from_the_checked_file(monkeypatch, tmp_path):
    sys.path.insert(0, str(ROOT / "scripts"))
    import u8_synthetic_v1 as v1

    monkeypatch.setattr(v1, "STATE", tmp_path / "v1")
    monkeypatch.setattr(v1, "RUN", tmp_path)
    with pytest.raises(v1.V1Refused, match="missing"):
        v1.child_command(v1.API_LABEL, "0" * 40)
    write_file(tmp_path, {**realm_environment(), "REDIS_PORT": "6379"})
    with pytest.raises(v1.V1Refused, match="redis-not-realm"):
        v1.child_command(v1.API_LABEL, "0" * 40)
    write_file(tmp_path, realm_environment())
    argv, cwd, environment = v1.child_command(v1.API_LABEL, "0" * 40)
    assert "18112" in argv and environment["REDIS_PORT"] == "16389" and cwd == v1.ROOT


# --- the stop on a realm that outlived its retention ----------------------------------------


def test_run_identity_admits_an_expired_realm_for_the_stop_only(monkeypatch):
    sys.path.insert(0, str(ROOT / "scripts"))
    import backend.local_profile as local_profile
    import u8_synthetic_v1 as v1

    manifest = v1.RUN / "environment.json"
    if not manifest.exists():
        pytest.fail("the realm's environment is set up before the operations phase")
    expires = json.loads(manifest.read_text())["expiresAt"]
    monkeypatch.setattr(local_profile.time, "time", lambda: expires + 1)
    with pytest.raises(ValueError, match="retention expired"):
        v1.run_identity(manifest)
    value = v1.run_identity(manifest, allow_expired=True)
    assert value["runId"].startswith("docsuri-u8-")


def test_run_identity_keeps_the_realm_check_for_an_expired_identity(monkeypatch):
    sys.path.insert(0, str(ROOT / "scripts"))
    import backend.local_profile as local_profile
    import u8_synthetic_v1 as v1

    manifest = v1.RUN / "environment.json"
    if not manifest.exists():
        pytest.fail("the realm's environment is set up before the operations phase")
    expires = json.loads(manifest.read_text())["expiresAt"]
    monkeypatch.setattr(local_profile.time, "time", lambda: expires + 1)
    monkeypatch.setattr(
        local_profile.LocalProfile, "preservation_identity",
        lambda path: {"realm": "elsewhere", "database": "docsuri_u8",
                      "runId": "docsuri-u8-" + "0" * 16})
    with pytest.raises(v1.V1Refused, match="composed realm only"):
        v1.run_identity(manifest, allow_expired=True)


def test_the_v1_stop_itself_accepts_an_expired_realms_identity(monkeypatch, tmp_path):
    sys.path.insert(0, str(ROOT / "scripts"))
    import backend.local_profile as local_profile
    import u8_synthetic_v1 as v1

    manifest = v1.RUN / "environment.json"
    if not manifest.exists():
        pytest.fail("the realm's environment is set up before the operations phase")
    expires = json.loads(manifest.read_text())["expiresAt"]
    monkeypatch.setattr(local_profile.time, "time", lambda: expires + 1)
    monkeypatch.setattr(v1, "STATE", tmp_path / "v1")
    monkeypatch.setattr(v1, "SERVICES", tmp_path / "platform" / "services")
    monkeypatch.setattr(v1, "supervisor_pid", lambda: None)

    class QuietProbe:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def connect_ex(self, address):
            return 1

    monkeypatch.setattr(v1.socket, "socket", QuietProbe)
    stopped = []
    monkeypatch.setattr(v1, "stop_data_plane",
                        lambda run_id: stopped.append(run_id) or {"state": "stopped"})
    result = v1.v1_down(manifest)
    assert result["state"] == "v1-down"
    assert stopped == [json.loads(manifest.read_text())["runId"]]


# --- supervised service control -------------------------------------------------------------


def register(services: Path, pid: int, run_id: str = RUN_ID) -> None:
    folder = services / "supervisors"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{LABEL}.json").write_text(json.dumps({"pid": pid, "runId": run_id}))


def acknowledge_when_asked(services: Path, *, observed: str, result: str = "succeeded",
                           order: list | None = None,
                           polled: threading.Event | None = None) -> threading.Thread:
    """A stand-in supervisor that acknowledges once the effect has written its wanted
    state (re-read every 0.01 s for at most 10 s), never after a fixed time. Given
    `polled`, it also waits (at most 10 s) until the effect has looked for the missing
    acknowledgement, so an effect that returns without waiting is never acknowledged. It
    notes `acknowledging` in `order` just before it writes the acknowledgement."""
    def answer():
        deadline = time.monotonic() + 10
        while not (services / f"{LABEL}.json").exists():
            if time.monotonic() >= deadline:
                return  # never asked: the effect is then refused unacknowledged
            time.sleep(0.01)
        if polled is not None and not polled.wait(10):
            return  # never waited for: the effect returned without an acknowledgement
        wanted = json.loads((services / f"{LABEL}.json").read_text())  # written by rename
        if order is not None:
            order.append("acknowledging")
        (services / f"{LABEL}.ack.json").write_text(json.dumps({
            "operationId": wanted["operationId"], "observed": observed, "result": result}))

    thread = threading.Thread(target=answer)
    thread.start()
    return thread


def control(tmp_path: Path, action: str, operation: str = "op-1"):
    services = tmp_path / "services"
    return driver(tmp_path, servicesRoot=str(services)).effect(
        "service-control", {"label": LABEL, "action": action}, context={
            "operationId": operation})


def test_an_unsupervised_label_records_its_wanted_state_and_waits_for_no_one(tmp_path):
    """No supervisor is registered, so the effect writes the wanted state and returns
    without an acknowledgement. The label has no wanted-state file, so it reports
    `wasLoaded=true`: a label never set cannot be known to be stopped, and production's
    fixed program answers loaded for a start of a job that already runs (review finding,
    Minor, R18). Only a label set `stopped` counts as unloaded."""
    assert control(tmp_path, "start") == [f"service/{LABEL}/start", "fact:wasLoaded=true"]
    wanted = json.loads((tmp_path / "services" / f"{LABEL}.json").read_text())
    assert wanted["state"] == "running"
    assert not (tmp_path / "services" / f"{LABEL}.ack.json").exists()
    assert control(tmp_path, "stop", "op-2") == [f"service/{LABEL}/stop", "fact:wasLoaded=true"]
    assert control(tmp_path, "start", "op-3") == [f"service/{LABEL}/start",
                                                  "fact:wasLoaded=false"]


def test_a_supervised_start_returns_only_after_the_supervisor_reports_it_running(tmp_path,
                                                                                monkeypatch):
    register(tmp_path / "services", os.getpid())
    order: list[str] = []
    polled = threading.Event()
    real_read = realm_driver._read

    def noting_read(path: Path) -> dict | None:
        # A call-through spy: it notes the driver's look for a missing acknowledgement.
        answer = real_read(path)
        if path.name == f"{LABEL}.ack.json" and answer is None:
            polled.set()
        return answer

    monkeypatch.setattr(realm_driver, "_read", noting_read)
    thread = acknowledge_when_asked(tmp_path / "services", observed="running", order=order,
                                    polled=polled)
    # No wanted-state file before the start, so the label reads as loaded (R18).
    assert control(tmp_path, "start") == [f"service/{LABEL}/start", "fact:wasLoaded=true"]
    order.append("returned")
    thread.join()
    # The start returned only after the supervisor began acknowledging it.
    assert order == ["acknowledging", "returned"]


def test_a_failed_acknowledgement_fails_the_effect(tmp_path):
    register(tmp_path / "services", os.getpid())
    thread = acknowledge_when_asked(tmp_path / "services", observed="stopped",
                                    result="failed")
    with pytest.raises(DriverRefused, match="service-control-failed"):
        control(tmp_path, "start")
    thread.join()


def test_a_gone_or_silent_supervisor_fails_the_effect(tmp_path, monkeypatch):
    services = tmp_path / "services"
    register(services, os.getpid())
    monkeypatch.setattr(realm_driver, "SERVICE_ACK_SECONDS", 0.5)
    with pytest.raises(DriverRefused, match="service-control-unacknowledged"):
        control(tmp_path, "stop")
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    register(services, dead.pid)
    # The first stop wrote its wanted state before its acknowledgement failed, so the
    # job reads as stopped before each of these (`wasLoaded` false).
    assert control(tmp_path, "stop", "op-2") == [f"service/{LABEL}/stop",
                                                 "fact:wasLoaded=false"]  # unsupervised
    register(services, os.getpid(), run_id="docsuri-u8-ffffffffffffffff")
    assert control(tmp_path, "stop", "op-3") == [f"service/{LABEL}/stop",
                                                 "fact:wasLoaded=false"]  # another run's


# --- the realm's secrets, made once per realm (Step 96(d), L1-36; Step 97(h)) ----------------


def scripts_on_path() -> None:
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)


def run_root(tmp_path: Path, run_id: str) -> Path:
    """A private run root holding a 0600 `environment.json` that names `run_id`."""
    root = tmp_path / run_id
    root.mkdir(mode=0o700)
    descriptor = os.open(root / "environment.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                         0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump({"runId": run_id}, stream)
    return root


def test_the_synthetic_v1_password_is_made_once_per_realm(tmp_path):
    from scripts import verify_docsuri_u8 as runner

    scripts_on_path()
    import u8_fixtures
    import u8_synthetic_v1

    first = run_root(tmp_path, RUN_ID)
    runner.write_v1_password(first, RUN_ID)
    record = first / u8_fixtures.V1_PASSWORD_FILE
    assert record.stat().st_mode & 0o777 == 0o600
    value = json.loads(record.read_text())
    password = value["password"]
    assert value["runId"] == RUN_ID and password.startswith("V1!") and len(password) > 20
    dataset = u8_fixtures.v1_dataset(first)
    assert dataset.password == password
    assert u8_fixtures.dataset_record(dataset, RUN_ID)["password"] == password
    assert u8_synthetic_v1.dataset_for(first).password == password
    # Another run's record differs.
    second_id = "docsuri-u8-fedcba9876543210"
    second = run_root(tmp_path, second_id)
    runner.write_v1_password(second, second_id)
    assert json.loads((second / u8_fixtures.V1_PASSWORD_FILE).read_text())["password"] != (
        password)
    # A run root without the record, or with another run's, is refused.
    bare = run_root(tmp_path, "docsuri-u8-00000000000000aa")
    with pytest.raises(ValueError, match="no synthetic v1 password"):
        u8_fixtures.v1_dataset(bare)
    os.replace(second / u8_fixtures.V1_PASSWORD_FILE, bare / u8_fixtures.V1_PASSWORD_FILE)
    with pytest.raises(ValueError, match="belongs to another run"):
        u8_fixtures.v1_dataset(bare)


def test_the_identity_client_secrets_are_made_once_per_realm(tmp_path):
    from types import SimpleNamespace

    from backend.u8_host import PROVIDER_ENVIRONMENT, PROVIDER_SECRETS
    from scripts import verify_docsuri_u8 as runner

    scripts_on_path()
    import serve_docsuri_u8

    def profile(root: Path, run_id: str) -> SimpleNamespace:
        return SimpleNamespace(is_production=False, realm=serve_docsuri_u8.REALM,
                               database_name=serve_docsuri_u8.DATABASE, root=root,
                               run_id=run_id)

    root = run_root(tmp_path, RUN_ID)
    runner.write_identity_clients(root, RUN_ID)
    record = root / "identity-clients.json"
    assert record.stat().st_mode & 0o777 == 0o600
    value = json.loads(record.read_text())
    assert value["runId"] == RUN_ID
    for provider in ("google", "orcid"):
        prefix = f"realm-{provider}-client-secret-"
        assert value[provider].startswith(prefix)
        assert len(value[provider]) == len(prefix) + 16
        int(value[provider][len(prefix):], 16)
    assert serve_docsuri_u8.standin_secrets(profile(root, RUN_ID)) == {
        "google": value["google"], "orcid": value["orcid"]}
    # Generated, not constant: the two providers differ, and another run's record differs
    # from this one for each provider.
    other_id = "docsuri-u8-fedcba9876543210"
    assert value["google"].split("-")[-1] != value["orcid"].split("-")[-1]
    (tmp_path / "second").mkdir()
    second_root = run_root(tmp_path / "second", other_id)
    runner.write_identity_clients(second_root, other_id)
    second = json.loads((second_root / "identity-clients.json").read_text())
    assert second["runId"] == other_id
    assert second["google"] != value["google"] and second["orcid"] != value["orcid"]
    assert second["google"].split("-")[-1] != second["orcid"].split("-")[-1]
    # A missing record, or another run's, is refused.
    with pytest.raises(ValueError, match="belongs to another run"):
        serve_docsuri_u8.standin_secrets(profile(root, other_id))
    bare = run_root(tmp_path, other_id)
    with pytest.raises(ValueError, match="no identity client record"):
        serve_docsuri_u8.standin_secrets(profile(bare, other_id))
    # A leftover private environment holding exactly these values, as a relaunch after
    # restart-host's SIGKILL finds it, is taken as the serve's own and removed at its end.
    leftover = root / PROVIDER_ENVIRONMENT
    values = {PROVIDER_SECRETS["provider." + name]: value[name] for name in ("google", "orcid")}
    descriptor = os.open(leftover, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump(values, stream)
    with serve_docsuri_u8.standin_clients(profile(root, RUN_ID)):
        assert json.loads(leftover.read_text()) == values
    assert not leftover.exists()
    # A file holding other values is left as it is.
    descriptor = os.open(leftover, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump({**values, "OTHER": secrets.token_hex(4)}, stream)
    with serve_docsuri_u8.standin_clients(profile(root, RUN_ID)):
        pass
    assert leftover.exists()
