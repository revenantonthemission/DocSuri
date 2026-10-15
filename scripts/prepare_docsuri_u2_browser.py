"""Reconcile explicit U2 browser dependencies or supervise one bounded HTTPS run."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import selectors
import signal
import socket
import stat
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "ops/src"))

import verify_docsuri_u2 as runner
from docsuri_ops.local_transport import inspect_transport

from backend.local_profile import private_bytes

MAX_LOG = 16 * 1024**2
MAX_RSS = 1024**3
PENDING = "browser-identity-pending.json"
IDENTITY_FIELDS = {"sourceSha", "sourceTreeSha256", "locks"}


def encoded(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, indent=2, allow_nan=False).encode()


def atomic_bytes(path: Path, payload: bytes) -> None:
    if path.parent != runner.RUN or path.is_symlink() or len(payload) > 65536:
        raise runner.Refused("invalid bounded private identity output")
    temporary = path.with_name(path.name + ".pending-write")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def exclusive():
    root = runner.RUN.lstat()
    if not stat.S_ISDIR(root.st_mode) or root.st_uid != os.getuid() or stat.S_IMODE(root.st_mode) != 0o700:
        raise runner.Refused("U2 run root custody mismatch")
    descriptor = os.open(runner.RUN / "fixture-run.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(descriptor)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
            raise runner.Refused("U2 run lock custody mismatch")
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(descriptor)


def checked(path: Path):
    if (runner.RUN / PENDING).exists() or (runner.RUN / PENDING).is_symlink():
        raise runner.Refused("interrupted identity update; run explicit recover first")
    profile, value = runner.manifest(path)
    runner.require_resources(value)
    runner.preflight()
    return profile, value


def reconcile(path: Path, previous: dict, replacement: dict) -> None:
    changed = {key for key in previous.keys() | replacement.keys() if previous.get(key) != replacement.get(key)}
    if not changed <= IDENTITY_FIELDS or previous["runId"] != replacement["runId"]:
        raise runner.Refused("identity update cannot change run, retention or service data")
    before = private_bytes(path)
    ownership = private_bytes(runner.RUN / "ownership.json")
    if (json.loads(before) != previous or json.loads(ownership) != {
            "runId": previous["runId"], "manifestSha256": hashlib.sha256(before).hexdigest()}):
        raise runner.Refused("environment changed before identity update")
    after = encoded(replacement)
    if len(after) > 16384:
        raise runner.Refused("environment identity exceeds manifest bound")
    new_owner = encoded({"runId": previous["runId"], "manifestSha256": hashlib.sha256(after).hexdigest()})
    pending = {"version": 1, "runId": previous["runId"], "before": before.decode(),
        "after": after.decode(), "ownershipBefore": ownership.decode(), "ownershipAfter": new_owner.decode()}
    atomic_bytes(runner.RUN / PENDING, encoded(pending))
    atomic_bytes(path, after)
    atomic_bytes(runner.RUN / "ownership.json", new_owner)
    runner.manifest(path)  # Full canonical load must agree before acknowledgement.
    (runner.RUN / PENDING).unlink()


def recover(path: Path) -> dict:
    """Explicitly roll metadata back, then require a fresh verified prepare."""
    pending_path = runner.RUN / PENDING
    pending = json.loads(private_bytes(pending_path, maximum=65536))
    before, after = pending["before"].encode(), pending["after"].encode()
    old, new = json.loads(before), json.loads(after)
    changed = {key for key in old.keys() | new.keys() if old.get(key) != new.get(key)}
    if (pending.get("version") != 1 or not changed <= IDENTITY_FIELDS
            or pending["runId"] != old["runId"] or old["runId"] != new["runId"]
            or not re.fullmatch(r"docsuri-u2-[0-9a-f]{16}", old["runId"])
            or private_bytes(path) not in (before, after)):
        raise runner.Refused("recovery identity is not a recognized interrupted update")
    for key, payload in (("ownershipBefore", before), ("ownershipAfter", after)):
        if json.loads(pending[key]) != {"runId": old["runId"], "manifestSha256": hashlib.sha256(payload).hexdigest()}:
            raise runner.Refused("recovery manifest digest mismatch")
    if private_bytes(runner.RUN / "ownership.json").decode() not in (pending["ownershipBefore"], pending["ownershipAfter"]):
        raise runner.Refused("recovery ownership has changed")
    atomic_bytes(path, before)
    atomic_bytes(runner.RUN / "ownership.json", pending["ownershipBefore"].encode())
    runner.manifest(path)  # Expired runs still fail; recovery never extends them.
    pending_path.unlink()
    return {"state": "identity-rolled-back", "runId": old["runId"], "prepareRequired": True}


def process_rss(pid: int, deadline: float) -> int:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise runner.Refused("process deadline reached")
    result = subprocess.run(["ps", "-Ao", "pid=,ppid=,rss="], capture_output=True,
        text=True, timeout=min(1, remaining), check=True)
    rows = [tuple(map(int, line.split())) for line in result.stdout.splitlines() if len(line.split()) == 3]
    included = {pid}
    while True:
        expanded = included | {child for child, parent, _ in rows if parent in included}
        if expanded == included:
            break
        included = expanded
    return sum(rss * 1024 for child, _, rss in rows if child in included)


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
    # The leader may exit while its child survives SIGTERM; fence the whole group.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=3)


def bounded_process(args: list[str], log: Path, *, seconds: float = 300,
                    rss_limit: int = MAX_RSS, expect_running: bool = False) -> dict:
    if not 0 < seconds <= 300 or not 0 < rss_limit <= MAX_RSS:
        raise runner.Refused("finite process bound required")
    existing_bytes = 0
    for prior in log.parent.glob("browser-*.log"):
        info = prior.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
            raise runner.Refused("existing private diagnostic custody differs")
        existing_bytes += info.st_size
    if existing_bytes >= MAX_LOG:
        raise runner.Refused("private diagnostics allocation already exhausted")
    descriptor = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    process = None
    beginning = time.monotonic()
    deadline = beginning + seconds
    observation_end = deadline - min(7, seconds / 2)
    count, peak, reason, code = 0, 0, "deadline", None
    environment = {key: os.environ[key] for key in ("PATH", "HOME", "TMPDIR", "LANG") if key in os.environ}
    environment.update(PYTHONPATH=str(ROOT), DOCSURI_U2_ENVIRONMENT_FILE=str(runner.RUN / "environment.json"),
        CI="true", COREPACK_ENABLE_DOWNLOAD_PROMPT="0", COREPACK_ENABLE_NETWORK="0")
    previous_signals = {value: signal.getsignal(value) for value in (signal.SIGTERM, signal.SIGINT)}

    def interrupted(signum, frame):
        # selectors catches InterruptedError as an interrupted syscall; use an
        # exception it cannot swallow so our finally block always stops children.
        raise RuntimeError("owned process supervision interrupted")

    for value in previous_signals:
        signal.signal(value, interrupted)
    try:
        with os.fdopen(descriptor, "wb") as stream, selectors.DefaultSelector() as selector:
            process = subprocess.Popen(args, cwd=ROOT, env=environment, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True,
                umask=0o077)
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
                    if existing_bytes + count > MAX_LOG:
                        raise runner.Refused("private process log exceeded 16 MiB")
                    stream.write(chunk)
                if time.monotonic() >= observation_end:
                    break
                peak = max(peak, process_rss(process.pid, observation_end))
                if peak > rss_limit:
                    raise runner.Refused("process tree exceeded RSS safety budget")
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
    result = {"exitCode": code, "reason": reason, "elapsedSeconds": time.monotonic() - beginning,
        "peakRssBytes": peak, "logBytes": count, "processStopped": True}
    if (not expect_running and (reason != "process-exit" or code != 0)) or (expect_running and reason == "process-exit"):
        raise runner.Refused("owned process failed or ended outside its expected lifetime")
    return result


def prepare(path: Path, store: Path) -> dict:
    _, value = checked(path)
    if store.is_symlink() or not store.is_dir() or store.stat().st_uid != os.getuid():
        raise runner.Refused("explicit existing owned pnpm store required")
    locks = {name: runner.digest(ROOT / name) for name in runner.LOCKS}
    if any(value["locks"].get(name) != checksum for name, checksum in locks.items()
           if name != "frontend/pnpm-lock.yaml"):
        raise runner.Refused("Python dependency change requires separate frozen environment verification")
    package = runner.digest(ROOT / "frontend/package.json")
    log = runner.RUN / f"browser-install-{time.time_ns()}.log"
    result = bounded_process(["corepack", "pnpm@9.15.9", "--dir", "frontend", "install",
        "--frozen-lockfile", "--offline", "--ignore-scripts", "--store-dir", str(store)], log)
    if locks != {name: runner.digest(ROOT / name) for name in runner.LOCKS} or package != runner.digest(ROOT / "frontend/package.json"):
        raise runner.Refused("dependency inputs changed during frozen installation")
    version = runner.require(["corepack", "pnpm@9.15.9", "--version"], timeout=10).stdout.strip()
    if version != "9.15.9":
        raise runner.Refused("pnpm tool identity mismatch")
    replacement = dict(value, locks=locks,
        sourceSha=runner.require(["git", "rev-parse", "HEAD"], timeout=10).stdout.strip(),
        sourceTreeSha256=runner.source_identity()["sha256"])
    reconcile(path, value, replacement)
    return {"state": "dependencies-reconciled", "runId": value["runId"], "pnpm": version, **result}


def serve(path: Path, seconds: int) -> dict:
    profile, value = checked(path)
    if {name: runner.digest(ROOT / name) for name in runner.LOCKS} != value["locks"]:
        raise runner.Refused("prepare the changed dependency identity before serving")
    inspect_transport(profile)
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", 18049)) == 0:
            raise runner.Refused("owned U2 listener is already occupied")
    return bounded_process([str(runner.PYTHON), str(ROOT / "scripts/serve_docsuri_u2.py"),
        "--environment-file", str(path)], runner.RUN / f"browser-server-{time.time_ns()}.log",
        seconds=seconds, expect_running=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("prepare", "recover", "serve"), required=True)
    parser.add_argument("--environment-file", type=Path, required=True)
    parser.add_argument("--store-dir", type=Path)
    parser.add_argument("--seconds", type=int, default=300)
    args = parser.parse_args()
    if args.environment_file.is_symlink() or args.environment_file.resolve() != runner.RUN / "environment.json":
        raise runner.Refused("only the exact U2 environment manifest is supported")
    path = args.environment_file.resolve()
    with exclusive():
        if args.phase == "prepare":
            if args.store_dir is None:
                parser.error("prepare requires an explicit --store-dir")
            result = prepare(path, args.store_dir)
        elif args.phase == "recover":
            result = recover(path)
        else:
            result = serve(path, args.seconds)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
