"""Bounded U2 synthetic runner; never a completion approval or real-data tool.

Setup is idempotent and never reseeds an existing run. Schema changes are a
separate explicit migrate phase. Inspection/test phases cannot initialize data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import shutil
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

from verify_docsuri_u1 import (
    GIB,
    IMAGE,
    LOCKS,
    ROOT,
    Refused,
    command,
    digest,
    headroom,
)
from verify_docsuri_u1 import (
    source_identity as u1_source_identity,
)

RUN = Path("/tmp/docsuri-u2-run").resolve()
PYTHON = ROOT / "backend/.venv/bin/python"
LABEL = "dev.docsuri.u2.run"
UNIT = "u2-account-personal-controls"
DATABASE = "docsuri_u2"
DATABASE_PORT = 15449
APPLICATION_PORT = 18049
MIGRATIONS = (
    ("accounts", "backend/modules/accounts/u2_controls.sql"),
    ("personalization", "backend/modules/personalization/u2_controls.sql"),
    ("library", "backend/modules/library/u2_controls.sql"),
    ("usage", "backend/modules/plans/u2_controls.sql"),
    ("assistance", "backend/modules/summarization/u2_controls.sql"),
    ("accounts", "backend/modules/accounts/u2_consent_projection.sql"),
    ("accounts", "backend/modules/accounts/u2_personalization_status.sql"),
    ("corpus", "backend/modules/corpus/u2_personalization_read.sql"),
    ("personalization", "backend/modules/personalization/u2_cleanup_permissions.sql"),
    ("accounts", "backend/modules/accounts/u2_assignment_target.sql"),
    ("accounts", "backend/modules/accounts/u2_consent_obligation.sql"),
    ("accounts", "backend/modules/accounts/u2_personalization_effect.sql"),
    ("discovery", "backend/modules/discovery/u2_history_admission.sql"),
    ("library", "backend/modules/library/u2_history_binding.sql"),
    ("accounts", "backend/modules/accounts/u2_history_authority_grant.sql"),
    ("accounts", "backend/modules/accounts/u2_lifecycle_effect.sql"),
    ("accounts", "backend/modules/accounts/u2_lifecycle_action.sql"),
    ("accounts", "backend/modules/accounts/u2_lifecycle_owner_grants.sql"),
    ("library", "backend/modules/library/u2_erasure.sql"),
    ("personalization", "backend/modules/personalization/u2_erasure.sql"),
    ("accounts", "backend/modules/accounts/u2_consent_time.sql"),
    ("accounts", "backend/modules/accounts/u2_reset_confirmation.sql"),
    ("accounts", "backend/modules/accounts/u2_owner_cleanup.sql"),
    ("discovery", "backend/modules/discovery/u2_owner_cleanup.sql"),
    ("assistance", "backend/modules/summarization/u2_owner_cleanup.sql"),
)
PHASES = (
    "setup",
    "migrate",
    "database",
    "repository",
    "component",
    "integration",
    "frontend",
    "browser",
    "operations",
    "serve",
    "teardown",
)

sys.path.insert(0, str(ROOT))

from backend.local_profile import LocalProfile, private_bytes


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
            "tests/u2_account_personal_controls",
            ".github/workflows/u2-account-controls.yml",
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
    if profile.realm != "account-controls" or profile.root != RUN:
        raise Refused("U2 requires its own explicitly provisioned realm")
    value = json.loads(private_bytes(path))
    if value.get("databaseImage") != IMAGE:
        raise Refused("database artifact identity changed")
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
                "missing or foreign U2 resource; retain state for explicit recovery"
            )


def preflight() -> None:
    headroom(existing=True)
    if shutil.disk_usage(ROOT).free < 4 * GIB:
        raise Refused("U2 recovery allocation is unavailable")
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
    run_id = "docsuri-u2-" + secrets.token_hex(8)
    value = {
        "unit": UNIT,
        "profile": "synthetic-local",
        "repository": str(ROOT),
        "runId": run_id,
        "container": run_id,
        "volume": run_id + "-pgdata",
        "databaseImage": IMAGE,
        "database": DATABASE,
        "realm": "account-controls",
        "databasePort": DATABASE_PORT,
        "applicationPort": APPLICATION_PORT,
        "createdAt": time.time(),
        "expiresAt": time.time() + 86400,
        "sourceSha": require(["git", "rev-parse", "HEAD"]).stdout.strip(),
        "locks": {name: digest(ROOT / name) for name in LOCKS},
        "policy": "u2-synthetic-v1",
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
        RUN / "control-keys.json",
        {
            "runId": run_id,
            "version": "synthetic-key-v1",
            "seed": secrets.token_hex(32),
            "cursor": secrets.token_hex(32),
            "proof": secrets.token_hex(32),
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
    return {"state": "base-installed", "runId": run_id, "u2MigrationsApplied": False}


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
                            "applied U2 migration changed; add a new ordered migration"
                        )
                    continue
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
    return {
        "state": "base-verified" if base_only else "u2-migrated",
        "schemaHashes": known,
    }


def run_phase(phase: str, path: Path) -> dict:
    _, value = manifest(path)
    require_resources(value)
    preflight()
    if {name: digest(ROOT / name) for name in LOCKS} != value["locks"]:
        raise Refused(
            "frozen dependency identity changed; reconcile environment before testing"
        )
    environment = {"DOCSURI_U2_ENVIRONMENT_FILE": str(path), "PYTHONPATH": str(ROOT)}
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
            "vitest.u2-account-controls.config.ts",
            "test/u2-account-personal-controls",
        ]
    elif phase == "browser":
        args = [
            "corepack",
            "pnpm@9.15.9",
            "--dir",
            "frontend",
            "exec",
            "playwright",
            "test",
            "--config",
            "playwright.u2-account-controls.config.ts",
        ]
    else:
        args = [
            str(PYTHON),
            "-m",
            "pytest",
            "-c",
            "backend/pytest.u2-account-personal-controls.ini",
            f"tests/u2_account_personal_controls/{phase}",
            "-q",
            f"--junitxml={RUN / (phase + '.xml')}",
        ]
    report = RUN / (phase + ".xml")
    if report.is_symlink():
        raise Refused("test report cannot be a symlink")
    report.unlink(missing_ok=True)  # A previous report can never certify this run.
    before = source_identity()
    start = time.monotonic()
    result = command(args, extra=environment, timeout=300)
    evidence = {
        "phase": phase,
        "runId": value["runId"],
        "command": args,
        "exitCode": result.returncode,
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
    # Raw pytest exceptions can include passwords, seeds or private payloads.
    # Expose only structural counts here; fault diagnostics use owner allowlists.
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
        raise Refused("U2 phase failed; no completion result recorded")
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
        raise Refused("only the U2 owned manifest is accepted")
    args.environment_file = args.environment_file.resolve()
    if args.phase == "setup":
        result = setup(args.environment_file)
    elif args.phase == "migrate":
        result = migrate(args.environment_file, base_only=args.base_only)
    elif args.phase in ("serve", "teardown"):
        raise Refused(
            "phase implementation not yet available; preserve owned resources"
        )
    else:
        result = run_phase(args.phase, args.environment_file)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Refused, ValueError, OSError) as exc:
        print(f"U2 prerequisite refused: {exc}", file=sys.stderr)
        raise SystemExit(2)
