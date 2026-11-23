"""The cutover stage: the companion the `browser-migration` and `browser-cutover` phases
serve instead of the served realm (U8 plan Step 43).

    backend/.venv/bin/python -m tests.u8_service_operations_integration.cutover_stage \
        --environment-file /tmp/docsuri-u8-run/environment.json

An abort or a rollback empties the production database, and the composed realm treats
`docsuri_u8` as production, so the browser's migration and cutover journeys never run
against it: each journey here is `integration/test_cutover_journeys.py`'s `Journey`, with
its own production stand-in database (`docsuri_u8j<hex>`), ledger, platform state, tunnel
routing and backup volume, against the running synthetic v1. The public stand-in on
`https://127.0.0.1:18110` routes between v2's host on 18109, the maintenance server on
18111 and v1's web, as the realm driver's tunnel routing says, so the browser sees what a
person would see at the public address.

The stage takes your words (the test harness acting as you: `browser_harness stage`) one
at a time over a private socket in the run root (`cutover-stage.sock`, 0600), each a JSON
line answered by one JSON line `{"ok": …, "result"|"reason": …}`:

- `ready`; `begin` (a new journey; the previous one ends first) and `end`;
- `dry-run` (a dry run with its idempotency pass), `start` (to the final report),
  `report` (a run's state and its parity report's counts, each misfit pair with its count,
  which hold no secret or content),
  `accept-final` (to the maintainer-only window), `open` (admission opening);
- `abort`, `rollback` (`{"v1Fails": true}` makes v1's restart fail, so the rollback waits),
  `cancel-rollback`; `served-by` (who answers the public address);
- `abort` with `{"hold": true}` holds the abort at the moment its database recreate is
  about to run and answers with who serves the public address and how many tables v2's
  database holds then; `release-abort` lets the recreate run and answers as `abort` does
  (U8 plan Step 168(e), L4-14). The observing wrapper forwards every call unchanged;
- `v2-lifecycle` (`{"name": …, "action": "erase" | "withdraw"}`) asks v2's own account
  services, while v2 serves, as `test_cutover_journeys.lifecycle_in_v2` does. The
  rollback's answer then carries v1's deletion records for those accounts, and the
  journey's end puts them back through v1's own reactivation.

It refuses the production profile and every environment but the composed realm's.
"""

from __future__ import annotations

import argparse
import collections
import contextlib
import datetime as dt
import json
import os
import signal
import socket
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOCKET_NAME = "cutover-stage.sock"
MAX_REQUEST = 64 * 1024
REALM, DATABASE = "service-operations", "docsuri_u8"


RECREATE = "platform.database.recreate"
# How long a held abort waits for its release before it goes on by itself, and how long
# a release waits for the abort to end.
HOLD_SECONDS = 120.0
# How long the `abort` word waits for a held abort to reach its recreate.
REACH_SECONDS = 120.0


class StageRefused(RuntimeError):
    pass


class HeldOperator:
    """The operator, observed (L4-14): every call is forwarded unchanged. Before the first
    database recreate is forwarded it notes what `observe` reads, says it has been
    reached, and waits for its release (or `HOLD_SECONDS`)."""

    def __init__(self, operator, observe):
        self.operator, self.observe = operator, observe
        self.reached, self.release = threading.Event(), threading.Event()
        self.at_recreate: dict | None = None
        # Why the observer could not read, when it could not; and whether the wait ended
        # by its release (True) or by its own bound (False).
        self.observer_error: str | None = None
        self.released: bool | None = None

    def __getattr__(self, name):
        return getattr(self.operator, name)

    def _hold(self) -> None:
        """Observe, say the recreate is reached, and wait. Whatever the observer does, the
        caller forwards the call afterwards."""
        try:
            self.at_recreate = self.observe()
        except Exception as error:  # noqa: BLE001 - shown by the stage, never swallowed
            self.at_recreate = {}
            self.observer_error = f"{type(error).__name__}: {error}"[:300]
        self.reached.set()
        self.released = self.release.wait(HOLD_SECONDS)

    def execute(self, operation, target, inputs, *, key, injected_fault=None, **options):
        if operation == RECREATE and self.at_recreate is None:
            self._hold()
        return self.operator.execute(operation, target, inputs, key=key,
                                     injected_fault=injected_fault, **options)


def _paths() -> None:
    for entry in (ROOT, ROOT / "backend", ROOT / "ingestion/src", ROOT / "ops/src",
                  ROOT / "scripts"):
        if str(entry) not in sys.path:
            sys.path.insert(0, str(entry))


class Stage:
    """One journey at a time over the realm, as the cutover journeys hold it."""

    def __init__(self, realm, folder: Path):
        from backend.local_profile import private_bytes
        from tests.u8_service_operations_integration.integration import (
            test_cutover_journeys as journeys,
        )

        self.realm, self.folder, self.journeys = realm, folder, journeys
        run = Path(realm.root)
        self.v1 = journeys.SyntheticV1(
            run, json.loads(private_bytes(run / "v1" / "dataset.json")),
            json.loads(private_bytes(run / "v1" / "credentials.json")))
        self.journey = None
        self.stack: contextlib.ExitStack | None = None
        self.count = 0
        self.real_v1_ready = None
        # A held abort (its wrapper, thread, outcome and the operator it wraps), and the
        # v1 names whose accounts a `v2-lifecycle` word changed in this journey.
        self.held: tuple | None = None
        self.lifecycled: list[str] = []

    # -- one journey ----------------------------------------------------------------------

    def begin(self, document: dict) -> dict:
        from tests.u8_service_operations_integration.conftest import Clock

        self.end({})
        if not self.v1.ready():
            raise StageRefused("the synthetic v1 is not serving; the phase runs v1-up first")
        self.count += 1
        # Unique across stage runs: an earlier phase's journey folders stay as evidence.
        folder = self.folder / f"journey-{os.getpid()}-{self.count}"
        folder.mkdir(mode=0o700, parents=True)
        # The journeys' one clock, 8 days before now (`test_cutover_journeys.clock`).
        clock = Clock(dt.datetime.now(dt.UTC) - dt.timedelta(days=8))
        journey = self.journeys.Journey(folder, self.realm, clock, self.v1)
        decided = {"done": False}
        decide_misfits = journey.decide_misfits

        def once() -> None:  # a dry run and the switch's readiness both decide; once is all
            if not decided["done"]:
                decide_misfits()
                decided["done"] = True

        journey.decide_misfits = once
        # Before any cutover the public address is v1's, as production's is today: the
        # journey's own routing starts at v1's web (the cutover's steps move it from here).
        self._route_v1(journey)
        stack = contextlib.ExitStack()
        try:
            stack.enter_context(journey.supervisor)
            stack.enter_context(journey.tunnel.running())
            stack.enter_context(self.journeys.maintenance_served(ROOT / "frontend" / "dist"))
        except BaseException:
            stack.close()
            journey.close()
            raise
        self.journey, self.stack = journey, stack
        self.real_v1_ready = journey.platform.v1_ready
        return {"journey": self.count, "production": journey.production,
                "servedBy": journey.served_by()}

    def _route_v1(self, journey) -> None:
        from u8_tunnel_standin import ACTIVE_FILE

        path = Path(journey.journey.root) / ACTIVE_FILE
        if path.exists():
            return
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            json.dump({"runId": self.realm.run_id, "origin": "v1-web"}, stream)

    def end(self, document: dict) -> dict:
        if self.journey is None:
            return {"ended": False}
        journey, stack = self.journey, self.stack
        failure: Exception | None = None
        try:
            if self.held is not None:
                self.release_abort({})
        except Exception as error:  # noqa: BLE001 - raised again once the journey is closed
            failure = error
        # v1's accounts are put back, and the journey closed, whatever the release did.
        try:
            self._restore_v1(journey)
        finally:
            self.journey = self.stack = None
            try:
                stack.close()
            finally:
                journey.close()
                self.journeys.v1_serving(Path(self.realm.root))
        if failure is not None:
            raise failure
        return {"ended": True}

    def _current(self):
        if self.journey is None:
            raise StageRefused("no journey; begin first")
        return self.journey

    # -- the migration --------------------------------------------------------------------

    def dry_run(self, document: dict) -> dict:
        from tests.u8_service_operations_integration import recovery_flows as rf

        journey = self._current()
        journey.decide_misfits()
        receipt = journey.operator.execute(
            "platform.isolation.check", "isolation", {"via": "in-person"},
            key=f"stage-isolation-{self.count}-{os.urandom(4).hex()}")
        if receipt["outcome"] != "succeeded":
            raise StageRefused(f"isolation check {receipt['outcome']}")
        go = rf.decide(journey.operator, journey.ledger, journey.clock, "dry-run-go-ahead",
                       "synthetic-v1")
        run = journey.migration.start_dry(go)
        # A failing step's place in the code, for the refusal below (the run itself keeps
        # only the error's type).
        import traceback

        failed_at: list[str] = []
        fail = journey.migration.fail

        def noting(run_id, reason):
            failed_at.extend(line.strip() for line in
                             traceback.format_exc().strip().splitlines()[-3:])
            return fail(run_id, reason)

        journey.migration.fail = noting
        try:
            reported = journey.migration.run(run["runId"])
        finally:
            journey.migration.fail = fail
        if reported["state"] != "reported":
            # Its reason keys only, never content.
            reasons = {key: reported.get(key) for key in ("reason", "reasonKey", "phase")
                       if reported.get(key) is not None}
            reasons["at"] = failed_at
            raise StageRefused(f"the dry run ended {reported['state']}: {json.dumps(reasons)}")
        answer = self.report({"runId": run["runId"]})
        approval = rf.decide(journey.operator, journey.ledger, journey.clock,
                             "dry-run-report", run["runId"])
        answer["decided"] = journey.migration.decide(run["runId"], approval)["state"]
        return answer

    def report(self, document: dict) -> dict:
        """A run's state and its parity report's per-kind counts (BR8.10): no secret, no
        address, no content, as the report itself holds none."""
        journey = self._current()
        run_id = document.get("runId") or journey.tool.machine.current().get("finalRunId")
        if not run_id:
            raise StageRefused("no run to report")
        run = journey.migration.runs.require(run_id)
        record = journey.ledger.get("parity-report", run_id)
        kinds, misfits = [], []
        if record is not None:
            path = journey.migration.platform.evidence / Path(record["reportRef"]).name
            report = json.loads(path.read_text())
            kinds = [{key: kind.get(key) for key in ("kind", "imported", "updated",
                                                       "unchanged", "excluded", "reconciles")}
                     for kind in report["kinds"]]
            # Each misfit pair (kind, reason) with its count (U8 plan Step 96(e)), sorted by
            # kind and reason, never a source record.
            counts = collections.Counter((item["kind"], item["reasonKey"])
                                         for entry in report["kinds"]
                                         for item in entry["misfits"])
            misfits = [{"kind": kind, "reasonKey": reason, "count": count}
                       for (kind, reason), count in sorted(counts.items())]
        return {"runId": str(run_id), "kind": run["kind"], "state": run["state"],
                "reconciles": record["reconciles"] if record else None, "kinds": kinds,
                "misfits": misfits}

    # -- the cutover ----------------------------------------------------------------------

    def start(self, document: dict) -> dict:
        journey = self._current()
        first = journey.start()
        return {"result": first, "state": journey.tool.machine.current()["state"],
                "servedBy": journey.served_by()}

    def accept_final(self, document: dict) -> dict:
        journey = self._current()
        journey.accept_final()
        second = journey.tool.start()
        return {"result": second, "servedBy": journey.served_by(),
                "profile": journey.journey.read_state("profile.json")}

    def open(self, document: dict) -> dict:
        journey = self._current()
        opened = journey.open_admission()
        return {"result": opened, "servedBy": journey.served_by(),
                "profile": journey.journey.read_state("profile.json")}

    def abort(self, document: dict) -> dict:
        journey = self._current()
        if document.get("hold"):
            return self._hold_abort(journey)
        result = self.journeys.run_word(journey.tool, "abort", {"reason": "operator-abort"})
        return {"result": result, "servedBy": journey.served_by(),
                "productionTables": journey.production_tables()}

    def _hold_abort(self, journey) -> dict:
        """The abort started on a thread of its own and held at its recreate: what the
        stage read at that moment, before the recreate was forwarded."""
        if self.held is not None:
            raise StageRefused("an abort is already held")
        original = journey.platform.operator
        held = HeldOperator(original, lambda: {
            "servedBy": journey.served_by(),
            "productionTables": journey.production_tables()})
        outcome: dict = {}

        def run() -> None:
            try:
                outcome["result"] = self.journeys.run_word(
                    journey.tool, "abort", {"reason": "operator-abort"})
            except Exception as error:  # noqa: BLE001 - reported by `release-abort`
                outcome["error"] = f"{type(error).__name__}: {error}"[:300]

        journey.platform.operator = held
        thread = threading.Thread(target=run, name="held-abort", daemon=True)
        thread.start()
        deadline = time.monotonic() + REACH_SECONDS
        while thread.is_alive() and time.monotonic() < deadline and not held.reached.wait(0.2):
            pass
        if not held.reached.is_set():
            # Never left waiting: an abort still running goes on through its recreate.
            held.release.set()
            if thread.is_alive():
                raise StageRefused(
                    f"abort-not-at-recreate: no recreate within {REACH_SECONDS:.0f} s")
            journey.platform.operator = original
            raise StageRefused(f"the abort ended before its recreate: {json.dumps(outcome)}")
        self.held = (held, thread, outcome, original)
        if held.observer_error is not None:
            raise StageRefused(f"the held abort's observer failed: {held.observer_error}")
        return {"held": True, **(held.at_recreate or {})}

    def release_abort(self, document: dict) -> dict:
        journey = self._current()
        if self.held is None:
            raise StageRefused("no abort is held")
        held, thread, outcome, original = self.held
        self.held = None
        held.release.set()
        thread.join(HOLD_SECONDS)
        journey.platform.operator = original
        if thread.is_alive():
            raise StageRefused("the released abort did not end")
        if "error" in outcome:
            raise StageRefused(f"the released abort failed: {outcome['error']}")
        # `heldUntilRelease`: the wait ended by this release, not by its own bound.
        return {"result": outcome["result"], "servedBy": journey.served_by(),
                "productionTables": journey.production_tables(),
                "atRecreate": held.at_recreate, "heldUntilRelease": held.released is True}

    def v2_lifecycle(self, document: dict) -> dict:
        """An erasure or a withdrawal asked of v2's own account services while v2 serves."""
        journey = self._current()
        name, action = document.get("name"), document.get("action")
        if name not in journey.v1.dataset["accounts"] or action not in ("erase", "withdraw"):
            raise StageRefused("a v2 lifecycle word names a v1 account and erase or withdraw")
        self.lifecycled.append(name)
        self.journeys.lifecycle_in_v2(journey, name, action)
        return {"name": name, "action": action, "servedBy": journey.served_by()}

    def _restore_v1(self, journey) -> None:
        """v1's accounts back as they were, through v1's own reactivation, as the Python
        journey's last lines do."""
        names, self.lifecycled = self.lifecycled, []
        if not names:
            return
        journey.driver.effect("v1-lifecycle-apply", {
            "outcomes": [{"v1AccountId": journey.v1.account(name), "outcome": "reactivate"}
                         for name in names], "accounts": []}, context={})

    def rollback(self, document: dict) -> dict:
        journey = self._current()
        failing = bool(document.get("v1Fails"))
        journey.platform.v1_ready = (lambda: False) if failing else self.real_v1_ready
        real_sleep = journey.platform.sleep
        if failing:
            # The never-ready v1's wait moves the journey's clock and sleeps no real time
            # (U8 plan Step 71(k)), so J11's cancelled rollback waits no 600 s.
            journey.platform.sleep = journey.clock.advance
        try:
            subject = journey.rollback_subject()
            result = journey.tool.rollback(journey.decide("rollback", subject), subject)
        finally:
            journey.platform.sleep = real_sleep
        # v1's own record of the accounts v2 changed: its state and whether it holds a
        # deletion record (read from v1's database, as the Python journey reads them).
        accounts = {name: journey.v1.account(name) for name in self.lifecycled}
        states = journey.v1.states(list(accounts.values())) if accounts else {}
        return {"result": result, "servedBy": journey.served_by(),
                "productionTables": journey.production_tables(),
                "v1Deletions": {name: journey.v1.deletion_due(account)
                                for name, account in accounts.items()},
                "v1States": {name: states.get(account) for name, account in accounts.items()}}

    def cancel_rollback(self, document: dict) -> dict:
        journey = self._current()
        result = self.journeys.run_word(journey.tool, "cancel-rollback",
                                        {"approvalId": journey.decide("rollback-cancel")})
        journey.platform.v1_ready = self.real_v1_ready
        return {"result": result, "servedBy": journey.served_by()}

    def served_by(self, document: dict) -> dict:
        return {"servedBy": self._current().served_by()}

    def words(self) -> dict:
        return {"ready": lambda document: {"ready": True}, "begin": self.begin,
                "end": self.end, "dry-run": self.dry_run, "report": self.report,
                "start": self.start, "accept-final": self.accept_final, "open": self.open,
                "abort": self.abort, "release-abort": self.release_abort,
                "v2-lifecycle": self.v2_lifecycle, "rollback": self.rollback,
                "cancel-rollback": self.cancel_rollback, "served-by": self.served_by}


def answer(stage: Stage, raw: bytes) -> dict:
    try:
        if len(raw) > MAX_REQUEST:
            raise StageRefused("request exceeds its bound")
        document = json.loads(raw or b"{}")
        if not isinstance(document, dict):
            raise StageRefused("a request is one object")
        word = document.pop("word", None)
        handler = stage.words().get(word)
        if handler is None:
            raise StageRefused("word outside the stage's closed set")
        return {"ok": True, "result": handler(document)}
    except Exception as error:  # noqa: BLE001 - one JSON answer for every refusal
        return {"ok": False, "reason": f"{type(error).__name__}: {error}"[:600]}


def serve(stage: Stage, path: Path, stopping: threading.Event) -> None:
    path.unlink(missing_ok=True)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        previous = os.umask(0o177)
        try:
            server.bind(str(path))
        finally:
            os.umask(previous)
        os.chmod(path, 0o600)
        server.listen(1)
        server.settimeout(0.5)
        while not stopping.is_set():
            try:
                connection, _ = server.accept()
            except TimeoutError:
                continue
            with connection:
                connection.settimeout(30)
                raw = b""
                while not raw.endswith(b"\n") and len(raw) <= MAX_REQUEST:
                    chunk = connection.recv(65536)
                    if not chunk:
                        break
                    raw += chunk
                connection.sendall(json.dumps(answer(stage, raw.strip()),
                                              default=str).encode() + b"\n")
    path.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    _paths()
    from backend.local_profile import LocalProfile

    parser = argparse.ArgumentParser(prog="cutover_stage")
    parser.add_argument("--environment-file", required=True, type=Path)
    args = parser.parse_args(argv)
    realm = LocalProfile.load(args.environment_file.resolve())
    if getattr(realm, "is_production", False) or (realm.realm, realm.database_name) != (
            REALM, DATABASE):
        print(json.dumps({"state": "refused", "reason": "the stage serves the composed realm"}))
        return 1
    root = Path(realm.root)
    os.environ.setdefault("DOCSURI_U8_ENVIRONMENT_FILE", str(args.environment_file.resolve()))
    stage = Stage(realm, root / "cutover-stage")
    stopping = threading.Event()
    for value in (signal.SIGTERM, signal.SIGINT):
        signal.signal(value, lambda signum, frame: stopping.set())
    try:
        serve(stage, root / SOCKET_NAME, stopping)
    finally:
        stage.end({})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
