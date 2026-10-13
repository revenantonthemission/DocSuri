"""Bounded, manifest-scoped U1 development runner; never a unit approval."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import stat
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = Path("/tmp/docsuri-u1-run").resolve()
IMAGE = (
    "postgres@sha256:a3b7f434b2dc57ce85a67e171163eb8ab1a1ebcb39d27484661f26b1dfbe30d6"
)
GIB = 1024**3
PYTHON = ROOT / "backend/.venv/bin/python"

# Bounded fixture transition for the browser phase: the synthetic realm admits
# two active accounts, so every active account is deactivated for the run (the
# browser scenarios register their own two owners) and the established demo
# account is reactivated afterwards. Nothing is deleted; no other data is
# touched, and the demo account keeps every row and its evidence.
BROWSER_RESET = """
import json, sys
from pathlib import Path
import psycopg
from backend.local_profile import LocalProfile

profile = LocalProfile.load(Path(sys.argv[1])).journey()
credentials = json.loads((profile.root / "owner-credentials.json").read_text())
with psycopg.connect(
    host="127.0.0.1",
    port=profile.database_port,
    dbname=profile.database_name,
    user="docsuri_accounts",
    password=credentials["roles"]["accounts"],
    connect_timeout=3,
) as conn:
    rows = conn.execute(
        "UPDATE accounts.account SET active=false WHERE active RETURNING email"
    ).fetchall()
    # The finite attempt ledger is test-owned diagnostic state, reset between
    # runs like the pytest fixture does; the 20/minute policy stays untouched.
    conn.execute("DELETE FROM accounts.entry_budget")
    conn.commit()
print(json.dumps({"deactivated": sorted(row[0] for row in rows)}))
"""

BROWSER_RESTORE = """
import json, sys
from pathlib import Path
import psycopg
from backend.local_profile import LocalProfile

profile = LocalProfile.load(Path(sys.argv[1])).journey()
credentials = json.loads((profile.root / "owner-credentials.json").read_text())
demo = json.loads((profile.root / "journey-account-a.json").read_text())["email"]
pattern = "browser-%@journey.fixture.example.com"

def connect(owner):
    return psycopg.connect(
        host="127.0.0.1",
        port=profile.database_port,
        dbname=profile.database_name,
        user="docsuri_" + owner,
        password=credentials["roles"][owner],
        connect_timeout=3,
    )

with connect("accounts") as conn:
    accounts = [
        row[0]
        for row in conn.execute(
            "SELECT id FROM accounts.account WHERE email LIKE %s", (pattern,)
        ).fetchall()
    ]
    if accounts:
        for owner, statements in {
            "assistance": (
                "DELETE FROM assistance.event WHERE job_id IN (SELECT id FROM assistance.job WHERE account_id = ANY(%s))",
                "DELETE FROM assistance.result WHERE account_id = ANY(%s)",
                "DELETE FROM assistance.job WHERE account_id = ANY(%s)",
                "DELETE FROM assistance.admission WHERE account_id = ANY(%s)",
                "DELETE FROM assistance.glossary WHERE account_id = ANY(%s)",
            ),
            "usage": (
                "DELETE FROM usage.reservation WHERE account_id = ANY(%s)",
                "DELETE FROM usage.entitlement WHERE account_id = ANY(%s)",
            ),
            "library": (
                "DELETE FROM library.saved_paper WHERE account_id = ANY(%s)",
                "DELETE FROM library.saved_query WHERE account_id = ANY(%s)",
                "DELETE FROM library.history WHERE account_id = ANY(%s)",
                "DELETE FROM library.history_boundary WHERE account_id = ANY(%s)",
            ),
            "personalization": (
                "DELETE FROM personalization.settings WHERE account_id = ANY(%s)",
                "DELETE FROM personalization.behavior WHERE account_id = ANY(%s)",
            ),
            "discovery": ("DELETE FROM discovery.execution WHERE account_id = ANY(%s)",),
        }.items():
            with connect(owner) as owner_conn:
                for statement in statements:
                    owner_conn.execute(statement, (accounts,))
                owner_conn.commit()
        conn.execute(
            "DELETE FROM accounts.delivery WHERE challenge_id IN (SELECT id FROM "
            "accounts.challenge WHERE account_id = ANY(%s))",
            (accounts,),
        )
        conn.execute("DELETE FROM accounts.challenge WHERE account_id = ANY(%s)", (accounts,))
        conn.execute("DELETE FROM accounts.session WHERE account_id = ANY(%s)", (accounts,))
        conn.execute("DELETE FROM accounts.consent WHERE account_id = ANY(%s)", (accounts,))
        conn.execute("DELETE FROM accounts.account WHERE id = ANY(%s)", (accounts,))
    conn.execute(
        "UPDATE accounts.account SET active=true WHERE email=%s AND NOT active", (demo,)
    )
    conn.commit()
print(json.dumps({"reactivated": demo}))
"""
SCOPES = (
    "database",
    "repository",
    "component",
    "contracts",
    "model",
    "integration",
    "operations",
)
PHASES = (
    "setup",
    "runner-readiness",
    *SCOPES,
    "frontend",
    "browser",
    "coverage",
    "teardown",
)
LABEL = "dev.docsuri.u1.run"
LOCKS = ("backend/uv.lock", "frontend/pnpm-lock.yaml", "shared/python/uv.lock")


def source_identity() -> dict:
    """Bind evidence to actual tracked and newly authored bytes, not just HEAD."""
    result = require(
        [
            "git",
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
            "--",
            "backend",
            "frontend",
            "shared",
            "scripts",
            "tests/u1_integrated_paper_journey",
            "ops",
            "ingestion",
        ]
    )
    files = {}
    for name in sorted(set(result.stdout.split("\0")) - {""}):
        path = ROOT / name
        if path.is_symlink():
            raise Refused("source inventory contains symlink")
        files[name] = digest(path) if path.is_file() else None
    encoded = json.dumps(files, sort_keys=True).encode()
    return {
        "head": require(["git", "rev-parse", "HEAD"]).stdout.strip(),
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "files": files,
    }


class Refused(RuntimeError):
    """A bounded precondition failed; no successful behavioral result exists."""


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def private_json(path: Path, value: object) -> None:
    """Publish only in this manifest-owned directory; never follow a symlink."""
    if path.parent.resolve() != RUN or path.is_symlink():
        raise Refused("unsafe private record path")
    temporary = path.with_name(path.name + ".pending")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, sort_keys=True, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def clean_environment() -> dict[str, str]:
    # Do not pass production database, cloud credentials or provider settings.
    allowed = ("PATH", "LANG", "LC_ALL", "TMPDIR", "SYSTEMROOT")
    return {name: os.environ[name] for name in allowed if name in os.environ}


def command(
    args: list[str],
    *,
    cwd: Path = ROOT,
    timeout: int = 120,
    extra: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    env = clean_environment()
    env.update(extra or {})
    try:
        return subprocess.run(
            args,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Refused(f"command unavailable or timed out: {args[0]}") from exc


def redact_output(value: str) -> str:
    """Known disposable credentials never leave private child process capture."""
    for name in ("owner-credentials.json", "migration-credentials.json"):
        path = RUN / name
        if path.is_file() and not path.is_symlink():
            record = json.loads(path.read_text())
            secrets_to_hide = list(record.get("roles", {}).values())
            if record.get("databaseAdminPassword"):
                secrets_to_hide.append(record["databaseAdminPassword"])
            for secret in secrets_to_hide:
                value = value.replace(secret, "[REDACTED]")
    return value


def require(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    result = command(args, **kwargs)
    if result.returncode:
        raise Refused(f"command failed with exit {result.returncode}: {args[0]}")
    return result


def headroom(*, existing: bool = False) -> None:
    # A repeat setup reserves the remaining allocation, not a second copy of
    # already installed build files. Runtime/recovery reserves stay untouched.
    occupied = 0
    if existing:
        paths = [
            ROOT / name
            for name in ("backend/.venv", "frontend/node_modules", "frontend/dist")
        ]
        for path in paths:
            if path.is_symlink():
                raise Refused("build allocation cannot follow a symlink")
        present = [str(path) for path in paths if path.exists()]
        if present:
            measured = require(["du", "-sk", *present])
            occupied = sum(
                int(line.split()[0]) * 1024 for line in measured.stdout.splitlines()
            )
        if occupied > 2 * GIB:
            raise Refused("measured build allocation exceeds 2 GiB")
    if shutil.disk_usage(ROOT).free < 12 * GIB - occupied:
        raise Refused(
            "insufficient free space for host floor and remaining allocated headroom"
        )


def load_manifest(path: Path) -> dict:
    if path != RUN / "environment.json" or path.is_symlink():
        raise Refused("environment-file must be the exact isolated U1 manifest")
    for candidate in (RUN, path, RUN / "ownership.json"):
        info = candidate.lstat()
        if (
            stat.S_ISLNK(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) & 0o077
        ):
            raise Refused("fixture ownership or private permissions do not match")
    value = json.loads(path.read_text())
    marker = json.loads((RUN / "ownership.json").read_text())
    if marker != {"runId": value.get("runId"), "manifestSha256": digest(path)}:
        raise Refused("ownership marker does not match exact manifest bytes")
    if value.get("profile") != "synthetic-local" or value.get("repository") != str(
        ROOT
    ):
        raise Refused("wrong repository/profile")
    if not re.fullmatch(r"docsuri-u1-[0-9a-f]{16}", value.get("runId", "")):
        raise Refused("invalid resource ownership identity")
    if value.get("databaseImage") != IMAGE:
        raise Refused("database image identity changed")
    return value


def resource_matches(kind: str, name: str, run_id: str) -> bool:
    result = command(["docker", kind, "inspect", name])
    if result.returncode:
        return False
    items = json.loads(result.stdout)
    labels = (
        items[0].get("Labels")
        if kind == "volume"
        else items[0].get("Config", {}).get("Labels")
    )
    return (labels or {}).get(LABEL) == run_id


def database_command(value: dict, *, initialize: bool) -> list[str]:
    args = [
        "docker",
        "run",
        "-d",
        "--name",
        value["container"],
        "--label",
        f"{LABEL}={value['runId']}",
        "--memory",
        "512m",
        "--cpus",
        "0.5",
        "--pids-limit",
        "64",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,size=16m",
        "--tmpfs",
        "/var/run/postgresql:rw,noexec,nosuid,size=16m",
        "-p",
        "127.0.0.1:15439:5432",
        "--mount",
        f"type=volume,src={value['volume']},dst=/var/lib/postgresql/data",
    ]
    if initialize:
        args.extend(
            [
                "-e",
                "POSTGRES_PASSWORD",
                "-e",
                "POSTGRES_DB=docsuri_u1",
                "-e",
                "POSTGRES_INITDB_ARGS=--data-checksums --auth-host=scram-sha-256",
            ]
        )
    return args + [
        IMAGE,
        "-c",
        "shared_buffers=32MB",
        "-c",
        "work_mem=2MB",
        "-c",
        "max_connections=12",
        "-c",
        "statement_timeout=5000",
        "-c",
        "lock_timeout=2000",
        "-c",
        "idle_in_transaction_session_timeout=5000",
        "-c",
        "max_wal_size=128MB",
    ]


def wait_database(value: dict) -> None:
    for _ in range(30):
        result = command(
            [
                "docker",
                "exec",
                value["container"],
                "pg_isready",
                "-U",
                "postgres",
                "-d",
                "docsuri_u1",
            ],
            timeout=3,
        )
        if result.returncode == 0:
            return
        time.sleep(0.5)
    raise Refused(
        "owned PostgreSQL did not become ready; persistent resources retained"
    )


def replace_database(value: dict) -> None:
    """Replace only this owned container, never the shared VM or its volume."""
    for kind, key in (("container", "container"), ("volume", "volume")):
        if not resource_matches(kind, value[key], value["runId"]):
            raise Refused("replacement resource identity mismatch")
    require(["docker", "stop", "--time", "10", value["container"]])
    require(["docker", "rm", value["container"]])
    require(database_command(value, initialize=False))
    wait_database(value)


def setup(path: Path) -> dict:
    if RUN.exists():
        value = load_manifest(path)
        headroom(existing=True)
        if not resource_matches("container", value["container"], value["runId"]):
            raise Refused(
                "existing manifest has missing or foreign container; recover explicitly"
            )
        # Initial setup-only credential record is separated before an API can
        # consume this public resource manifest. Never hand migration authority
        # to the runtime application profile.
        if "databaseAdminPassword" in value:
            private_json(
                RUN / "migration-credentials.json",
                {"databaseAdminPassword": value.pop("databaseAdminPassword")},
            )
            private_json(path, value)
            private_json(
                RUN / "ownership.json",
                {"runId": value["runId"], "manifestSha256": digest(path)},
            )
        rewritten = False
        current_locks = {name: digest(ROOT / name) for name in LOCKS}
        if value["locks"] != current_locks:
            # An explicit setup invocation adopts an authored dependency change,
            # preserves the old configuration identity, and requires fresh tests.
            value.setdefault("configurationHistory", []).append(
                {"locks": value["locks"], "replacedAt": time.time()}
            )
            value["locks"] = current_locks
            rewritten = True
        # An explicit setup invocation renews finite retention of the owned
        # environment when the current window is nearly or already over,
        # recording the superseded window in the configuration history.
        if value["expiresAt"] <= time.time() + 3600:
            value.setdefault("configurationHistory", []).append(
                {"expiresAt": value["expiresAt"], "renewedAt": time.time()}
            )
            value["expiresAt"] = time.time() + 86400
            rewritten = True
        if rewritten:
            private_json(path, value)
            private_json(
                RUN / "ownership.json",
                {"runId": value["runId"], "manifestSha256": digest(path)},
            )
        return value
    headroom()
    require(["docker", "image", "inspect", IMAGE])  # Never pull an absent image.
    RUN.mkdir(mode=0o700)
    run_id = "docsuri-u1-" + secrets.token_hex(8)
    value = {
        "profile": "synthetic-local",
        "repository": str(ROOT),
        "runId": run_id,
        "container": run_id,
        "volume": run_id + "-pgdata",
        "databaseImage": IMAGE,
        "database": "docsuri_u1",
        "databasePort": 15439,
        "applicationPort": 18039,
        "modelPort": 11439,
        "createdAt": time.time(),
        "expiresAt": time.time() + 86400,
        "sourceSha": require(["git", "rev-parse", "HEAD"]).stdout.strip(),
        "limits": {
            "hostFreeBytes": 8 * GIB,
            "buildBytes": 2 * GIB,
            "runtimeBytes": GIB,
            "recoveryBytes": GIB,
            "postgresMemory": 512 * 1024**2,
        },
        "locks": {p: digest(ROOT / p) for p in LOCKS},
        "fixtureAccounts": [],
        "fixturePapers": [],
    }
    private_json(path, value)
    private_json(
        RUN / "ownership.json", {"runId": run_id, "manifestSha256": digest(path)}
    )
    administrator_password = secrets.token_urlsafe(32)
    private_json(
        RUN / "migration-credentials.json",
        {"databaseAdminPassword": administrator_password},
    )
    require(
        ["docker", "volume", "create", "--label", f"{LABEL}={run_id}", value["volume"]]
    )
    require(
        database_command(value, initialize=True),
        extra={"POSTGRES_PASSWORD": administrator_password},
    )
    wait_database(value)
    return value


def python_args(phase: str, *, collect: bool = False) -> list[str]:
    directory = ROOT / "tests/u1_integrated_paper_journey" / phase
    if not directory.is_dir() or directory.is_symlink():
        raise Refused(f"{phase}: required test directory not authored")
    args = [
        str(PYTHON),
        "-m",
        "pytest",
        "-c",
        "backend/pytest.u1-paper-journey.ini",
        str(directory),
        "-m",
        "u1_" + phase,
        "-p",
        "no:cacheprovider",
    ]
    return args + (
        ["--collect-only", "-q"]
        if collect
        else ["-q", "--tb=short", "--junitxml", str(RUN / f"{phase}-junit.xml")]
    )


def phase_commands(phase: str) -> tuple[list[str], list[str], Path]:
    if phase in SCOPES:
        return python_args(phase, collect=True), python_args(phase), ROOT
    if phase == "frontend":
        base = ["corepack", "pnpm@9.15.9", "exec", "vitest"]
        config = ["--config", "vitest.u1-paper-journey.config.ts"]
        return (
            base + ["list", "--json"] + config,
            base
            + ["run"]
            + config
            + ["--reporter=json", "--outputFile", str(RUN / "frontend-outcomes.json")],
            ROOT / "frontend",
        )
    if phase == "browser":
        base = [
            "corepack",
            "pnpm@9.15.9",
            "exec",
            "playwright",
            "test",
            "--config",
            "playwright.u1-paper-journey.config.ts",
        ]
        return base + ["--list"], base + ["--reporter=json"], ROOT / "frontend"
    raise Refused(
        "coverage requires a completed explicit source inventory; not yet available"
    )


def reset_browser_owners(path: Path) -> None:
    """Free the finite two-account allocation for the browser scenarios.

    Every active account is deactivated for the run and the established demo
    account is reactivated afterwards; nothing is deleted and the demo account
    keeps every row and its evidence.
    """
    result = command([str(PYTHON), "-c", BROWSER_RESET, str(path)], cwd=ROOT)
    if result.returncode:
        raise Refused("browser fixture transition refused")


def restore_browser_demo(path: Path) -> None:
    result = command([str(PYTHON), "-c", BROWSER_RESTORE, str(path)], cwd=ROOT)
    if result.returncode:
        raise Refused("browser demo restore refused")


def ensure_journey_transport(path: Path) -> None:
    """Mint or renew the owned journey HTTPS material for the current retention.

    The certificate is bound to the manifest retention window, so an explicitly
    renewed window re-mints only the three owned transport files; no trust
    store or unrelated material is touched.
    """
    manifest = json.loads(path.read_text())
    record = RUN / "journey-tls.json"
    stale = True
    if record.is_file() and not record.is_symlink():
        try:
            stale = int(json.loads(record.read_text())["expiresAt"]) != int(
                manifest["expiresAt"]
            )
        except (KeyError, TypeError, ValueError):
            stale = True
    if stale:
        for name in ("journey-tls.key", "journey-tls.crt", "journey-tls.json"):
            (RUN / name).unlink(missing_ok=True)
    require(
        [
            str(PYTHON),
            str(ROOT / "scripts/prepare_docsuri_u1_transport.py"),
            "--environment-file",
            str(path),
        ]
    )


def run_phase(phase: str, value: dict, path: Path) -> None:
    collect, execute, cwd = phase_commands(phase)
    extra = {
        "DOCSURI_U1_ENVIRONMENT_FILE": str(path),
        "DOCSURI_U1_ORIGIN": f"http://127.0.0.1:{value['applicationPort']}",
    }
    result = command(collect, cwd=cwd, extra=extra)
    if phase in SCOPES:
        match = re.search(r"(\d+) tests? collected", result.stdout)
        count = int(match[1]) if match else 0
    elif phase == "frontend":
        try:
            count = len(json.loads(result.stdout))
        except ValueError:
            count = 0
    else:
        match = re.search(r"Total: (\d+) tests?", result.stdout)
        count = int(match[1]) if match else 0
    if phase == "browser":
        ensure_journey_transport(path)
        reset_browser_owners(path)
    identity = source_identity()
    report = {
        "phase": phase,
        "source": identity,
        "collectionCommand": collect,
        "collectionExit": result.returncode,
        "collected": count,
        "executedCommand": execute,
        "executedExit": None,
        "timestamp": time.time(),
    }
    if result.returncode or count < 1:
        private_json(RUN / f"{phase}-result.json", report)
        raise Refused(f"{phase}: collection failed or empty; no behavior passed")
    outcome_path = RUN / (
        f"{phase}-junit.xml" if phase in SCOPES else f"{phase}-outcomes.json"
    )
    if outcome_path.is_symlink():
        raise Refused("unsafe prior outcome report")
    outcome_path.unlink(missing_ok=True)
    result = command(execute, cwd=cwd, extra=extra, timeout=1800)
    if phase == "browser":
        restore_browser_demo(path)
    report["executedExit"] = result.returncode
    if phase in SCOPES:
        xml_path = RUN / f"{phase}-junit.xml"
        try:
            suites = ET.parse(xml_path).getroot().iter("testsuite")
            counts = {key: 0 for key in ("tests", "failures", "errors", "skipped")}
            for suite in suites:
                for key in counts:
                    counts[key] += int(suite.get(key, "0"))
            counts["passed"] = counts["tests"] - sum(
                counts[k] for k in ("failures", "errors", "skipped")
            )
            report["outcomes"] = counts
        except (OSError, ValueError, ET.ParseError):
            report["outcomes"] = {"passed": 0, "missingReport": True}
    else:
        try:
            outcomes = json.loads(
                outcome_path.read_text() if phase == "frontend" else result.stdout
            )
            if phase == "frontend":
                report["outcomes"] = {
                    "passed": outcomes["numPassedTests"],
                    "skipped": outcomes["numPendingTests"]
                    + outcomes.get("numTodoTests", 0),
                    "failures": outcomes["numFailedTests"],
                }
            else:
                stats = outcomes["stats"]
                report["outcomes"] = {
                    "passed": stats["expected"],
                    "skipped": stats["skipped"],
                    "failures": stats["unexpected"] + stats["flaky"],
                }
        except (OSError, ValueError, KeyError):
            report["outcomes"] = {"passed": 0, "missingReport": True}
    report["sourceUnchangedDuringRun"] = (
        source_identity()["sha256"] == identity["sha256"]
    )
    private_json(RUN / f"{phase}-result.json", report)
    print(redact_output(result.stdout))
    print(redact_output(result.stderr), file=sys.stderr)
    if result.returncode:
        raise Refused(f"{phase}: child failure propagated ({result.returncode})")
    if not report["sourceUnchangedDuringRun"]:
        raise Refused(
            f"{phase}: source changed during execution; repeat with stable bytes"
        )
    if (
        report["outcomes"]["passed"] < 1
        or report["outcomes"].get("skipped", 0)
        or report["outcomes"].get("failures", 0)
        or report["outcomes"].get("errors", 0)
    ):
        raise Refused(
            f"{phase}: required cases skipped or no passing behavior recorded"
        )


def readiness(value: dict) -> None:
    if time.time() >= value["expiresAt"]:
        raise Refused("synthetic environment retention expired")
    if not PYTHON.is_file():
        raise Refused("locked backend environment missing")
    require(
        [
            str(PYTHON),
            "-c",
            "import pytest, pytest_cov, fastapi, psycopg, psycopg_pool; from docsuri_shared.workspace import wire, execution",
        ]
    )
    for path, expected in value["locks"].items():
        if digest(ROOT / path) != expected:
            raise Refused("dependency lock differs from environment manifest")
    if not resource_matches("container", value["container"], value["runId"]):
        raise Refused("required owned database unavailable")
    missing = [
        phase
        for phase in SCOPES
        if not (ROOT / "tests/u1_integrated_paper_journey" / phase).is_dir()
    ]
    print(
        json.dumps(
            {
                "runnerImports": "ready",
                "notAuthored": missing,
                "behaviorTestsPassed": False,
                "requiredModelAndMountedEvidence": "pending",
            }
        )
    )


def teardown(value: dict) -> None:
    # No recursive filesystem removal: retain private records until evidence is extracted.
    for kind, key in (("container", "container"), ("volume", "volume")):
        name = value[key]
        if not resource_matches(kind, name, value["runId"]):
            raise Refused("unknown or missing resource ownership; teardown refused")
    require(["docker", "stop", "--time", "10", value["container"]])
    require(["docker", "rm", value["container"]])
    require(["docker", "volume", "rm", value["volume"]])
    print("Owned container and volume removed; private manifest/evidence retained.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True, choices=PHASES)
    parser.add_argument("--profile", required=True, choices=["synthetic-local"])
    parser.add_argument("--environment-file", required=True, type=Path)
    args = parser.parse_args()
    path = args.environment_file.absolute()
    if path != Path("/tmp/docsuri-u1-run/environment.json"):
        parser.error("only the approved isolated environment-file is accepted")
    path = RUN / "environment.json"
    try:
        value = setup(path) if args.phase == "setup" else load_manifest(path)
        if args.phase == "setup":
            print(
                "Owned persistent PostgreSQL created; owner migrations and behavioral evidence pending."
            )
        elif args.phase == "runner-readiness":
            readiness(value)
        elif args.phase == "teardown":
            teardown(value)
        else:
            readiness(value)
            run_phase(args.phase, value, path)
        return 0
    except (Refused, OSError, ValueError, KeyError) as exc:
        print(f"U1 REFUSED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
