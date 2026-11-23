"""Workflow 1's start checks, the refused-start state and registration (U8 plan Step 12).

Refusals that stop before any owner service is built run against a copy of the realm's
profile root in a temporary folder: the same run identity, database and owner logins,
with the one condition each case needs. The cases that build every contribution run
against the realm itself. The stand-in for a database that does not answer yet is a
closed loopback port the system assigns free (never a realm address: 15510 is the
synthetic v1's PostgreSQL) that a relay to the real instance opens after a few waits.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import os
import shutil
import socket
import tempfile
import threading
import time
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from backend import u8_migrations
from backend.control_runtime import WORK_DEADLINE
from backend.local_profile import KEY_FOLDERS
from backend.modules.operations.ledger import Ledger
from backend.u8_host import (
    BUILDERS,
    PROVIDER_ENVIRONMENT,
    Activation,
    HostProcess,
    Startup,
    compose,
    host_app,
    run_scheduler_once,
    run_workers,
    unauthorized_restore,
)
from backend.u8_main import REALM_MANIFEST, boundary_hosts
from backend.u8_profile import ProductionProfile, ProfileRefused
from backend.u8_registry import (
    CAPABILITIES,
    CONTRIBUTIONS,
    LIFECYCLE_MANIFEST,
    MODEL_EVIDENCE,
    NAVIGATION,
    REQUIRED,
    Manifest,
)
from backend.u8_workers import CompletePassIncomplete, CompleteWorker, bounded
from tests.u8_service_operations_integration.host_flows import set_flag, signal_or_failure

ROOT = Path(__file__).resolve().parents[3]
def closed_port() -> int:
    """A loopback port that answers nothing until the relay opens it: one the system
    assigns free, never a realm address (15510 is the synthetic v1's PostgreSQL, which
    the integration-carrying phases run)."""
    import socket

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


RELAY_PORT = closed_port()


def write_private(path: Path, payload: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload)


def copy_root(realm, parent: Path, *, without: tuple[str, ...] = ()):
    """A private profile root holding the realm's owner logins, its key folders and an
    empty ledger folder, less the names in `without`."""
    root = parent / "root"
    root.mkdir(mode=0o700)
    os.chmod(root, 0o700)
    if "owner-credentials.json" not in without:
        write_private(
            root / "owner-credentials.json", (realm.root / "owner-credentials.json").read_bytes()
        )
    for name in (*KEY_FOLDERS, "ledger"):
        if name not in without:
            (root / name).mkdir(mode=0o700)
            os.chmod(root / name, 0o700)
    return dataclasses.replace(realm, root=root)


async def ask(app, path: str, host: str = "127.0.0.1:18109") -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url=f"http://{host}"
    ) as http:
        return await http.get(path)


def started(load, **options) -> HostProcess:
    startup = Startup(load, role="host", **options)
    startup.run()
    return HostProcess(startup, hosts=boundary_hosts(REALM_MANIFEST))


async def assert_serves_only_health(process: HostProcess, check: str) -> None:
    assert process.startup.state == "refused" and process.startup.check == check
    assert process.startup.composition is None
    live = await ask(process, "/health/live")
    assert live.status_code == 200 and live.json() == {"process": "alive", "state": "refused"}
    ready = await ask(process, "/health/ready")
    assert ready.status_code == 503 and ready.json()["missing"] == [check]
    for path in ("/api/v2/capabilities", "/", "/search"):
        assert (await ask(process, path)).status_code == 404
    assert process.app is None


# --- 1. Each refusal is named and leaves only the health routes ------------------------


async def test_a_root_under_tmp_is_refused():
    parent = Path(tempfile.mkdtemp(prefix="docsuri-u8-start-test-", dir="/tmp"))
    try:
        root = parent / "profile"
        root.mkdir(mode=0o700)
        write_private(root / "environment.json", b"{}")
        process = started(
            lambda: ProductionProfile.load(root / "environment.json", service_uid=os.getuid())
        )
        await assert_serves_only_health(process, "root")
        assert process.startup.detail == "root-under-tmp"
    finally:
        shutil.rmtree(parent)


async def test_a_broken_ledger_is_refused(realm, tmp_path):
    profile = copy_root(realm, tmp_path)
    write_private(profile.root / "ledger" / "ledger.jsonl", b"")
    write_private(
        profile.root / "ledger" / "head.json",
        json.dumps({"count": 3, "head": "a" * 64}, separators=(",", ":")).encode(),
    )
    process = started(lambda: profile)
    await assert_serves_only_health(process, "ledger")


async def test_a_missing_key_folder_is_refused_while_accounts_exist(realm, tmp_path, authority):
    profile = copy_root(realm, tmp_path, without=("cursor-key",))
    process = started(lambda: profile)
    await assert_serves_only_health(process, "key-folders")
    assert process.startup.detail == "missing-with-accounts"


async def test_a_key_folder_that_is_not_the_profiles_own_is_refused(realm, tmp_path):
    profile = copy_root(realm, tmp_path)
    os.chmod(profile.root / "control-keys", 0o755)
    process = started(lambda: profile)
    await assert_serves_only_health(process, "key-folders")
    assert process.startup.detail == "control-keys-custody"


async def test_a_missing_service_secret_is_refused_by_name(realm, tmp_path):
    profile = copy_root(realm, tmp_path, without=("owner-credentials.json",))
    process = started(lambda: profile)
    await assert_serves_only_health(process, "service-secrets")
    assert process.startup.detail == "owner-credentials"


async def test_a_schema_digest_difference_is_refused_naming_it(realm, tmp_path):
    release = tmp_path / "release"
    changed = "backend/modules/export/u8_export.sql"
    for file in u8_migrations.chain_files():
        target = release / file
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / file).read_bytes())
    with open(release / changed, "a") as stream:
        stream.write("\n-- a changed migration\n")
    profile = copy_root(realm, tmp_path)
    process = started(lambda: profile, release_root=release)
    await assert_serves_only_health(process, "schema")
    assert changed in process.startup.detail


def held_restore() -> dict:
    """A RecoveryRequest version in the ledger's schema: a held production restore of
    the live environment, without `startAuthorizedAt`."""
    now = "2026-10-22T00:00:00.000Z"
    return {
        "recoveryRequestId": str(uuid4()), "revision": 1, "environment": "live",
        "origin": "administrator", "operation": "restore.production",
        "targetId": str(uuid4()), "expectedRevision": 1, "requestedBy": str(uuid4()),
        "mfaVerifiedAt": now, "submissionId": str(uuid4()), "idempotencyKey": "a" * 64,
        "state": "requested", "evidenceRefs": [], "createdAt": now, "updatedAt": now,
    }


async def test_an_active_restore_without_its_start_authorization_is_refused(realm, tmp_path):
    profile = copy_root(realm, tmp_path)
    ledger = Ledger.open(profile.root / "ledger", clock=realm_clock)
    try:
        request = held_restore()
        ledger.append("recovery-request", request, expect_revision=0)
        for revision, state in enumerate(("awaiting-operator", "running", "held"), start=2):
            request = {**request, "revision": revision, "state": state}
            ledger.append("recovery-request", request, expect_revision=revision - 1)
    finally:
        ledger.close()
    process = started(lambda: profile)
    await assert_serves_only_health(process, "restore-authorization")


def realm_clock():
    import datetime as dt

    return dt.datetime.now(dt.UTC)


def test_only_an_active_unauthorized_live_restore_blocks_the_start():
    held = {**held_restore(), "state": "held"}
    request = held["recoveryRequestId"]
    assert unauthorized_restore([held]) == request
    assert unauthorized_restore([{**held, "startAuthorizedAt": "2026-10-22T00:00:00.000Z"}]) is None
    assert unauthorized_restore([{**held, "state": "failed"}]) is None
    assert unauthorized_restore([{**held, "environment": "rehearsal"}]) is None
    assert unauthorized_restore([{**held, "operation": "restore.verify"}]) is None


# --- 2. A missing provider secret leaves only that provider unconfigured --------------


def test_a_missing_provider_secret_leaves_that_provider_unconfigured(realm):
    path = realm.root / PROVIDER_ENVIRONMENT
    write_private(path, json.dumps({"googleClientSecret": uuid4().hex}).encode())  # L1-36
    try:
        composition = compose(realm)
    finally:
        path.unlink()
    try:
        assert composition.report["providers"] == {
            "provider.google": "configured",
            "provider.orcid": "unconfigured",
            "provider.resend": "unconfigured",
        }
        # The sign-in and mail providers belong to account-controls, which runs the
        # composed realm's `u8-synthetic-v1` from Step 17 on.
        assert composition.activations["account-controls"].activation == "active"
        states = composition.capability_states()
        # A contribution's unavailability comes first (BR1.3).
        unavailable = dataclasses.replace(composition, activations={
            **composition.activations,
            "account-controls": Activation("account-controls", "unavailable",
                                           "policy-unresolved"),
        })
        assert unavailable.capability_states()["provider.orcid"] == {
            "state": "unavailable", "reason": "policy-unresolved"}
        # Only the provider without a secret is unconfigured; the configured one waits
        # for its first observation.
        assert states["provider.orcid"] == {"state": "unavailable", "reason": "unconfigured"}
        assert states["provider.resend"]["reason"] == "unconfigured"
        # Its state now derives from the realm's observations (Step 15): none yet, or an
        # old one from an earlier phase; never unconfigured.
        assert states["provider.google"]["reason"] in ("no-observation", "observation-stale")
        assert states["public.static"]["state"] == "available"
        # The rest starts: the composition and its contributions are built.
        assert composition.activations["paper-corpus"].activation == "active"
        assert composition.activations["service-operations"].activation == "active"
        assert composition.worker is not None
    finally:
        composition.close()


# --- 3. A database that does not answer yet -------------------------------------------


class Relay:
    """Opens the closed port: every connection is relayed to the realm's instance."""

    def __init__(self, target: int):
        self.target = target
        self.listener: socket.socket | None = None

    def open(self) -> None:
        self.listener = socket.create_server(("127.0.0.1", RELAY_PORT))
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self) -> None:
        while True:
            try:
                client, _ = self.listener.accept()
            except OSError:
                return
            upstream = socket.create_connection(("127.0.0.1", self.target))
            for source, sink in ((client, upstream), (upstream, client)):
                threading.Thread(target=self._pump, args=(source, sink), daemon=True).start()

    @staticmethod
    def _pump(source, sink) -> None:
        try:
            while chunk := source.recv(65536):
                sink.sendall(chunk)
        except OSError:
            pass
        finally:
            for side in (source, sink):
                try:
                    side.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

    def close(self) -> None:
        if self.listener is not None:
            self.listener.close()


def test_the_host_stays_live_and_not_ready_with_growing_waits_until_the_database_answers(realm):
    profile = dataclasses.replace(realm, database_port=RELAY_PORT)
    relay = Relay(realm.database_port)
    waits, observed = [], {}
    process: HostProcess | None = None

    def sleep(seconds):
        waits.append(seconds)
        if len(waits) == 2:
            live = asyncio.run(ask(process, "/health/live"))
            ready = asyncio.run(ask(process, "/health/ready"))
            observed.update(live=(live.status_code, live.json()),
                            ready=(ready.status_code, ready.json()))
        if len(waits) == 6:
            relay.open()

    startup = Startup(lambda: profile, role="host", sleep=sleep)
    process = HostProcess(startup, hosts=boundary_hosts(REALM_MANIFEST))
    try:
        composition = startup.run()
        assert waits == [1, 2, 4, 8, 16, 30]
        assert startup.waits == waits and startup.state == "composed"
        assert observed["live"] == (200, {"process": "alive", "state": "waiting-database"})
        assert observed["ready"][0] == 503 and observed["ready"][1]["missing"] == ["database"]
        assert composition.activations["paper-journey"].activation == "active"
        composition.close()
    finally:
        relay.close()


def test_a_stopped_start_ends_its_waits(realm):
    profile = dataclasses.replace(realm, database_port=RELAY_PORT)
    startup = Startup(lambda: profile, role="workers")
    thread = threading.Thread(target=startup.run)
    thread.start()
    deadline = time.monotonic() + 15
    while startup.state != "waiting-database" and time.monotonic() < deadline:
        time.sleep(0.05)
    startup.stop()
    thread.join(15)
    assert startup.state == "stopped" and startup.composition is None


# --- 4. A contribution whose schema digest differs ------------------------------------


def manifest_with(contributions) -> Manifest:
    return Manifest(
        contributions, CAPABILITIES, NAVIGATION, LIFECYCLE_MANIFEST, MODEL_EVIDENCE
    ).sealed().verify()


async def test_a_changed_schema_digest_makes_its_contribution_incompatible(realm):
    changed = tuple(
        dataclasses.replace(entry, schema_digest="0" * 64)
        if entry.contribution_id == "approved-export" else entry
        for entry in CONTRIBUTIONS
    )
    composition = compose(realm, manifest=manifest_with(changed))
    try:
        assert composition.activations["approved-export"].activation == "unavailable"
        assert composition.activations["approved-export"].reason == "incompatible"
        assert "approved-export" not in composition.parts
        states = composition.capability_states()
        assert states["export"] == {"state": "unavailable", "reason": "incompatible"}
        assert states["provider.notion"]["state"] == "unavailable"
        report = composition.readiness()
        assert report["ready"] is False and "export" in report["missing"]
        app = host_app(composition)
        ready = await ask(app, "/health/ready")
        assert ready.status_code == 503
        assert ready.json()["contributions"]["approved-export"]["reason"] == "incompatible"
        live = await ask(app, "/health/live")
        assert live.status_code == 200
    finally:
        composition.close()


def test_a_missing_or_revised_contribution_and_its_dependents_are_unavailable(realm):
    builders = dict(BUILDERS)
    del builders["topics-digests"]
    builders["platform-control"] = ("u7-platform-control-2", BUILDERS["platform-control"][1])
    composition = compose(realm, builders=builders)
    try:
        reasons = {name: item.reason for name, item in composition.activations.items()}
        assert reasons["topics-digests"] == "missing"
        assert reasons["approved-export"] == "dependency-unavailable"
        assert reasons["platform-control"] == "incompatible"
        assert reasons["service-operations"] == "dependency-unavailable"
        # account-controls runs the composed realm's policy, bound since Step 17.
        assert reasons["account-controls"] is None
        assert reasons["research-workspace"] is None
        assert composition.capability_states()["operations.ledger"]["state"] == "unavailable"
    finally:
        composition.close()


# --- The roles ----------------------------------------------------------------------


def test_the_complete_worker_runs_both_halves_within_their_own_bounds():
    calls = []

    class Half:
        def __init__(self, name, fail=False):
            self.name, self.fail = name, fail

        def run_once(self, limit=1):
            calls.append((self.name, WORK_DEADLINE.get() - time.monotonic()))
            if self.fail:
                raise RuntimeError("private detail")
            return {self.name: limit}

    worker = CompleteWorker(Half("chained"), Half("lifecycle"), chained_seconds=2,
                            lifecycle_seconds=1)
    assert worker.run_once(limit=1) == {"chained": {"chained": 1}, "lifecycle": {"lifecycle": 1}}
    assert calls[0][1] <= 2 and calls[1][1] <= 1
    failing = CompleteWorker(Half("chained", fail=True), Half("lifecycle"))
    with pytest.raises(CompletePassIncomplete) as raised:
        failing.run_once()
    assert raised.value.halves == ("chained",) and calls[-1][0] == "lifecycle"
    token = WORK_DEADLINE.set(time.monotonic() + 0.5)
    try:
        with bounded(5):
            assert WORK_DEADLINE.get() - time.monotonic() <= 0.5
    finally:
        WORK_DEADLINE.reset(token)
    with pytest.raises(ValueError):
        CompleteWorker(Half("chained"), chained_seconds=0)


def test_the_workers_pass_and_the_scheduler_run_over_the_composition(realm, monkeypatch):
    from backend.modules.operations.incidents import ToleranceWatcher

    watched: list = []
    recorded = threading.Event()
    real_watch = ToleranceWatcher.run

    async def spied_watch(self, stopping, *args, **options):
        # A delegating spy: it records the seconds and runs the real watcher.
        watched.append(options.get("seconds", args[0] if args else None))
        recorded.set()
        return await real_watch(self, stopping, *args, **options)

    monkeypatch.setattr(ToleranceWatcher, "run", spied_watch)
    composition = compose(realm, process="workers")
    try:
        summary = composition.worker.run_once(limit=1)
        # Both halves run: the chained worker, and the lifecycle worker now that
        # account-controls runs the composed realm's policy (Step 17).
        assert set(summary) == {"chained", "lifecycle"}
        # D2's finished sign-in limit rows are removed with the housekeeping, and so are
        # provider sign-in flows a minute after they expire (Step 19).
        assert run_scheduler_once(composition) == {
            "topics": "done", "export-housekeeping": "done", "operations-housekeeping": "done",
            "entry-limits": "done", "identity-flows": "done",
        }

        async def briefly():
            stopping = asyncio.Event()
            task = asyncio.create_task(run_workers(composition, stopping))
            # `stopping` is set once the watcher has started (the spy recorded), never
            # after a fixed time.
            await signal_or_failure(set_flag(recorded), task, 30, "the watcher never started")
            stopping.set()
            await asyncio.wait_for(task, 30)

        # Called without `watch_seconds`, the watcher gets its 60 s (O3); setting
        # `stopping` ended both tasks.
        asyncio.run(briefly())
        assert watched == [60]
    finally:
        composition.close()


def production_manifest(parent: Path) -> Path:
    """A profile root outside /tmp owned by this user, not the service account."""
    root = parent / "profile"
    root.mkdir(mode=0o700)
    os.chmod(root, 0o700)
    write_private(root / "environment.json", b"{}")
    return root / "environment.json"


def test_the_entrypoint_selects_the_loader_and_port_by_the_manifests_place(realm, tmp_path):
    from backend import u8_main

    manifest = Path(os.environ["DOCSURI_U8_ENVIRONMENT_FILE"])
    assert u8_main.is_realm(manifest) and u8_main.listen_port(manifest) == 18109
    assert u8_main.loader(manifest)() == realm
    other = production_manifest(tmp_path)
    assert not u8_main.is_realm(other) and u8_main.listen_port(other) == 18200
    # The production loader checks the root against the service account (UID 610).
    with pytest.raises(ProfileRefused) as raised:
        u8_main.loader(other)()
    assert raised.value.check == "root-owner"


@pytest.mark.parametrize(
    "argv", [["host"], ["browser", "--profile", "/x"], ["workers", "--profile", "relative.json"]]
)
def test_the_entrypoint_refuses_a_role_or_profile_outside_its_form(argv):
    from backend import u8_main

    with pytest.raises(SystemExit) as raised:
        u8_main.main(argv)
    assert raised.value.code == 2


class WatchedStop(asyncio.Event):
    """`stopping` as `run_background` gets it, telling when the role waits on it again.

    `run_background` waits on `stopping` once beside its start; its next wait is the
    refused role's idle wait, or the scheduler's wait after its first pass over the
    composition. `waiting` is set at that second wait, so a test stops the role after
    that point, never after a fixed time."""

    def __init__(self) -> None:
        super().__init__()
        self.waits = 0
        self.waiting = asyncio.Event()

    async def wait(self) -> bool:
        self.waits += 1
        if self.waits >= 2:
            self.waiting.set()
        return await super().wait()


def test_a_refused_background_role_waits_idle_until_it_is_stopped(tmp_path):
    from backend import u8_main

    manifest = production_manifest(tmp_path)

    async def run():
        stopping = WatchedStop()
        task = asyncio.create_task(u8_main.run_background(manifest, "scheduler", stopping))
        await signal_or_failure(stopping.waiting.wait(), task, 30,
                                "the refused role never waited idle")
        assert not task.done()  # refused, but never exits on its own (R2)
        stopping.set()
        await asyncio.wait_for(task, 10)

    asyncio.run(run())


def test_a_background_role_runs_its_composition_until_it_is_stopped(realm):
    from backend import u8_main

    manifest = Path(os.environ["DOCSURI_U8_ENVIRONMENT_FILE"])

    async def run():
        stopping = WatchedStop()
        task = asyncio.create_task(u8_main.run_background(manifest, "scheduler", stopping))
        # The scheduler waits on `stopping` after its first pass over the composition.
        await signal_or_failure(stopping.waiting.wait(), task, 60,
                                "the scheduler never waited after its first pass")
        assert not task.done()
        stopping.set()
        await asyncio.wait_for(task, 60)

    asyncio.run(run())


# --- Step 12 gains (your decisions of 2026-10-24) ------------------------------------------


def failing_builders(calls: list | None = None) -> dict:
    """The real builders, with the paper corpus's raising an unexpected error whose
    message must never reach the log."""
    builders = dict(BUILDERS)
    revision, _ = builders["paper-corpus"]

    def broken(ctx):
        raise KeyError("private-detail-never-logged")

    builders["paper-corpus"] = (revision, broken)
    if calls is not None:
        for name, (rev, build) in list(builders.items()):
            builders[name] = (rev, lambda ctx, build=build, name=name: (
                calls.append(name), build(ctx))[1])
    return builders


async def test_an_unexpected_start_error_is_logged_by_its_type_and_the_role_exits(realm,
                                                                                caplog):
    from backend import u8_main
    from backend.log_events import EVENTS_LOGGER

    failures: list[str] = []
    caplog.set_level("INFO", logger=EVENTS_LOGGER)
    process = started(lambda: realm, builders=failing_builders(), on_failure=failures.append)
    assert process.startup.state == "failed" and failures == ["KeyError"]
    lines = [json.loads(record.getMessage()) for record in caplog.records
             if record.name == EVENTS_LOGGER]
    refused = [line for line in lines if line["event"] == "start.refused"]
    assert refused and refused[-1]["errorType"] == "KeyError"
    assert "private-detail-never-logged" not in caplog.text
    ready = await ask(process, "/health/ready")
    assert ready.status_code == 503 and ready.json()["missing"] == ["start"]
    # The background role returns status 1 at once (the exit, injected here as the
    # returned status `main` passes to `SystemExit`).
    manifest = Path(os.environ["DOCSURI_U8_ENVIRONMENT_FILE"])

    async def run():
        stopping = asyncio.Event()
        return await asyncio.wait_for(u8_main.run_background(
            manifest, "scheduler", stopping, options={"builders": failing_builders()}), 60)

    assert await run() == u8_main.FAILED_EXIT == 1


async def test_a_missing_verifier_key_with_accounts_is_refused_before_any_builder(
        realm, tmp_path, authority):
    calls: list[str] = []
    builders = {name: (revision, lambda ctx, build=build, name=name: (
        calls.append(name), build(ctx))[1]) for name, (revision, build) in BUILDERS.items()}
    profile = copy_root(realm, tmp_path)
    process = started(lambda: profile, builders=builders)
    await assert_serves_only_health(process, "key-folders")
    assert process.startup.detail == "verifier-key-missing-with-accounts"
    assert calls == []


KEY_WRITER = """
import dataclasses, json, sys, time
from pathlib import Path
from backend.local_profile import LocalProfile, verifier_key_path
from backend.modules.accounts.u8_verifier_key import _read_key
from backend.u8_host import cursor_key_path, start_keys
realm = LocalProfile.load(Path(sys.argv[1]))
profile = dataclasses.replace(realm, root=Path(sys.argv[2]))
go = Path(sys.argv[3])
Path(sys.argv[4]).write_text("polling")
while not go.exists():
    time.sleep(0.001)
start_keys(profile, occupied=False)
cursor = cursor_key_path(profile).read_bytes()
assert len(cursor) == 32
print(json.dumps({"verifier": _read_key(verifier_key_path(profile)).hex(),
                  "cursor": cursor.hex()}))
"""


def test_two_starts_together_keep_one_verifier_key_and_one_cursor_key(realm, tmp_path):
    import subprocess
    import sys

    root = tmp_path / "keys-root"
    root.mkdir(mode=0o700)
    (root / "verifier-key").mkdir(mode=0o700)
    (root / "cursor-key").mkdir(mode=0o700)  # the cursor key's own folder (L1-4)
    go = tmp_path / "go"
    manifest = os.environ["DOCSURI_U8_ENVIRONMENT_FILE"]
    environment = {**os.environ, "PYTHONPATH": str(ROOT)}
    polling = [tmp_path / f"polling-{index}" for index in range(2)]
    children = [subprocess.Popen([sys.executable, "-c", KEY_WRITER, manifest, str(root),
                                  str(go), str(mark)], cwd=ROOT, env=environment,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                for mark in polling]
    # `go` is written once both children say they are polling for it, never after a
    # fixed time.
    deadline = time.monotonic() + 60
    try:
        while not all(mark.exists() for mark in polling):
            exited = [f"{child.returncode}: {child.stderr.read().decode()}"
                      for child in children if child.poll() is not None]
            assert not exited, "a child exited before polling: " + "; ".join(exited)
            assert time.monotonic() < deadline, "the children never began polling"
            time.sleep(0.01)
    except BaseException:
        for child in children:  # a child still polling for `go` would never end
            child.kill()
            child.communicate()
        raise
    go.write_text("go")
    answers = []
    for child in children:
        out, err = child.communicate(timeout=60)
        assert child.returncode == 0, err.decode()
        answers.append(json.loads(out))
    assert answers[0] == answers[1]  # one key each, and neither read a partial one
    assert sorted(path.name for path in (root / "verifier-key").iterdir()) == [
        "account-verifier.key"]
    assert sorted(path.name for path in (root / "cursor-key").iterdir()) == [
        "search-cursor.key"]
    assert not (root / "search-cursor.key").exists()
    assert [path.name for path in root.iterdir() if path.name.startswith(".")] == []


def test_an_arranged_production_start_reads_nothing_under_library_docsuri(realm,
                                                                         monkeypatch):
    from backend.u8_host import worker_producers
    from docsuri_ops.arrangement import paths as arrangement_paths
    from docsuri_ops.u8_platform import platform_profile
    from tests.u8_service_operations_integration.host_flows import production_composition

    production_built: list[str] = []
    original = arrangement_paths.ArrangementPaths.__init__

    def recording(self, prefix=arrangement_paths.PREFIX, system=arrangement_paths.SYSTEM_ROOT):
        if Path(prefix) == arrangement_paths.PREFIX:
            production_built.append("ArrangementPaths()")
        original(self, prefix, system)

    production_profile = platform_profile.U8PlatformProfile.production.__func__

    def production(cls, actor="operator", *, control=platform_profile.U8_PRODUCTION_CONTROL):
        if control == platform_profile.U8_PRODUCTION_CONTROL:
            production_built.append("U8PlatformProfile.production()")
        return production_profile(cls, actor, control=control)

    monkeypatch.setattr(arrangement_paths.ArrangementPaths, "__init__", recording)
    monkeypatch.setattr(platform_profile.U8PlatformProfile, "production",
                        classmethod(production))
    with production_composition(realm) as env:
        composition = env.composition
        assert composition.arrangement is env.standin.arrangement
        host_app(composition)
        worker_producers(composition)
        from backend.u8_host import build_platform_control

        build_platform_control(type("Ctx", (), {"profile": composition.profile,
                                                "arrangement": composition.arrangement})())
        assert production_built == []


def test_the_entrypoint_never_passes_an_arrangement():
    import ast

    from backend import u8_main

    tree = ast.parse(Path(u8_main.__file__).read_text())
    keywords = {keyword.arg for node in ast.walk(tree) if isinstance(node, ast.Call)
                for keyword in node.keywords}
    assert "arrangement" not in keywords
    # A running role therefore gets `ArrangementPaths()` and the root-owned rule.
    from types import SimpleNamespace

    from backend.u8_host import arrangement_for, release_owner
    from docsuri_ops.arrangement.paths import ArrangementPaths

    chosen = arrangement_for(SimpleNamespace(is_production=True))
    assert chosen == ArrangementPaths() and release_owner(chosen) == 0
    assert arrangement_for(SimpleNamespace(is_production=False),
                           ArrangementPaths.under(Path("/x/prefix"))) is None


def test_the_stand_ins_database_copy_takes_only_a_rehearsal_name(realm):
    from docsuri_ops.migration.realm import RealmDatabases

    databases = RealmDatabases.for_realm(realm.root)
    for name in ("docsuri_u8", "docsuri_v2", "docsuri_u8_rehearsal_" + "a" * 12,
                 "docsuri_v2_import_" + "b" * 12):
        with pytest.raises(ValueError):
            databases.copy_composed_schema(name)


async def test_the_host_process_serves_the_composition_once_it_completes(realm, empty_outbox):
    process = HostProcess(Startup(lambda: realm, role="host"),
                          hosts=boundary_hosts(REALM_MANIFEST))
    inbox: asyncio.Queue = asyncio.Queue()
    sent = []

    async def send(message):
        sent.append(message["type"])

    await inbox.put({"type": "lifespan.startup"})
    lifespan = asyncio.create_task(process({"type": "lifespan"}, inbox.get, send))
    deadline = time.monotonic() + 60
    while process.app is None and time.monotonic() < deadline:
        await asyncio.sleep(0.1)
    try:
        assert process.app is not None and process.startup.state == "composed"
        live = await ask(process, "/health/live")
        assert live.status_code == 200 and live.json()["process"] == "alive"
        ready = await ask(process, "/health/ready")
        report = ready.json()
        # Derived from the realm's latest observations (Step 15): ready exactly when no
        # required capability is unavailable, unknown or stale.
        assert ready.status_code == (200 if report["ready"] else 503)
        assert set(report["missing"]) <= REQUIRED and "manifestRevision" in report
        # BR6.5: the development tree has no release identity, and no kind or path.
        assert report["release"] == {"tag": None, "commit": None}
        assert process.app.state.capacity_refresher.task is not None
    finally:
        await inbox.put({"type": "lifespan.shutdown"})
        await asyncio.wait_for(lifespan, 60)
    assert sent == ["lifespan.startup.complete", "lifespan.shutdown.complete"]


# --- Step 88(c): the listener and the host before its composition ----------------------------


def test_the_production_host_listens_only_on_127_0_0_1_18200(tmp_path, monkeypatch):
    from backend import u8_main

    recorded = []

    class Stub:
        def run(self):
            return None

    def recording(process, config):
        recorded.append(config)
        return Stub()

    monkeypatch.setattr(u8_main, "draining_server", recording)
    u8_main.run_host(production_manifest(tmp_path))
    u8_main.run_host(Path(os.environ["DOCSURI_U8_ENVIRONMENT_FILE"]))
    production, composed = recorded
    assert (production.host, production.port, production.proxy_headers, production.uds,
            production.fd) == ("127.0.0.1", 18200, False, None, None)
    assert composed.port == 18109


async def ask_host(process, path: str, host: str) -> httpx.Response:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=process),
                                 base_url="http://127.0.0.1") as http:
        return await http.get(path, headers={"host": host})


async def without_host(process) -> tuple[int, dict]:
    """One `GET /health/live` that carries no `Host` header at all."""
    sent = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    await process({"type": "http", "method": "GET", "path": "/health/live", "headers": [],
                   "query_string": b""}, receive, send)
    body = b"".join(message.get("body", b"") for message in sent[1:])
    return sent[0]["status"], json.loads(body)


def assert_fixed_headers(answer: httpx.Response) -> None:
    from backend.production_boundary import FIXED_HEADERS

    for name, value in FIXED_HEADERS:
        assert answer.headers.get_list(name.decode()) == [value.decode()], name


async def assert_answers_only_its_names(process) -> None:
    for host in ("docsuri.rvnnt.dev", "127.0.0.1", "127.0.0.1:18200"):
        live = await ask_host(process, "/health/live", host)
        assert live.status_code == 200, host
        assert_fixed_headers(live)
    for host in ("elsewhere.example", "localhost:18200", "127.0.0.1:18110"):
        refused = await ask_host(process, "/health/live", host)
        assert refused.status_code == 400, host
        assert refused.json()["messageKey"] == "request.host", host
        assert_fixed_headers(refused)
    status, body = await without_host(process)
    assert status == 400 and body["messageKey"] == "request.host"


async def test_a_host_before_its_composition_answers_only_its_accepted_names(realm, tmp_path):
    from backend import u8_main

    manifest = production_manifest(tmp_path)
    loading = threading.Event()

    def load():
        loading.wait(30)  # the start stays `starting` until the test lets it go on
        return u8_main.loader(manifest)()

    process = HostProcess(Startup(load, role="host"), hosts=u8_main.boundary_hosts(manifest))
    assert process.hosts.accepted == {"docsuri.rvnnt.dev", "127.0.0.1", "127.0.0.1:18200"}
    process.start()
    try:
        assert process.startup.state == "starting"
        await assert_answers_only_its_names(process)
    finally:
        loading.set()
        await asyncio.to_thread(process.thread.join, 30)
    # The production manifest under the test's folder is refused by the root-owner check.
    assert (process.startup.state, process.startup.check, process.startup.detail) == (
        "refused", "root", "root-owner")
    await assert_answers_only_its_names(process)
    # The composed realm's refused host still serves only its health routes.
    parent = tmp_path / "realm-copy"
    parent.mkdir()
    profile = copy_root(realm, parent, without=("owner-credentials.json",))
    refused = started(lambda: profile)
    await assert_serves_only_health(refused, "service-secrets")
    assert (await ask(refused, "/health/live", host="127.0.0.1:18200")).status_code == 400


# --- Step 88(d): the release identity (BR6.5) -------------------------------------------------


def test_readiness_evidence_records_the_running_release_tag_and_commit(realm):
    import re
    import subprocess

    from docsuri_ops.release import write_identity
    from tests.u8_service_operations_integration.host_flows import production_composition

    commit = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True,
                            check=True, timeout=30).stdout.decode().strip()
    assert re.fullmatch(r"[0-9a-f]{40}", commit)
    with production_composition(realm) as env:
        composition = env.composition
        assert composition.readiness()["release"] == {"tag": "v2.0.0", "commit": commit}
        ready = asyncio.run(ask(host_app(composition), "/health/ready", host="127.0.0.1:18200"))
        assert ready.json()["release"] == {"tag": "v2.0.0", "commit": commit}
        write_identity(env.standin.release_root, "v2.0.1", "d" * 40, owner_uid=os.getuid())
        assert composition.readiness()["release"] == {"tag": "v2.0.0", "commit": commit}
        second = compose(env.standin.profile, release_root=env.standin.release_root,
                         arrangement=env.standin.arrangement, builders={})
        try:
            assert second.readiness()["release"] == {"tag": "v2.0.1", "commit": "d" * 40}
        finally:
            second.close()


def test_a_production_start_needs_a_well_formed_release_identity(realm, tmp_path):
    from backend.u8_host import RELEASE_IDENTITY, StartRefused, release_identity
    from tests.u8_service_operations_integration.host_flows import (
        installer_manifest,
        production_root,
    )

    with production_root() as folder:
        root = folder / "profile"
        root.mkdir(mode=0o700)
        for name in KEY_FOLDERS:
            (root / name).mkdir(mode=0o700)
        write_private(root / "environment.json", json.dumps(
            installer_manifest("docsuri-v2-" + "c" * 16, uuid4())).encode())
        production = ProductionProfile.load(root / "environment.json", service_uid=os.getuid())
        release = tmp_path / "release"
        release.mkdir()
        with pytest.raises(StartRefused) as missing:
            release_identity(production, release)
        assert (missing.value.check, missing.value.detail) == (
            "release", "release-identity-missing")
        for payload in (json.dumps({"tag": "v2.0.0"}).encode(), b"\xff\xfe not json"):
            (release / RELEASE_IDENTITY).unlink(missing_ok=True)
            write_private(release / RELEASE_IDENTITY, payload)
            with pytest.raises(StartRefused) as malformed:
                release_identity(production, release)
            assert (malformed.value.check, malformed.value.detail) == (
                "release", "release-identity-malformed")
    assert release_identity(realm, tmp_path / "empty") == {"tag": None, "commit": None}


# --- Step 88(e): the key folders (L1-4) -------------------------------------------------------

KEY_NAMES = frozenset({
    "account-verifier.key", "search-cursor.key", "account-control-keyring.json",
    "account-control-keyring.lock", "account-control-keyring.initialized",
    "export-token-keyring.json", "export-token-keyring.lock",
    "export-token-keyring.initialized", "u8-keyring-snapshot",
})
STAGING_PREFIXES = (".account-verifier.key-", ".search-cursor.key-", ".control-key-",
                    ".export-key-", ".verifier-key-")


def is_key_name(name: str) -> bool:
    return name in KEY_NAMES or name.startswith(STAGING_PREFIXES)


def named_under(root: Path, depth: int = 2) -> list[Path]:
    """Every key or keyring name under `root`, at most `depth` folders down, never
    following a link."""
    found = []
    for path in root.iterdir():
        if is_key_name(path.name):
            found.append(path)
        if depth > 1 and path.is_dir() and not path.is_symlink():
            try:
                found += named_under(path, depth - 1)
            except PermissionError:
                continue
    return found


def listing(folder: Path) -> list[str]:
    return sorted(str(path.relative_to(folder)) for path in folder.rglob("*"))


def test_each_key_file_lives_in_its_own_folder(realm):
    controls = sorted(path.name for path in (realm.root / "control-keys").iterdir())
    composition = compose(realm)
    try:
        keyring = composition.parts["approved-export"]["service"].vault._keys
        assert keyring.root == realm.root / "export-keys"
    finally:
        composition.close()
    # The realm's start writes no control keyring and no snapshot: only
    # `control-key-start` does.
    assert sorted(path.name for path in (realm.root / "control-keys").iterdir()) == controls
    # Each key or keyring file's name prefix, with the folder it belongs in.
    folder_of = (("export-token-keyring", "export-keys"), ("account-control-keyring",
                                                           "control-keys"),
                 ("u8-keyring-snapshot", "control-keys"), ("account-verifier.key",
                                                           "verifier-key"),
                 ("search-cursor.key", "cursor-key"))
    for path in named_under(realm.root):
        assert path.parent != realm.root, path  # no key or keyring file under the root
        for prefix, folder in folder_of:
            if path.name.startswith(prefix):
                assert path.parent == realm.root / folder, path
    assert (realm.root / "verifier-key" / "account-verifier.key").is_file()
    assert (realm.root / "cursor-key" / "search-cursor.key").is_file()
    assert not any(is_key_name(path.name) for path in realm.root.iterdir())


def copy_key(realm, profile, folder: str, name: str) -> None:
    write_private(profile.root / folder / name, (realm.root / folder / name).read_bytes())


def test_no_start_recreates_a_missing_key_while_accounts_exist(realm, tmp_path, transactions):
    from backend.modules.export.errors import ProtectionUnavailable
    from backend.modules.export.repository import ExportRepository
    from backend.modules.export.token_keyring import MARKER_FILE, TokenKeyring
    from backend.u6_policy import SYNTHETIC_EXPORT
    from backend.u8_host import start_keys

    folder = tmp_path / "export-keys"
    folder.mkdir(mode=0o700)
    write_private(folder / MARKER_FILE, realm.run_id.encode())
    # As `u6_host.export_contribution` builds it: the run's id and U6's store as witness.
    keyring = TokenKeyring(folder, realm.run_id, ExportRepository(transactions, SYNTHETIC_EXPORT),
                           policy=SYNTHETIC_EXPORT)
    with pytest.raises(ProtectionUnavailable) as lost:
        keyring.load()
    assert lost.value.args[0] == "key-lost"
    assert [path.name for path in folder.iterdir()] == [MARKER_FILE]
    parent = tmp_path / "occupied"
    parent.mkdir()
    profile = copy_root(realm, parent)
    copy_key(realm, profile, "verifier-key", "account-verifier.key")
    copy_key(realm, profile, "cursor-key", "search-cursor.key")
    before = listing(profile.root)
    start_keys(profile, occupied=True)
    assert listing(profile.root) == before
    assert list((profile.root / "control-keys").iterdir()) == []


async def test_a_missing_cursor_key_with_accounts_is_refused(realm, tmp_path, authority):
    import stat as stat_module

    from backend.u8_host import start_keys

    calls: list[str] = []
    builders = {name: (revision, lambda ctx, build=build, name=name: (
        calls.append(name), build(ctx))[1]) for name, (revision, build) in BUILDERS.items()}
    first = tmp_path / "first"
    first.mkdir()
    profile = copy_root(realm, first)
    copy_key(realm, profile, "verifier-key", "account-verifier.key")
    keys_before = {name: listing(profile.root / name) for name in KEY_FOLDERS}
    process = started(lambda: profile, builders=builders)
    await assert_serves_only_health(process, "key-folders")
    assert process.startup.detail == "cursor-key-missing-with-accounts"
    assert calls == []
    assert {name: listing(profile.root / name) for name in KEY_FOLDERS} == keys_before
    second = tmp_path / "second"
    second.mkdir()
    only_verifier = copy_root(realm, second)
    copy_key(realm, only_verifier, "verifier-key", "account-verifier.key")
    start_keys(only_verifier, occupied=False)
    root = only_verifier.root
    assert listing(root / "cursor-key") == ["search-cursor.key"]
    cursor = root / "cursor-key" / "search-cursor.key"
    info = cursor.stat()
    assert info.st_size == 32 and stat_module.S_IMODE(info.st_mode) == 0o600
    assert listing(root / "verifier-key") == ["account-verifier.key"]
    assert sorted(path.name for path in root.iterdir() if path.is_file()) == [
        "owner-credentials.json"]


# --- Step 88(f): a missing or unfit backup volume never stops the start (NFR7.13) -------------


def pinned_capacity(composition):
    """The composition's `CapacityProducer` with this Mac's own inputs pinned: an available
    agent status with no findings, its volume identity the realm's expected None, and
    plentiful disk readings."""
    from backend.modules.operations.producers import CapacityProducer
    from backend.u8_host import worker_producers

    producers = [item for item in worker_producers(composition)
                 if isinstance(item, CapacityProducer)]
    assert len(producers) == 1
    capacity = producers[0]
    assert capacity.expected_volume is None
    capacity.agent_status = lambda: {"available": True, "volumeIdentity": None,
                                     "freeBytes": 10 ** 13, "catalogue": "intact"}
    capacity._free = lambda: 10 ** 13
    return capacity


def record_once(composition, producer) -> None:
    from backend.modules.operations.observation_store import ObservationStore
    from backend.modules.operations.observations import Observations
    from backend.modules.operations.producers import ProducerSchedule

    ProducerSchedule([producer], Observations(ObservationStore(composition.transactions)),
                     composition.policy, composition.clock).run_due()


def test_a_missing_or_unfit_backup_volume_never_stops_the_start(realm, monkeypatch):
    from backend import u8_host

    assert u8_host.BACKUP_STANDIN == "backup-volume"
    assert u8_host.backup_volume_state(realm) == "stand-in"
    normal = compose(realm)
    try:
        expected = {name: (item.activation, item.reason)
                    for name, item in normal.activations.items()}
    finally:
        normal.close()
    absent = "backup-volume-absent-" + uuid4().hex[:8]
    link = realm.root / ("backup-volume-link-" + uuid4().hex[:8])
    assert not (realm.root / absent).exists()
    try:
        for state, name in (("absent", absent), ("link", link.name)):
            if state == "link":
                os.symlink(realm.root / "backup-volume", link)
            monkeypatch.setattr(u8_host, "BACKUP_STANDIN", name)
            startup = Startup(lambda: realm, role="host")
            composition = startup.run()
            try:
                assert startup.state == "composed", (state, startup.check, startup.detail)
                assert {key: (item.activation, item.reason)
                        for key, item in composition.activations.items()} == expected
                assert composition.report["backupVolume"] == "unavailable"
                app = host_app(composition)
                app.state.control_capacity.refresh()
                assert asyncio.run(ask(app, "/health/live")).status_code == 200
                assert asyncio.run(ask(app, "/api/v2/capabilities",
                                       host="127.0.0.1:18110")).status_code == 200
                capacity = pinned_capacity(composition)
                observed = capacity.observe(composition.clock())
                assert (observed.outcome, observed.reason) == (
                    "degraded", "backup-volume-unavailable"), state
                record_once(composition, capacity)
                report = asyncio.run(ask(app, "/health/ready")).json()
                assert "storage.capacity" in report["degraded"], (state, report)
                assert "storage.capacity" not in report["missing"], (state, report)
                if state == "absent":
                    workers = compose(realm, process="workers")
                    workers.close()
                else:
                    monkeypatch.setattr(u8_host, "BACKUP_STANDIN", "backup-volume")
                    again = capacity.observe(composition.clock())
                    assert "backup-volume-unavailable" not in (again.reason,
                                                               *again.limitations), again
                    record_once(composition, capacity)
            finally:
                composition.close()
    finally:
        if link.is_symlink():
            link.unlink()
    assert (realm.root / "backup-volume").is_dir() and not (realm.root / absent).exists()


# --- Step 88(g): with the database gone (L1-28) -----------------------------------------------


ORIGIN ="https://127.0.0.1:18110"


def post_headers(csrf: str, address: str) -> dict:
    return {"origin": ORIGIN, "x-csrf-token": csrf, "idempotency-key": str(uuid4()),
            "cf-connecting-ip": address}


async def test_with_the_database_gone_reads_answer_retryably_and_ready_is_false(
        realm, connect, sign_in_account, own_address, empty_outbox, monkeypatch, caplog):
    from backend.log_events import EVENTS_LOGGER
    from backend.modules.accounts import u8_mail_outbox
    from backend.modules.accounts.local_http import ENTRY_POLICY
    from tests.u8_service_operations_integration.conftest import SIGN_IN_PASSWORD

    # The sender passes once as it starts and then only when woken, so no pass runs while
    # the database is gone and no failed `mail.sender` run reaches the realm's evidence.
    monkeypatch.setattr(u8_mail_outbox, "WAKE_SECONDS", 3600)
    caplog.set_level("INFO", logger=EVENTS_LOGGER)
    _, email = sign_in_account("sign-in-member")
    profile = dataclasses.replace(realm, database_port=RELAY_PORT)
    relay = Relay(realm.database_port)
    relay.open()
    process = HostProcess(Startup(lambda: profile, role="host"),
                          hosts=boundary_hosts(REALM_MANIFEST))
    try:
        await asyncio.to_thread(process.startup.run)
        assert process.startup.state == "composed"
        await process._serve_composition()
        app = process.app
        refresher, capacity = app.state.capacity_refresher, app.state.control_capacity
        deadline = time.monotonic() + 30
        while refresher.status["refreshes"] < 1 and time.monotonic() < deadline:
            await asyncio.sleep(0.05)
        assert refresher.status["refreshes"] >= 1 and capacity.admitting
        await refresher.close()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=process),
                                     base_url=ORIGIN) as client:
            csrf = (await client.get("/api/v2/session",
                                     headers={"cf-connecting-ip": own_address})).json()
            signed = await client.post("/api/v2/c02/access-login", json={
                "email": email, "password": SIGN_IN_PASSWORD, "policyRef": ENTRY_POLICY,
            }, headers=post_headers(csrf["csrfToken"], own_address))
            assert signed.status_code == 200, signed.text
            token = (await client.get("/api/v2/session",
                                      headers={"cf-connecting-ip": own_address})).json()
            relay.close()

            async def jobs():
                return await client.post("/api/v2/c07/list-research-jobs", json={"limit": 2},
                                         headers=post_headers(token["csrfToken"], own_address))

            before = await jobs()
            assert before.status_code == 503, before.text
            assert (before.json()["code"], before.json()["retryable"]) == (
                "DEPENDENCY_UNAVAILABLE", True)
            # The refresher's pass, run here as `CapacityRefresher.run` runs it: it fails
            # and closes admission, as production's refresher does within 2 s.
            with pytest.raises(Exception):  # noqa: B017 - whatever the lost database raises
                await asyncio.to_thread(capacity.refresh)
            assert not capacity.admitting
            closed = await jobs()
            assert closed.status_code == 503, closed.text
            assert (closed.json()["code"], closed.json()["messageKey"],
                    closed.json()["retryable"]) == ("NOT_READY", "capacity.exhausted", True)
            session = await client.get("/api/v2/session",
                                       headers={"cf-connecting-ip": own_address})
            assert session.status_code == 503, session.text
            assert (session.json()["code"], session.json()["retryable"]) == (
                "DEPENDENCY_UNAVAILABLE", True)
            ready = await client.get("/health/ready")
            assert ready.status_code == 503
            report = ready.json()
            assert (report["ready"], report["admission"]) == (False, "closed")
            assert report["missing"] == sorted(REQUIRED)
            assert (await client.get("/health/live")).status_code == 200
        states = process.startup.composition.capability_states()
        for capability in REQUIRED:
            assert states[capability] == {"state": "unknown", "reason": "store-unavailable"}, (
                capability, states[capability])
    finally:
        # Closed with the relay still closed: the sender stops and its beat stays behind.
        await process.close()
        relay.close()
        with connect("accounts") as conn:
            conn.execute("DELETE FROM accounts.mail_sender_beat")
    lines = [json.loads(record.getMessage()) for record in caplog.records
             if record.name == EVENTS_LOGGER]
    unremoved = [line for line in lines if line.get("event") == "mail.beat-unremoved"]
    assert len(unremoved) == 1 and unremoved[0]["component"] == "accounts"


# --- Step 88(h): the workers (P5, O3) -------------------------------------------------------


def test_the_workers_loop_passes_every_two_seconds_under_its_deadline(realm, monkeypatch):
    from backend import control_runtime

    composition = compose(realm, process="workers")
    try:
        loops: list = []
        waits: list = []
        spans: list = []
        outer: dict = {}
        real_loop = control_runtime.ControlLoop

        class RecordingLoop(real_loop):
            """The built loop, recorded."""

            def __init__(self, *args, **options):
                super().__init__(*args, **options)
                loops.append(self)

        class AsyncioProxy:
            """`backend.control_runtime`'s `asyncio` only: every name is asyncio's own but
            `wait_for`, which records each timeout, delegates the pass's own wait and
            answers the wait between passes with `TimeoutError` at once."""

            def __getattr__(self, name):
                return getattr(asyncio, name)

            async def wait_for(self, awaitable, timeout):
                loop = loops[-1]
                if timeout == loop.interval:
                    waits.append(("between", timeout, loop.status["passes"]))
                    awaitable.close()
                    if len([item for item in waits if item[0] == "between"]) == 2:
                        loop.stopping.set()
                        outer["stopping"].set()
                    raise TimeoutError
                waits.append(("pass", timeout, loop.status["passes"]))
                return await asyncio.wait_for(awaitable, timeout)

        worker = composition.worker
        real_run_once = worker.run_once
        running: list = []

        def spied_run_once(*args, **options):
            spans.append(("start", WORK_DEADLINE.get() - time.monotonic()))
            assert not running  # no pass starts while one runs
            running.append(True)
            try:
                return real_run_once(*args, **options)
            finally:
                running.pop()
                spans.append(("end",))

        monkeypatch.setattr(control_runtime, "ControlLoop", RecordingLoop)
        monkeypatch.setattr(control_runtime, "asyncio", AsyncioProxy())
        monkeypatch.setattr(worker, "run_once", spied_run_once)

        async def scenario():
            outer["stopping"] = asyncio.Event()
            await asyncio.wait_for(run_workers(composition, outer["stopping"]), 120)

        asyncio.run(scenario())
        assert len(loops) == 1
        assert (loops[0].interval, loops[0].deadline) == (2.0, 10.0)
        assert waits == [("pass", 10.0, 0), ("between", 2.0, 1),
                         ("pass", 10.0, 1), ("between", 2.0, 2)]
        assert [span[0] for span in spans] == ["start", "end", "start", "end"]
        for span in spans:
            if span[0] == "start":
                assert 0 < span[1] <= 10.0, span
        assert loops[0].status["state"] == "stopped"
    finally:
        composition.close()


# --- Step 88(j): the account-mail sender in the host (Step 53(h), L1-69, L1-70) ---------------


class IdleEvent(threading.Event):
    """The entry's `mail_waiting`, which sets `idle` each time the sender waits on it."""

    def __init__(self):
        super().__init__()
        self.idle = threading.Event()

    def wait(self, timeout=None):
        self.idle.set()
        return super().wait(timeout)


class HandedRecorder:
    """The test's own account mail: each message forwarded to a `LocalAccountMail` over a
    ledger of the test's own, then `handed` set; every other name is the inner's."""

    def __init__(self, inner):
        self.inner, self.messages, self.handed = inner, [], threading.Event()

    def deliver(self, message):
        self.messages.append(message)
        try:
            return self.inner.deliver(message)
        finally:
            self.handed.set()

    def __getattr__(self, name):
        return getattr(self.inner, name)


def beat_row(connect):
    with connect("accounts") as conn:
        return conn.execute("SELECT beat_at FROM accounts.mail_sender_beat").fetchone()


async def test_the_host_runs_the_account_mail_sender(
        realm, connect, sign_in_account, own_address, empty_outbox, monkeypatch, tmp_path):
    from backend.modules.accounts import u8_mail_outbox
    from backend.modules.accounts.entry_limits import client_address
    from backend.modules.accounts.integrations.account_mail import LocalAccountMail
    from backend.modules.operations.allowance import LedgerAllowance
    from backend.modules.operations.producers import BackgroundWorkProducer
    from backend.u8_counts import counts_over
    from backend.u8_host import worker_producers
    from backend.u8_policy import SYNTHETIC_OPERATIONS

    composition = compose(realm)
    try:
        entry = composition.parts["account-controls"]["entry"]
        sender = host_app(composition).state.account_mail_sender
        assert isinstance(sender, u8_mail_outbox.AccountMailSender) and sender.entry is entry
        assert sender._thread is None and beat_row(connect) is None
        background = [item for item in worker_producers(composition)
                      if isinstance(item, BackgroundWorkProducer)]
        assert len(background) == 1
        beat = background[0].sender_beat
        assert (beat.__module__, beat.__qualname__) == (u8_mail_outbox.__name__,
                                                        "beat_reader.<locals>.read")
        # L1-70: the recorder counts through the host's own `ProcessCounts`; the spy notes
        # the call and does not call through, so the realm's evidence gains no line.
        counts = composition.transactions._counts
        noted: list = []
        monkeypatch.setattr(counts, "record",
                            lambda kind, *, failed: noted.append((kind, failed)))
        sender.record_failure()
        monkeypatch.setattr(counts, "record", type(counts).record.__get__(counts))
        assert noted == [("mail.sender", True)]
        now = composition.clock()
        assert background[0].sender_counts(now) == counts_over(
            realm.root / "evidence", ("mail.sender",), now)["mail.sender"]
    finally:
        composition.close()
    alone = compose(realm, builders={key: value for key, value in BUILDERS.items()
                                     if key != "account-controls"})
    try:
        assert host_app(alone).state.account_mail_sender is None
    finally:
        alone.close()

    ledger_folder = tmp_path / "own-ledger"
    ledger_folder.mkdir(mode=0o700)
    own_ledger = Ledger.open(ledger_folder, clock=realm_clock)
    waiting = IdleEvent()
    recorders: list[HandedRecorder] = []

    def prepare(served):
        served_entry = served.parts["account-controls"]["entry"]
        recorder = HandedRecorder(LocalAccountMail(
            served_entry.mail, allowance=LedgerAllowance(own_ledger, SYNTHETIC_OPERATIONS)))
        served_entry.account_mail = recorder
        served_entry.mail_waiting = waiting
        recorders.append(recorder)

    monkeypatch.setattr(u8_mail_outbox, "WAKE_SECONDS", 3600)
    member, email = sign_in_account("sign-in-member")
    process = HostProcess(Startup(lambda: realm, role="host"),
                          hosts=boundary_hosts(REALM_MANIFEST), prepare=prepare)
    thread = None
    try:
        await asyncio.to_thread(process.startup.run)
        assert process.startup.state == "composed"
        await process._serve_composition()
        sender = process.app.state.account_mail_sender
        thread = sender._thread
        assert thread is not None and thread.is_alive()
        assert process.app.state.capacity_refresher.task is not None
        assert await asyncio.to_thread(waiting.idle.wait, 10)  # the first pass has run
        served_entry = process.startup.composition.parts["account-controls"]["entry"]

        def reset():
            with client_address(own_address):
                return served_entry.request_password_reset(uuid4(), email,
                                                           "flow-" + uuid4().hex)

        await asyncio.to_thread(reset)
        assert await asyncio.to_thread(recorders[0].handed.wait, 10)
        assert [message.purpose for message in recorders[0].messages] == ["password-reset"]
        assert beat_row(connect) is not None
    finally:
        await process.close()
        own_ledger.close()
        with connect("accounts") as conn:
            conn.execute(
                "UPDATE accounts.control_proof SET expires_at=clock_timestamp()-"
                "interval '1 minute' WHERE account_id=%s AND purpose='password-reset' "
                "AND consumed_at IS NULL", (member.account_id,))
    assert thread is not None and not thread.is_alive()
    assert process.app.state.account_mail_sender._thread is None
    assert beat_row(connect) is None
