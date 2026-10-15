"""Bounded U3 synthetic runner; never a completion approval or real-data tool.

Setup is idempotent and never reseeds an existing run. Schema changes are a
separate explicit migrate phase. Inspection/test phases cannot initialize data.
The runner validates its own run identity, ownership, listeners, frozen locks
and retention before executing any phase; a U1/U2 environment manifest is never
accepted as an alias.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import selectors
import shutil
import signal
import socket
import stat
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

# CLI and imported test use share the same repository-local helper modules.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from verify_docsuri_u1 import (  # noqa: E402
    GIB,
    IMAGE,
    LOCKS,
    ROOT,
    Refused,
    command,
    digest,
    headroom,
)
from verify_docsuri_u1 import source_identity as u1_source_identity  # noqa: E402

RUN = Path("/tmp/docsuri-u3-run").resolve()
PYTHON = ROOT / "backend/.venv/bin/python"
LABEL = "dev.docsuri.u3.run"
UNIT = "u3-paper-corpus-capabilities"
DATABASE = "docsuri_u3"
DATABASE_PORT = 15459
APPLICATION_PORT = 18059
MAX_LOG = 16 * 1024**2
MAX_RSS = 1024**3

# Ordered, compatible U3 migrations; append-only. Base schemas and the U1
# amendments install first through the same shared bootstrap identity.
MIGRATIONS = (
    ("corpus", "backend/modules/corpus/u3_schema.sql"),
    ("corpus", "backend/modules/corpus/u3_guards.sql"),
    ("corpus", "backend/modules/corpus/u3_watermark_v2.sql"),
    ("discovery", "backend/modules/discovery/u3_schema.sql"),
    ("discovery", "backend/modules/discovery/u2_history_admission.sql"),
    ("discovery", "backend/modules/discovery/u3_grants.sql"),
    ("library", "backend/modules/library/u3_schema.sql"),
    ("library", "backend/modules/library/u2_history_binding.sql"),
    ("assistance", "backend/modules/summarization/u3_schema.sql"),
    ("assistance", "backend/modules/summarization/u3_glossary_v2.sql"),
    ("accounts", "backend/modules/accounts/u3_corpus_authority.sql"),
    ("accounts", "backend/modules/accounts/u3_session_authority.sql"),
    ("accounts", "backend/modules/accounts/u2_history_authority_grant.sql"),
    ("operations", "ops/src/docsuri_ops/u3_capacity.sql"),
)
PHASES = (
    "setup",
    "migrate",
    "database",
    "repository",
    "component",
    "integration",
    "browser",
    "operations",
    "coverage",
    "frontend",
    "serve",
    "teardown",
)

sys.path.insert(0, str(ROOT))

from backend.local_profile import LocalProfile, private_bytes  # noqa: E402


def require(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    result = command(args, **kwargs)
    if result.returncode:
        raise Refused(f"command failed ({result.returncode}): {args[0]}")
    return result


def source_identity() -> dict:
    """Extend the shared source inventory to this unit's tests and pipeline."""
    value = u1_source_identity()
    listed = require(
        [
            "git",
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
            "--",
            "tests/u3_paper_corpus_capabilities",
            "frontend/test/u3-paper-corpus-capabilities",
            "frontend/e2e/u3-paper-corpus-capabilities",
            ".github/workflows/u3-paper-corpus-capabilities.yml",
        ]
    )
    for name in sorted(set(listed.stdout.split("\0")) - {""}):
        path = ROOT / name
        if path.is_symlink():
            raise Refused("source inventory contains symlink")
        value["files"][name] = digest(path) if path.is_file() else None
    value["sha256"] = hashlib.sha256(
        json.dumps(value["files"], sort_keys=True).encode()
    ).hexdigest()
    return value


def private_json(path: Path, value: object) -> None:
    if path.parent != RUN or path.is_symlink():
        raise Refused("private output outside owned run")
    info = RUN.lstat()
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o700
    ):
        raise Refused("run directory ownership changed")
    temporary = path.with_name(path.name + ".pending-" + secrets.token_hex(8))
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def manifest(path: Path) -> tuple[LocalProfile, dict]:
    profile = LocalProfile.load(path)
    if profile.realm != "corpus-maintenance" or profile.root != RUN:
        raise Refused("U3 requires its own explicitly provisioned realm")
    value = json.loads(private_bytes(path))
    if value.get("databaseImage") != IMAGE:
        raise Refused("database artifact identity changed")
    if value.get("policy") != "u3-synthetic-v1":
        raise Refused("U3 finite policy identity changed")
    return profile, value


def owned_resource(kind: str, name: str, run_id: str) -> bool:
    result = command(
        [
            "docker",
            kind,
            "inspect",
            name,
            "--format",
            "{{json .Labels}}" if kind == "volume" else "{{json .Config.Labels}}",
        ]
    )
    if result.returncode:
        return False
    return json.loads(result.stdout or "{}").get(LABEL) == run_id


def require_resources(value: dict) -> None:
    for kind, field in (("container", "container"), ("volume", "volume")):
        if not owned_resource(kind, value[field], value["runId"]):
            raise Refused(
                "missing or foreign U3 resource; retain state for explicit recovery"
            )


def preflight() -> None:
    headroom(existing=True)
    if shutil.disk_usage(ROOT).free < 4 * GIB:
        raise Refused("U3 recovery allocation is unavailable")
    require(["docker", "image", "inspect", IMAGE])  # No download or paid fallback.
    info = json.loads(require(["docker", "info", "--format", "{{json .}}"]).stdout)
    if info["MemTotal"] < 1536 * 1024**2:
        raise Refused("database memory plus recovery reserve unavailable")


def check_ports() -> None:
    for port in (APPLICATION_PORT, DATABASE_PORT):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", port))


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


def setup(path: Path) -> dict:
    preflight()
    if RUN.exists():
        info = RUN.lstat()
        if (
            not stat.S_ISDIR(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o700
        ):
            raise Refused("existing run root is not a private owned directory")
        if any(RUN.iterdir()):
            _, value = manifest(path)
            require_resources(value)
            return {"state": "preserved", "runId": value["runId"]}
    check_ports()
    RUN.mkdir(mode=0o700, exist_ok=True)
    run_id = "docsuri-u3-" + secrets.token_hex(8)
    value = {
        "unit": UNIT,
        "profile": "synthetic-local",
        "repository": str(ROOT),
        "runId": run_id,
        "container": run_id,
        "volume": run_id + "-pgdata",
        "databaseImage": IMAGE,
        "database": DATABASE,
        "realm": "corpus-maintenance",
        "databasePort": DATABASE_PORT,
        "applicationPort": APPLICATION_PORT,
        "createdAt": time.time(),
        "expiresAt": time.time() + 86400,
        "sourceSha": require(["git", "rev-parse", "HEAD"]).stdout.strip(),
        "locks": {name: digest(ROOT / name) for name in LOCKS},
        "policy": "u3-synthetic-v1",
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
    private_json(
        RUN / "corpus-keys.json",
        {
            "runId": run_id,
            "version": "u3-synthetic-key-v1",
            "cursor": secrets.token_hex(32),
            "provider": secrets.token_hex(32),
        },
    )
    require(
        ["docker", "volume", "create", "--label", f"{LABEL}={run_id}", value["volume"]]
    )
    require(database_command(value), extra={"POSTGRES_PASSWORD": password})
    for _ in range(30):
        result = command(
            ["docker", "exec", run_id, "pg_isready", "-U", "postgres", "-d", DATABASE],
            timeout=3,
        )
        if result.returncode == 0:
            break
        time.sleep(0.5)
    else:
        raise Refused("database startup failed; owned resources preserved")
    # Re-exec the schema setup under the frozen backend interpreter; the user
    # may invoke this launcher with the system Python, which lacks psycopg.
    require(
        [
            str(PYTHON),
            str(Path(__file__)),
            "--phase",
            "migrate",
            "--base-only",
            "--profile",
            "synthetic-local",
            "--environment-file",
            str(path),
        ]
    )
    return {"state": "base-installed", "runId": run_id, "u3MigrationsApplied": False}


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


def migrate(path: Path, *, base_only: bool = False) -> dict:
    import psycopg
    from bootstrap_docsuri_u1 import SCHEMAS, amend
    from psycopg import sql

    _, value = manifest(path)
    require_resources(value)
    # Migrations are permitted only with the API stopped, never as a test read.
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", APPLICATION_PORT)) == 0:
            raise Refused("stop the application before migrating")
    credentials_path = RUN / "owner-credentials.json"
    if credentials_path.exists():
        credentials = json.loads(private_bytes(credentials_path))
        if credentials["runId"] != value["runId"] or set(credentials["roles"]) != set(
            SCHEMAS
        ):
            raise Refused("owner credential identity mismatch")
    else:
        credentials = {
            "runId": value["runId"],
            "roles": {name: secrets.token_urlsafe(32) for name in SCHEMAS},
        }
        private_json(credentials_path, credentials)
    hashes = {name: digest(ROOT / file) for name, file in SCHEMAS.items()}
    with connect_admin(value) as conn:
        if conn.execute("SHOW server_version").fetchone()[0].split()[0] != "16.15":
            raise Refused("pinned PostgreSQL version mismatch")
        if not conn.execute(
            "SELECT to_regclass('public.docsuri_local_identity')"
        ).fetchone()[0]:
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
                (value["runId"], psycopg.types.json.Jsonb(hashes)),
            )
            for name, file in SCHEMAS.items():
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
                conn.execute(
                    sql.SQL("CREATE SCHEMA {} AUTHORIZATION {}").format(schema, owner)
                )
                conn.execute(sql.SQL("SET LOCAL ROLE {}").format(owner))
                conn.execute(
                    sql.SQL(
                        "ALTER DEFAULT PRIVILEGES IN SCHEMA {} REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC"
                    ).format(schema)
                )
                conn.execute((ROOT / file).read_text(), prepare=False)
                conn.execute(
                    sql.SQL(
                        "CREATE TABLE {}.receipt (account_id uuid NOT NULL,kind text NOT NULL,key uuid NOT NULL,intent_hash text NOT NULL CHECK(intent_hash ~ '^[0-9a-f]{{64}}$'),outcome jsonb NOT NULL,created_at timestamptz NOT NULL DEFAULT clock_timestamp(),PRIMARY KEY(account_id,kind,key))"
                    ).format(schema)
                )
                conn.execute(
                    sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(schema, runtime)
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
                conn.execute("RESET ROLE")
                conn.execute(
                    sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(runtime)
                )
                conn.execute(
                    sql.SQL(
                        "GRANT SELECT ON public.docsuri_local_identity TO {}"
                    ).format(runtime)
                )
            for name in (
                "library",
                "personalization",
                "discovery",
                "usage",
                "assistance",
            ):
                runtime = sql.Identifier(f"docsuri_{name}")
                conn.execute(
                    sql.SQL("GRANT USAGE ON SCHEMA accounts TO {}").format(runtime)
                )
                conn.execute(
                    sql.SQL(
                        "GRANT EXECUTE ON FUNCTION accounts.guard_session(uuid,uuid,text) TO {}"
                    ).format(runtime)
                )
            for name in ("library", "discovery", "assistance"):
                runtime = sql.Identifier(f"docsuri_{name}")
                conn.execute(
                    sql.SQL("GRANT USAGE ON SCHEMA corpus TO {}").format(runtime)
                )
                conn.execute(
                    sql.SQL(
                        "GRANT EXECUTE ON FUNCTION corpus.guard_version(text,text) TO {}"
                    ).format(runtime)
                )
            conn.execute(
                "GRANT EXECUTE ON FUNCTION accounts.guard_execution(uuid,uuid) TO docsuri_assistance"
            )
            conn.execute(
                "GRANT SELECT ON corpus.paper,corpus.version,corpus.projection TO docsuri_discovery"
            )
        known = amend(conn, value, hashes)
        if not base_only:
            for owner, file in MIGRATIONS:
                current = digest(ROOT / file)
                if file in known:
                    if known[file] != current:
                        raise Refused(
                            "applied U3 migration changed; add a new ordered migration"
                        )
                    continue
                if file == "ops/src/docsuri_ops/u3_capacity.sql":
                    # Only the non-login schema owner receives aggregate WAL
                    # observation authority, never an application login role.
                    conn.execute(
                        "GRANT CONNECT ON DATABASE docsuri_u3 TO docsuri_operations_owner"
                    )
                    conn.execute(
                        "GRANT EXECUTE ON FUNCTION pg_catalog.pg_ls_waldir() "
                        "TO docsuri_operations_owner"
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
                (psycopg.types.json.Jsonb(known),),
            )
    if not base_only:
        # Establish verifier custody before test fixtures insert the first account.
        from backend.modules.accounts.services.guarded_entry import GuardedEntryService
        from backend.transactions import OwnerTransactions

        transactions = OwnerTransactions(LocalProfile.load(path))
        try:
            GuardedEntryService(transactions)
        finally:
            transactions.close()
        # Prepare the owned short-lived HTTPS transport while the API is stopped;
        # serving only ever inspects the already-provisioned material.
        sys.path.insert(0, str(ROOT / "ops/src"))
        from docsuri_ops.local_transport import prepare_transport

        prepare_transport(LocalProfile.load(path))
    return {
        "state": "base-verified" if base_only else "u3-migrated",
        "schemaHashes": known,
    }


def stop(process: subprocess.Popen) -> None:
    """Terminate the process group before reaping its leader; never replace it."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=3)


def process_rss(pid: int, deadline: float) -> int:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise Refused("process deadline reached")
    result = subprocess.run(
        ["ps", "-Ao", "pid=,ppid=,rss="],
        capture_output=True,
        text=True,
        timeout=min(1, remaining),
        check=True,
    )
    rows = [
        tuple(map(int, line.split()))
        for line in result.stdout.splitlines()
        if len(line.split()) == 3
    ]
    included = {pid}
    while True:
        expanded = included | {child for child, parent, _ in rows if parent in included}
        if expanded == included:
            break
        included = expanded
    return sum(rss * 1024 for child, _, rss in rows if child in included)


def bounded_process(args: list[str], log: Path, *, seconds: float = 300,
                    rss_limit: int = MAX_RSS) -> dict:
    if not 0 < seconds <= 300 or not 0 < rss_limit <= MAX_RSS:
        raise Refused("finite process bound required")
    descriptor = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    process = None
    beginning = time.monotonic()
    deadline = beginning + seconds
    observation_end = deadline - min(7, seconds / 2)
    count, peak, reason, code = 0, 0, "deadline", None
    environment = {
        key: os.environ[key] for key in ("PATH", "HOME", "TMPDIR", "LANG") if key in os.environ
    }
    environment.update(
        PYTHONPATH=str(ROOT),
        DOCSURI_U3_ENVIRONMENT_FILE=str(RUN / "environment.json"),
        CI="true",
        COREPACK_ENABLE_DOWNLOAD_PROMPT="0",
        COREPACK_ENABLE_NETWORK="0",
    )
    previous_signals = {value: signal.getsignal(value) for value in (signal.SIGTERM, signal.SIGINT)}

    def interrupted(signum, frame):
        raise RuntimeError("owned process supervision interrupted")

    for value in previous_signals:
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
            assert process.stdout is not None
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
                if time.monotonic() >= observation_end:
                    break
                peak = max(peak, process_rss(process.pid, observation_end))
                if peak > rss_limit:
                    raise Refused("process tree exceeded RSS safety budget")
                code = process.poll()
                if code is not None and not selector.get_map():
                    reason = "process-exit"
                    break
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        try:
            if process is not None:
                stop(process)
                if process.stdout is not None:
                    process.stdout.close()
        finally:
            for value, previous in previous_signals.items():
                signal.signal(value, previous)
    result = {
        "exitCode": code,
        "reason": reason,
        "elapsedSeconds": time.monotonic() - beginning,
        "peakRssBytes": peak,
        "logBytes": count,
        "processStopped": True,
    }
    if reason != "process-exit" or code != 0:
        raise Refused("owned process failed or ended outside its expected lifetime")
    return result


def run_phase(phase: str, path: Path) -> dict:
    _, value = manifest(path)
    require_resources(value)
    preflight()
    if {name: digest(ROOT / name) for name in LOCKS} != value["locks"]:
        raise Refused(
            "frozen dependency identity changed; reconcile environment before testing"
        )
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
            "vitest.u3-corpus.config.ts",
            "test/u3-paper-corpus-capabilities",
        ]
    elif phase == "browser":
        args = [
            str(ROOT / "frontend/node_modules/.bin/playwright"),
            "test",
            "--config",
            "frontend/playwright.u3-corpus.config.ts",
            "--max-failures=1",
        ]
    elif phase == "coverage":
        args = [
            str(PYTHON),
            "-m",
            "pytest",
            "-c",
            "backend/pytest.u3-paper-corpus.ini",
            "tests/u3_paper_corpus_capabilities/component",
            "--cov",
            "--cov-config=backend/.coveragerc.u3",
            "--cov-report=term-missing",
            "-q",
            f"--junitxml={RUN / (phase + '.xml')}",
        ]
    else:
        args = [
            str(PYTHON),
            "-m",
            "pytest",
            "-c",
            "backend/pytest.u3-paper-corpus.ini",
            f"tests/u3_paper_corpus_capabilities/{phase}",
            "-q",
            "--maxfail=1",
            f"--junitxml={RUN / (phase + '.xml')}",
        ]
    report = RUN / (phase + ".xml")
    if report.is_symlink():
        raise Refused("test report cannot be a symlink")
    report.unlink(missing_ok=True)  # A previous report can never certify this run.
    before = source_identity()
    start = time.monotonic()
    server = None
    if phase == "browser":
        # The owned Python supervisor runs the actual host for this phase only;
        # Playwright never attaches to an arbitrary existing listener.
        from docsuri_ops.local_transport import inspect_transport

        inspect_transport(LocalProfile.load(path))
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", APPLICATION_PORT)) == 0:
                raise Refused("owned U3 listener is already occupied")
        server = subprocess.Popen(
            [
                str(PYTHON),
                str(ROOT / "scripts/serve_docsuri_u3.py"),
                "--environment-file",
                str(path),
            ],
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            start_new_session=True,
            umask=0o077,
            env={
                **{
                    key: os.environ[key]
                    for key in ("PATH", "HOME", "TMPDIR", "LANG")
                    if key in os.environ
                },
                "PYTHONPATH": str(ROOT),
            },
        )
        try:
            ready_deadline = time.monotonic() + 30
            while True:
                if server.poll() is not None:
                    raise Refused("owned U3 server exited before the browser phase")
                with socket.socket() as probe:
                    if probe.connect_ex(("127.0.0.1", APPLICATION_PORT)) == 0:
                        break
                if time.monotonic() >= ready_deadline:
                    raise Refused("owned U3 server did not become ready")
                time.sleep(0.25)
        except BaseException:
            stop(server)
            server = None
            raise
    process_evidence, failure = {}, None
    try:
        process_evidence = bounded_process(
            args,
            RUN / f"u3-phase-{phase}-{time.time_ns()}.log",
            seconds=300,
        )
    except (Refused, RuntimeError, OSError) as error:
        failure = type(error).__name__
    finally:
        if server is not None:
            stop(server)
    evidence = {
        "phase": phase,
        "runId": value["runId"],
        "command": args,
        "exitCode": 1 if failure else process_evidence["exitCode"],
        "supervision": process_evidence,
        "failureCategory": failure,
        "durationSeconds": time.monotonic() - start,
        "source": before,
        "locks": value["locks"],
    }
    if phase not in ("frontend", "browser") and (RUN / (phase + ".xml")).exists():
        suite = ET.parse(RUN / (phase + ".xml")).getroot()
        cases = list(suite.iter("testcase"))
        evidence.update(
            tests=len(cases),
            failures=sum(1 for c in cases if c.find("failure") is not None),
            errors=sum(1 for c in cases if c.find("error") is not None),
            skipped=sum(1 for c in cases if c.find("skipped") is not None),
        )
        if not cases or evidence["skipped"]:
            evidence["exitCode"] = evidence["exitCode"] or 1
    elif phase not in ("frontend", "browser"):
        evidence["missingTestReport"] = True
        evidence["exitCode"] = evidence["exitCode"] or 1
    if source_identity()["sha256"] != before["sha256"]:
        evidence["sourceChangedDuringRun"] = True
        evidence["exitCode"] = evidence["exitCode"] or 1
    private_json(RUN / f"{phase}-evidence.json", evidence)
    print(
        json.dumps(
            {
                key: evidence[key]
                for key in (
                    "phase",
                    "exitCode",
                    "tests",
                    "failures",
                    "errors",
                    "skipped",
                )
                if key in evidence
            }
        )
    )
    if evidence["exitCode"]:
        raise Refused("U3 phase failed; no completion result recorded")
    return {"state": "passed", "phase": phase}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True, choices=PHASES)
    parser.add_argument("--profile", required=True, choices=["synthetic-local"])
    parser.add_argument("--environment-file", required=True, type=Path)
    parser.add_argument("--base-only", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if (
        args.environment_file.is_symlink()
        or args.environment_file.resolve() != RUN / "environment.json"
    ):
        raise Refused("only the U3 owned manifest is accepted")
    args.environment_file = args.environment_file.resolve()
    if args.phase == "setup":
        result = setup(args.environment_file)
    elif args.phase == "migrate":
        result = migrate(args.environment_file, base_only=args.base_only)
    elif args.phase == "serve":
        from scripts.serve_docsuri_u3 import serve

        result = serve(args.environment_file, 300)
    elif args.phase == "teardown":
        # Preserve failed/unknown responsibility evidence first; this runner
        # never deletes a synthetic run that still holds unresolved state.
        _, value = manifest(args.environment_file)
        evidence = sorted(p.name for p in RUN.glob("*-evidence.json"))
        print(
            json.dumps(
                {
                    "state": "preserved",
                    "runId": value["runId"],
                    "evidence": evidence,
                    "note": (
                        "automatic disposal is disabled; failed or unknown "
                        "responsibility evidence is retained for explicit recovery"
                    ),
                }
            )
        )
        return 0
    else:
        result = run_phase(args.phase, args.environment_file)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Refused, ValueError, OSError) as exc:
        print(f"U3 prerequisite refused: {exc}", file=sys.stderr)
        raise SystemExit(2)
