"""Bounded, explicitly owned U6 synthetic-local experiments.

Never adopts another realm, extends retention, changes old containers or treats
missing/zero/skipped execution as success. Setup and migrations are explicit;
test phases inspect established resources and preserve failed evidence. The
environment's `export-keys/` folder is created empty at setup; no key exists until
the token keyring creates the first one on first use.
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
from contextlib import contextmanager
from pathlib import Path

from defusedxml import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "ops/src"))

from bootstrap_docsuri_u1 import SCHEMAS, amend
from verify_docsuri_u1 import GIB, IMAGE, LOCKS, Refused, command, digest, headroom
from verify_docsuri_u3 import stop
from verify_docsuri_u5 import MIGRATIONS as U5_MIGRATIONS

from backend.local_profile import LocalProfile, private_bytes

RUN = Path("/tmp/docsuri-u6-run").resolve()
_RUNNER_OWNED = False
PYTHON = ROOT / "backend/.venv/bin/python"
UNIT = "u6-approved-export"
REALM = "approved-export"
DATABASE = "docsuri_u6"
DATABASE_PORT = 15499
APPLICATION_PORT = 18099
LABEL = "dev.docsuri.u6.run"
POLICY = "u6-synthetic-v1"
# One bound for every supervised phase (R-08). An overrun fails the phase; it is never
# escaped by splitting a pass, excluding tests or lowering a floor.
PHASE_SECONDS = 300
MAX_LOG = 16 * 1024**2
MAX_RSS = GIB
DB_MEMORY = GIB
RECOVERY_MEMORY = 512 * 1024**2
KEY_FOLDER = "export-keys"
TEST_ROOT = "tests/u6_approved_export"
OWNERS = frozenset(SCHEMAS) | {"research", "topics", "export"}
# U5's applied chain, then U6's own files, each applied as the owner of the schema it
# changes. Applied files are never edited; a correction is a new file.
MIGRATIONS = (
    *U5_MIGRATIONS,
    ("accounts", "backend/modules/accounts/u6_lifecycle_guard.sql"),
    ("export", "backend/modules/export/u6_schema.sql"),
    ("export", "backend/modules/export/u6_custody.sql"),
    ("export", "backend/modules/export/u6_maintenance.sql"),
)
TEST_PHASES = (
    "database",
    "repository",
    "component",
    "integration",
    "operations",
    "coverage",
)
KEY_PHASES = ("create-key-after-loss", "rotate-key", "retire-key", "key-counts")
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
    *KEY_PHASES,
)
# Every phase that runs the synthetic composition or its tests. Each refuses while the
# operator's `real-export.json` exists: that environment holds a real sealed token which
# a synthetic run could open and hand to the fake Notion (cicd-pipeline §4.3). The
# archive, the operator key commands and teardown stay available.
SYNTHETIC_PHASES = frozenset({"fixtures", *TEST_PHASES, "frontend", "browser", "serve"})
ACTIVATION_FILE = "real-export.json"
EVIDENCE_PATTERN = "*-evidence-*.json"
CLOCK_DELEGATION = "browser-clock-delegation.json"
CLOCK_CAPABILITY = "DOCSURI_U6_CLOCK_CAPABILITY"
VITEST_CONFIG = "vitest.u6-export.config.ts"
PLAYWRIGHT_CONFIG = "frontend/playwright.u6-export.config.ts"
PRESERVATION_SCRIPT = "scripts/u6_preservation.py"
# Login roles that receive USAGE on schema accounts and EXECUTE on the session guard.
SESSION_GUARD_LOGINS = (
    "library",
    "personalization",
    "discovery",
    "usage",
    "assistance",
    "research",
    "topics",
    "export",
)
CORPUS_GUARD_LOGINS = ("library", "discovery", "assistance", "research", "topics")


def require(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    result = command(args, **kwargs)
    if result.returncode:
        raise Refused(f"command failed ({result.returncode}): {args[0]}")
    return result


def require_private_directory(path: Path, message: str) -> None:
    """A real directory (never a link), owned by this user, at exactly mode 0700."""
    info = path.lstat()
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o700
    ):
        raise Refused(message)


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def private_json(path: Path, value: object) -> None:
    if path.parent != RUN or path.is_symlink():
        raise Refused("private output outside owned run")
    require_private_directory(RUN, "run directory custody differs")
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
        fsync_directory(RUN)
    finally:
        pending.unlink(missing_ok=True)


@contextmanager
def exclusive():
    """One U6 runner phase, including setup and preservation, across processes."""
    global _RUNNER_OWNED
    path = RUN.parent / ".docsuri-u6-runner.lock"
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
            raise Refused("another U6 phase is active") from error
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


def require_no_real_export() -> None:
    """Real-export isolation: no synthetic phase runs beside the operator's settings."""
    target = RUN / ACTIVATION_FILE
    if target.exists() or target.is_symlink():
        raise Refused(
            "synthetic phases refuse an environment holding real-export settings; "
            "archive it with archive-owned"
        )


@contextmanager
def browser_clock_delegation(value: dict, seconds: float):
    """Delegate only fixture-clock writes while the browser parent retains custody."""
    if not _RUNNER_OWNED or not 0 < seconds <= PHASE_SECONDS:
        raise Refused("clock delegation requires bounded runner ownership")
    token = secrets.token_urlsafe(32)
    target = RUN / CLOCK_DELEGATION
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


def _delegation_grant(value: dict, token: str) -> dict:
    grant = json.loads(private_bytes(RUN / CLOCK_DELEGATION))
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
        or not time.time() < grant["expiresAt"] <= value["expiresAt"]
        or not secrets.compare_digest(
            grant["tokenHash"], hashlib.sha256(token.encode()).hexdigest()
        )
    ):
        raise Refused("clock delegation differs or expired")
    return grant


def authorize_clock_child(value: dict) -> None:
    """Validate a private browser capability without taking its parent's lock."""
    token = os.environ.get(CLOCK_CAPABILITY, "")
    if not 1 <= len(token) <= 128:
        raise Refused("clock delegation unavailable")
    grant = _delegation_grant(value, token)
    lock = RUN.parent / ".docsuri-u6-runner.lock"
    owner = private_bytes(lock).decode()
    if owner != str(grant["ownerPid"]):
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
        raise Refused("U6 requires its own explicit realm")
    require_manifest_identity(value)
    return profile, value


def require_manifest_identity(value: dict) -> None:
    """Bind both runtime and preservation metadata to this runner's resources."""
    if value.get("databaseImage") != IMAGE or value.get("policy") != POLICY:
        raise Refused("U6 image or policy identity differs")
    if (
        value.get("container") != value["runId"]
        or value.get("volume") != value["runId"] + "-pgdata"
    ):
        raise Refused("U6 resource names differ from run identity")


def require_key_folder() -> None:
    """The key folder exists inside the owned run, private, and is never a link."""
    require_private_directory(RUN / KEY_FOLDER, "export key folder custody differs")


def require_resources(value: dict) -> None:
    for kind, name in (("container", value["container"]), ("volume", value["volume"])):
        records = json.loads(require(["docker", kind, "inspect", name]).stdout)
        if len(records) != 1:
            raise Refused("ambiguous U6 resource")
        record = records[0]
        labels = (
            record.get("Labels", {})
            if kind == "volume"
            else record["Config"].get("Labels", {})
        )
        if labels.get(LABEL) != value["runId"]:
            raise Refused("missing or foreign U6 resource; preserve for recovery")
        if kind == "container":
            require_container_bounds(record, value)


def require_container_bounds(record: dict, value: dict) -> None:
    host = record["HostConfig"]
    if (
        record["Config"]["Image"] != IMAGE
        or host["Memory"] != DB_MEMORY
        or host["MemorySwap"] != DB_MEMORY
        or host["NanoCpus"] != 1_000_000_000
        or host["PidsLimit"] != 64
        or not host["ReadonlyRootfs"]
        or host["PortBindings"]
        != {"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": str(DATABASE_PORT)}]}
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
        raise Refused("U6 disk recovery reserve unavailable")
    require(["docker", "image", "inspect", IMAGE])
    info = json.loads(require(["docker", "info", "--format", "{{json .}}"]).stdout)
    if info["MemTotal"] < DB_MEMORY + RECOVERY_MEMORY:
        raise Refused("Docker memory cannot fit the database and recovery reserve")
    # Observe the daemon's kernel rather than macOS RAM. The cached probe has no
    # network, mounts, secrets or writable root and is bounded to 16 MiB/8 PIDs.
    raw = require(
        [
            "docker", "run", "--rm", "--network", "none", "--read-only",
            "--memory", "16m", "--memory-swap", "16m", "--cpus", "0.1",
            "--pids-limit", "8", "--entrypoint", "cat", IMAGE, "/proc/meminfo",
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
        "docker", "run", "-d",
        "--name", value["container"],
        "--label", f"{LABEL}={value['runId']}",
        "--memory", "1g", "--memory-swap", "1g", "--cpus", "1", "--pids-limit", "64",
        "--read-only",
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=16m",
        "--tmpfs", "/var/run/postgresql:rw,noexec,nosuid,size=16m",
        "-p", f"127.0.0.1:{DATABASE_PORT}:5432",
        "--mount", f"type=volume,src={value['volume']},dst=/var/lib/postgresql/data",
        "-e", "POSTGRES_PASSWORD",
        "-e", f"POSTGRES_DB={DATABASE}",
        "-e", "POSTGRES_INITDB_ARGS=--data-checksums --auth-host=scram-sha-256",
        IMAGE,
        "-c", "shared_buffers=64MB",
        "-c", "work_mem=2MB",
        "-c", "max_connections=12",
        "-c", "statement_timeout=3000",
        "-c", "lock_timeout=1000",
        "-c", "idle_in_transaction_session_timeout=5000",
        "-c", "max_wal_size=128MB",
    ]


def create_key_folder() -> None:
    """The empty, private key folder; no key is created here (security design §4.4)."""
    folder = RUN / KEY_FOLDER
    if folder.exists() or folder.is_symlink():
        raise Refused("export key folder already exists in a fresh run")
    os.mkdir(folder, 0o700)
    os.chmod(folder, 0o700, follow_symlinks=False)
    fsync_directory(RUN)
    require_key_folder()
    if any(folder.iterdir()):
        raise Refused("fresh export key folder is not empty")


def setup(path: Path) -> dict:
    if RUN.exists():
        require_private_directory(RUN, "existing directory custody differs")
        if any(RUN.iterdir()):
            _, value = manifest(path)
            require_resources(value)
            require_key_folder()
            return {"state": "preserved", "runId": value["runId"]}
    resources = preflight()
    check_ports()
    RUN.mkdir(mode=0o700, exist_ok=True)
    run_id = "docsuri-u6-" + secrets.token_hex(8)
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
    private_json(RUN / "ownership.json", {"runId": run_id, "manifestSha256": digest(path)})
    password = secrets.token_urlsafe(32)
    private_json(RUN / "migration-credentials.json", {"databaseAdminPassword": password})
    private_json(RUN / "setup-resources.json", resources)
    create_key_folder()
    require(["docker", "volume", "create", "--label", f"{LABEL}={run_id}", value["volume"]])
    require(database_command(value), extra={"POSTGRES_PASSWORD": password})
    wait_database_endpoint(value)
    migrate(path, base_only=True)
    return {
        "state": "base-installed",
        "runId": run_id,
        "u6MigrationsApplied": False,
        "keyFolder": {"mode": "0700", "entries": 0},
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

    deadline = time.monotonic() + 105  # 30 * (3-second probe + 0.5-second wait).
    for _ in range(30):
        if deadline - time.monotonic() < 4.5:
            break  # Leave room for the bounded connect, query and retry delay.
        try:
            with connect_admin(value) as conn:
                conn.execute("SET LOCAL statement_timeout=1000")
                if conn.execute("SELECT current_database()").fetchone() != (DATABASE,):
                    raise Refused("database endpoint identity differs; owned resources preserved")
            return
        except (psycopg.OperationalError, psycopg.InterfaceError):
            time.sleep(0.5)
    raise Refused("database TCP startup failed; owned resources preserved")


def install_base(conn, value: dict, credentials: dict, hashes: dict) -> None:
    """Create the shared base plus separately owned research, topics and export schemas."""
    from psycopg import sql
    from psycopg.types.json import Jsonb

    unexpected = conn.execute(
        "SELECT nspname FROM pg_namespace WHERE nspname NOT LIKE 'pg_%' AND nspname NOT IN ('public','information_schema')"
    ).fetchall()
    if unexpected:
        raise Refused("unrecognized schema; no migration attempted")
    conn.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(DATABASE)))
    conn.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
    conn.execute(
        "CREATE TABLE public.docsuri_local_identity (singleton boolean PRIMARY KEY CHECK(singleton),run_id text NOT NULL,schema_hashes jsonb NOT NULL)"
    )
    conn.execute(
        "INSERT INTO public.docsuri_local_identity VALUES(true,%s,%s)",
        (value["runId"], Jsonb(hashes)),
    )
    for name in sorted(OWNERS):
        install_owner(conn, name, credentials)
    for name in SESSION_GUARD_LOGINS:
        role = sql.Identifier(f"docsuri_{name}")
        conn.execute(sql.SQL("GRANT USAGE ON SCHEMA accounts TO {}").format(role))
        conn.execute(
            sql.SQL("GRANT EXECUTE ON FUNCTION accounts.guard_session(uuid,uuid,text) TO {}").format(
                role
            )
        )
    for name in CORPUS_GUARD_LOGINS:
        role = sql.Identifier(f"docsuri_{name}")
        conn.execute(sql.SQL("GRANT USAGE ON SCHEMA corpus TO {}").format(role))
        conn.execute(
            sql.SQL("GRANT EXECUTE ON FUNCTION corpus.guard_version(text,text) TO {}").format(role)
        )
    conn.execute(
        "GRANT EXECUTE ON FUNCTION accounts.guard_execution(uuid,uuid) TO docsuri_assistance"
    )
    conn.execute("GRANT SELECT ON corpus.paper,corpus.version,corpus.projection TO docsuri_discovery")


def install_owner(conn, name: str, credentials: dict) -> None:
    """One owner: a NOLOGIN schema owner, a bounded login role and the owned schema."""
    from psycopg import sql

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
        sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(DATABASE), runtime)
    )
    conn.execute(sql.SQL("CREATE SCHEMA {} AUTHORIZATION {}").format(schema, owner))
    conn.execute(sql.SQL("SET LOCAL ROLE {}").format(owner))
    conn.execute(
        sql.SQL("ALTER DEFAULT PRIVILEGES IN SCHEMA {} REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC").format(
            schema
        )
    )
    if name in SCHEMAS:
        conn.execute((ROOT / SCHEMAS[name]).read_text(), prepare=False)
        conn.execute(
            sql.SQL(
                "CREATE TABLE {}.receipt (account_id uuid NOT NULL,kind text NOT NULL,key uuid NOT NULL,intent_hash text NOT NULL CHECK(intent_hash ~ '^[0-9a-f]{{64}}$'),outcome jsonb NOT NULL,created_at timestamptz NOT NULL DEFAULT clock_timestamp(),PRIMARY KEY(account_id,kind,key))"
            ).format(schema)
        )
        for statement in (
            "GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA {} TO {}",
            "REVOKE UPDATE,DELETE ON {}.receipt FROM {}",
            "GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA {} TO {}",
            "GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA {} TO {}",
        ):
            conn.execute(sql.SQL(statement).format(schema, runtime))
    conn.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(schema, runtime))
    conn.execute("RESET ROLE")
    conn.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(runtime))
    conn.execute(sql.SQL("GRANT SELECT ON public.docsuri_local_identity TO {}").format(runtime))


def owner_credentials(value: dict) -> dict:
    target = RUN / "owner-credentials.json"
    if target.exists():
        credentials = json.loads(private_bytes(target))
        if credentials.get("runId") != value["runId"] or set(credentials.get("roles", {})) != OWNERS:
            raise Refused("owner credential identity mismatch")
        return credentials
    credentials = {
        "runId": value["runId"],
        "roles": {name: secrets.token_urlsafe(32) for name in sorted(OWNERS)},
    }
    private_json(target, credentials)
    return credentials


def apply_migrations(conn, known: dict) -> None:
    """Append-only: an applied file whose bytes changed refuses; new files apply once."""
    from psycopg import sql

    for owner, file in MIGRATIONS:
        current = digest(ROOT / file)
        if file in known:
            if known[file] != current:
                raise Refused("applied migration changed; append a new migration")
            continue
        if file == "ops/src/docsuri_ops/u3_capacity.sql":
            conn.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO docsuri_operations_owner").format(
                    sql.Identifier(DATABASE)
                )
            )
            conn.execute(
                "GRANT EXECUTE ON FUNCTION pg_catalog.pg_ls_waldir() TO docsuri_operations_owner"
            )
        conn.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(f"docsuri_{owner}_owner")))
        conn.execute((ROOT / file).read_text(), prepare=False)
        conn.execute("RESET ROLE")
        known[file] = current


def migrate(path: Path, *, base_only: bool = False) -> dict:
    from psycopg.types.json import Jsonb

    _, value = manifest(path)
    require_resources(value)
    require_key_folder()
    require_stopped()
    credentials = owner_credentials(value)
    hashes = {name: digest(ROOT / file) for name, file in SCHEMAS.items()}
    with connect_admin(value) as conn:
        if conn.execute("SHOW server_version").fetchone()[0].split()[0] != "16.15":
            raise Refused("pinned PostgreSQL version mismatch")
        if not conn.execute("SELECT to_regclass('public.docsuri_local_identity')").fetchone()[0]:
            install_base(conn, value, credentials, hashes)
        known = amend(conn, value, hashes)
        if not base_only:
            apply_migrations(conn, known)
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
        "state": "base-verified" if base_only else "u6-migrated",
        "migrationCount": len(known),
    }


def listed_files(*paths: str) -> list[str]:
    """Files git tracks or would track: the `--cached --others --exclude-standard` listing."""
    result = require(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", *paths]
    )
    return sorted(set(result.stdout.split("\0")) - {""})


def require_test_paths(paths: tuple[str, ...]) -> None:
    """Every test path a phase names resolves to at least one listed file.

    An ignored or empty folder lists nothing and refuses, so a phase can never pass by
    naming a path a fresh checkout lacks.
    """
    for name in paths:
        if not listed_files(name):
            raise Refused("phase test path lists no tracked or untracked-unignored file")


def source_identity() -> dict:
    """Bind evidence to the actual listed bytes of every source the phases exercise."""
    files = {}
    for name in listed_files(
        "backend",
        "frontend",
        "shared",
        "scripts",
        "ops",
        "ingestion",
        TEST_ROOT,
        ".github/workflows/u6-approved-export.yml",
    ):
        path = ROOT / name
        if path.is_symlink():
            raise Refused("source inventory contains symlink")
        files[name] = digest(path) if path.is_file() else None
    return {
        "head": require(["git", "rev-parse", "HEAD"]).stdout.strip(),
        "sha256": hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest(),
        "files": files,
    }


def child_environment() -> dict:
    environment = {
        key: os.environ[key] for key in ("PATH", "HOME", "TMPDIR", "LANG") if key in os.environ
    }
    environment.update(
        PYTHONPATH=str(ROOT),
        DOCSURI_U6_ENVIRONMENT_FILE=str(RUN / "environment.json"),
        PLAYWRIGHT_JUNIT_OUTPUT_FILE=str(RUN / "browser.xml"),
        CI="true",
        COREPACK_ENABLE_DOWNLOAD_PROMPT="0",
        COREPACK_ENABLE_NETWORK="0",
    )
    return environment


OBSERVATION_SECONDS = 1


def process_tree_rss(roots: tuple[int, ...], deadline: float) -> int:
    """Aggregate RSS of every supervised root's tree from ONE process snapshot."""
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


def supervision_record(reason: str, beginning: float, totals: dict, *, stopped: bool) -> dict:
    return {
        "exitCode": 1,
        "reason": reason,
        "elapsedSeconds": time.monotonic() - beginning,
        "peakRssBytes": totals["peak"],
        "logBytes": totals["count"],
        "processStopped": stopped,
        "observations": totals["observations"],
        "slowestObservationSeconds": totals["slowest"],
    }


SUPERVISION_REASONS = {
    "private process log exceeded 16 MiB": "log-limit",
    "private application log exceeded 16 MiB": "companion-log-limit",
    "owned application exited during browser verification": "companion-exit",
    "process tree exceeded RSS safety budget": "rss-limit",
    "owned process supervision interrupted": "interrupted",
}


def bounded_process(
    args: list[str],
    log: Path,
    *,
    seconds: float = PHASE_SECONDS,
    companion=None,
    companion_log: Path | None = None,
    allow_bounded_stop: bool = False,
    clock_capability: str | None = None,
) -> dict:
    """Run one child under the phase bound, an RSS budget and a private 16 MiB log.

    A browser run supervises Playwright together with its `companion` host: both trees
    count against one RSS budget, and the host exiting early fails the run. `serve`
    expects its host to be still running at the bound and stops it there.
    """
    if not 0 < seconds <= PHASE_SECONDS or log.parent != RUN:
        raise Refused("finite owned process bound required")
    descriptor = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    process, code, failure = None, None, None
    beginning = time.monotonic()
    observation_end = beginning + seconds - min(7, seconds / 2)
    totals = {"count": 0, "peak": 0, "observations": 0, "slowest": 0.0}
    environment = child_environment()
    if clock_capability is not None:
        environment[CLOCK_CAPABILITY] = clock_capability
    if companion is not None:
        # Bound the Playwright coordinator and worker heaps; the aggregate RSS check
        # stays authoritative.
        environment["NODE_OPTIONS"] = "--max-old-space-size=128 --max-semi-space-size=8"
    previous = {value: signal.getsignal(value) for value in (signal.SIGTERM, signal.SIGINT)}

    def interrupted(signum, frame):
        raise RuntimeError("owned process supervision interrupted")

    for value in previous:
        signal.signal(value, interrupted)
    try:
        with os.fdopen(descriptor, "wb") as stream, selectors.DefaultSelector() as selector:
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
            watched = (companion, companion_log)
            code = supervise(process, selector, stream, observation_end, totals, watched)
            stream.flush()
            os.fsync(stream.fileno())
    except (Refused, RuntimeError, OSError, subprocess.SubprocessError) as error:
        reason = SUPERVISION_REASONS.get(str(error), "supervision-error")
        failure = supervision_record(reason, beginning, totals, stopped=False)
        error.supervision = failure
        raise
    finally:
        try:
            if process is not None:
                stop(process)
                process.stdout.close()
            if failure is not None:
                failure["processStopped"] = process is None or process.poll() is not None
        finally:
            for value, previous_handler in previous.items():
                signal.signal(value, previous_handler)
    if code is None and not allow_bounded_stop:
        error = Refused("owned process exceeded its deadline")
        error.supervision = supervision_record("deadline", beginning, totals, stopped=True)
        raise error
    reason = "bounded-stop" if code is None else "process-exit"
    return {
        **supervision_record(reason, beginning, totals, stopped=True),
        "exitCode": 0 if code is None else code,
    }


def supervise(
    process, selector, stream, observation_end: float, totals: dict, watched=(None, None)
) -> int | None:
    """Copy bounded output and observe the process trees until exit or time runs out."""
    companion, companion_log = watched
    code = None
    while time.monotonic() < observation_end:
        for key, _ in selector.select(timeout=0.05):
            chunk = os.read(key.fileobj.fileno(), 65536)
            if not chunk:
                selector.unregister(key.fileobj)
                continue
            totals["count"] += len(chunk)
            if totals["count"] > MAX_LOG:
                raise Refused("private process log exceeded 16 MiB")
            stream.write(chunk)
        roots = (process.pid,)
        if companion is not None:
            if companion.poll() is not None:
                raise Refused("owned application exited during browser verification")
            if companion_log.stat().st_size > MAX_LOG:
                raise Refused("private application log exceeded 16 MiB")
            roots = (process.pid, companion.pid)
        observed = time.monotonic()
        rss = process_tree_rss(roots, observation_end)
        totals["observations"] += 1
        totals["slowest"] = max(totals["slowest"], time.monotonic() - observed)
        totals["peak"] = max(totals["peak"], rss)
        if totals["peak"] > MAX_RSS:
            raise Refused("process tree exceeded RSS safety budget")
        code = process.poll()
        if code is not None and not selector.get_map():
            return code
    return None


def start_server(path: Path, log: Path):
    """Start only this profile's synthetic host and wait for verified HTTPS readiness."""
    from docsuri_ops.local_transport import inspect_transport

    profile = LocalProfile.load(path)
    transport = inspect_transport(profile)
    require_stopped()
    descriptor = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        process = subprocess.Popen(
            serve_command(path),
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
            if process_tree_rss((process.pid,), deadline) > MAX_RSS or log.stat().st_size > MAX_LOG:
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


def serve_command(path: Path) -> list[str]:
    """The synthetic host; the tool never passes `--real-export` (cicd-pipeline §4.3)."""
    return [str(PYTHON), str(ROOT / "scripts/serve_docsuri_u6.py"), "--environment-file", str(path)]


def build_browser_assets(log: Path, *, seconds: float) -> dict:
    """Vite empties `frontend/dist` and rebuilds the current entry; a prior checkout's
    assets are never served under a current-source receipt. Next's `.next` is untouched."""
    build = ["corepack", "pnpm@9.15.9", "--dir", "frontend", "exec", "vite", "build"]
    result = bounded_process(build, log, seconds=seconds)
    if result["exitCode"]:
        error = Refused("current browser asset build failed")
        error.supervision = result
        raise error
    return {"command": build, "supervision": result, "log": log.name}


def preserve_prior_reports(phase: str) -> list[dict]:
    """Preserve the exact owned report before a phase can replace it.

    Each candidate is validated before the rename; content and permissions stay
    unchanged and unsafe paths fail closed.
    """
    if phase not in {*TEST_PHASES, "frontend", "browser"}:
        raise Refused("report preservation requires a verification phase")
    require_private_directory(RUN, "report preservation root custody differs")
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
        expected = stat.S_ISREG if source.suffix == ".xml" else stat.S_ISDIR
        if not expected(info.st_mode):
            raise Refused("prior report or browser evidence type differs")
        destination = source.with_name(f"{source.stem}-{suffix}{source.suffix}")
        if destination.exists() or destination.is_symlink():
            raise Refused("prior evidence preservation destination exists")
        planned.append((source, destination, evidence_inventory(source)))
    preserved = []
    for source, destination, before in planned:
        os.rename(source, destination)
        if evidence_inventory(destination) != before:
            raise Refused("preserved evidence checksum differs")
        preserved.append(
            {"original": source.name, "preserved": destination.name, "inventory": before}
        )
    if preserved:
        fsync_directory(RUN)
    return preserved


def evidence_inventory(root: Path) -> dict:
    """Digests of a report file or an evidence folder, each entry's custody checked."""
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
            continue
        size += info.st_size
        if info.st_size > MAX_LOG or size > 4 * MAX_LOG:
            raise Refused("prior evidence byte allocation exceeded")
        raw = private_bytes(entry, maximum=MAX_LOG)
        files[relative] = {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
    return files


def phase_command(phase: str, report: Path) -> tuple[list[str], tuple[str, ...]]:
    """The command a verification phase runs, and the test paths it names."""
    if phase == "frontend":
        return [
            "corepack", "pnpm@9.15.9", "--dir", "frontend", "exec", "vitest", "run",
            "--config", VITEST_CONFIG, "--coverage", "--reporter=junit", f"--outputFile={report}",
        ], ("frontend/test/u6-export",)
    if phase == "browser":
        return [
            str(ROOT / "frontend/node_modules/.bin/playwright"), "test",
            "--config", PLAYWRIGHT_CONFIG, "--max-failures=1", "--reporter=junit",
        ], ("frontend/e2e/u6-approved-export",)
    paths = (TEST_ROOT,) if phase == "coverage" else (f"{TEST_ROOT}/{phase}",)
    args = [
        str(PYTHON), "-m", "pytest", "-c", "backend/pytest.u6-approved-export.ini",
        *paths, "-q", "--tb=short", "--maxfail=1", f"--junitxml={report}",
    ]
    if phase == "coverage":
        args.extend(["--cov", "--cov-config=backend/.coveragerc.u6", "--cov-report=term-missing"])
    return args, paths


def junit_counts(report: Path, evidence: dict) -> None:
    """Zero tests, any skip, any error or failure, or a missing/invalid report fails."""
    cases = None
    if report.exists() and not report.is_symlink():
        try:
            cases = list(ET.fromstring(private_bytes(report, maximum=MAX_LOG)).iter("testcase"))
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
        if not cases or evidence["skipped"] or evidence["errors"] or evidence["failures"]:
            evidence["exitCode"] = evidence["exitCode"] or 1
    elif "invalidTestReport" not in evidence:
        evidence["missingTestReport"] = True
        evidence["exitCode"] = evidence["exitCode"] or 1


def remaining_seconds(started: float) -> float:
    """What is left of the one phase bound that a phase's children share."""
    return max(0.01, PHASE_SECONDS - (time.monotonic() - started))


COVERAGE_LINE = re.compile(
    r"^(TOTAL|scripts/u6_preservation\.py)\s+\d+\s+\d+\s+(\d+(?:\.\d+)?)%", re.MULTILINE
)


def coverage_percent(log: Path) -> float | None:
    """The last TOTAL (or preservation-only) line coverage figure a report printed."""
    try:
        text = private_bytes(log, maximum=MAX_LOG).decode(errors="replace")
    except (OSError, ValueError):
        return None
    found = COVERAGE_LINE.findall(text)
    return float(found[-1][1]) if found else None


def preservation_report(started: float) -> dict:
    """The second coverage report: `scripts/u6_preservation.py` on its own at 80%."""
    args = [
        str(PYTHON), "-m", "coverage", "report", "--rcfile=backend/.coveragerc.u6",
        f"--include={PRESERVATION_SCRIPT}", "--fail-under=80",
    ]
    log = RUN / f"u6-phase-coverage-preservation-{time.time_ns()}.log"
    supervision = bounded_process(args, log, seconds=remaining_seconds(started))
    return {
        "command": args,
        "exitCode": supervision["exitCode"],
        "linePercent": coverage_percent(log),
        "supervision": supervision,
    }


def run_browser(path: Path, value: dict, args: list[str], started: float) -> tuple[dict, dict]:
    """Build the assets, start the synthetic host, run Playwright: one shared bound."""
    extra, server = {}, None
    server_log = RUN / f"u6-browser-host-{time.time_ns()}.log"
    try:
        extra["build"] = build_browser_assets(
            RUN / f"u6-browser-build-{time.time_ns()}.log", seconds=remaining_seconds(started)
        )
        server = start_server(path, server_log)
        seconds = remaining_seconds(started)
        with browser_clock_delegation(value, seconds) as capability:
            supervision = bounded_process(
                args,
                RUN / f"u6-phase-browser-{time.time_ns()}.log",
                seconds=seconds,
                companion=server,
                companion_log=server_log,
                clock_capability=capability,
            )
    except BaseException as error:
        error.phase_extra = extra
        raise
    finally:
        if server is not None:
            stop(server)
    return supervision, extra


def execute_phase(phase: str, path: Path, value: dict, args: list[str], started: float):
    if phase == "browser":
        return run_browser(path, value, args, started)
    log = RUN / f"u6-phase-{phase}-{time.time_ns()}.log"
    supervision = bounded_process(args, log)
    extra = {}
    if phase == "coverage":
        extra["coverageTotalPercent"] = coverage_percent(log)
        if supervision["exitCode"] == 0:
            extra["preservationReport"] = preservation_report(started)
    return supervision, extra


def run_serve(path: Path, value: dict, resources: dict) -> dict:
    """The synthetic host for its bounded demonstration; never the real composition."""
    before = source_identity()
    args = serve_command(path)
    supervision = bounded_process(
        args, RUN / f"u6-serve-{time.time_ns()}.log", allow_bounded_stop=True
    )
    evidence = {
        "phase": "serve",
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
        raise Refused("owned serving process exited before its bounded demonstration ended")
    return {"state": "experiment-ended", "completionVerification": False}


def prepare_phase(phase: str, path: Path) -> tuple[dict, dict]:
    """The checks every verification phase runs first; then its fixtures when it uses them."""
    _, value = manifest(path)
    require_resources(value)
    require_key_folder()
    resources = preflight(established=True)
    if {name: digest(ROOT / name) for name in LOCKS} != value["locks"]:
        raise Refused("frozen dependency identity changed")
    require_stopped()
    if phase == "browser" and any(RUN.glob(EVIDENCE_PATTERN)):
        raise Refused(
            "browser verification requires a fresh realm; preserve this realm before replacement"
        )
    if phase in {"browser", "coverage"}:
        from scripts.u6_browser_fixtures import setup as prepare_browser_fixtures

        prepare_browser_fixtures(path)
    return value, resources


def run_phase(phase: str, path: Path) -> dict:
    value, resources = prepare_phase(phase, path)
    if phase == "serve":
        return run_serve(path, value, resources)
    report = RUN / f"{phase}.xml"
    if report.is_symlink():
        raise Refused("test report cannot be a symlink")
    args, paths = phase_command(phase, report)
    require_test_paths(paths)
    preserved = preserve_prior_reports(phase)
    before = source_identity()
    started = time.monotonic()
    supervision, failure, extra = {}, None, {}
    try:
        supervision, extra = execute_phase(phase, path, value, args, started)
    except (Refused, RuntimeError, OSError, subprocess.SubprocessError) as error:
        failure = type(error).__name__
        supervision = getattr(error, "supervision", {})
        extra = getattr(error, "phase_extra", {})
    evidence = {
        "phase": phase,
        "runId": value["runId"],
        "command": args,
        "testPaths": list(paths),
        "exitCode": 1 if failure else supervision["exitCode"],
        "supervision": supervision,
        "failureCategory": failure,
        "durationSeconds": time.monotonic() - started,
        "phaseBoundSeconds": PHASE_SECONDS,
        "source": before,
        "locks": value["locks"],
        "policy": value["policy"],
        "manifestSha256": digest(path),
        "fixtureSourceSha256": digest(ROOT / TEST_ROOT / "conftest.py"),
        "browserFixtureSha256": digest(RUN / "browser-fixtures.json")
        if (RUN / "browser-fixtures.json").exists()
        else None,
        "resources": resources,
        "preservedEvidence": preserved,
        **extra,
    }
    if phase == "coverage" and not failure and not extra.get("preservationReport"):
        evidence["exitCode"] = evidence["exitCode"] or 1
    if extra.get("preservationReport", {}).get("exitCode"):
        evidence["exitCode"] = evidence["exitCode"] or 1
    junit_counts(report, evidence)
    if source_identity()["sha256"] != before["sha256"]:
        evidence["sourceChangedDuringRun"] = True
        evidence["exitCode"] = evidence["exitCode"] or 1
    private_json(RUN / f"{phase}-evidence-{time.time_ns()}.json", evidence)
    print(json.dumps(safe_phase_summary(evidence)))
    if evidence["exitCode"]:
        raise Refused("U6 phase failed; evidence preserved")
    return {"state": "passed", "phase": phase}


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
            "coverageTotalPercent",
            "durationSeconds",
        )
        if key in evidence
    }
    if "preservationReport" in evidence:
        result["preservationReport"] = {
            key: evidence["preservationReport"].get(key) for key in ("exitCode", "linePercent")
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


def key_file_present() -> bool:
    from backend.modules.export.token_keyring import KEY_FILE

    target = RUN / KEY_FOLDER / KEY_FILE
    return target.exists() or target.is_symlink()


def teardown(path: Path) -> dict:
    """Reports and disposes of nothing; an environment holding a key ends only through
    the destructive archive, so a teardown can never leave a key behind (§4.3)."""
    _, value = manifest(path)
    if key_file_present():
        raise Refused("teardown refuses while export-keys holds a key file; run archive-owned")
    return {
        "state": "preserved",
        "runId": value["runId"],
        "note": "automatic disposal disabled; retain evidence and resources",
    }


def key_phase(phase: str, path: Path, version: str | None) -> tuple[dict, int]:
    """An operator key command through the administrative path (cicd-pipeline §4.5).

    The command itself checks the key folder, takes the keyring's waiting lock and acts
    as `docsuri_export_owner`; every report and refusal holds counts and versions only.
    """
    from backend.modules.export import key_commands
    from backend.modules.export.errors import ProtectionUnavailable
    from backend.modules.export.token_keyring import KeyOperationRefused

    if (phase == "retire-key") != (version is not None):
        raise Refused("--version is required by retire-key and accepted by no other phase")
    _, value = manifest(path)
    require_resources(value)
    folder, run_id = RUN / KEY_FOLDER, value["runId"]
    commands = {
        "create-key-after-loss": key_commands.create_key_after_loss,
        "rotate-key": key_commands.rotate_key,
        "key-counts": key_commands.key_counts,
    }
    with connect_admin(value) as conn:
        try:
            if phase == "retire-key":
                return key_commands.retire_key(folder, run_id, conn, version), 0
            return commands[phase](folder, run_id, conn), 0
        except KeyOperationRefused as error:
            return {"state": "refused", "category": error.category, "counts": error.counts}, 1
        except ProtectionUnavailable as error:
            return {"state": "refused", "category": "protection-unavailable", "reason": str(error)}, 1


def archive_identity(path: Path) -> dict:
    """Preservation identity (an expired environment is accepted), bound to this tool."""
    value = LocalProfile.preservation_identity(path)
    if path != RUN / "environment.json" or value.get("unit") != UNIT:
        raise Refused("U6 preservation requires its own explicit realm")
    require_manifest_identity(value)
    return value


def inventory_entries(root: Path) -> list[Path]:
    """Every entry under the environment folder, bounded at 4096."""
    entries = [root]
    for entry in root.rglob("*"):
        entries.append(entry)
        if len(entries) > 4096:
            raise Refused("preservation inventory exceeds its bounded allocation")
    return entries


def stop_database(value: dict) -> None:
    """An acknowledged `docker stop --time 10` of the owned database container."""
    require(["docker", "stop", "--time", "10", value["container"]], timeout=15)
    stopped = json.loads(require(["docker", "container", "inspect", value["container"]]).stdout)
    if len(stopped) != 1 or stopped[0]["State"]["Running"]:
        raise Refused("database stop was not acknowledged; directory retained")


def preservation_context():
    """The runner's helpers, handed to `scripts/u6_preservation.py` (R-05: no import cycle)."""
    from scripts.u6_preservation import ArchiveContext

    return ArchiveContext(
        run=RUN,
        key_folder=RUN / KEY_FOLDER,
        database=DATABASE,
        refused=Refused,
        identity=archive_identity,
        resources=require_resources,
        idle_port=require_stopped,
        open_files=lambda root: command(["lsof", "+D", str(root)], timeout=10),
        inventory=inventory_entries,
        connect_admin=connect_admin,
        stop_database=stop_database,
        sync=fsync_directory,
    )


def dispatch(phase: str, path: Path, version: str | None = None) -> tuple[dict, int]:
    """One phase under the runner lock; synthetic phases refuse beside real settings."""
    if phase in SYNTHETIC_PHASES:
        require_no_real_export()
    if phase in KEY_PHASES:
        return key_phase(phase, path, version)
    if version is not None:
        raise Refused("--version is required by retire-key and accepted by no other phase")
    if phase == "setup":
        return setup(path), 0
    if phase == "migrate":
        return migrate(path), 0
    if phase == "fixtures":
        from scripts.u6_browser_fixtures import setup as prepare_browser_fixtures

        return prepare_browser_fixtures(path), 0
    if phase == "teardown":
        return teardown(path), 0
    if phase == "archive-owned":
        from scripts.u6_preservation import archive

        return archive(path, preservation_context()), 0
    return run_phase(phase, path), 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True, choices=PHASES)
    parser.add_argument("--profile", required=True, choices=["synthetic-local"])
    parser.add_argument("--environment-file", required=True, type=Path)
    parser.add_argument("--version", help="the key version retire-key removes (u6-<32 hex>)")
    args = parser.parse_args()
    if (
        args.environment_file.is_symlink()
        or args.environment_file.parent.is_symlink()
        or args.environment_file.resolve() != RUN / "environment.json"
    ):
        raise Refused("only the explicit U6 owned manifest is accepted")
    path = args.environment_file.resolve()
    with exclusive():
        result, code = dispatch(args.phase, path, args.version)
    print(json.dumps(result))
    return code


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
