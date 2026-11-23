"""The complete assembly's only entrypoint (BR1.7; U8 plan Step 11).

    python -m backend.u8_main <host|workers|scheduler> --profile <manifest>

It parses the role and the profile, configures the process's logs, composes and runs
the role. The composed realm's manifest is `/tmp/docsuri-u8-run/environment.json`;
any other manifest is read by the production loader as the service account's. A
process whose start is refused never exits: the host serves only its health routes,
naming the check, and the workers and the scheduler wait idle, doing no work (R2). A
start that fails unexpectedly (your decision of 2026-10-24) is logged by its error's
type and the role exits with status 1, the host after stopping its server, so launchd
relaunches it.

It never passes an arrangement to `compose`: every running role gets `ArrangementPaths()`
and the root-owned release rule (U8 plan Step 11).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import signal
from pathlib import Path

from .local_profile import RUN_PARENT, LocalProfile
from .u8_host import (
    HostProcess,
    Startup,
    compose,
    draining_server,
    run_scheduler,
    run_workers,
)
from .u8_profile import PRODUCTION_LISTEN_PORT, ProductionProfile

ROLES = ("host", "workers", "scheduler")
REALM_MANIFEST = (RUN_PARENT / "docsuri-u8-run" / "environment.json").resolve()
REALM_LISTEN_PORT = 18109


def is_realm(manifest: Path) -> bool:
    return Path(manifest).resolve() == REALM_MANIFEST


def loader(manifest: Path):
    """The profile loader the manifest's place selects."""
    if is_realm(manifest):
        return lambda: LocalProfile.load(Path(manifest))

    def production() -> ProductionProfile:
        from docsuri_ops.arrangement.paths import Accounts

        return ProductionProfile.load(Path(manifest), service_uid=Accounts.standard().service.uid)

    return production


def listen_port(manifest: Path) -> int:
    """The host's loopback port, known before the profile loads, so that a refused
    start still answers its health routes."""
    return REALM_LISTEN_PORT if is_realm(manifest) else PRODUCTION_LISTEN_PORT


def boundary_hosts(manifest: Path):
    """The host names the host accepts before its composition is served, known before
    the profile loads (Step 79(b)): the same set `host_app`'s
    `BoundaryHosts.for_profile(profile)` accepts once it serves."""
    from .local_profile import public_origin
    from .production_boundary import BoundaryHosts
    from .u8_profile import PRODUCTION_ORIGIN

    origin = public_origin("u8") if is_realm(manifest) else PRODUCTION_ORIGIN
    return BoundaryHosts(origin.split("://", 1)[1], f"127.0.0.1:{listen_port(manifest)}")


def configure_logs(manifest: Path, role: str) -> None:
    from . import log_events

    folder = Path(manifest).parent / "logs"
    if Path(manifest).parent.is_dir():
        log_events.configure(role, folder, production=not is_realm(manifest))


FAILED_EXIT = 1


def run_host(manifest: Path, *, options: dict | None = None) -> int:
    """The host role. A start that fails unexpectedly stops the server and the role
    exits with status 1; `options` reach `Startup` (tests only)."""
    from .production_boundary import server_config

    holder: dict = {}

    def failed(kind: str) -> None:
        server = holder.get("server")
        if server is not None:
            server.should_exit = True

    process = HostProcess(Startup(loader(manifest), role="host", on_failure=failed,
                                  **(options or {})), hosts=boundary_hosts(manifest))
    server = draining_server(process, server_config(process, listen_port(manifest)))
    holder["server"] = server
    server.run()
    return FAILED_EXIT if process.startup.state == "failed" else 0


async def run_background(manifest: Path, role: str, stopping: asyncio.Event | None = None,
                         *, options: dict | None = None) -> int:
    """The workers or the scheduler: compose with the start's retries, then run until a
    termination signal (or the given event); a refused start waits idle until then, and
    a start that fails unexpectedly returns status 1 at once. `options` reach `Startup`
    (tests only)."""
    if stopping is None:
        stopping = asyncio.Event()
        loop = asyncio.get_running_loop()
        for value in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(value, stopping.set)
    startup = Startup(loader(manifest), role=role, **(options or {}))
    composing = asyncio.create_task(asyncio.to_thread(startup.run))
    await asyncio.wait({composing, asyncio.create_task(stopping.wait())},
                       return_when=asyncio.FIRST_COMPLETED)
    if not composing.done():
        startup.stop()
        await composing
    if startup.state == "failed":
        return FAILED_EXIT
    composition = startup.composition
    if composition is None:
        await stopping.wait()
        return 0
    try:
        if role == "workers":
            await run_workers(composition, stopping)
        else:
            await run_scheduler(composition, stopping)
    finally:
        await asyncio.to_thread(composition.close)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m backend.u8_main")
    parser.add_argument("role", choices=ROLES)
    parser.add_argument("--profile", required=True, type=Path)
    args = parser.parse_args(argv)
    if not args.profile.is_absolute():
        parser.error("the profile manifest must be an absolute path")
    os.umask(0o077)
    configure_logs(args.profile, args.role)
    if args.role == "host":
        return run_host(args.profile)
    return asyncio.run(run_background(args.profile, args.role))


__all__ = ["compose", "main"]

if __name__ == "__main__":
    raise SystemExit(main())
