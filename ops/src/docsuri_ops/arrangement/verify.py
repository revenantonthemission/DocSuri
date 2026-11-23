"""The installation's verification (U8 plan Step 37; Workflow 20 step 11, plan section
"Completion and evidence boundaries").

When the installer runs in person as root, `run_checks` executes the checks that need
the real arrangement, records each result in the installation log, and ends with the
runtime isolation check. Each check is decided by the outcome of its own tool calls: one
call each, except the check of the runtime's client programs, which asks each of the three
for its version and for the libraries it loads. So the logic is tested here with fakes
and runs for real only at the installation:

- **in person (D4):** an in-person command run without your password is refused (`sudo
  -n` as your login account), and so is any in-person command for the scheduler;
- **standing grants:** the scheduler runs its unattended set without a password;
- **NFR1.5:** the service account may run nothing through sudo;
- **D5:** your login account cannot read the operator tool's keychain item;
- **NFR3.3:** a TCP login as the superuser fails;
- **NFR3.3, "through libpq 16 or later" (L4-5 (A)):** the pinned runtime's `pg_dump`,
  `pg_restore` and `psql` each report the pinned version and load the runtime's own
  libpq, the one built with them, and no other;
- **NFR3.7:** both Time Machine exclusions hold;
- **the isolation check** passes every item.

What cannot be decided by one tool call here (the same through SSH, another account's
listener while its service is stopped, the restart within 3 minutes) is a checklist
item of the restart phase, recorded as you confirm it.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from . import render, timemachine
from .macos import SECURITY, SYSTEM_KEYCHAIN, ToolFailed
from .runtimes import POSTGRESQL_VERSION

SUDO = "/usr/bin/sudo"
# The runtime's client programs that open connections to v2's instance: the backup
# agent's and the production tool's dumps and restores, and the installer's own `psql`.
RUNTIME_CLIENTS = ("pg_dump", "pg_restore", "psql")


def _refused(tools, argv: list[str]) -> bool:
    """The command must fail (a nonzero exit is the expected answer)."""
    try:
        tools.run(argv, seconds=30)
    except ToolFailed:
        return True
    return False


def _allowed(tools, argv: list[str]) -> bool:
    try:
        tools.run(argv, seconds=60)
    except ToolFailed:
        return False
    return True


def _client_is_pinned(tools, runtime: Path, name: str) -> bool:
    """One client program of the runtime reports the pinned version, and every libpq it
    loads is the runtime's own: an absolute path under the runtime's folder. A libpq
    named through `@rpath` or another folder, or none at all, does not pass."""
    program = runtime / "bin" / name
    reported = tools.run([str(program), "--version"], seconds=30).decode().strip()
    if reported != f"{name} (PostgreSQL) {POSTGRESQL_VERSION}":
        return False
    libraries = tools.libraries(program) or []
    libpq = [library for library in libraries if Path(library).name.startswith("libpq.")]
    own = str(runtime).rstrip("/") + "/"
    return bool(libpq) and all(library.startswith(own) for library in libpq)


def _runtime_clients_pinned(tools, runtime: Path) -> bool:
    return all(_client_is_pinned(tools, runtime, name) for name in RUNTIME_CLIENTS)


def checks(ctx) -> list[tuple[str, Callable[[], bool]]]:
    tools, paths, accounts = ctx.tools, ctx.paths, ctx.accounts
    program = str(paths.release_bin / "docsuri-tunnel-route")
    agent = str(paths.release_bin / "docsuri-backup-agent")
    release = str(paths.release_bin / "docsuri-release")
    psql = str(paths.postgres_runtime / "bin" / "psql")
    return [
        ("in-person-command-needs-a-password", lambda: _refused(
            tools, [SUDO, "-u", ctx.operator, SUDO, "-n", "-k", program, "maintenance"])),
        ("scheduler-runs-no-in-person-command", lambda: _refused(
            tools, [SUDO, "-u", accounts.scheduler.name, SUDO, "-n", release, "install"])),
        ("scheduler-runs-no-service-control", lambda: _refused(
            tools, [SUDO, "-u", accounts.scheduler.name, SUDO, "-n",
                    str(paths.release_bin / "docsuri-service-stop"), "org.docsuri.v2.host"])),
        ("scheduler-runs-its-unattended-set", lambda: _allowed(
            tools, [SUDO, "-u", accounts.scheduler.name, SUDO, "-n", "-u",
                    accounts.backup.name, agent, "status"])),
        ("service-account-runs-nothing", lambda: _refused(
            tools, [SUDO, "-u", accounts.service.name, SUDO, "-n", agent, "status"])),
        ("login-cannot-read-operator-login", lambda: _refused(
            tools, [SUDO, "-u", ctx.operator, SECURITY, "find-generic-password", "-s",
                    "docsuri-v2-operator", "-w", SYSTEM_KEYCHAIN])),
        ("superuser-tcp-login-refused", lambda: _refused(
            tools, [psql, "-w", "-X", "-h", "127.0.0.1", "-p", "15432", "-U", render.SUPERUSER,
                    "-d", "postgres", "-c", "SELECT 1"])),
        ("runtime-clients-load-their-own-libpq", lambda: _runtime_clients_pinned(
            tools, paths.postgres_runtime)),
        ("time-machine-exclusions", lambda: timemachine.missing(tools) == []),
        ("isolation-check", lambda: _isolation_passes(ctx)),
    ]


def _isolation_passes(ctx) -> bool:
    from docsuri_ops.isolation_check import CheckContext, IsolationCheck

    check = IsolationCheck(CheckContext(paths=ctx.paths, accounts=ctx.accounts,
                                        tools=getattr(ctx, "isolation_tools", None),
                                        clock=ctx.clock, owner_uid=ctx.root_uid))
    result = check.run()
    check.write_result(result)
    return bool(result["passed"])


def run_checks(ctx) -> list[dict]:
    """Every check in order, each recorded in the installation log by its name and
    outcome only."""
    results = []
    for name, decide in checks(ctx):
        try:
            passed = bool(decide())
        except Exception:  # noqa: BLE001 - a check that cannot decide does not pass
            passed = False
        ctx.log.write("verify", name, "passed" if passed else "failed")
        results.append({"check": name, "passed": passed})
    return results
