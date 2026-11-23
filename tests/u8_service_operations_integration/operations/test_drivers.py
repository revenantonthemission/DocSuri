"""The two drivers (U8 plan Step 28; A6, BR7.1, BR10.2).

The realm driver refuses the production profile and the arrangement driver every
synthetic one. For the same operation both settle the same receipt (outcome, operation,
target, input hash, the effect record as the first reference) and give the same receipt
facts to the ledger: the shared path above the driver is one path.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import secrets
import subprocess
from pathlib import Path

import pytest

from docsuri_ops.platform_control.executor import EffectOutcome
from docsuri_ops.u8_platform import drivers
from docsuri_ops.u8_platform.drivers import DriverRefused, driver_for
from docsuri_ops.u8_platform.drivers.arrangement import ArrangementDriver
from docsuri_ops.u8_platform.drivers.realm import RealmDriver
from docsuri_ops.u8_platform.u8_protocols import readers_for
from tests.u8_service_operations_integration import platform_flows as pf

REALM_CONFIG = {"kind": "realm", "runRoot": "/tmp/x", "stateRoot": "/tmp/x/s",
                "runId": "docsuri-u8-0000000000000000"}


def noting_pid(path: Path):
    """A `preexec_fn` that writes the started program's process id to `path` before the
    program runs, with plain system calls only (it runs in the forked child)."""
    def note() -> None:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        os.write(descriptor, str(os.getpid()).encode())
        os.close(descriptor)
    return note


def assert_program_ended(pid_file: Path, record: Path) -> None:
    """The program `run_program` ended at its bound is gone, so it can write no late
    record: checked on its process, never by waiting out the time it would have taken."""
    with pytest.raises(ProcessLookupError):
        os.kill(int(pid_file.read_text()), 0)
    assert not record.exists()  # ended at the bound: no late record


def test_the_realm_driver_refuses_the_production_profile():
    with pytest.raises(DriverRefused, match="realm-driver-refuses-production"):
        RealmDriver({**REALM_CONFIG, "production": True})
    with pytest.raises(DriverRefused, match="realm-driver-refuses-production"):
        driver_for(REALM_CONFIG, production=True)
    with pytest.raises(DriverRefused, match="realm-driver-refuses-production"):
        RealmDriver({**REALM_CONFIG, "kind": "arrangement"})


def test_the_arrangement_driver_refuses_every_synthetic_profile():
    for config in ({"kind": "arrangement"}, {"kind": "arrangement", "production": False},
                   {"kind": "realm", "production": True}):
        with pytest.raises(DriverRefused, match="arrangement-driver-refuses-synthetic"):
            ArrangementDriver(config)
    with pytest.raises(DriverRefused, match="arrangement-driver-refuses-synthetic"):
        driver_for({"kind": "arrangement", "production": True}, production=False)


def test_an_unconfigured_effects_root_is_refused_before_any_effect(tmp_path):
    with pytest.raises(FileNotFoundError):
        drivers.load_config(tmp_path)
    (tmp_path / "driver.json").write_bytes(b'{"kind": "generic"}')
    with pytest.raises(DriverRefused, match="driver-unconfigured"):
        drivers.load_config(tmp_path)


def test_effect_files_are_written_only_through_the_effects_folders_descriptor(tmp_path):
    """Your answer of 2026-11-10 ("Fix both and sweep the rest"): the release command, run
    as root, writes effect inputs and records in your login's effects folder. A link in
    place of the target folder or of the effects root is refused with nothing written; a
    link or a second name at the input's name, holding the very payload that would be
    accepted, is refused and never read as the input; a second name left at the effect
    record's pending name is removed and never written."""
    import os

    root = tmp_path / "control" / "effects" / "operator"
    root.mkdir(parents=True)
    # The effect token, generated per run (L1-36).
    directory, token, value = root / "tunnel", secrets.token_hex(4), {"origin": "v2-host"}
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    directory.symlink_to(elsewhere)
    with pytest.raises(DriverRefused, match="^effects-folder-is-a-link$"):
        drivers.write_input(directory, token, value)
    with pytest.raises(DriverRefused, match="^effects-folder-is-a-link$"):
        drivers.write_caller(directory, token, "operator")
    directory.unlink()
    kept = tmp_path / "kept"
    root.rename(kept)
    root.symlink_to(elsewhere)
    with pytest.raises(DriverRefused, match="^effects-folder-is-a-link$"):
        drivers.write_input(directory, token, value)
    assert os.listdir(elsewhere) == []
    root.unlink()
    kept.rename(root)
    directory.mkdir(mode=0o700)
    other = tmp_path / "other"
    other.write_bytes(drivers.canonical(value))
    path = drivers.input_path(directory, token)
    for plant, reason in ((lambda: os.link(other, path), "effects-not-its-own-file"),
                          (lambda: path.symlink_to(other), "effects-file-is-a-link")):
        plant()
        with pytest.raises(DriverRefused, match=f"^{reason}$"):
            drivers.write_input(directory, token, value)
        path.unlink()
    assert drivers.write_input(directory, token, value) == path
    assert drivers.read_input(directory, token, drivers.input_hash(value)) == value
    assert drivers.write_input(directory, token, value) == path  # the same input again
    with pytest.raises(DriverRefused, match="^input-changed$"):
        drivers.write_input(directory, token, {"origin": "maintenance"})
    pending = directory / f"effect-{token}.json.pending"
    os.link(other, pending)
    before = (other.read_bytes(), other.stat().st_mode, other.stat().st_ino)
    reference = drivers._effect_record(directory, token, {
        "targetId": "tunnel", "inputHash": drivers.input_hash(value), "operationId": None,
        "operationName": "platform.tunnel.route"}, ["fact:wasLoaded=true"])
    assert reference == f"tunnel/effect-{token}.json"
    assert (other.read_bytes(), other.stat().st_mode, other.stat().st_ino) == before
    assert other.stat().st_nlink == 1 and not pending.exists()
    record = directory / f"effect-{token}.json"
    assert record.stat().st_ino != before[2]
    assert json.loads(record.read_bytes())["refs"] == ["fact:wasLoaded=true"]


def bounded(call, seconds: float = 10.0):
    """`call()` in a thread, waited on for at most `seconds`: answers ("answered", value),
    ("raised", error) or ("stalled", None). A stalled thread is a daemon blocked on a
    FIFO; the test opens the FIFO's other end to release it."""
    import threading

    outcome: list = []

    def run():
        try:
            outcome.append(("answered", call()))
        except BaseException as error:  # noqa: BLE001 - handed back to the test
            outcome.append(("raised", error))

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(seconds)
    return outcome[0] if outcome else ("stalled", None)


def release_fifo(path: Path) -> None:
    import os

    with contextlib.suppress(OSError):
        os.close(os.open(path, os.O_WRONLY | os.O_NONBLOCK))


def test_the_root_readers_refuse_a_fifo_a_second_name_or_a_link_at_once(tmp_path):
    """The review of the sweep (2026-11-10): the release command, run as root, reads
    `driver.json`, effect inputs and caller files from your login's effects folder. A FIFO
    at any of them answers at once with `effects-not-its-own-file` (it would otherwise
    stall root before any bound applies), and so does a second name of a file holding the
    very bytes that would be accepted; a link at the file or in place of the effects root
    is refused too. Nothing planted is changed, and with each plant gone the same read is
    accepted."""
    import os

    root = tmp_path / "control" / "effects" / "operator"
    # The effect token, generated per run (L1-36).
    directory, token, value = root / "tunnel", secrets.token_hex(4), {"origin": "v2-host"}
    directory.mkdir(parents=True)
    config = {"kind": "arrangement", "production": True}
    files = {
        root / "driver.json": (drivers.canonical(config), lambda: drivers.load_config(root),
                               config),
        drivers.input_path(directory, token): (
            drivers.canonical(value),
            lambda: drivers.read_input(directory, token, drivers.input_hash(value)), value),
        drivers.caller_path(directory, token): (
            drivers.canonical({"caller": "scheduler"}),
            lambda: drivers.read_caller(directory, token), "scheduler"),
    }
    for path, (payload, read, accepted) in files.items():
        other = tmp_path / f"other-{path.name}"
        other.write_bytes(payload)
        before = (other.read_bytes(), other.stat().st_mode, other.stat().st_ino)
        os.mkfifo(path)
        outcome = bounded(read)
        if outcome[0] == "stalled":
            release_fifo(path)
        assert outcome[0] == "raised", (path.name, outcome)
        assert isinstance(outcome[1], DriverRefused), (path.name, outcome)
        assert outcome[1].reason == "effects-not-its-own-file", path.name
        path.unlink()
        for plant, reason in (
            (lambda other=other, path=path: os.link(other, path), "effects-not-its-own-file"),
            (lambda other=other, path=path: path.symlink_to(other), "effects-file-is-a-link"),
        ):
            plant()
            with pytest.raises(DriverRefused, match=f"^{reason}$"):
                read()
            path.unlink()
        assert (other.read_bytes(), other.stat().st_mode, other.stat().st_ino) == before
        assert other.stat().st_nlink == 1
        path.write_bytes(payload)
        assert read() == accepted
    elsewhere = tmp_path / "elsewhere"
    (elsewhere / "tunnel").mkdir(parents=True)
    for path in files:
        (elsewhere / path.relative_to(root)).write_bytes(path.read_bytes())
    kept = tmp_path / "kept"
    root.rename(kept)
    root.symlink_to(elsewhere)
    for _path, (_payload, read, _accepted) in files.items():
        with pytest.raises(DriverRefused, match="^effects-folder-is-a-link$"):
            read()
    root.unlink()
    kept.rename(root)


class FakeSudo:
    """The fixed program answering through sudo: records each argv, answers ok."""

    def __init__(self):
        self.calls: list[list[str]] = []

    def __call__(self, argv, **options):
        self.calls.append(list(argv))
        return subprocess.CompletedProcess(argv, 0, stdout=b'{"ok": true}\n', stderr=b"")


def in_process(monkeypatch, sudo: FakeSudo):
    """U7's bounded child run in process, with the arrangement driver's sudo faked."""
    def make(config, *, production=None):
        return ArrangementDriver(config, run=sudo)

    monkeypatch.setattr(drivers, "driver_for", make)

    def run_effect(*, target_root: Path, operation_id, operation_name, target_id, token,
                   effect_kind, input_hash, **_):
        result = drivers.apply({"operationId": operation_id, "operationName": operation_name,
                                "targetId": target_id, "token": token,
                                "effectKind": effect_kind, "inputHash": input_hash,
                                "targetRoot": str(target_root)}, target_root / target_id)
        return EffectOutcome(result["status"], result["effectRefs"], result["error"])

    return run_effect


def _same(receipt: dict) -> dict:
    return {name: receipt[name] for name in ("outcome", "operation", "targetId", "inputHash")}


def test_both_drivers_settle_the_same_receipt_and_ledger_facts(tmp_path, realm, monkeypatch):
    inputs = {"origin": "v2-host"}
    realm_side = pf.journey(tmp_path / "realm", realm)
    realm_receipt = realm_side.operator().execute("platform.tunnel.route", "tunnel", inputs,
                                                  key=f"drivers-realm-{tmp_path.name}-{pf.RUN}")
    assert realm_side.tunnel()["origin"] == "v2-host"

    sudo = FakeSudo()
    arrangement_side = pf.journey(tmp_path / "arrangement", realm, kind="arrangement",
                                  production=True)
    operator = arrangement_side.operator(run_effect=in_process(monkeypatch, sudo))
    arrangement_receipt = operator.execute("platform.tunnel.route", "tunnel", inputs,
                                           key=f"drivers-arrangement-{tmp_path.name}-{pf.RUN}")
    # The arrangement ran exactly one fixed program in person, with one word.
    assert sudo.calls == [["/usr/bin/sudo", "-k", "-u", "root",
                           "/Library/DocSuri/release/ops/bin/docsuri-tunnel-route", "v2-host"]]

    assert _same(realm_receipt) == _same(arrangement_receipt) == {
        "outcome": "succeeded", "operation": "platform.tunnel.route", "targetId": "tunnel",
        "inputHash": drivers.input_hash(inputs)}
    for receipt in (realm_receipt, arrangement_receipt):
        assert receipt["effectRefs"][0].startswith("tunnel/effect-")
        assert receipt["effectRefs"][1:] == ["tunnel/v2-host"]

    # The ledger component confirms each through the service account's receipt reader,
    # with the operation's name, and both give the same facts.
    reader = readers_for(realm)[0]
    confirmed = [reader.read(receipt["operationId"])
                 for receipt in (realm_receipt, arrangement_receipt)]
    assert [_same(item) for item in confirmed] == [_same(realm_receipt)] * 2
    assert [item["receiptId"] for item in confirmed] == [
        realm_receipt["receiptId"], arrangement_receipt["receiptId"]]


# --- each effect, in process -------------------------------------------------------------
# U7's bounded child runs the drivers in a process of its own, which a coverage report
# cannot see; these cases run each effect of both drivers here, against the same state.


CONTEXT = {"operationId": "00000000-0000-4000-8000-000000000001", "targetId": "t",
           "token": secrets.token_hex(8)}  # sixteen hex digits, generated per run (L1-36)


@pytest.fixture
def realm_driver(tmp_path, realm):
    journey = pf.journey(tmp_path, realm)
    return journey, RealmDriver(journey.config)


def test_the_realm_driver_applies_and_observes_each_local_effect(realm_driver):
    journey, driver = realm_driver
    label = "dev.docsuri.u8.run.v1-web"
    assert driver.effect("service-control", {"label": label, "action": "stop"},
                         context=CONTEXT) == [f"service/{label}/stop", "fact:wasLoaded=true"]
    assert driver.observe("service-control", {"label": label, "action": "stop"})
    assert not driver.observe("service-control", {"label": label, "action": "start"})
    driver.effect("service-control", {"label": label, "action": "start"}, context=CONTEXT)
    assert journey.read_state("stops", f"{label}.json") is None
    assert driver.effect("tunnel-route", {"origin": "maintenance"}, context=CONTEXT) == [
        "tunnel/maintenance"]
    assert driver.observe("tunnel-route", {"origin": "maintenance"})
    assert driver.effect("isolation-check", {"via": "standing"}, context=CONTEXT) == [
        "isolation/standin"]
    assert driver.effect("profile-change", {"field": "admission", "value": "open"},
                         context=CONTEXT) == ["profile/admission"]
    assert driver.observe("profile-change", {"field": "admission", "value": "open"})
    assert journey.read_state("profile.json")["receiptOperationId"] == CONTEXT["operationId"]
    assert driver.effect("decision-record", dict(pf.DECISION_INPUTS), context=CONTEXT) == [
        f"decisions/{CONTEXT['operationId']}"]
    assert not driver.observe("decision-record", {})


def test_the_realm_driver_takes_a_label_never_set_as_loaded_for_a_start_too(realm_driver):
    """Review finding (Minor, R18): a label with no wanted-state file is running, for a
    start as for a stop (production's job runs at boot before any wanted state is
    written, and its fixed program answers `wasLoaded: true`); only a label set
    `stopped` counts as unloaded, so an interrupted `verify` never stops a role that
    ran before it began."""
    journey, driver = realm_driver
    label = "dev.docsuri.u8.run.workers"
    assert journey.read_state("services", f"{label}.json") is None
    assert driver.effect("service-control", {"label": label, "action": "start"},
                         context=CONTEXT) == [f"service/{label}/start", "fact:wasLoaded=true"]
    assert driver.effect("service-control", {"label": label, "action": "stop"},
                         context=CONTEXT) == [f"service/{label}/stop", "fact:wasLoaded=true"]
    assert driver.effect("service-control", {"label": label, "action": "stop"},
                         context=CONTEXT) == [f"service/{label}/stop", "fact:wasLoaded=false"]
    assert driver.effect("service-control", {"label": label, "action": "start"},
                         context=CONTEXT) == [f"service/{label}/start", "fact:wasLoaded=false"]


def test_the_realm_driver_refuses_inputs_outside_each_effects_form(realm_driver):
    _, driver = realm_driver
    cases = [
        ("service-control", {"label": "org.docsuri.v2.host", "action": "stop"}, "label-refused"),
        ("service-control", {"label": "dev.docsuri.u8.run.host", "action": "kill"},
         "label-refused"),
        ("tunnel-route", {"origin": "elsewhere"}, "origin-refused"),
        ("profile-change", {"field": "secret", "value": 1}, "profile-field-refused"),
        ("copy-dispose", {"place": "elsewhere", "location": "x"}, "place-refused"),
        # A production restore runs only in person (Step 29), and no other mode exists.
        ("database-restore", {"mode": "production", "via": "standing"}, "restore-mode-refused"),
        ("database-restore", {"mode": "elsewhere"}, "restore-mode-refused"),
        ("file-write", {}, "unsupported-effect-kind"),
    ]
    for kind, inputs, reason in cases:
        with pytest.raises(DriverRefused, match=reason):
            driver.effect(kind, inputs, context=CONTEXT)


def test_v1_lifecycle_apply_runs_v1s_runtime_from_its_checkout(tmp_path, realm):
    import sys

    journey = pf.journey(tmp_path, realm)
    # The realm's own configuration names v1's runtime once `v1-up` ran; without it:
    unconfigured = {key: value for key, value in journey.config.items()
                    if not key.startswith("v1")}
    with pytest.raises(DriverRefused, match="v1-runtime-unconfigured"):
        RealmDriver(unconfigured).effect("v1-lifecycle-apply", {"outcomes": [],
                                                               "accounts": []},
                                         context=CONTEXT)
    from tests.u8_service_operations_integration.v1_flows import (
        realm_environment,
        write_environment,
    )

    # The journey's own run root holds the checked v1 environment (never the realm's).
    environment = write_environment(tmp_path, realm_environment())
    v1 = {"v1EnvironmentRoot": str(tmp_path), "v1EnvironmentFile": str(environment),
          "v1Checkout": str(tmp_path)}
    seen = tmp_path / "seen"
    accepting = [sys.executable, "-c",
                 f"import sys; open({str(seen)!r}, 'wb').write(sys.stdin.buffer.read())"]
    driver = RealmDriver({**journey.config, **v1, "v1Runtime": accepting})
    inputs = {"outcomes": [{"v1AccountId": "a", "outcome": "erase"}], "accounts": ["a"]}
    assert driver.effect("v1-lifecycle-apply", inputs, context=CONTEXT) == ["v1/lifecycle"]
    assert json.loads(seen.read_bytes()) == inputs
    failing = RealmDriver({**journey.config, **v1, "v1Runtime": [sys.executable, "-c",
                                                                 "raise SystemExit(1)"]})
    with pytest.raises(DriverRefused, match="v1-lifecycle-refused"):
        failing.effect("v1-lifecycle-apply", inputs, context=CONTEXT)


def connect_grantees(admin, database: str) -> set[str]:
    with admin() as conn:
        return {row[0] for row in conn.execute(
            "SELECT coalesce(r.rolname,'PUBLIC') FROM pg_database d, aclexplode(d.datacl) a "
            "LEFT JOIN pg_roles r ON r.oid=a.grantee WHERE d.datname=%s "
            "AND a.privilege_type='CONNECT'", (database,)).fetchall()}


def test_the_realm_driver_drops_and_recreates_only_through_its_logins(realm_driver, realm,
                                                                       monkeypatch):
    """Step 98(d) (L1-56): on a production stand-in of its own, through the real `_connect`
    under a call-through spy. `copy-dispose` drops a scratch database owned by the
    disposable role through the realm's scheduler stand-in; `database-recreate` recreates
    the stand-in's own database through the realm's administrator login, never
    `docsuri_u8`."""
    from psycopg import sql

    from docsuri_ops.migration.realm import DISPOSABLE, RealmDatabases
    from tests.u8_service_operations_integration import host_flows

    _, driver = realm_driver
    databases = RealmDatabases.for_realm(realm.root)
    logins: list[tuple[str, str]] = []
    real_connect = driver._connect

    def recorded_connect(user, password, dbname="postgres"):
        logins.append((user, dbname))
        return real_connect(user, password, dbname)

    scratch = pf.NAMES.new("scratch")
    with host_flows.production_stand_in(realm) as standin:
        with databases.admin() as conn:
            conn.execute(sql.SQL("CREATE DATABASE {} OWNER {} TEMPLATE template1").format(
                sql.Identifier(scratch), sql.Identifier(DISPOSABLE)))
        try:
            before = connect_grantees(databases.admin, standin.database)
            monkeypatch.setattr(driver, "_connect", recorded_connect)
            assert driver.effect("copy-dispose", {"place": "database", "location": scratch},
                                 context=CONTEXT) == [f"database/{scratch}"]
            assert driver.effect("database-recreate", {"database": standin.database},
                                 context=CONTEXT) == [f"database/{standin.database}"]
            monkeypatch.undo()
            users = [user for user, _ in logins]
            assert users[0] == "docsuri_scheduler" and set(users[1:]) == {"postgres"}
            assert "docsuri_u8" not in {dbname for _, dbname in logins}
            with databases.admin() as conn:
                assert conn.execute("SELECT 1 FROM pg_database WHERE datname=%s",
                                    (scratch,)).fetchone() is None
            # The base kept in the journey's `recreate/` folder, read before the drop.
            base = journey_base(driver, standin.database)
            owners = {schema: owner for schema, owner in base["schemas"]}
            assert owners and all(owner == f"docsuri_{schema}_owner"
                                  for schema, owner in owners.items())
            assert base["identity"]["runId"] == standin.run_id
            # Afterwards: the empty schemas, the identity row and the CONNECT grants.
            after = connect_grantees(databases.admin, standin.database)
            assert before <= after and after - before <= {"postgres"}
            with databases.admin(standin.database) as conn:
                assert {row[0]: row[1] for row in conn.execute(
                    "SELECT nspname,pg_get_userbyid(nspowner) FROM pg_namespace WHERE "
                    "nspname = ANY(%s)", (list(owners),)).fetchall()} == owners
                assert conn.execute("SELECT count(*) FROM pg_class c JOIN pg_namespace n ON "
                                    "n.oid=c.relnamespace WHERE n.nspname = ANY(%s)",
                                    (list(owners),)).fetchone()[0] == 0
                assert conn.execute("SELECT run_id FROM public.docsuri_local_identity"
                                    ).fetchone()[0] == standin.run_id
        finally:
            with databases.admin() as conn:
                conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                    sql.Identifier(scratch)))


def journey_base(driver, database):
    return json.loads(driver._base_path(database).read_bytes())


def test_the_realm_driver_refuses_another_realms_credentials(realm_driver, tmp_path):
    journey, driver = realm_driver
    other = RealmDriver({**journey.config, "runId": "docsuri-u8-ffffffffffffffff"})
    with pytest.raises(DriverRefused, match="realm-credential-mismatch"):
        other._password("standin-credentials.json", "scheduler")
    unconfigured = RealmDriver({k: v for k, v in journey.config.items() if k != "repository"})
    with pytest.raises(DriverRefused, match="realm-repository-unconfigured"):
        unconfigured.effect("database-backup", {"database": "docsuri_u8", "recordId": "r",
                                                "via": "standing"}, context=CONTEXT)


def test_the_realm_driver_reports_an_agent_refusal_by_its_reason(realm_driver):
    journey, _ = realm_driver
    driver = RealmDriver({**journey.config, "agentFolder": str(journey.root / "nowhere")})
    with pytest.raises(DriverRefused) as caught:
        driver.effect("database-restore", {"mode": "scratch", "via": "standing",
                                           "scratchDatabase": pf.NAMES.new("scratch"),
                                           "setKind": "live-set"}, context=CONTEXT)
    assert caught.value.reason in ("realm-entry-refused", "agent-config-refused")


ARRANGEMENT = {"kind": "arrangement", "production": True}


RELEASED = secrets.token_hex(20)  # forty characters, generated per run (L1-36)


def released(login: str) -> bytearray:
    """The in-person credential release (D5), stood in for."""
    return bytearray(RELEASED.encode())


def test_the_arrangement_driver_runs_one_fixed_program_per_effect():
    sudo = FakeSudo()
    driver = ArrangementDriver(ARRANGEMENT, run=sudo, release=released)
    bin_ = "/Library/DocSuri/release/ops/bin/"
    scratch = pf.NAMES.new("scratch")
    cases = [
        ("database-backup", {"database": "docsuri_v2", "recordId": "r", "via": "standing"},
         ["-n", "-u", "_docsuri_r1t_backup", bin_ + "docsuri-backup-agent", "backup"]),
        ("database-restore", {"mode": "scratch", "scratchDatabase": scratch,
                              "setKind": "live-set", "via": "standing"},
         ["-n", "-u", "_docsuri_r1t_backup", bin_ + "docsuri-backup-agent", "verify"]),
        ("database-recreate", {"database": "docsuri_v2"},
         ["-k", "-u", "_docsuri_v2", bin_ + "docsuri-production-tool", "recreate-database"]),
        ("database-remove", {"database": scratch, "via": "in-person"},
         ["-k", "-u", "_docsuri_v2", bin_ + "docsuri-production-tool", "remove-database"]),
        ("service-control", {"label": "org.docsuri.v2.host", "action": "stop"},
         ["-k", "-u", "root", bin_ + "docsuri-service-stop", "org.docsuri.v2.host"]),
        ("service-control", {"label": "org.docsuri.v2.host", "action": "start"},
         ["-k", "-u", "root", bin_ + "docsuri-service-start", "org.docsuri.v2.host"]),
        ("isolation-check", {"via": "standing"},
         ["-n", "-u", "root", bin_ + "docsuri-isolation-check"]),
        ("profile-change", {"field": "mode", "value": "live"},
         ["-k", "-u", "_docsuri_v2", bin_ + "docsuri-profile", "mode"]),
        ("copy-dispose", {"place": "backup-volume", "location": "x", "event": "e"},
         ["-k", "-u", "_docsuri_r1t_backup", bin_ + "docsuri-backup-agent", "dispose-event"]),
        ("copy-dispose", {"place": "database", "location": scratch},
         ["-k", "-u", "_docsuri_v2", bin_ + "docsuri-production-tool", "remove-database"]),
    ]
    sudo_answers = {"backup": b'{"ok": true, "location": "archives/a"}\n',
                    "verify": f'{{"ok": true, "scratchDatabase": "{scratch}"}}\n'.encode()}
    for kind, inputs, argv in cases:
        sudo.calls.clear()
        word = argv[-1]

        def answer(call_argv, _word=word, **options):
            sudo.calls.append(list(call_argv))
            return subprocess.CompletedProcess(call_argv, 0, stdout=sudo_answers.get(
                _word, b'{"ok": true}\n'), stderr=b"")

        driver._run = answer
        assert driver.effect(kind, inputs, context=CONTEXT)
        assert sudo.calls == [["/usr/bin/sudo", *argv]], kind
    assert driver.effect("decision-record", {}, context=CONTEXT) == [
        f"decisions/{CONTEXT['operationId']}"]
    assert driver.observe("tunnel-route", {"origin": "v2-host"}) is False


def test_a_fixed_program_is_ended_at_a_bound_below_its_protocols_deadline(tmp_path):
    """Review finding (Minor, R16): each fixed program runs under a bound below its
    protocol's deadline (`program_bound`), and `run_program` ends the program itself at
    that bound, so a late answer never arrives: a program that would write its record
    after the bound writes nothing, and the effect is refused `program-timed-out`."""
    import sys

    from docsuri_ops.u8_platform.drivers.arrangement import (
        PROGRAM_SECONDS,
        program_bound,
        run_program,
    )

    assert program_bound("service-control") == 115.0  # the 120 s deadline, less 5 s
    assert program_bound("profile-change") == 25.0  # the 30 s deadline, less 5 s
    assert program_bound("tunnel-route") == 55.0
    assert program_bound("database-backup") == 1795.0 and program_bound("database-restore") < 2700
    assert program_bound("no-such-kind") == PROGRAM_SECONDS
    record = tmp_path / "stop-record.json"
    script = ("import sys, time, pathlib\n"
              "sys.stdin.buffer.read()\n"
              "time.sleep(2)\n"
              f"pathlib.Path({str(record)!r}).write_text('late')\n"
              "print('{\"ok\": true}')\n")
    pid_file = tmp_path / "stop-program.pid"
    with pytest.raises(subprocess.TimeoutExpired):
        run_program([sys.executable, "-c", script], input=b"{}", capture_output=True,
                    timeout=0.3, preexec_fn=noting_pid(pid_file))
    assert_program_ended(pid_file, record)
    # Within the bound, the program answers as `subprocess.run` would.
    quick = run_program([sys.executable, "-c", "import sys; sys.stdin.buffer.read(); "
                         "print('{\"ok\": true}')"], input=b"{}", capture_output=True,
                        timeout=10)
    assert quick.returncode == 0 and quick.stdout.strip() == b'{"ok": true}'
    # The driver refuses the effect, and its receipt then settles not applied.
    def late(argv, **options):
        raise subprocess.TimeoutExpired(argv, options["timeout"])

    driver = ArrangementDriver(ARRANGEMENT, run=late)
    with pytest.raises(DriverRefused, match="program-timed-out"):
        driver.effect("service-control", {"label": "org.docsuri.v2.host", "action": "stop"},
                      context=CONTEXT)
    assert driver._bound == PROGRAM_SECONDS  # the bound is the effect's alone


def test_the_tools_words_and_the_streamed_set_run_under_the_effects_bound(tmp_path):
    """Review finding (Major, R21): the production environment tool's words, the agent's
    `stream-back` and v1's lifecycle apply ran under `invoke`'s 3300 s or a 3600 s
    timeout, above their protocols' deadlines. Each now runs under what is left of the
    effect's bound, counted from the effect's start, so the two programs of a production
    restore share one bound, and a `recreate-database` still running at the bound is
    ended with no late record."""
    import hashlib
    import sys

    from docsuri_ops.u8_platform.drivers.arrangement import (
        PROGRAM_SECONDS,
        program_bound,
        run_program,
    )

    seen = []

    def recording(argv, **options):
        seen.append((argv[-1], options["timeout"]))
        return subprocess.CompletedProcess(argv, 0, stdout=b'{"ok": true}\n', stderr=b"")

    driver = ArrangementDriver(ARRANGEMENT, run=recording, release=released)
    driver.effect("database-recreate", {"database": "docsuri_v2"}, context=CONTEXT)
    ((word, timeout),) = seen
    assert word == "recreate-database"
    assert 0 < timeout <= program_bound("database-recreate") == 295.0
    seen.clear()
    driver.effect("database-remove", {"database": "docsuri_v2", "via": "in-person"},
                  context=CONTEXT)
    assert seen[0][0] == "remove-database" and seen[0][1] <= program_bound("database-remove")
    seen.clear()
    applying = ArrangementDriver({**ARRANGEMENT, "v1Runtime": [sys.executable],
                                  "v1Checkout": str(tmp_path)}, run=recording)
    applying.effect("v1-lifecycle-apply", {"outcomes": [], "accounts": []}, context=CONTEXT)
    assert seen[0][1] <= program_bound("v1-lifecycle-apply") == 595.0
    # A production restore: the stream-back took 1,000 s of the bound, and the restore
    # gets what is left.
    seen.clear()
    clock = {"now": 100.0}
    digest = hashlib.sha256(b"set").hexdigest()

    def streaming(argv, **options):
        seen.append((argv[-1], options["timeout"]))
        if argv[-1] == "stream-back":
            clock["now"] += 1000.0
            return subprocess.CompletedProcess(argv, 0, stdout=b"set",
                                               stderr=b'{"ok": true}\n')
        return subprocess.CompletedProcess(argv, 0, stdout=b'{"ok": true}\n', stderr=b"")

    restoring = ArrangementDriver(ARRANGEMENT, run=streaming, release=released)
    restoring._monotonic = lambda: clock["now"]
    restoring.effect("database-restore", {"mode": "production", "via": "in-person",
                                          "database": "docsuri_v2", "setPath": "archives/a",
                                          "setSha256": digest}, context=CONTEXT)
    bound = program_bound("database-restore")
    assert [word for word, _ in seen] == ["stream-back", "restore-database"]
    assert seen[0][1] == pytest.approx(bound) and seen[1][1] == pytest.approx(bound - 1000.0)
    # Outside an effect the whole program bound applies.
    assert restoring._deadline is None and restoring._remaining() == PROGRAM_SECONDS
    # A late recreate is ended at the bound: the program would write its record after
    # it, and writes nothing.
    record = tmp_path / "recreated"
    script = ("import sys, time, pathlib\n"
              "sys.stdin.buffer.read()\n"
              "time.sleep(2)\n"
              f"pathlib.Path({str(record)!r}).write_text('late')\n"
              "print('{\"ok\": true}')\n")

    pid_file = tmp_path / "recreate-program.pid"

    def late(argv, **options):
        return run_program([sys.executable, "-c", script], preexec_fn=noting_pid(pid_file),
                           **options)

    ticks = iter([0.0] + [program_bound("database-recreate") - 0.3] * 8)
    ending = ArrangementDriver(ARRANGEMENT, run=late, release=released)
    ending._monotonic = lambda: next(ticks)
    with pytest.raises(DriverRefused, match="program-timed-out"):
        ending.effect("database-recreate", {"database": "docsuri_v2"}, context=CONTEXT)
    assert_program_ended(pid_file, record)


def test_a_root_driver_reads_your_login_only_from_a_root_owned_file(tmp_path):
    """Review finding (Minor, R17): the authority identities a root driver takes your
    login from must be a root-owned regular file writable by its owner only; a file
    owned by anyone else, or writable by others, is refused, and a missing one answers
    nothing."""
    from docsuri_ops.u8_platform.drivers.arrangement import read_root_authorities

    assert read_root_authorities(tmp_path / "absent.json") is None
    mine = tmp_path / "platform-authorities.json"
    mine.write_text(json.dumps({"actors": {"operator": "maintainer"}}))
    mine.chmod(0o644)
    with pytest.raises(DriverRefused, match="authorities-file-refused"):
        read_root_authorities(mine)  # owned by this test's user, not root
    link = tmp_path / "link.json"
    link.symlink_to(mine)
    with pytest.raises(DriverRefused, match="authorities-file-refused"):
        read_root_authorities(link)


def test_the_arrangement_driver_refuses_a_program_that_refused_or_answered_nothing():
    driver = ArrangementDriver(ARRANGEMENT, run=lambda argv, **o: subprocess.CompletedProcess(
        argv, 1, stdout=b'{"ok": false, "reason": "label-refused"}\n', stderr=b""))
    with pytest.raises(DriverRefused, match="label-refused"):
        driver.effect("tunnel-route", {"origin": "v2-host"}, context=CONTEXT)
    silent = ArrangementDriver(ARRANGEMENT, run=lambda argv, **o: subprocess.CompletedProcess(
        argv, 0, stdout=b"", stderr=b""))
    with pytest.raises(ValueError):
        silent.effect("tunnel-route", {"origin": "v2-host"}, context=CONTEXT)
    with pytest.raises(DriverRefused, match="authority-refused"):
        silent.command("root", "docsuri-logs", "filter", via="anyone")
    for kind, inputs, reason in (
        ("database-restore", {"mode": "production", "via": "standing"}, "restore-mode-refused"),
        ("copy-dispose", {"place": "elsewhere"}, "place-refused"),
        ("v1-lifecycle-apply", {"outcomes": [], "accounts": []}, "v1-runtime-unconfigured"),
        ("file-probe", {}, "unsupported-effect-kind"),
    ):
        with pytest.raises(DriverRefused, match=reason):
            silent.effect(kind, inputs, context=CONTEXT)


def test_the_arrangement_driver_restores_and_backs_up_through_its_fixed_programs():
    """Step 29: the agent's receipt travels beside the set as `fact:` references; a
    production restore and an abandonment's recreate go to the production environment
    tool in person; the operator tool's own agent words never take a byte word."""
    answers = {
        "backup": {"ok": True, "location": "archives/live-set-1.archive", "recordId": "r",
                   "sha256": "a" * 64, "size": 10, "integrity": "passed",
                   "disposeAfter": "2026-11-05T12:00:00+00:00",
                   "stagingLocation": "staging/live-set-1", "incarnation": "docsuri_v2:1",
                   "databaseBytes": 99},
        "verify": {"ok": True, "scratchDatabase": "docsuri_v2_scratch_000000000000",
                   "setRecordId": "r", "setSha256": "a" * 64, "setPath": "archives/x"},
    }
    calls = []
    archive = b"PGDMP" + bytes(range(64))
    digest = hashlib.sha256(archive).hexdigest()

    def run(argv, **options):
        header, _, payload = options["input"].partition(b"\n")
        calls.append((list(argv), json.loads(header), payload))
        word = argv[-1]
        if word == "stream-back":  # the set's bytes on standard output (BR4.3)
            return subprocess.CompletedProcess(argv, 0, stdout=archive, stderr=b'{"ok":true}')
        return subprocess.CompletedProcess(
            argv, 0, stdout=json.dumps(answers.get(word, {"ok": True})).encode() + b"\n",
            stderr=b"")

    driver = ArrangementDriver(ARRANGEMENT, run=run, release=released)
    refs = driver.effect("database-backup", {"database": "docsuri_v2", "recordId": "r",
                                             "via": "standing"}, context=CONTEXT)
    assert refs[0] == "backup-volume/archives/live-set-1.archive"
    assert drivers.parse_facts(refs) == {
        "recordId": "r", "sha256": "a" * 64, "size": "10", "integrity": "passed",
        "disposeAfter": "2026-11-05T12:00:00+00:00", "stagingLocation": "staging/live-set-1",
        "incarnation": "docsuri_v2:1", "databaseBytes": "99"}
    verified = driver.effect("database-restore", {
        "mode": "scratch", "scratchDatabase": "docsuri_v2_scratch_000000000000",
        "setKind": "live-set", "via": "standing", "recordId": "r"}, context=CONTEXT)
    assert drivers.parse_facts(verified)["setRecordId"] == "r"
    assert calls[-1][1]["recordId"] == "r"
    restored = driver.effect("database-restore", {
        "mode": "production", "database": "docsuri_v2", "setPath": "archives/x",
        "setSha256": digest, "via": "in-person", "recoveryRequestId": "q"}, context=CONTEXT)
    assert restored[0] == "database/docsuri_v2"
    streamed, tool_call = calls[-2], calls[-1]
    assert streamed[0][1:5] == ["-k", "-u", "_docsuri_r1t_backup",
                                "/Library/DocSuri/release/ops/bin/docsuri-backup-agent"]
    argv, document, payload = tool_call
    assert argv[:2] == ["/usr/bin/sudo", "-k"] and argv[-2:] == [
        "/Library/DocSuri/release/ops/bin/docsuri-production-tool", "restore-database"]
    assert document["setSha256"] == digest and payload == archive
    assert document["login"] == {"password": RELEASED}  # released in person, on stdin only
    assert RELEASED not in " ".join(argv)
    with pytest.raises(DriverRefused, match="streamed-set-digest-mismatch"):
        driver.effect("database-restore", {
            "mode": "production", "database": "docsuri_v2", "setPath": "archives/x",
            "setSha256": "0" * 64, "via": "in-person"}, context=CONTEXT)
    driver.effect("database-recreate", {"database": "docsuri_v2", "abandonment": True},
                  context=CONTEXT)
    assert calls[-1][1]["abandonment"] is True
    assert driver.agent_word("status", {}, via="in-person") == {"ok": True}
    with pytest.raises(DriverRefused, match="byte-word-refused"):
        driver.agent_word("stream-back", {}, via="in-person")


def test_the_arrangement_driver_takes_a_lone_ledger_copy_one_program_after_the_other():
    """L1-5, Step 64(c): the ledger component's `copy` as the service account, then the
    agent's `ledger-copy`, the first's standard output the second's input, each answering
    on standard error; `sudo -n` standing and `sudo -k` in person."""
    from docsuri_ops.u8_platform.drivers.arrangement import program_bound

    stream = b"LEDGER-BYTES" * 8
    agent = {"ok": True, "location": "ledger/copy-1.archive", "recordId": "lc-1",
             "sha256": "c" * 64, "size": len(stream), "integrity": "passed",
             "disposeAfter": "2026-11-24T04:00:00+00:00", "stagingLocation": "staging/copy-1",
             "stagingRemovedAt": "2026-11-10T04:00:01+00:00"}
    calls = []
    refuse = {"agent": False}

    def run(argv, **options):
        calls.append((list(argv), options["input"]))
        if argv[-1] == "copy":
            head = {"ok": True, "count": 41, "head": "d" * 64, "sha256": "e" * 64}
            return subprocess.CompletedProcess(argv, 0, stdout=stream,
                                               stderr=json.dumps(head).encode() + b"\n")
        answer = {"ok": False, "reason": "volume-check-failed"} if refuse["agent"] else agent
        return subprocess.CompletedProcess(argv, 1 if refuse["agent"] else 0, stdout=b"",
                                           stderr=json.dumps(answer).encode() + b"\n")

    driver = ArrangementDriver(ARRANGEMENT, run=run)
    bin_dir = "/Library/DocSuri/release/ops/bin"
    for via, flag in (("standing", "-n"), ("in-person", "-k")):
        calls.clear()
        refs = driver.effect("ledger-copy", {"via": via, "environment": "live"},
                             context=CONTEXT)
        assert [argv for argv, _ in calls] == [
            ["/usr/bin/sudo", flag, "-u", "_docsuri_v2", f"{bin_dir}/docsuri-ledger", "copy"],
            ["/usr/bin/sudo", flag, "-u", "_docsuri_r1t_backup",
             f"{bin_dir}/docsuri-backup-agent", "ledger-copy"]]
        assert calls[1][1] == stream  # the first's output, in memory, as the second's input
        assert refs[0] == "backup-volume/ledger/copy-1.archive"
        facts = drivers.parse_facts(refs)
        assert (facts["headSequence"], facts["headDigest"]) == ("41", "d" * 64)
        assert facts["recordId"] == "lc-1" and facts["integrity"] == "passed"
    assert program_bound("ledger-copy") == 595.0
    refuse["agent"] = True
    with pytest.raises(DriverRefused, match="volume-check-failed"):
        driver.effect("ledger-copy", {"via": "standing", "environment": "live"},
                      context=CONTEXT)


def test_the_standing_removal_drops_through_the_schedulers_own_login(tmp_path, realm,
                                                                     monkeypatch):
    """BR9.17: unattended, through the scheduler account's database login (a member of
    the disposable-databases role only), read from its private credentials file; no sudo.
    Step 98(d) (L1-56): a `docsuri_v2_scratch_<12 hex>` database in the realm's instance,
    owned by the disposable role, dropped through the realm's scheduler stand-in by the
    driver's default `psycopg.connect`, under a call-through spy."""
    import os

    import psycopg
    from psycopg import sql

    from docsuri_ops.migration.realm import DISPOSABLE, RealmDatabases
    from docsuri_ops.platform_control.profile import private_bytes

    databases = RealmDatabases.for_realm(realm.root)
    stand_ins = json.loads(private_bytes(Path(realm.root) / "standin-credentials.json"))
    password = stand_ins.get("roles", {}).get("scheduler", stand_ins.get("scheduler"))
    credentials = tmp_path / "credentials.json"
    descriptor = os.open(credentials, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write(json.dumps({"database": {"user": "docsuri_scheduler",
                                              "password": password}}))
    opened = []
    real_connect = psycopg.connect

    def recorded_connect(*args, **options):
        opened.append({key: value for key, value in options.items() if key != "password"})
        return real_connect(*args, **options)

    sudo = FakeSudo()
    config = {**ARRANGEMENT, "schedulerCredentials": str(credentials),
              "databasePort": realm.database_port}
    driver = ArrangementDriver(config, run=sudo)
    scratch = "docsuri_v2_scratch_" + secrets.token_hex(6)
    with databases.admin() as conn:
        conn.execute(sql.SQL("CREATE DATABASE {} OWNER {} TEMPLATE template1").format(
            sql.Identifier(scratch), sql.Identifier(DISPOSABLE)))
    try:
        monkeypatch.setattr(psycopg, "connect", recorded_connect)
        assert driver.effect("database-remove", {"database": scratch, "via": "standing"},
                             context=CONTEXT) == [f"database/{scratch}"]
        monkeypatch.undo()
        assert sudo.calls == [] and len(opened) == 1
        assert (opened[0]["user"], opened[0]["require_auth"], opened[0]["dbname"]) == (
            "docsuri_scheduler", "scram-sha-256", "postgres")
        with databases.admin() as conn:
            assert conn.execute("SELECT 1 FROM pg_database WHERE datname=%s",
                                (scratch,)).fetchone() is None
    finally:
        monkeypatch.undo()
        with databases.admin() as conn:
            conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                sql.Identifier(scratch)))
    for name in ("docsuri_v2", "docsuri_v2_platform"):
        with pytest.raises(DriverRefused, match="database-refused"):
            driver.effect("database-remove", {"database": name, "via": "standing"},
                          context=CONTEXT)
    missing = ArrangementDriver({**config, "schedulerCredentials": str(tmp_path / "x")},
                                run=sudo)
    with pytest.raises(DriverRefused, match="scheduler-credentials-unavailable"):
        missing.effect("database-remove", {"database": scratch, "via": "standing"},
                       context=CONTEXT)


def test_the_arrangement_driver_checks_v1s_stores_are_gone_read_only(tmp_path):
    present = tmp_path / "v1-database"
    present.mkdir()
    config = {**ARRANGEMENT, "v1Stores": {"v1-stores/database": str(present),
                                          "v1-stores/objects": str(tmp_path / "gone")}}
    driver = ArrangementDriver(config, run=FakeSudo())
    inputs = {"place": "v1-stores", "locations": ["v1-stores/objects"]}
    assert driver.effect("copy-dispose", inputs, context=CONTEXT) == ["v1-stores/objects/absent"]
    with pytest.raises(DriverRefused, match="v1-store-still-present"):
        driver.effect("copy-dispose", {**inputs, "locations": ["v1-stores/database"]},
                      context=CONTEXT)
    assert present.exists()  # nothing deleted
    with pytest.raises(DriverRefused, match="v1-store-location-refused"):
        driver.effect("copy-dispose", {**inputs, "locations": ["v1-stores/unknown"]},
                      context=CONTEXT)


def test_effect_facts_hold_only_registered_names_and_bounded_values():
    assert drivers.facts_of({"sha256": "a" * 64, "other": "x"}) == [f"fact:sha256={'a' * 64}"]
    with pytest.raises(DriverRefused, match="effect-fact-outside-its-form"):
        drivers.facts_of({"location": "a b", "recordId": "has space"})
    assert drivers.parse_facts(["backup-volume/x", "fact:size=3"]) == {"size": "3"}
    with pytest.raises(ValueError):
        drivers.parse_facts(["fact:password=x"])


def test_the_realm_driver_keeps_only_the_owners_entries_of_a_set():
    listing = "\n".join([
        ";", "; Archive created",
        "5357; 0 0 ACL - SCHEMA public pg_database_owner",
        "2; 3079 16713 EXTENSION - vector ",
        "10; 2615 17000 SCHEMA - accounts docsuri_accounts_owner",
        "227; 1259 17041 TABLE public docsuri_local_identity postgres",
        "300; 1259 17100 TABLE accounts account docsuri_accounts_owner",
        "301; 0 17100 TABLE DATA accounts account docsuri_accounts_owner",
        "5453; 0 0 ACL pg_catalog FUNCTION pg_ls_waldir(OUT name text) postgres",
        "302; 0 0 ACL accounts TABLE account docsuri_accounts_owner",
    ])
    kept = RealmDriver.owners_entries(listing).splitlines()
    assert kept == [
        "300; 1259 17100 TABLE accounts account docsuri_accounts_owner",
        "301; 0 17100 TABLE DATA accounts account docsuri_accounts_owner",
        "302; 0 0 ACL accounts TABLE account docsuri_accounts_owner",
    ]


def test_the_arrangement_driver_runs_v1s_own_account_code_in_its_checkout(tmp_path):
    calls = []

    def run(argv, **options):
        calls.append((argv, options["cwd"]))
        return subprocess.CompletedProcess(argv, 0, stdout=b"", stderr=b"")

    driver = ArrangementDriver({**ARRANGEMENT, "v1Runtime": ["/v1/.venv/bin/python"],
                                "v1Checkout": str(tmp_path)}, run=run)
    assert driver.effect("v1-lifecycle-apply", {"outcomes": [], "accounts": []},
                         context=CONTEXT) == ["v1/lifecycle"]
    assert calls == [(["/v1/.venv/bin/python", "-I", "-m",
                       "backend.modules.accounts.services.v2_rollback_apply"], str(tmp_path))]
    driver._run = lambda argv, **o: subprocess.CompletedProcess(argv, 2, stdout=b"",
                                                                stderr=b"")
    with pytest.raises(DriverRefused, match="v1-lifecycle-refused"):
        driver.effect("v1-lifecycle-apply", {"outcomes": [], "accounts": []}, context=CONTEXT)


# --- the bounded child's side, in process -------------------------------------------------


def test_u8s_adapter_hands_a6s_effects_to_the_driver_with_u7s_faults(tmp_path, realm):
    """U8's bounded child (`u8_platform.adapter`) runs A6's effects; U7's child, as
    built, refuses the same request and writes nothing (U8 plan Step 44)."""
    from docsuri_ops.platform_control import native_adapter as u7_child
    from docsuri_ops.u8_platform import adapter as native_adapter

    journey = pf.journey(tmp_path, realm)
    inputs = {"origin": "v1-web"}
    digest = drivers.input_hash(inputs)
    token = secrets.token_hex(8)  # sixteen hex digits, generated per run (L1-36)
    drivers.write_input(journey.profile.effects_root / "tunnel", token, inputs)
    request = {"operationId": CONTEXT["operationId"], "operationName": "platform.tunnel.route",
               "targetId": "tunnel", "token": token, "effectKind": "tunnel-route",
               "inputHash": digest, "targetRoot": str(journey.profile.effects_root)}
    tunnel_before = journey.tunnel()
    refused = u7_child.apply_effect(dict(request))
    assert refused["status"] == "not-applied"
    assert refused["error"]["message"] == "unsupported effect kind"
    assert journey.tunnel() == tunnel_before
    assert native_adapter.apply_effect(dict(request), injected_fault="permission")[
        "status"] == "not-applied"
    assert native_adapter.apply_effect(dict(request), injected_fault="disk")["status"] == (
        "unknown")
    applied = native_adapter.apply_effect(dict(request))
    assert applied["status"] == "applied", applied
    assert applied["effectRefs"][1:] == ["tunnel/v1-web"]
    assert journey.tunnel()["origin"] == "v1-web"
    # Reconciliation reads the effect record the child wrote, and runs nothing again.
    assert drivers.observe(journey.profile.effects_root, "tunnel", token, "tunnel-route",
                           digest)
    changed = native_adapter.apply_effect({**request, "inputHash": "0" * 64})
    assert changed["status"] == "not-applied"
    assert changed["error"]["message"] == "input-hash-mismatch"
    escaped = native_adapter.apply_effect({**request, "targetId": "../tunnel"})
    assert escaped["status"] == "not-applied"


def test_an_unknown_effect_without_a_record_is_read_from_its_target(tmp_path, realm):
    journey = pf.journey(tmp_path, realm)
    inputs = {"field": "mode", "value": "rehearsal"}
    token = secrets.token_hex(32)  # sixty-four hex digits, generated per run (L1-36)
    drivers.write_input(journey.profile.effects_root / "profile", token, inputs)
    assert drivers.observe(journey.profile.effects_root, "profile", token, "profile-change",
                           drivers.input_hash(inputs))
    with pytest.raises(DriverRefused, match="input-changed"):
        drivers.write_input(journey.profile.effects_root / "profile", token, {"x": 1})
    large = secrets.token_hex(32)  # an effect token, generated per run (L1-36)
    big = journey.profile.effects_root / "profile" / f"input-{large}.json"
    big.write_bytes(b"{" + b" " * (drivers.MAX_INPUT + 2) + b"}")
    with pytest.raises(DriverRefused, match="input-too-large"):
        drivers.read_input(big.parent, large, "0" * 64)


# --- U8's platform profiles ------------------------------------------------------------------


def test_the_platform_profiles_name_their_store_and_driver(tmp_path, realm):
    from docsuri_ops.u8_platform.platform_profile import (
        PRODUCTION_LABELS,
        REALM_LABELS,
        U8PlatformProfile,
    )

    production = U8PlatformProfile.production()
    assert (production.kind, production.database, production.port) == (
        "production", "docsuri_v2_platform", 15432)
    assert production.labels == PRODUCTION_LABELS and production.run_root is None
    with pytest.raises(ValueError, match="released in person"):
        production.realm_password("runtime")
    realm_profile = U8PlatformProfile.realm(Path(realm.root))
    assert realm_profile.labels == REALM_LABELS
    from docsuri_ops.platform_control import RUNTIME_ROLE

    target = realm_profile.store(RUNTIME_ROLE, "unused").target
    assert (target.host, target.port, target.dbname) == (
        "127.0.0.1", realm.database_port, "docsuri_u8_platform")
    with pytest.raises(ValueError):
        realm_profile.realm_password("superuser")
    reader = realm_profile.reader()
    assert reader is not None and reader.password is None and "password" not in repr(reader)
    folder = tmp_path / "reader"
    folder.mkdir(mode=0o700)
    for value in ({"authorityId": "not-a-uuid", "actor": "a"},
                  {"authorityId": "00000000-0000-4000-8000-000000000000", "actor": "a",
                   "password": ""}):
        path = folder / "platform-reader.json"
        path.write_text(json.dumps(value))
        path.chmod(0o600)
        with pytest.raises(ValueError, match="outside its form"):
            realm_profile.reader(folder)
    reader_password = secrets.token_hex(8)  # generated per run (L1-36)
    path.write_text(json.dumps({"authorityId": "00000000-0000-4000-8000-000000000000",
                                "actor": "service", "password": reader_password}))
    bound = realm_profile.reader(folder)
    assert bound.password == reader_password and reader_password not in repr(bound)
    assert realm_profile.reader(tmp_path / "absent") is None
    not_realm = tmp_path / "other"
    not_realm.mkdir(mode=0o700)
    (not_realm / "environment.json").write_text(json.dumps({"realm": "diagnostic"}))
    (not_realm / "environment.json").chmod(0o600)
    with pytest.raises(ValueError, match="composed realm"):
        U8PlatformProfile.realm(not_realm)


# --- the Docker the realm helpers reach (L1-76, L1-78) ---------------------------------------


class Stopped(Exception):
    """Raised by a spy after it records the `env` a call is handed: no Docker runs."""


def recorded_env(monkeypatch, module, name: str, call) -> dict:
    """The `env` that `call()` hands `module.<name>`, under a spy that then raises."""
    seen: list[dict] = []

    def spy(*args, **options):
        seen.append(dict(options["env"]))
        raise Stopped

    with monkeypatch.context() as scoped:
        scoped.setattr(module, name, spy)
        with pytest.raises(Stopped):
            call()
    assert len(seen) == 1
    return seen[0]


class SettlesNotApplied:
    """A stand-in bounded child that answers a not-applied settlement line."""

    returncode = 0

    def communicate(self, payload=None, timeout=None):
        return json.dumps({"status": "not-applied", "effectRefs": [],
                           "error": {"kind": "internal", "message": "stand-in"}}).encode(), b""


@pytest.mark.parametrize("docker_host_set", [True, False])
def test_the_realm_helpers_pass_docker_host_only_when_it_is_set(tmp_path, realm, monkeypatch,
                                                                docker_host_set):
    import os
    import secrets
    import sys
    import uuid

    from docsuri_ops.backup_agent import dumps
    from docsuri_ops.backup_agent.config import Login
    from docsuri_ops.migration import realm as migration_realm
    from docsuri_ops.platform_control import executor
    from docsuri_ops.u8_platform.drivers import realm as realm_module

    socket = f"unix://{tmp_path}/docker-{secrets.token_hex(4)}.sock"
    planted = {name: f"planted-{secrets.token_hex(8)}"
               for name in ("DATABASE_URL", "OPENAI_API_KEY")}
    for name, value in planted.items():
        monkeypatch.setenv(name, value)
    if docker_host_set:
        monkeypatch.setenv("DOCKER_HOST", socket)
    else:
        monkeypatch.delenv("DOCKER_HOST", raising=False)
    docker_host = {"DOCKER_HOST": socket} if docker_host_set else {}

    login = Login("127.0.0.1", 5432, "docsuri_backup", "backup-password")
    tools_password = secrets.token_hex(8)  # generated per run (L1-36)
    container = dumps.ContainerTools(login, tools_password, container="docsuri-u8-" + "0" * 16)
    runtime = dumps.RuntimeTools(login, tools_password, bin_dir=tmp_path)
    driver = RealmDriver({**REALM_CONFIG, "repository": str(tmp_path / "repo"),
                          "agentFolder": str(tmp_path / "agent"), "schedulerUid": 501,
                          "operatorUid": 502})

    # Each environment as its one function builds it, and as the call that uses it hands it.
    built_migration = {name: os.environ[name] for name in ("PATH", "HOME", "DOCKER_CONFIG")
                       if name in os.environ}
    default_path = "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"
    built_driver = {"PATH": os.environ.get("PATH", default_path),
                    **{name: os.environ[name] for name in ("DOCKER_CONFIG", "HOME")
                       if os.environ.get(name)}}
    built_tools = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                   "PGPASSWORD": tools_password, "LANG": "C"}
    assert migration_realm.docker_environment() == {**built_migration, **docker_host}
    assert recorded_env(monkeypatch, migration_realm.subprocess, "run",
                        lambda: migration_realm._docker("ps")) == {**built_migration,
                                                                   **docker_host}
    assert RealmDriver.docker_environment() == {**built_driver, **docker_host}
    assert recorded_env(monkeypatch, realm_module.subprocess, "run",
                        lambda: driver._docker("ps")) == {**built_driver, **docker_host}
    agent = driver._agent_command("backup", "standing")[1]
    assert agent == {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "SUDO_UID": "501",
                     **docker_host}
    assert container.environment() == {**built_tools, **docker_host}
    assert recorded_env(monkeypatch, dumps.subprocess, "run",
                        lambda: container._run("pg_dump", ["--version"], seconds=5)) == {
        **built_tools, **docker_host}
    assert runtime.environment() == built_tools

    # A realm effect through a journey's operator, so through U7's bounded child (L1-78).
    handed: list[tuple[list[str], dict]] = []

    def popen(argv, **options):
        handed.append((list(argv), dict(options["env"])))
        return SettlesNotApplied()

    monkeypatch.setattr(executor.subprocess, "Popen", popen)
    receipt = pf.journey(tmp_path / "journey", realm).operator().execute(
        "platform.tunnel.route", "tunnel", {"origin": "v1-web"},
        key=f"docker-host-{uuid.uuid4().hex}-{pf.RUN}")
    assert receipt["outcome"] == "failed"
    assert [argv for argv, _ in handed] == [
        [sys.executable, "-m", "docsuri_ops.u8_platform.adapter"]]
    built_child = {name: os.environ[name] for name in ("PATH", "LANG", "LC_ALL", "TMPDIR")
                   if name in os.environ}
    assert handed[0][1] == {**built_child, **docker_host}


# --- Step 164(g): the realm's stand-ins demand SCRAM as production does (NFR3.3; L4-12) ----

# Exempt by name: the realm's own superuser restore inside its container
# (`RealmDatabases.restore_import`, `pg_restore -U postgres -d <name>` over the
# container's private socket). The superuser has no production counterpart over TCP
# (NFR3.3's second bullet), so that restore names no `require_auth`.
SUPERUSER_RESTORE = ("docsuri_ops.migration.realm", "RealmDatabases.restore_import")


def _restore_target(driver, tmp_path, database: str) -> dict:
    """The connection string the realm driver hands `pg_restore`, parsed by libpq's own
    parser. Docker is not run: each call is recorded and answered as done."""
    import psycopg

    handed: list[tuple] = []

    def docker(*args, **options):
        handed.append(args)
        return subprocess.CompletedProcess(args, 0, stdout=b"", stderr=b"")

    driver._docker = docker
    spool = tmp_path / "set.archive"
    spool.write_bytes(b"PGDMP" + os.urandom(16))
    driver._pg_restore(database, spool, secrets.token_hex(8))
    [restore] = [args for args in handed if "-d" in args]
    assert "pg_restore" in restore and "--no-password" in restore
    return psycopg.conninfo.conninfo_to_dict(restore[restore.index("-d") + 1])


def test_the_realm_stand_ins_demand_scram_as_production_does(realm_driver, realm, tmp_path,
                                                             monkeypatch):
    """The realm driver's connections and its `pg_restore` string, the realm's migration
    databases and its recovery wiring each name `require_auth=scram-sha-256`, as their
    production counterparts do. The driver's `connect` is a raise-only spy that refuses
    before any connection."""
    import inspect

    import psycopg

    from docsuri_ops.migration import realm as migration_realm
    from docsuri_ops.u8_platform import recovery_words
    from tests.u8_service_operations_integration.operations.test_scram_sites import (
        Reached,
        demanded,
        refusing_connect,
    )

    journey, driver = realm_driver
    port, scratch, scram = realm.database_port, pf.NAMES.new("scratch"), "scram-sha-256"
    target = _restore_target(driver, tmp_path, scratch)
    assert (target["host"], str(target["port"]), target["user"], target["dbname"],
            target.get("require_auth")) == ("127.0.0.1", "5432", "docsuri_restore", scratch, scram)
    monkeypatch.setattr(psycopg, "connect", refusing_connect)

    def asked(call) -> tuple:
        with pytest.raises(Reached) as reached:
            call()
        return demanded(reached.value.options)

    def reading(databases, name):
        with databases.import_reader(name):
            raise AssertionError("no connection is opened here")

    databases = migration_realm.RealmDatabases.for_realm(realm.root)
    imported = pf.NAMES.new("import")
    recovery = recovery_words._connector(journey.profile, "docsuri_restore",
                                         secrets.token_hex(16))  # made per run (L1-36)
    assert {
        "the driver's drop": asked(lambda: driver._drop_disposable(scratch)),
        "the migration databases' reader": asked(lambda: reading(databases, imported)),
        "the migration databases' connector": asked(lambda: migration_realm._connect(
            port, "docsuri_scheduler", secrets.token_hex(16), imported)),
        "the recovery wiring": asked(lambda: recovery("docsuri_u8")),
    } == {
        "the driver's drop": ("127.0.0.1", port, "docsuri_scheduler", "postgres", scram),
        "the migration databases' reader": (
            "127.0.0.1", port, "docsuri_scheduler", imported, scram),
        "the migration databases' connector": (
            "127.0.0.1", port, "docsuri_scheduler", imported, scram),
        "the recovery wiring": ("127.0.0.1", port, "docsuri_restore", "docsuri_u8", scram),
    }
    # The one stand-in exempt by name: it reaches the container's socket as the superuser.
    exempt = inspect.getsource(migration_realm.RealmDatabases.restore_import)
    assert SUPERUSER_RESTORE == (migration_realm.__name__, "RealmDatabases.restore_import")
    assert '"-U", "postgres"' in exempt and "require_auth" not in exempt
    assert "host=" not in exempt and "-h" not in exempt.split()
