"""The production migration platform on the synthetic v1 (U8 plan Step 32; the person's
decision of 2026-10-24, "Build it, test on test v1"; BR8.2, BR8.3, BR8.10, BR8.11,
BR8.12, BR9.12).

The platform's production class (`docsuri_ops.migration.production`) is configured to
the synthetic v1's addresses, which `v1-up` serves on the realm's v1 ports (PostgreSQL
15510, the search index 19209, the object store 19009): an environment file of the
test's own names them, as the installer names v1's in the operator's
`driver.json`. Its v1 side is production's own: the agent's `snapshot` carrying the
named address, the read-only index transport and the read-only object-store client.
Its v2 side is the composed realm's (the realm's own PostgreSQL for the run's databases,
the owners' imports in this process), because the production environment tool and the
import program run only against the production profile, whose refusals of synthetic
values stay as they are; those words are tested with stand-ins in
`operations/test_production_tool.py` and `operations/test_production_migration_words.py`.

The live v1 is never touched: every address here is a realm port.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import json
import os
import secrets
from pathlib import Path

import httpx
import psycopg
import pytest

from backend.local_profile import private_bytes
from backend.modules.operations.migration.misfits import MAPPING_RULES, PROPOSALS
from backend.modules.operations.migration_records import MigrationRuns, MisfitDecisions
from backend.modules.operations.retained_copies import RetainedCopies
from backend.u8_policy import SYNTHETIC_OPERATIONS
from docsuri_ops.arrangement.paths import REALM_DATABASES
from docsuri_ops.backup_agent.config import AgentConfig, Login, write
from docsuri_ops.backup_agent.disposal import prepare_volume
from docsuri_ops.migration import production
from docsuri_ops.migration.disk_guard import DiskGuard
from docsuri_ops.migration.isolation_gate import IsolationGate
from docsuri_ops.migration.realm import RealmDatabases, owners_for
from docsuri_ops.migration.snapshot import BucketObjects, OpenSearchDocuments, SnapshotRefused
from docsuri_ops.migration.tool import MigrationPlatform, MigrationTool
from docsuri_ops.u8_platform.drivers import load_config
from docsuri_ops.u8_platform.drivers.realm import RealmDriver
from docsuri_ops.u8_platform.u8_protocols import realm_facts, realm_operator
from tests.u8_service_operations_integration import platform_flows as pf
from tests.u8_service_operations_integration import recovery_flows as rf
from tests.u8_service_operations_integration.integration import test_cutover_journeys as tj

synthetic_v1 = tj.synthetic_v1
ROOM = 100 * rf.GIB
COMMIT = "0" * 40
INDEX_URL = f"http://127.0.0.1:{synthetic_v1.PORTS['opensearch'][0]}"
OBJECTS_URL = f"http://127.0.0.1:{synthetic_v1.PORTS['objects'][0]}"


def write_private(path: Path, value: dict) -> Path:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump(value, stream)
    return path


def environment_file(folder: Path, dataset: dict, secret: dict, **override) -> dict:
    """The operator's environment file as the installer writes it, naming the synthetic
    v1's addresses; the object store's credentials in a private file of the test's own."""
    credentials = folder / "v1-objects.json"
    if not credentials.exists():
        write_private(credentials, {"accessKey": secret["objectsUser"],
                                    "secretKey": secret["objectsPassword"]})
    sources = {
        "database": {"host": "127.0.0.1", "port": synthetic_v1.PORTS["postgres"][0],
                     "database": synthetic_v1.DATABASE},
        "index": {"url": INDEX_URL, "name": dataset["index"]},
        "objects": {"url": OBJECTS_URL, "bucket": dataset["bucket"],
                    "credentials": str(credentials)},
    }
    for part, value in override.items():
        sources[part] = {**sources[part], **value}
    return {"kind": "arrangement", "production": True, "actor": "operator",
            production.SOURCES_KEY: sources}


def agent_folder(tmp_path: Path, realm, prefix: str, clock) -> Path:
    """The agent's folder and stand-in volume: v1's database through v1's reader login
    in v1's own container, as `v1-up` wires the realm's agent."""
    run = Path(realm.root)
    driver = json.loads(private_bytes(run / "platform" / "effects" / "driver.json"))
    environment = json.loads(private_bytes(run / "environment.json"))
    volume, folder = tmp_path / "volume", tmp_path / "agent"
    for path in (volume, folder):
        path.mkdir(mode=0o700)
    prepare_volume(volume, clock=clock)
    for file, password in {
        "v2-login": rf.credentials(realm, "standin-credentials.json")["roles"]["backupAgent"],
        synthetic_v1.AGENT_V1_LOGIN: json.loads(private_bytes(run / "v1" / "credentials.json"))[
            "reader"],
    }.items():
        descriptor = os.open(folder / file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            stream.write(password)
    write(folder, AgentConfig(
        kind="realm", mount=volume, volume_identity="standin-production-0001",
        database_prefix=prefix,
        v2_login=Login("127.0.0.1", realm.database_port, "docsuri_backup_agent", "v2-login"),
        scheduler_uid=driver["schedulerUid"], operator_uid=driver["operatorUid"],
        service_uid=710, container=environment["container"], space_floor_bytes=1024**2,
        v1_database=synthetic_v1.DATABASE,
        v1_login=Login("127.0.0.1", synthetic_v1.PORTS["postgres"][0], synthetic_v1.READER,
                       synthetic_v1.AGENT_V1_LOGIN),
        v1_container=f"{environment['container']}-v1-postgres",
    ))
    return folder


@dataclasses.dataclass
class RealmV2:
    """v2's side of the run on the composed realm: its own PostgreSQL instance for the
    rehearsal and import databases and the owners' imports in this process."""

    databases: RealmDatabases
    owners_for: object

    def __getattr__(self, name):
        return getattr(self.databases, name)


class Stage:
    def __init__(self, tmp_path, realm, clock, v1, *, prefix: str = "docsuri_u8"):
        self.tmp, self.realm, self.clock, self.v1 = tmp_path, realm, clock, v1
        agent = agent_folder(tmp_path, realm, prefix, clock)
        self.journey = pf.journey(tmp_path, realm, mode="rehearsal",
                                  admission="maintainer-only", agentFolder=str(agent))
        self.ledger = rf.open_ledger(tmp_path, clock)
        self.operator = realm_operator(self.journey.profile, "operator", self.ledger,
                                       clock=clock)
        self.driver = RealmDriver(load_config(self.journey.profile.effects_root))
        self.copies = RetainedCopies(self.ledger, SYNTHETIC_OPERATIONS, clock=clock)
        self.databases = RealmDatabases.for_realm(Path(realm.root))
        self.runs = MigrationRuns(self.ledger, clock=clock)
        self.isolation_passed()
        self.decide_all()

    def gate(self) -> IsolationGate:
        return IsolationGate(self.journey.state / "isolation",
                             freshness_seconds=SYNTHETIC_OPERATIONS.isolation_freshness_seconds,
                             clock=self.clock)

    def production_tool(self, config: dict, name: str = "production") -> MigrationTool:
        """The production class, configured by `config` (the environment file)."""
        sources = production.V1Sources.from_config(config)
        folder = self.tmp / name
        platform = production.production_migration_platform(
            self.operator, sources=sources, names=REALM_DATABASES, driver=self.driver,
            databases=RealmV2(self.databases, owners_for(self.realm)), importer=None,
            isolation=self.gate(),
            disk=DiskGuard(lambda: ROOM, SYNTHETIC_OPERATIONS.internal_disk_threshold_bytes),
            spool=folder / "spool", evidence=folder / "evidence", installed=lambda: True,
            copies=self.copies)
        return MigrationTool(self.runs, self.copies, platform, clock=self.clock,
                             tool_commit=COMMIT)

    def realm_tool(self) -> MigrationTool:
        """The realm's platform over the same synthetic v1 (`words.realm_migration_tool`'s
        readers, unguarded), for the parity comparison."""
        import boto3
        from botocore.config import Config

        secret = self.v1.secret
        s3 = boto3.client("s3", endpoint_url=OBJECTS_URL,
                          aws_access_key_id=secret["objectsUser"],
                          aws_secret_access_key=secret["objectsPassword"],
                          region_name="ap-northeast-2", config=Config(signature_version="s3v4"))
        folder = self.tmp / "realm"
        spool = folder / "spool"
        spool.mkdir(mode=0o700, parents=True)

        def dump(kind, record, decided):
            document = {"kind": kind, "recordId": record}
            if decided is not None:
                document["decided"] = decided
            return self.driver.agent_word("snapshot", document, via="in-person")

        from docsuri_ops.migration.snapshot import Snapshot

        snapshot = Snapshot(self.copies, dump=dump, stream=self.driver.snapshot_stream,
                            index=OpenSearchDocuments(INDEX_URL, self.v1.dataset["index"]),
                            objects=BucketObjects(s3, self.v1.dataset["bucket"]),
                            evidence=folder / "evidence")
        platform = MigrationPlatform(
            operator=self.operator, names=REALM_DATABASES, snapshot=snapshot,
            create_rehearsal=self.databases.create_rehearsal,
            create_import=self.databases.create_import,
            restore_import=self.databases.restore_import,
            import_reader=self.databases.import_reader, owners_for=owners_for(self.realm),
            stream_back=self.driver.stream_back, isolation=self.gate(),
            disk=DiskGuard(lambda: ROOM, SYNTHETIC_OPERATIONS.internal_disk_threshold_bytes),
            spool=spool, evidence=folder / "evidence", installed=lambda: True,
            database_bytes=self.databases.database_bytes)
        return MigrationTool(self.runs, self.copies, platform, clock=self.clock,
                             tool_commit=COMMIT)

    def isolation_passed(self) -> None:
        receipt = self.operator.execute("platform.isolation.check", "isolation",
                                        {"via": "in-person"}, key=f"isolation-{pf.RUN}-"
                                        f"{self.clock().timestamp()}-{os.urandom(4).hex()}")
        assert receipt["outcome"] == "succeeded", receipt

    def decide_all(self) -> None:
        decisions = MisfitDecisions(self.ledger, clock=self.clock)
        for (kind, reason), decision in PROPOSALS.items():
            approval = rf.approval_record(self.ledger, "misfit-decision", f"{kind}:{reason}",
                                          now=self.clock())
            decisions.decide(kind, reason, decision, approval_id=approval["approvalId"],
                             mapping_rule=MAPPING_RULES.get((kind, reason))
                             if decision == "map" else None)

    def dry_run(self, tool: MigrationTool) -> dict:
        go = rf.decide(self.operator, self.ledger, self.clock, "dry-run-go-ahead",
                       "synthetic-v1")
        run = tool.start_dry(go)
        return tool.run(run["runId"])

    def report(self, tool: MigrationTool, run_id: str) -> dict:
        record = self.ledger.get("parity-report", run_id)
        return json.loads((tool.platform.evidence / Path(record["reportRef"]).name).read_text())

    def cleanup(self) -> None:
        for record in self.ledger.records("retained-copy"):
            for location in record["locations"]:
                if location.startswith("database/"):
                    rf.drop_database(self.realm, location.removeprefix("database/"))
        self.ledger.close()


# --- v1's stores, read for their checksums only ---------------------------------------------


def database_checksum(v1) -> dict:
    """Each of v1's tables, its rows' digest in a fixed order, read as v1's owner login."""
    found = {}
    with v1.connect() as conn:
        tables = [row[0] for row in conn.execute(
            "SELECT quote_ident(schemaname)||'.'||quote_ident(tablename) FROM pg_tables "
            "WHERE schemaname NOT IN ('pg_catalog','information_schema') ORDER BY 1")]
        for table in tables:
            row = conn.execute(psycopg.sql.SQL(
                "SELECT count(*), coalesce(md5(string_agg(md5(t::text), '' ORDER BY "
                "md5(t::text))), '') FROM {} t").format(psycopg.sql.SQL(table))).fetchone()
            found[table] = list(row)
    return found


def index_checksum(v1) -> dict:
    """The index's documents and its own write counters (nothing indexed or deleted)."""
    documents = OpenSearchDocuments(INDEX_URL, v1.dataset["index"])()
    with httpx.Client(base_url=INDEX_URL, timeout=30, trust_env=False) as client:
        stats = client.get(f"/{v1.dataset['index']}/_stats/indexing").json()
    indexing = stats["_all"]["primaries"]["indexing"]
    digest = hashlib.sha256(b"".join(sorted(
        json.dumps(item, sort_keys=True).encode() for item in documents))).hexdigest()
    return {"documents": len(documents), "digest": digest,
            "indexTotal": indexing["index_total"], "deleteTotal": indexing["delete_total"]}


def bucket_listing(v1) -> list[tuple[str, int, str]]:
    """`list_objects_v2` over the whole bucket: each object's `Key`, `Size` and `ETag`."""
    import boto3
    from botocore.config import Config

    s3 = boto3.client("s3", endpoint_url=OBJECTS_URL,
                      aws_access_key_id=v1.secret["objectsUser"],
                      aws_secret_access_key=v1.secret["objectsPassword"],
                      region_name="ap-northeast-2", config=Config(signature_version="s3v4"))
    listed, token = [], None
    while True:
        options = {"Bucket": v1.dataset["bucket"]}
        if token:
            options["ContinuationToken"] = token
        page = s3.list_objects_v2(**options)
        listed += [(item["Key"], item["Size"], item["ETag"]) for item in page.get("Contents", [])]
        if not page.get("IsTruncated"):
            break
        token = page["NextContinuationToken"]
    return listed


def table_digests(conn) -> dict:
    """Each table's row count and its rows' digest in a fixed order (the query of
    `database_checksum`), read in UTC so two instances print times alike."""
    conn.execute("SET TIME ZONE 'UTC'")
    found = {}
    tables = [row[0] for row in conn.execute(
        "SELECT quote_ident(schemaname)||'.'||quote_ident(tablename) FROM pg_tables "
        "WHERE schemaname NOT IN ('pg_catalog','information_schema') ORDER BY 1")]
    for table in tables:
        row = conn.execute(psycopg.sql.SQL(
            "SELECT count(*), coalesce(md5(string_agg(md5(t::text), '' ORDER BY "
            "md5(t::text))), '') FROM {} t").format(psycopg.sql.SQL(table))).fetchone()
        found[table] = list(row)
    return found


def objects_checksum(v1) -> dict:
    listed = bucket_listing(v1)
    return {"objects": len(listed),
            "digest": hashlib.sha256(json.dumps(sorted(listed)).encode()).hexdigest()}


def v1_checksums(v1) -> dict:
    return {"database": database_checksum(v1), "index": index_checksum(v1),
            "objects": objects_checksum(v1)}


@pytest.fixture(scope="module")
def v1(realm):
    run = Path(realm.root)
    value = tj.SyntheticV1(run, json.loads(private_bytes(run / "v1" / "dataset.json")),
                           json.loads(private_bytes(run / "v1" / "credentials.json")))
    if synthetic_v1.supervisor_pid() is None or not value.ready():
        pytest.fail("the synthetic v1 is not serving; the phase runs v1-up first")
    return value


@pytest.fixture
def stage(tmp_path, realm, clock, v1):
    value = Stage(tmp_path, realm, clock, v1)
    yield value
    value.cleanup()


# --- 1 and 2. a dry run through it, with the realm platform's parity; v1 unchanged -----------


def copied_parts(stage, tool, reported: dict, snapshot: dict) -> None:
    """U8 plan Step 90(f) (L1-37): what the reported run copied from the served v1, read
    back before your decision."""
    import u8_fixtures
    from backend.modules.operations.migration.v1_source import LISTING_MEMBER, split_listing
    from docsuri_ops.backup_agent.archives import unpack_bytes

    v1 = stage.v1
    listed = bucket_listing(v1)
    keys = {key for key, _, _ in listed}
    dataset = u8_fixtures.v1_dataset(Path(stage.realm.root))
    assert set(dataset.objects()) <= keys
    assert "assets/2101.00001/v1/fig1.webp" in keys
    assert len([key for key in keys if key.startswith("uploads/")]) == 1
    assert "doc-model/2109.99999/v1.json" in keys
    # The objects and index parts, read back through the platform's own `stream_back`.
    parts = tool.platform.snapshot.verified_parts(snapshot)
    archives = {}
    for part in ("index", "objects"):
        spool = tool.platform.spool / f"read-back.{part}"
        try:
            tool.platform.stream_back(parts[part], spool)
            archives[part] = unpack_bytes(spool.read_bytes())
        finally:
            spool.unlink(missing_ok=True)
    objects = archives["objects"]
    assert LISTING_MEMBER in objects
    assert sorted((item["key"], item["size"], item["etag"]) for item in split_listing(
        objects[LISTING_MEMBER])) == sorted(listed)
    assert set(objects) - {LISTING_MEMBER} == {key for key in keys
                                               if key.startswith("doc-model/")}
    assert "doc-model/2101.00006/v1.json" in objects
    copied = [json.loads(line) for line in archives["index"]["documents.jsonl"].splitlines()
              if line.strip()]
    read = OpenSearchDocuments(INDEX_URL, v1.dataset["index"])()

    def canonical(items):
        return sorted(json.dumps(item, sort_keys=True) for item in items)

    assert canonical(copied) == canonical(read) and read
    # The run's import database holds every v1 table, row for row.
    (record,) = [item for item in stage.copies.undisposed("import-database")
                 if item["sourceRef"] == f"run:{reported['runId']}"]
    name = record["locations"][0].removeprefix("database/")
    with v1.connect() as conn:
        expected = table_digests(conn)
    with rf.admin(stage.realm, name) as conn:
        assert table_digests(conn) == expected


def index_only_paper_landed(stage, ours: dict) -> None:
    """U8 plan Step 90(j) (L1-57; Step 68(f)): the paper only the served v1's index names
    landed from the copy's objects part, with its figure the one misfit naming it."""
    import uuid

    import u8_fixtures

    with stage.v1.connect() as conn:
        assert conn.execute("SELECT count(*) FROM paper_version_state WHERE paper_id=%s",
                            ("2101.00006",)).fetchone()[0] == 0
    paper = next(kind for kind in ours["kinds"] if kind["kind"] == "paper")
    assert paper["source"] == 7 and paper["imported"] == 4
    misfits = [item for kind in ours["kinds"] for item in kind["misfits"]]
    assert [(item["kind"], item["reasonKey"]) for item in misfits
            if item["sourceId"] == "2101.00006:v1"] == [("paper-figure", "no-v2-home")]
    saved_8 = str(uuid.uuid5(u8_fixtures.NAMESPACE, "v1-saved:saved-8"))
    assert not [item for item in misfits if item["sourceId"] == saved_8]
    assert not [item for item in misfits if item["sourceId"].startswith("2109.99999")]


def test_a_dry_run_through_it_reports_the_realm_platforms_parity_and_leaves_v1_unchanged(
        stage, tmp_path):
    before = v1_checksums(stage.v1)
    tool = stage.production_tool(environment_file(tmp_path, stage.v1.dataset, stage.v1.secret))
    reported = stage.dry_run(tool)
    assert reported["state"] == "reported", reported
    record = stage.ledger.get("parity-report", reported["runId"])
    assert record["reconciles"] is True
    # The agent read v1 at the named address, and the receipt says so.
    snapshot = stage.copies.get(stage.runs.require(reported["runId"])["snapshotCopyId"])
    assert snapshot["completedAt"] and snapshot["checksum"]
    ours = stage.report(tool, reported["runId"])
    copied_parts(stage, tool, reported, snapshot)
    index_only_paper_landed(stage, ours)
    # One run at a time: your decision ends this one before the realm platform's starts.
    accepted = tool.decide(reported["runId"], rf.decide(
        stage.operator, stage.ledger, stage.clock, "dry-run-report", reported["runId"]))
    assert accepted["state"] == "accepted"
    # The realm's platform over the same v1: the same parity, kind for kind.
    realm_tool = stage.realm_tool()
    realm_run = stage.dry_run(realm_tool)
    assert realm_run["state"] == "reported", realm_run
    theirs = stage.report(realm_tool, realm_run["runId"])
    assert ours["kinds"] == theirs["kinds"] and ours["reconciles"] is True
    assert {kind["kind"] for kind in ours["kinds"]} >= {"account", "paper", "saved-paper"}
    # v1's three stores hold exactly what they held before: nothing was written to v1.
    assert v1_checksums(stage.v1) == before


# --- 3. an address the environment file does not name is refused ------------------------------


def test_a_database_the_environment_file_does_not_name_is_refused_before_any_copy(
        stage, tmp_path):
    other = environment_file(tmp_path, stage.v1.dataset, stage.v1.secret,
                             database={"port": synthetic_v1.PORTS["postgres"][0] + 1})
    tool = stage.production_tool(other)
    failed = stage.dry_run(tool)
    # The agent refused before it connected: its v1 login reaches another address.
    assert failed["state"] == "failed" and failed["reason"] == "v1-source-not-named", failed
    assert not list((stage.tmp / "volume" / "docsuri-v2" / "archives").glob("*"))


def test_the_index_and_object_store_admit_only_reads_at_the_named_origin(stage, tmp_path):
    import boto3
    from botocore.config import Config

    sources = production.V1Sources.from_config(
        environment_file(tmp_path, stage.v1.dataset, stage.v1.secret))
    before = {"index": index_checksum(stage.v1), "objects": objects_checksum(stage.v1)}
    transport = production.ReadOnlyIndexTransport(sources)
    with httpx.Client(transport=transport, timeout=10, trust_env=False) as client:
        for method, url in (("POST", f"http://127.0.0.1:{19210}/{sources.index_name}/_search"),
                            ("POST", f"http://localhost:19209/{sources.index_name}/_search")):
            with pytest.raises(SnapshotRefused, match="v1-address-not-named"):
                client.request(method, url, json={})
        for method, path in (("PUT", f"/{sources.index_name}/_doc/x"),
                             ("DELETE", f"/{sources.index_name}"),
                             ("POST", f"/{sources.index_name}/_delete_by_query")):
            with pytest.raises(SnapshotRefused, match="v1-write-refused"):
                client.request(method, INDEX_URL + path, json={"query": {"match_all": {}}})
    s3 = boto3.client("s3", endpoint_url=OBJECTS_URL,
                      aws_access_key_id=stage.v1.secret["objectsUser"],
                      aws_secret_access_key=stage.v1.secret["objectsPassword"],
                      region_name="ap-northeast-2", config=Config(signature_version="s3v4"))
    objects = production.read_only_objects(sources, client_factory=lambda: s3)
    assert objects()  # every document model, read
    with pytest.raises(SnapshotRefused, match="v1-write-refused"):
        s3.put_object(Bucket=sources.bucket, Key="docmodel/written.json", Body=b"{}")
    with pytest.raises(SnapshotRefused, match="v1-write-refused"):
        s3.delete_object(Bucket=sources.bucket, Key="docmodel/written.json")
    with pytest.raises(SnapshotRefused, match="v1-address-not-named"):
        objects.client.list_objects_v2(Bucket="another-bucket")
    assert {"index": index_checksum(stage.v1), "objects": objects_checksum(stage.v1)} == before


@pytest.mark.parametrize("override", [
    {"database": {"host": "192.168.1.10"}},
    {"database": {"port": 15432}},  # v2's own database is never v1
    {"index": {"url": "https://127.0.0.1:19209"}},
    {"index": {"url": "http://search.example.com:9200"}},
    {"objects": {"url": "http://127.0.0.1"}},
    {"objects": {"credentials": "relative/v1-objects.json"}},
])
def test_the_environment_file_names_loopback_addresses_only(tmp_path, override):
    dataset = {"index": "docsuri-corpus", "bucket": "docsuri-v1"}
    login = {"objectsUser": "u", "objectsPassword": secrets.token_hex(8)}  # per run (L1-36)
    config = environment_file(tmp_path, dataset, login, **override)
    with pytest.raises(production.SourcesRefused):
        production.V1Sources.from_config(config)
    with pytest.raises(production.SourcesRefused, match="v1-sources-unconfigured"):
        production.V1Sources.from_config({"kind": "arrangement"})


# --- 4. the cutover's final run takes it --------------------------------------------------------


class StandInNames:
    """The realm's names with a production stand-in of the test's own."""

    def __init__(self, production_name: str):
        self.production, self.prefix = production_name, "docsuri_u8"

    def kind_of(self, name: str):
        return "production" if name == self.production else REALM_DATABASES.kind_of(name)

    def new(self, kind: str) -> str:
        return REALM_DATABASES.new(kind)

    def pattern(self, kind: str):
        return REALM_DATABASES.pattern(kind)


def test_the_cutovers_final_run_takes_it(stage, tmp_path, realm):
    config = environment_file(tmp_path, stage.v1.dataset, stage.v1.secret)
    tool = stage.production_tool(config)
    dry = stage.dry_run(tool)
    assert dry["state"] == "reported", dry
    tool.decide(dry["runId"], rf.decide(stage.operator, stage.ledger, stage.clock,
                                        "dry-run-report", dry["runId"]))
    # What the first dry run met beyond Workflow 10's table is decided archive-only, and
    # a dry run under the decisions current then is accepted before the switch.
    current = MisfitDecisions(stage.ledger, clock=stage.clock)
    for kind, reason in current.current().undecided(stage.runs.met_pairs(dry["runId"])):
        approval = rf.approval_record(stage.ledger, "misfit-decision", f"{kind}:{reason}",
                                      now=stage.clock())
        current.decide(kind, reason, "archive-only", approval_id=approval["approvalId"])
    if not stage.runs.dry_run_current():
        again = stage.dry_run(tool)
        tool.decide(again["runId"], rf.decide(stage.operator, stage.ledger, stage.clock,
                                              "dry-run-report", again["runId"]))
    assert stage.runs.dry_run_current()
    production_name = REALM_DATABASES.new("rehearsal")
    stage.databases.create_rehearsal(production_name)
    names = StandInNames(production_name)
    base = realm_facts(stage.journey.profile, stage.ledger, clock=stage.clock)

    def facts():
        found = base()
        found.names = names
        return found

    operator = realm_operator(stage.journey.profile, "operator", stage.ledger,
                              clock=stage.clock, facts=facts)
    tool.platform.operator, tool.platform.names = operator, names
    cutover = rf.cutover_record(stage.ledger, "preparing")
    for state in ("rehearsing", "ready-to-switch", "switching"):
        cutover = rf.advance_cutover(stage.ledger, cutover, state)
    approval = rf.decide(operator, stage.ledger, stage.clock, "switch-start",
                         cutover["cutoverId"])
    before = v1_checksums(stage.v1)
    try:
        # The cutover's `final_run` and `final_decide`, as production wires them.
        reported = production.final_run_for(tool)(approval, stage.clock() + dt.timedelta(days=30))
        assert reported["state"] == "reported" and reported["kind"] == "final", reported
        assert stage.ledger.get("parity-report", reported["runId"])["reconciles"] is True
        accepted = production.final_decide_for(tool)(reported["runId"], rf.decide(
            operator, stage.ledger, stage.clock, "final-report", reported["runId"]))
        assert accepted["state"] == "accepted"
        snapshot = stage.copies.get(accepted["snapshotCopyId"])
        assert snapshot["kind"] == "v1-final-snapshot" and "disposedAt" not in snapshot
        accounts = next(kind for kind in stage.report(tool, reported["runId"])["kinds"]
                        if kind["kind"] == "account")
        assert accounts["imported"] > 0
        with rf.admin(realm, production_name) as conn:
            assert conn.execute("SELECT count(*) FROM accounts.account").fetchone()[0] == (
                accounts["imported"])
        assert v1_checksums(stage.v1) == before
    finally:
        rf.drop_database(realm, production_name)
