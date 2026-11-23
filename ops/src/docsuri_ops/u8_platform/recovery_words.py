"""The operator tool's recovery words (U8 plan Step 29; BR4.2, BR4.7, BR4.10, BR9.10).

`python -m docsuri_ops.u8_platform recovery <word>` (the operator tool's `recovery`
command, routed here from `operator_tool.main`), with bounded JSON on standard input and one
JSON result on standard output:

- `backup` `{recoveryRequestId}`: Workflow 5 for an admitted `backup.create`;
- `verify` `{recoveryRequestId}`: Workflow 6 for an admitted `restore.verify`;
- `restore` `{recoveryRequestId, continue?}`: Workflow 7 for an admitted
  `restore.production`, in person; `continue` resumes a request where it waits:
  `finish` (the last steps after `startAuthorizedAt`), `retry-post-restore`,
  `abandon` (after your abandonment decision) or `reconcile` (an unknown outcome);
- `retire-volume` `{approvalId, mount, identity}`: BR4.10's fixed order;
- `remove-scratch` `{copyId}`: a scratch database a failed check left behind, removed
  through `platform.database.remove` and its copy record closed on that receipt
  (U8 plan Step 72(c), L1-23).

Each word is a sequence of PlatformControl's bound operations
(`backend.modules.operations.recovery_procedures`), shown step by step against its
bound (`in_person.StepClock`), which never cuts a step off (R6). The composed realm's
wiring (`realm_procedures`) uses its own ledger, PlatformControl store and the realm
driver; `--production` (`production_word`, Step 37) the operator tool's logins released
in person (D5) and the ledger component's fixed command.
"""

from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import shutil
import sys
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from docsuri_ops.platform_control.errors import POLICY_UNRESOLVED, ControlError

WORDS = ("backup", "verify", "restore", "retire-volume", "remove-scratch")
CONTINUATIONS = ("finish", "retry-post-restore", "abandon", "reconcile")
V2_SUFFIXES = (".host", ".workers", ".scheduler")
MAX_INPUT = 64 * 1024
READY_SECONDS = 10


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


@dataclass
class Wiring:
    procedures: object
    close: Callable[[], None]


def _login(profile, file: str, role: str) -> str:
    from docsuri_ops.platform_control.profile import private_bytes

    value = json.loads(private_bytes(profile.run_root / file))
    if value.get("runId") != profile.run_id:
        raise ControlError(POLICY_UNRESOLVED, "realm credential identity mismatch")
    return value["roles"][role]


def _connector(profile, user: str, password: str):
    import psycopg

    def connect(database: str):
        return psycopg.connect(host="127.0.0.1", port=profile.port, dbname=database, user=user,
                               password=password, require_auth="scram-sha-256",
                               connect_timeout=5, autocommit=True)

    return connect


def _ready_probe(port: int) -> Callable[[], bool]:
    """The realm host's local readiness, within the probe limit."""

    def ready() -> bool:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health/ready",
                                        timeout=READY_SECONDS) as answer:
                return answer.status == 200
        except OSError:
            return False

    return ready


def realm_procedures(profile, ledger, *, clock: Callable[[], dt.datetime] = _now,
                     role: str = "operator", ready: Callable[[], bool] | None = None,
                     steps: Callable | None = None, mfa_current=None, names=None,
                     free_bytes: Callable[[], int] | None = None, policy=None) -> Wiring:
    """The procedures over the composed realm: its operator (or standing scheduler),
    its driver, and the stand-in logins its tool provisioned (the scheduler's for a
    scratch copy, the restore login for production)."""
    from backend.modules.operations import restore_checks
    from backend.modules.operations.incidents import Incidents
    from backend.modules.operations.recovery import RecoveryRequests
    from backend.modules.operations.recovery_procedures import Platform, RecoveryProcedures
    from backend.modules.operations.tombstones import Tombstones
    from backend.u8_policy import SYNTHETIC_OPERATIONS

    from docsuri_ops.arrangement.paths import DatabaseNames

    from .drivers import load_config
    from .drivers.realm import RealmDriver
    from .u8_protocols import realm_facts, realm_operator

    names = names or DatabaseNames("docsuri_u8")
    policy = policy or SYNTHETIC_OPERATIONS
    facts = realm_facts(profile, ledger, clock=clock)
    if names.prefix != "docsuri_u8":
        base = facts

        def facts():
            current = base()
            current.names = names
            return current

    operator = realm_operator(profile, role, ledger, clock=clock, facts=facts)
    driver = RealmDriver(load_config(profile.effects_root),
                         caller="scheduler" if role == "scheduler" else "operator")
    scheduler = _connector(profile, "docsuri_scheduler",
                           _login(profile, "standin-credentials.json", "scheduler"))
    restorer = _connector(profile, "docsuri_restore",
                          _login(profile, "standin-credentials.json", "restore"))

    def scratch_checks(database: str, accounts: list[str]) -> dict:
        with scheduler(database) as conn:
            checked = restore_checks.integrity(conn)
            replayed = restore_checks.replay(conn, accounts)
            return {**checked, **replayed, "surviving": restore_checks.surviving(conn, accounts)}

    def restore_evaluate(database: str, accounts: list[str]) -> dict:
        with restorer(database) as conn:
            replayed = restore_checks.replay(conn, accounts)
            return {**replayed, "surviving": restore_checks.surviving(conn, accounts)}

    def production_integrity(database: str) -> dict:
        with restorer(database) as conn:
            return restore_checks.integrity(conn)

    def drop_scratch(database: str) -> None:
        from psycopg import sql

        if names.kind_of(database) != "scratch":
            raise ValueError("only a scratch database is dropped here")
        with scheduler("postgres") as conn:
            conn.execute("SET statement_timeout = '600s'")
            conn.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(database)))

    def ledger_copy() -> dict:
        stream = io.BytesIO()
        head = ledger.copy(stream)
        return {"agent": driver.ledger_copy(stream.getvalue()), "head": head}

    def rehearsal() -> str | None:
        return facts().current_rehearsal

    def show(line: str) -> None:
        sys.stderr.write(line + "\n")

    if steps is None:
        from .in_person import StepClock

        clock_steps = StepClock(show)

        def steps(name, bound, work):
            return clock_steps.run(name, bound, work)[0]

    labels = tuple(label for label in profile.labels if label.endswith(V2_SUFFIXES))
    platform = Platform(
        operator=operator, production=names.production, labels=labels,
        scratch_name=lambda: names.new("scratch"),
        free_bytes=free_bytes or (lambda: shutil.disk_usage(profile.run_root).free),
        scratch_checks=scratch_checks, restore_evaluate=restore_evaluate,
        production_integrity=production_integrity, drop_scratch=drop_scratch,
        ready=ready or _ready_probe(18109), rehearsal=rehearsal, ledger_copy=ledger_copy,
        agent=driver.agent_word, steps=steps,
        # Live when the profile's mode is live, else rehearsal (U8 plan Step 64(h)).
        current_environment=lambda: "live" if facts().mode == "live" else "rehearsal",
    )
    requests = RecoveryRequests(ledger, policy, clock=clock, mfa_current=mfa_current)
    procedures = RecoveryProcedures(requests, platform, incidents=Incidents(ledger,
                                                                            environment="live"),
                                    tombstones=Tombstones(ledger), policy=policy, clock=clock)
    return Wiring(procedures, close=lambda: None)


def run_word(word: str, document: dict, procedures) -> dict:
    """One recovery word over the given procedures."""
    if word not in WORDS:
        raise ControlError("INVALID_INPUT", "recovery word outside its closed set")
    if word == "retire-volume":
        if set(document) != {"approvalId", "mount", "identity"}:
            raise ControlError("INVALID_INPUT", "retire-volume takes approvalId, mount, identity")
        return procedures.retire_volume(document["approvalId"], mount=str(document["mount"]),
                                        identity=str(document["identity"]))
    if word == "remove-scratch":
        if set(document) != {"copyId"}:
            raise ControlError("INVALID_INPUT", "remove-scratch takes exactly copyId")
        return procedures.remove_scratch(str(document["copyId"]))
    allowed = {"recoveryRequestId", "continue"} if word == "restore" else {"recoveryRequestId"}
    if not set(document) <= allowed or "recoveryRequestId" not in document:
        raise ControlError("INVALID_INPUT", "a recovery word takes its request")
    request = str(document["recoveryRequestId"])
    if word == "backup":
        return procedures.backup(request, via="in-person")
    if word == "verify":
        return procedures.verify(request, via="in-person")
    resume = document.get("continue")
    if resume is None:
        return procedures.restore(request)
    if resume not in CONTINUATIONS:
        raise ControlError("INVALID_INPUT", "restore continuation outside its closed set")
    return {
        "finish": procedures.finish_restore, "retry-post-restore": procedures.retry_post_restore,
        "abandon": procedures.abandon, "reconcile": procedures.reconcile,
    }[resume](request)


class _Unrecorded:
    """The procedures of a realm whose ledger has never been opened: the host creates the
    `ledger/` folder at its first start, so before then the realm holds no recovery
    request and no approval, and every word naming one answers `NOT_FOUND`. The word's
    input is still checked first, and nothing is created: a word only reads."""

    def __getattr__(self, name: str):
        from backend.modules.operations.errors import OperationsError

        def unrecorded(*args, **kwargs):
            raise OperationsError("NOT_FOUND")

        return unrecorded


def production_word(word: str, document: dict) -> dict:
    """One recovery word on this Mac, in person (Step 37's wiring): the ledger through
    `docsuri-ledger` (`sudo -k`) and the operator with its logins released in person,
    each step shown against its bound."""
    from docsuri_ops.production_wiring import (
        LedgerClient,
        WiringRefused,
        production_operator,
        production_procedures,
    )

    from .in_person import StepClock

    clock_steps = StepClock(lambda line: sys.stderr.write(line + "\n"))
    ledger = LedgerClient(via="in-person", clock=_now)
    try:
        operator = production_operator(ledger, clock=_now)
        wiring = production_procedures(
            ledger, operator, role="operator", clock=_now,
            steps=lambda name, bound, work: clock_steps.run(name, bound, work)[0])
        return run_word(word, document, wiring.procedures)
    except WiringRefused as refused:
        raise ControlError(POLICY_UNRESOLVED, str(refused)) from None
    finally:
        ledger.close()


def main(argv: list[str]) -> int:
    from backend.modules.operations.errors import OperationsError

    parser = argparse.ArgumentParser(prog="docsuri-ops recovery")
    parser.add_argument("word", choices=WORDS)
    parser.add_argument("--environment-file", type=Path)
    parser.add_argument("--production", action="store_true")
    args = parser.parse_args(argv)
    raw = sys.stdin.buffer.read(MAX_INPUT + 1)
    try:
        if len(raw) > MAX_INPUT:
            raise ControlError("INVALID_INPUT", "input exceeds its bound")
        document = json.loads(raw or b"{}")
        if not isinstance(document, dict):
            raise ControlError("INVALID_INPUT", "input must be one object")
        if args.production == (args.environment_file is not None):
            raise ControlError(POLICY_UNRESOLVED,
                               "name either --production or the realm's environment file")
        if args.production:
            result = production_word(args.word, document)
        else:
            from backend.modules.operations.ledger import Ledger

            from .platform_profile import U8PlatformProfile

            profile = U8PlatformProfile.realm(args.environment_file.parent)
            folder = profile.run_root / "ledger"
            if not folder.exists() and not folder.is_symlink():
                # Answered before any wiring: a realm never served has nothing to act on
                # (`_Unrecorded` raises for every request and approval).
                result = run_word(args.word, document, _Unrecorded())
            else:
                ledger = Ledger.open(folder, clock=_now)
                try:
                    wiring = realm_procedures(profile, ledger)
                    try:
                        result = run_word(args.word, document, wiring.procedures)
                    finally:
                        wiring.close()
                finally:
                    ledger.close()
    except ControlError as error:
        sys.stdout.write(json.dumps({"ok": False, "error": error.as_wire_error()}))
        return 1
    except OperationsError as error:
        sys.stdout.write(json.dumps({"ok": False, "code": error.code, "current": error.current}))
        return 1
    sys.stdout.write(json.dumps({"ok": True, "result": result}, sort_keys=True))
    return 0
