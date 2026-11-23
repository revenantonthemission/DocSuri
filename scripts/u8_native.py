"""The composed realm tool's release-side helpers (U8 plan Step 43; cicd-pipeline § 5.2;
your decision of 2026-10-24, "The release's performance phase").

- `--database native`: the realm's PostgreSQL from the arrangement's pinned runtime
  (`/Library/DocSuri/runtimes/postgresql-16.14`, with its pgvector), its data in the run
  root, on the realm's port 15509, `max_connections = 50` and `shared_buffers = 512MB`,
  run as the invoking account, with no container. `native_commands` gives its `initdb`,
  start, status and stop commands.
- The interpreter falls back to the release's own `.venv` when `backend/.venv` is absent
  (`python_for`).
- A release environment (a folder holding the release identity `.docsuri-release.json`)
  runs only the release's performance phases; any phase that needs pytest or the
  development tree is refused (`require_release_phase`).
- `--playwright <checkout>`: your checkout's Playwright binary, configuration and specs,
  once it is at the release's commit with a clean tree and an equal
  `frontend/pnpm-lock.yaml` (`playwright_checkout`).
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path

NATIVE_RUNTIME = Path("/Library/DocSuri/runtimes/postgresql-16.14")
RELEASE_IDENTITY = ".docsuri-release.json"
# The phases a release environment runs (`release-performance` and its steps).
RELEASE_PHASES = ("setup", "migrate", "fixtures", "serve", "performance", "archive-owned",
                  "teardown", "release-performance")
NATIVE_SETTINGS = (
    ("listen_addresses", "127.0.0.1"), ("shared_buffers", "512MB"), ("max_connections", "50"),
    ("work_mem", "16MB"), ("maintenance_work_mem", "256MB"),
    ("password_encryption", "scram-sha-256"), ("statement_timeout", "3000"),
    ("lock_timeout", "1000"), ("idle_in_transaction_session_timeout", "5000"),
    ("max_wal_size", "1GB"), ("wal_keep_size", "0"), ("archive_mode", "off"),
    ("max_replication_slots", "0"), ("max_wal_senders", "0"),
    # security-design § 7.2's log settings (Step 79(d)).
    ("log_min_messages", "log"), ("log_error_verbosity", "terse"),
    ("log_min_error_statement", "panic"), ("log_statement", "none"),
    ("log_min_duration_statement", "-1"), ("log_parameter_max_length", "0"),
    ("log_parameter_max_length_on_error", "0"),
)
START_SECONDS = 60


class NativeRefused(RuntimeError):
    """A release-side precondition failed; the message is a fixed reason."""


def python_for(root: Path) -> Path:
    """`backend/.venv`'s interpreter in the development tree, else the release's own
    `.venv` (decision "The release environment")."""
    development = root / "backend" / ".venv" / "bin" / "python"
    return development if development.exists() else root / ".venv" / "bin" / "python"


def release_identity(root: Path) -> dict | None:
    """The release identity the installer's staging wrote, or None in a development
    tree."""
    path = root / RELEASE_IDENTITY
    if not path.is_file() or path.is_symlink():
        return None
    try:
        value = json.loads(path.read_bytes())
    except ValueError:
        raise NativeRefused("release identity unreadable") from None
    if not isinstance(value, dict) or set(value) != {"tag", "commit"}:
        raise NativeRefused("release identity outside its form")
    return value


def require_release_phase(phase: str, root: Path) -> None:
    """From a release environment, only the release's performance phases run."""
    if release_identity(root) is not None and phase not in RELEASE_PHASES:
        raise NativeRefused(f"a release environment runs no {phase} phase; it needs pytest "
                            "or the development tree")


def native_commands(run: Path, *, port: int, runtime: Path = NATIVE_RUNTIME,
                    password_file: Path | None = None) -> dict[str, list[str]]:
    """`initdb` (SCRAM for loopback, the C locale, data checksums, the superuser's
    password from a private file), and the start, status and stop of the native server
    with its settings, its socket in the run root, as the invoking account."""
    data, socket = run / "pgdata", run / "pgsocket"
    options = " ".join([f"-p {port}", f"-k {socket}",
                        *(f"-c {name}={value}" for name, value in NATIVE_SETTINGS)])
    commands = {
        "start": [str(runtime / "bin" / "pg_ctl"), "-D", str(data), "-l",
                  str(run / "pgdata.log"), "-w", "-t", str(START_SECONDS), "-o", options,
                  "start"],
        "status": [str(runtime / "bin" / "pg_ctl"), "-D", str(data), "status"],
        "stop": [str(runtime / "bin" / "pg_ctl"), "-D", str(data), "-m", "fast", "-w", "-t",
                 str(START_SECONDS), "stop"],
    }
    if password_file is not None:
        commands["initdb"] = [str(runtime / "bin" / "initdb"), "-D", str(data), "-U",
                              "postgres", f"--pwfile={password_file}",
                              "--auth-host=scram-sha-256", "--auth-local=scram-sha-256",
                              "--encoding=UTF8", "--locale=C", "--data-checksums"]
    return commands


def runtime_present(runtime: Path = NATIVE_RUNTIME) -> bool:
    return all((runtime / "bin" / name).is_file()
               for name in ("initdb", "pg_ctl", "postgres", "pg_dump", "pg_restore"))


def playwright_checkout(checkout: Path, root: Path, *,
                        git: Callable[[list[str]], tuple[int, str]] | None = None) -> Path:
    """Your checkout, after the commit, clean-tree and lockfile checks against the
    release this tool runs from; returns its `frontend` folder."""
    from docsuri_ops.release import Refused, checkout_checks

    identity = release_identity(root)
    if identity is None:
        raise NativeRefused("--playwright runs only from a release environment")

    def run_git(arguments: list[str]) -> tuple[int, str]:
        completed = subprocess.run(["/usr/bin/git", "-C", str(checkout), *arguments],
                                   capture_output=True, timeout=60, check=False)
        return completed.returncode, completed.stdout.decode("utf-8", "replace")

    try:
        checkout_checks(checkout, commit=identity["commit"], folder=root, git=git or run_git)
    except Refused as refused:
        raise NativeRefused(refused.reason) from None
    frontend = checkout / "frontend"
    if not (frontend / "node_modules" / ".bin" / "playwright").exists():
        raise NativeRefused("playwright-checkout-has-no-playwright")
    return frontend
