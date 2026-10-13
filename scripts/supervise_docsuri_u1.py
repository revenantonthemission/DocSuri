"""Versioned local supervisor for the owned synthetic U1 environment.

Every command is bound to the explicit manifest and only touches resources this
run owns: the disposable PostgreSQL container, the journey HTTPS transport, the
API process started from this checkout and the bounded local model endpoint.
Each command records bounded evidence in the run root; unknown profiles, foreign
containers, stale process files and missing transport material are refused.

Commands (all require --environment-file):
    status              bounded component and readiness report
    start-api           start the journey API from this checkout
    stop-api            stop the owned API process
    restart-api         stop then start; proves process replacement
    restart-container   restart the owned disposable database container
    backup              pg_dump the owned realm into a private dump file
    restore --from NAME restore the realm from an owned dump (coherent rollback)
    rollback --to NAME  alias of restore recorded as an explicit rollback
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import socket
import ssl
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "ops/src"))

from backend.local_profile import LocalProfile, private_bytes

PYTHON = ROOT / "backend/.venv/bin/python"
SERVE = ROOT / "scripts/serve_docsuri_u1.py"
API_TIMEOUT = 20.0


def _private_json(profile: LocalProfile, name: str, value: object) -> Path:
    path = profile.root / name
    temporary = path.with_name(path.name + ".pending")
    descriptor = os.open(
        temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
    )
    with os.fdopen(descriptor, "w") as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    return path


def _docker(
    args: list[str], *, stdin: bytes | None = None
) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", *args], input=stdin, capture_output=True, check=False, timeout=180
    )


def _record(profile: LocalProfile) -> dict:
    """The owned journey database record: container, volume and owner role."""
    return json.loads(private_bytes(profile.root / "journey-database.json"))


def _container(profile: LocalProfile) -> str:
    value = _record(profile).get("container")
    if not isinstance(value, str) or not value:
        raise ValueError("journey record carries no owned container")
    return value


def _container_state(profile: LocalProfile) -> str:
    result = _docker(["inspect", "--format", "{{.State.Status}}", _container(profile)])
    if result.returncode:
        return "absent"
    return result.stdout.decode().strip()


def _owns_container(profile: LocalProfile) -> bool:
    result = _docker(
        [
            "inspect",
            "--format",
            '{{index .Config.Labels "dev.docsuri.u1.run"}}',
            _container(profile),
        ]
    )
    return result.returncode == 0 and result.stdout.decode().strip() == profile.run_id


def _api_request(profile: LocalProfile, path: str, timeout: float = 3.0):
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    request = urllib.request.Request(
        profile.origin + path, headers={"Host": "127.0.0.1:18039"}
    )
    try:
        with urllib.request.urlopen(
            request, timeout=timeout, context=context
        ) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode())
    except (urllib.error.URLError, OSError, ValueError):
        return None, None


def _model_reachable(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except OSError:
        return False


def _read_pid(profile: LocalProfile) -> int | None:
    path = profile.root / "api.pid"
    if not path.exists() or path.is_symlink():
        return None
    info = path.lstat()
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
        raise ValueError("API process file custody differs")
    raw = json.loads(private_bytes(path))
    if raw.get("runId") != profile.run_id:
        raise ValueError("API process belongs to another run")
    return int(raw["pid"])


def _pid_alive(pid: int | None) -> bool:
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def status(profile: LocalProfile, manifest: dict) -> dict:
    pid = _read_pid(profile)
    api_live, ready = None, None
    if _pid_alive(pid):
        _, api_live = _api_request(profile, "/health/live")
        _, ready = _api_request(profile, "/health/ready")
    return {
        "runId": profile.run_id,
        "realm": profile.realm,
        "database": profile.database_name,
        "retentionExpiresAt": profile.expires_at,
        "retentionActive": time.time() < profile.expires_at,
        "container": _container_state(profile),
        "containerOwned": _owns_container(profile),
        "apiPid": pid,
        "apiRunning": _pid_alive(pid),
        "apiLive": api_live,
        "readiness": ready,
        "modelEndpointReachable": _model_reachable(int(manifest["modelPort"])),
        "transportPresent": (profile.root / "journey-tls.crt").is_file(),
    }


def start_api(profile: LocalProfile, manifest: Path) -> dict:
    existing = _read_pid(profile)
    if _pid_alive(existing):
        raise ValueError("owned API process already running")
    log = profile.root / "api.log"
    descriptor = os.open(
        log, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600
    )
    with os.fdopen(descriptor, "ab") as stream:
        process = subprocess.Popen(
            [str(PYTHON), str(SERVE), "--environment-file", str(manifest)],
            stdout=stream,
            stderr=stream,
            start_new_session=True,
            cwd=ROOT,
        )
    _private_json(profile, "api.pid", {"runId": profile.run_id, "pid": process.pid})
    deadline = time.monotonic() + API_TIMEOUT
    while time.monotonic() < deadline:
        code, _ = _api_request(profile, "/health/live")
        if code == 200:
            return {"apiPid": process.pid, "apiLive": True}
        if process.poll() is not None:
            raise ValueError("owned API process exited during startup")
        time.sleep(0.25)
    raise ValueError("owned API process did not become live within the bound")


def stop_api(profile: LocalProfile) -> dict:
    pid = _read_pid(profile)
    if pid is None:
        return {"stopped": False, "reason": "no owned process file"}
    if not _pid_alive(pid):
        (profile.root / "api.pid").unlink(missing_ok=True)
        return {"stopped": True, "alreadyExited": True}
    os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if not _pid_alive(pid):
            (profile.root / "api.pid").unlink(missing_ok=True)
            return {"stopped": True, "pid": pid}
        time.sleep(0.25)
    raise ValueError(
        "owned API process did not stop within the bound; refusing forced kill"
    )


def restart_container(profile: LocalProfile) -> dict:
    if not _owns_container(profile):
        raise ValueError("refusing to restart a container this run does not own")
    before = _docker(
        ["inspect", "--format", "{{.State.StartedAt}}", _container(profile)]
    ).stdout.decode().strip()
    result = _docker(["restart", "--time", "10", _container(profile)])
    if result.returncode:
        raise ValueError("owned container restart refused")
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if _container_state(profile) == "running":
            after = _docker(
                ["inspect", "--format", "{{.State.StartedAt}}", _container(profile)]
            ).stdout.decode().strip()
            return {
                "container": _container(profile),
                "state": "running",
                "replacedFrom": before,
                "startedAt": after,
            }
        time.sleep(0.5)
    raise ValueError("owned container did not return to running within the bound")


def _admin_password(profile: LocalProfile) -> str:
    record = json.loads(private_bytes(profile.root / "migration-credentials.json"))
    return str(record["databaseAdminPassword"])


def _dump_path(profile: LocalProfile, name: str) -> Path:
    if not name or "/" in name or name.startswith("."):
        raise ValueError("dump name outside the owned vocabulary")
    return profile.root / f"{name}.dump"


def backup(profile: LocalProfile, name: str) -> dict:
    if _container_state(profile) != "running" or not _owns_container(profile):
        raise ValueError("owned database container is not running")
    path = _dump_path(profile, name)
    if path.exists() or path.is_symlink():
        raise ValueError("refusing to overwrite an existing dump")
    result = _docker(
        [
            "exec",
            _container(profile),
            "pg_dump",
            "-U",
            "postgres",
            "-Fc",
            profile.database_name,
        ]
    )
    if result.returncode or not result.stdout:
        raise ValueError("owned realm dump refused")
    descriptor = os.open(
        path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
    )
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(result.stdout)
        stream.flush()
        os.fsync(stream.fileno())
    evidence = {
        "name": name,
        "database": profile.database_name,
        "sha256": hashlib.sha256(result.stdout).hexdigest(),
        "byteLength": len(result.stdout),
        "recordedAt": time.time(),
    }
    _private_json(profile, f"backup-{name}.json", evidence)
    return evidence


def restore(profile: LocalProfile, name: str) -> dict:
    path = _dump_path(profile, name)
    if path.is_symlink() or not path.is_file():
        raise ValueError("owned dump missing")
    info = path.lstat()
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
        raise ValueError("dump custody differs")
    payload = private_bytes(path, maximum=1 << 30)
    if not _owns_container(profile) or _container_state(profile) != "running":
        raise ValueError("owned database container is not running")
    # The reviewed dump also exists on the container filesystem copy for pg_restore.
    inner = f"/tmp/{profile.run_id}-{name}.dump"
    written = _docker(
        ["exec", "-i", _container(profile), "sh", "-c", f"cat > {inner}"], stdin=payload
    )
    if written.returncode:
        raise ValueError("dump staging refused")
    password = _admin_password(profile)
    owner = str(_record(profile)["ownerRole"])
    for statement in (
        f"DROP DATABASE IF EXISTS {profile.database_name} WITH (FORCE)",
        f"CREATE DATABASE {profile.database_name} OWNER {owner} TEMPLATE template0",
    ):
        result = _docker(
            [
                "exec",
                "-e",
                f"PGPASSWORD={password}",
                _container(profile),
                "psql",
                "-U",
                "postgres",
                "-c",
                statement,
            ]
        )
        if result.returncode:
            raise ValueError("owned realm restore refused during database recreation")
    result = _docker(
        [
            "exec",
            "-e",
            f"PGPASSWORD={password}",
            _container(profile),
            "pg_restore",
            "-U",
            "postgres",
            "--no-owner",
            "--role",
            owner,
            "-d",
            profile.database_name,
            inner,
        ]
    )
    if result.returncode:
        raise ValueError("owned realm restore refused during data load")
    evidence = {
        "name": name,
        "database": profile.database_name,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "restoredAt": time.time(),
    }
    _private_json(profile, f"restore-{name}.json", evidence)
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=(
            "status",
            "start-api",
            "stop-api",
            "restart-api",
            "restart-container",
            "backup",
            "restore",
            "rollback",
        ),
    )
    parser.add_argument("--environment-file", type=Path, required=True)
    parser.add_argument("--from", dest="source")
    parser.add_argument("--to", dest="target")
    parser.add_argument("--name", default="realm")
    args = parser.parse_args()
    manifest = args.environment_file.resolve()
    raw = json.loads(manifest.read_text())
    profile = LocalProfile.load(manifest).journey()
    if args.command == "status":
        report = status(profile, raw)
    elif args.command == "start-api":
        report = start_api(profile, manifest)
    elif args.command == "stop-api":
        report = stop_api(profile)
    elif args.command == "restart-api":
        stop_api(profile)
        report = {"replaced": True, **start_api(profile, manifest)}
    elif args.command == "restart-container":
        report = restart_container(profile)
    elif args.command == "backup":
        report = backup(profile, args.name)
    elif args.command == "restore":
        report = restore(profile, args.source or args.name)
    else:
        report = {"rollback": True, **restore(profile, args.target or args.name)}
        _private_json(profile, "rollback.json", report)
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
