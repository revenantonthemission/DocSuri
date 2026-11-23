"""Serve the composed realm (U8 plan Step 39): the three roles, the maintenance server, the
public stand-in and the identity stand-in, with Step 9's server settings.

    backend/.venv/bin/python scripts/serve_docsuri_u8.py \
        --environment-file /tmp/docsuri-u8-run/environment.json

- **host** runs in this process on `127.0.0.1:18109` (plain HTTP on loopback, D7's
  boundary, `SERVER_SETTINGS`), with the **identity stand-in** beside it on
  `https://localhost:18114`: the codes the stand-in issues live in the process that
  redeems them, so the host's Google and ORCID adapters are the real ones over the
  stand-in's recorded answers (`RecordedAnswers`), wired in before the routes are built;
- **workers** and **scheduler** run as `python -m backend.u8_main <role>`;
- the **maintenance server** serves the build's notice and legal pages on `18111`;
- the **public stand-in** plays Cloudflare and the tunnel on `https://127.0.0.1:18110`,
  routed to v2's host unless the realm's active configuration already names an origin.

Every part refuses the production profile. A termination signal stops the children,
then drains the host (event streams close with their retry hint).

`--observe-gates` (U8 plan Step 114(c)) writes the host's gate waits and holds to the run
root's `gate-waits.json` every 0.5 s for the `capacity-burst` phase; no other phase passes
the flag, and without it the program serves exactly as before.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT, ROOT / "ops/src", ROOT / "scripts"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

# The repository's own packages resolve only once the paths above are on sys.path.
from backend.local_profile import LocalProfile  # noqa: E402

REALM = "service-operations"
DATABASE = "docsuri_u8"
HOST_PORT = 18109
# The realm's registered identity clients' secrets, made once per realm by `setup`
# (U8 plan Step 96(d), L1-36), never a real one.
IDENTITY_CLIENTS = "identity-clients.json"
STANDIN_PROVIDERS = ("google", "orcid")


def require_realm(profile) -> None:
    if getattr(profile, "is_production", False) or (
        profile.realm, profile.database_name) != (REALM, DATABASE):
        raise ValueError("the composed realm's server serves its own realm only")


def standin_secrets(profile) -> dict[str, str]:
    """The stand-in clients' secrets from `<root>/identity-clients.json`, refusing a
    missing record or another run's."""
    from backend.local_profile import private_bytes

    require_realm(profile)
    path = profile.root / IDENTITY_CLIENTS
    if not path.exists():
        raise ValueError("the realm holds no identity client record; run setup first")
    value = json.loads(private_bytes(path))
    if value.get("runId") != profile.run_id or not all(
            isinstance(value.get(name), str) and value[name] for name in STANDIN_PROVIDERS):
        raise ValueError("the identity client record belongs to another run")
    return {name: value[name] for name in STANDIN_PROVIDERS}


def standin_providers(profile, answers) -> dict:
    """The real Google and ORCID adapters over the stand-in's recorded answers."""
    from backend.modules.accounts.integrations.identity_providers import (
        GoogleIdentityProvider,
        OrcidIdentityProvider,
    )
    from u8_identity_standin import CLIENTS

    secrets = standin_secrets(profile)
    return {
        name: kind(client_id=CLIENTS[name], client_secret=secrets[name],
                   origin=profile.origin, client_factory=answers.client_factory)
        for name, kind in (("google", GoogleIdentityProvider), ("orcid", OrcidIdentityProvider))
    }


@contextmanager
def standin_clients(profile):
    """The realm's private environment names the stand-in clients' secrets for as long as
    the realm is served, so readiness counts Google and ORCID configured (BR6.7) and
    their sign-in buttons serve; Resend stays unconfigured, so no mail leaves. Another
    file already present is left as it is. One holding exactly the stand-in values is
    this program's own, from an earlier serve that was stopped before its end, and is
    removed at this one's end (the start-check tests write their own while nothing is
    served)."""
    from backend.local_profile import private_bytes
    from backend.u8_host import PROVIDER_ENVIRONMENT, PROVIDER_SECRETS

    path = profile.root / PROVIDER_ENVIRONMENT
    values = {PROVIDER_SECRETS["provider." + name]: secret
              for name, secret in standin_secrets(profile).items()}
    if path.exists() or path.is_symlink():
        try:
            owned = json.loads(private_bytes(path)) == values
        except (OSError, ValueError):
            owned = False
    else:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            json.dump(values, stream)
        owned = True

    def release() -> None:
        # Called first as serving ends: stopping the children can outlast the runner's
        # grace, and the file must not outlive the serve.
        if owned:
            path.unlink(missing_ok=True)

    try:
        yield release
    finally:
        release()


def observe_host_gates(composition, path: Path | None = None):
    """The host's gates observed (U8 plan Step 114(c)): a `GateWaits` given to the
    composition's `CompleteTransactions`, written to `path` (the run root's
    `gate-waits.json` by default) every 0.5 s by the started `SnapshotWriter` answered."""
    from backend.u8_gate_waits import GATE_WAITS_FILE, GateWaits, SnapshotWriter

    observer = GateWaits()
    composition.transactions.observe_gates(observer)
    return SnapshotWriter(observer, path or composition.profile.root / GATE_WAITS_FILE).start()


def prepare_with(answers, *, observe: bool = False, observed: list | None = None):
    """The host's `prepare` hook: the stand-in's adapters in the account controls, and,
    with `observe`, the host's gates observed, the writer appended to `observed`."""

    def prepare(composition) -> None:
        controls = composition.parts.get("account-controls")
        if controls is not None:
            controls["entry"].identity_providers = standin_providers(composition.profile,
                                                                     answers)
        if observe:
            # `compose` runs once per process (`backend/u8_host.py:3-4`).
            if observed is None:
                raise ValueError("the observed writers need a list")
            if observed:
                raise ValueError("the host gates are observed once")
            observed.append(observe_host_gates(composition))

    return prepare


def arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="serve_docsuri_u8.py")
    parser.add_argument("--environment-file", required=True, type=Path)
    parser.add_argument("--identity-scenario", type=Path)
    # The `capacity-burst` phase's gate record (Step 114(c)); off by default.
    parser.add_argument("--observe-gates", action="store_true", default=False)
    return parser.parse_args(argv)


def children(environment: Path) -> list[list[str]]:
    python = sys.executable
    build = ROOT / "frontend/dist"
    return [
        [python, "-m", "backend.u8_main", "workers", "--profile", str(environment)],
        [python, "-m", "backend.u8_main", "scheduler", "--profile", str(environment)],
        [python, "-m", "backend.maintenance_server", "--build", str(build), "--port", "18111",
         "--public-authority", "127.0.0.1:18110",
         "--log-folder", str(environment.parent / "logs")],
        [python, str(ROOT / "scripts/u8_tunnel_standin.py"), "--environment-file",
         str(environment)],
    ]


def start_children(environment: Path) -> list[subprocess.Popen]:
    started = []
    for argv in children(environment):
        started.append(subprocess.Popen(argv, cwd=ROOT))
    return started


# The realm driver's service control of the two roles this program runs as children
# (`platform.service.control`): the wanted state in `platform/services/<label>.json`,
# acknowledged once the child has started or exited, as the synthetic v1's supervisor does.
SUPERVISED = {"dev.docsuri.u8.run.workers": 0, "dev.docsuri.u8.run.scheduler": 1}
STOP_SECONDS = 15


class ServiceWatcher:
    def __init__(self, profile, environment: Path, started: list[subprocess.Popen]):
        self.profile, self.environment, self.started = profile, environment, started
        self.services = profile.root / "platform" / "services"
        self.stopping = False
        self.done: dict[str, str] = {}

    def _write(self, path: Path, value: dict) -> None:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        pending = path.with_name(path.name + ".pending")
        descriptor = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW,
                             0o600)
        with os.fdopen(descriptor, "w") as stream:
            json.dump(value, stream)
        os.replace(pending, path)

    def register(self) -> None:
        for label in SUPERVISED:
            self._write(self.services / "supervisors" / f"{label}.json",
                        {"pid": os.getpid(), "runId": self.profile.run_id})

    def unregister(self) -> None:
        for label in SUPERVISED:
            (self.services / "supervisors" / f"{label}.json").unlink(missing_ok=True)

    def _act(self, label: str, wanted: str) -> bool:
        index = SUPERVISED[label]
        child = self.started[index]
        if wanted == "stopped":
            if child.poll() is None:
                child.send_signal(signal.SIGTERM)
                try:
                    child.wait(STOP_SECONDS)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(5)
            return child.poll() is not None
        if child.poll() is not None:
            self.started[index] = subprocess.Popen(children(self.environment)[index], cwd=ROOT)
        return self.started[index].poll() is None

    def turn(self) -> None:
        for label in SUPERVISED:
            path = self.services / f"{label}.json"
            if not path.exists():
                continue
            value = json.loads(path.read_text())
            if self.done.get(label) == value.get("operationId"):
                continue
            result = self._act(label, value["state"])
            observed = value["state"] if result else "unknown"
            self._write(self.services / f"{label}.ack.json", {
                "label": label, "operationId": value["operationId"], "observed": observed,
                "result": "succeeded" if result else "failed"})
            self.done[label] = value["operationId"]

    def run(self) -> None:
        # Operations acknowledged before this program started are not acted on again.
        for label in SUPERVISED:
            path = self.services / f"{label}.json"
            if path.exists():
                self.done[label] = json.loads(path.read_text()).get("operationId")
        while not self.stopping:
            self.turn()
            time.sleep(0.25)


def stop_children(started: list[subprocess.Popen]) -> None:
    for process in started:
        if process.poll() is None:
            process.send_signal(signal.SIGTERM)
    for process in started:
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()


def main(argv: list[str] | None = None) -> int:
    from backend.production_boundary import server_config
    from backend.u8_host import HostProcess, Startup, draining_server
    from backend.u8_main import REALM_MANIFEST, boundary_hosts
    from u8_identity_standin import IdentityStandin, RecordedAnswers, load_scenario
    from u8_tunnel_standin import active_origin, set_route

    args = arguments(argv)
    environment = args.environment_file.resolve()
    profile = LocalProfile.load(environment)
    require_realm(profile)
    if active_origin(profile) is None:
        set_route(profile, "v2-host")
    standin = IdentityStandin(profile)
    if args.identity_scenario is not None:
        load_scenario(standin, args.identity_scenario)
    answers = RecordedAnswers(standin)
    observed: list = []
    with standin_clients(profile) as release:
        started = start_children(environment)
        watcher = ServiceWatcher(profile, environment, started)
        watcher.register()
        watching = threading.Thread(target=watcher.run, daemon=True)
        watching.start()
        try:
            process = HostProcess(Startup(lambda: LocalProfile.load(environment), role="host"),
                                  hosts=boundary_hosts(REALM_MANIFEST),
                                  prepare=prepare_with(answers, observe=args.observe_gates,
                                                       observed=observed))
            with standin.running():
                draining_server(process, server_config(process, HOST_PORT)).run()
        finally:
            # The last snapshot, if the process gets this far (`runner.stop` kills the
            # group 3 s after its SIGTERM); no phase reads it.
            for writer in observed:
                writer.stop()
            release()
            watcher.stopping = True
            watching.join(5)
            watcher.unregister()
            stop_children(watcher.started)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
