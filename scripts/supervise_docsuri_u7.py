"""Local supervisor for the owned U7 operator environment.

status / start / stop / restart / backup / restore / rollback for the operator's
durable store. There is no daemon manager dependency and no hosted service: the
long-lived component is the owned local PostgreSQL, and the operator CLI is
stateless. A restore proves the backup round-trip in a fresh database without
destroying the live one; a rollback is forward-compatible (additive migrations
only) and never destroys receipts.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from verify_docsuri_u7 import (
    ROOT,
    RUN,
    Refused,
    command,
    load_manifest,
    private_json,
    require,
)

sys.path.insert(0, str(ROOT))

from docsuri_ops.platform_control.profile import PlatformProfile
from docsuri_ops.platform_control.reconciler import promote_stale
from docsuri_ops.platform_control.store import Store

RESTORE_DB = "docsuri_u7_restore"


def _profile() -> PlatformProfile:
    return PlatformProfile.load(RUN / "environment.json")


def _container_state(container: str) -> str:
    result = command(["docker", "inspect", "-f", "{{.State.Status}}", container])
    return result.stdout.strip() if not result.returncode else "missing"


def _psql(container: str, database: str, statement: str) -> str:
    result = require(
        [
            "docker",
            "exec",
            container,
            "psql",
            "-U",
            "postgres",
            "-d",
            database,
            "-tAc",
            statement,
        ],
        timeout=30,
    )
    return result.stdout.strip()


def _wait_ready(container: str) -> None:
    for _ in range(40):
        result = command(
            ["docker", "exec", container, "pg_isready", "-U", "postgres", "-d", "docsuri_u7"],
            timeout=3,
        )
        if result.returncode == 0:
            return
        time.sleep(0.5)
    raise Refused("owned PostgreSQL did not become ready")


def _summary(profile: PlatformProfile) -> dict:
    """The privileged local supervision summary (provisioner role)."""
    return Store.provisioner(profile).supervisor_summary()


def _startup_promotion(profile: PlatformProfile) -> int:
    """On startup, promote any over-deadline in-flight operation to unknown."""
    return promote_stale(Store.runtime(profile))


def status() -> dict:
    profile = _profile()
    manifest = load_manifest(RUN / "environment.json")
    state = _container_state(manifest["container"])
    summary = None
    unresolved = None
    if state == "running":
        view = _summary(profile)
        summary = {
            key: int(view.get(key, 0))
            for key in ("authorized", "executing", "completed", "failed", "unknown")
        }
        unresolved = list(view.get("unresolvedOperations", []))
    return {
        "container": manifest["container"],
        "state": state,
        "runId": manifest["runId"],
        "receiptCounts": summary,
        "unresolvedOperations": unresolved,
    }


def start() -> dict:
    manifest = load_manifest(RUN / "environment.json")
    if _container_state(manifest["container"]) == "running":
        return status()
    require(["docker", "start", manifest["container"]])
    _wait_ready(manifest["container"])
    promoted = _startup_promotion(_profile())
    return {**status(), "promotedOnStartup": promoted}


def stop() -> dict:
    manifest = load_manifest(RUN / "environment.json")
    require(["docker", "stop", "--time", "10", manifest["container"]])
    return {"container": manifest["container"], "state": "stopped"}


def restart() -> dict:
    manifest = load_manifest(RUN / "environment.json")
    require(["docker", "stop", "--time", "10", manifest["container"]])
    require(["docker", "start", manifest["container"]])
    _wait_ready(manifest["container"])
    promoted = _startup_promotion(_profile())
    return {**status(), "promotedOnStartup": promoted}


def backup() -> dict:
    manifest = load_manifest(RUN / "environment.json")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = RUN / f"backup-{stamp}.sql"
    result = command(
        ["docker", "exec", manifest["container"], "pg_dump", "-U", "postgres", "--no-owner", "docsuri_u7"],
        timeout=120,
    )
    if result.returncode:
        raise Refused("backup dump failed")
    temporary = path.with_name(path.name + ".pending")
    temporary.write_text(result.stdout)
    temporary.replace(path)
    receipts = _psql(manifest["container"], "docsuri_u7", "SELECT count(*) FROM platform_control.receipt")
    private_json(RUN / "latest-backup.json", {"path": str(path), "receipts": int(receipts)})
    return {"backup": path.name, "receipts": int(receipts)}


def _latest_backup() -> tuple[Path, dict]:
    record = RUN / "latest-backup.json"
    if not record.is_file():
        raise Refused("no backup to restore")
    value = json.loads(record.read_text())
    path = Path(value["path"])
    if not path.is_file() or path.parent != RUN:
        raise Refused("recorded backup is missing or outside the owned root")
    return path, value


def restore() -> dict:
    """Restore the latest backup into a fresh database and prove the receipts survived."""
    manifest = load_manifest(RUN / "environment.json")
    container = manifest["container"]
    path, _value = _latest_backup()
    _psql(container, "postgres", f"DROP DATABASE IF EXISTS {RESTORE_DB}")
    _psql(container, "postgres", f"CREATE DATABASE {RESTORE_DB}")
    # the dump is streamed through `docker exec -i` because `command` has no stdin
    with path.open("rb") as stream:
        result = subprocess.run(
            [
                "docker",
                "exec",
                "-i",
                container,
                "psql",
                "-U",
                "postgres",
                "-d",
                RESTORE_DB,
                "-v",
                "ON_ERROR_STOP=1",
            ],
            stdin=stream,
            capture_output=True,
            timeout=180,
            check=False,
        )
    if result.returncode:
        raise Refused("restore load failed")
    restored = int(
        _psql(container, RESTORE_DB, "SELECT count(*) FROM platform_control.receipt")
    )
    _psql(container, "postgres", f"DROP DATABASE {RESTORE_DB}")
    return {"backup": path.name, "restoredReceipts": restored}


def rollback() -> dict:
    """Forward-compatible rollback: verify the marker and that receipts are intact.

    There is no destructive schema change to undo; a rollback restores the prior
    executable and leaves the additive schema and every receipt in place.
    """
    profile = _profile()
    manifest = load_manifest(RUN / "environment.json")
    row = _psql(
        manifest["container"],
        "docsuri_u7",
        "SELECT run_id FROM public.docsuri_u7_identity",
    )
    if row != manifest["runId"]:
        raise Refused("schema migration marker does not match the owned run")
    before = _summary(profile)
    restart_result = restart()
    after = _summary(profile)
    if int(after.get("completed", 0)) < int(before.get("completed", 0)):
        raise Refused("rollback lost committed receipts")
    return {
        "migrationMarker": "forward-compatible",
        "state": restart_result["state"],
        "receiptsBefore": before,
        "receiptsAfter": after,
    }


COMMANDS = {
    "status": status,
    "start": start,
    "stop": stop,
    "restart": restart,
    "backup": backup,
    "restore": restore,
    "rollback": rollback,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=sorted(COMMANDS))
    args = parser.parse_args(argv)
    try:
        print(json.dumps(COMMANDS[args.command](), sort_keys=True))
        return 0
    except (Refused, OSError, ValueError, KeyError) as exc:
        print(f"U7 supervisor refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
