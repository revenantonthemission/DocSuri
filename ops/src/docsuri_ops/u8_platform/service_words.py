"""The operator tool's in-person service control (the person's decision of 2026-10-25,
"Add an in-person stop command"; Workflow 20 step 9, BR6.12, NFR7.19).

`python -I -m docsuri_ops.u8_platform service <stop|start> <label> --production` on this
Mac (or `--environment-file /tmp/docsuri-u8-run/environment.json` in the composed realm),
with `{}` on standard input and one JSON result on standard output:

- run in person only: production's operator (your login account, its PlatformControl
  login released in person, D5; each effect through `sudo -k`), or the realm's synthetic
  operator; never the standing authority;
- only v2's three labels (`.host`, `.workers`, `.scheduler`); any other label is refused
  before anything is bound;
- each run is one `platform.service.control` through `Operator.execute` under a key of
  its own, so PlatformControl binds the receipt before the fixed program writes or
  removes the stop record, and the record cites that receipt;
- `service stop` on a job already stopped renews its stop record under the new receipt
  with a new 14 days: while a rollback keeps v2 stopped, that is how its stop records
  are renewed before they lapse (`cutover status` shows their expiry, and whether the
  isolation check counts each as planned);
- refused while an install or a release rollback holds the live exclusion (the ledger's
  release record), and while a release command runs: its run marker
  (`release.release_run_active`, a root-written file read without a password and without
  locking anything; the lock itself is root-only), checked right before the control is
  bound and again once it is bound (your decision of 2026-10-26, "Check the release run
  lock"): in production the ledger is a copy taken before the first check, so the marker,
  not a re-read of that copy, is what sees a release command that began meanwhile; a
  marker left by a command that died refuses too (`release-run-marker-stale`) until the
  next release command; an earlier run's unresolved service control of the label is
  reconciled before a new one is bound;
- `input-not-json` answers only a JSON error; every other failure has its own reason.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import uuid
from collections.abc import Callable
from pathlib import Path

from docsuri_ops.platform_control.errors import (
    FORBIDDEN,
    INVALID_INPUT,
    POLICY_UNRESOLVED,
    ControlError,
)

WORDS = ("stop", "start")
V2_SUFFIXES = (".host", ".workers", ".scheduler")
MAX_INPUT = 1024
OPERATION = "platform.service.control"


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def v2_labels(labels) -> tuple[str, ...]:
    """v2's three roles among a profile's labels."""
    return tuple(label for label in labels if label.endswith(V2_SUFFIXES))


def service_key(action: str, label: str) -> str:
    """Each run's own key: a renewal binds a new receipt instead of replaying the last."""
    return f"service:{action}:{label}:{uuid.uuid4().hex}"


def release_exclusion(ledger) -> str | None:
    """The install or release rollback holding the live exclusion, read from the ledger
    (`release_records.release_blocker`), or None. A ledger that cannot be read refuses
    (fail closed)."""
    from backend.modules.operations.release_records import release_blocker

    if ledger is None:
        return None
    return release_blocker(ledger)


def release_held(ledger, run_lock: Callable[[], str | None] | None) -> str | None:
    """Why a service control may not act now: an install or a release rollback holding
    the live exclusion in the ledger, else a release command running, read from its run
    marker (`run_lock`, `release.release_run_active` in production), else None."""
    blocker = release_exclusion(ledger)
    if blocker is None and run_lock is not None:
        blocker = run_lock()
    return blocker


def run_service(action: str, label: str, operator, *, key: str | None = None,
                ledger=None, run_lock: Callable[[], str | None] | None = None) -> dict:
    """One in-person stop or start of one of v2's three roles, through
    `platform.service.control`, run to a settled outcome.

    Refused while an install or a release rollback holds the live exclusion (`ledger`
    given; the review's fix of 2026-10-26) or a release command runs, read from its run
    marker (`run_lock` given; your decision of 2026-10-26, "Check the release run
    lock"), before anything is bound, and both are read again once the receipt is bound,
    right before the effect runs. The marker is what sees a release command that began
    between the first check and the binding: the ledger may be a copy taken before the
    first check (production's `LedgerClient`), so a re-read of it protects nothing.
    Before its own receipt is bound, any earlier service control of the label that was
    left unresolved (a run interrupted after binding) is reconciled from its target
    (`u8_protocols.reconcile_unresolved`), so a fresh key never leaves one behind."""
    from .u8_protocols import (
        EffectUnsettled,
        PreconditionRefused,
        execute_settled,
        reconcile_unresolved,
        refusal_error,
    )

    if action not in WORDS:
        raise ControlError(INVALID_INPUT, "service word outside its closed set")
    if getattr(operator, "standing", False):
        raise ControlError(FORBIDDEN, "service control runs only in person")
    if label not in v2_labels(operator.profile.labels):
        raise ControlError(INVALID_INPUT, "only v2's three labels",
                           details={"messageKey": "label-refused"})
    blocker = release_held(ledger, run_lock)
    if blocker is not None:
        raise ControlError("CONFLICT", "a release command holds the live exclusion",
                           details={"messageKey": blocker})
    reconcile_unresolved(operator, label)
    try:
        # Checked again once the receipt is bound, right before the effect runs: the run
        # lock sees a release command that began after the first check.
        receipt = execute_settled(operator, OPERATION, label,
                                  {"label": label, "action": action},
                                  key=key or service_key(action, label),
                                  recheck=None if ledger is None and run_lock is None
                                  else (lambda: release_held(ledger, run_lock)))
    except PreconditionRefused as refused:
        raise refusal_error(refused) from None
    except EffectUnsettled as unsettled:
        reason = unsettled.reason or f"service-{action}-failed"
        raise ControlError("CONFLICT", reason, details={"messageKey": reason}) from None
    return {"label": label, "action": action, "operationId": str(receipt["operationId"]),
            "receiptId": str(receipt["receiptId"]), "outcome": receipt["outcome"]}


def stop_expiries(folder: Path, labels, *, now: dt.datetime,
                  planned: Callable[[Path], bool] | None = None) -> list[dict]:
    """What `cutover status` shows for each of v2's labels while it is kept stopped: its
    stop record's expiry (`expiresAt`), the receipt it cites, whether it has lapsed by
    its expiry alone (`lapsed`) and, when `planned` is given, whether the isolation check
    counts it as planned (`planned`, computed the way the check computes it:
    `planned_by_check`), so a record past its form, custody or receipt shows as not
    planned however far its expiry is. `expiresAt` is None when the label has no readable
    record."""
    import os

    shown = []
    for label in v2_labels(labels):
        path = folder / f"{label}.json"
        value = None
        try:
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(descriptor, "rb") as stream:
                value = json.loads(stream.read(MAX_INPUT * 4))
        except (OSError, ValueError):
            value = None
        try:
            expires = dt.datetime.fromisoformat(str(value["expiresAt"]))
        except (TypeError, KeyError, ValueError):
            entry = {"label": label, "expiresAt": None, "lapsed": True}
            shown.append({**entry, "planned": False} if planned is not None else entry)
            continue
        receipt = value.get("receiptId") or value.get("operationId")
        entry = {"label": label, "expiresAt": expires.isoformat(), "receipt": receipt,
                 "lapsed": now > expires}
        if planned is not None:
            try:
                entry["planned"] = bool(planned(path))
            except Exception:  # noqa: BLE001 - a record the check cannot confirm is a lapse
                entry["planned"] = False
        shown.append(entry)
    return shown


def stopped_v2_labels(folder: Path, labels) -> dict[str, str]:
    """v2's labels that a stop left stopped, each with the receipt its stop record cites:
    a start removes the record, so a record there is a stop later than any start. The
    soak's start uses it to run a new start when a later stop superseded the start it
    would replay (the review's fix of 2026-10-26). A record it cannot read still counts
    as stopped (`unreadable`)."""
    stopped: dict[str, str] = {}
    for entry in stop_expiries(folder, labels, now=_now()):
        path = folder / f"{entry['label']}.json"
        if path.exists() or path.is_symlink():
            stopped[entry["label"]] = str(entry.get("receipt") or "unreadable")
    return stopped


def planned_by_check(*, owner_uid: int, held: Callable[[dict], bool],
                     now: Callable[[], dt.datetime]) -> Callable[[Path], bool]:
    """A stop record as the isolation check counts it (`IsolationCheck.boot`): readable
    by `fixed.read_stop_record` (owned by `owner_uid`, in its form, within its bound) and
    its receipt held (`isolation_check.receipt_held_by`)."""
    from .fixed import read_stop_record

    def planned(path: Path) -> bool:
        record = read_stop_record(path, owner_uid=owner_uid, now=now())
        return record is not None and bool(held(record))

    return planned


class OperatorReceipts:
    """The isolation check's receipt reader (`receipt_held_by`'s `reader`) over the
    in-person operator's own grants, for `cutover status`: the operator does not hold the
    service account's reader binding the root-run check reads."""

    def __init__(self, operator):
        self.operator = operator

    def read(self, operation_id: str) -> dict:
        from .u8_protocols import ReceiptReader

        receipt = self.operator._read_named(operation_id)
        return {"operation": str(receipt.get("operation")),
                "targetId": str(receipt.get("targetId")),
                "inputHash": str(receipt.get("inputHash")),
                "outcome": ReceiptReader.outcome(receipt),
                "recordedAt": None if receipt.get("recordedAt") is None
                else str(receipt["recordedAt"])}


class _NoLedger:
    """A realm whose ledger has never been opened holds no recovery request: the
    preconditions read an empty ledger, and nothing is created."""

    def records(self, kind: str) -> list:
        return []

    def get(self, kind: str, key) -> None:
        return None

    def close(self) -> None:
        return None


def realm_operator_for(environment_file: Path, *, clock=_now):
    """The composed realm's in-person operator, over its ledger (read only here)."""
    from backend.modules.operations.ledger import Ledger

    from .platform_profile import U8PlatformProfile
    from .u8_protocols import realm_operator

    profile = U8PlatformProfile.realm(environment_file.parent)
    folder = profile.run_root / "ledger"
    ledger = (Ledger.open(folder, clock=clock) if folder.exists() or folder.is_symlink()
              else _NoLedger())
    return realm_operator(profile, "operator", ledger, clock=clock), ledger


def production_operator_for(*, clock=_now):
    """Production's in-person operator (Step 37's wiring): the ledger through
    `docsuri-ledger` (`sudo -k`), the operator with its login released in person."""
    from docsuri_ops.production_wiring import LedgerClient, production_operator

    ledger = LedgerClient(via="in-person", clock=clock)
    try:
        return production_operator(ledger, clock=clock), ledger
    except Exception:
        ledger.close()
        raise


def main(argv: list[str]) -> int:
    from docsuri_ops.production_wiring import WiringRefused

    parser = argparse.ArgumentParser(prog="python -I -m docsuri_ops.u8_platform service")
    parser.add_argument("word", choices=WORDS)
    parser.add_argument("label")
    parser.add_argument("--environment-file", type=Path)
    parser.add_argument("--production", action="store_true")
    args = parser.parse_args(argv)
    raw = sys.stdin.buffer.read(MAX_INPUT + 1)
    try:
        if len(raw) > MAX_INPUT:
            raise ControlError(INVALID_INPUT, "input exceeds its bound")
        try:
            document = json.loads(raw or b"{}")
        except ValueError:
            # Only a JSON error is `input-not-json` (the review's fix of 2026-10-26).
            return _answer({"ok": False, "reason": "input-not-json"}, 1)
        if document != {}:
            raise ControlError(INVALID_INPUT, "service control takes an empty object")
        if args.production == (args.environment_file is not None):
            raise ControlError(POLICY_UNRESOLVED,
                               "name either --production or the realm's environment file")
        if args.production:
            from docsuri_ops.arrangement.paths import ArrangementPaths
            from docsuri_ops.release import release_run_active

            operator, ledger = production_operator_for()
            paths = ArrangementPaths()
            # The release command's run marker, read without a password or a lock.
            run_lock = lambda: release_run_active(paths)  # noqa: E731 - one reader
        else:
            # The composed realm runs no release command beside its service words: no
            # run lock to read (its tests hand `run_service` one under a test prefix).
            operator, ledger = realm_operator_for(args.environment_file)
            run_lock = None
        try:
            result = run_service(args.word, args.label, operator, ledger=ledger,
                                 run_lock=run_lock)
        finally:
            ledger.close()
    except WiringRefused as refused:
        return _answer({"ok": False, "reason": str(refused)}, 1)
    except ControlError as error:
        return _answer({"ok": False, "error": error.as_wire_error()}, 1)
    except Exception as error:  # noqa: BLE001 - every other failure, with its own reason
        return _answer({"ok": False, "reason": _failure_reason(error)}, 1)
    return _answer({"ok": True, "result": result}, 0)


def _answer(value: dict, status: int) -> int:
    sys.stdout.write(json.dumps(value, sort_keys=True))
    return status


def _failure_reason(error: Exception) -> str:
    """A failure outside the input's form, by its own fixed reason: the error's reason
    key when it carries one (a wiring or driver refusal), `profile-unreadable` for a
    profile or binding the tool cannot read, `store-unavailable` for the store, else
    `service-control-failed`. Never a path, value or traceback."""
    reason = getattr(error, "reason", None)
    if isinstance(reason, str) and reason.replace("-", "").isalnum():
        return reason
    if isinstance(error, (OSError, ValueError, KeyError)):
        return "profile-unreadable"
    if type(error).__module__.startswith("psycopg"):
        return "store-unavailable"
    return "service-control-failed"
