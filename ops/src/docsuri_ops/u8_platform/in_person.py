"""In person (U8 plan Step 27; D4, R6, security-design § 5.3).

- The actor of an in-person step is the account sudo authenticated, read from
  `SUDO_UID`, which sudo sets itself so a caller cannot choose it. `getpass.getuser()`
  stays only for display. In the composed realm the realm driver's synthetic operator
  (`operator.json`) stands in for it.
- `actor_from_sudo` has three production callers (U8 plan Step 119; D4): the credential
  release (`fixed.credential_release`), which serves only the installed operator and
  names that account in its result, so the operator tool binds the account its release
  named; `production_wiring.in_person_actor`, for the release command run as root; and
  the installer's in-person password change. The production tool's in-person words
  (`production_tool.invoke`) bind no actor and read no `SUDO_UID`: they run as the
  service account under `sudo -k -u`, a decision they apply was bound to the operator's
  actor by `platform.decision.record`, and a word that takes a login releases it through
  the credential release, whose own check refuses every account but the installed
  operator. A MaintainerApproval appended through `docsuri-ledger append` is not gated on
  `SUDO_UID`; its receipt-authority checks stay as built.
- The operator tool runs each bound step under `StepClock`, which shows the step's
  elapsed time against its bound while it runs and records whether it went over. It
  never cuts a step off: a step past its bound keeps running to its own end (R6).
"""

from __future__ import annotations

import json
import pwd
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from docsuri_ops.platform_control.errors import FORBIDDEN, ControlError

REFRESH_SECONDS = 15.0


def actor_from_sudo(environ: Mapping[str, str], *,
                    lookup: Callable[[int], object] = pwd.getpwuid) -> str:
    """The account sudo authenticated; refused when sudo did not run the step."""
    value = environ.get("SUDO_UID", "")
    if not value.isdigit():
        raise ControlError(FORBIDDEN, "an in-person step runs only through sudo")
    try:
        account = lookup(int(value))
    except KeyError:
        raise ControlError(FORBIDDEN, "the authenticated account is unknown") from None
    name = getattr(account, "pw_name", None)
    if not name:
        raise ControlError(FORBIDDEN, "the authenticated account is unknown")
    return name


def realm_actor(run_root: Path) -> str:
    """The composed realm's synthetic operator (decision "Recording your decisions in
    the realm")."""
    from docsuri_ops.platform_control.profile import private_bytes

    value = json.loads(private_bytes(run_root / "operator.json"))
    if value.get("kind") != "synthetic-operator":
        raise ControlError(FORBIDDEN, "not the realm's synthetic operator")
    return f"realm-operator:{value['operatorId']}"


@dataclass(frozen=True)
class StepRecord:
    step: str
    bound_seconds: float
    elapsed_seconds: float

    @property
    def over_bound(self) -> bool:
        return self.elapsed_seconds > self.bound_seconds

    def as_dict(self) -> dict:
        return {"step": self.step, "boundSeconds": self.bound_seconds,
                "elapsedSeconds": round(self.elapsed_seconds, 3), "overBound": self.over_bound}


class StepClock:
    """Shows each bound step's elapsed time against its bound; never cuts one off."""

    def __init__(self, show: Callable[[str], None], *, monotonic: Callable[[], float] =
                 time.monotonic, refresh_seconds: float = REFRESH_SECONDS):
        self.show, self.monotonic, self.refresh = show, monotonic, refresh_seconds

    def line(self, step: str, elapsed: float, bound: float) -> str:
        state = "over its bound" if elapsed > bound else "within its bound"
        return f"{step}: {elapsed:.0f} s of {bound:.0f} s ({state})"

    def run(self, step: str, bound_seconds: float, work: Callable[[], object]):
        if not bound_seconds > 0:
            raise ValueError("a bound step needs a positive bound")
        started = self.monotonic()
        finished = threading.Event()

        def report() -> None:
            while not finished.wait(self.refresh):
                self.show(self.line(step, self.monotonic() - started, bound_seconds))

        watcher = threading.Thread(target=report, daemon=True)
        watcher.start()
        try:
            result = work()  # runs to its own end, whatever the bound
        finally:
            finished.set()
            watcher.join()
        record = StepRecord(step, bound_seconds, self.monotonic() - started)
        self.show(self.line(step, record.elapsed_seconds, bound_seconds))
        return result, record
