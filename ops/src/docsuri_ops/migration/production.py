"""The production migration platform (the person's decision of 2026-10-24, "Build it, test
on test v1"; U8 plan Step 31; BR8.2, BR8.11, BR9.12, BR9.17, D4–D6).

`migration … --production` and the cutover's final run take this platform. It reads v1
read-only, at the addresses the production environment file names and at no other:

- **The environment file** is the operator's arrangement-driver configuration
  (`/Library/DocSuri/control/effects/operator/driver.json`, root-written by the
  installer, paths and addresses only, never a secret). Its `v1Sources` names v1's
  PostgreSQL (`database`: loopback host, port, database name), its search index
  (`index`: loopback URL and index name) and its object store (`objects`: loopback URL,
  bucket, and the absolute path of your login's private credentials file for it).
  `V1Sources.from_config` refuses anything else, and refuses v2's own database port.
- **v1's PostgreSQL** is dumped by the backup agent's in-person `snapshot` through its
  read-only login (`pg_read_all_data`). The word carries the named address
  (`v1Source`): the agent refuses before any connection when its own v1 login reaches
  another, and the dump's receipt names where it read from, which is checked again.
- **v1's search index** is read through a transport that admits only the scroll API's
  two read requests at the named origin (`ReadOnlyIndexTransport`).
- **v1's object store** is read through a client that admits only `GET` and `HEAD` at
  the named origin, and exposes only listing and reading the named bucket
  (`ReadOnlyBucket`).

v2's side runs through the production environment tool and the import program, in
person (`ToolDatabases`, `ProgramImporter`): the rehearsal and import databases are
created by `docsuri-production-tool create-disposable` as the disposable-databases role,
which then owns them (a rehearsal database is the template copied whole), the snapshot's
dump is restored into the import database by `restore-import`, the owners' imports run
as the service account through `docsuri-migration-import`, and a final run's production
database is the template copied whole by `prepare-production`.

The first real read is the first dry run, with you present, at the Operation stages.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import stat
import subprocess
from collections.abc import Callable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import httpx

from .snapshot import BucketObjects, OpenSearchDocuments, SnapshotRefused

SOURCES_KEY = "v1Sources"
LOOPBACK = "127.0.0.1"
V2_DATABASE_PORT = 15432
_NAME = re.compile(r"[a-z][a-z0-9_]{1,62}")
_INDEX = re.compile(r"[a-z0-9][a-z0-9._-]{0,254}")
_BUCKET = re.compile(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]")
MAX_CREDENTIALS = 4096
# v1's own object-store client signs for this region (v1's `AWS_REGION`).
OBJECTS_REGION = "ap-northeast-2"
IMPORT_SECONDS = 7200
IMPORT_PROGRAM = "/Library/DocSuri/release/ops/bin/docsuri-migration-import"
SUDO = "/usr/bin/sudo"


class SourcesRefused(SnapshotRefused):
    """The environment file's `v1Sources` is missing or outside its form."""


# --- the addresses the environment file names ---------------------------------------------


def _origin(url: str) -> tuple[str, str, int]:
    parts = urlsplit(url)
    if parts.scheme != "http" or parts.hostname != LOOPBACK or parts.port is None or (
        parts.path not in ("", "/") or parts.query or parts.fragment or parts.username
    ):
        raise SourcesRefused("v1-address-not-loopback")
    return parts.scheme, parts.hostname, parts.port


@dataclass(frozen=True)
class V1Sources:
    database: Mapping  # {"host", "port", "database"}
    index_url: str
    index_name: str
    objects_url: str
    bucket: str
    credentials: Path

    @classmethod
    def from_config(cls, config: Mapping) -> V1Sources:
        value = config.get(SOURCES_KEY)
        if not isinstance(value, dict) or set(value) != {"database", "index", "objects"}:
            raise SourcesRefused("v1-sources-unconfigured")
        database, index, objects = value["database"], value["index"], value["objects"]
        if not isinstance(database, dict) or set(database) != {"host", "port", "database"}:
            raise SourcesRefused("v1-database-address-refused")
        port = database["port"]
        if database["host"] != LOOPBACK or type(port) is not int or not 1 <= port <= 65535 or (
            port == V2_DATABASE_PORT
        ) or not _NAME.fullmatch(str(database["database"])):
            raise SourcesRefused("v1-database-address-refused")
        if not isinstance(index, dict) or set(index) != {"url", "name"} or not _INDEX.fullmatch(
            str(index["name"])
        ):
            raise SourcesRefused("v1-index-address-refused")
        if not isinstance(objects, dict) or set(objects) != {"url", "bucket", "credentials"} or (
            not _BUCKET.fullmatch(str(objects["bucket"]))
        ) or not Path(str(objects["credentials"])).is_absolute():
            raise SourcesRefused("v1-objects-address-refused")
        _origin(str(index["url"]))
        _origin(str(objects["url"]))
        return cls({"host": LOOPBACK, "port": port, "database": str(database["database"])},
                   str(index["url"]).rstrip("/"), str(index["name"]),
                   str(objects["url"]).rstrip("/"), str(objects["bucket"]),
                   Path(str(objects["credentials"])))

    def require_database(self, source) -> None:
        if source != dict(self.database):
            raise SnapshotRefused("v1-address-not-named")

    def require_origin(self, kind: str, scheme: str, host: str | None, port: int | None) -> None:
        named = _origin(self.index_url if kind == "index" else self.objects_url)
        if (scheme, host, port) != named:
            raise SnapshotRefused("v1-address-not-named")


# --- v1's database, through the agent's read-only login -----------------------------------


def named_dump(sources: V1Sources, agent_word: Callable[..., dict]):
    """The agent's in-person `snapshot`, carrying the named address of v1's database: the
    agent refuses before any connection when its v1 login reaches another one."""

    def dump(kind: str, record_id: str, decided: dict | None) -> dict:
        document = {"kind": kind, "recordId": record_id, "v1Source": dict(sources.database)}
        if decided is not None:
            document["decided"] = decided
        from docsuri_ops.u8_platform.drivers import DriverRefused

        try:
            receipt = agent_word("snapshot", document, via="in-person")
        except DriverRefused as refused:
            # The agent's refusal (`v1-source-not-named` among them) fails the run.
            raise SnapshotRefused(refused.reason) from None
        sources.require_database(receipt.get("source"))
        return receipt

    return dump


# --- v1's search index, read only ---------------------------------------------------------


class ReadOnlyIndexTransport(httpx.BaseTransport):
    """Admits only the scroll API's two reads (`POST /<index>/_search?scroll=…` and
    `POST /_search/scroll`) at the named origin; anything else is refused before it is
    sent."""

    def __init__(self, sources: V1Sources, inner=None):
        self.sources = sources
        self.inner = inner if inner is not None else httpx.HTTPTransport()

    def handle_request(self, request):
        url = request.url
        self.sources.require_origin("index", url.scheme, url.host, url.port)
        reads = {f"/{self.sources.index_name}/_search", "/_search/scroll"}
        if request.method != "POST" or url.path not in reads:
            raise SnapshotRefused("v1-write-refused")
        return self.inner.handle_request(request)

    def close(self) -> None:
        self.inner.close()


def read_only_index(sources: V1Sources, *, inner_factory: Callable | None = None):
    return OpenSearchDocuments(
        sources.index_url, sources.index_name,
        transport_factory=lambda: ReadOnlyIndexTransport(
            sources, inner_factory() if inner_factory is not None else None))


# --- v1's object store, read only ---------------------------------------------------------


def objects_credentials(path: Path) -> dict:
    """Your login's private credentials for v1's object store: a regular file of yours,
    0600 or tighter, never through a link, `{"accessKey", "secretKey"}`."""
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        raise SourcesRefused("v1-objects-credentials-unreadable") from None
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or (
            info.st_mode & 0o077
        ) or info.st_size > MAX_CREDENTIALS:
            raise SourcesRefused("v1-objects-credentials-refused")
        value = json.loads(os.read(descriptor, MAX_CREDENTIALS))
    except ValueError:
        raise SourcesRefused("v1-objects-credentials-refused") from None
    finally:
        os.close(descriptor)
    if not isinstance(value, dict) or set(value) != {"accessKey", "secretKey"} or not all(
        isinstance(item, str) and item for item in value.values()
    ):
        raise SourcesRefused("v1-objects-credentials-refused")
    return value


class ReadOnlyBucket:
    """Only listing and reading the named bucket; no other client method is reachable."""

    def __init__(self, client, bucket: str):
        self._client, self._bucket = client, bucket

    def _require(self, bucket) -> None:
        if bucket != self._bucket:
            raise SnapshotRefused("v1-address-not-named")

    def list_objects_v2(self, **options):
        self._require(options.get("Bucket"))
        return self._client.list_objects_v2(**options)

    def get_object(self, *, Bucket, Key):  # noqa: N803 - the S3 client's own names
        self._require(Bucket)
        return self._client.get_object(Bucket=Bucket, Key=Key)


def guard_requests(sources: V1Sources):
    """botocore's `before-send` hook: only GET and HEAD, only at the named origin."""

    def before_send(request, **_):
        parts = urlsplit(request.url)
        sources.require_origin("objects", parts.scheme, parts.hostname, parts.port)
        if request.method not in ("GET", "HEAD"):
            raise SnapshotRefused("v1-write-refused")
        return None

    return before_send


def read_only_objects(sources: V1Sources, *, client_factory: Callable | None = None):
    """v1's document models through an S3 client of the named object store, read only."""
    if client_factory is None:
        import boto3
        from botocore.config import Config

        secret = objects_credentials(sources.credentials)
        client = boto3.client("s3", endpoint_url=sources.objects_url,
                              aws_access_key_id=secret["accessKey"],
                              aws_secret_access_key=secret["secretKey"],
                              region_name=OBJECTS_REGION,
                              config=Config(signature_version="s3v4", retries={"max_attempts": 2},
                                            s3={"addressing_style": "path"}))
    else:
        client = client_factory()
    client.meta.events.register("before-send.s3", guard_requests(sources))
    return BucketObjects(ReadOnlyBucket(client, sources.bucket), sources.bucket)


# --- v2's side, through the production environment tool and the import program -------------


class ToolRefused(RuntimeError):
    """A word of the production environment tool or the import program refused."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass
class ToolDatabases:
    """The run's databases on v2's instance: created, restored into and prepared by the
    production environment tool in person; read through the operator tool's login."""

    invoke: Callable[..., dict]  # production_tool.invoke, its login released in person
    connect: Callable[[str], object]  # the operator tool's login, one database

    def _word(self, word: str, document: dict, payload: bytes | None = None) -> dict:
        from docsuri_ops.production_tool import Refused

        try:
            return self.invoke(word, {**document, "operationId": str(uuid4())},
                               login="operator", payload=payload)
        except Refused as refused:
            raise ToolRefused(refused.reason) from None

    def create_rehearsal(self, name: str) -> None:
        self._word("create-disposable", {"database": name})

    def create_import(self, name: str) -> None:
        self._word("create-disposable", {"database": name})

    def restore_import(self, name: str, spool: Path) -> None:
        payload = spool.read_bytes()
        self._word("restore-import", {"database": name,
                                      "sha256": hashlib.sha256(payload).hexdigest()}, payload)

    def prepare_production(self, name: str) -> None:
        self._word("prepare-production", {"database": name})

    def database_bytes(self, name: str) -> int:
        with self.connect("postgres") as conn:
            row = conn.execute("SELECT pg_database_size(datname) FROM pg_database "
                               "WHERE datname=%s", (name,)).fetchone()
        return 0 if row is None else int(row[0])

    @contextmanager
    def import_reader(self, name: str):
        from psycopg.rows import dict_row

        with self.connect(name) as conn:
            conn.row_factory = dict_row
            yield conn


class ProgramImporter:
    """The import phases as the service account, in person: `sudo -k -u <service>
    docsuri-migration-import <word>`, the operator tool's login released in person and
    handed on in the header line only, then the snapshot's two archives."""

    def __init__(self, *, release: Callable | None = None, run: Callable = subprocess.run,
                 program: str = IMPORT_PROGRAM, account: str | None = None):
        self.release, self.run, self.program = release, run, program
        self.account = account

    def __call__(self, word: str, request: dict) -> dict:
        from docsuri_ops.arrangement.paths import Accounts
        from docsuri_ops.u8_platform.credential_release import release as release_login

        if word not in ("import", "idempotency"):
            raise ToolRefused("word-refused")
        archives = request["archives"]
        payload = archives["index"] + archives["objects"]
        header = {key: value for key, value in request.items() if key != "archives"}
        header["archives"] = {"index": len(archives["index"]),
                              "objects": len(archives["objects"])}
        secret = (self.release or release_login)("operator")
        try:
            header["login"] = {"password": secret.decode()}
            body = json.dumps(header).encode() + b"\n" + payload
        finally:
            secret[:] = b"\0" * len(secret)
        account = self.account or Accounts.standard().service.name
        completed = self.run([SUDO, "-k", "-u", account, self.program, word], input=body,
                             capture_output=True, timeout=IMPORT_SECONDS, check=False)
        try:
            result = json.loads(completed.stdout.decode().splitlines()[-1])
        except (ValueError, IndexError):
            raise ToolRefused("import-answered-no-result") from None
        if completed.returncode != 0 or not result.get("ok"):
            raise ToolRefused(str(result.get("reason", "import-refused")))
        return result


# --- the platform -------------------------------------------------------------------------


def production_migration_platform(operator, *, sources: V1Sources, names, driver, databases,
                                  importer, isolation, disk, spool: Path, evidence: Path,
                                  installed: Callable[[], bool], copies,
                                  index_reader=None, objects_reader=None):
    """The MigrationPlatform that reads v1 only at `sources`. `driver` gives the backup
    agent's words (`agent_word`, `snapshot_stream`, `stream_back`); `databases` v2's side
    (`ToolDatabases` in production); `importer` the import phases (`ProgramImporter` in
    production, or None for the owners' imports in this process through
    `databases.owners_for`)."""
    from .snapshot import Snapshot
    from .tool import MigrationPlatform

    spool.mkdir(mode=0o700, parents=True, exist_ok=True)
    snapshot = Snapshot(
        copies, dump=named_dump(sources, driver.agent_word), stream=driver.snapshot_stream,
        index=index_reader or read_only_index(sources),
        objects=objects_reader or read_only_objects(sources), evidence=evidence)
    return MigrationPlatform(
        operator=operator, names=names, snapshot=snapshot,
        create_rehearsal=databases.create_rehearsal, create_import=databases.create_import,
        restore_import=databases.restore_import, import_reader=databases.import_reader,
        owners_for=getattr(databases, "owners_for", None), stream_back=driver.stream_back,
        isolation=isolation, disk=disk, spool=spool, evidence=evidence, installed=installed,
        database_bytes=databases.database_bytes,
        prepare_production=databases.prepare_production, importer=importer)


def production_migration_tool(ledger, operator, *, clock: Callable[[], dt.datetime],
                              paths=None, release: Callable | None = None):
    """The migration tool on this Mac, in person: the operator's environment file names
    v1's stores, the arrangement driver runs the agent's words, the production
    environment tool and the import program run v2's side, and the operator's own
    evidence folder holds the run's parity reports."""
    from backend.modules.operations.migration_records import MigrationRuns
    from backend.modules.operations.retained_copies import RetainedCopies
    from backend.u8_policy import PRODUCTION_OPERATIONS as policy

    from docsuri_ops.arrangement.paths import (
        DATABASE_ROLES,
        PRODUCTION_DATABASES,
        ArrangementPaths,
    )
    from docsuri_ops.production_tool import invoke
    from docsuri_ops.production_wiring import (
        _connector,
        _released,
        arrangement_driver,
        free_space,
    )
    from docsuri_ops.u8_platform.drivers import load_config

    from .disk_guard import DiskGuard
    from .isolation_gate import IsolationGate
    from .tool import MigrationTool
    from .words import _commit

    paths = paths or ArrangementPaths()
    folder = paths.effects / "operator"
    sources = V1Sources.from_config(load_config(folder))
    driver = arrangement_driver(paths, "operator", release=release)
    copies = RetainedCopies(ledger, policy, clock=clock)
    connect = _connector(DATABASE_ROLES.operator, _released("operator", release))

    def run_word(word, document, *, login=None, payload=None):
        return invoke(word, document, login=login, payload=payload, release=release)

    platform = production_migration_platform(
        operator, sources=sources, names=PRODUCTION_DATABASES, driver=driver,
        databases=ToolDatabases(run_word, connect), importer=ProgramImporter(release=release),
        isolation=IsolationGate(paths.isolation_evidence,
                                freshness_seconds=policy.isolation_freshness_seconds,
                                clock=clock),
        disk=DiskGuard(lambda: free_space(paths), policy.internal_disk_threshold_bytes,
                       policy.internal_disk_critical_bytes),
        spool=folder / "migration-spool", evidence=folder / "evidence" / "migration",
        installed=lambda: paths.arrangement_manifest.is_file(), copies=copies)
    return MigrationTool(MigrationRuns(ledger, clock=clock), copies, platform, clock=clock,
                         tool_commit=_commit(paths.release))


# --- the cutover's final run --------------------------------------------------------------


def final_run_for(tool) -> Callable[[str, dt.datetime], dict]:
    """The cutover's `final_run`: a final run started inside the switch on your
    `switch-start` decision, driven to its report (or until it stops)."""

    def final_run(approval_id: str, dispose_after: dt.datetime) -> dict:
        run = tool.start_final(approval_id=approval_id, dispose_after=dispose_after)
        return tool.run(run["runId"])

    return final_run


def final_decide_for(tool) -> Callable[[str, str], dict]:
    """The cutover's `final_decide`: your `final-report` decision applied to the run."""

    def final_decide(run_id: str, approval_id: str) -> dict:
        return tool.decide(run_id, approval_id)

    return final_decide
