"""The operator tool's availability report (U8 plan Step 72(b); NFR9.13, observability-design
§ 12, L1-45).

`python -I -m docsuri_ops.u8_platform availability report [--month YYYY-MM]
(--production | --environment-file PATH)` prints one JSON result for a calendar month in
Asia/Seoul (the current month by default):

- **The record.** The heartbeat's availability folder, read directly, with no sudo and
  no subprocess: in production `ArrangementPaths().availability` with
  `PRODUCTION_OPERATIONS.availability_slot_seconds` (300); in the composed realm the run
  root's `availability/` with `SYNTHETIC_OPERATIONS`' slot (5).
- **The opening.** The newest CutoverRecord's `admissionOpenedAt`, through the in-person
  ledger read: production's `LedgerClient(via="in-person")` (`sudo -k`, your password),
  or the realm's own ledger; a realm whose ledger does not exist yet has no opening.
- **The result.** `month`, `closed` (true for a month before the current Seoul month)
  and `admissionOpenedAt` (null without an opening), with:
  - for the opening's month and every later month, `AvailabilityRecord.figure` from the
    opening, as `Figure.as_dict()`: the running figure and the budget left for the
    current month, or a closed month's figure over all its slots;
  - with no opening, or for a month that ends at or before the opening, only the
    month's slot counts (`scheduledSlots`, `upSlots`, `downSlots`) and
    `"beforeOpening": true`: § 12 counts the first month from admission opening, so a
    slot before it is not v2's availability, and `figure` with an opening after a
    month's end would give a negative budget.
- **Refusals.** A refused ledger read prints `{"ok": false, "reason": <its key>}` and
  exits 1, never a figure without the opening. A word or flag outside the form prints
  the usage and exits 2.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TextIO

WORDS = ("report",)
USAGE = ("usage: python -I -m docsuri_ops.u8_platform availability report "
         "[--month YYYY-MM] (--production | --environment-file PATH)\n")
_MONTH = re.compile(r"[0-9]{4}-(0[1-9]|1[0-2])")


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _iso_ms(moment: dt.datetime) -> str:
    return moment.astimezone(dt.UTC).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z")


def admission_opened(ledger) -> dt.datetime | None:
    """The newest CutoverRecord's `admissionOpenedAt`, or None (no ledger, no record, or
    a record that has not opened admission)."""
    if ledger is None:
        return None
    records = ledger.records("cutover-record")
    if not records or not records[-1].get("admissionOpenedAt"):
        return None
    moment = dt.datetime.fromisoformat(str(records[-1]["admissionOpenedAt"]).replace(
        "Z", "+00:00"))
    if moment.tzinfo is None:
        raise ValueError("an admission opening is an aware instant")
    return moment


def report(month: str | None, *, folder: Path, slot_seconds: int, now: dt.datetime,
           opened_at: dt.datetime | None) -> dict:
    """The month's result (the current Seoul month when `month` is None)."""
    from docsuri_ops.standing.availability import AvailabilityRecord, month_bounds, month_of

    current = month_of(now)
    chosen = current if month is None else month
    record = AvailabilityRecord(folder, slot_seconds=slot_seconds)
    _start, end = month_bounds(chosen)
    common = {"closed": chosen < current,
              "admissionOpenedAt": None if opened_at is None else _iso_ms(opened_at)}
    if opened_at is None or end <= opened_at:
        figure = record.figure(chosen, now)
        return {"month": chosen, "scheduledSlots": figure.scheduled, "upSlots": figure.up,
                "downSlots": figure.down, "beforeOpening": True, **common}
    return {**record.figure(chosen, now, opened_at=opened_at).as_dict(), **common}


def run(month: str | None, *, folder: Path, slot_seconds: int,
        ledger_reader: Callable[[], object], clock: Callable[[], dt.datetime] = _now,
        stdout: TextIO | None = None) -> int:
    """Read the opening through `ledger_reader` (a ledger, or None when there is none),
    then print the report. A refused read prints only its reason and exits 1."""
    from docsuri_ops.production_wiring import WiringRefused

    out = stdout or sys.stdout
    ledger = None
    try:
        ledger = ledger_reader()
        opened_at = admission_opened(ledger)
    except WiringRefused as refused:
        out.write(json.dumps({"ok": False, "reason": str(refused)}, sort_keys=True))
        return 1
    finally:
        if ledger is not None:
            ledger.close()
    out.write(json.dumps(report(month, folder=folder, slot_seconds=slot_seconds,
                                now=clock(), opened_at=opened_at), sort_keys=True))
    return 0


def _parse(argv: list[str]) -> tuple[str | None, bool, Path | None] | None:
    """`report [--month YYYY-MM] (--production | --environment-file PATH)`, or None."""
    if not argv or argv[0] not in WORDS:
        return None
    month: str | None = None
    production = False
    environment: Path | None = None
    rest = list(argv[1:])
    while rest:
        flag = rest.pop(0)
        if flag == "--production" and not production:
            production = True
        elif flag in ("--month", "--environment-file") and rest:
            value = rest.pop(0)
            if flag == "--month" and month is None and _MONTH.fullmatch(value):
                month = value
            elif flag == "--environment-file" and environment is None:
                environment = Path(value)
            else:
                return None
        else:
            return None
    if production == (environment is not None):
        return None
    return month, production, environment


def main(argv: list[str]) -> int:
    parsed = _parse(argv)
    if parsed is None:
        sys.stderr.write(USAGE)
        return 2
    month, production, environment = parsed
    from backend.u8_policy import PRODUCTION_OPERATIONS, SYNTHETIC_OPERATIONS

    if production:
        from docsuri_ops.arrangement.paths import ArrangementPaths
        from docsuri_ops.production_wiring import LedgerClient

        return run(month, folder=ArrangementPaths().availability,
                   slot_seconds=int(PRODUCTION_OPERATIONS.availability_slot_seconds),
                   ledger_reader=lambda: LedgerClient(via="in-person"))
    from backend.modules.operations.ledger import Ledger

    from .platform_profile import U8PlatformProfile

    run_root = U8PlatformProfile.realm(environment.parent).run_root
    ledger_folder = run_root / "ledger"

    def realm_ledger():
        if not (ledger_folder.exists() or ledger_folder.is_symlink()):
            return None
        return Ledger.open(ledger_folder, clock=_now)

    return run(month, folder=run_root / "availability",
               slot_seconds=int(SYNTHETIC_OPERATIONS.availability_slot_seconds),
               ledger_reader=realm_ledger)
