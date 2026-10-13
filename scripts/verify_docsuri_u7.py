"""Bounded, manifest-scoped U7 development runner; never a unit approval.

Orchestrates only the approved U7 phases against one owned synthetic-local
environment. It rejects unknown phases, escaping paths, missing dependencies, an
unavailable required service and an empty behaviour-test collection; its phase
selector never falls back to a repository-wide test run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import stat
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = Path("/tmp/docsuri-u7-run").resolve()
IMAGE = "postgres@sha256:a3b7f434b2dc57ce85a67e171163eb8ab1a1ebcb39d27484661f26b1dfbe30d6"
GIB = 1024**3
PYTHON = ROOT / "backend/.venv/bin/python"
LABEL = "dev.docsuri.u7.run"
SCOPES = ("component", "database", "repository", "integration", "operations")
PHASES = ("setup", "runner-readiness", *SCOPES, "coverage", "teardown")
LOCKS = ("backend/uv.lock", "shared/python/uv.lock")
FIXTURE_TARGETS = ("u7-alpha", "u7-beta", "u7-release")


class Refused(RuntimeError):
    """A bounded precondition failed; no successful behavioural result exists."""


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_identity() -> dict:
    result = require(
        [
            "git",
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
            "--",
            "ops/src/docsuri_ops/platform_control",
            "scripts",
            "tests/u7_controlled_platform_protocols",
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


def private_json(path: Path, value: object) -> None:
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


def require(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    result = command(args, **kwargs)
    if result.returncode:
        raise Refused(f"command failed with exit {result.returncode}: {args[0]}")
    return result


def load_manifest(path: Path) -> dict:
    if path != RUN / "environment.json" or path.is_symlink():
        raise Refused("environment-file must be the exact isolated U7 manifest")
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
    if value.get("profile") != "synthetic-local" or value.get("repository") != str(ROOT):
        raise Refused("wrong repository/profile")
    if not re.fullmatch(r"docsuri-u7-[0-9a-f]{16}", value.get("runId", "")):
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
        "256m",
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
        "127.0.0.1:15440:5432",
        "--mount",
        f"type=volume,src={value['volume']},dst=/var/lib/postgresql/data",
    ]
    if initialize:
        args.extend(
            [
                "-e",
                "POSTGRES_PASSWORD",
                "-e",
                "POSTGRES_DB=docsuri_u7",
                "-e",
                "POSTGRES_INITDB_ARGS=--data-checksums --auth-host=scram-sha-256",
            ]
        )
    return args + [
        IMAGE,
        "-c",
        "shared_buffers=32MB",
        "-c",
        "max_connections=12",
        "-c",
        "statement_timeout=5000",
        "-c",
        "lock_timeout=2000",
        "-c",
        "idle_in_transaction_session_timeout=5000",
    ]


def wait_database(value: dict) -> None:
    for _ in range(40):
        result = command(
            [
                "docker",
                "exec",
                value["container"],
                "pg_isready",
                "-U",
                "postgres",
                "-d",
                "docsuri_u7",
            ],
            timeout=3,
        )
        if result.returncode == 0:
            return
        time.sleep(0.5)
    raise Refused("owned PostgreSQL did not become ready; persistent resources retained")


def ensure_targets(value: dict) -> None:
    root = Path(value["targetRoot"])
    root.mkdir(mode=0o700, exist_ok=True)
    for name in FIXTURE_TARGETS:
        (root / name).mkdir(mode=0o700, exist_ok=True)


def bootstrap() -> dict:
    result = require([str(PYTHON), str(ROOT / "scripts/bootstrap_docsuri_u7.py")])
    return json.loads(result.stdout)


def setup(path: Path) -> dict:
    if RUN.exists():
        value = load_manifest(path)
        if not resource_matches("container", value["container"], value["runId"]):
            raise Refused("existing manifest has a missing or foreign container")
        ensure_targets(value)
        require([str(PYTHON), str(ROOT / "scripts/bootstrap_docsuri_u7.py")])
        return value
    if shutil_free() < 8 * GIB:
        raise Refused("insufficient free space for the owned environment")
    require(["docker", "image", "inspect", IMAGE])  # never pull an absent image
    RUN.mkdir(mode=0o700, exist_ok=True)
    run_id = "docsuri-u7-" + secrets.token_hex(8)
    value = {
        "profile": "synthetic-local",
        "repository": str(ROOT),
        "runId": run_id,
        "container": run_id,
        "volume": run_id + "-pgdata",
        "databaseImage": IMAGE,
        "database": "docsuri_u7",
        "databasePort": 15440,
        "createdAt": time.time(),
        "expiresAt": time.time() + 86400,
        "sourceSha": require(["git", "rev-parse", "HEAD"]).stdout.strip(),
        "targetRoot": str(RUN / "targets"),
        "limits": {"hostFreeBytes": 8 * GIB, "postgresMemory": 256 * 1024**2},
        "locks": {p: digest(ROOT / p) for p in LOCKS},
    }
    private_json(path, value)
    private_json(RUN / "ownership.json", {"runId": run_id, "manifestSha256": digest(path)})
    administrator_password = secrets.token_urlsafe(32)
    private_json(RUN / "migration-credentials.json", {"databaseAdminPassword": administrator_password})
    ensure_targets(value)
    require(["docker", "volume", "create", "--label", f"{LABEL}={run_id}", value["volume"]])
    require(database_command(value, initialize=True), extra={"POSTGRES_PASSWORD": administrator_password})
    wait_database(value)
    result = bootstrap()
    print(json.dumps({"schemaState": result.get("schemaState"), "runId": run_id}, sort_keys=True))
    return value


def replace_database(value: dict) -> None:
    for kind, key in (("container", "container"), ("volume", "volume")):
        if not resource_matches(kind, value[key], value["runId"]):
            raise Refused("replacement resource identity mismatch")
    require(["docker", "stop", "--time", "10", value["container"]])
    require(["docker", "rm", value["container"]])
    require(database_command(value, initialize=False))
    wait_database(value)


def shutil_free() -> int:
    import shutil

    return shutil.disk_usage(ROOT).free


def python_args(phase: str, *, collect: bool = False) -> list[str]:
    directory = ROOT / "tests/u7_controlled_platform_protocols" / phase
    if not directory.is_dir() or directory.is_symlink():
        raise Refused(f"{phase}: required test directory not authored")
    args = [
        str(PYTHON),
        "-m",
        "pytest",
        "-c",
        "backend/pytest.u7-platform-control.ini",
        str(directory),
        "-m",
        "u7_" + phase,
        "-p",
        "no:cacheprovider",
    ]
    return args + (
        ["--collect-only", "-q"]
        if collect
        else ["-q", "--tb=short", "--junitxml", str(RUN / f"{phase}-junit.xml")]
    )


def run_phase(phase: str, value: dict, path: Path) -> None:
    collect = python_args(phase, collect=True)
    execute = python_args(phase)
    extra = {
        "DOCSURI_U7_ENVIRONMENT_FILE": str(path),
        "DOCSURI_U7_RUN": str(RUN),
    }
    result = command(collect, extra=extra)
    match = re.search(r"(\d+) tests? collected", result.stdout)
    count = int(match[1]) if match else 0
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
        raise Refused(f"{phase}: collection failed or empty; no behaviour passed")
    xml_path = RUN / f"{phase}-junit.xml"
    xml_path.unlink(missing_ok=True)
    result = command(execute, extra=extra, timeout=1800)
    report["executedExit"] = result.returncode
    try:
        counts = {key: 0 for key in ("tests", "failures", "errors", "skipped")}
        for suite in ET.parse(xml_path).getroot().iter("testsuite"):
            for key in counts:
                counts[key] += int(suite.get(key, "0"))
        counts["passed"] = counts["tests"] - sum(counts[k] for k in ("failures", "errors", "skipped"))
        report["outcomes"] = counts
    except (OSError, ValueError, ET.ParseError):
        report["outcomes"] = {"passed": 0, "missingReport": True}
    report["sourceUnchangedDuringRun"] = source_identity()["sha256"] == identity["sha256"]
    private_json(RUN / f"{phase}-result.json", report)
    print(result.stdout)
    print(result.stderr, file=sys.stderr)
    if result.returncode:
        raise Refused(f"{phase}: child failure propagated ({result.returncode})")
    if not report["sourceUnchangedDuringRun"]:
        raise Refused(f"{phase}: source changed during execution; repeat with stable bytes")
    outcomes = report["outcomes"]
    if (
        outcomes.get("passed", 0) < 1
        or outcomes.get("skipped", 0)
        or outcomes.get("failures", 0)
        or outcomes.get("errors", 0)
    ):
        raise Refused(f"{phase}: required cases skipped or no passing behaviour recorded")


def readiness(value: dict) -> None:
    if time.time() >= value["expiresAt"]:
        raise Refused("synthetic environment retention expired")
    if not PYTHON.is_file():
        raise Refused("locked backend environment missing")
    require(
        [
            str(PYTHON),
            "-c",
            (
                "import pytest, pytest_cov, psycopg; "
                "from docsuri_shared.workspace import wire, execution; "
                "from docsuri_ops.platform_control import cli, store, executor, inventory"
            ),
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
        if not (ROOT / "tests/u7_controlled_platform_protocols" / phase).is_dir()
    ]
    print(
        json.dumps(
            {
                "runnerImports": "ready",
                "notAuthored": missing,
                "behaviourTestsPassed": False,
                "requiredDatabaseExecutorEvidence": "pending",
            }
        )
    )


def run_coverage(value: dict, path: Path) -> None:
    directory = ROOT / "tests/u7_controlled_platform_protocols"
    args = [
        str(PYTHON),
        "-m",
        "pytest",
        "-c",
        "backend/pytest.u7-platform-control.ini",
        str(directory),
        "-q",
        "--cov=docsuri_ops.platform_control",
        "--cov-report=json:" + str(RUN / "coverage.json"),
        "--cov-report=term-missing",
        "-p",
        "no:cacheprovider",
    ]
    extra = {"DOCSURI_U7_ENVIRONMENT_FILE": str(path), "DOCSURI_U7_RUN": str(RUN)}
    result = command(args, extra=extra, timeout=1800)
    print(result.stdout)
    if result.returncode:
        raise Refused(f"coverage: child failure propagated ({result.returncode})")
    report = json.loads((RUN / "coverage.json").read_text())
    per_file = {
        name: data.get("summary", {}).get("percent_covered", 0.0)
        for name, data in report.get("files", {}).items()
    }
    # The floor is applied to every measured module; there is no name-based
    # exclusion. In-process tests exercise each module, including the native
    # adapter and the package entrypoint.
    below = {name: pct for name, pct in per_file.items() if pct < 80.0}
    private_json(RUN / "coverage-summary.json", {"perFile": per_file, "belowFloor": below})
    print(json.dumps({"measured": len(per_file), "belowFloor": below}, sort_keys=True))
    if below:
        raise Refused("coverage: changed module below the 80% line floor")


def teardown(value: dict) -> None:
    for kind, key in (("container", "container"), ("volume", "volume")):
        if not resource_matches(kind, value[key], value["runId"]):
            raise Refused("unknown or missing resource ownership; teardown refused")
    require(["docker", "stop", "--time", "10", value["container"]])
    require(["docker", "rm", value["container"]])
    require(["docker", "volume", "rm", value["volume"]])
    print("Owned container and volume removed; private manifest/evidence retained.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True, choices=PHASES)
    parser.add_argument("--profile", required=True, choices=["local", "synthetic-local"])
    parser.add_argument("--environment-file", required=True, type=Path)
    args = parser.parse_args()
    resolved = args.environment_file.absolute()
    if resolved != Path("/tmp/docsuri-u7-run/environment.json"):
        parser.error("only the approved isolated environment-file is accepted")
    path = RUN / "environment.json"
    try:
        value = setup(path) if args.phase == "setup" else load_manifest(path)
        if args.phase == "setup":
            print("Owned persistent PostgreSQL and PlatformControl schema ready.")
        elif args.phase == "runner-readiness":
            readiness(value)
        elif args.phase == "teardown":
            teardown(value)
        elif args.phase == "coverage":
            readiness(value)
            run_coverage(value, path)
        else:
            readiness(value)
            run_phase(args.phase, value, path)
        return 0
    except (Refused, OSError, ValueError, KeyError) as exc:
        print(f"U7 REFUSED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
