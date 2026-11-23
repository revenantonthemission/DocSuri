"""The CutoverRecord machine in the operations ledger (U8 plan Step 33; BR9.1–BR9.17,
RC2, functional-spec.md § State machine — CutoverRecord).

Exactly one CutoverRecord exists, and it is never deleted. Every change is one version of
it, decided and appended while the ledger's lock is held (`Ledger.atomic`), so a guard
and the append it allows are one step for every process. The guards are the table's:

- **preparing / rolled-back**: a dry run accepted sets `acceptedDryRunId`; with the
  complete verification also passed on the release (BR10.5) the soak starts
  (`rehearsing`, `soakStartedAt`). From `rolled-back`, nothing starts while the
  rollback's copy is pending.
- **rehearsing**: a newer dry run moves the soak onto its database; a new release tag
  resets the clean period; the soak's verdict is ledger evidence only (`soak_verdict`,
  BR9.3); once BR9.2 (1)–(9) hold the cutover is `ready-to-switch`, and a lapse returns
  it to `rehearsing` with the missing items named. A rehearsal database reaching its
  backstop returns the cutover to `preparing` with an incident on storage.capacity.
- **the switch** (`switching`): your decision on the start with BR9.2 holding; the
  4-hour bound runs from v1's stop (`v1_stopped`), after which only the abort is
  offered (R8). Opening needs the approved final report, the first live backup passed,
  every configured outward or sign-in provider active or accepted unavailable by your
  opening decision, every required capability available and no incident open (BR9.4).
- **the abort** (`aborting`): the abort's incident is the live operations.cutover one,
  taken over or opened (`Incidents.take_over_cutover`); it returns to `rehearsing` only
  once v1 answers at the public address again, and stays `aborting` when v1 does not
  start (BR9.5).
- **the rollback** (`rolling-back`): your decision within the window; v1 serves again
  (`rollbackV1ServingAt`) only after v2's lifecycle outcomes reached v1 and every v1
  session ended (BR9.13); at that step the accepted dry run is cleared, its database
  gone with opening (`rollback_returned_to_rehearsal`); then the copy is recorded
  (`rolled-back`), or it is pending
  (`rollbackCopyPendingSince`, its incident taken over), retried, written to a
  replacement volume, or waived by your decision. Before v1 serves, your decision can
  cancel it (`switched`).
- **settlement** (`settled`): your decision after the window, with the consumer
  inventory's dispositions ready (BR9.8, BR9.11).

Each effect's PlatformControl receipt is added to `effectReceipts` with its binding
facts, and each of your decisions to `approvals`. The operator tool runs the effects
(`docsuri_ops.cutover.tool`); this module keeps the machine, the soak's verdict, the
restart rehearsal's record, the first sign-in notice and the routing reader the
`operations.cutover` producer compares the record with.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
import stat
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from uuid import UUID, uuid4

from .errors import OperationsError
from .ledger import Ledger, utc_text

KIND = "cutover-record"
INCIDENT = "service-incident"
# One rollback attempt's own facts. Each rollback starts without them, and a rolled-back
# record that goes back to rehearsing leaves them behind, so a later switch's rollback
# runs every step of its own (BR9.7, the CutoverRecord rows for `rolled-back`).
ROLLBACK_ATTEMPT = {"rollbackV1ServingAt": None, "rollbackCopyIncidentId": None,
                    "rollbackCopyPendingSince": None}
LIVE_EXCLUSION = frozenset({"switching", "aborting", "rolling-back"})
BEFORE_SWITCH = frozenset({"preparing", "rehearsing", "ready-to-switch"})
STORAGE = "storage.capacity"
ISOLATION = "platform.isolation"
OUTWARD_AND_SIGN_IN = ("google", "orcid", "resend", "notion")
MAX_RECEIPTS = 512
# Where the public address is routed in each state (the producer compares it).
EXPECTED_ROUTE = {
    "preparing": "v1-web", "rehearsing": "v1-web", "ready-to-switch": "v1-web",
    "switching": "maintenance", "switched": "v2-host", "settled": "v2-host",
    "aborting": "v1-web", "rolling-back": "v1-web", "rolled-back": "v1-web",
}


def _parse(text: str) -> dt.datetime:
    return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))


def _refused(reason: str, **facts) -> OperationsError:
    return OperationsError("CONFLICT", current={"reasonKey": reason, **facts})


def _no_release_exclusion(view) -> None:
    """The exclusion holds both ways (the review's fix of 2026-10-26): no switch and no
    cutover rollback starts while an install or a release rollback holds it."""
    from .release_records import release_blocker

    blocker = release_blocker(view)
    if blocker is not None:
        raise _refused(blocker)


def render_subject(subject: Mapping) -> bytes:
    """The exact bytes a decision's subject is shown as (`u8_platform.decisions`)."""
    return json.dumps(subject, sort_keys=True, indent=2, ensure_ascii=False).encode() + b"\n"


def subject_digest(subject: Mapping) -> str:
    return hashlib.sha256(render_subject(subject)).hexdigest()


# --- the soak's verdict (BR9.3) -----------------------------------------------------------


def soak_verdict(reader, record: Mapping, now: dt.datetime) -> tuple[bool, list[str]]:
    """Whether the soak ran clean for its full period on ledger evidence alone, with the
    reasons it did not: for the rehearsal environment and the soak period, every incident
    on a required capability or on platform.isolation resolved with verification, the
    scheduled backups recorded each day with integrity passed, at least one restore
    verification verified, and no incident open at its end."""
    from backend.u8_registry import REQUIRED

    started = record.get("soakStartedAt")
    if started is None:
        return False, ["soak-not-started"]
    start = _parse(started)
    end = start + dt.timedelta(seconds=record["soakPeriodSeconds"])
    reasons: list[str] = []
    if now < end:
        reasons.append("soak-period-running")
    for incident in reader.records(INCIDENT):
        if incident["environment"] != "rehearsal":
            continue
        if incident["state"] != "resolved":
            reasons.append("incident-open")
            continue
        opened = _parse(incident["openedAt"])
        counted = any(name in REQUIRED or name == ISOLATION for name in incident["capabilities"])
        if counted and start <= opened <= end and (
            incident.get("resolutionKind") != "capability-available"
        ):
            reasons.append("incident-not-resolved-with-verification")
    sets = [item for item in reader.records("backup-set")
            if item["environment"] == "rehearsal" and item["trigger"] == "scheduled"
            and start <= _parse(item["takenAt"]) <= end]
    if any(item["integrity"] != "passed" for item in sets):
        reasons.append("scheduled-backup-failed")
    days = math.ceil(record["soakPeriodSeconds"] / 86400)
    passed_days = {_parse(item["takenAt"]).date() for item in sets
                   if item["integrity"] == "passed"}
    if len(passed_days) < days:
        reasons.append("scheduled-backups-missing")
    if not any(
        item["environment"] == "rehearsal" and item.get("result") == "verified"
        and start <= _parse(item["startedAt"]) <= end
        for item in reader.records("restore-verification")
    ):
        reasons.append("restore-verification-missing")
    return not reasons, list(dict.fromkeys(reasons))


# --- the restart rehearsal (BR9.16) --------------------------------------------------------


def rehearsal_current(record: Mapping, now: dt.datetime, *, window_seconds: int,
                      commit: str | None, fingerprint_matches: bool) -> str | None:
    """Why v1's restart rehearsal does not count now, or None: it must have passed within
    its window, at the commit v1 runs from now, with v1's checkout and services unchanged
    since (any change voids it)."""
    rehearsed = record.get("v1RestartRehearsedAt")
    if rehearsed is None or record.get("v1CheckoutCommit") is None:
        return "restart-rehearsal-missing"
    if commit is None:
        return "v1-checkout-not-fixed"
    if commit != record["v1CheckoutCommit"] or not fingerprint_matches:
        return "restart-rehearsal-void"
    if now - _parse(rehearsed) > dt.timedelta(seconds=window_seconds):
        return "restart-rehearsal-expired"
    return None


# --- the first sign-in notice (BR9.6) ------------------------------------------------------


def moved_notice(profile) -> bool:
    """The profile marks the switch: once it is live with admission open, every arrival
    is a first sign-in after the move, and the entry screen shows MovedNotice (Step 41)."""
    return bool(getattr(profile, "is_production", False)) and (
        getattr(profile, "mode", None) == "live" and getattr(profile, "admission", None) == "open"
    )


# --- the routing reader for `operations.cutover` -------------------------------------------


def _read_bounded(path: Path, *, maximum: int = 4096) -> dict | None:
    """A small JSON file read without following a link or blocking on a FIFO."""
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return None
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_size > maximum:
            return None
        value = json.loads(os.read(descriptor, maximum))
    except (OSError, ValueError):
        return None
    finally:
        os.close(descriptor)
    return value if isinstance(value, dict) else None


def active_route_path(profile, arrangement=None) -> Path:
    """Where the active tunnel origin is recorded: the root-owned `active.json` of the
    tunnel's registered configurations in production (`docsuri-tunnel-route`, under the
    composition's one arrangement value), the run root's `tunnel-active.json` in the
    composed realm (the realm driver's routing)."""
    if getattr(profile, "is_production", False):
        if arrangement is None:
            from docsuri_ops.arrangement.paths import ArrangementPaths

            arrangement = ArrangementPaths()
        return arrangement.tunnel_config / "active.json"
    return Path(profile.root) / "tunnel-active.json"


def routing_reader(profile, inspect: Callable[[], dict],
                   arrangement=None) -> Callable[[], dict]:
    """PlatformControl's routing evidence, read-only: the public address's active origin
    and the number of effects whose outcome is still unresolved (`inspect`, the bounded
    status reader). The service account can execute nothing through it."""
    path = active_route_path(profile, arrangement)
    run_id = None if getattr(profile, "is_production", False) else getattr(profile, "run_id", None)

    def read() -> dict:
        value = _read_bounded(path) or {}
        origin = value.get("origin")
        if run_id is not None and value.get("runId") != run_id:
            origin = None
        status = inspect()
        return {"route": origin if origin in EXPECTED_ROUTE.values() else None,
                "unknownEffects": int(status.get("unresolved", 0))}

    return read


# --- the machine ---------------------------------------------------------------------------


class Cutover:
    def __init__(self, ledger: Ledger, policy, *, clock: Callable[[], dt.datetime] | None = None,
                 incidents=None):
        self.ledger, self.policy = ledger, policy
        self.clock = clock or ledger.clock
        if incidents is None:
            from .incidents import Incidents

            incidents = Incidents(ledger, environment="live")
        self.incidents = incidents

    # --- reading -------------------------------------------------------------------

    def current(self) -> dict | None:
        records = self.ledger.records(KIND)
        return records[-1] if records else None

    def require(self) -> dict:
        record = self.current()
        if record is None:
            raise OperationsError("NOT_FOUND")
        return record

    def holds_live_exclusion(self) -> bool:
        record = self.current()
        return record is not None and record["state"] in LIVE_EXCLUSION

    def bound_passed(self, now: dt.datetime | None = None) -> bool:
        """The 4-hour bound from v1's stop has passed: only the abort is offered (R8)."""
        record = self.current()
        if record is None or record["state"] != "switching" or "switchStartedAt" not in record:
            return False
        moment = now or self.clock()
        return moment - _parse(record["switchStartedAt"]) > dt.timedelta(
            seconds=record["switchTimeBoundSeconds"])

    def window_open(self, now: dt.datetime | None = None) -> bool:
        record = self.current()
        if record is None or "admissionOpenedAt" not in record:
            return False
        moment = now or self.clock()
        return moment - _parse(record["admissionOpenedAt"]) <= dt.timedelta(
            seconds=record["rollbackWindowSeconds"])

    # --- versions --------------------------------------------------------------------

    def begin(self, release_tag: str) -> dict:
        """(none) → preparing: U8 starts building the release (exactly one record)."""
        record = {
            "cutoverId": str(uuid4()), "releaseTag": release_tag, "state": "preparing",
            "soakPeriodSeconds": self.policy.soak_clean_seconds, "soakClean": False,
            "switchTimeBoundSeconds": self.policy.switch_bound_seconds,
            "rollbackWindowSeconds": self.policy.rollback_window_seconds,
            "effectReceipts": [], "approvals": [],
        }

        def step(view):
            if view.records(KIND):
                raise _refused("cutover-record-exists")
            view.append(KIND, record, expect_revision=0)
            return record

        return self.ledger.atomic(step)

    def _move(self, decide: Callable[[dict, object], dict | None], *,
              receipts: Iterable[dict] = (), approval: str | None = None) -> dict:
        """One version: `decide(current, view)` returns the changed fields (with `state`)
        or None to leave the record as it is; receipts and an approval are added in the
        same version."""
        facts = tuple(receipts)

        def step(view):
            records = view.records(KIND)
            if not records:
                raise OperationsError("NOT_FOUND")
            current = records[-1]
            change = decide(current, view)
            if change is None and not facts and approval is None:
                return current
            record = {**current, **(change or {})}
            for name in [name for name, value in record.items() if value is None]:
                record.pop(name)
            cited = list(record["effectReceipts"])
            for item in facts:
                if item["receiptId"] not in cited:
                    cited.append(item["receiptId"])
            if len(cited) > MAX_RECEIPTS:
                raise _refused("receipt-list-full")
            record["effectReceipts"] = cited
            if approval is not None and approval not in record["approvals"]:
                record["approvals"] = [*record["approvals"], approval][-MAX_RECEIPTS:]
            if record == current:
                return current
            key = current["cutoverId"]
            view.append(KIND, record, expect_revision=view.revision(KIND, key), receipts=facts)
            return record

        return self.ledger.atomic(step)

    def _approved(self, view, current: dict, approval_id, step: str) -> dict:
        """Your decision for this record's step; a declined one refuses the move."""
        approval = None if approval_id is None else view.get("maintainer-approval",
                                                             str(approval_id))
        if approval is None or approval["step"] != step or (
            approval["subjectRef"] != current["cutoverId"]
        ):
            raise OperationsError("FORBIDDEN", current={"reasonKey": "decision-required"})
        if approval["decision"] != "approved":
            raise _refused("decision-declined")
        return approval

    @staticmethod
    def _in(current: dict, *states: str) -> None:
        if current["state"] not in states:
            raise _refused("cutover-not-at-this-step", state=current["state"])

    def record_receipts(self, receipts: Iterable[dict]) -> dict:
        """Add effect receipts in the current state (a step's bound operations)."""
        return self._move(lambda current, view: None, receipts=receipts)

    # --- before the switch -------------------------------------------------------------

    def dry_run_accepted(self, run_id) -> dict:
        """A dry run accepted: the soak moves onto its database (BR9.3); a ready cutover
        lapses until BR9.2 is checked again."""
        identity = str(UUID(str(run_id)))

        def decide(current, view):
            self._in(current, "preparing", "rehearsing", "ready-to-switch", "rolled-back")
            if current["state"] == "rolled-back" and "rollbackCopyPendingSince" in current:
                raise _refused("rollback-copy-pending")
            run = view.get("migration-run", identity)
            if run is None or run["kind"] != "dry" or run["state"] != "accepted":
                raise _refused("dry-run-not-accepted")
            target = (view.get("retained-copy", run["targetCopyId"])
                      if run.get("targetCopyId") else {})
            if target is None or any(name in target for name in (
                    "disposedAt", "retiredWithVolumeAt", "returnedToServiceAt")):
                # The run's rehearsal database is gone: the soak cannot move onto it.
                raise _refused("rehearsal-database-disposed")
            state = "rehearsing" if current["state"] == "ready-to-switch" else current["state"]
            return {"acceptedDryRunId": identity, "state": state}

        return self._move(decide)

    def verification_passed(self, run_id, release_tag: str) -> dict:
        """The complete verification passed on this release (BR10.5)."""
        identity = str(UUID(str(run_id)))

        def decide(current, view):
            if current["releaseTag"] != release_tag:
                raise _refused("verification-not-for-this-release")
            if current["state"] in LIVE_EXCLUSION or current["state"] == "settled":
                raise _refused("cutover-not-at-this-step", state=current["state"])
            return {"verificationRunId": identity}

        return self._move(decide)

    def start_soak(self) -> dict:
        """preparing or rolled-back → rehearsing: an accepted dry run exists and the
        complete verification passed on the release, in either order (BR10.5). Leaving
        rolled-back clears the finished rollback's own facts (`ROLLBACK_ATTEMPT`). Refused
        while an install or a release rollback holds the live exclusion, read inside the
        same atomic step (review finding, Minor, R13)."""
        now = utc_text(self.clock())

        def decide(current, view):
            self._in(current, "preparing", "rolled-back")
            _no_release_exclusion(view)
            if current["state"] == "rolled-back" and "rollbackCopyPendingSince" in current:
                raise _refused("rollback-copy-pending")
            if "acceptedDryRunId" not in current:
                raise _refused("dry-run-not-accepted")
            if "verificationRunId" not in current:
                raise _refused("verification-not-passed")
            return {"state": "rehearsing", "soakStartedAt": now, "soakClean": False,
                    **ROLLBACK_ATTEMPT}

        return self._move(decide)

    def new_release(self, release_tag: str) -> dict:
        """A new release tag resets the soak's clean period; the soak starts again only
        once the complete verification passes on the new tag (BR9.3)."""

        def decide(current, view):
            self._in(current, "preparing", "rehearsing", "ready-to-switch", "rolled-back")
            if current["releaseTag"] == release_tag:
                return None
            state = "rehearsing" if current["state"] == "ready-to-switch" else current["state"]
            return {"releaseTag": release_tag, "state": state, "soakStartedAt": None,
                    "soakClean": False, "verificationRunId": None}

        return self._move(decide)

    def restart_soak(self) -> dict:
        """rehearsing with no soak running (after a new tag): the verification passed on
        the new tag, so the soak starts again."""
        now = utc_text(self.clock())

        def decide(current, view):
            self._in(current, "rehearsing")
            if "soakStartedAt" in current:
                return None
            if "verificationRunId" not in current:
                raise _refused("verification-not-passed")
            return {"soakStartedAt": now, "soakClean": False}

        return self._move(decide)

    def evaluate_soak(self) -> tuple[dict, list[str]]:
        """Record the soak's verdict from the ledger (BR9.3)."""
        now = self.clock()
        reasons: list[str] = []

        def decide(current, view):
            self._in(current, "rehearsing", "ready-to-switch")
            clean, why = soak_verdict(view, current, now)
            reasons.extend(why)
            return {"soakClean": clean}

        return self._move(decide), reasons

    def check_ready(self, missing: Iterable[str]) -> dict:
        """The preconditions checked again: rehearsing → ready-to-switch when BR9.2 (1)–(9)
        hold, ready-to-switch → rehearsing when one lapsed."""
        gaps = list(missing)

        def decide(current, view):
            self._in(current, "rehearsing", "ready-to-switch")
            if gaps:
                return {"state": "rehearsing"}
            if not current["soakClean"]:
                raise _refused("soak-not-clean")
            return {"state": "ready-to-switch"}

        return self._move(decide)

    def rehearsal_backstop(self) -> dict:
        """The accepted dry run's rehearsal database reached its backstop: back to
        preparing, with an incident on storage.capacity until the operator removes it in
        person (BR9.12, BR9.17); a new dry run is needed."""

        def decide(current, view):
            self._in(current, "rehearsing", "ready-to-switch")
            return {"state": "preparing", "acceptedDryRunId": None, "soakStartedAt": None,
                    "soakClean": False}

        record = self._move(decide)
        self.incidents.signal(STORAGE, "tolerance-exceeded",
                              correlation=f"cutover:{record['cutoverId']}:rehearsal-backstop",
                              environment="rehearsal")
        return record

    def record_restart_rehearsal(self, approval_id, *, commit: str,
                                 receipts: Iterable[dict]) -> dict:
        """v1's restart rehearsal passed, on your decision, with its receipts and v1's
        commit (BR9.16)."""
        now = utc_text(self.clock())
        facts = tuple(receipts)

        def decide(current, view):
            self._in(current, "preparing", "rehearsing", "ready-to-switch", "rolled-back")
            self._approved(view, current, approval_id, "v1-restart-rehearsal")
            return {"v1CheckoutCommit": commit, "v1RestartRehearsedAt": now}

        return self._move(decide, receipts=facts, approval=str(approval_id))

    # --- the switch ------------------------------------------------------------------

    def approve_start(self, approval_id, missing: Iterable[str], *,
                      checked_at: dt.datetime | None = None) -> dict:
        """ready-to-switch → switching on your decision, with BR9.2 holding: the live
        environment's exclusion is held from here (BR4.4, BR9.10). The instant the
        preconditions were checked is recorded as `switchCheckedAt` (the machine's own
        clock when none is given), and an earlier abort's `abortStartedAt` is cleared
        (U8 plan Step 70(a)-(b))."""
        gaps = list(missing)
        checked = utc_text(checked_at or self.clock())

        def decide(current, view):
            self._in(current, "ready-to-switch")
            self._approved(view, current, approval_id, "switch-start")
            _no_release_exclusion(view)
            if gaps:
                raise _refused("precondition-missing", missing=gaps)
            return {"state": "switching", "switchStartedAt": None, "finalRunId": None,
                    "switchCheckedAt": checked, "abortStartedAt": None}

        return self._move(decide, approval=str(approval_id))

    def v1_stopped(self, receipts: Iterable[dict]) -> dict:
        """v1's writes stopped: the 4-hour switch bound starts from here (R8)."""
        now = utc_text(self.clock())

        def decide(current, view):
            self._in(current, "switching")
            if "switchStartedAt" in current:
                return None
            return {"switchStartedAt": now}

        return self._move(decide, receipts=receipts)

    def final_run(self, run_id) -> dict:
        identity = str(UUID(str(run_id)))

        def decide(current, view):
            self._in(current, "switching")
            run = view.get("migration-run", identity)
            if run is None or run["kind"] != "final":
                raise _refused("not-a-final-run")
            return {"finalRunId": identity}

        return self._move(decide)

    def opening_gates(self, view, current: dict, *, accepted_unavailable: Iterable[str],
                      capabilities_missing: Iterable[str]) -> list[str]:
        """What BR9.4 still misses before admission opens, each named."""
        missing: list[str] = []
        run = view.get("migration-run", current.get("finalRunId")) if current.get(
            "finalRunId") else None
        if run is None or run["state"] != "accepted":
            missing.append("final-report-not-approved")
        started = current.get("switchStartedAt")
        if started is None or not any(
            item["environment"] == "live" and item["trigger"] == "first-live"
            and item["integrity"] == "passed" and _parse(item["takenAt"]) >= _parse(started)
            for item in view.records("backup-set")
        ):
            missing.append("first-live-backup-not-passed")
        accepted = set(accepted_unavailable)
        for record in view.records("provider-activation"):
            if record["provider"] in OUTWARD_AND_SIGN_IN and record["state"] not in (
                "active", "unconfigured"
            ) and record["provider"] not in accepted:
                missing.append(f"provider-{record['provider']}-not-verified")
        missing.extend(f"capability-{name}-not-available" for name in capabilities_missing)
        if any(item["state"] != "resolved" for item in view.records(INCIDENT)):
            missing.append("incident-open")
        return missing

    def open(self, approval_id, subject: Mapping, *,
             capabilities_missing: Iterable[str]) -> dict:
        """switching → switched on your opening decision, whose shown subject names any
        provider it accepts unavailable; refused with the missing items named (BR9.4)."""
        now = utc_text(self.clock())
        missing_capabilities = list(capabilities_missing)

        def decide(current, view):
            self._in(current, "switching")
            approval = self._approved(view, current, approval_id, "admission-opening")
            if approval["subjectDigest"] != subject_digest(subject):
                raise _refused("decision-subject-differs")
            missing = self.opening_gates(
                view, current,
                accepted_unavailable=subject.get("providersAcceptedUnavailable", []),
                capabilities_missing=missing_capabilities)
            if missing:
                raise _refused("opening-gate-missing", missing=missing)
            return {"state": "switched", "admissionOpenedAt": now}

        return self._move(decide, approval=str(approval_id))

    def stores_recorded(self, copy_id) -> dict:
        """Right after admission opens, v1's stopped stores are a retained copy."""

        def decide(current, view):
            self._in(current, "switched")
            return {"v1StoresCopyId": str(UUID(str(copy_id)))}

        return self._move(decide)

    def final_snapshot(self, copy_id) -> dict:
        def decide(current, view):
            self._in(current, "switching", "aborting", "switched")
            return {"finalSnapshotCopyId": None if copy_id is None else str(UUID(str(copy_id)))}

        return self._move(decide)

    # --- the abort (BR9.5) --------------------------------------------------------------

    def abort(self, *, reason: str) -> dict:
        """switching → aborting: a failed or declined step, an interrupted final run past
        its bound, or the switch bound passing. The abort's incident is the live
        operations.cutover incident, taken over or opened."""
        current = self.require()
        self._in(current, "switching", "aborting")
        incident = self.incidents.take_over_cutover(
            "switch-aborted", correlation=f"cutover:{current['cutoverId']}:{reason}")
        now = utc_text(self.clock())

        def decide(current, view):
            self._in(current, "switching", "aborting")
            change = {"state": "aborting", "abortIncidentId": incident["incidentId"]}
            if current["state"] == "switching":
                # The abort's start, from which an aborted final snapshot's 30 days count
                # on your disposal-date decision (U8 plan Step 70(a), L1-3, L1-66).
                change["abortStartedAt"] = now
            return change

        return self._move(decide)

    def v1_restart_failed(self) -> dict:
        """v1 did not start: the cutover stays aborting, and the abort's incident records
        v1-restart-failed (BR9.16)."""
        current = self.require()
        self._in(current, "aborting")
        self.incidents.take_over_cutover(
            "switch-aborted", correlation=f"cutover:{current['cutoverId']}:v1-restart-failed")
        return current

    def aborted(self, *, receipts: Iterable[dict] = ()) -> dict:
        """aborting → rehearsing once v1 answers at the public address again."""

        def decide(current, view):
            self._in(current, "aborting")
            return {"state": "rehearsing", "switchStartedAt": None}

        return self._move(decide, receipts=receipts)

    # --- the rollback (BR9.7, BR9.13) ------------------------------------------------------

    def rollback(self, approval_id) -> dict:
        """switched → rolling-back on your decision within the window. The rollback starts
        with none of an earlier rollback's facts (`ROLLBACK_ATTEMPT`): v1 serves again only
        after this rollback's own steps (a switch after a rolled-back cutover)."""
        now = self.clock()

        def decide(current, view):
            self._in(current, "switched")
            self._approved(view, current, approval_id, "rollback")
            _no_release_exclusion(view)
            if now - _parse(current["admissionOpenedAt"]) > dt.timedelta(
                seconds=current["rollbackWindowSeconds"]
            ):
                raise _refused("rollback-window-closed")
            return {"state": "rolling-back", **ROLLBACK_ATTEMPT}

        return self._move(decide, approval=str(approval_id))

    def rollback_v1_serving(self, *, applied: Mapping, receipts: Iterable[dict] = ()) -> dict:
        """v1 answers at the public address, after v2's lifecycle outcomes reached it and
        every v1 session ended (`applied` from the v1 lifecycle operation)."""
        now = utc_text(self.clock())

        def decide(current, view):
            self._in(current, "rolling-back")
            if "rollbackV1ServingAt" in current:
                return None
            if not applied.get("outcomesApplied") or not applied.get("sessionsEnded"):
                raise _refused("v1-lifecycle-not-applied")
            return {"rollbackV1ServingAt": now}

        return self._move(decide, receipts=receipts)

    def rollback_returned_to_rehearsal(self) -> dict:
        """At v1's serving, the profile is back in rehearsal on the rollback's new, empty
        rehearsal database (your decision of 2026-10-24, "Create a fresh rehearsal
        database"): the accepted dry run is cleared, because opening removed its
        database, so the soak starts again only after a dry run accepted after the
        rollback (the CutoverRecord rows for `rolled-back`)."""

        def decide(current, view):
            self._in(current, "rolling-back")
            if "rollbackV1ServingAt" not in current:
                raise _refused("v1-not-serving")
            return {"acceptedDryRunId": None} if "acceptedDryRunId" in current else None

        return self._move(decide)

    def rollback_copy_pending(self) -> dict:
        """The stopped production database's copy cannot be completed: the wait, with its
        incident on operations.cutover taken over or opened (BR3.7)."""
        current = self.require()
        self._in(current, "rolling-back")
        if "rollbackV1ServingAt" not in current:
            raise _refused("v1-not-serving")
        incident = self.incidents.take_over_cutover(
            "rollback-copy-pending", correlation=f"cutover:{current['cutoverId']}:copy-pending")
        now = utc_text(self.clock())

        def decide(current, view):
            self._in(current, "rolling-back")
            return {"rollbackCopyPendingSince": current.get("rollbackCopyPendingSince", now),
                    "rollbackCopyIncidentId": incident["incidentId"]}

        return self._move(decide)

    def replacement_volume(self, approval_id) -> dict:
        """Your decision retired a volume lost for good: the copy may be written to its
        replacement (BR4.10), which passed the volume check at its retirement."""

        def decide(current, view):
            self._in(current, "rolling-back")
            if "rollbackCopyPendingSince" not in current:
                raise _refused("rollback-copy-not-pending")
            approval = view.get("maintainer-approval", str(approval_id))
            if approval is None or approval["step"] != "backup-volume-retirement" or (
                approval["decision"] != "approved"
            ):
                raise OperationsError("FORBIDDEN", current={"reasonKey": "decision-required"})
            return None

        return self._move(decide, approval=str(approval_id))

    def rolled_back(self, *, receipts: Iterable[dict] = (), waiver=None) -> dict:
        """rolling-back → rolled-back: the copy's checksum is recorded, or your decision
        waived it; the production database is then recreated empty."""

        def decide(current, view):
            self._in(current, "rolling-back")
            if "rollbackV1ServingAt" not in current:
                raise _refused("v1-not-serving")
            if waiver is not None:
                if "rollbackCopyPendingSince" not in current:
                    raise _refused("rollback-copy-not-pending")
                self._approved(view, current, waiver, "rollback-copy-waiver")
            return {"state": "rolled-back", "rollbackCopyPendingSince": None}

        return self._move(decide, receipts=receipts,
                          approval=None if waiver is None else str(waiver))

    def cancel_rollback(self, approval_id, *, receipts: Iterable[dict] = ()) -> dict:
        """rolling-back → switched on your decision, only before v1 serves; the window
        keeps counting from admission opening."""

        def decide(current, view):
            self._in(current, "rolling-back")
            self._approved(view, current, approval_id, "rollback-cancel")
            if "rollbackV1ServingAt" in current:
                raise _refused("v1-already-serving")
            return {"state": "switched"}

        return self._move(decide, receipts=receipts, approval=str(approval_id))

    # --- settlement (BR9.8) ------------------------------------------------------------

    def settle(self, approval_id) -> dict:
        """switched → settled on your decision after the window, under the inventory's
        rules measured from the switch's check (`switchCheckedAt`, L1-21); the move's
        instant is recorded as `settledAt`, from which the final snapshot's 30 days count
        (L1-3)."""
        now = self.clock()

        def decide(current, view):
            self._in(current, "switched")
            self._approved(view, current, approval_id, "settlement")
            if now - _parse(current["admissionOpenedAt"]) <= dt.timedelta(
                seconds=current["rollbackWindowSeconds"]
            ):
                raise _refused("rollback-window-open")
            inventory = view.get("consumer-inventory", current.get("consumerInventoryId"))
            checked = current.get("switchCheckedAt") or current.get("switchStartedAt")
            gap = inventory_gap(inventory, policy=self.policy,
                                switch_at=_parse(checked) if checked else now)
            if gap == "inventory-incomplete":
                raise _refused("inventory-not-ready")
            if gap is not None:
                raise _refused(gap)
            return {"state": "settled", "settledAt": utc_text(now)}

        return self._move(decide, approval=str(approval_id))

    def inventory_taken(self, inventory_id) -> dict:
        identity = str(UUID(str(inventory_id)))

        def decide(current, view):
            if view.get("consumer-inventory", identity) is None:
                raise OperationsError("NOT_FOUND")
            return {"consumerInventoryId": identity}

        return self._move(decide)


def inventory_ready(inventory: Mapping | None) -> bool:
    """Complete, with every consumer's disposition approved (BR9.11)."""
    if inventory is None or not inventory.get("complete"):
        return False
    return all("disposition" in item and "approvalId" in item
               for item in inventory["consumers"])


def inventory_gap(inventory: Mapping | None, *, policy, switch_at: dt.datetime) -> str | None:
    """The first rule the consumer inventory breaks for a switch checked at `switch_at`,
    or None (U8 plan Step 70(b); BR9.11, reliability-design § 12, your decision of
    2026-11-01, L1-21): `inventory-incomplete` until it is complete with every
    disposition approved; `inventory-window-short` when it covers less than the
    consumer window (14 days); `inventory-not-recent` when it ends more than
    `inventory_recency_seconds` (24 hours) before the switch's check, or after it.
    Missing dispositions keep their own key, so a stale or short inventory is never
    read as undecided consumers."""
    if not inventory_ready(inventory):
        return "inventory-incomplete"
    start, end = _parse(inventory["observedFrom"]), _parse(inventory["observedUntil"])
    if (end - start).total_seconds() < policy.consumer_window_seconds:
        return "inventory-window-short"
    if end < switch_at - dt.timedelta(seconds=policy.inventory_recency_seconds) or (
        end > switch_at
    ):
        return "inventory-not-recent"
    return None
