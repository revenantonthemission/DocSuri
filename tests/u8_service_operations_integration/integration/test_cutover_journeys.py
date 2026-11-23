"""The cutover journeys against the synthetic v1 (U8 plan Step 34; Workflows 13 and 14,
BR9.2, BR9.4, BR9.5, BR9.7, BR9.13, R8).

v1 here is the synthetic v1 that `v1-up` runs from v1's own code at the repository's
commit (`scripts/u8_synthetic_v1.py`): its API on 18112 and its Next.js web on 18113,
supervised, over its own PostgreSQL, Redis, search index and object store, with the
synthetic v1 dataset. The phase that runs this file starts it first; nothing here starts
or replaces it, and it is left serving.

Each journey has its own ledger, platform state and tunnel routing, its own stand-in
backup volume, and a production stand-in database of its own in the realm's instance
(`docsuri_u8j<hex>`): the only database a final run imports into and an abort or a
rollback empties, never `docsuri_u8`. The rest is real:

- **service control** goes through the realm driver: v1's two labels reach the synthetic
  v1's supervisor, which starts and stops v1's own processes before it acknowledges;
  v2's three labels reach this journey's supervisor, which serves the complete assembly
  on 18109 over the journey's production database, with D7's boundary;
- **the public address** is the public stand-in on `https://127.0.0.1:18110`, routed by
  the realm driver's tunnel routing between v2's host, the maintenance server and v1's
  web; every check of who serves goes through it;
- **the final run** is the migration tool's: the backup agent's snapshot of v1's database
  from v1's own container, v1's search index and objects, the owners' imports into the
  production stand-in, and the report your decision accepts;
- **the first live backup and the rollback's copy** are the agent's, on the journey's
  volume;
- **a rollback** runs v1's own account code with v2's lifecycle outcomes and ends every
  v1 session (sessions made through v1's own sign-in), before v1 serves.

The dry run, the soak's evidence and the inventory are ledger records, as the component
journeys hold them (`component/test_cutover_words.py`): the dry run itself is
`integration/test_migration_run.py`'s subject.
"""

from __future__ import annotations

import contextlib
import dataclasses
import datetime as dt
import json
import os
import secrets
import socket
import ssl
import sys
import threading
import time
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import psycopg
import pytest
import uvicorn

from backend.local_profile import private_bytes
from backend.modules.accounts.services.first_sign_in import FirstSignIn
from backend.modules.accounts.services.rollback_outcomes import RollbackOutcomes
from backend.modules.operations.incidents import Incidents
from backend.modules.operations.migration.misfits import Decisions
from backend.modules.operations.migration_records import MigrationRuns
from backend.modules.operations.retained_copies import RetainedCopies
from backend.production_boundary import server_config
from backend.transactions import Authority
from backend.u8_policy import SYNTHETIC_OPERATIONS
from docsuri_ops.arrangement.paths import DatabaseNames
from docsuri_ops.backup_agent.config import AgentConfig, Login, write
from docsuri_ops.backup_agent.disposal import prepare_volume
from docsuri_ops.cutover import tool as cutover_tool
from docsuri_ops.cutover.preconditions import SwitchEvidence
from docsuri_ops.cutover.tool import CutoverPlatform, CutoverTool, run_word
from docsuri_ops.migration.disk_guard import DiskGuard
from docsuri_ops.migration.isolation_gate import IsolationGate
from docsuri_ops.migration.realm import RealmDatabases, owners_for
from docsuri_ops.migration.snapshot import BucketObjects, OpenSearchDocuments, Snapshot
from docsuri_ops.migration.tool import MigrationPlatform, MigrationTool
from docsuri_ops.u8_platform.drivers import load_config
from docsuri_ops.u8_platform.drivers.realm import RealmDriver
from docsuri_ops.u8_platform.recovery_words import realm_procedures
from docsuri_ops.u8_platform.u8_protocols import realm_facts, realm_operator
from tests.u8_service_operations_integration import cutover_flows as cf
from tests.u8_service_operations_integration import platform_flows as pf
from tests.u8_service_operations_integration import recovery_flows as rf

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

import u8_synthetic_v1 as synthetic_v1  # noqa: E402
from u8_tunnel_standin import TunnelStandin  # noqa: E402

DAY = 86400
V2_PORT = 18109
PUBLIC = "https://127.0.0.1:18110"
V1_API = "http://127.0.0.1:18112"
V2_LABELS = tuple(f"dev.docsuri.u8.run.{name}" for name in ("host", "workers", "scheduler"))
V1_LABELS = (synthetic_v1.API_LABEL, synthetic_v1.WEB_LABEL)
ROOM = 100 * rf.GIB
COMMIT = "0" * 40
# The journey's stand-in volume is a folder on this Mac's disk: its free-space floor is the
# realm's stand-in floor, as the realm's own agent is configured (`verify_docsuri_u8.
# REALM_SPACE_FLOOR_BYTES`); production's 64 GiB floor is unchanged.
POLICY = dataclasses.replace(SYNTHETIC_OPERATIONS, backup_volume_floor_bytes=1024**3)


def free(port: int) -> bool:
    with socket.socket() as probe:
        return probe.connect_ex(("127.0.0.1", port)) != 0


def wait_port(port: int, *, open_: bool = True, seconds: float = 30) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if free(port) != open_:
            return
        time.sleep(0.05)
    raise AssertionError(f"port {port} did not {'open' if open_ else 'close'}")


# --- the synthetic v1 ----------------------------------------------------------------------


@dataclasses.dataclass
class SyntheticV1:
    """The running synthetic v1: its dataset, a read of its accounts, its own sign-in."""

    run: Path
    dataset: dict
    secret: dict

    def connect(self):
        return psycopg.connect(host="127.0.0.1", port=synthetic_v1.PORTS["postgres"][0],
                               dbname=synthetic_v1.DATABASE, user=synthetic_v1.DATABASE_USER,
                               password=self.secret["postgres"], connect_timeout=3,
                               autocommit=True)

    def account(self, name: str) -> str:
        return self.dataset["accounts"][name]["v1AccountId"]

    def email(self, name: str) -> str:
        return self.dataset["accounts"][name]["email"]

    def accounts(self) -> list[str]:
        with self.connect() as conn:
            return [row[0] for row in conn.execute("SELECT id FROM accounts ORDER BY id")]

    def states(self, ids: list[str]) -> dict[str, str | None]:
        with self.connect() as conn:
            rows = dict(conn.execute("SELECT id,status FROM accounts WHERE id = ANY(%s)",
                                     (list(ids),)).fetchall())
        return {item: rows.get(item) for item in ids}

    def deletion_due(self, account: str) -> bool:
        with self.connect() as conn:
            return conn.execute("SELECT 1 FROM account_deletions WHERE account_id=%s",
                                (account,)).fetchone() is not None

    def sign_in(self, name: str) -> httpx.Client:
        """A v1 session through v1's own sign-in on its API. v1 sets its `session_id`
        cookie `Secure`, which a client only sends over HTTPS; the loopback API is plain
        HTTP, so the cookie is carried as a header, as the BFF carries it."""
        with httpx.Client(base_url=V1_API, timeout=15) as login:
            answer = login.post("/auth/login", json={"email": self.email(name),
                                                     "password": self.dataset["password"]})
        assert answer.status_code == 200, answer.text
        session = answer.cookies.get("session_id")
        assert session, "v1 issued no session"
        return httpx.Client(base_url=V1_API, timeout=15,
                            headers={"cookie": f"session_id={session}"})

    def ready(self) -> bool:
        return cutover_tool.http_probe(f"{V1_API}/health") == 200


def v1_serving(run: Path) -> None:
    """Leave v1 serving: its two services wanted running and acknowledged."""
    operation = f"journeys-restore:{time.time_ns()}"
    for label in V1_LABELS:
        synthetic_v1.set_wanted(label, "running", operation)
    synthetic_v1.wait_services("running", operation, synthetic_v1.START_SECONDS + 10)


@pytest.fixture(scope="module")
def v1(realm):
    run = Path(realm.root)
    dataset = json.loads(private_bytes(run / "v1" / "dataset.json"))
    secret = json.loads(private_bytes(run / "v1" / "credentials.json"))
    value = SyntheticV1(run, dataset, secret)
    if synthetic_v1.supervisor_pid() is None or not value.ready():
        pytest.fail("the synthetic v1 is not serving; the phase runs v1-up first")
    yield value
    v1_serving(run)


# --- the journey's v2: the complete assembly over its production stand-in ---------------------


class V2Supervisor:
    """The journey's process supervisor for v2's three named services, on the realm
    driver's wanted state in the journey's own services folder: `host` serves the complete
    assembly on 18109 over the journey's production database; `workers` runs every
    producer once, as the workers role does at its start; `scheduler` has nothing to run
    in a journey. Each operation is acknowledged once its process state holds."""

    def __init__(self, folder: Path, profile, run_id: str):
        self.folder, self.profile, self.run_id = folder, profile, run_id
        self.composition = self.server = self.thread = None
        self.stopping = threading.Event()
        self.loop = threading.Thread(target=self._run, daemon=True)
        self.errors: list[str] = []

    def __enter__(self):
        for label in V2_LABELS:
            path = self.folder / "supervisors" / f"{label}.json"
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            path.write_text(json.dumps({"pid": os.getpid(), "runId": self.run_id}))
        self.loop.start()
        return self

    def __exit__(self, *exc):
        self.stopping.set()
        self.loop.join(30)
        self._stop_host()
        for label in V2_LABELS:
            (self.folder / "supervisors" / f"{label}.json").unlink(missing_ok=True)

    @property
    def serving(self) -> bool:
        return self.thread is not None and self.thread.is_alive()

    def _start_host(self) -> bool:
        from backend.u8_host import compose, host_app

        if self.serving:
            return True
        wait_port(V2_PORT, open_=False)
        self.composition = compose(self.profile)
        app = host_app(self.composition)
        app.state.control_capacity.refresh()
        self.server = uvicorn.Server(server_config(app, V2_PORT, log_level="error"))
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.thread.start()
        wait_port(V2_PORT)
        return cutover_tool.http_probe(f"http://127.0.0.1:{V2_PORT}/health/live") == 200

    def _stop_host(self) -> bool:
        if self.server is not None:
            self.server.should_exit = True
            self.thread.join(30)
        if self.composition is not None:
            self.composition.close()
        self.composition = self.server = self.thread = None
        return free(V2_PORT)

    def _workers(self) -> bool:
        from backend.modules.operations.observation_store import ObservationStore
        from backend.modules.operations.observations import Observations
        from backend.modules.operations.producers import ProducerSchedule
        from backend.u8_host import worker_producers

        if self.composition is None:
            return False
        # One bounded pass of the complete worker, as the workers role's loop runs it; its
        # status is what `background.work`'s producer reads.
        self.composition.worker.run_once(4)
        status = {"state": "running", "timeouts": 0}
        schedule = ProducerSchedule(
            worker_producers(self.composition, loop_status=lambda: status),
            Observations(ObservationStore(self.composition.transactions)),
            self.composition.policy, self.composition.clock)
        schedule.run_due()
        return True

    def _act(self, label: str, wanted: str) -> bool:
        name = label.rsplit(".", 1)[-1]
        if name == "host":
            return self._start_host() if wanted == "running" else self._stop_host()
        if name == "workers" and wanted == "running":
            return self._workers()
        return True

    def _run(self) -> None:
        done: dict[str, str] = {}
        while not self.stopping.is_set():
            for label in V2_LABELS:
                path = self.folder / f"{label}.json"
                if not path.exists():
                    continue
                value = json.loads(path.read_text())
                if done.get(label) == value["operationId"]:
                    continue
                try:
                    result = self._act(label, value["state"])
                except Exception as error:  # noqa: BLE001 - reported through the ack
                    self.errors.append(f"{label}:{type(error).__name__}:{error}")
                    result = False
                observed = value["state"] if result else "unknown"
                (self.folder / f"{label}.ack.json").write_text(json.dumps({
                    "operationId": value["operationId"], "observed": observed,
                    "result": "succeeded" if result else "failed"}))
                done[label] = value["operationId"]
            time.sleep(0.1)


# --- one journey ------------------------------------------------------------------------------


def create_production(realm, name: str) -> None:
    """The journey's production stand-in: `docsuri_u8`'s database grants and composed
    schema with its identity row, nothing else, as a production database starts."""
    from psycopg import sql

    rf.drop_database(realm, name)
    with rf.admin(realm) as conn:
        ident = sql.Identifier(name)
        conn.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template1").format(ident))
        conn.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(ident))
        for role, privilege in conn.execute(
            "SELECT r.rolname,a.privilege_type FROM pg_database d, aclexplode(d.datacl) a "
            "JOIN pg_roles r ON r.oid=a.grantee WHERE d.datname='docsuri_u8' "
            "AND r.rolname<>'postgres'").fetchall():
            conn.execute(sql.SQL("GRANT {} ON DATABASE {} TO {}").format(
                sql.SQL(privilege), ident, sql.Identifier(role)))
    RealmDatabases.for_realm(Path(realm.root)).prepare_production(name)


def journey_agent(tmp_path: Path, realm, name: str, clock) -> Path:
    """The agent's folder and stand-in volume for the journey: its production database,
    and v1's database read through v1's reader login in v1's own container."""
    run = Path(realm.root)
    driver = json.loads(private_bytes(run / "platform" / "effects" / "driver.json"))
    environment = json.loads(private_bytes(run / "environment.json"))
    volume, folder = tmp_path / "volume", tmp_path / "agent"
    for path in (volume, folder):
        path.mkdir(mode=0o700)
    prepare_volume(volume, clock=clock)
    secrets_ = {"v2-login": rf.credentials(realm, "standin-credentials.json")["roles"][
        "backupAgent"], "v1-login": json.loads(private_bytes(run / "v1" / "credentials.json"))[
        "reader"]}
    for file, password in secrets_.items():
        descriptor = os.open(folder / file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            stream.write(password)
    write(folder, AgentConfig(
        kind="realm", mount=volume, volume_identity=f"standin-cutover-{secrets.token_hex(4)}",
        database_prefix=name,
        v2_login=Login("127.0.0.1", realm.database_port, "docsuri_backup_agent", "v2-login"),
        scheduler_uid=driver["schedulerUid"], operator_uid=driver["operatorUid"],
        service_uid=710, container=environment["container"], space_floor_bytes=1024**2,
        v1_database=synthetic_v1.DATABASE,
        v1_login=Login("127.0.0.1", synthetic_v1.PORTS["postgres"][0], synthetic_v1.READER,
                       synthetic_v1.AGENT_V1_LOGIN),
        v1_container=f"{environment['container']}-v1-postgres",
    ))
    return folder


class Journey:
    def __init__(self, tmp_path: Path, realm, clock, v1: SyntheticV1):
        self.tmp, self.realm, self.clock, self.v1 = tmp_path, realm, clock, v1
        self.production = f"docsuri_u8j{secrets.token_hex(3)[:5]}"
        self.names = DatabaseNames(self.production)
        create_production(realm, self.production)
        agent = journey_agent(tmp_path, realm, self.production, clock)
        self.services = tmp_path / "services"
        self.journey = pf.journey(
            tmp_path, realm, mode="rehearsal", admission="maintainer-only",
            agentFolder=str(agent), servicesRoot=str(self.services),
            v1ServicesRoot=str(synthetic_v1.SERVICES), v1StoresRoot=str(tmp_path))
        self.ledger = rf.open_ledger(tmp_path, clock)
        base = realm_facts(self.journey.profile, self.ledger, clock=clock)

        def facts():
            current = base()
            current.names = self.names
            return current

        self.operator = realm_operator(self.journey.profile, "operator", self.ledger,
                                       clock=clock, facts=facts)
        self.driver = RealmDriver(load_config(self.journey.profile.effects_root))
        self.v2_profile = dataclasses.replace(realm, database_name=self.production)
        self.supervisor = V2Supervisor(self.services, self.v2_profile, realm.run_id)
        self.migration = self._migration_tool()
        self.platform = self._platform()
        self.tool = CutoverTool(self.ledger, POLICY, self.platform, clock=clock)
        self.tunnel = TunnelStandin(realm, routes_root=self.journey.root)
        context = ssl.create_default_context(
            cafile=str(Path(realm.root) / "service-operations-tls.crt"))
        self.public_client = httpx.Client(base_url=PUBLIC, verify=context, timeout=15)

    # -- the parts the cutover needs -------------------------------------------------------

    def _migration_tool(self) -> MigrationTool:
        import boto3
        from botocore.config import Config

        evidence, spool = self.tmp / "evidence" / "migration", self.tmp / "spool"
        spool.mkdir(mode=0o700)
        secret = self.v1.secret
        s3 = boto3.client("s3", endpoint_url=f"http://127.0.0.1:{synthetic_v1.PORTS['objects'][0]}",
                          aws_access_key_id=secret["objectsUser"],
                          aws_secret_access_key=secret["objectsPassword"],
                          region_name="ap-northeast-2",
                          config=Config(signature_version="s3v4"))

        def dump(kind, record, decided):
            document = {"kind": kind, "recordId": record}
            if decided is not None:
                document["decided"] = decided
            return self.driver.agent_word("snapshot", document, via="in-person")

        copies = RetainedCopies(self.ledger, SYNTHETIC_OPERATIONS, clock=self.clock)
        snapshot = Snapshot(
            copies, dump=dump, stream=self.driver.snapshot_stream,
            index=OpenSearchDocuments(
                f"http://127.0.0.1:{synthetic_v1.PORTS['opensearch'][0]}",
                self.v1.dataset["index"]),
            objects=BucketObjects(s3, self.v1.dataset["bucket"]), evidence=evidence)
        databases = RealmDatabases.for_realm(Path(self.realm.root))
        platform = MigrationPlatform(
            operator=self.operator, names=self.names, snapshot=snapshot,
            create_rehearsal=databases.create_rehearsal, create_import=databases.create_import,
            restore_import=databases.restore_import, import_reader=databases.import_reader,
            owners_for=owners_for(self.realm), stream_back=self.driver.stream_back,
            isolation=IsolationGate(self.journey.state / "isolation",
                                    freshness_seconds=SYNTHETIC_OPERATIONS
                                    .isolation_freshness_seconds, clock=self.clock),
            disk=DiskGuard(lambda: ROOM, SYNTHETIC_OPERATIONS.internal_disk_threshold_bytes),
            spool=spool, evidence=evidence, installed=lambda: True,
            database_bytes=databases.database_bytes,
            prepare_production=databases.prepare_production,
        )
        return MigrationTool(MigrationRuns(self.ledger, clock=self.clock), copies, platform,
                             clock=self.clock, tool_commit=COMMIT)

    def final_run(self, approval: str, dispose_after: dt.datetime) -> dict:
        run = self.migration.start_final(approval_id=approval, dispose_after=dispose_after)
        return self.migration.run(run["runId"])

    def first_backup(self, key: str) -> dict:
        procedures = realm_procedures(self.journey.profile, self.ledger, clock=self.clock,
                                      ready=lambda: True, free_bytes=lambda: ROOM,
                                      mfa_current=lambda account, at: True,
                                      names=self.names).procedures
        procedures.platform.operator = self.operator
        return procedures.take("live", "first-live", request=None, via="in-person",
                               step="first-live", owner_key=key)

    def _transactions(self):
        from backend.transactions import OwnerTransactions

        return OwnerTransactions(self.v2_profile)

    def lifecycle_outcomes(self, since: dt.datetime) -> list[dict]:
        transactions = self._transactions()
        try:
            return RollbackOutcomes(transactions).latest_outcomes(since)
        finally:
            transactions.close()

    def v2_writes(self, since: dt.datetime) -> dict[str, int]:
        transactions = self._transactions()
        try:
            return RollbackOutcomes(transactions).changes_since(since)
        finally:
            transactions.close()

    def public(self, kind: str) -> bool:
        return cutover_tool.http_probe(
            PUBLIC + cutover_tool.PUBLIC_PATHS[kind],
            context=ssl.create_default_context(
                cafile=str(Path(self.realm.root) / "service-operations-tls.crt"))) == 200

    def capabilities_missing(self) -> list[str]:
        report = cutover_tool.ready_report(f"http://127.0.0.1:{V2_PORT}/health/ready")
        if report is None:
            return ["readiness-unreadable"]
        return sorted({*report.get("missing", [])})

    def _platform(self) -> CutoverPlatform:
        self.created_rehearsals: list[str] = []
        folder = self.tmp / "evidence"
        isolation = self.tmp / "isolation"
        isolation.mkdir()
        self.isolation = isolation
        evidence = SwitchEvidence(
            verification=lambda run: {"passed": True, "releaseTag": cf.TAG},
            v1_checkout=cutover_tool.V1Checkout(ROOT, ()),
            rehearsal_fingerprint=cutover_tool.rehearsal_fingerprint_reader(folder),
            agent_status=lambda: self.driver.agent_word("status", {}, via="in-person"),
            service_volume=lambda: "stand-in",
            isolation=IsolationGate(isolation, freshness_seconds=900, clock=self.clock),
            # The profile's rehearsal database, as the operator's facts read it.
            rehearsal_database=lambda: self.operator.facts().current_rehearsal,
        )
        return CutoverPlatform(
            operator=self.operator, production=self.production, v1_labels=V1_LABELS,
            v2_labels=V2_LABELS,
            v2_ready=lambda: cutover_tool.http_probe(
                f"http://127.0.0.1:{V2_PORT}/health/live") == 200,
            v1_ready=self.v1.ready, public=self.public, evidence=evidence,
            evidence_folder=folder, capabilities_missing=self.capabilities_missing,
            final_run=self.final_run, first_backup=self.first_backup,
            agent=self.driver.agent_word, lifecycle_outcomes=self.lifecycle_outcomes,
            v1_accounts=self.v1.accounts, v1_states=self.v1.states, v2_writes=self.v2_writes,
            v1_store_present=cutover_tool.store_present(self.tmp),
            # A rollback's new rehearsal database, recorded instead of created: v2 stays
            # stopped after a rollback, and the journeys are about v1 serving again.
            create_rehearsal=self.created_rehearsals.append,
        )

    # -- the cutover's evidence and your decisions -------------------------------------------

    def decide(self, step: str, subject: dict | None = None, ref: str | None = None) -> str:
        record = self.tool.machine.current()
        return rf.decide(self.operator, self.ledger, self.clock, step,
                         ref or record["cutoverId"], subject=subject)

    def decide_misfits(self) -> None:
        """Workflow 10: your decision on each (kind, reason), Workflow 10's proposals, so
        the final run applies them and only what it meets first takes archive-only."""
        from backend.modules.operations.migration.misfits import MAPPING_RULES, PROPOSALS
        from backend.modules.operations.migration_records import MisfitDecisions

        decisions = MisfitDecisions(self.ledger, clock=self.clock)
        for (kind, reason), decision in PROPOSALS.items():
            approval = rf.approval_record(self.ledger, "misfit-decision", f"{kind}:{reason}",
                                          now=self.clock())
            decisions.decide(kind, reason, decision, approval_id=approval["approvalId"],
                             mapping_rule=MAPPING_RULES.get((kind, reason))
                             if decision == "map" else None)

    def isolation_passed(self) -> None:
        moment = self.clock()
        (self.isolation / f"{moment:%Y%m%dT%H%M%S%f}.json").write_text(json.dumps(
            {"passed": True, "checkedAt": moment.isoformat(), "items": []}))

    def ready(self) -> dict:
        """Ready to switch: BR9.2 (1)–(9), the restart rehearsal run on the real v1."""
        machine = self.tool.machine
        machine.begin(cf.TAG)
        self.decide_misfits()
        # The soak's rehearsal database: recorded as the dry run's target and held by the
        # profile (v2 itself runs on this journey's own production stand-in).
        soak = self.names.new("rehearsal")
        run = cf.accepted_dry_run(self.ledger, now=self.clock(), database=soak,
                                  decisionsDigest=Decisions.from_ledger(self.ledger).digest())
        self.journey.set_profile(rehearsalDatabase=soak)
        machine.dry_run_accepted(run["runId"])
        machine.verification_passed(uuid4(), cf.TAG)
        record = machine.start_soak()
        start = dt.datetime.fromisoformat(record["soakStartedAt"].replace("Z", "+00:00"))
        sets = cf.scheduled_sets(self.ledger, start, 7, database=soak)
        cf.verified_restore(self.ledger, sets[0], now=start + dt.timedelta(hours=2))
        self.clock.advance(7 * DAY + 60)
        # The inventory at the check's clock, after the soak (L1-21).
        machine.inventory_taken(cf.complete_inventory(self.ledger, now=self.clock())[
            "inventoryId"])
        rehearsed = self.tool.rehearse_restart(self.decide("v1-restart-rehearsal"))
        assert rehearsed["rehearsed"], rehearsed
        self.isolation_passed()
        checked = self.tool.check()
        assert checked == {"state": "ready-to-switch", "missing": []}, checked
        return machine.current()

    def start(self) -> dict:
        record = self.ready()
        # The policy's rule, not a date (L1-3).
        subject = {"cutoverId": record["cutoverId"], "finalSnapshotBackstopSeconds":
                   SYNTHETIC_OPERATIONS.final_snapshot_backstop_seconds}
        return self.tool.start(self.decide("switch-start", subject), subject)

    def accept_final(self) -> None:
        record = self.tool.machine.current()
        approval = self.decide("final-report", ref=record["finalRunId"])
        decided = self.migration.decide(record["finalRunId"], approval)
        assert decided["state"] == "accepted", decided

    def switched(self) -> dict:
        first = self.start()
        assert first.get("waiting") == "final-report", first
        self.accept_final()
        second = self.tool.start()
        assert second == {"state": "switching", "waiting": "maintainer-window"}, (
            second, self.supervisor.errors)
        opened = self.open_admission()
        assert opened["state"] == "switched", opened
        return opened

    def open_admission(self) -> dict:
        """Your opening decision; a refused gate fails with what it names."""
        from backend.modules.operations.errors import OperationsError

        record = self.tool.machine.current()
        subject = {"cutoverId": record["cutoverId"], "providersAcceptedUnavailable": [],
                   "v1StoresDisposalSeconds": SYNTHETIC_OPERATIONS.v1_stores_disposal_seconds}
        try:
            return self.tool.open(self.decide("admission-opening", subject), subject)
        except OperationsError as refused:
            raise AssertionError(f"opening refused: {refused.code} {refused.current}") from None

    def rollback_subject(self) -> dict:
        record = self.tool.machine.current()
        return {"cutoverId": record["cutoverId"], "rolledBackDisposalSeconds":
                SYNTHETIC_OPERATIONS.rolled_back_disposal_seconds}

    # -- what the public address serves --------------------------------------------------------

    def served_by(self) -> str:
        """Who answers the public address now: v2's host, v1's web or the notice."""
        answer = self.public_client.get("/health/live")
        if answer.status_code == 200 and answer.json().get("process") == "alive":
            return "v2-host"
        page = self.public_client.get("/bff/health")
        if page.status_code == 200 and "next-router" in page.headers.get("vary", ""):
            return "v1-web"
        notice = self.public_client.get("/")
        return "maintenance" if notice.status_code == 503 or b"maintenance" in (
            notice.content.lower()) else f"other:{notice.status_code}"

    def production_tables(self) -> int:
        with rf.admin(self.realm, self.production) as conn:
            return conn.execute(
                "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE c.relkind='r' AND n.nspname NOT IN ('pg_catalog','information_schema',"
                "'public')").fetchone()[0]

    def close(self) -> None:
        self.public_client.close()
        for record in self.ledger.records("retained-copy"):
            for location in record["locations"]:
                if location.startswith("database/"):
                    rf.drop_database(self.realm, location.removeprefix("database/"))
        self.ledger.close()
        rf.drop_database(self.realm, self.production)


@contextlib.contextmanager
def maintenance_served(build: Path = ROOT / "frontend"):
    """The maintenance server on the realm's 18111 with `build`'s script-free pages (the
    browser stage passes the built `frontend/dist`, whose pages link their stylesheets)."""
    from backend.maintenance_server import REALM_PORT, MaintenanceServer, Pages
    server = MaintenanceServer(Pages.load(build), port=REALM_PORT,
                               public_authority="127.0.0.1:18110")
    server.start()
    try:
        yield server
    finally:
        server.stop()


@pytest.fixture
def clock():
    """The journey's one clock, started 8 days before now: the soak's 7 days of ledger
    evidence end before the real moment v2 serves, so what v2's database stamps with its
    own clock (a lifecycle request's acceptance) comes after the switch, as in production."""
    from tests.u8_service_operations_integration.conftest import Clock

    return Clock(dt.datetime.now(dt.UTC) - dt.timedelta(days=8))


@pytest.fixture
def journey(tmp_path, realm, clock, v1):
    for port in (V2_PORT, 18110, 18111):
        assert free(port), f"port {port} is in use; the phase runs with the realm stopped"
    value = Journey(tmp_path, realm, clock, v1)
    try:
        with value.supervisor, value.tunnel.running(), maintenance_served():
            yield value
    finally:
        value.close()
        v1_serving(Path(realm.root))


def services(journey) -> dict[str, str]:
    states = {}
    for label in V2_LABELS:
        states[label.rsplit(".", 1)[-1]] = json.loads(
            (journey.services / f"{label}.json").read_text())["state"]
    for label in V1_LABELS:
        states[label.rsplit(".", 1)[-1]] = synthetic_v1.wanted(label)["state"]
    return states


# --- 1. a switch, through every step ----------------------------------------------------------


def test_a_switch_ends_with_admission_open_and_only_v2_at_the_public_address(journey):
    first = journey.start()
    assert first["waiting"] == "final-report", first
    record = journey.tool.machine.current()
    assert record["state"] == "switching" and "switchStartedAt" in record
    # The maintenance notice serves while v1 is stopped and the final run imports.
    assert journey.served_by() == "maintenance"
    assert not journey.v1.ready() and free(synthetic_v1.WEB_PORT)
    run = journey.migration.runs.require(record["finalRunId"])
    assert run["state"] == "reported" and run["kind"] == "final"
    assert journey.production_tables() > 0  # v1's records are in the production stand-in
    journey.accept_final()
    assert journey.tool.start() == {"state": "switching", "waiting": "maintainer-window"}
    # The maintainer-only window: v2 serves its own production database, publicly.
    assert journey.served_by() == "v2-host"
    profile = journey.journey.read_state("profile.json")
    assert profile["mode"] == "live" and profile["admission"] == "maintainer-only"
    backups = [item for item in journey.ledger.records("backup-set")
               if item["environment"] == "live"]
    assert backups and backups[-1]["integrity"] == "passed"
    # The switch's first live set has exactly one ledger copy of its own (L1-5).
    copies = [item for item in journey.ledger.records("ledger-copy")
              if item.get("backupId") == backups[-1]["backupId"]]
    assert len(copies) == 1 and copies[0]["verifiedAt"], copies
    opened = journey.open_admission()
    assert opened["state"] == "switched", opened
    profile = journey.journey.read_state("profile.json")
    assert profile["mode"] == "live" and profile["admission"] == "open"
    # Only the v2 workspace at the public address; v1 is stopped, its services too.
    assert journey.served_by() == "v2-host"
    # Nothing of v1's answers: v1's web marks every answer with Next's router `vary`.
    for path in ("/", "/bff/health", "/login"):
        assert "next-router" not in journey.public_client.get(path).headers.get("vary", "")
    assert services(journey) == {"host": "running", "workers": "running",
                                 "scheduler": "running", "v1-api": "stopped",
                                 "v1-web": "stopped"}
    assert free(synthetic_v1.API_PORT) and free(synthetic_v1.WEB_PORT)


# --- 2. an abort: v1 serves before v2's database is emptied ------------------------------------


class Watched:
    """The operator, noting who serves the public address and what the production
    stand-in holds at the moment its recreate runs."""

    def __init__(self, journey):
        self.journey, self.operator = journey, journey.operator
        self.at_recreate: list[tuple[str, int]] = []

    def __getattr__(self, name):
        return getattr(self.operator, name)

    def execute(self, operation, target, inputs, *, key, injected_fault=None, **options):
        if operation == "platform.database.recreate":
            self.at_recreate.append((self.journey.served_by(),
                                     self.journey.production_tables()))
        return self.operator.execute(operation, target, inputs, key=key,
                                     injected_fault=injected_fault, **options)


def test_an_abort_has_v1_serving_before_v2s_database_is_emptied(journey):
    journey.start()
    assert journey.production_tables() > 0
    watched = Watched(journey)
    journey.platform.operator = watched
    result = run_word(journey.tool, "abort", {"reason": "operator-abort"})
    assert result["state"] == "rehearsing", result
    # At the recreate, v1 already served the public address and v2's database was whole.
    assert watched.at_recreate and watched.at_recreate[0][0] == "v1-web"
    assert watched.at_recreate[0][1] > 0
    assert journey.production_tables() == 0
    assert journey.served_by() == "v1-web" and journey.v1.ready()
    record = journey.tool.machine.current()
    incident = Incidents(journey.ledger, environment="live").get(record["abortIncidentId"])
    assert incident["openedBy"] == "switch-aborted"
    run = journey.ledger.get("migration-run", record["finalRunId"])
    assert run["state"] == "failed"  # a final run not yet accepted ends failed
    profile = journey.journey.read_state("profile.json")
    assert profile["mode"] == "rehearsal" and profile["admission"] == "maintainer-only"


# --- 3 and 4. a rollback, and a cancelled one ----------------------------------------------------


def sign_in_v2(journey, name: str):
    """A migrated account's first sign-in to v2 through AccountAccess, then its consents:
    a full session (BR8.6)."""
    entry = journey.supervisor.composition.parts["account-controls"]["entry"]
    result = entry.login(journey.v1.email(name), journey.v1.dataset["password"],
                         flow_binding=f"journey-{uuid4().hex[:8]}")
    assert result.public["state"] == "consent_pending", result.public
    session = result.public["session"]
    authority = Authority(UUID(session["accountId"]), UUID(session["sessionId"]))
    for purpose, granted in (("local-research", True), ("personalization", False)):
        entry.first_sign_in.give_consent(
            result.token, result.csrf, uuid4(),
            UUID(FirstSignIn.pending_revision(authority.account_id, purpose)), purpose,
            granted)
    return authority


def lifecycle_in_v2(journey, name: str, action: str) -> UUID:
    composition = journey.supervisor.composition
    authority = sign_in_v2(journey, name)
    revision = composition.transactions.run("accounts", lambda conn: conn.execute(
        "SELECT lifecycle_revision FROM accounts.account WHERE id=%s",
        (authority.account_id,)).fetchone()["lifecycle_revision"])
    composition.parts["account-controls"]["lifecycle"].request(
        authority, uuid4(), revision, action, journey.v1.dataset["password"])
    return authority.account_id


def v1_session_active(client: httpx.Client) -> bool:
    """v1's own session check: `{"userId": …}` while signed in, 401 otherwise."""
    answer = client.get("/auth/session")
    return answer.status_code == 200 and bool(answer.json().get("userId"))


def copies_recorded_first(journey, approval: str) -> dict:
    """U8 plan Step 90(i): delegating spies on the agent's `rollback-copy` and on the
    rollback's rehearsal-database creation. Each reads the journey's ledger first, then
    calls the real part and returns its result; what each found is kept by kind."""
    from backend.modules.operations.ledger import utc_text
    from backend.modules.operations.retained_copies import _parse

    seen: dict[str, dict] = {}
    copies = RetainedCopies(journey.ledger, SYNTHETIC_OPERATIONS, clock=journey.clock)
    day = dt.timedelta(days=1)
    real_agent, real_create = journey.platform.agent, journey.platform.create_rehearsal

    def agent(word, document, *, via):
        if word == "rollback-copy":
            [copy] = [item for item in copies.undisposed("rolled-back-v2-database")
                      if item["copyId"] == document["recordId"]]
            record = journey.tool.machine.current()
            assert copy["disposeAfter"] == utc_text(
                _parse(record["rollbackV1ServingAt"]) + 30 * day), copy
            assert copy["disposalApprovalId"] == approval
            assert copies.backstop_of(copy) == _parse(copy["createdAt"]) + 90 * day
            seen["rolled-back-v2-database"] = copy
        return real_agent(word, document, via=via)

    def create(name):
        [copy] = [item for item in copies.undisposed("rehearsal-database")
                  if item["locations"] == [f"database/{name}"]]
        assert _parse(copy["disposeAfter"]) - _parse(copy["createdAt"]) == 60 * day, copy
        seen["rehearsal-database"] = copy
        return real_create(name)

    journey.platform.agent, journey.platform.create_rehearsal = agent, create
    return seen


def test_a_cancelled_rollback_returns_v2_and_then_a_rollback_hands_v1_v2s_outcomes(journey):
    # Sessions made through v1's own sign-in before the switch.
    v1_sessions = [journey.v1.sign_in("member-b"), journey.v1.sign_in("member-a")]
    assert all(v1_session_active(client) for client in v1_sessions)
    journey.switched()
    # 4. A cancelled rollback: v1 does not start, your decision cancels, v2 serves again.
    synthetic_v1_stop = journey.platform.v1_ready
    journey.platform.v1_ready = lambda: False
    # The never-ready v1's wait moves the journey's clock and sleeps no real time
    # (Step 71(k)); both are put back before the second rollback.
    real_sleep = journey.platform.sleep
    journey.platform.sleep = journey.clock.advance
    subject = journey.rollback_subject()
    waiting = journey.tool.rollback(journey.decide("rollback", subject), subject)
    assert waiting == {"state": "rolling-back", "reason": "v1-restart-failed",
                       "offered": ["cancel-rollback"]}
    assert journey.production_tables() > 0
    cancelled = run_word(journey.tool, "cancel-rollback",
                         {"approvalId": journey.decide("rollback-cancel")})
    assert cancelled == {"state": "switched"}
    assert journey.served_by() == "v2-host" and free(synthetic_v1.API_PORT)
    journey.platform.v1_ready = synthetic_v1_stop
    journey.platform.sleep = real_sleep
    # 3. While v2 served, a migrated account asked to be erased, and another withdrew
    # (NFR7.16).
    erased = lifecycle_in_v2(journey, "member-b", "erase")
    withdrawn = lifecycle_in_v2(journey, "member-a", "withdraw")
    subject = journey.rollback_subject()
    approval = journey.decide("rollback", subject)
    seen = copies_recorded_first(journey, approval)
    result = journey.tool.rollback(approval, subject)
    try:
        assert result["state"] == "rolled-back", result
        # Each copy was recorded before its effect ran (L1-2, L1-3).
        assert sorted(seen) == ["rehearsal-database", "rolled-back-v2-database"], seen
        member = journey.v1.account("member-b")
        leaver = journey.v1.account("member-a")
        # v2's outcomes reached v1 through v1's own code, before v1 served: both are
        # deactivated, and only the erasure has a deletion record.
        assert journey.v1.states([member, leaver]) == {member: "DEACTIVATED",
                                                       leaver: "DEACTIVATED"}
        assert journey.v1.deletion_due(member)
        assert not journey.v1.deletion_due(leaver)
        record = journey.tool.machine.current()
        evidence = json.loads((journey.tmp / "evidence" /
                               f"rollback-accounts-{record['cutoverId']}.json").read_bytes())
        assert {(item["v1AccountId"], item["outcome"], item["state"])
                for item in evidence["accounts"]} == {
            (member, "erase", "DEACTIVATED"), (leaver, "withdraw", "DEACTIVATED")}
        # v2's own identities, mapped back by BR8.3.
        assert str(erased) != member and str(withdrawn) != leaver
        # Every v1 session ended.
        assert not any(v1_session_active(client) for client in v1_sessions)
        assert journey.served_by() == "v1-web"
        profile = journey.journey.read_state("profile.json")
        assert profile["mode"] == "rehearsal" and profile["admission"] == "maintainer-only"
        copies = RetainedCopies(journey.ledger, SYNTHETIC_OPERATIONS)
        rolled = copies.undisposed("rolled-back-v2-database")
        assert len(rolled) == 1 and "completedAt" in rolled[0]
        assert journey.production_tables() == 0
    finally:
        for client in v1_sessions:
            client.close()
        # v1's accounts back as they were, through v1's own reactivation.
        journey.driver.effect("v1-lifecycle-apply", {
            "outcomes": [{"v1AccountId": journey.v1.account(name), "outcome": "reactivate"}
                         for name in ("member-b", "member-a")], "accounts": []}, context={})


# --- 5. a rollback whose copy cannot be completed, and its three exits ---------------------------


def copy_cannot_complete(journey) -> dict:
    """The rollback with the stand-in volume unreadable: its copy waits on its incident."""
    journey.switched()
    volume = journey.tmp / "volume"
    os.chmod(volume, 0o000)
    try:
        subject = journey.rollback_subject()
        waiting = journey.tool.rollback(journey.decide("rollback", subject), subject)
    finally:
        os.chmod(volume, 0o700)
    assert waiting.get("copyPending") is True, waiting
    record = journey.tool.machine.current()
    assert record["state"] == "rolling-back" and "rollbackCopyPendingSince" in record
    assert journey.served_by() == "v1-web" and journey.v1.ready()
    assert journey.production_tables() > 0  # stopped and untouched while the copy waits
    return record


def assert_settled(journey, record: dict) -> None:
    incident = Incidents(journey.ledger, environment="live").get(
        record["rollbackCopyIncidentId"])
    assert incident["state"] == "resolved"
    assert incident["resolutionKind"] == "rollback-copy-settled"
    assert journey.tool.machine.current()["state"] == "rolled-back"
    assert journey.production_tables() == 0


def test_a_waiting_copy_completes_on_a_retry_once_the_volume_is_fit(journey):
    record = copy_cannot_complete(journey)
    done = run_word(journey.tool, "retry-copy", {})
    assert done["state"] == "rolled-back", done
    assert_settled(journey, record)
    rolled = RetainedCopies(journey.ledger, SYNTHETIC_OPERATIONS).undisposed(
        "rolled-back-v2-database")
    assert [item for item in rolled if "completedAt" in item]


def test_a_waiting_copy_completes_on_a_replacement_volume(journey):
    record = copy_cannot_complete(journey)
    # Your retirement decision: a new volume, prepared and configured for the agent.
    replacement = journey.tmp / "replacement"
    replacement.mkdir(mode=0o700)
    prepare_volume(replacement, clock=journey.clock)
    from docsuri_ops.backup_agent.config import load as load_agent

    folder = journey.tmp / "agent"
    write(folder, dataclasses.replace(
        load_agent(folder), mount=replacement,
        volume_identity=f"standin-replacement-{secrets.token_hex(4)}"))
    approval = journey.decide("backup-volume-retirement")
    done = run_word(journey.tool, "retry-copy", {"replacementApprovalId": approval})
    assert done["state"] == "rolled-back", done
    assert_settled(journey, record)
    assert any((replacement / "docsuri-v2" / "archives").iterdir())


def test_a_waiting_copy_is_waived_on_your_decision_shown_what_is_lost(journey):
    record = copy_cannot_complete(journey)
    os.chmod(journey.tmp / "volume", 0o000)
    try:
        assert run_word(journey.tool, "retry-copy", {})["reason"] == "backup-volume-unfit"
    finally:
        os.chmod(journey.tmp / "volume", 0o700)
    lost = journey.v2_writes(dt.datetime.fromisoformat(
        record["admissionOpenedAt"].replace("Z", "+00:00")))
    waiver = {"cutoverId": record["cutoverId"], "perKind": lost}
    done = run_word(journey.tool, "waive-copy", {
        "approvalId": journey.decide("rollback-copy-waiver", waiver), "subject": waiver})
    assert done["state"] == "rolled-back", done
    assert_settled(journey, record)
    assert not [item for item in RetainedCopies(journey.ledger, SYNTHETIC_OPERATIONS)
                .undisposed("rolled-back-v2-database") if "completedAt" in item]


# --- 6. the 4-hour bound offers only the abort ----------------------------------------------------


def test_the_four_hour_bound_offers_only_the_abort(journey):
    journey.start()
    journey.accept_final()
    journey.clock.advance(4 * 3600 + 1)
    assert journey.tool.start() == {"state": "switching", "offered": ["abort"],
                                    "reason": "switch-bound-passed"}
    record = journey.tool.machine.current()
    subject = {"cutoverId": record["cutoverId"], "providersAcceptedUnavailable": [],
               "v1StoresDisposalSeconds": SYNTHETIC_OPERATIONS.v1_stores_disposal_seconds}
    aborted = journey.tool.open(journey.decide("admission-opening", subject), subject)
    assert aborted["state"] == "rehearsing", aborted  # opening past the bound aborts
    assert journey.served_by() == "v1-web" and journey.production_tables() == 0
