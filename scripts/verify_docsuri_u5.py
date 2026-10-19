"""Bounded, explicitly owned U5 synthetic-local experiments.

Never adopts another realm, extends retention, changes old containers or treats
missing/zero/skipped execution as success. Setup and migrations are explicit;
test phases inspect established resources and preserve failed evidence.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import secrets
import selectors
import shutil
import signal
import socket
import ssl
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from contextlib import contextmanager, nullcontext
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "ops/src"))

from bootstrap_docsuri_u1 import SCHEMAS, amend
from verify_docsuri_u1 import GIB, IMAGE, LOCKS, Refused, command, digest, headroom
from verify_docsuri_u1 import source_identity as base_source_identity
from verify_docsuri_u3 import stop
from verify_docsuri_u4 import MIGRATIONS as U4_MIGRATIONS

from backend.local_profile import LocalProfile, private_bytes

RUN = Path("/tmp/docsuri-u5-run").resolve()
_RUNNER_OWNED = False
PYTHON = ROOT / "backend/.venv/bin/python"
UNIT = "u5-topics-digests"
REALM = "topics-digests"
DATABASE = "docsuri_u5"
DATABASE_PORT = 15489
APPLICATION_PORT = 18089
LABEL = "dev.docsuri.u5.run"
POLICY = "u5-synthetic-v1"
MAX_LOG = 16 * 1024**2
MAX_RSS = GIB
DB_MEMORY = GIB
RECOVERY_MEMORY = 512 * 1024**2
OWNERS = frozenset(SCHEMAS) | {"research", "topics"}
MIGRATIONS = (
    *U4_MIGRATIONS,
    ("accounts", "backend/modules/accounts/u5_lifecycle_tables.sql"),
    ("accounts", "backend/modules/accounts/u2_lifecycle_effect.sql"),
    ("accounts", "backend/modules/accounts/u2_lifecycle_action.sql"),
    ("accounts", "backend/modules/accounts/u5_lifecycle_guard.sql"),
    ("corpus", "backend/modules/corpus/u5_digest_read.sql"),
    ("accounts", "backend/modules/accounts/u5_digest_recipient.sql"),
    ("topics", "backend/modules/topics/u5_schema.sql"),
    ("topics", "backend/modules/topics/u5_erasure.sql"),
    ("topics", "backend/modules/topics/u5_run_guard.sql"),
    ("personalization", "backend/modules/personalization/u5_digest_preferences.sql"),
    ("topics", "backend/modules/topics/u5_preference_snapshot.sql"),
    ("topics", "backend/modules/topics/u5_schedule.sql"),
    ("topics", "backend/modules/topics/u5_unsubscribe_capability.sql"),
)
TEST_PHASES = (
    "database",
    "repository",
    "component",
    "integration",
    "operations",
    "coverage",
)
PHASES = (
    "setup",
    "migrate",
    "fixtures",
    "archive-owned",
    *TEST_PHASES,
    "frontend",
    "browser",
    "serve",
    "teardown",
)


def require(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    result = command(args, **kwargs)
    if result.returncode:
        raise Refused(f"command failed ({result.returncode}): {args[0]}")
    return result


def private_json(path: Path, value: object) -> None:
    if path.parent != RUN or path.is_symlink():
        raise Refused("private output outside owned run")
    info = RUN.lstat()
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o700
    ):
        raise Refused("run directory custody differs")
    pending = path.with_name(path.name + ".pending-" + secrets.token_hex(8))
    descriptor = os.open(
        pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
    )
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump(value, stream, sort_keys=True, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(pending, path)
        directory = os.open(RUN, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        pending.unlink(missing_ok=True)


@contextmanager
def exclusive():
    """One U5 runner phase, including setup and preservation, across processes."""
    global _RUNNER_OWNED
    path = RUN.parent / ".docsuri-u5-runner.lock"
    descriptor = os.open(
        path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600
    )
    acquired = False
    try:
        info = os.fstat(descriptor)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_nlink != 1
        ):
            raise Refused("runner lock custody differs")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise Refused("another U5 phase is active") from error
        os.ftruncate(descriptor, 0)
        os.write(descriptor, str(os.getpid()).encode())
        os.fsync(descriptor)
        _RUNNER_OWNED = True
        acquired = True
        yield
    finally:
        if acquired:
            _RUNNER_OWNED = False
        os.close(descriptor)


@contextmanager
def browser_clock_delegation(value: dict, seconds: float):
    """Delegate only fixture-clock writes while the browser parent retains custody."""
    if not _RUNNER_OWNED or not 0 < seconds <= 300:
        raise Refused("clock delegation requires bounded runner ownership")
    token = secrets.token_urlsafe(32)
    target = RUN / "browser-clock-delegation.json"
    private_json(
        target,
        {
            "runId": value["runId"],
            "ownerPid": os.getpid(),
            "expiresAt": min(value["expiresAt"], time.time() + seconds),
            "tokenHash": hashlib.sha256(token.encode()).hexdigest(),
        },
    )
    try:
        yield token
    finally:
        target.unlink(missing_ok=True)


def authorize_clock_child(value: dict) -> None:
    """Validate a private browser capability without taking its parent's lock."""
    token = os.environ.get("DOCSURI_U5_CLOCK_CAPABILITY", "")
    if not 1 <= len(token) <= 128:
        raise Refused("clock delegation unavailable")
    grant = json.loads(private_bytes(RUN / "browser-clock-delegation.json"))
    if (
        not isinstance(grant, dict)
        or type(grant.get("ownerPid")) is not int
        or grant["ownerPid"] <= 0
        or type(grant.get("expiresAt")) not in (int, float)
        or not isinstance(grant.get("tokenHash"), str)
        or re.fullmatch(r"[a-f0-9]{64}", grant["tokenHash"]) is None
    ):
        raise Refused("clock delegation malformed")
    if (
        grant.get("runId") != value["runId"]
        or not time.time() < grant.get("expiresAt", 0) <= value["expiresAt"]
        or not secrets.compare_digest(
            grant.get("tokenHash", ""), hashlib.sha256(token.encode()).hexdigest()
        )
    ):
        raise Refused("clock delegation differs or expired")
    lock = RUN.parent / ".docsuri-u5-runner.lock"
    owner = private_bytes(lock).decode()
    if owner != str(grant.get("ownerPid")):
        raise Refused("clock delegation owner differs")
    os.kill(int(owner), 0)
    descriptor = os.open(lock, os.O_RDWR | os.O_NOFOLLOW)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        raise Refused("clock delegation owner is inactive")
    finally:
        os.close(descriptor)


def manifest(path: Path) -> tuple[LocalProfile, dict]:
    profile = LocalProfile.load(path)
    value = json.loads(private_bytes(path))
    if (
        profile.root != RUN
        or profile.realm != REALM
        or profile.database_name != DATABASE
    ):
        raise Refused("U5 requires its own explicit realm")
    require_manifest_identity(value)
    return profile, value


def require_manifest_identity(value: dict) -> None:
    """Bind both runtime and preservation metadata to this runner's resources."""
    if value.get("databaseImage") != IMAGE or value.get("policy") != POLICY:
        raise Refused("U5 image or policy identity differs")
    if (
        value.get("container") != value["runId"]
        or value.get("volume") != value["runId"] + "-pgdata"
    ):
        raise Refused("U5 resource names differ from run identity")


def require_resources(value: dict) -> None:
    for kind, name in (("container", value["container"]), ("volume", value["volume"])):
        raw = require(["docker", kind, "inspect", name]).stdout
        records = json.loads(raw)
        if len(records) != 1:
            raise Refused("ambiguous U5 resource")
        record = records[0]
        labels = (
            record.get("Labels", {})
            if kind == "volume"
            else record["Config"].get("Labels", {})
        )
        if labels.get(LABEL) != value["runId"]:
            raise Refused("missing or foreign U5 resource; preserve for recovery")
        if kind == "container":
            host = record["HostConfig"]
            if (
                record["Config"]["Image"] != IMAGE
                or host["Memory"] != DB_MEMORY
                or host["MemorySwap"] != DB_MEMORY
                or host["NanoCpus"] != 1_000_000_000
                or host["PidsLimit"] != 64
                or not host["ReadonlyRootfs"]
                or host["PortBindings"]
                != {
                    "5432/tcp": [
                        {"HostIp": "127.0.0.1", "HostPort": str(DATABASE_PORT)}
                    ]
                }
                or not record["State"]["Running"]
            ):
                raise Refused("owned database bounds or running state differ")
            volumes = [item for item in record["Mounts"] if item["Type"] == "volume"]
            if (
                len(volumes) != 1
                or volumes[0]["Name"] != value["volume"]
                or volumes[0]["Destination"] != "/var/lib/postgresql/data"
            ):
                raise Refused("database volume binding differs")


def memory_available(raw: str) -> int:
    match = re.search(r"^MemAvailable:\s+(\d+) kB$", raw, re.MULTILINE)
    if match is None:
        raise Refused("Docker available memory could not be measured")
    return int(match[1]) * 1024


def preflight(*, established: bool = False) -> dict:
    headroom(existing=True)
    free = shutil.disk_usage(ROOT).free
    if free < 4 * GIB:
        raise Refused("U5 disk recovery reserve unavailable")
    require(["docker", "image", "inspect", IMAGE])
    info = json.loads(require(["docker", "info", "--format", "{{json .}}"]).stdout)
    if info["MemTotal"] < DB_MEMORY + RECOVERY_MEMORY:
        raise Refused("Docker memory cannot fit the database and recovery reserve")
    # Observe the daemon's kernel rather than macOS RAM. The cached probe has no
    # network, mounts, secrets or writable root and is bounded to 16 MiB/8 PIDs.
    raw = require(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--memory",
            "16m",
            "--memory-swap",
            "16m",
            "--cpus",
            "0.1",
            "--pids-limit",
            "8",
            "--entrypoint",
            "cat",
            IMAGE,
            "/proc/meminfo",
        ],
        timeout=15,
    ).stdout
    available = memory_available(raw)
    required = RECOVERY_MEMORY if established else DB_MEMORY + RECOVERY_MEMORY
    if available < required:
        raise Refused(
            f"Docker available bytes {available} below required allocation and reserve {required}"
        )
    return {
        "hostFreeBytes": free,
        "dockerTotalBytes": info["MemTotal"],
        "dockerAvailableBytes": available,
        "databaseLimitBytes": DB_MEMORY,
        "recoveryReserveBytes": RECOVERY_MEMORY,
    }


def check_ports() -> None:
    for port in (APPLICATION_PORT, DATABASE_PORT):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", port))


def require_stopped(port: int = APPLICATION_PORT) -> None:
    with socket.socket() as listener:
        if listener.connect_ex(("127.0.0.1", port)) == 0:
            raise Refused("stop the application before this phase")


def database_command(value: dict) -> list[str]:
    return [
        "docker",
        "run",
        "-d",
        "--name",
        value["container"],
        "--label",
        f"{LABEL}={value['runId']}",
        "--memory",
        "1g",
        "--memory-swap",
        "1g",
        "--cpus",
        "1",
        "--pids-limit",
        "64",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,size=16m",
        "--tmpfs",
        "/var/run/postgresql:rw,noexec,nosuid,size=16m",
        "-p",
        f"127.0.0.1:{DATABASE_PORT}:5432",
        "--mount",
        f"type=volume,src={value['volume']},dst=/var/lib/postgresql/data",
        "-e",
        "POSTGRES_PASSWORD",
        "-e",
        f"POSTGRES_DB={DATABASE}",
        "-e",
        "POSTGRES_INITDB_ARGS=--data-checksums --auth-host=scram-sha-256",
        IMAGE,
        "-c",
        "shared_buffers=64MB",
        "-c",
        "work_mem=2MB",
        "-c",
        "max_connections=12",
        "-c",
        "statement_timeout=3000",
        "-c",
        "lock_timeout=1000",
        "-c",
        "idle_in_transaction_session_timeout=5000",
        "-c",
        "max_wal_size=128MB",
    ]


def archive_owned(path: Path) -> dict:
    """Stop an idle exact-owned realm and preserve all bytes for later inspection.

    This explicit phase never deletes a container, volume or file, modifies an
    expiry, adopts a different label, or stops an application to make it idle.
    The caller holds the runner lock; other database clients prevent rotation.
    """
    value = LocalProfile.preservation_identity(path)
    if path != RUN / "environment.json" or value.get("unit") != UNIT:
        raise Refused("U5 preservation requires its own explicit realm")
    require_manifest_identity(value)
    require_resources(value)
    require_stopped()
    opened = command(["lsof", "+D", str(RUN)], timeout=10)
    if opened.returncode != 1 or opened.stdout.strip():
        raise Refused("owned directory is in use or custody could not be checked")
    entries = [RUN, *RUN.rglob("*")]
    if len(entries) > 4096:
        raise Refused("preservation inventory exceeds its bounded allocation")
    for entry in entries:
        info = entry.lstat()
        directory = stat.S_ISDIR(info.st_mode)
        if (
            info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != (0o700 if directory else 0o600)
            or not (directory or stat.S_ISREG(info.st_mode))
            or (not directory and info.st_nlink != 1)
        ):
            raise Refused("preservation entry custody differs")
    with connect_admin(value) as conn:
        identity = conn.execute(
            "SELECT run_id,current_database() FROM public.docsuri_local_identity"
        ).fetchone()
        if identity != (value["runId"], DATABASE):
            raise Refused("preservation database identity differs")
        active = conn.execute(
            "SELECT count(*) FROM pg_stat_activity WHERE pid<>pg_backend_pid() "
            "AND backend_type='client backend'"
        ).fetchone()[0]
        if active:
            raise Refused("other database clients prevent safe preservation")
    destination = RUN.with_name(
        f"docsuri-u5-preserved-{value['runId']}-{secrets.token_hex(4)}"
    )
    if destination.exists() or destination.is_symlink():
        raise Refused("preservation destination exists")
    require_resources(value)
    require(["docker", "stop", "--time", "10", value["container"]], timeout=15)
    stopped = json.loads(
        require(["docker", "container", "inspect", value["container"]]).stdout
    )
    if len(stopped) != 1 or stopped[0]["State"]["Running"]:
        raise Refused("database stop was not acknowledged; directory retained")
    os.rename(RUN, destination)
    descriptor = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return {
        "state": "preserved",
        "path": str(destination),
        "runId": value["runId"],
        "expiresAt": value["expiresAt"],
        "containerStopped": True,
        "volumePreserved": value["volume"],
    }


def setup(path: Path) -> dict:
    if RUN.exists():
        info = RUN.lstat()
        if (
            not stat.S_ISDIR(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o700
        ):
            raise Refused("existing directory custody differs")
        if any(RUN.iterdir()):
            _, value = manifest(path)
            require_resources(value)
            return {"state": "preserved", "runId": value["runId"]}
    resources = preflight()
    check_ports()
    RUN.mkdir(mode=0o700, exist_ok=True)
    run_id = "docsuri-u5-" + secrets.token_hex(8)
    now = time.time()
    value = {
        "unit": UNIT,
        "profile": "synthetic-local",
        "repository": str(ROOT),
        "runId": run_id,
        "container": run_id,
        "volume": run_id + "-pgdata",
        "databaseImage": IMAGE,
        "database": DATABASE,
        "realm": REALM,
        "databasePort": DATABASE_PORT,
        "applicationPort": APPLICATION_PORT,
        "createdAt": now,
        "expiresAt": now + 86400,
        "sourceSha": require(["git", "rev-parse", "HEAD"]).stdout.strip(),
        "locks": {name: digest(ROOT / name) for name in LOCKS},
        "policy": POLICY,
        "fixtureAccounts": [],
        "fixturePapers": [],
    }
    private_json(path, value)
    private_json(
        RUN / "ownership.json", {"runId": run_id, "manifestSha256": digest(path)}
    )
    password = secrets.token_urlsafe(32)
    private_json(
        RUN / "migration-credentials.json", {"databaseAdminPassword": password}
    )
    private_json(RUN / "setup-resources.json", resources)
    require(
        ["docker", "volume", "create", "--label", f"{LABEL}={run_id}", value["volume"]]
    )
    require(database_command(value), extra={"POSTGRES_PASSWORD": password})
    wait_database_endpoint(value)
    migrate(path, base_only=True)
    return {
        "state": "base-installed",
        "runId": run_id,
        "u5MigrationsApplied": False,
        "resources": resources,
    }


def connect_admin(value: dict):
    import psycopg

    secret = json.loads(private_bytes(RUN / "migration-credentials.json"))
    return psycopg.connect(
        host="127.0.0.1",
        port=DATABASE_PORT,
        dbname=DATABASE,
        user="postgres",
        password=secret["databaseAdminPassword"],
        connect_timeout=3,
    )


def wait_database_endpoint(value):
    """Probe the authenticated TCP endpoint migrations actually use, not initdb's socket."""
    import psycopg

    deadline = (
        time.monotonic() + 105
    )  # Previous 30 * (3-second probe + 0.5-second wait).
    for _ in range(30):
        if deadline - time.monotonic() < 4.5:
            break  # Leave room for the bounded connect, query and retry delay.
        try:
            with connect_admin(value) as conn:
                conn.execute("SET LOCAL statement_timeout=1000")
                row = conn.execute("SELECT current_database()").fetchone()
                if row != (DATABASE,):
                    raise Refused(
                        "database endpoint identity differs; owned resources preserved"
                    )
            return
        except (psycopg.OperationalError, psycopg.InterfaceError):
            time.sleep(0.5)
    raise Refused("database TCP startup failed; owned resources preserved")


def install_base(conn, value: dict, credentials: dict, hashes: dict) -> None:
    """Create the shared base plus separately owned research and topics schemas."""
    from psycopg import sql
    from psycopg.types.json import Jsonb

    unexpected = conn.execute(
        "SELECT nspname FROM pg_namespace WHERE nspname NOT LIKE 'pg_%' AND nspname NOT IN ('public','information_schema')"
    ).fetchall()
    if unexpected:
        raise Refused("unrecognized schema; no migration attempted")
    conn.execute(
        sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(
            sql.Identifier(DATABASE)
        )
    )
    conn.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
    conn.execute(
        "CREATE TABLE public.docsuri_local_identity (singleton boolean PRIMARY KEY CHECK(singleton),run_id text NOT NULL,schema_hashes jsonb NOT NULL)"
    )
    conn.execute(
        "INSERT INTO public.docsuri_local_identity VALUES(true,%s,%s)",
        (value["runId"], Jsonb(hashes)),
    )
    for name in sorted(OWNERS):
        owner, runtime, schema = (
            sql.Identifier(f"docsuri_{name}_owner"),
            sql.Identifier(f"docsuri_{name}"),
            sql.Identifier(name),
        )
        conn.execute(
            sql.SQL(
                "CREATE ROLE {} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
            ).format(owner)
        )
        conn.execute(
            sql.SQL(
                "CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS CONNECTION LIMIT 2 PASSWORD {}"
            ).format(runtime, sql.Literal(credentials["roles"][name]))
        )
        conn.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(DATABASE), runtime
            )
        )
        conn.execute(sql.SQL("CREATE SCHEMA {} AUTHORIZATION {}").format(schema, owner))
        conn.execute(sql.SQL("SET LOCAL ROLE {}").format(owner))
        conn.execute(
            sql.SQL(
                "ALTER DEFAULT PRIVILEGES IN SCHEMA {} REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC"
            ).format(schema)
        )
        if name in SCHEMAS:
            conn.execute((ROOT / SCHEMAS[name]).read_text(), prepare=False)
            conn.execute(
                sql.SQL(
                    "CREATE TABLE {}.receipt (account_id uuid NOT NULL,kind text NOT NULL,key uuid NOT NULL,intent_hash text NOT NULL CHECK(intent_hash ~ '^[0-9a-f]{{64}}$'),outcome jsonb NOT NULL,created_at timestamptz NOT NULL DEFAULT clock_timestamp(),PRIMARY KEY(account_id,kind,key))"
                ).format(schema)
            )
            conn.execute(
                sql.SQL(
                    "GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA {} TO {}"
                ).format(schema, runtime)
            )
            conn.execute(
                sql.SQL("REVOKE UPDATE,DELETE ON {}.receipt FROM {}").format(
                    schema, runtime
                )
            )
            conn.execute(
                sql.SQL(
                    "GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA {} TO {}"
                ).format(schema, runtime)
            )
            conn.execute(
                sql.SQL("GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA {} TO {}").format(
                    schema, runtime
                )
            )
        conn.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(schema, runtime))
        conn.execute("RESET ROLE")
        conn.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(runtime))
        conn.execute(
            sql.SQL("GRANT SELECT ON public.docsuri_local_identity TO {}").format(
                runtime
            )
        )
    for name in (
        "library",
        "personalization",
        "discovery",
        "usage",
        "assistance",
        "research",
        "topics",
    ):
        role = sql.Identifier(f"docsuri_{name}")
        conn.execute(sql.SQL("GRANT USAGE ON SCHEMA accounts TO {}").format(role))
        conn.execute(
            sql.SQL(
                "GRANT EXECUTE ON FUNCTION accounts.guard_session(uuid,uuid,text) TO {}"
            ).format(role)
        )
    for name in ("library", "discovery", "assistance", "research", "topics"):
        role = sql.Identifier(f"docsuri_{name}")
        conn.execute(sql.SQL("GRANT USAGE ON SCHEMA corpus TO {}").format(role))
        conn.execute(
            sql.SQL(
                "GRANT EXECUTE ON FUNCTION corpus.guard_version(text,text) TO {}"
            ).format(role)
        )
    conn.execute(
        "GRANT EXECUTE ON FUNCTION accounts.guard_execution(uuid,uuid) TO docsuri_assistance"
    )
    conn.execute(
        "GRANT SELECT ON corpus.paper,corpus.version,corpus.projection TO docsuri_discovery"
    )


def migrate(path: Path, *, base_only: bool = False) -> dict:
    from psycopg import sql
    from psycopg.types.json import Jsonb

    _, value = manifest(path)
    require_resources(value)
    require_stopped()
    target = RUN / "owner-credentials.json"
    if target.exists():
        credentials = json.loads(private_bytes(target))
        if (
            credentials.get("runId") != value["runId"]
            or set(credentials.get("roles", {})) != OWNERS
        ):
            raise Refused("owner credential identity mismatch")
    else:
        credentials = {
            "runId": value["runId"],
            "roles": {name: secrets.token_urlsafe(32) for name in sorted(OWNERS)},
        }
        private_json(target, credentials)
    hashes = {name: digest(ROOT / file) for name, file in SCHEMAS.items()}
    with connect_admin(value) as conn:
        if conn.execute("SHOW server_version").fetchone()[0].split()[0] != "16.15":
            raise Refused("pinned PostgreSQL version mismatch")
        if not conn.execute(
            "SELECT to_regclass('public.docsuri_local_identity')"
        ).fetchone()[0]:
            install_base(conn, value, credentials, hashes)
        known = amend(conn, value, hashes)
        if not base_only:
            for owner, file in MIGRATIONS:
                current = digest(ROOT / file)
                if file in known:
                    if known[file] != current:
                        raise Refused(
                            "applied migration changed; append a new migration"
                        )
                    continue
                if file == "ops/src/docsuri_ops/u3_capacity.sql":
                    conn.execute(
                        sql.SQL(
                            "GRANT CONNECT ON DATABASE {} TO docsuri_operations_owner"
                        ).format(sql.Identifier(DATABASE))
                    )
                    conn.execute(
                        "GRANT EXECUTE ON FUNCTION pg_catalog.pg_ls_waldir() TO docsuri_operations_owner"
                    )
                conn.execute(
                    sql.SQL("SET LOCAL ROLE {}").format(
                        sql.Identifier(f"docsuri_{owner}_owner")
                    )
                )
                conn.execute((ROOT / file).read_text(), prepare=False)
                conn.execute("RESET ROLE")
                known[file] = current
            conn.execute(
                "UPDATE public.docsuri_local_identity SET schema_hashes=%s WHERE singleton",
                (Jsonb(known),),
            )
    if not base_only:
        from docsuri_ops.local_transport import prepare_transport

        from backend.modules.accounts.services.guarded_entry import GuardedEntryService
        from backend.transactions import OwnerTransactions

        transactions = OwnerTransactions(LocalProfile.load(path))
        try:
            GuardedEntryService(transactions)
        finally:
            transactions.close()
        prepare_transport(LocalProfile.load(path))
    return {
        "state": "base-verified" if base_only else "u5-migrated",
        "migrationCount": len(known),
    }


def source_identity() -> dict:
    value = base_source_identity()
    result = require(
        [
            "git",
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
            "--",
            "tests/u5_topics_digests",
            ".github/workflows/u5-topics-digests.yml",
        ]
    )
    for name in sorted(set(result.stdout.split("\0")) - {""}):
        path = ROOT / name
        if path.is_symlink():
            raise Refused("source inventory contains symlink")
        value["files"][name] = digest(path) if path.is_file() else None
    value["sha256"] = hashlib.sha256(
        json.dumps(value["files"], sort_keys=True).encode()
    ).hexdigest()
    return value


def child_environment() -> dict:
    environment = {
        key: os.environ[key]
        for key in ("PATH", "HOME", "TMPDIR", "LANG")
        if key in os.environ
    }
    environment.update(
        PYTHONPATH=str(ROOT),
        DOCSURI_U5_ENVIRONMENT_FILE=str(RUN / "environment.json"),
        PLAYWRIGHT_JUNIT_OUTPUT_FILE=str(RUN / "browser.xml"),
        CI="true",
        COREPACK_ENABLE_DOWNLOAD_PROMPT="0",
        COREPACK_ENABLE_NETWORK="0",
    )
    return environment


OBSERVATION_SECONDS = 1


def process_tree_rss(roots: tuple[int, ...], deadline: float) -> int:
    """Aggregate RSS of every supervised root's tree from ONE process snapshot.

    Browser verification supervises Playwright and its companion host. Taking a
    separate `ps` snapshot per root doubled the process-table scans inside each
    tick and measured the two trees at different instants. One bounded snapshot
    keeps the unchanged per-observation limit and the aggregate RSS budget; the
    union also prevents counting a shared descendant twice.
    """
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise Refused("process deadline reached")
    result = subprocess.run(
        ["ps", "-Ao", "pid=,ppid=,rss="],
        capture_output=True,
        text=True,
        timeout=min(OBSERVATION_SECONDS, remaining),
        check=True,
    )
    rows = [
        tuple(map(int, line.split()))
        for line in result.stdout.splitlines()
        if len(line.split()) == 3
    ]
    included = set(roots)
    while True:
        expanded = included | {child for child, parent, _ in rows if parent in included}
        if expanded == included:
            break
        included = expanded
    return sum(rss * 1024 for child, _, rss in rows if child in included)


def bounded_process(
    args: list[str],
    log: Path,
    *,
    seconds: float = 300,
    companion=None,
    companion_log: Path | None = None,
    allow_bounded_stop: bool = False,
    clock_capability: str | None = None,
) -> dict:
    if not 0 < seconds <= 300 or log.parent != RUN:
        raise Refused("finite owned process bound required")
    descriptor = os.open(
        log, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
    )
    process = None
    beginning = time.monotonic()
    observation_end = beginning + seconds - min(7, seconds / 2)
    count, peak, code = 0, 0, None
    observations, slowest = 0, 0.0
    environment = child_environment()
    if clock_capability is not None:
        environment["DOCSURI_U5_CLOCK_CAPABILITY"] = clock_capability
    if companion is not None:
        # Bound the Playwright coordinator and inherited worker heaps. The
        # aggregate process-tree RSS check below remains authoritative.
        environment["NODE_OPTIONS"] = "--max-old-space-size=128 --max-semi-space-size=8"
    previous = {
        value: signal.getsignal(value) for value in (signal.SIGTERM, signal.SIGINT)
    }

    def interrupted(signum, frame):
        raise RuntimeError("owned process supervision interrupted")

    for value in previous:
        signal.signal(value, interrupted)
    failure_metrics = None
    try:
        with (
            os.fdopen(descriptor, "wb") as stream,
            selectors.DefaultSelector() as selector,
        ):
            process = subprocess.Popen(
                args,
                cwd=ROOT,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                umask=0o077,
            )
            os.set_blocking(process.stdout.fileno(), False)
            selector.register(process.stdout, selectors.EVENT_READ)
            while time.monotonic() < observation_end:
                for key, _ in selector.select(timeout=0.05):
                    chunk = os.read(key.fileobj.fileno(), 65536)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    count += len(chunk)
                    if count > MAX_LOG:
                        raise Refused("private process log exceeded 16 MiB")
                    stream.write(chunk)
                roots = (process.pid,)
                if companion is not None:
                    if companion.poll() is not None:
                        raise Refused(
                            "owned application exited during browser verification"
                        )
                    roots = (process.pid, companion.pid)
                observed = time.monotonic()
                rss = process_tree_rss(roots, observation_end)
                observations += 1
                slowest = max(slowest, time.monotonic() - observed)
                if companion is not None and companion_log.stat().st_size > MAX_LOG:
                    raise Refused("private application log exceeded 16 MiB")
                peak = max(peak, rss)
                if peak > MAX_RSS:
                    raise Refused("process tree exceeded RSS safety budget")
                code = process.poll()
                if code is not None and not selector.get_map():
                    break
            stream.flush()
            os.fsync(stream.fileno())
    except (Refused, RuntimeError, OSError, subprocess.SubprocessError) as error:
        reasons = {
            "private process log exceeded 16 MiB": "log-limit",
            "private application log exceeded 16 MiB": "companion-log-limit",
            "owned application exited during browser verification": "companion-exit",
            "process tree exceeded RSS safety budget": "rss-limit",
            "owned process supervision interrupted": "interrupted",
        }
        failure_metrics = {
            "exitCode": 1,
            "reason": reasons.get(str(error), "supervision-error"),
            "elapsedSeconds": time.monotonic() - beginning,
            "peakRssBytes": peak,
            "logBytes": count,
            "processStopped": False,
            "observations": observations,
            "slowestObservationSeconds": slowest,
        }
        error.supervision = failure_metrics
        raise
    finally:
        try:
            if process is not None:
                stop(process)
                process.stdout.close()
            if failure_metrics is not None:
                failure_metrics["processStopped"] = (
                    process is None or process.poll() is not None
                )
        finally:
            for value, previous_handler in previous.items():
                signal.signal(value, previous_handler)
    bounded_stop = code is None
    if bounded_stop and not allow_bounded_stop:
        error = Refused("owned process exceeded its deadline")
        error.supervision = {
            "exitCode": 1,
            "reason": "deadline",
            "elapsedSeconds": time.monotonic() - beginning,
            "peakRssBytes": peak,
            "logBytes": count,
            "processStopped": True,
            "observations": observations,
            "slowestObservationSeconds": slowest,
        }
        raise error
    return {
        "exitCode": 0 if bounded_stop else code,
        "reason": "bounded-stop" if bounded_stop else "process-exit",
        "elapsedSeconds": time.monotonic() - beginning,
        "peakRssBytes": peak,
        "logBytes": count,
        "processStopped": True,
        "observations": observations,
        "slowestObservationSeconds": slowest,
    }


def start_server(path: Path, log: Path):
    """Start only this profile's host and wait for verified HTTPS readiness."""
    from docsuri_ops.local_transport import inspect_transport

    profile = LocalProfile.load(path)
    transport = inspect_transport(profile)
    require_stopped()
    descriptor = os.open(
        log, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
    )
    with os.fdopen(descriptor, "wb") as stream:
        process = subprocess.Popen(
            [
                str(PYTHON),
                str(ROOT / "scripts/serve_docsuri_u5.py"),
                "--environment-file",
                str(path),
            ],
            cwd=ROOT,
            env=child_environment(),
            stdin=subprocess.DEVNULL,
            stdout=stream,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            umask=0o077,
        )
    deadline = time.monotonic() + 30
    context = ssl.create_default_context(cafile=str(transport.certificate))
    try:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise Refused("owned application exited before readiness")
            if (
                process_tree_rss((process.pid,), deadline) > MAX_RSS
                or log.stat().st_size > MAX_LOG
            ):
                raise Refused("owned application exceeded startup bounds")
            try:
                with urllib.request.urlopen(
                    profile.origin + "/health/ready", context=context, timeout=1
                ) as response:
                    if response.status == 200:
                        return process
            except (urllib.error.URLError, TimeoutError, OSError):
                pass
            time.sleep(0.1)
        raise Refused("owned application did not become ready within 30 seconds")
    except BaseException:
        stop(process)
        raise


def preserve_prior_reports(phase: str) -> list[dict]:
    """Preserve the exact owned report/evidence before a tool can replace it.

    All candidates are validated before the first rename. Content, permissions
    and the environment expiry stay unchanged; unsafe paths fail closed.
    """
    if phase not in {*TEST_PHASES, "frontend", "browser"}:
        raise Refused("report preservation requires a verification phase")
    custody = RUN.lstat()
    if (
        not stat.S_ISDIR(custody.st_mode)
        or custody.st_uid != os.getuid()
        or stat.S_IMODE(custody.st_mode) != 0o700
    ):
        raise Refused("report preservation root custody differs")

    def inventory(root: Path) -> dict:
        pending, files, size, entries = [root], {}, 0, 0
        while pending:
            entry = pending.pop()
            entries += 1
            if entries > 4096:
                raise Refused("prior evidence inventory exceeds bounds")
            info = entry.lstat()
            directory = stat.S_ISDIR(info.st_mode)
            if (
                info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != (0o700 if directory else 0o600)
                or not (directory or stat.S_ISREG(info.st_mode))
                or (not directory and info.st_nlink != 1)
            ):
                raise Refused("prior evidence entry custody differs")
            relative = str(entry.relative_to(root))
            if directory:
                files[relative] = {"directory": True}
                pending.extend(entry.iterdir())
            else:
                size += info.st_size
                if info.st_size > MAX_LOG or size > 4 * MAX_LOG:
                    raise Refused("prior evidence byte allocation exceeded")
                raw = private_bytes(entry, maximum=MAX_LOG)
                files[relative] = {
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "bytes": len(raw),
                }
        return files

    candidates = [RUN / f"{phase}.xml"]
    if phase == "browser":
        candidates.append(RUN / "browser-evidence")
    suffix = f"preserved-{time.time_ns()}-{secrets.token_hex(4)}"
    planned = []
    for source in candidates:
        try:
            info = source.lstat()
        except FileNotFoundError:
            continue
        if not (
            stat.S_ISREG(info.st_mode)
            if source.suffix == ".xml"
            else stat.S_ISDIR(info.st_mode)
        ):
            raise Refused("prior report or browser evidence type differs")
        before = inventory(source)
        destination = source.with_name(f"{source.stem}-{suffix}{source.suffix}")
        if destination.exists() or destination.is_symlink():
            raise Refused("prior evidence preservation destination exists")
        planned.append((source, destination, before))
    preserved = []
    for source, destination, before in planned:
        os.rename(source, destination)
        if inventory(destination) != before:
            raise Refused("preserved evidence checksum differs")
        preserved.append(
            {
                "original": source.name,
                "preserved": destination.name,
                "inventory": before,
            }
        )
    if preserved:
        descriptor = os.open(RUN, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    return preserved


def run_phase(phase: str, path: Path) -> dict:
    _, value = manifest(path)
    require_resources(value)
    resources = preflight(established=True)
    if {name: digest(ROOT / name) for name in LOCKS} != value["locks"]:
        raise Refused("frozen dependency identity changed")
    require_stopped()
    if phase == "browser" and any(RUN.glob("*-evidence-*.json")):
        raise Refused(
            "browser verification requires a fresh realm; preserve this realm before replacement"
        )
    if phase in {"browser", "integration", "coverage"}:
        from scripts.u5_browser_fixtures import setup as prepare_browser_fixtures

        prepare_browser_fixtures(path)
    preserved = preserve_prior_reports(phase) if phase != "serve" else []
    before = source_identity()
    if phase == "serve":
        args = [
            str(PYTHON),
            str(ROOT / "scripts/serve_docsuri_u5.py"),
            "--environment-file",
            str(path),
        ]
        supervision = bounded_process(
            args, RUN / f"u5-serve-{time.time_ns()}.log", allow_bounded_stop=True
        )
        evidence = {
            "phase": phase,
            "runId": value["runId"],
            "source": before,
            "locks": value["locks"],
            "command": args,
            "supervision": supervision,
            "resources": resources,
            "completionVerification": False,
        }
        private_json(RUN / f"serve-evidence-{time.time_ns()}.json", evidence)
        if supervision["exitCode"] or supervision["reason"] != "bounded-stop":
            raise Refused(
                "owned serving process exited before its bounded demonstration ended"
            )
        return {"state": "experiment-ended", "completionVerification": False}
    report = RUN / f"{phase}.xml"
    if report.is_symlink():
        raise Refused("test report cannot be a symlink")
    args = [
        str(PYTHON),
        "-m",
        "pytest",
        "-c",
        "backend/pytest.u5-topics-digests.ini",
        "tests/u5_topics_digests"
        if phase == "coverage"
        else f"tests/u5_topics_digests/{phase}",
        "-q",
        "--tb=short",
        "--maxfail=1",
        f"--junitxml={report}",
    ]
    if phase == "frontend":
        args = [
            "corepack",
            "pnpm@9.15.9",
            "--dir",
            "frontend",
            "exec",
            "vitest",
            "run",
            "--config",
            "vitest.u5-topics.config.ts",
            "--reporter=junit",
            f"--outputFile={report}",
        ]
    elif phase == "browser":
        args = [
            str(ROOT / "frontend/node_modules/.bin/playwright"),
            "test",
            "--config",
            "frontend/playwright.u5-topics.config.ts",
            "--max-failures=1",
            "--reporter=junit",
        ]
    elif phase == "coverage":
        args.extend(
            [
                "--cov",
                "--cov-config=backend/.coveragerc.u5",
                "--cov-report=term-missing",
            ]
        )
    elif phase == "component":
        args.append("tests/u5_topics_digests/runtime")
    started = time.monotonic()
    supervision, failure, server, build = {}, None, None, None
    server_log = RUN / f"u5-browser-host-{time.time_ns()}.log"
    try:
        if phase == "browser":
            build = build_browser_assets(
                RUN / f"u5-browser-build-{time.time_ns()}.log",
                seconds=max(0.01, 300 - (time.monotonic() - started)),
            )
            server = start_server(path, server_log)
        remaining = max(0.01, 300 - (time.monotonic() - started))
        with (
            browser_clock_delegation(value, remaining)
            if phase == "browser"
            else nullcontext()
        ) as clock_capability:
            supervision = bounded_process(
                args,
                RUN / f"u5-phase-{phase}-{time.time_ns()}.log",
                clock_capability=clock_capability,
                **(
                    {
                        "seconds": remaining,
                        "companion": server,
                        "companion_log": server_log,
                    }
                    if server is not None
                    else {}
                ),
            )
    except (Refused, RuntimeError, OSError, subprocess.SubprocessError) as error:
        failure = type(error).__name__
        supervision = getattr(error, "supervision", {})
    finally:
        if server is not None:
            stop(server)
    evidence = {
        "phase": phase,
        "runId": value["runId"],
        "command": args,
        "exitCode": 1 if failure else supervision["exitCode"],
        "supervision": supervision,
        "build": build,
        "failureCategory": failure,
        "durationSeconds": time.monotonic() - started,
        "source": before,
        "locks": value["locks"],
        "policy": value["policy"],
        "manifestSha256": digest(path),
        "fixtureSourceSha256": digest(ROOT / "tests/u5_topics_digests/conftest.py"),
        "browserFixtureSha256": digest(RUN / "browser-fixtures.json")
        if (RUN / "browser-fixtures.json").exists()
        else None,
        "resources": resources,
        "preservedEvidence": preserved,
    }
    cases = None
    if report.exists() and not report.is_symlink():
        try:
            cases = list(
                ET.fromstring(private_bytes(report, maximum=MAX_LOG)).iter("testcase")
            )
        except (ValueError, OSError, ET.ParseError):
            evidence["invalidTestReport"] = True
            evidence["exitCode"] = evidence["exitCode"] or 1
    if cases is not None:
        evidence.update(
            tests=len(cases),
            failures=sum(c.find("failure") is not None for c in cases),
            errors=sum(c.find("error") is not None for c in cases),
            skipped=sum(c.find("skipped") is not None for c in cases),
        )
        if (
            not cases
            or evidence["skipped"]
            or evidence["errors"]
            or evidence["failures"]
        ):
            evidence["exitCode"] = evidence["exitCode"] or 1
    elif "invalidTestReport" not in evidence:
        evidence["missingTestReport"] = True
        evidence["exitCode"] = evidence["exitCode"] or 1
    if source_identity()["sha256"] != before["sha256"]:
        evidence["sourceChangedDuringRun"] = True
        evidence["exitCode"] = evidence["exitCode"] or 1
    private_json(RUN / f"{phase}-evidence-{time.time_ns()}.json", evidence)
    print(json.dumps(safe_phase_summary(evidence)))
    if evidence["exitCode"]:
        raise Refused("U5 phase failed; evidence preserved")
    return {"state": "passed", "phase": phase}


def build_browser_assets(log: Path, *, seconds: float) -> dict:
    # Vite's approved configuration empties dist and rebuilds the current entry.
    # Never serve a prior checkout's assets under a current-source test receipt.
    command = ["corepack", "pnpm@9.15.9", "--dir", "frontend", "exec", "vite", "build"]
    result = bounded_process(command, log, seconds=seconds)
    if result["exitCode"]:
        error = Refused("current browser asset build failed")
        error.supervision = result
        raise error
    return {"command": command, "supervision": result, "log": str(log)}


def safe_phase_summary(evidence):
    """Only fixed classifications and numeric supervision; never private log content."""
    result = {
        key: evidence[key]
        for key in (
            "phase",
            "exitCode",
            "tests",
            "failures",
            "errors",
            "skipped",
            "failureCategory",
            "missingTestReport",
            "invalidTestReport",
            "sourceChangedDuringRun",
        )
        if key in evidence
    }
    result["supervision"] = {
        key: evidence.get("supervision", {}).get(key)
        for key in (
            "reason",
            "exitCode",
            "elapsedSeconds",
            "peakRssBytes",
            "logBytes",
            "processStopped",
        )
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True, choices=PHASES)
    parser.add_argument("--profile", required=True, choices=["synthetic-local"])
    parser.add_argument("--environment-file", required=True, type=Path)
    args = parser.parse_args()
    if (
        args.environment_file.is_symlink()
        or args.environment_file.parent.is_symlink()
        or args.environment_file.resolve() != RUN / "environment.json"
    ):
        raise Refused("only the explicit U5 owned manifest is accepted")
    path = args.environment_file.resolve()
    with exclusive():
        if args.phase == "archive-owned":
            result = archive_owned(path)
        elif args.phase == "setup":
            result = setup(path)
        elif args.phase == "migrate":
            result = migrate(path)
        elif args.phase == "fixtures":
            from scripts.u5_browser_fixtures import setup as prepare_browser_fixtures

            result = prepare_browser_fixtures(path)
        elif args.phase == "teardown":
            _, value = manifest(path)
            result = {
                "state": "preserved",
                "runId": value["runId"],
                "note": "automatic disposal disabled; retain evidence and resources",
            }
        else:
            result = run_phase(args.phase, path)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Refused, ValueError, OSError) as error:
        print(
            json.dumps(
                {
                    "state": "refused",
                    "category": type(error).__name__,
                    "reason": str(error)
                    if isinstance(error, Refused)
                    else "owned prerequisite unavailable",
                }
            )
        )
        raise SystemExit(1) from None
