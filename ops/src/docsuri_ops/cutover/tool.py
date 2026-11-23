"""The cutover commands (U8 plan Step 33; Workflows 12–14, BR9.1–BR9.17, R8).

`docsuri-ops cutover status | begin | check | start | open | abort | rollback |
cancel-rollback | retry-copy | waive-copy | settle | rehearse-restart | v1-stores-deleted |
decide <kind> | provider-previews | provider-decision | provider-failed`, run by the
operator in person. Each
word runs its bound PlatformControl operations in order (`Operator.execute`: A6's
preconditions, the receipt bound before the effect, one effect through the driver the
profile names), adds each receipt to the CutoverRecord, and shows each step against the
time left: the switch's 4-hour bound from v1's stop while switching, the rollback window
while rolling back (R6: a step is never cut off).

- `start`: on your decision (`switch-start`, whose shown subject names the final
  snapshot's offset, 120 days from the switch's check, with the accepted dry run's
  durations and the soak's 95th percentiles), with BR9.2 holding at one check instant
  (`preconditions.missing`, `switchCheckedAt`; L1-3, L1-21, L1-59): maintenance,
  v1 stopped (the bound starts), the rehearsal v2 stopped, then the final run to its
  report. Run again after your decision on the final report: the profile goes live with
  admission maintainer-only, v2 starts on the production database, the first live
  backup must pass, and the public address routes to v2 for the maintainer-only window.
  A failed or declined step, or the bound passing, aborts.
- `open`: your opening decision, whose subject names any provider it accepts
  unavailable and v1 stores' offset (90 days from admission's opening, L1-3); with
  BR9.4's gates holding, admission
  opens. Right after, v1's stores are recorded as a retained copy, the profile's
  rehearsal database is cleared, the rehearsal databases are removed, and only then are
  their sets disposed (profile, database, sets), each set once the removal of its own
  database has applied (review finding, Major, R-02): a removal that failed, is still
  within its lease or has an unknown outcome leaves its database pending and its sets
  waiting with that reason. A disposal step that fails answers why, and `open` run
  again on the switched record re-runs that disposal, database, then sets.
- `abort`: v1 serves again before anything of v2's is removed (BR9.5).
- `rollback`, `cancel-rollback`, `retry-copy`, `waive-copy`: BR9.7 and BR9.13. At v1's
  serving the rollback returns to rehearsal on a new, empty rehearsal database (named,
  recorded as a retained copy, created, then set), clears the accepted dry run and only
  then copies; a retry runs that step's missing parts first (your decision of
  2026-10-24, "Create a fresh rehearsal database"). A rollback is never blocked by the
  database count (your decision of 2026-10-25, "Never block a rollback"): its start is
  never refused for NFR8.15, and its serving step first removes the rehearsal databases
  opening left pending (only copies recorded at or before admission opened); their sets
  are disposed once the rollback has ended, since A6 refuses a disposal while it runs. A
  removal that fails leaves v1 serving, and `rollback` run again retries it, each run
  one new attempt under keys of its own, so no number of failures exhausts it. A
  `retry-copy` onto a replacement volume records your retirement decision on the
  record, so the later runs key the serving step's profile changes under that decision;
  each settles the earlier runs' keys first (`_rollback_profile`; review finding, Minor,
  R-04): an applied change is taken as done, and a new effect runs only where every
  earlier run left nothing applied.
- `migration accept` (`after_dry_run`): the accepted run's database set and v2 restarted
  on it, then the rehearsal database the profile named before removed and its sets
  disposed (profile, database, sets). A move that stopped is run again by `check`. After
  a rollback the database is set but v2 stays stopped; its three roles start, with the
  readiness wait, when the soak starts (your decision of 2026-10-25, "Follow the
  design").
- NFR8.15 at each creation: a dry run's start and `begin` are refused with
  `rehearsal-database-limit` before anything is written while two rehearsal databases
  are open, counted from the ledger's open retained copies; the rollback's creation is
  counted only after the databases opening left pending are removed, so it fits.
- `settle` `{approvalId, subject}`: your decision after the window, under the
  inventory's rules measured from the switch's check (BR9.8, L1-21); the final snapshot
  is then re-dated to 30 days after the settlement, or keeps an earlier date (L1-3).
- `date-final-snapshot` `{approvalId, subject}`: after an abort, your disposal-date
  decision dates the aborted attempt's final snapshot 30 days after the abort; the next
  start waits for it (L1-66).
- `rehearse-restart`: v1's restart from its fixed checkout, rehearsed on your decision
  (BR9.16), v1's local health waited for and v1's own restart seconds recorded (NFR8.6,
  L1-59). The abort and the rollback wait for v1's health the same way.
- `v1-stores-deleted` `{copyId?}`: after you have deleted v1's stores by hand at the
  approved date, a read-only check that each location is gone, then the deletion recorded
  on the v1-stores RetainedCopy (`disposedAt`, the in-person receipt and the check's
  evidence); refused before the date, while any location remains, and unless in person
  (the person's decision of 2026-10-22: "Record it after manual deletion").
- `status`: the record, the time left, the soak's verdict and what BR9.2 still misses;
  `none` before any record exists.
- `begin` (your decision of 2026-10-24): the CutoverRecord for the installed release's
  tag, the profile's rehearsal database recorded, created and set, and v2 restarted on
  it, readiness waited for (up to 10 minutes, polled every 5 s). A begin that stopped is
  run again with `begin`, on the same record and name.
- Every word run again after a failed step retries that step: a succeeded step replays
  its receipt by its key, and one that left nothing applied runs again under its next
  retry key (a failed receipt; an operation interrupted after its receipt was bound,
  promoted once its lease passed and reconciled not applied from its target; an unknown
  outcome reconciled not applied). An interrupted operation still within its lease
  answers `effect-in-progress` (`u8_protocols.execute_settled`).
- `check`: the soak's evaluation, then rehearsing ⇄ ready-to-switch, naming what is
  missing. The switch's start, opening (which now restarts v2 on the opened profile and
  requires readiness), and a dry run's acceptance (`migration accept`) wait for
  readiness the same way.
- `decide <kind>` `{decision?, confirm?, …}`: your decision for the command that takes it,
  in two calls (shown, then confirmed with the shown digest), recorded through
  `platform.decision.record` (`cutover.decide`; the person's decision of 2026-10-24, "Add
  decision commands"). `start` run again with `{approvalId}` of a `final-report`
  decision applies it to the final run.
- `provider-previews` `{provider, digest?}`, `provider-decision` `{approvalId, subject}`
  and `provider-failed` `{provider}` (U8 plan Step 106(d), CP-3; BR7.3, BR7.8): a held
  outward provider's previews held since the switch's check, or one's exact content;
  your `provider-sign-in` or `provider-first-effect` decision applied with the subject it
  was shown with; a sign-in provider whose real sign-in failed recorded unavailable,
  only while switching. The first two run while the cutover is switching, switched or
  settled. Each runs a production tool word in person (`platform.provider_word`), as
  the service account, since the previews and the profile's live settings are that
  account's; none writes the CutoverRecord. The composed realm wires none, and each is
  refused `provider-words-unwired`.

The composed realm's wiring (`realm_platform`) uses its operator, store and driver; the
parts that need the synthetic v1 (its fixed checkout and its account code) or the final
migration run come with their own steps (Step 43's synthetic v1, Step 31's migration
tool), and the production wiring with the production environment tool (Step 37).
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

from backend.modules.operations.cutover import Cutover, subject_digest
from backend.modules.operations.errors import OperationsError
from backend.modules.operations.ledger import utc_text
from backend.modules.operations.migration_records import MigrationRuns
from backend.modules.operations.retained_copies import RetainedCopies, receipt_facts

from .preconditions import SwitchEvidence, missing

WORDS = ("status", "begin", "check", "start", "open", "abort", "rollback", "cancel-rollback",
         "retry-copy", "waive-copy", "settle", "rehearse-restart", "v1-stores-deleted",
         "decide", "date-final-snapshot",
         # U8 plan Step 106(d), CP-3: the providers' window words.
         "provider-previews", "provider-decision", "provider-failed")
MAX_INPUT = 64 * 1024
STEP_SECONDS = 600  # a step outside the switch and the rollback: shown against 10 minutes
# Readiness waits (your decision of 2026-10-24): after `start-v2` at the switch, after
# opening's restart, after `cutover begin` and after `migration accept`, readiness is polled
# every 5 s for up to 10 minutes, as the release command's own wait does.
READY_BOUND_SECONDS = 600
READY_POLL_SECONDS = 5
READY_POLLS = READY_BOUND_SECONDS // READY_POLL_SECONDS
# A step whose earlier attempt failed is run again under the next of these keys, so a
# word run again retries it instead of replaying the failure (`CutoverTool._effect`).
STEP_RETRIES = 8
# The unsettled reasons a left database's removal surfaces as they are, so the operator
# sees why the rollback waits; any other failure is `rehearsal-database-removal-failed`.
SURFACED_REMOVAL_REASONS = frozenset({"effect-in-progress", "effect-outcome-unknown"})
# The profile's bound operations, by the field each changes (`_profile`).
PROFILE_OPERATIONS = {"mode": "platform.profile.mode", "admission": "platform.profile.admission",
                      "rehearsalDatabase": "platform.profile.rehearsal-database"}
V1_STATES ={"erase": ("DEACTIVATED", "DELETED", None), "withdraw": ("DEACTIVATED",),
             "reactivate": ("ACTIVE",)}


class StepFailed(Exception):
    """A bound step failed with a fixed reason key."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _direct(name: str, bound: float, work: Callable[[], object]) -> object:
    return work()


def _parse(text: str) -> dt.datetime:
    return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))


@dataclass
class CutoverPlatform:
    """What the cutover commands need from the platform side."""

    operator: object
    production: str
    v1_labels: tuple[str, ...]
    v2_labels: tuple[str, ...]
    v2_ready: Callable[[], bool]
    v1_ready: Callable[[], bool]
    public: Callable[[str], bool]
    evidence: SwitchEvidence
    evidence_folder: Path
    capabilities_missing: Callable[[], list[str]] = field(default=lambda: [])
    final_run: Callable[[str, dt.datetime], dict] | None = None
    # Your `final-report` decision applied to the final run (MigrationTool.decide).
    final_decide: Callable[[str, str], dict] | None = None
    fail_final: Callable[[str, str], dict] | None = None
    first_backup: Callable[[str], dict] | None = None
    agent: Callable[..., dict] | None = None
    lifecycle_outcomes: Callable[[dt.datetime], list[dict]] | None = None
    v1_accounts: Callable[[], list[str]] | None = None
    v1_states: Callable[[list[str]], dict[str, str | None]] | None = None
    v2_writes: Callable[[dt.datetime], dict[str, int]] | None = None
    v1_stores: tuple[str, ...] = ("v1-stores/database", "v1-stores/search-index",
                                  "v1-stores/objects", "v1-stores/backups")
    activation: object | None = None
    rehearsal_copy: Callable[[], str | None] = field(default=lambda: None)
    steps: Callable[[str, float, Callable[[], object]], object] = _direct
    # Whether one of v1's stores' locations is still there, read-only (lstat).
    v1_store_present: Callable[[str], bool] | None = None
    # `cutover begin` (your decision of 2026-10-24): the installed release's tag, the
    # rehearsal database the profile names, and its creation (`create-disposable`, a
    # template copy with production's CONNECT grants).
    release_tag: Callable[[], str | None] = field(default=lambda: None)
    named_rehearsal: Callable[[], str | None] = field(default=lambda: None)
    create_rehearsal: Callable[[str], object] | None = None
    # The readiness waits' sleep (injected in tests, so no real wait runs).
    sleep: Callable[[float], None] = time.sleep
    # v2's stop records with their expiry, shown by `status` while the record is
    # `rolled-back` (the person's decision of 2026-10-25, "Add an in-person stop
    # command"; `service_words.stop_expiries`).
    stop_records: Callable[[], list[dict]] = field(default=lambda: [])
    # The linked release's tag when it was installed while v2 was kept stopped and has
    # not been probed yet (the person's decision of 2026-10-25, "Probe it when the soak
    # starts"), else None. Its probe journey, and § 6's switch back when it fails, need
    # the release command's root custody of the links, so the soak then starts only
    # through `docsuri-release verify` with `{"tag"}` on standard input
    # (`ReleaseInstall._move_cutover`).
    release_unprobed: Callable[[], str | None] = field(default=lambda: None)
    # v2's labels a stop left stopped, each with the receipt its stop record cites
    # (`service_words.stopped_v2_labels`): the soak's start runs a new start for a label
    # a later stop superseded (the review's fix of 2026-10-26).
    stopped_labels: Callable[[], dict[str, str]] = field(default=lambda: {})
    # `release-run-active` while a release command runs, read from its run marker
    # (`release.release_run_active`: a root-written file read without a password and
    # without locking anything; the lock itself is root-only), else None (your decision
    # of 2026-10-26, "Check the release run lock"): the words that switch, roll back or
    # restart v2, the soak's start and `cutover check`'s set retry refuse meanwhile.
    release_run: Callable[[], str | None] = field(default=lambda: None)
    # A v1-final-snapshot copy's three part files (`Snapshot.verified_parts` over the
    # migration's evidence folder), for the re-date's `set-date` (U8 plan Step 70(a)).
    snapshot_parts: Callable[[str], dict] | None = None
    # The soak's latency lines over [from, until] (`request_context.window_summaries`),
    # shown with your switch-start decision (U8 plan Step 70(d), L1-59).
    soak_latency: Callable[[dt.datetime, dt.datetime], dict] | None = None
    # The service side of the three provider words (U8 plan Step 106(d), CP-3):
    # production's runs the production tool's words in person, the tests' stage runs
    # `provider_activation.provider_word` over its own ledger; None refuses them
    # `provider-words-unwired`.
    provider_word: Callable[[str, dict], dict] | None = None


class CutoverTool:
    def __init__(self, ledger, policy, platform: CutoverPlatform, *,
                 clock: Callable[[], dt.datetime]):
        self.ledger, self.policy, self.platform, self.clock = ledger, policy, platform, clock
        self.machine = Cutover(ledger, policy, clock=clock)
        self.incidents = self.machine.incidents
        self.copies = RetainedCopies(ledger, policy, clock=clock)
        self.runs = MigrationRuns(ledger, clock=clock)

    # --- the shared path ------------------------------------------------------------------

    def _attempt(self, record: dict) -> str:
        """The current attempt's identity: the latest decision on the record, so each
        switch, abort or rollback binds its own receipts and a re-run replays them."""
        return record["approvals"][-1] if record["approvals"] else record["cutoverId"]

    def _key(self, record: dict, step: str) -> str:
        """The step's idempotency key, within U7's 128 characters: the digest of the
        record, the attempt and the step, so the same step of the same attempt replays its
        receipt and nothing else does."""
        identity = f"{record['cutoverId']}:{self._attempt(record)}:{step}"
        return "cutover:" + hashlib.sha256(identity.encode()).hexdigest()

    def _bound(self, record: dict) -> float:
        """The time left the step is shown against: the switch's bound from v1's stop,
        the rollback window, or a plain step bound."""
        now = self.clock()
        if record["state"] == "switching" and "switchStartedAt" in record:
            end = _parse(record["switchStartedAt"]) + dt.timedelta(
                seconds=record["switchTimeBoundSeconds"])
            return max(1.0, (end - now).total_seconds())
        if record["state"] == "rolling-back" and "admissionOpenedAt" in record:
            end = _parse(record["admissionOpenedAt"]) + dt.timedelta(
                seconds=record["rollbackWindowSeconds"])
            return max(1.0, (end - now).total_seconds())
        return float(STEP_SECONDS)

    def _effect(self, operation: str, target: str, inputs: dict, *, key: str,
                recheck: Callable[[], str | None] | None = None,
                replayed: list[bool] | None = None) -> dict:
        """One bound operation run to a settled outcome (`execute_settled`, BR9.10).

        A succeeded step replays its receipt by its key, so a word run again runs only
        what is missing. A step an earlier attempt left with nothing applied (its receipt
        failed, its operation interrupted and reconciled not applied once its lease
        passed, or its unknown outcome reconciled not applied) runs again under the next
        retry key, so running the word again is that step's retry; a failure in this run
        fails the step at once, and an interrupted operation still within its lease
        answers `effect-in-progress`. `recheck` is asked again once the receipt is bound
        (`Operator.execute`). `replayed`, when given, gains whether the receipt was a
        replay of an earlier run's (U8 plan Step 70(e))."""
        from docsuri_ops.platform_control.errors import ControlError
        from docsuri_ops.u8_platform.u8_protocols import (
            EffectUnsettled,
            PreconditionRefused,
            execute_settled,
        )

        options = {} if recheck is None else {"recheck": recheck}
        try:
            receipt = execute_settled(self.platform.operator, operation, target, inputs,
                                      key=key, retries=STEP_RETRIES, **options)
        except PreconditionRefused as refused:
            raise StepFailed(refused.reason) from None
        except ControlError as error:
            raise StepFailed(error.code.lower().replace("_", "-")) from None
        except EffectUnsettled as unsettled:
            raise StepFailed(unsettled.reason or (
                f"{operation.removeprefix('platform.').replace('.', '-')}-failed")) from None
        if replayed is not None:
            replayed.append(bool(receipt.get("replayed")))
        return receipt_facts(receipt, now=self.clock())

    def _settled_earlier(self, operation: str, target: str, inputs: dict, *,
                         keys: Iterable[str]) -> dict | None:
        """Earlier runs' keys for this step, settled before this run opens its own
        (`u8_protocols.settle_earlier`; review finding, Major, R12): the receipt facts of
        the first that applied (the step is done), None when every one left nothing
        applied or never ran; `effect-in-progress` while one is within its lease and
        `effect-outcome-unknown` while one's outcome cannot be proven, so nothing runs
        beside it and an unknown receipt is reconciled again on every run."""
        from docsuri_ops.platform_control.errors import ControlError
        from docsuri_ops.u8_platform.u8_protocols import (
            EffectUnsettled,
            PreconditionRefused,
            settle_earlier,
        )

        for key in keys:
            try:
                receipt = settle_earlier(self.platform.operator, operation, target, inputs,
                                         key=key)
            except PreconditionRefused as refused:
                raise StepFailed(refused.reason) from None
            except ControlError as error:
                raise StepFailed(error.code.lower().replace("_", "-")) from None
            except EffectUnsettled as unsettled:
                raise StepFailed(unsettled.reason or "effect-outcome-unknown") from None
            if receipt is not None:
                return receipt_facts(receipt, now=self.clock())
        return None

    def _step(self, record: dict, name: str, work: Callable[[], object]) -> object:
        return self.platform.steps(name, self._bound(record), work)

    def _record(self, receipts: Iterable[dict]) -> dict:
        return self.machine.record_receipts(list(receipts))

    def _route(self, record: dict, origin: str, step: str) -> dict:
        facts = self._effect("platform.tunnel.route", "tunnel", {"origin": origin},
                             key=self._key(record, step))
        return self._record([facts])

    def _services(self, record: dict, labels: Iterable[str], action: str, step: str) -> list:
        receipts = [self._effect("platform.service.control", label,
                                 {"label": label, "action": action},
                                 key=self._key(record, f"{step}:{label}"))
                    for label in labels]
        self._record(receipts)
        return receipts

    def _start_superseded(self, record: dict, step: str) -> list:
        """The soak's start of v2's three roles under its keys, so `cutover check` run
        again replays what succeeded. A label a stop left stopped (its stop record is
        there: a start removes it) starts under a key of that stop's own, so a later stop
        (`service stop`, run after a start that was not ready) is followed by a new start
        rather than a replay of the start it superseded (the review's fix of 2026-10-26)."""
        stopped = self.platform.stopped_labels()
        receipts = []
        for label in self.platform.v2_labels:
            inputs = {"label": label, "action": "start"}
            key = self._key(record, f"{step}:{label}")
            if label in stopped and self._settled_earlier(
                    "platform.service.control", label, inputs, keys=[key]) is not None:
                # The start under this key succeeded and a later stop superseded it.
                key = self._key(record, f"{step}:{label}:after:{stopped[label]}")
            # Checked again once each start's receipt is bound, right before it runs: the
            # release command's run marker sees an install that began after
            # `soak_report`'s check (review finding, Minor, R13; your decision of
            # 2026-10-26, "Check the release run lock"), which a re-read of a cached
            # ledger copy would not.
            receipts.append(self._effect("platform.service.control", label, inputs, key=key,
                                         recheck=self._release_exclusion))
        self._record(receipts)
        return receipts

    def _release_exclusion(self) -> str | None:
        """The install or release rollback holding the live exclusion (the ledger), else
        the release command running (`platform.release_run`: its run marker, read without
        a password and without locking anything, right where a word acts), else None."""
        from backend.modules.operations.release_records import release_blocker

        blocker = release_blocker(self.ledger)
        if blocker is not None:
            return blocker
        run_lock = getattr(self.platform, "release_run", None)
        return None if run_lock is None else run_lock()

    def _refuse_during_release(self) -> None:
        """The exclusion holds both ways (the review's fix of 2026-10-26): no cutover word
        switches, rolls back or restarts v2 while an install or a release rollback holds
        it."""
        blocker = self._release_exclusion()
        if blocker is not None:
            raise OperationsError("CONFLICT", current={"reasonKey": blocker})

    def _profile(self, record: dict, field_name: str, value, step: str, **extra) -> dict:
        facts = self._effect(PROFILE_OPERATIONS[field_name], "profile",
                             {"field": field_name, "value": value, **extra},
                             key=self._key(record, step))
        return self._record([facts])

    def _require(self, part, name: str):
        if part is None:
            raise OperationsError("DEPENDENCY_UNAVAILABLE", current={"reasonKey": name})
        return part

    def _rehearsal_limit(self, names) -> str | None:
        """NFR8.15 at a creation (`cutover begin`; the rollback's, after `_remove_left`): a
        new rehearsal database only while fewer than two are open, counted from the
        ledger's open retained copies; `rehearsal-database-limit` otherwise, asked before
        anything is written."""
        from docsuri_ops.u8_platform.u8_protocols import database_limit_reason

        return database_limit_reason("rehearsal", self.ledger, names)

    def _admit_rehearsal(self, names) -> None:
        reason = self._rehearsal_limit(names)
        if reason is not None:
            raise OperationsError("CONFLICT", current={"reasonKey": reason})

    def _create_rehearsal(self, record: dict, copy: dict) -> str:
        """The recorded copy's rehearsal database created once: the copy's completion
        marks the creation, so a retry after a confirmed creation creates nothing. Any
        failure is a step failure with a fixed reason (production's `Refused` keeps its
        own key), so the word answers and its retry creates it again: the creation is
        idempotent for a database this copy recorded and nothing uses yet
        (`create-disposable`, `RealmDatabases.create_rehearsal`)."""
        name = copy["locations"][0].removeprefix("database/")
        if "completedAt" in copy:
            return name
        create = self.platform.create_rehearsal
        if create is None:
            raise StepFailed("rehearsal-creation-unwired")
        try:
            self._step(record, "create-rehearsal", lambda: create(name))
        except StepFailed:
            raise
        except Exception as error:  # noqa: BLE001 - any failure: the retry creates it
            reason = getattr(error, "reason", None)
            fixed = isinstance(reason, str) and reason.replace("-", "").isalnum()
            raise StepFailed(reason if fixed else "rehearsal-creation-failed") from None
        self.copies.complete(copy["copyId"])
        return name

    def _subject(self, approval_id, subject: dict, step: str) -> dict:
        approval = self.ledger.get("maintainer-approval", str(approval_id))
        if approval is None or approval["step"] != step:
            raise OperationsError("FORBIDDEN", current={"reasonKey": "decision-required"})
        if approval["subjectDigest"] != subject_digest(subject):
            raise OperationsError("CONFLICT", current={"reasonKey": "decision-subject-differs"})
        return approval

    def _approval_first(self, record: dict, approval_id, step: str) -> None:
        """Your decision for this record's step, checked before any effect runs (the
        machine checks it again when it moves): absent, another step's, another
        record's or declined, the command is refused."""
        approval = None if approval_id is None else self.ledger.get("maintainer-approval",
                                                                    str(approval_id))
        if approval is None or approval["step"] != step or (
            approval["subjectRef"] != record["cutoverId"]
        ) or approval["decision"] != "approved":
            raise OperationsError("FORBIDDEN", current={"reasonKey": "decision-required"})

    def _rule(self, subject: dict, name: str, attribute: str) -> int:
        """The offset a decided date takes, as the subject names it: refused before any
        effect when it differs from the policy's (`decided-rule-differs`; U8 plan Step
        70(a), L1-3)."""
        expected = getattr(self.policy, attribute)
        value = subject.get(name)
        if type(value) is not int or value != expected:
            raise OperationsError("INVALID_INPUT", current={"reasonKey": "decided-rule-differs",
                                                            "rule": name})
        return expected

    # --- status ---------------------------------------------------------------------------

    def missing(self, now: dt.datetime | None = None) -> list[str]:
        """BR9.2 at `now` (the start's one check instant), or at this call's own clock."""
        record = self.machine.require()
        return missing(self.ledger, record, self.platform.evidence, self.policy,
                       now or self.clock())

    def awaiting_final_snapshot(self, record: dict) -> dict:
        """`{"finalSnapshotAwaitingDate": <copyId>}` while an aborted attempt's final
        snapshot waits for your disposal-date decision (L1-66), else nothing."""
        from .preconditions import awaiting_final_snapshot

        copy_id = awaiting_final_snapshot(self.ledger, record, self.policy)
        return {} if copy_id is None else {"finalSnapshotAwaitingDate": copy_id}

    def status(self) -> dict:
        from backend.modules.operations.cutover import soak_verdict

        record = self.machine.current()
        if record is None:
            # No cutover has begun yet (`cutover begin`).
            return {"state": "none"}
        clean, reasons = soak_verdict(self.ledger, record, self.clock())
        value = {"state": record["state"], "releaseTag": record["releaseTag"],
                 "timeLeftSeconds": round(self._bound(record)), "soakClean": clean,
                 "soakReasons": reasons, "boundPassed": self.machine.bound_passed()}
        if record["state"] in ("rehearsing", "ready-to-switch"):
            value["missing"] = self.missing()
        value.update(self.awaiting_final_snapshot(record))
        if record["state"] == "rolled-back":
            # While a rollback keeps v2 stopped, its stop records lapse after 14 days;
            # `service stop` renews them in person.
            value["v2StopRecords"] = self.platform.stop_records()
        return value

    def check(self) -> dict:
        """`cutover check`: the soak's evaluation, then BR9.2 again, moving the record
        between rehearsing and ready-to-switch and naming what is missing; before the
        soak (preparing) it only names what is missing. First, an accepted dry run's move
        that stopped is run again (`resume_dry_run`)."""
        moved = self.resume_dry_run()
        extra = {} if moved is None else {"dryRunMove": moved}
        record = self.machine.require()
        left = self.retry_left_sets(record)
        if left:
            extra["leftSets"] = left
        if record["state"] == "rolled-back" and moved is None:
            # After a rollback, a soak whose v2 start stopped is started again here.
            soak = self.soak_report()
            if soak["soak"] is not None or "v2Start" in soak:
                extra["soak"] = soak
            record = self.machine.require()
        if record["state"] not in ("rehearsing", "ready-to-switch"):
            return {"state": record["state"], "missing": self.missing(), **extra}
        self.machine.evaluate_soak()
        gaps = self.missing()
        record = self.machine.check_ready(gaps)
        return {"state": record["state"], "missing": gaps,
                **self.awaiting_final_snapshot(record), **extra}

    # --- readiness, v2's restart and the begin (your decision of 2026-10-24) --------------

    def wait_ready(self, *, probe: Callable[[], bool] | None = None) -> dict:
        """v2's readiness (or `probe`'s answer) polled every 5 s for up to 10 minutes (on
        the injected clock and sleep); a poll count bounds it too, so a clock that stands
        still never waits for ever. The wait only reads and sleeps: it sends no effect."""
        probe = probe or self.platform.v2_ready
        started = self.clock()
        for poll in range(READY_POLLS + 1):
            if probe():
                return {"ready": True,
                        "waitedSeconds": round((self.clock() - started).total_seconds())}
            if poll == READY_POLLS or (
                    self.clock() - started).total_seconds() >= READY_BOUND_SECONDS:
                break
            self.platform.sleep(READY_POLL_SECONDS)
        return {"ready": False,
                "waitedSeconds": round((self.clock() - started).total_seconds())}

    def wait_v1_ready(self) -> dict:
        """v1's local health waited for as v2's readiness is (U8 plan Step 70(e)-(f),
        L1-59): after the restart rehearsal's, the abort's and the rollback's v1 starts.
        It never starts v1 again."""
        return self.wait_ready(probe=self.platform.v1_ready)

    def restart_v2(self, record: dict, step: str) -> list:
        """v2's three roles restarted through `platform.service.control`: each stopped,
        then each started, every effect with its receipt on the record."""
        labels = self.platform.v2_labels
        receipts = self._services(record, labels, "stop", f"{step}:restart-stop")
        receipts += self._services(record, labels, "start", f"{step}:restart-start")
        return receipts

    def begin(self) -> dict:
        """`cutover begin`, in person (BR9.1): the CutoverRecord for the installed
        release's tag; the rehearsal database the profile names recorded as a retained
        copy and created (a template copy with production's CONNECT grants); the profile
        set to it through `platform.profile.rehearsal-database`, so the ledger knows the
        database v2 runs on; v2's three roles restarted, and readiness waited for.

        A begin whose steps did not all complete is run again with `begin`: while the
        record is still preparing, its rehearsal database's copy is open and the begin's
        completion is not recorded, the same name is created if its creation was not
        confirmed, and the profile and restart steps run again under their keys (a step
        that succeeded replays its receipt, a failed one runs again). Once the begin
        completed, `begin` is refused (`cutover-record-exists`)."""
        self._refuse_during_release()
        tag = self.platform.release_tag()
        if not tag:
            raise OperationsError("CONFLICT", current={"reasonKey": "release-not-installed"})
        self._require(self.platform.create_rehearsal, "rehearsal-creation-unwired")
        record, copy = self._begun_or_new(tag)
        name = copy["locations"][0].removeprefix("database/")
        # The begin's keys are the record's own, whatever decision came after it (a
        # restart rehearsal may be recorded while preparing).
        keyed = self._keyed(record, None)
        try:
            self._create_rehearsal(keyed, copy)
            record = self._profile(keyed, "rehearsalDatabase", name, "begin-rehearsal-database")
            self._step(keyed, "restart-v2", lambda: self.restart_v2(keyed, "begin"))
        except StepFailed as failure:
            return {"state": record["state"], "cutoverId": record["cutoverId"],
                    "rehearsalDatabase": name, "copyId": copy["copyId"],
                    "reason": failure.reason, "offered": ["begin"]}
        self._write_evidence(self._begin_evidence(record), {
            "cutoverId": record["cutoverId"], "rehearsalDatabase": name,
            "copyId": copy["copyId"], "begunAt": utc_text(self.clock())})
        waited = self.wait_ready()
        return {"state": record["state"], "cutoverId": record["cutoverId"],
                "releaseTag": tag, "rehearsalDatabase": name, "copyId": copy["copyId"],
                **waited}

    @staticmethod
    def _begin_evidence(record: dict) -> str:
        return f"begin-{record['cutoverId']}.json"

    def _begun_or_new(self, tag: str) -> tuple[dict, dict]:
        """The CutoverRecord and its first rehearsal database's copy: new ones, or those
        of a begin whose steps did not all complete (its retry)."""
        record = self.machine.current()
        if record is None:
            name = self.platform.named_rehearsal()
            # The instance's own naming, read from the operator's facts (the same names
            # its `platform.profile.rehearsal-database` protocol checks), before anything
            # is written.
            names = self.platform.operator.facts().names
            if not isinstance(name, str) or names.kind_of(name) != "rehearsal":
                raise OperationsError("CONFLICT",
                                      current={"reasonKey": "rehearsal-database-unnamed"})
            self._admit_rehearsal(names)
            record = self.machine.begin(tag)
            copy = self.copies.record("rehearsal-database", f"cutover:{record['cutoverId']}",
                                      [f"database/{name}"])
            return record, copy
        copy = next((item for item in self.copies.undisposed("rehearsal-database")
                     if item["sourceRef"] == f"cutover:{record['cutoverId']}"), None)
        unfinished = (record["state"] == "preparing" and copy is not None
                      and "acceptedDryRunId" not in record
                      and self._read_evidence(self._begin_evidence(record)) is None)
        if not unfinished:
            raise OperationsError("CONFLICT", current={"reasonKey": "cutover-record-exists"})
        return record, copy

    def after_dry_run(self, run_id: str, database: str) -> dict:
        """`migration accept` moves the cutover (BR9.3; your decision of 2026-10-24): the
        acceptance recorded on the record, the run's rehearsal database set through
        `platform.profile.rehearsal-database`, v2's three roles restarted, readiness
        waited for, and the soak started or restarted once the release's verification
        has passed. Without a CutoverRecord nothing moves.

        Then the rehearsal database the profile named before (an earlier accepted run's,
        `cutover begin`'s or a rollback's) is removed and its rehearsal sets disposed, in
        the order profile, database, sets; a removal that cannot complete stays pending
        for the disposal pass. So repeated dry runs stay within NFR8.15's two rehearsal
        databases (the CutoverRecord row "a dry run is accepted", BR9.17).

        The move's own record (`dry-run-move-<runId>.json`) names the database it
        replaces before any effect, and its completion once v2 restarted on the accepted
        run's database. A move that stopped (a failed profile step or restart) is run
        again by `cutover check`, with the same keys and the same replaced database
        (`resume_dry_run`); until it completes, BR9.2 names
        `rehearsal-database-not-the-accepted-runs` and no switch can start."""
        record = self.machine.current()
        if record is None:
            return {"cutover": "none"}
        name = self._move_evidence(run_id)
        kept = self._read_evidence(name)
        if kept is None or kept.get("database") != database:
            self._write_evidence(name, {
                "runId": run_id, "database": database,
                "previous": self.platform.operator.facts().current_rehearsal,
                "attempt": self._attempt(record)})
        record = self.machine.dry_run_accepted(run_id)
        return self._move_to_dry_run(record, run_id)

    @staticmethod
    def _keyed(record: dict, attempt: str | None) -> dict:
        """The record as a step's keys read it, pinned to the attempt the step began
        under, so a decision recorded in between (a restart rehearsal) changes no key."""
        if attempt is None or attempt == record["cutoverId"]:
            return {**record, "approvals": []}
        return {**record, "approvals": [attempt]}

    @staticmethod
    def _move_evidence(run_id: str) -> str:
        return f"dry-run-move-{run_id}.json"

    def _move_to_dry_run(self, record: dict, run_id: str) -> dict:
        """The accepted run's database set on the profile, v2 restarted on it, readiness
        waited for, its completion recorded, then the database it replaced removed and
        the soak started or restarted."""
        name = self._move_evidence(run_id)
        kept = self._read_evidence(name) or {}
        database, previous = kept["database"], kept.get("previous")
        keyed = self._keyed(record, kept.get("attempt"))
        step = f"dry-run:{run_id}"
        # After a rollback v2 stays stopped: the profile names the run's database, and
        # v2's three roles start only when the soak starts (functional spec, the
        # CutoverRecord rows for `rolled-back`; your decision of 2026-10-25, "Follow the
        # design"). Before any rollback v2 restarts on it here.
        after_rollback = record["state"] == "rolled-back"
        blocker = self._release_exclusion()
        if blocker is not None:
            # No restart of v2 while an install or a release rollback holds the exclusion;
            # `cutover check` runs the move again once it is released.
            return {"cutover": record["state"], "rehearsalDatabase": database,
                    "reason": blocker, "offered": ["check"]}
        try:
            self._profile(keyed, "rehearsalDatabase", database, f"{step}:rehearsal-database")
            if not after_rollback:
                self.restart_v2(keyed, step)
        except StepFailed as failure:
            return {"cutover": record["state"], "rehearsalDatabase": database,
                    "reason": failure.reason, "offered": ["check"]}
        self._write_evidence(name, {**kept, "movedAt": utc_text(self.clock())})
        waited = {"v2": "stopped"} if after_rollback else self.wait_ready()
        replaced = self._replace_rehearsal(keyed, previous, database, step)
        return {"cutover": self.machine.require()["state"], "rehearsalDatabase": database,
                **replaced, **waited, **self.soak_report()}

    def resume_dry_run(self) -> dict | None:
        """`cutover check`'s first part: the accepted dry run's move run again when it
        stopped before v2 restarted on the run's database (`after_dry_run`); None when
        there is no such move."""
        record = self.machine.require()
        run_id = record.get("acceptedDryRunId")
        if run_id is None or record["state"] not in (
                "preparing", "rehearsing", "ready-to-switch", "rolled-back"):
            return None
        kept = self._read_evidence(self._move_evidence(run_id))
        if kept is None or "movedAt" in kept or not isinstance(kept.get("database"), str):
            return None
        return self._move_to_dry_run(record, run_id)

    def _replace_rehearsal(self, record: dict, previous: str | None, database: str,
                           step: str) -> dict:
        """The rehearsal database a newer accepted dry run replaced: its retained copy's
        database removed, then that database's rehearsal sets disposed."""
        if not previous or previous == database:
            return {}
        copies = [copy for copy in self.copies.undisposed("rehearsal-database")
                  if f"database/{previous}" in copy["locations"]]
        removed = [copy["copyId"] for copy in copies
                   if self._remove_rehearsal(record, copy, prefix=f"{step}:")]
        sets, waiting = [], []
        if len(removed) == len(copies):
            sets, waiting = self._dispose_rehearsal_sets(record, database=previous)
        return {"replacedRehearsalDatabase": previous, "rehearsalDatabasesRemoved": removed,
                "rehearsalDatabasesPending": [copy["copyId"] for copy in copies
                                              if copy["copyId"] not in removed],
                "rehearsalSetsDisposed": sets, "rehearsalSetsWaiting": waiting}

    def soak_after_verification(self) -> str | None:
        """Start (from preparing or rolled-back) or restart (rehearsing with none running)
        the soak once the release's verification has passed on the record."""
        return self.soak_report()["soak"]

    def soak_report(self) -> dict:
        """`soak_after_verification` with what it did to v2: from rolled-back, the
        rehearsal v2 starts on the profile's rehearsal database first (its three roles
        through `platform.service.control`, then readiness waited for), and only then
        does the soak start (functional spec, the CutoverRecord row "an accepted dry run
        exists and the complete verification passes"; your decision of 2026-10-25). A
        start that fails, or a v2 that does not become ready within the wait, starts no
        soak; `cutover check` runs it again under its keys.

        Where the links are read (production), no soak starts or restarts for a record
        whose tag is not the release the links point to (`release-not-linked`, review
        finding, Major, R13), whatever verification it holds: `docsuri-release verify` on
        the linked tag names it and records its own."""
        from backend.modules.operations.release_records import recover_blocker

        from docsuri_ops.cutover.preconditions import linked_differs

        record = self.machine.require()
        if "verificationRunId" not in record:
            return {"soak": None}
        # A release record waiting for `recover` (a switch back whose stops failed) blocks
        # every soak start and restart (review finding, Major, R15).
        recover = recover_blocker(self.machine.ledger)
        if recover is not None:
            return {"soak": None, "v2Start": {
                "reason": recover, "offered": [
                    "sudo -k /Library/DocSuri/release/ops/bin/docsuri-release recover"]}}
        linked = linked_differs(record, getattr(self.platform, "evidence", None))
        if linked is not None:
            offered = [] if linked == "none" else [
                "echo '{\"tag\": \"" + linked + "\"}' | sudo -k "
                "/Library/DocSuri/release/ops/bin/docsuri-release verify"]
            return {"soak": None, "v2Start": {"reason": "release-not-linked",
                                              "releaseTag": record["releaseTag"],
                                              "linkedTag": linked, "offered": offered}}
        if record["state"] in ("preparing", "rolled-back") and "acceptedDryRunId" in record:
            started = {}
            if record["state"] == "rolled-back":
                unprobed = self.platform.release_unprobed()
                if unprobed is not None:
                    # A release installed while v2 was kept stopped is probed when the soak
                    # starts; this check starts and stops nothing, and the record stays
                    # rolled-back until the release command runs its probe journey (your
                    # decision of 2026-10-25, "Probe it when the soak starts"). v2 is as
                    # it was: stopped after a rollback, or running on the unprobed release
                    # after a `verify` whose start or readiness failed, whose way out is
                    # that `verify` run again (review finding, Minor, R13).
                    return {"soak": None, "v2Start": {
                        "reason": "release-not-probed", "releaseTag": unprobed,
                        "offered": ["echo '{\"tag\": \"" + unprobed + "\"}' | sudo -k "
                                    "/Library/DocSuri/release/ops/bin/docsuri-release "
                                    "verify"]}}
                blocker = self._release_exclusion()
                if blocker is not None:
                    return {"soak": None, "v2Start": {"reason": blocker, "offered": ["check"]}}
                step = f"soak-start-v2:{record['acceptedDryRunId']}"
                try:
                    self._step(record, step, lambda: self._start_superseded(record, step))
                except StepFailed as failure:
                    return {"soak": None, "v2Start": {"reason": failure.reason,
                                                      "offered": ["check"]}}
                waited = self.wait_ready()
                if not waited["ready"]:
                    # v2 did not become ready: no soak on a stopped or failing v2; `cutover
                    # check` waits again (its start replays by its keys).
                    return {"soak": None, "v2Start": {**waited, "reason": "v2-not-ready",
                                                      "offered": ["check"]}}
                started = {"v2Start": waited}
            self.machine.start_soak()
            return {"soak": "started", **started}
        if record["state"] == "rehearsing" and "soakStartedAt" not in record:
            self.machine.restart_soak()
            return {"soak": "restarted"}
        return {"soak": None}

    # --- the switch (Workflow 13) ----------------------------------------------------------

    def start(self, approval_id=None, subject: dict | None = None) -> dict:
        record = self.machine.require()
        self._refuse_during_release()
        if record["state"] == "ready-to-switch":
            approval = self._subject(approval_id, subject or {}, "switch-start")
            backstop = self._rule(subject or {}, "finalSnapshotBackstopSeconds",
                                  "final_snapshot_backstop_seconds")
            # One instant for the switch (L1-21): the preconditions are evaluated at it,
            # it is recorded as `switchCheckedAt`, and the final snapshot is dated from it
            # (L1-3), never later than the copy's own backstop, recorded after it.
            checked = self.clock()
            record = self.machine.approve_start(approval["approvalId"], self.missing(checked),
                                                checked_at=checked)
            dispose_after = _parse(record["switchCheckedAt"]) + dt.timedelta(seconds=backstop)
            return self._switch_first(record, approval["approvalId"], dispose_after)
        if record["state"] != "switching":
            raise OperationsError("CONFLICT", current={"reasonKey": "cutover-not-switching"})
        if self.machine.bound_passed():
            return {"state": "switching", "offered": ["abort"], "reason": "switch-bound-passed"}
        run = None if "finalRunId" not in record else self.runs.get(record["finalRunId"])
        if run is not None and run["state"] == "reported" and approval_id is not None:
            # Your `final-report` decision (`cutover decide final-report`), applied to the
            # final run; a declined one rejects it and the switch aborts.
            decide = self._require(self.platform.final_decide, "final-decision-unwired")
            try:
                run = self._step(record, "final-report",
                                 lambda: decide(run["runId"], str(approval_id)))
            except StepFailed as failure:
                return self.abort(reason=failure.reason)
        if run is None or run["state"] in ("failed", "rejected"):
            return self.abort(reason="final-run-not-reported" if run is None else
                              f"final-run-{run['state']}")
        if run["state"] != "accepted":
            return {"state": "switching", "waiting": "final-report", "finalRunId": run["runId"]}
        return self._switch_second(record)

    def _switch_first(self, record: dict, approval: str, dispose_after: dt.datetime) -> dict:
        try:
            self._step(record, "route-maintenance",
                       lambda: self._route(record, "maintenance", "route-maintenance"))
            stopped = self._step(record, "stop-v1", lambda: self._services(
                record, self.platform.v1_labels, "stop", "stop-v1"))
            record = self.machine.v1_stopped(stopped)
            self._step(record, "stop-rehearsal-v2", lambda: self._services(
                record, self.platform.v2_labels, "stop", "stop-rehearsal-v2"))
            final = self._require(self.platform.final_run, "final-run-unwired")
            run = self._step(record, "final-run", lambda: final(approval, dispose_after))
        except StepFailed as failure:
            return self.abort(reason=failure.reason)
        self.machine.final_run(run["runId"])
        if run.get("snapshotCopyId"):
            snapshot = self.copies.get(run["snapshotCopyId"])
            if snapshot is not None and "completedAt" in snapshot:
                self.machine.final_snapshot(snapshot["copyId"])
        if run["state"] != "reported":
            return self.abort(reason=f"final-run-{run['state']}")
        return {"state": "switching", "waiting": "final-report", "finalRunId": run["runId"]}

    def _switch_second(self, record: dict) -> dict:
        try:
            self._step(record, "profile-live",
                       lambda: self._profile(record, "mode", "live", "profile-live"))
            self._step(record, "start-v2", lambda: self._services(
                record, self.platform.v2_labels, "start", "start-v2"))
            if not self.wait_ready()["ready"]:
                raise StepFailed("v2-not-ready")
            first = self._require(self.platform.first_backup, "first-backup-unwired")
            backup = self._step(record, "first-live-backup",
                                lambda: first(self._key(record, "first-live-backup")))
            if backup.get("integrity") != "passed":
                raise StepFailed("first-live-backup-failed")
            self._step(record, "route-v2", lambda: self._route(record, "v2-host", "route-v2"))
        except StepFailed as failure:
            return self.abort(reason=failure.reason)
        return {"state": "switching", "waiting": "maintainer-window"}

    def open(self, approval_id, subject: dict) -> dict:
        """Your opening decision applied (BR9.4), then the opening's disposal (profile,
        database, sets). Run again once switched, `open` re-runs only that disposal, under
        the same keys: a step that succeeded replays its receipt, a failed one runs again,
        and only the copies and sets still open are addressed."""
        record = self.machine.require()
        if record["state"] == "switched":
            return {"state": "switched", "v1StoresCopyId": record.get("v1StoresCopyId"),
                    **self.after_opening(record)}
        if record["state"] != "switching":
            raise OperationsError("CONFLICT", current={"reasonKey": "cutover-not-switching"})
        if self.machine.bound_passed():
            return self.abort(reason="switch-bound-passed")
        approval = self._subject(approval_id, subject, "admission-opening")
        offset = self._rule(subject, "v1StoresDisposalSeconds", "v1_stores_disposal_seconds")
        if offset < record["rollbackWindowSeconds"]:
            # v1's stores are kept at least as long as a rollback can need them.
            raise OperationsError("INVALID_INPUT", current={"reasonKey": "before-window-end"})
        accepted = subject.get("providersAcceptedUnavailable", [])
        gaps = self.ledger.atomic(lambda view: self.machine.opening_gates(
            view, view.records("cutover-record")[-1], accepted_unavailable=accepted,
            capabilities_missing=self.platform.capabilities_missing()))
        if gaps:
            raise OperationsError("CONFLICT", current={"reasonKey": "opening-gate-missing",
                                                       "missing": gaps})
        attempt = {**record, "approvals": [*record["approvals"], approval["approvalId"]]}
        try:
            facts = self._effect("platform.profile.admission", "profile",
                                 {"field": "admission", "value": "open",
                                  "approvalId": approval["approvalId"]},
                                 key=self._key(attempt, "admission-open"))
            self._record([facts])
            # Opening applies admission (BR9.4; your decision of 2026-10-24): v2's three
            # roles restart on the opened profile, and readiness is required before the
            # record moves to switched; otherwise the switch aborts, and admission
            # returns to maintainer-only.
            self._step(record, "restart-v2", lambda: self.restart_v2(attempt, "opening"))
            if not self.wait_ready()["ready"]:
                raise StepFailed("v2-not-ready-after-opening")
        except StepFailed as failure:
            return self.abort(reason=failure.reason)
        record = self.machine.open(approval["approvalId"], subject,
                                   capabilities_missing=self.platform.capabilities_missing())
        # v1's stores are dated at admission's opening plus the policy's offset (L1-3).
        stores_after = _parse(record["admissionOpenedAt"]) + dt.timedelta(seconds=offset)
        stores = self.copies.record("v1-stores", f"cutover:{record['cutoverId']}",
                                    list(self.platform.v1_stores), dispose_after=stores_after,
                                    approval_id=approval["approvalId"])
        self.machine.stores_recorded(stores["copyId"])
        disposed = self.after_opening(record)
        return {"state": "switched", "v1StoresCopyId": stores["copyId"], **disposed}

    def after_opening(self, record: dict) -> dict:
        """Profile, database, then sets: the profile's rehearsal database cleared, every
        rehearsal database removed, and only then their backup sets disposed, each set
        once the removal of its own database has applied (BR9.12, BR9.15, BR9.17; review
        finding, Major, R-02). A clear that fails stops here, before any removal, and
        answers why. A removal that failed, is still within its lease or has an unknown
        outcome (`_removal`) leaves its database pending (`rehearsalDatabasesPending`,
        with the reason) and its sets waiting with that same reason: a disposal cannot be
        undone, so none runs before its database is shown gone, by the removal's applied
        receipt here or by the precondition the disposal protocol checks. The record is
        switched, and `open` run again re-runs these steps in the same order, database,
        then sets (`cutover check` names it while switched, `retry_left_sets`)."""
        from docsuri_ops.cutover.disposal import removed_rehearsal_databases

        key = self._opening_attempt(record)
        try:
            self._profile(key, "rehearsalDatabase", None, "clear-rehearsal-database")
        except StepFailed as failure:
            return {"rehearsalDatabaseCleared": False, "reason": failure.reason,
                    "rehearsalDatabasesRemoved": [], "rehearsalDatabasesPending": [],
                    "rehearsalSetsDisposed": [], "rehearsalSetsWaiting": [],
                    "offered": ["open"]}
        removed, pending = [], []
        for copy in self._opening_addressed(record):
            reason = self._removal(key, copy)
            if reason is not None and reason not in SURFACED_REMOVAL_REASONS:
                reason = "rehearsal-database-removal-failed"
            (removed if reason is None else pending).append((copy, reason))
        # The databases shown gone: removed in this run, or by an earlier run (their
        # copies disposed on the removal's receipt), whose sets may still be waiting.
        gone = sorted({name for copy, _ in removed for name in self._database_names(copy)}
                      | removed_rehearsal_databases(self.ledger))
        sets, waiting = [], []
        for name in gone:
            disposed, held = self._dispose_rehearsal_sets(key, database=name)
            sets += disposed
            waiting += held
        for copy, reason in pending:
            # The database is not shown gone: its sets wait, with the removal's reason.
            waiting += [{"backupId": backup["backupId"], "reason": reason}
                        for name in self._database_names(copy)
                        for backup in self._open_rehearsal_sets(name)]
        answer = {"rehearsalDatabaseCleared": True,
                  "rehearsalDatabasesRemoved": [copy["copyId"] for copy, _ in removed],
                  "rehearsalDatabasesPending": [{"copyId": copy["copyId"], "reason": reason}
                                                for copy, reason in pending],
                  "rehearsalSetsDisposed": sets, "rehearsalSetsWaiting": waiting}
        return {**answer, "offered": ["open"]} if pending else answer

    @staticmethod
    def _database_names(copy: dict) -> list[str]:
        """The databases a retained copy's locations name."""
        return [location.removeprefix("database/") for location in copy["locations"]
                if location.startswith("database/")]

    def _open_rehearsal_sets(self, database: str | None = None) -> list[dict]:
        """The undisposed rehearsal backup sets: every one, or only `database`'s (its
        incarnation names it)."""
        return [backup for backup in self.ledger.records("backup-set")
                if backup["environment"] == "rehearsal"
                and not any(name in backup for name in ("disposedAt", "retiredWithVolumeAt"))
                and (database is None
                     or str(backup.get("databaseIncarnation", "")).split(":", 1)[0]
                     == database)]

    def _opening_attempt(self, record: dict) -> dict:
        """The record as its opening's keys read it: the attempt is the opening decision,
        whichever decisions came after it (a cancelled rollback's), so a re-run binds the
        same keys as the opening did."""
        opening = next((ref for ref in reversed(record["approvals"])
                        if (self.ledger.get("maintainer-approval", ref) or {}).get("step")
                        == "admission-opening"), None)
        if opening is None:
            return record
        index = record["approvals"].index(opening)
        return {**record, "approvals": record["approvals"][:index + 1]}

    def _opening_addressed(self, record: dict) -> list[dict]:
        """The open rehearsal databases this cutover's opening addressed: the copies
        recorded at or before admission opened. A copy recorded later is another run's
        own and is never removed here (a dry run cannot start while the cutover is
        switched, `MigrationTool._dry_precondition`, so none should exist)."""
        opened = record.get("admissionOpenedAt")
        copies = self.copies.undisposed("rehearsal-database")
        if not opened:
            return copies
        moment = _parse(opened)
        return [copy for copy in copies if _parse(copy["createdAt"]) <= moment]

    def _remove_rehearsal(self, record: dict, copy: dict, *, prefix: str = "") -> bool:
        """One rehearsal database's removal through PlatformControl, then its retained
        copy disposed on the receipt; one that cannot complete stays pending for the
        disposal pass (BR9.17)."""
        return self._removal(record, copy, prefix=prefix) is None

    def _removal(self, record: dict, copy: dict, *, prefix: str = "",
                 earlier: tuple[str, ...] = ()) -> str | None:
        """`_remove_rehearsal`, answering None once removed, or the failure's reason.
        `earlier` names the prefixes earlier runs keyed this removal under: each is
        settled first (`_settled_earlier`), so a removal an earlier run left in flight is
        never run beside, and one that applied is taken as done."""
        receipt, reason = None, None
        for location in copy["locations"]:
            name = location.removeprefix("database/")
            inputs = {"database": name, "via": "in-person"}
            try:
                receipt = self._settled_earlier(
                    "platform.database.remove", "database-rehearsal", inputs,
                    keys=[self._key(record, f"{before}remove:{name}") for before in earlier])
                if receipt is None:
                    receipt = self._effect("platform.database.remove", "database-rehearsal",
                                           inputs, key=self._key(record, f"{prefix}remove:{name}"))
            except StepFailed as failure:
                receipt, reason = None, failure.reason
                break
        if receipt is None:
            self.copies.disposal_pending(copy["copyId"])
            return reason or "rehearsal-database-removal-failed"
        self.copies.disposed(copy["copyId"], receipt)
        return None

    @staticmethod
    def _set_evidence(record: dict) -> str:
        return f"set-disposals-{record['cutoverId']}.json"

    def _dispose_rehearsal_sets(self, record: dict, *, database: str | None = None,
                                recheck: Callable[[], str | None] | None = None
                                ) -> tuple[list, list]:
        """The rehearsal backup sets disposed after their database left the profile and
        was removed: every one, or only `database`'s (its incarnation names it).
        `recheck` is asked again once each disposal's receipt is bound (`_effect`).

        Each set's disposal is one run of its own, whoever runs it (opening, a replaced
        dry run's move, a rollback's end, `cutover check`): its key names the set and the
        run's count, kept in `set-disposals-<cutoverId>.json`, and is pinned to the
        cutover's identity rather than its latest decision (`_keyed`), so no decision
        recorded in between changes it. Every earlier run's key is settled first
        (`_settled_earlier`; the re-review's findings of 2026-10-26): a disposal an
        earlier run left in flight is never run beside (the set waits), one that applied
        (the agent deleted the archive before its record was written) is taken as done
        and recorded, never run again against a catalogue that no longer holds it, and
        one that failed, however many runs, never exhausts its keys."""
        pinned = self._keyed(record, None)
        evidence = self._set_evidence(record)
        kept = self._read_evidence(evidence) or {}
        attempts = dict(kept.get("attempts") or {})
        sets, waiting = [], []
        for backup in self._open_rehearsal_sets(database):
            identity = backup["backupId"]
            inputs = {"recordKind": "BackupSet", "recordId": identity,
                      "place": "backup-volume", "location": backup["location"],
                      "event": "rehearsal-database-removed"}
            run = int(attempts.get(identity, 0)) + 1
            try:
                receipt = self._settled_earlier(
                    "platform.copy.dispose", "copies", inputs,
                    keys=[self._key(pinned, f"dispose-set:{identity}:{earlier}")
                          for earlier in range(1, run)])
                if receipt is None:
                    attempts[identity] = run
                    self._write_evidence(evidence, {"cutoverId": record["cutoverId"],
                                                    "attempts": attempts})
                    self._effect("platform.copy.dispose", "copies", inputs,
                                 key=self._key(pinned, f"dispose-set:{identity}:{run}"),
                                 recheck=recheck)
            except StepFailed as failure:
                # The floor, the volume, or an earlier run still in flight: the set waits
                # for the next in-person run.
                waiting.append({"backupId": identity, "reason": failure.reason})
                continue
            current = self.ledger.get("backup-set", identity)
            self.ledger.append("backup-set", {**current, "disposedAt": utc_text(self.clock())},
                               expect_revision=self.ledger.revision("backup-set", identity))
            sets.append(identity)
        return sets, waiting

    # --- the providers in the window (U8 plan Step 106(d), CP-3; BR7.3, BR7.8) -----------

    PROVIDER_STATES = ("switching", "switched", "settled")

    def _provider_record(self, states: tuple[str, ...], reason: str) -> dict:
        record = self.machine.require()
        if record["state"] not in states:
            raise OperationsError("CONFLICT", current={"reasonKey": reason,
                                                       "state": record["state"]})
        return record

    def provider_previews(self, document: dict) -> dict:
        """A held outward provider's previews held since the switch's check, or one's
        exact content, read through the provider words."""
        words = self._require(self.platform.provider_word, "provider-words-unwired")
        record = self._provider_record(self.PROVIDER_STATES, "cutover-state-differs")
        return {"state": record["state"], **words("provider-previews", document)}

    def provider_decision(self, approval_id, subject) -> dict:
        """Your recorded provider decision applied with the subject it was shown with.
        Every binding check, the window rule for a sign-in approval included, is
        `ProviderActivation.approve`'s, on the service side. The CutoverRecord is never
        written: its `approvals` key the switch's own steps."""
        words = self._require(self.platform.provider_word, "provider-words-unwired")
        record = self._provider_record(self.PROVIDER_STATES, "cutover-state-differs")
        if not isinstance(subject, dict) or not isinstance(subject.get("provider"), str):
            raise OperationsError("INVALID_INPUT",
                                  current={"reasonKey": "word-or-input-refused"})
        result = words("provider-decision", {"provider": subject["provider"],
                                             "approvalId": str(approval_id),
                                             "subject": subject})
        answer = {"state": record["state"], "provider": result["provider"],
                  "providerState": result["state"], "limitations": result["limitations"]}
        for name in ("approvedAt", "approvalContentHash"):
            if name in result:
                answer[name] = result[name]
        return answer

    def provider_failed(self, provider) -> dict:
        """A sign-in provider whose real sign-in failed in the window, recorded
        unavailable, only while switching."""
        words = self._require(self.platform.provider_word, "provider-words-unwired")
        record = self._provider_record(("switching",), "cutover-not-switching")
        result = words("provider-failed", {"provider": provider})
        return {"state": record["state"], "provider": result["provider"],
                "providerState": result["state"], "limitations": result["limitations"]}

    # --- the abort (Workflow 14 step 1) ----------------------------------------------------

    def abort(self, *, reason: str) -> dict:
        record = self.machine.require()
        if record["state"] == "switching":
            record = self.machine.abort(reason=reason)
        elif record["state"] != "aborting":
            raise OperationsError("CONFLICT", current={"reasonKey": "cutover-not-switching"})
        try:
            self._step(record, "route-maintenance",
                       lambda: self._route(record, "maintenance", "abort-maintenance"))
            stopped = self._step(record, "stop-v2", lambda: self._services(
                record, self.platform.v2_labels, "stop", "abort-stop-v2"))
        except StepFailed as failure:
            return {"state": "aborting", "reason": failure.reason}
        try:
            self._step(record, "start-v1", lambda: self._services(
                record, self.platform.v1_labels, "start", "abort-start-v1"))
        except StepFailed:
            self.machine.v1_restart_failed()
            return {"state": "aborting", "reason": "v1-restart-failed"}
        # v1's local health waited for, every 5 s for up to 10 minutes (L1-59); the wait
        # never starts v1 again.
        if not self.wait_v1_ready()["ready"]:
            self.machine.v1_restart_failed()
            return {"state": "aborting", "reason": "v1-restart-failed"}
        try:
            self._route(record, "v1-web", "abort-route-v1")
            if not self.platform.public("v1-health"):
                raise StepFailed("v1-not-answering-publicly")
            # Only now does anything of v2's change: the profile, then the database. The
            # admission returns to maintainer-only first: a rehearsal profile with
            # admission open does not load (opening's failed restart aborts after the
            # admission opened).
            self._profile(record, "admission", "maintainer-only", "abort-profile-admission")
            self._profile(record, "mode", "rehearsal", "abort-profile-mode")
            recreated = self._effect("platform.database.recreate", "database-production",
                                     {"database": self.platform.production},
                                     key=self._key(record, "abort-recreate"))
            self._record([recreated])
        except StepFailed as failure:
            return {"state": "aborting", "reason": failure.reason}
        if self.platform.activation is not None:
            self.platform.activation.clear_approvals(mode="rehearsal")
        listed = self._stop_incidents(record, stopped, keep=record.get("abortIncidentId"))
        self.machine.aborted()
        self._end_final_run(record)
        self.runs.end_freeze()
        try:
            self._services(self.machine.require(), self.platform.v2_labels, "start",
                           "abort-start-rehearsal-v2")
        except StepFailed as failure:
            return {"state": "rehearsing", "stoppedIncidents": listed, "reason": failure.reason}
        return {"state": "rehearsing", "stoppedIncidents": listed}

    def _end_final_run(self, record: dict) -> None:
        """A final run not yet accepted ends failed; an incomplete final snapshot is
        disposed through its record, a completed one stays under its date (BR9.12)."""
        run = None if "finalRunId" not in record else self.runs.get(record["finalRunId"])
        if run is None or run["state"] in ("accepted", "rejected", "failed"):
            return
        if self.platform.fail_final is not None:
            self.platform.fail_final(run["runId"], "switch-aborted")
        else:
            self.runs.move(run["runId"], "failed")

    def _stop_incidents(self, record: dict, stopped: list, *, keep: str | None) -> list[str]:
        """Every other unresolved live incident resolves as environment-stopped with the
        stop's receipt and is listed on the abort's or the rollback's incident."""
        evidence = [f"receipt:{item['receiptId']}" for item in stopped][:4] or [
            f"cutover:{record['cutoverId']}:v2-stopped"]
        listed = []
        for incident in self.ledger.records("service-incident"):
            if incident["state"] == "resolved" or incident["environment"] != "live" or (
                incident["incidentId"] in (keep, record.get("rollbackCopyIncidentId"))
            ):
                continue
            try:
                self.incidents.resolve(incident["incidentId"], "environment-stopped", evidence)
            except OperationsError:
                continue
            listed.append(incident["incidentId"])
        if keep is not None:
            for incident in listed:
                self.incidents.take_over_cutover(
                    "switch-aborted" if record["state"] == "aborting"
                    else "rollback-copy-pending", correlation=f"stopped:{incident}")
        return listed

    # --- the rollback (Workflow 14 step 2) -------------------------------------------------

    def rollback(self, approval_id, subject: dict) -> dict:
        record = self.machine.require()
        self._refuse_during_release()
        if record["state"] == "switched":
            approval = self._subject(approval_id, subject, "rollback")
            self._rule(subject, "rolledBackDisposalSeconds", "rolled_back_disposal_seconds")
            # A rollback is never blocked by the database count (your decision of
            # 2026-10-25, "Never block a rollback"): its start is not refused for NFR8.15;
            # the serving step first removes what opening left pending (`_remove_left`).
            record = self.machine.rollback(approval["approvalId"])
            # The decision binds this subject's digest; it is kept as evidence for a
            # retried copy, which applies its rule again.
            self._write_evidence(f"rollback-subject-{record['cutoverId']}.json", subject)
        elif record["state"] != "rolling-back":
            raise OperationsError("CONFLICT", current={"reasonKey": "cutover-not-switched"})
        if "rollbackV1ServingAt" in record:
            return self.retry_copy()
        try:
            self._step(record, "route-maintenance",
                       lambda: self._route(record, "maintenance", "rollback-maintenance"))
            stopped = self._step(record, "stop-v2", lambda: self._services(
                record, self.platform.v2_labels, "stop", "rollback-stop-v2"))
            self._step(record, "start-v1", lambda: self._services(
                record, self.platform.v1_labels, "start", "rollback-start-v1"))
            # v1's local health waited for, every 5 s for up to 10 minutes (L1-59).
            if not self.wait_v1_ready()["ready"]:
                raise StepFailed("v1-restart-failed")
            applied = self._step(record, "v1-lifecycle", lambda: self._apply_lifecycle(record))
            self._route(record, "v1-web", "rollback-route-v1")
            if not self.platform.public("v1-health"):
                raise StepFailed("v1-not-answering-publicly")
        except StepFailed as failure:
            # The maintenance notice stays; your decision can cancel (BR9.7).
            return {"state": "rolling-back", "reason": failure.reason,
                    "offered": ["cancel-rollback"]}
        record = self.machine.rollback_v1_serving(applied=applied)
        failed = self._serve(record)
        if failed is not None:
            return failed
        return self._copy(self.machine.require(), stopped=stopped)

    def _apply_lifecycle(self, record: dict) -> dict:
        """v2's lifecycle outcomes reach v1 through v1's own account code, every v1
        session ends, and each account's v1 state is read back (BR9.13)."""
        from backend.modules.operations.migration.identities import target_id

        outcomes_of = self._require(self.platform.lifecycle_outcomes, "lifecycle-unwired")
        accounts_of = self._require(self.platform.v1_accounts, "v1-accounts-unwired")
        states_of = self._require(self.platform.v1_states, "v1-states-unwired")
        since = _parse(record.get("admissionOpenedAt") or record["switchStartedAt"])
        accounts = list(accounts_of())
        by_target = {str(target_id("account", account)): account for account in accounts}
        outcomes = [{"v1AccountId": by_target[item["accountId"]], "outcome": item["outcome"]}
                    for item in outcomes_of(since) if item["accountId"] in by_target]
        facts = self._effect("platform.v1.lifecycle.apply", "v1-accounts",
                             {"outcomes": outcomes, "accounts": accounts},
                             key=self._key(record, "v1-lifecycle"))
        self._record([facts])
        states = states_of([item["v1AccountId"] for item in outcomes])
        for item in outcomes:
            if states.get(item["v1AccountId"]) not in V1_STATES[item["outcome"]]:
                raise StepFailed("v1-account-mismatch")
        self._write_evidence(f"rollback-accounts-{record['cutoverId']}.json", {
            "cutoverId": record["cutoverId"],
            "accounts": [{"v1AccountId": item["v1AccountId"], "outcome": item["outcome"],
                          "state": states.get(item["v1AccountId"])} for item in outcomes]})
        return {"outcomesApplied": True, "sessionsEnded": True, "applied": len(outcomes)}

    def _serve(self, record: dict) -> dict | None:
        """The serving step, or why it stopped: v1 keeps serving, the cutover stays
        rolling-back and the copy does not start; the rollback's retry runs it again."""
        try:
            self._serving_step(record)
        except StepFailed as failure:
            return {"state": "rolling-back", "v1Serving": True, "reason": failure.reason,
                    "offered": ["rollback"]}
        return None

    def _serving_step(self, record: dict) -> None:
        """At v1's serving (BR9.7, BR9.15): v1's stores return to service; the rollback's
        new, empty rehearsal database is named, recorded, created and set, because
        opening removed every rehearsal database (your decision of 2026-10-24, "Create a
        fresh rehearsal database"); only then does the profile return to rehearsal with
        admission maintainer-only; the accepted dry run is cleared, provider approvals
        are cleared, and the decisions unfreeze. v2 stays stopped, on a profile that
        loads, until a dry run accepted after the rollback replaces that database.

        Each step replays its receipt by its key, and the database is created once, so a
        retry runs only what is missing."""
        if record.get("v1StoresCopyId"):
            self.copies.returned_to_service(record["v1StoresCopyId"])
        name = self._rollback_rehearsal(record)
        record = self._rollback_profile(record, "rehearsalDatabase", name,
                                        "rollback-rehearsal-database")
        # Admission first: a rehearsal profile with admission open does not load.
        record = self._rollback_profile(record, "admission", "maintainer-only",
                                        "rollback-profile-admission")
        self._rollback_profile(record, "mode", "rehearsal", "rollback-profile-mode")
        self.machine.rollback_returned_to_rehearsal()
        if self.platform.activation is not None:
            self.platform.activation.clear_approvals(mode="rehearsal")
        self.runs.end_freeze()

    def _rollback_profile(self, record: dict, field_name: str, value, step: str) -> dict:
        """One of the serving step's profile changes, the earlier runs' keys for it
        settled first (`_settled_earlier`; review finding, Minor, R-04). `retry-copy`
        onto a replacement volume records your retirement decision on the record, so a
        later run keys this step under that decision instead of the rollback's: a change
        an earlier run applied is taken as done and its receipt recorded, one still
        within its lease answers `effect-in-progress`, one whose outcome cannot be proven
        is reconciled, and a new effect runs under this run's key only where every
        earlier run left nothing applied."""
        inputs = {"field": field_name, "value": value}
        facts = self._settled_earlier(
            PROFILE_OPERATIONS[field_name], "profile", inputs,
            keys=[self._key(earlier, step) for earlier in self._rollback_attempts_before(record)])
        if facts is not None:
            return self._record([facts])
        return self._profile(record, field_name, value, step)

    def _rollback_attempts_before(self, record: dict) -> list[dict]:
        """The record as each earlier run of this rollback keyed its steps (`_key` reads
        the latest decision): the rollback decision, then every decision recorded after
        it but before the latest (a replacement volume's), oldest first; none while the
        latest decision is the rollback's own."""
        approvals = record["approvals"]
        rollback = self._rollback_subject(record)["approvalId"]
        if rollback not in approvals:
            return []
        return [{**record, "approvals": approvals[:index + 1]}
                for index in range(approvals.index(rollback), len(approvals) - 1)]

    def _rollback_rehearsal(self, record: dict) -> str:
        """The rollback's rehearsal database: named with the instance's naming and
        recorded as a retained `rehearsal-database` copy of this rollback before anything
        is written, so a retry finds it and uses the same name; then created empty
        (`create-disposable`), once: the copy's completion marks the creation."""
        approval = self._rollback_subject(record)["approvalId"]
        source = f"cutover:{record['cutoverId']}:rollback:{approval}"
        copy = next((item for item in self.copies.undisposed("rehearsal-database")
                     if item["sourceRef"] == source), None)
        if copy is None:
            # Never block a rollback: first the rehearsal databases opening left pending.
            self._remove_left(record)
            names = self.platform.operator.facts().names
            # Only the new database's creation is then counted, and it fits; were it
            # refused all the same, v1 keeps serving and the retry asks again.
            reason = self._rehearsal_limit(names)
            if reason is not None:
                raise StepFailed(reason)
            name = names.new("rehearsal")
            copy = self.copies.record("rehearsal-database", source, [f"database/{name}"])
        # Any failure: v1 keeps serving, and the retry creates it (idempotently).
        return self._create_rehearsal(record, copy)

    @staticmethod
    def _left_evidence(record: dict) -> str:
        return f"rollback-left-{record['cutoverId']}.json"

    def _remove_left(self, record: dict) -> None:
        """A rollback is never blocked by the database count (your decision of
        2026-10-25, "Never block a rollback"): before the rollback names its new database,
        the rehearsal databases this cutover's opening left pending (the copies recorded
        at or before admission opened, `_opening_addressed`; a later copy is another
        run's own and is left alone) are removed through PlatformControl's database
        removal, after a profile still naming one is cleared (an opening whose clear
        failed). Their sets are disposed once the rollback has ended (`_finish_rollback`),
        because A6 refuses every disposal while the record is rolling-back.

        Every name this step addresses is kept in its evidence before any removal runs,
        so the sets of a database removed by an earlier run of `rollback` are disposed
        too. Each run of `rollback` is one new attempt of each removal, under keys of
        that run's own (the evidence counts the runs), so a removal that failed, however
        many times, runs again on the next `rollback` and never exhausts its keys. A
        removal that fails raises, so v1 keeps serving; the rollback's own copy is
        recorded only after this step, so a retry that found it skips it."""
        left = self._opening_addressed(record)
        if not left:
            return
        names = sorted({location.removeprefix("database/") for copy in left
                        for location in copy["locations"] if location.startswith("database/")})
        evidence = self._left_evidence(record)
        kept = self._read_evidence(evidence) or {}
        attempt = int(kept.get("attempts", 0)) + 1
        self._write_evidence(evidence, {
            "cutoverId": record["cutoverId"], "attempts": attempt,
            "names": sorted({*kept.get("names", []), *names})})
        if self.platform.operator.facts().current_rehearsal in names:
            self._profile(record, "rehearsalDatabase", None, "rollback-clear-rehearsal-database")
        for copy in left:
            # Every earlier run's key for this removal is settled before this run's opens
            # (review finding, Major, R12).
            reason = self._removal(record, copy, prefix=f"rollback-left:{attempt}:",
                                   earlier=tuple(f"rollback-left:{before}:"
                                                 for before in range(1, attempt)))
            if reason is not None:
                raise StepFailed(reason if reason in SURFACED_REMOVAL_REASONS
                                 else "rehearsal-database-removal-failed")

    def _dispose_left_sets(self, record: dict) -> dict:
        """Once the rollback has ended (the live exclusion released): the sets of every
        rehearsal database `_remove_left` addressed, in any run of `rollback`, disposed
        after their database (profile, database, sets; BR9.17). A set that cannot be
        disposed now waits for the disposal pass, with its reason."""
        kept = self._read_evidence(self._left_evidence(record)) or {}
        names = kept.get("names") or []
        if not names:
            return {}
        sets, waiting = [], []
        for name in names:
            disposed, held = self._dispose_rehearsal_sets(record, database=name)
            sets += disposed
            waiting += held
        return {"rehearsalDatabasesLeft": names, "rehearsalSetsDisposed": sets,
                "rehearsalSetsWaiting": waiting}

    def retry_left_sets(self, record: dict) -> dict:
        """`cutover check`'s retry by event (the review's fix of 2026-10-26; review
        finding, Major, R16): every rehearsal set still waiting after its database was
        removed (`disposal.waiting_rehearsal_sets`, the sets the standing pass reports) is
        disposed of again, after its database, so a transient failure does not keep a
        removed database's migrated data until the set's retention date. That covers a
        rollback's left sets (the names in `rollback-left-<id>.json`), opening's sets
        once a rollback ended, and the sets of a database a newer accepted dry run
        replaced. Each run disposes of a set under a key of that run's own, after the
        earlier runs' keys are settled (`_dispose_rehearsal_sets`; the re-review's
        findings of 2026-10-26), so a failing disposal never runs out of keys, and one
        an earlier run applied without recording it is recorded rather than run again.

        Nothing runs while the record holds the live exclusion, while an install or a
        release rollback holds it (BR4.4; review finding, Minor, R13: the sets wait, with
        that reason), while a release command runs (its run marker, read right before
        the disposals act, and again once each is bound; your decision of 2026-10-26,
        "Check the release run lock"), or when no set is waiting. While the record is switched,
        opening's disposal is the retry: `cutover open` run again re-runs it under its own
        keys (`after_opening`), so this names that command (`offered: ["open"]`) and
        disposes of none."""
        from backend.modules.operations.cutover import LIVE_EXCLUSION

        from docsuri_ops.cutover.disposal import set_database, waiting_rehearsal_sets

        if record["state"] in LIVE_EXCLUSION:
            return {}
        waiting = waiting_rehearsal_sets(self.ledger)
        if not waiting:
            return {}
        names = (self._read_evidence(self._left_evidence(record)) or {}).get("names") or []
        left = {"rehearsalDatabasesLeft": names} if names else {}
        reason = "cutover-switched" if record["state"] == "switched" else (
            self._release_exclusion())
        if reason is not None:
            held = {"rehearsalSetsDisposed": [], "rehearsalSetsWaiting": [
                {"backupId": backup["backupId"], "reason": reason} for backup in waiting]}
            return {**left, **held, **({"offered": ["open"]} if reason == "cutover-switched"
                                      else {})}
        sets, held = [], []
        for name in sorted({set_database(backup) for backup in waiting}):
            disposed, still = self._dispose_rehearsal_sets(record, database=name,
                                                           recheck=self._release_exclusion)
            sets += disposed
            held += still
        return {**left, "rehearsalSetsDisposed": sets, "rehearsalSetsWaiting": held}

    def _rollback_subject(self, record: dict) -> dict:
        approval = next(
            (item for item in (self.ledger.get("maintainer-approval", ref)
                               for ref in reversed(record["approvals"]))
             if item is not None and item["step"] == "rollback"), None)
        if approval is None:
            raise OperationsError("FORBIDDEN", current={"reasonKey": "decision-required"})
        return approval

    def _copy(self, record: dict, *, stopped: list | None = None) -> dict:
        """The stopped production database's copy onto the backup volume as a retained
        copy, then the recreate (BR9.7). Any failure keeps the cutover rolling-back with
        the copy pending."""
        approval = self._rollback_subject(record)
        subject = self._read_evidence(f"rollback-subject-{record['cutoverId']}.json")
        if subject is None or subject_digest(subject) != approval["subjectDigest"]:
            raise OperationsError("CONFLICT", current={"reasonKey": "decision-subject-differs"})
        # The rolled-back copy is dated at v1's serving again plus the policy's offset
        # (L1-3).
        offset = self._rule(subject, "rolledBackDisposalSeconds", "rolled_back_disposal_seconds")
        dispose_after = _parse(record["rollbackV1ServingAt"]) + dt.timedelta(seconds=offset)
        agent = self._require(self.platform.agent, "agent-unwired")
        previous = [item for item in self.copies.undisposed("rolled-back-v2-database")
                    if item["sourceRef"] == f"cutover:{record['cutoverId']}"
                    and "completedAt" not in item]
        for item in previous:
            self.copies.disposal_pending(item["copyId"])  # cut short: retried as a new copy
        copy = self.copies.record("rolled-back-v2-database", f"cutover:{record['cutoverId']}",
                                  ["backup-volume:rolled-back-database"],
                                  dispose_after=dispose_after,
                                  approval_id=approval["approvalId"])
        try:
            result = agent("rollback-copy", {"recordId": copy["copyId"], "decided": {
                "date": dispose_after.isoformat(), "receipt": approval["operatorReceiptRef"],
                "subjectDigest": approval["subjectDigest"]}}, via="in-person")
        except Exception:  # noqa: BLE001 - any failure: the copy waits (BR9.7)
            result = {}
        if not result.get("sha256") or result.get("integrity") not in (None, "passed"):
            record = self.machine.rollback_copy_pending()
            return {"state": "rolling-back", "copyPending": True,
                    "incidentId": record["rollbackCopyIncidentId"]}
        self.copies.complete(copy["copyId"], checksum=result["sha256"],
                             source_database_bytes=int(result.get("databaseBytes", 0) or 0))
        return self._finish_rollback(record, settled=f"copy:{copy['copyId']}", stopped=stopped)

    def _finish_rollback(self, record: dict, *, settled: str, waiver=None,
                         stopped: list | None = None) -> dict:
        # What v2 made since the switch is read from the stopped database before the
        # recreate empties it (found by the cutover journeys on the realm).
        writes = {} if self.platform.v2_writes is None else self.platform.v2_writes(
            _parse(record["admissionOpenedAt"]))
        try:
            recreated = self._effect("platform.database.recreate", "database-production",
                                     {"database": self.platform.production},
                                     key=self._key(record, "rollback-recreate"))
        except StepFailed as failure:
            return {"state": "rolling-back", "reason": failure.reason}
        record = self._record([recreated])
        pending = record.get("rollbackCopyIncidentId")
        if pending is not None:
            incident = self.incidents.get(pending)
            if incident is not None and incident["state"] != "resolved":
                self.incidents.resolve(pending, "rollback-copy-settled",
                                       [settled, f"receipt:{recreated['receiptId']}"])
        listed = self._stop_incidents(record, stopped or [recreated], keep=None)
        reference = self._write_evidence(f"rollback-writes-{record['cutoverId']}.json",
                                         {"cutoverId": record["cutoverId"], "perKind": writes})
        record = self.machine.rolled_back(waiver=waiver)
        # The left databases' sets, now that A6 admits a disposal (`_remove_left`).
        left = self._dispose_left_sets(record)
        return {"state": "rolled-back", "stoppedIncidents": listed, "writesReport": reference,
                **left}

    def retry_copy(self, *, replacement=None) -> dict:
        """The operator retries the copy, once the volume check passes when the volume was
        the cause, or on a replacement volume after your retirement decision (BR4.10)."""
        record = self.machine.require()
        if record["state"] != "rolling-back" or "rollbackV1ServingAt" not in record:
            raise OperationsError("CONFLICT", current={"reasonKey": "rollback-not-waiting"})
        # The serving step's missing steps first, each replaying its receipt by its key;
        # only then the copy (your decision of 2026-10-24).
        failed = self._serve(record)
        if failed is not None:
            return failed
        record = self.machine.require()
        if replacement is not None:
            self.machine.replacement_volume(replacement)
        elif "rollbackCopyPendingSince" in record and self.platform.agent is not None:
            status = self.platform.agent("status", {}, via="in-person")
            if not status.get("available"):
                return {"state": "rolling-back", "copyPending": True,
                        "reason": "backup-volume-unfit"}
        return self._copy(self.machine.require())

    def waive_copy(self, approval_id, subject: dict) -> dict:
        """Your decision waives the copy, shown the per-kind count of what v2 made since
        the switch that will be lost; the database is recreated without a copy."""
        record = self.machine.require()
        if record["state"] != "rolling-back" or "rollbackCopyPendingSince" not in record:
            raise OperationsError("CONFLICT", current={"reasonKey": "rollback-copy-not-pending"})
        approval = self._subject(approval_id, subject, "rollback-copy-waiver")
        return self._finish_rollback(record, settled=f"waiver:{approval['approvalId']}",
                                     waiver=approval["approvalId"])

    def cancel_rollback(self, approval_id) -> dict:
        """Before v1 serves, your decision cancels: v1 stops, v2 starts again on its
        untouched database, the public address routes back to v2 (BR9.7)."""
        record = self.machine.require()
        if record["state"] != "rolling-back" or "rollbackV1ServingAt" in record:
            raise OperationsError("CONFLICT", current={"reasonKey": "rollback-not-cancellable"})
        self._approval_first(record, approval_id, "rollback-cancel")
        attempt = {**record, "approvals": [*record["approvals"], str(approval_id)]}
        try:
            receipts = self._services(attempt, self.platform.v1_labels, "stop", "cancel-stop-v1")
            receipts += self._services(attempt, self.platform.v2_labels, "start",
                                       "cancel-start-v2")
            if not self.platform.v2_ready():
                raise StepFailed("v2-not-ready")
            self._route(attempt, "v2-host", "cancel-route-v2")
        except StepFailed as failure:
            return {"state": "rolling-back", "reason": failure.reason}
        record = self.machine.cancel_rollback(approval_id)
        return {"state": record["state"]}

    # --- v1's stores, deleted by hand (the person's decision of 2026-10-22) -------------------

    def v1_stores_deleted(self, copy_id: str | None = None) -> dict:
        """After you have deleted v1's stores by hand, at the date your decision
        approved: check read-only that each location is gone, then record the deletion
        and its time on the v1-stores RetainedCopy with the check's evidence, bound to
        an in-person receipt of `platform.copy.dispose` (place `v1-stores`), so erasure
        evidence stops counting the copy and its storage incident can resolve. The system
        never deletes v1's data itself (BR9.17)."""
        if getattr(self.platform.operator, "standing", False):
            raise OperationsError("FORBIDDEN", current={"reasonKey": "in-person-required"})
        copy = self._v1_stores_copy(copy_id)
        now = self.clock()
        if _parse(copy["disposeAfter"]) > now:
            raise OperationsError("CONFLICT", current={"reasonKey": "before-approved-date",
                                                       "disposeAfter": copy["disposeAfter"]})
        present = self._require(self.platform.v1_store_present, "v1-stores-unwired")
        remaining = [location for location in copy["locations"] if present(location)]
        if remaining:
            raise OperationsError("CONFLICT", current={"reasonKey": "v1-store-still-present",
                                                       "locations": remaining})
        inputs = {"recordKind": "RetainedCopy", "recordId": copy["copyId"],
                  "place": "v1-stores", "locations": list(copy["locations"]),
                  "via": "in-person"}
        key = "cutover:" + hashlib.sha256(
            f"v1-stores-deleted:{copy['copyId']}".encode()).hexdigest()
        try:
            facts = self._effect("platform.copy.dispose", "copies", inputs, key=key)
        except StepFailed as failure:
            raise OperationsError("CONFLICT", current={"reasonKey": failure.reason}) from None
        reference = self._write_evidence(f"v1-stores-deleted-{copy['copyId']}.json", {
            "copyId": copy["copyId"], "checkedAt": utc_text(now),
            "locations": [{"location": location, "present": False}
                          for location in copy["locations"]],
            "receiptId": facts["receiptId"], "deletedBy": "operator-in-person",
        })
        record = self.copies.disposed_in_person(copy["copyId"], facts, reference)
        return {"copyId": record["copyId"], "disposedAt": record["disposedAt"],
                "checkRef": reference, "receiptId": facts["receiptId"]}

    def _v1_stores_copy(self, copy_id: str | None) -> dict:
        if copy_id is None:
            record = self.machine.require()
            copy_id = record.get("v1StoresCopyId")
        copy = None if copy_id is None else self.copies.get(copy_id)
        if copy is None or copy["kind"] != "v1-stores":
            raise OperationsError("NOT_FOUND", current={"reasonKey": "v1-stores-not-recorded"})
        if any(name in copy for name in ("disposedAt", "retiredWithVolumeAt",
                                         "returnedToServiceAt")):
            raise OperationsError("CONFLICT", current={"reasonKey": "v1-stores-closed"})
        return copy

    # --- settlement and the restart rehearsal ------------------------------------------------

    def settle(self, approval_id, subject: dict) -> dict:
        """Your settlement decision after the window (BR9.8), then the final snapshot it
        names re-dated to the settlement's move plus the policy's offset (L1-3; NFR3.12
        counts 30 days from the settlement). On a settled record, a re-date that was cut
        short, it goes straight to the re-date."""
        record = self.machine.require()
        if record["state"] not in ("switched", "settled"):
            raise OperationsError("CONFLICT", current={"reasonKey": "cutover-not-switched",
                                                       "state": record["state"]})
        self._approval_first(record, approval_id, "settlement")
        approval = self._subject(approval_id, subject, "settlement")
        offset = self._rule(subject, "finalSnapshotDisposalSeconds",
                            "final_snapshot_disposal_seconds")
        if record["state"] == "switched":
            record = self.machine.settle(approval["approvalId"])
        copy_id = subject.get("finalSnapshotCopyId")
        if copy_id is None:
            return {"state": record["state"], "finalSnapshotRedated": False,
                    "reason": "final-snapshot-not-recorded"}
        date = _parse(record["settledAt"]) + dt.timedelta(seconds=offset)
        return {"state": record["state"],
                **self._redate_final_snapshot(str(copy_id), date, approval, "settle")}

    def date_final_snapshot(self, approval_id, subject: dict) -> dict:
        """`cutover date-final-snapshot`, after an abort (L1-3, L1-66): your disposal-date
        decision dates the aborted attempt's completed final snapshot 30 days after the
        abort, through the agent's `set-date`; until then the next start waits
        (`final-snapshot-awaiting-date`)."""
        from .decide import aborted_final_snapshot

        record = self.machine.require()
        if record["state"] not in ("rehearsing", "ready-to-switch"):
            raise OperationsError("CONFLICT", current={"reasonKey": "cutover-state-differs",
                                                       "state": record["state"]})
        self._approval_first(record, approval_id, "disposal-date")
        approval = self._subject(approval_id, subject, "disposal-date")
        copy = aborted_final_snapshot(self.ledger, record)
        if copy is None:
            raise OperationsError("CONFLICT", current={"reasonKey": "no-aborted-final-snapshot"})
        date = _parse(record["abortStartedAt"]) + dt.timedelta(
            seconds=self.policy.final_snapshot_disposal_seconds)
        if subject.get("finalSnapshotDisposeAfter") != utc_text(date):
            raise OperationsError("INVALID_INPUT", current={
                "reasonKey": "decided-rule-differs", "rule": "finalSnapshotDisposeAfter"})
        if subject.get("finalSnapshotCopyId") != copy["copyId"]:
            raise OperationsError("CONFLICT", current={"reasonKey": "decision-subject-differs"})
        return {"state": record["state"], **self._redate_final_snapshot(
            copy["copyId"], date, approval, "date-final-snapshot")}

    def _redate_final_snapshot(self, copy_id: str, computed: dt.datetime, approval: dict,
                               word: str) -> dict:
        """The final snapshot re-dated (settlement and the disposal-date decision): the
        earlier of the computed date and the copy's current date. When the computed date
        is not earlier, nothing is sent or recorded and the current date is answered; a
        closed copy is left alone (`final-snapshot-closed`). Otherwise, after the approval
        read from the ledger is checked against its step and digest (security-design § 9's
        check, made here as `rollback-copy`'s path makes it), the agent's in-person
        `set-date` runs for each of the copy's three parts with the decision's receipt and
        digest, and Step 64(i)'s re-date version is recorded on that receipt. A refusal
        answers why, and running the word again resumes the re-date."""
        from backend.modules.operations.retained_copies import is_open

        def refused(reason: str) -> dict:
            return {"finalSnapshotRedated": False, "finalSnapshotCopyId": copy_id,
                    "reason": reason, "offered": [word]}

        copy = self.copies.get(copy_id)
        if copy is None or copy["kind"] != "v1-final-snapshot":
            return refused("final-snapshot-not-recorded")
        if not is_open(copy):
            return {"finalSnapshotRedated": False, "finalSnapshotCopyId": copy_id,
                    "reason": "final-snapshot-closed"}
        if computed >= _parse(copy["disposeAfter"]):
            return {"finalSnapshotRedated": False, "finalSnapshotCopyId": copy_id,
                    "finalSnapshotDisposeAfter": copy["disposeAfter"]}
        held = self.ledger.get("maintainer-approval", str(approval["approvalId"]))
        if held is None or held["step"] != approval["step"] or (
            held["subjectDigest"] != approval["subjectDigest"]
        ):
            return refused("decision-subject-differs")
        reader = self.platform.snapshot_parts
        agent = self.platform.agent
        if reader is None or agent is None:
            return refused("snapshot-parts-unwired" if reader is None else "agent-unwired")
        try:
            parts = reader(copy_id)
        except Exception as error:  # noqa: BLE001 - any failure: the word is run again
            return refused(getattr(error, "reason", None) or "snapshot-parts-unreadable")
        decided = {"date": computed.isoformat(), "receipt": held["operatorReceiptRef"],
                   "subjectDigest": held["subjectDigest"]}
        for name in sorted(parts):
            try:
                agent("set-date", {"path": parts[name]["path"], "decided": decided},
                      via="in-person")
            except Exception as error:  # noqa: BLE001 - a refusal keeps its key
                reason = getattr(error, "reason", None)
                if reason == "decided-date-not-earlier":
                    continue  # this part already holds that date
                return refused(reason if isinstance(reason, str) else "set-date-failed")
        record = self.copies.redated(copy_id, dispose_after=computed, approval=held)
        return {"finalSnapshotRedated": True, "finalSnapshotCopyId": copy_id,
                "finalSnapshotDisposeAfter": record["disposeAfter"]}

    def rehearse_restart(self, approval_id) -> dict:
        """v1's restart rehearsed on your decision: maintenance, every v1 named service
        stopped and started from its fixed checkout, v1's health locally, the route back,
        then v1's health and a signed-out page through the public address (BR9.16)."""
        record = self.machine.require()
        self._approval_first(record, approval_id, "v1-restart-rehearsal")
        checkout = self.platform.evidence.v1_checkout()
        if checkout is None:
            raise OperationsError("CONFLICT", current={"reasonKey": "v1-checkout-not-fixed"})
        attempt = {**record, "approvals": [*record["approvals"], str(approval_id)]}
        receipts: list[dict] = []
        replayed: list[bool] = []
        started = ready = None
        try:
            receipts.append(self._effect("platform.tunnel.route", "tunnel",
                                         {"origin": "maintenance"},
                                         key=self._key(attempt, "rehearse-maintenance")))
            for action in ("stop", "start"):
                for label in self.platform.v1_labels:
                    if action == "start" and started is None:
                        # v1's restart is timed from its first start (NFR8.6, L1-59).
                        started = self.clock()
                    receipts.append(self._effect(
                        "platform.service.control", label, {"label": label, "action": action},
                        key=self._key(attempt, f"rehearse-{action}:{label}"),
                        replayed=replayed if action == "start" else None))
            # v1's local health waited for, every 5 s for up to 10 minutes (L1-59).
            if not self.wait_v1_ready()["ready"]:
                raise StepFailed("v1-restart-failed")
            ready = self.clock()
            receipts.append(self._effect("platform.tunnel.route", "tunnel", {"origin": "v1-web"},
                                         key=self._key(attempt, "rehearse-route-v1")))
            if not (self.platform.public("v1-health") and self.platform.public("v1-signed-out")):
                raise StepFailed("v1-not-answering-publicly")
        except StepFailed as failure:
            return {"state": record["state"], "rehearsed": False, "reason": failure.reason}
        measured = self._restart_seconds(record, str(approval_id), started, ready,
                                         replayed=any(replayed))
        record = self.machine.record_restart_rehearsal(approval_id, commit=checkout["commit"],
                                                       receipts=receipts)
        self._write_evidence(self._rehearsal_evidence(record), {
            "cutoverId": record["cutoverId"], "commit": checkout["commit"],
            "fingerprint": checkout["fingerprint"],
            "rehearsedAt": record["v1RestartRehearsedAt"],
            "receipts": [item["receiptId"] for item in receipts],
            "approvalId": str(approval_id), **measured})
        return {"state": record["state"], "rehearsed": True,
                "rehearsedAt": record["v1RestartRehearsedAt"], **measured}

    @staticmethod
    def _rehearsal_evidence(record: dict) -> str:
        return f"restart-rehearsal-{record['cutoverId']}.json"

    def _restart_seconds(self, record: dict, approval_id: str, started, ready, *,
                         replayed: bool) -> dict:
        """v1's own restart seconds at the rehearsal, from its first start to its first
        ready answer, to a tenth of a second (NFR8.6, L1-59). When a start replayed an
        earlier run's receipt, nothing restarted in this run: the figure the evidence
        file already holds for this approval is kept, or none was measured."""
        if replayed:
            kept = self._read_evidence(self._rehearsal_evidence(record)) or {}
            if kept.get("approvalId") == approval_id and isinstance(
                    kept.get("v1RestartSeconds"), (int, float)):
                return {"v1RestartSeconds": kept["v1RestartSeconds"],
                        "v1RestartStartedAt": kept.get("v1RestartStartedAt"),
                        "v1RestartMeasured": True}
            return {"v1RestartSeconds": None, "v1RestartStartedAt": None,
                    "v1RestartMeasured": False}
        return {"v1RestartSeconds": round((ready - started).total_seconds(), 1),
                "v1RestartStartedAt": utc_text(started), "v1RestartMeasured": True}

    # --- evidence files ---------------------------------------------------------------------

    def _write_evidence(self, name: str, value: dict) -> str:
        folder = self.platform.evidence_folder
        folder.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = folder / name
        payload = json.dumps(value, sort_keys=True).encode()
        pending = path.with_name(path.name + ".pending")
        descriptor = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW,
                             0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(pending, path)
        return f"evidence:cutover/{name}:{hashlib.sha256(payload).hexdigest()[:16]}"

    def _read_evidence(self, name: str) -> dict | None:
        try:
            descriptor = os.open(self.platform.evidence_folder / name,
                                 os.O_RDONLY | os.O_NOFOLLOW)
        except OSError:
            return None
        with os.fdopen(descriptor, "rb") as stream:
            return json.loads(stream.read(MAX_INPUT))


def rehearsal_fingerprint_reader(folder: Path) -> Callable[[str], str | None]:
    """The fingerprint the latest restart rehearsal recorded, by cutover."""

    def read(cutover_id: str) -> str | None:
        try:
            descriptor = os.open(folder / f"restart-rehearsal-{cutover_id}.json",
                                 os.O_RDONLY | os.O_NOFOLLOW)
        except OSError:
            return None
        with os.fdopen(descriptor, "rb") as stream:
            value = json.loads(stream.read(MAX_INPUT))
        return value.get("fingerprint") if isinstance(value, dict) else None

    return read


@dataclass
class V1Checkout:
    """v1's fixed checkout: its commit, and a fingerprint of the checkout's state and of
    v1's service definitions, so any later change voids the restart rehearsal (BR9.16)."""

    path: Path
    definitions: tuple[Path, ...]
    run: Callable = field(default=None)

    def __call__(self) -> dict | None:
        import subprocess

        run = self.run or subprocess.run
        head = run(["git", "-C", str(self.path), "rev-parse", "HEAD"], capture_output=True,
                   timeout=30, check=False)
        state = run(["git", "-C", str(self.path), "status", "--porcelain"],
                    capture_output=True, timeout=30, check=False)
        if head.returncode != 0 or state.returncode != 0:
            return None
        commit = head.stdout.decode().strip()
        if len(commit) != 40:
            return None
        digest = hashlib.sha256(commit.encode() + b"\0" + state.stdout)
        for definition in self.definitions:
            try:
                digest.update(definition.name.encode() + b"\0" + definition.read_bytes())
            except OSError:
                digest.update(definition.name.encode() + b"\0missing")
        return {"commit": commit, "fingerprint": digest.hexdigest(),
                "clean": not state.stdout.strip()}


def run_word(tool: CutoverTool, word: str, document: dict, *, kind: str | None = None,
             in_person=None) -> dict:
    """One cutover word over the given tool. `decide <kind>` records your decision for
    the command that takes it, in two calls (`cutover.decide`), through `in_person`."""
    if word == "decide":
        from .decide import CutoverDecisions

        if in_person is None:
            raise OperationsError("DEPENDENCY_UNAVAILABLE",
                                  current={"reasonKey": "decisions-unwired"})
        return CutoverDecisions(tool, in_person).run(kind, document)
    if kind is not None:
        raise OperationsError("INVALID_INPUT", current={"reasonKey": "word-or-input-refused"})
    allowed = {
        "status": set(), "begin": set(), "check": set(),
        "start": {"approvalId", "subject"}, "open": {"approvalId", "subject"},
        "abort": {"reason"}, "rollback": {"approvalId", "subject"},
        "cancel-rollback": {"approvalId"}, "retry-copy": {"replacementApprovalId"},
        "waive-copy": {"approvalId", "subject"}, "settle": {"approvalId", "subject"},
        "rehearse-restart": {"approvalId"}, "v1-stores-deleted": {"copyId"},
        "date-final-snapshot": {"approvalId", "subject"},
        "provider-previews": {"provider", "digest"},
        "provider-decision": {"approvalId", "subject"},
        "provider-failed": {"provider"},
    }
    if word not in allowed or not set(document) <= allowed[word]:
        raise OperationsError("INVALID_INPUT", current={"reasonKey": "word-or-input-refused"})
    if word == "status":
        return tool.status()
    if word == "begin":
        if getattr(tool.platform.operator, "standing", False):
            raise OperationsError("FORBIDDEN", current={"reasonKey": "in-person-required"})
        return tool.begin()
    if word == "check":
        return tool.check()
    if word == "start":
        return tool.start(document.get("approvalId"), document.get("subject"))
    if word == "open":
        return tool.open(document.get("approvalId"), document.get("subject") or {})
    if word == "abort":
        reason = str(document.get("reason", "operator-abort"))
        return tool.abort(reason=reason if reason.replace("-", "").isalnum() else "operator-abort")
    if word == "rollback":
        return tool.rollback(document.get("approvalId"), document.get("subject") or {})
    if word == "cancel-rollback":
        return tool.cancel_rollback(document.get("approvalId"))
    if word == "retry-copy":
        return tool.retry_copy(replacement=document.get("replacementApprovalId"))
    if word == "waive-copy":
        return tool.waive_copy(document.get("approvalId"), document.get("subject") or {})
    if word == "settle":
        return tool.settle(document.get("approvalId"), document.get("subject") or {})
    if word == "date-final-snapshot":
        return tool.date_final_snapshot(document.get("approvalId"),
                                        document.get("subject") or {})
    if word == "v1-stores-deleted":
        return tool.v1_stores_deleted(document.get("copyId"))
    if word == "provider-previews":
        return tool.provider_previews(document)
    if word == "provider-decision":
        return tool.provider_decision(document.get("approvalId"), document.get("subject"))
    if word == "provider-failed":
        return tool.provider_failed(document.get("provider"))
    return tool.rehearse_restart(document.get("approvalId"))


# --- the composed realm's wiring ------------------------------------------------------------

REALM_HOST = "http://127.0.0.1:18109"
REALM_V1_API = "http://127.0.0.1:18112"
REALM_PUBLIC = "https://127.0.0.1:18110"
# v1's health through the public address is its BFF's (`/bff/health`, which asks v1's
# API): v1's web answers `/health` with its 404 page (found by the cutover journeys).
PUBLIC_PATHS = {"v1-health": "/bff/health", "v1-signed-out": "/", "v2-workspace": "/"}
PROBE_SECONDS = 10


def http_probe(url: str, *, context=None, seconds: float = PROBE_SECONDS) -> int | None:
    """The status code of one GET, or None when nothing answered."""
    import urllib.error
    import urllib.request

    try:
        with urllib.request.urlopen(url, timeout=seconds, context=context) as answer:
            return answer.status
    except urllib.error.HTTPError as error:
        return error.code
    except OSError:
        return None


def ready_report(url: str = f"{REALM_HOST}/health/ready") -> dict | None:
    import urllib.error
    import urllib.request

    try:
        with urllib.request.urlopen(url, timeout=PROBE_SECONDS) as answer:
            return json.loads(answer.read(65536))
    except urllib.error.HTTPError as error:
        try:
            return json.loads(error.read(65536))
        except ValueError:
            return None
    except (OSError, ValueError):
        return None


def realm_platform(profile, ledger, *, clock: Callable[[], dt.datetime], policy,
                   steps: Callable | None = None) -> CutoverPlatform:
    """The cutover's platform over the composed realm: its operator and store, the realm
    driver's agent words, its isolation stand-in, its probes and its evidence folder. The
    synthetic v1's parts (its fixed checkout, its account code and states) arrive with
    `v1-up` (Step 43) and the final run with the migration tool's realm wiring; until
    wired, the words that need them refuse with `DEPENDENCY_UNAVAILABLE`."""
    import ssl

    from docsuri_ops.migration.isolation_gate import IsolationGate
    from docsuri_ops.u8_platform.drivers import load_config
    from docsuri_ops.u8_platform.drivers.realm import RealmDriver
    from docsuri_ops.u8_platform.service_words import stop_expiries, stopped_v2_labels
    from docsuri_ops.u8_platform.u8_protocols import realm_facts, realm_operator

    facts = realm_facts(profile, ledger, clock=clock)
    operator = realm_operator(profile, "operator", ledger, clock=clock, facts=facts)
    config = load_config(profile.effects_root)
    driver = RealmDriver(config)
    folder = profile.run_root / "evidence" / "cutover"
    certificate = profile.run_root / "service-operations-tls.crt"
    context = ssl.create_default_context(cafile=str(certificate)) if certificate.exists() else None

    def public(kind: str) -> bool:
        return http_probe(REALM_PUBLIC + PUBLIC_PATHS[kind], context=context) == 200

    def missing_capabilities() -> list[str]:
        report = ready_report()
        if report is None:
            return ["readiness-unreadable"]
        return sorted({*report.get("missing", []), *report.get("degraded", [])})

    def verification(run_id: str) -> dict | None:
        value = None
        try:
            descriptor = os.open(profile.run_root / "verification" / f"{run_id}.json",
                                 os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(descriptor, "rb") as stream:
                value = json.loads(stream.read(MAX_INPUT))
        except (OSError, ValueError):
            return None
        return value if isinstance(value, dict) else None

    checkout = config.get("v1Checkout")
    evidence = SwitchEvidence(
        verification=verification,
        v1_checkout=V1Checkout(Path(checkout), ()) if checkout else (lambda: None),
        rehearsal_fingerprint=rehearsal_fingerprint_reader(folder),
        agent_status=lambda: driver.agent_word("status", {}, via="in-person"),
        service_volume=lambda: "stand-in" if (profile.run_root / "backup-volume").is_dir()
        else "unavailable",
        isolation=IsolationGate(profile.state_root / "isolation",
                                freshness_seconds=policy.isolation_freshness_seconds,
                                clock=clock),
        rehearsal_database=lambda: facts().current_rehearsal,
    )
    from backend.modules.operations.recovery_procedures import OutcomeUnknown, ProcedureFailed

    from docsuri_ops.u8_platform.recovery_words import realm_procedures

    procedures = realm_procedures(profile, ledger, clock=clock, policy=policy,
                                  ready=lambda: True).procedures

    def first_backup(key: str) -> dict:
        """The switch's first live backup, as Workflow 5 takes a set (BR4.3, BR9.4)."""
        try:
            return procedures.take("live", "first-live", request=None, via="in-person",
                                   step="first-live", owner_key=key)
        except ProcedureFailed as failure:
            raise StepFailed(failure.reason) from None
        except OutcomeUnknown:
            raise StepFailed("effect-outcome-unknown") from None

    def create_rehearsal(name: str) -> None:
        """A rollback's new rehearsal database on the realm's instance (the migration
        tool's realm wiring: the disposable role's, with the composed template's schema)."""
        from docsuri_ops.migration.realm import RealmDatabases

        RealmDatabases.for_realm(profile.run_root).create_rehearsal(name)

    from backend.request_context import window_summaries
    from backend.u8_policy import SYNTHETIC_OPERATIONS

    latency = profile.run_root / "evidence" / "latency"

    def soak_latency(start: dt.datetime, end: dt.datetime) -> dict:
        """The host's latency lines in the run root (Step 70(d))."""
        return window_summaries(latency, start=start, end=end,
                                window_seconds=SYNTHETIC_OPERATIONS.latency_window_seconds)

    labels = profile.labels
    return CutoverPlatform(
        soak_latency=soak_latency,
        snapshot_parts=snapshot_parts_reader(profile.run_root / "evidence" / "migration",
                                             ledger, policy, clock),
        operator=operator, production="docsuri_u8", create_rehearsal=create_rehearsal,
        v1_labels=tuple(label for label in labels if label.rsplit(".", 1)[-1].startswith("v1-")),
        v2_labels=tuple(label for label in labels
                        if label.rsplit(".", 1)[-1] in ("host", "workers", "scheduler")),
        v2_ready=lambda: http_probe(f"{REALM_HOST}/health/ready") == 200,
        v1_ready=lambda: http_probe(f"{REALM_V1_API}/health") == 200,
        public=public, evidence=evidence, evidence_folder=folder,
        capabilities_missing=missing_capabilities, agent=driver.agent_word,
        first_backup=first_backup, rehearsal_copy=lambda: facts().current_rehearsal,
        steps=steps or _direct, v1_store_present=store_present(profile.run_root),
        stop_records=lambda: stop_expiries(driver.state / "stops", labels, now=clock()),
        stopped_labels=lambda: stopped_v2_labels(driver.state / "stops", labels),
    )


def snapshot_parts_reader(folder: Path, ledger, policy,
                          clock: Callable[[], dt.datetime]) -> Callable[[str], dict]:
    """A recorded snapshot copy's parts (`Snapshot.verified_parts` over the migration's
    evidence folder `folder`), checked against the digest its record holds, for the
    final snapshot's re-date (U8 plan Step 70(a))."""
    from docsuri_ops.migration.snapshot import Snapshot, SnapshotRefused

    copies = RetainedCopies(ledger, policy, clock=clock)
    snapshot = Snapshot(copies, dump=None, stream=None, index=None, objects=None,
                        evidence=folder)

    def parts(copy_id: str) -> dict:
        record = copies.get(copy_id)
        if record is None:
            raise SnapshotRefused("snapshot-not-recorded")
        return snapshot.verified_parts(record)

    return parts


def store_present(root: Path) -> Callable[[str], bool]:
    """Whether one of v1's stores' locations is still there, read-only: the realm's
    `v1-stores/*` stand-ins under its run root (production names its own paths)."""
    import re

    pattern = re.compile(r"v1-stores/[a-z0-9-]{1,32}")

    def present(location: str) -> bool:
        if not pattern.fullmatch(location):
            raise OperationsError("INVALID_INPUT",
                                  current={"reasonKey": "v1-store-location-refused"})
        try:
            os.lstat(root / location)
        except FileNotFoundError:
            return False
        return True

    return present


def production_tool(clock: Callable[[], dt.datetime], steps: Callable):
    """The cutover commands on this Mac, in person (Step 37's wiring): the ledger through
    `docsuri-ledger` (`sudo -k`), the operator with its login released in person."""
    from backend.u8_policy import PRODUCTION_OPERATIONS

    from docsuri_ops.production_wiring import (
        LedgerClient,
        production_cutover_platform,
        production_operator,
    )

    ledger = LedgerClient(via="in-person", clock=clock)
    operator = production_operator(ledger, clock=clock)
    platform = production_cutover_platform(ledger, operator, clock=clock, steps=steps)
    return CutoverTool(ledger, PRODUCTION_OPERATIONS, platform, clock=clock), ledger


def main(argv: list[str]) -> int:
    """`docsuri-ops cutover <word>` on the composed realm, or `--production` on this Mac."""
    from backend.modules.operations.ledger import Ledger
    from backend.u8_policy import SYNTHETIC_OPERATIONS

    from docsuri_ops.platform_control.errors import POLICY_UNRESOLVED, ControlError
    from docsuri_ops.production_wiring import WiringRefused
    from docsuri_ops.u8_platform.in_person import StepClock
    from docsuri_ops.u8_platform.platform_profile import U8PlatformProfile

    parser = argparse.ArgumentParser(prog="docsuri-ops cutover")
    parser.add_argument("word", choices=WORDS)
    parser.add_argument("kind", nargs="?", help="decide's kind of decision")
    parser.add_argument("--environment-file", type=Path)
    parser.add_argument("--production", action="store_true")
    args = parser.parse_args(argv)
    raw = sys.stdin.buffer.read(MAX_INPUT + 1)

    def now() -> dt.datetime:
        return dt.datetime.now(dt.UTC)

    try:
        if len(raw) > MAX_INPUT:
            raise ControlError("INVALID_INPUT", "input exceeds its bound")
        document = json.loads(raw or b"{}")
        if not isinstance(document, dict):
            raise ControlError("INVALID_INPUT", "input must be one object")
        if args.production == (args.environment_file is not None):
            raise ControlError(POLICY_UNRESOLVED,
                               "name either --production or the realm's environment file")
        clock_steps = StepClock(lambda line: sys.stderr.write(line + "\n"))

        def steps(name, bound, work):
            return clock_steps.run(name, bound, work)[0]

        from docsuri_ops.migration.words import InPerson, production_appender, realm_appender
        from docsuri_ops.u8_platform.decisions import Decisions

        if args.production:
            tool, ledger = production_tool(now, steps)
            append = production_appender(ledger)
        else:
            profile = U8PlatformProfile.realm(args.environment_file.parent)
            ledger = Ledger.open(profile.run_root / "ledger", clock=now)
            platform = realm_platform(profile, ledger, clock=now, policy=SYNTHETIC_OPERATIONS,
                                      steps=steps)
            tool = CutoverTool(ledger, SYNTHETIC_OPERATIONS, platform, clock=now)
            append = realm_appender(ledger, now)
        try:
            in_person = InPerson(Decisions(tool.platform.operator, append, clock=now))
            result = run_word(tool, args.word, document, kind=args.kind, in_person=in_person)
        finally:
            ledger.close()
    except WiringRefused as refused:
        sys.stdout.write(json.dumps({"ok": False, "reason": str(refused)}))
        return 1
    except StepFailed as failure:
        # A step's failure that reached the word: answered by its fixed key; the word
        # run again retries the step.
        sys.stdout.write(json.dumps({"ok": False, "reason": failure.reason}))
        return 1
    except ControlError as error:
        sys.stdout.write(json.dumps({"ok": False, "error": error.as_wire_error()}))
        return 1
    except OperationsError as error:
        sys.stdout.write(json.dumps({"ok": False, "code": error.code, "current": error.current}))
        return 1
    sys.stdout.write(json.dumps({"ok": True, "result": result}, sort_keys=True, default=str))
    return 0
