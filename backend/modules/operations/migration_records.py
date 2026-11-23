"""The migration's own records in the operations ledger (U8 plan Step 31; BR8.9–BR8.15,
BR9.2, functional-spec.md § State machine — MigrationRun).

The migration tool owns only its run, parity and misfit records; every imported record
is its owner's (BR1.6, BR8.2). Each change is one version appended under the ledger's
lock:

- `MigrationRuns`: the MigrationRun machine. A run starts only when no other run is
  active: a dry run on your go-ahead (`dry-run-go-ahead`), a final run only while the
  cutover is switching; the start records the digest of the decisions current then, and
  a final run freezes them. It then moves preparing → copying → importing → verifying →
  reported → accepted or rejected, with `failed`, `interrupted` (its phase recorded) and
  a resume to exactly that phase.
- `MisfitRecord`s: one per misfit a run met, by kind, source id and reason; the kinds Q13
  did not name are recorded once per kind with their count (the report names each id).
- `MisfitDecisions`: your decision per (kind, reason), each bound to its
  MaintainerApproval; refused while a final run's freeze holds, which ends when that run
  is rejected or fails, or the cutover aborts or rolls back after it started (BR8.9).
- `ParityReport`: the report's reference and digest, with whether it reconciles.
- `dry_run_current`: whether the latest accepted dry run ran under the decisions current
  now, which the switch requires (BR8.9, BR9.2).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Iterable
from uuid import UUID, uuid4

from .errors import OperationsError
from .ledger import Ledger, utc_text
from .ledger_records import MIGRATION_PHASES, MISFIT_REASONS, PARITY_KINDS
from .migration.misfits import DECISIONS, MAPPING_RULES, NOT_IN_SCOPE, Decisions

RUN, MISFIT, DECISION, REPORT = "migration-run", "misfit-record", "misfit-decision", (
    "parity-report")
TERMINAL = frozenset({"accepted", "rejected", "failed"})
ACTIVE = frozenset({*MIGRATION_PHASES, "reported", "interrupted"})
# Misfits per ledger step: well inside the ledger component's batch (`ledger_cli.MAX_BATCH`,
# 4,096 appends) and its 16 MiB input, a misfit record being a few hundred bytes.
MISFIT_CHUNK = 1000


def _seconds(start: str, end: str) -> int:
    """The whole seconds between two ledger times."""
    elapsed = dt.datetime.fromisoformat(end) - dt.datetime.fromisoformat(start)
    return max(0, int(elapsed.total_seconds()))


def _timed(record: dict, current: dict, state: str, now: str) -> None:
    """Each phase's last start and seconds, and the run's duration (NFR8.8, U8 plan Step
    68(g)): entering a phase or `reported` from another state stamps its start; leaving a
    phase for another state stamps its last attempt's whole seconds; `reported` stamps
    `reportedAt` and, from `snapshotStartedAt`, `durationSeconds`; an interruption adds
    one to `interruptions`."""
    previous = current["state"]
    if state == previous:
        return
    started = dict(record.get("phaseStartedAt") or {})
    if previous in MIGRATION_PHASES and previous in started:
        seconds = dict(record.get("phaseSeconds") or {})
        seconds[previous] = _seconds(started[previous], now)
        record["phaseSeconds"] = seconds
    if state in (*MIGRATION_PHASES, "reported"):
        started[state] = now
        record["phaseStartedAt"] = started
    if state == "reported":
        record["reportedAt"] = now
        if "snapshotStartedAt" in record:
            record["durationSeconds"] = _seconds(record["snapshotStartedAt"], now)
    if state == "interrupted":
        record["interruptions"] = int(record.get("interruptions", 0)) + 1


def _latest(records: list[dict], kind: str) -> dict | None:
    """The latest accepted run of a kind: by its start, then by the ledger's order (runs
    are listed in the order they were first recorded)."""
    accepted = [(record["startedAt"], index, record) for index, record in enumerate(records)
                if record["kind"] == kind and record["state"] == "accepted"]
    return max(accepted, key=lambda item: item[:2])[2] if accepted else None


class MigrationRuns:
    def __init__(self, ledger: Ledger, *, clock: Callable | None = None):
        self.ledger = ledger
        self.clock = clock or ledger.clock

    # --- reading -------------------------------------------------------------------

    def get(self, run_id) -> dict | None:
        return self.ledger.get(RUN, str(run_id))

    def require(self, run_id) -> dict:
        record = self.get(run_id)
        if record is None:
            raise OperationsError("NOT_FOUND")
        return record

    def active(self) -> dict | None:
        return next((record for record in self.ledger.records(RUN)
                     if record["state"] in ACTIVE), None)

    def latest_accepted(self, kind: str = "dry") -> dict | None:
        return _latest(self.ledger.records(RUN), kind)

    def met_pairs(self, run_id) -> set[tuple[str, str]]:
        return {(item["kind"], item["reasonKey"]) for item in self.ledger.records(MISFIT)
                if item["runId"] == str(run_id)}

    def dry_run_current(self) -> bool:
        """The latest accepted dry run ran under the decisions current now (BR9.2)."""
        accepted = self.latest_accepted("dry")
        return accepted is not None and accepted["decisionsDigest"] == Decisions.from_ledger(
            self.ledger).digest()

    def required_pairs(self) -> set[tuple[str, str]]:
        """The (kind, reason)s a final run needs decided: those the accepted dry run met,
        and those an earlier final run met before its freeze ended (BR8.9)."""
        pairs: set[tuple[str, str]] = set()
        accepted = self.latest_accepted("dry")
        if accepted is not None:
            pairs |= self.met_pairs(accepted["runId"])
        for record in self.ledger.records(RUN):
            if record["kind"] == "final" and record["state"] in ("rejected", "failed"):
                pairs |= self.met_pairs(record["runId"])
        return pairs

    # --- the machine ---------------------------------------------------------------------

    def _approved(self, view, approval_id, step: str) -> dict:
        approval = None if approval_id is None else view.get("maintainer-approval",
                                                             str(approval_id))
        if approval is None or approval["step"] != step or approval["decision"] != "approved":
            raise OperationsError("FORBIDDEN", current={"reasonKey": "decision-required"})
        return approval

    def start(self, kind: str, *, tool_commit: str, go_ahead=None,
              precondition: Callable[[object], str | None] | None = None) -> dict:
        """Start a run (`preparing`); `precondition(view)` names the first missing BR9.2
        or BR8.11 precondition the tool read, or None."""
        if kind not in ("dry", "final"):
            raise OperationsError("INVALID_INPUT")
        now = utc_text(self.clock())

        def step(view):
            if any(record["state"] in ACTIVE for record in view.records(RUN)):
                raise OperationsError("CONFLICT", current={"reasonKey": "run-active"})
            if precondition is not None:
                missing = precondition(view)
                if missing is not None:
                    raise OperationsError("CONFLICT", current={"reasonKey": missing})
            decisions = Decisions.from_records(view.records(DECISION))
            if kind == "dry":
                self._approved(view, go_ahead, "dry-run-go-ahead")
            else:
                cutovers = view.records("cutover-record")
                if not cutovers or cutovers[-1]["state"] != "switching":
                    raise OperationsError("CONFLICT", current={"reasonKey": "not-switching"})
                undecided = decisions.undecided(self._required(view))
                if undecided:
                    raise OperationsError("CONFLICT", current={
                        "reasonKey": "misfits-undecided",
                        "undecided": [f"{kind_}:{reason}" for kind_, reason in undecided]})
                accepted = self._latest_accepted(view)
                if accepted is None or accepted["decisionsDigest"] != decisions.digest():
                    raise OperationsError("CONFLICT", current={"reasonKey": "dry-run-not-current"})
                self._freeze(view, True)
            record = {
                "runId": str(uuid4()), "kind": kind,
                "target": "rehearsal" if kind == "dry" else "production",
                "toolCommit": tool_commit, "decisionsDigest": decisions.digest(),
                "state": "preparing", "startedAt": now,
                "phaseStartedAt": {"preparing": now}, "interruptions": 0,
            }
            view.append(RUN, record, expect_revision=0)
            return record

        return self.ledger.atomic(step)

    def _latest_accepted(self, view) -> dict | None:
        return _latest(view.records(RUN), "dry")

    def _required(self, view) -> set[tuple[str, str]]:
        pairs: set[tuple[str, str]] = set()
        accepted = self._latest_accepted(view)
        runs = [accepted] if accepted else []
        runs += [record for record in view.records(RUN)
                 if record["kind"] == "final" and record["state"] in ("rejected", "failed")]
        for run in runs:
            pairs |= {(item["kind"], item["reasonKey"]) for item in view.records(MISFIT)
                      if item["runId"] == run["runId"]}
        return pairs

    def _freeze(self, view, frozen: bool) -> None:
        for record in view.records(DECISION):
            if record["frozen"] != frozen:
                key = (record["kind"], record["reasonKey"])
                view.append(DECISION, {**record, "frozen": frozen},
                            expect_revision=view.revision(DECISION, key))

    def move(self, run_id, state: str, **fields) -> dict:
        """One version of the run in `state`; the schema holds the machine's moves."""
        identity = str(UUID(str(run_id)))
        now = utc_text(self.clock())

        def step(view):
            current = view.get(RUN, identity)
            if current is None:
                raise OperationsError("NOT_FOUND")
            record = {**current, **fields, "state": state}
            _timed(record, current, state, now)
            if state != "interrupted":
                record.pop("interruptedPhase", None)
            if state in TERMINAL:
                record["finishedAt"] = now
            if state == "accepted":
                record["acceptedAt"] = now
            view.append(RUN, record, expect_revision=view.revision(RUN, identity))
            if current["kind"] == "final" and state in ("rejected", "failed"):
                self._freeze(view, False)
            return record

        return self.ledger.atomic(step)

    def interrupt(self, run_id, phase: str) -> dict:
        if phase not in MIGRATION_PHASES:
            raise OperationsError("INVALID_INPUT")
        # The move itself adds one to `interruptions`, read inside its own ledger step.
        return self.move(run_id, "interrupted", interruptedPhase=phase)

    def resume(self, run_id) -> dict:
        """An interrupted run goes back to exactly the phase it stopped in (BR8.15)."""
        current = self.require(run_id)
        if current["state"] != "interrupted":
            raise OperationsError("CONFLICT", current={"state": current["state"]})
        return self.move(run_id, current["interruptedPhase"])

    def decide_report(self, run_id, approval_id) -> dict:
        """Your decision on the report: accepted only when it reconciles, and for a final
        run only with its first-met items explicitly approved (BR8.9, BR8.10)."""
        current = self.require(run_id)
        if current["state"] != "reported":
            raise OperationsError("CONFLICT", current={"state": current["state"]})
        step = "dry-run-report" if current["kind"] == "dry" else "final-report"
        approval = self.ledger.get("maintainer-approval", str(approval_id))
        if approval is None or approval["step"] != step or approval["subjectRef"] != str(run_id):
            raise OperationsError("FORBIDDEN", current={"reasonKey": "decision-required"})
        if approval["decision"] != "approved":
            return self.move(run_id, "rejected", reportApprovalId=approval["approvalId"])
        report = self.ledger.get(REPORT, str(run_id))
        if report is None or not report["reconciles"]:
            raise OperationsError("CONFLICT", current={"reasonKey": "report-not-reconciled"})
        return self.move(run_id, "accepted", reportApprovalId=approval["approvalId"])

    def end_freeze(self) -> None:
        """An abort or a rollback after a final run started ends its freeze (BR8.9)."""
        self.ledger.atomic(lambda view: self._freeze(view, False))

    # --- misfits and the report ---------------------------------------------------------

    def record_misfits(self, run_id, misfits: Iterable[tuple[str, str, str]], *,
                       new_in_final: set[tuple[str, str]] = frozenset()) -> int:
        """One MisfitRecord per misfit (a kind Q13 did not name once, with its count),
        written in steps of at most `MISFIT_CHUNK` records (review finding, Major, R15):
        a dry run over v1's corpus can name thousands, and one ledger step is one batch
        with a bound. Each misfit's key is its own, so a chunk that ran is skipped when
        the call runs again, and a call stopped between chunks completes on its rerun."""
        counted: dict[str, int] = {}
        records = []
        for kind, source, reason in misfits:
            if kind not in PARITY_KINDS or reason not in MISFIT_REASONS:
                raise OperationsError("INVALID_INPUT")
            if reason == NOT_IN_SCOPE:
                counted[kind] = counted.get(kind, 0) + 1
                continue
            records.append((kind, source, reason))
        records += [(kind, f"count:{count}", NOT_IN_SCOPE) for kind, count in counted.items()]
        run = str(run_id)

        def step(chunk, view):
            added = 0
            for kind, source, reason in chunk:
                key = (run, kind, source, reason)
                if view.get(MISFIT, key) is not None:
                    continue
                view.append(MISFIT, {"runId": run, "kind": kind, "sourceId": source,
                                     "reasonKey": reason,
                                     "newInFinal": (kind, reason) in new_in_final},
                            expect_revision=0)
                added += 1
            return added

        added = 0
        for start in range(0, len(records), MISFIT_CHUNK):
            chunk = records[start:start + MISFIT_CHUNK]
            added += self.ledger.atomic(lambda view, chunk=chunk: step(chunk, view))
        return added

    def record_report(self, run_id, *, reference: str, digest: str, kinds: int,
                      reconciles: bool) -> dict:
        record = {"runId": str(run_id), "reportRef": reference, "reportDigest": digest,
                  "kinds": kinds, "reconciles": reconciles,
                  "recordedAt": utc_text(self.clock())}

        def step(view):
            prior = view.get(REPORT, str(run_id))
            if prior is not None:
                return prior
            view.append(REPORT, record, expect_revision=0)
            return record

        return self.ledger.atomic(step)


class MisfitDecisions:
    def __init__(self, ledger: Ledger, *, clock: Callable | None = None):
        self.ledger = ledger
        self.clock = clock or ledger.clock

    def current(self) -> Decisions:
        return Decisions.from_ledger(self.ledger)

    def decide(self, kind: str, reason: str, decision: str, *, approval_id,
               mapping_rule: str | None = None) -> dict:
        """Your decision on one (kind, reason), bound to its MaintainerApproval."""
        if decision not in DECISIONS or kind not in PARITY_KINDS or reason not in MISFIT_REASONS:
            raise OperationsError("INVALID_INPUT")
        if decision == "map" and mapping_rule != MAPPING_RULES.get((kind, reason)):
            raise OperationsError("INVALID_INPUT", current={"reasonKey": "mapping-rule-unknown"})
        record = {"kind": kind, "reasonKey": reason, "decision": decision,
                  "decidedAt": utc_text(self.clock()), "approvalId": str(approval_id),
                  "frozen": False}
        if decision == "map":
            record["mappingRule"] = mapping_rule

        def step(view):
            approval = view.get("maintainer-approval", str(approval_id))
            if approval is None or approval["step"] != "misfit-decision" or approval[
                "decision"
            ] != "approved" or approval["subjectRef"] != f"{kind}:{reason}":
                raise OperationsError("FORBIDDEN", current={"reasonKey": "decision-required"})
            key = (kind, reason)
            current = view.get(DECISION, key)
            if current is not None and current["frozen"]:
                raise OperationsError("CONFLICT", current={"reasonKey": "decisions-frozen"})
            view.append(DECISION, record, expect_revision=view.revision(DECISION, key))
            return record

        return self.ledger.atomic(step)
