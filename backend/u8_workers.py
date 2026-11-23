"""The workers' one bounded pass (U8 plan Step 11; decision "The application's processes").

`CompleteWorker.run_once(limit)` runs the chained worker (`U3ControlWorker` →
`ResearchWorker` → `TopicsWorker` → `ExportWorker`), then the lifecycle `ControlWorker`
with every participant, each within its own bound, and returns their summaries. In
production a third part records the held first export's preview (Step 21). A half that
fails does not stop the others: the pass runs each, then raises `CompletePassIncomplete`
naming the failed halves, so the control loop counts it failed.
"""

from __future__ import annotations

import datetime as dt
import time
from contextlib import contextmanager

from .control_runtime import WORK_DEADLINE
from .control_worker import SET_ASIDE, ControlWorker, PendingLifecycleEvidence
from .log_events import current as current_log

# Each half's share of the control loop's 10-second work deadline.
CHAINED_SECONDS = 5.0
LIFECYCLE_SECONDS = 4.0
# The held first export's preview pass (Step 21, BR7.3), production only.
PREVIEWS_SECONDS = 1.0


class CompletePassIncomplete(RuntimeError):
    """One or both halves failed; holds only their fixed names."""

    def __init__(self, halves: tuple[str, ...]):
        super().__init__("complete worker pass failed: " + ",".join(halves))
        self.halves = halves


@contextmanager
def bounded(seconds: float):
    """A bound inside the caller's: the earlier of the two deadlines applies."""
    outer = WORK_DEADLINE.get()
    deadline = time.monotonic() + seconds
    token = WORK_DEADLINE.set(deadline if outer is None else min(outer, deadline))
    try:
        yield
    finally:
        WORK_DEADLINE.reset(token)


def chain_steps(chained, limit: int, *, model_work_in_lane: bool = False
                ) -> list[tuple[str, object]]:
    """The chained worker's own steps, innermost first, each without its inherited pass:
    U3's (corpus runs, assistance dispatch, dispositions, admission reconciliation,
    execution recovery), research's execution step and artifact expiry, the topics
    scheduler, and the export pass. A link this does not know runs whole, as built.

    With `model_work_in_lane` (production, Step 21) the model lane owns model work: the
    assistance dispatch is left out, and research's step is its housekeeping only."""
    steps: list[tuple[str, object]] = []
    worker = chained
    while worker is not None:
        inner = getattr(worker, "inherited", None)
        own: list[tuple[str, object]]
        if hasattr(worker, "export_pass"):
            own = [("export-pass", lambda w=worker: w.export_pass.run_once())]
        elif hasattr(worker, "scheduler") and inner is not None:
            own = [("digest-schedule", lambda w=worker: w.scheduler.run_once(limit=limit))]
        elif hasattr(worker, "execution") and inner is not None:
            own = [("research-execution",
                    lambda w=worker: w.execution.step() if w.execution.enabled else None),
                   ("research-expiry", lambda w=worker: w.execution.expire_artifacts())]
        elif all(hasattr(worker, name) for name in
                 ("maintenance", "dispatch", "dispositions", "admission")):
            own = [("corpus-runs", lambda w=worker: _corpus_runs(w, limit)),
                   ("assistance-dispatch", lambda w=worker: w.dispatch.run_once(limit=limit)),
                   ("dispositions", lambda w=worker: _dispositions(w)),
                   ("assistance-admissions",
                    lambda w=worker: w.admission.reconcile_admissions(limit=limit)),
                   ("assistance-execution",
                    lambda w=worker: w.admission.recover_execution(limit=limit))]
            if model_work_in_lane:
                own = [step for step in own if step[0] != "assistance-dispatch"]
            inner = None
        else:
            own = [("chained", lambda w=worker: w.run_once(limit=limit))]
            inner = None
        steps = own + steps
        worker = inner
    return steps


def _corpus_runs(worker, limit: int) -> int:
    executed = 0
    for run in worker.maintenance.pending_runs(limit=limit):
        try:
            worker.maintenance.execute(run["id"])
            executed += 1
        except (PermissionError, ValueError):
            continue  # not claimable; the durable row stays inspectable (U3's rule)
    return executed


def _dispositions(worker) -> int:
    try:
        return worker.dispositions.consume(limit=50)["applied"]
    except (PermissionError, ValueError):
        return 0  # U3's rule: an unconsumable disposition waits, counted as none


class CompleteWorker:
    def __init__(
        self, chained, lifecycle=None, *, previews=None,
        chained_seconds: float = CHAINED_SECONDS, lifecycle_seconds: float = LIFECYCLE_SECONDS,
        set_aside=None, model_work_in_lane: bool = False,
    ):
        if not (0 < chained_seconds <= 10 and 0 < lifecycle_seconds <= 10):
            raise ValueError("each half needs a finite bound")
        if model_work_in_lane and set_aside is None:
            raise ValueError("a pass whose model work is the lane's runs step by step")
        # Step 21: production's model work is the model lane's (`u8_model_lane`).
        self.model_work_in_lane = model_work_in_lane
        self.chained = chained
        self.lifecycle = lifecycle
        self.previews = previews
        # The person's decision of 2026-10-23 ("Set it aside, record it"): in the two
        # complete realms a recorder `(kind, identity, error)`. Each of the chained
        # worker's steps then runs on its own; a step whose item fails is recorded as an
        # operations incident and gives up its turn, the rest of the pass carries on, and
        # the item is retried next pass under its own built attempt rules. None keeps the
        # built chain, where one failure ends the half.
        if (lifecycle is not None and set_aside is not None
                and not isinstance(lifecycle, CompleteLifecycleWorker)):
            raise TypeError("only the complete lifecycle worker sets an item aside")
        self.set_aside = set_aside
        if lifecycle is not None and set_aside is not None:
            lifecycle.set_aside = set_aside
        self.bounds = {"chained": chained_seconds, "lifecycle": lifecycle_seconds,
                       "previews": PREVIEWS_SECONDS}

    def _chained_steps(self, limit: int) -> dict:
        done, aside = [], []
        for name, step in chain_steps(self.chained, limit,
                                      model_work_in_lane=self.model_work_in_lane):
            try:
                step()
                done.append(name)
            except Exception as error:  # noqa: BLE001 - recorded by kind and identity only
                self.set_aside(name, "pass", error)
                aside.append(name)
        return {"steps": done, "setAside": aside}

    def run_once(self, limit: int = 1) -> dict:
        summaries, failed = {}, []
        chained = self.chained
        if self.set_aside is not None:
            chained = _Steps(self._chained_steps)
        halves = [("chained", chained)]
        if self.lifecycle is not None:
            halves.append(("lifecycle", self.lifecycle))
        if self.previews is not None:
            halves.append(("previews", self.previews))
        for name, worker in halves:
            try:
                with bounded(self.bounds[name]):
                    summaries[name] = worker.run_once(limit=limit)
            except Exception as error:  # noqa: BLE001 - reduced to its type below
                failed.append(name)
                current_log().exception("workers", "pass.half-failed", error, state=name)
        if failed:
            raise CompletePassIncomplete(tuple(failed))
        return summaries


class _Steps:
    """The chained half run step by step (`CompleteWorker._chained_steps`)."""

    def __init__(self, run):
        self._run = run

    def run_once(self, limit: int = 1) -> dict:
        return self._run(limit)


# --- The complete realms' lifecycle worker (the person's decision of 2026-10-24) ---------

INVALID_RETENTION_DATE = "retention-date-invalid"


def retention_date(value):
    """A participant's retention date (BR2.5) as an aware datetime: an aware datetime as
    it is, an ISO 8601 string with its offset parsed. Anything else, a naive time
    included, is refused as a pending reason, so the scope records why and the pass goes
    on."""
    if isinstance(value, str):
        try:
            value = dt.datetime.fromisoformat(value)
        except ValueError:
            raise PendingLifecycleEvidence(INVALID_RETENTION_DATE) from None
    if not isinstance(value, dt.datetime) or value.tzinfo is None:
        raise PendingLifecycleEvidence(INVALID_RETENTION_DATE)
    return value


_HOOKS = ("_open_requests", "_guarded", "_acknowledgement_options")


class CompleteLifecycleWorker(ControlWorker):
    """U2's lifecycle `ControlWorker` with the complete realms' parts (BR2.1–BR2.5):

    - the ResearchWorkspace, ApprovedExport and ServiceOperations participants, with the
      composition's clock for ApprovedExport's;
    - the waiting-part selection (your decision of 2026-10-22): a request whose open
      parts all wait on a participant that is not ready is passed over, spends no attempt
      and holds back no later request;
    - the set-aside recorder (your decision of 2026-10-23): an item whose processing
      fails is recorded and gives up its turn while the pass carries on;
    - each part's retention date, handed to `CompleteLifecycleService.acknowledge`.

    It refuses a lifecycle service, bare or behind `GatedLifecycle`, that is not
    `CompleteLifecycleService`, and a U2 worker that lacks one of its hooks."""

    _OPEN_REQUESTS = (
        "SELECT r.id,r.account_id,r.action,r.accepted_at,r.origin_request_id "
        "FROM accounts.lifecycle_request r "
        "JOIN accounts.account a ON a.id=r.account_id "
        "WHERE r.revision=a.lifecycle_revision AND r.disposition<>'complete' "
        "AND r.manifest_revision=%s AND EXISTS (SELECT 1 FROM accounts.lifecycle_scope s "
        "WHERE s.request_id=r.id AND s.disposition<>'complete' AND s.attempts<3 "
        "AND (s.lease_until IS NULL OR s.lease_until<=clock_timestamp())) "
    )

    # A recorder `(kind, identity, error)` the composition sets; None keeps the built
    # behaviour, where a failure ends the pass.
    set_aside = None

    def __init__(self, entry, lifecycle, personalization, files, *, clock=None,
                 operations=None):
        if any(not callable(getattr(ControlWorker, hook, None)) for hook in _HOOKS):
            raise TypeError("U2's ControlWorker lacks one of its hooks")
        from backend.modules.accounts.u8_lifecycle import CompleteLifecycleService
        from backend.modules.operations.lifecycle import GatedLifecycle

        service = lifecycle.service if isinstance(lifecycle, GatedLifecycle) else lifecycle
        if not isinstance(service, CompleteLifecycleService):
            raise TypeError("the complete lifecycle worker runs U8's lifecycle service")
        super().__init__(entry, lifecycle, personalization, files)
        # The requests the current pass inspected (`run_once`).
        self._inspected: list = []
        from backend.modules.export.control_lifecycle import ExportLifecycleParticipant
        from backend.modules.research.control_lifecycle import ResearchLifecycleParticipant

        self.participants["ResearchWorkspace"] = ResearchLifecycleParticipant(self.transactions)
        self.participants["ApprovedExport"] = ExportLifecycleParticipant(
            self.transactions, **({} if clock is None else {"clock": clock})
        )
        if operations is not None:
            self.participants["ServiceOperations"] = operations

    def _select(self, limit, after=None):
        """The open requests in acceptance order, `limit` of them, after `after`."""
        query, values = self._OPEN_REQUESTS, [self.lifecycle.revision]
        if after is not None:
            query += "AND (r.accepted_at,r.id)>(%s,%s) "
            values += [after["accepted_at"], after["id"]]
        return self.transactions.run(
            "accounts",
            lambda conn: conn.execute(
                query + "ORDER BY r.accepted_at,r.id LIMIT %s", (*values, limit)
            ).fetchall(),
        )

    def _waiting_participants(self) -> bool:
        """Whether a participant the manifest names can wait (ServiceOperations and
        ResearchWorkspace, through their `ready`)."""
        named = {participant for participant, _ in self.lifecycle.manifest}
        return any(
            callable(getattr(self.participants.get(name), "ready", None)) for name in named
        )

    def _waits(self, request) -> bool:
        """True when every open part of the request waits on a participant that is not
        ready, so claiming it now could only spend an attempt."""
        parts = self.transactions.run(
            "accounts",
            lambda conn: conn.execute(
                "SELECT participant,scope FROM accounts.lifecycle_scope WHERE request_id=%s "
                "AND disposition<>'complete' AND attempts<3 "
                "AND (lease_until IS NULL OR lease_until<=clock_timestamp())",
                (request["id"],),
            ).fetchall(),
        )
        for part in parts:
            ready = getattr(self.participants.get(part["participant"]), "ready", None)
            if ready is None or ready(request, part["scope"]):
                return False
        return bool(parts)

    def _requests(self, limit):
        """The first `limit` open requests in U2's order that are not only waiting.
        Candidates are read a bounded page at a time, after the last one read."""
        chosen, after = [], None
        while len(chosen) < limit:
            page = self._select(limit, after)
            for request in page:
                if not self._waits(request):
                    chosen.append(request)
                    if len(chosen) == limit:
                        break
            if len(page) < limit:
                break
            after = page[-1]
        return chosen

    def _open_requests(self, limit):
        from .u8_job_lines import STARTED, job_line

        requests = (self._requests(limit) if self._waiting_participants()
                    else self._select(limit))
        # The workers' job lines (Step 51(d), L1-6): each request the pass inspects.
        for request in requests:
            job_line(STARTED, request["id"], request["origin_request_id"])
            self._inspected.append(request)
        return requests

    def run_once(self, limit=4):
        """U2's pass, then `job.ended` for each request it inspected: `inspected`, or
        `error` when the pass raised."""
        from .u8_job_lines import ENDED, job_line

        self._inspected = []
        state = "error"
        try:
            result = super().run_once(limit=limit)
            state = "inspected"
            return result
        finally:
            inspected, self._inspected = self._inspected, []
            for request in inspected:
                job_line(ENDED, request["id"], request["origin_request_id"], state)

    def _guarded(self, kind: str, identity, work):
        if self.set_aside is None:
            return work()
        try:
            return work()
        except PendingLifecycleEvidence:
            raise
        except Exception as error:  # noqa: BLE001 - recorded by kind and identity only
            self.set_aside(kind, str(identity), error)
            return SET_ASIDE

    def _acknowledgement_options(self, result) -> dict:
        """A part retained by policy may report the date it is gone (BR2.5)."""
        if result.get("retainedUntil") is None:
            return {}
        return {"retained_until": retention_date(result["retainedUntil"])}
