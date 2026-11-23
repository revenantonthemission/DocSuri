"""Service incidents in the ledger and the tolerance watcher (U8 plan Step 15; BR3.7, O3,
NFR9.3).

The ServiceIncident machine (functional-spec.md § State machine — ServiceIncident) lives
in the operations ledger, so a production restore never erases the incident that
caused it. There is at most one incident not yet resolved per (environment, capability);
a new signal for that capability attaches to it. An incident moves open → investigating
→ recovering → resolved, and resolves only with the evidence of its kind:

- `capability-available`: every capability it names is available again, and every
  recovery it links has succeeded; never for an abort's or a rollback's incident;
- `abort-reviewed`: only the abort's incident (the CutoverRecord's `abortIncidentId`),
  and only once your review of the abort is recorded as a MaintainerApproval;
- `rollback-copy-settled`: only the rollback's copy-pending incident
  (`rollbackCopyIncidentId`), on the receipts of the copy or its waiver and the
  recreate, with no observation needed;
- `environment-stopped`: any other live incident still open when an abort or a rollback
  stops v2, with the stop's receipt.

A recovery request from an incident (L1-19, L1-64) is written in one ledger step with
the incident's own versions (`recovery_versions`): an `open` incident's `investigating`
version with the diagnosis `recovery-requested`, the request, then its `recovering`
version linking it; an incident already `investigating` or `recovering` gets only the
last. A resolved incident is refused before any request exists, and any refusal writes
nothing, so the incident stays as it was.

An abort or a rollback takes over the live `operations.cutover` incident already open,
or opens its own (BR9.5, BR9.7). The tolerance watcher runs every 60 seconds over each
capability's derived state and opens incidents by observability-design § 3.2's rules,
and when job failures are counted against a required capability that is not available.
An incident never closes because signals stopped arriving.

The ledger's own damage (your decision of 2026-10-22, BR6.10). A damaged ledger cannot
hold its own incident: while it is damaged, readiness shows `operations.ledger` as
unavailable and the watcher writes a counted `incident.unrecordable` line, appending
nothing. The ledger's repair records the incident (`ledger-damaged`, opened at the time
the damage was first found; `ledger_cli`), and the watcher resolves it as
`capability-available` once the ledger check passes again, so the ledger's record of
the damage is complete.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from uuid import UUID, uuid4

from backend.u8_registry import REQUIRED

from .errors import LedgerDamaged, OperationsError
from .ledger import Ledger, utc_text

KIND = "service-incident"
CUTOVER = "operations.cutover"
ISOLATION = "platform.isolation"
LEDGER = "operations.ledger"
CAPACITY = "storage.capacity"
LEDGER_DAMAGED = "ledger-damaged"
# The diagnosis a recovery request from an open incident records (L1-19).
RECOVERY_REQUESTED = "recovery-requested"
WATCH_SECONDS = 60
MAX_CORRELATIONS = 32


def _unresolved(record: dict) -> bool:
    return record["state"] != "resolved"


class Incidents:
    def __init__(self, ledger: Ledger, *, environment: str):
        if environment not in ("rehearsal", "live"):
            raise ValueError("environment outside the registered set")
        self.ledger, self.environment = ledger, environment

    # --- reading -------------------------------------------------------------------

    def get(self, incident_id) -> dict | None:
        return self.ledger.get(KIND, str(incident_id))

    def open_for(self, capability: str, environment: str | None = None) -> dict | None:
        environment = environment or self.environment
        for record in self.ledger.records(KIND):
            if (
                _unresolved(record) and record["environment"] == environment
                and capability in record["capabilities"]
            ):
                return record
        return None

    def role(self, incident_id) -> str:
        """`abort`, `rollback-copy` or `ordinary`, from the CutoverRecord."""
        return _role(self.ledger, str(incident_id))

    # --- signals -------------------------------------------------------------------

    def signal(self, capability: str, opened_by: str, *, correlation: str | None = None,
               environment: str | None = None) -> dict:
        """Open an incident for the capability, or attach the signal to the open one."""
        environment = environment or self.environment
        now = utc_text(self.ledger.clock())

        def step(view):
            current = next((
                record for record in view.records(KIND)
                if _unresolved(record) and record["environment"] == environment
                and capability in record["capabilities"]
            ), None)
            if current is not None:
                correlations = list(current["correlationIds"])
                if correlation is not None and correlation not in correlations:
                    correlations = (correlations + [correlation])[-MAX_CORRELATIONS:]
                if correlations == current["correlationIds"]:
                    return current
                revision = view.revision(KIND, current["incidentId"])
                record = {**current, "revision": revision + 1, "correlationIds": correlations}
                view.append(KIND, record, expect_revision=revision)
                return record
            record = {
                "incidentId": str(uuid4()), "environment": environment, "revision": 1,
                "capabilities": [capability],
                "correlationIds": [] if correlation is None else [correlation],
                "state": "open", "openedAt": now, "openedBy": opened_by,
                "recoveryRequestIds": [], "evidenceRefs": [],
            }
            view.append(KIND, record, expect_revision=0)
            return record

        return self.ledger.atomic(step)

    def take_over_cutover(self, opened_by: str, *, correlation: str | None = None) -> dict:
        """An abort (`switch-aborted`) or a rollback whose copy cannot be completed
        (`rollback-copy-pending`) takes over the live operations.cutover incident
        already open, or opens its own."""
        if opened_by not in ("switch-aborted", "rollback-copy-pending"):
            raise ValueError("only an abort or a rollback takes over the cutover incident")
        return self.signal(CUTOVER, opened_by, correlation=correlation, environment="live")

    # --- the machine -----------------------------------------------------------------

    def _move(self, incident_id, changes: Callable[[dict, object], dict]) -> dict:
        """One version of the incident, decided and appended under the ledger's lock;
        `changes(current, view)` reads only through the locked view."""
        identity = str(UUID(str(incident_id)))

        def step(view):
            current = view.get(KIND, identity)
            if current is None:
                raise OperationsError("NOT_FOUND")
            revision = view.revision(KIND, identity)
            record = {**changes(current, view), "revision": revision + 1}
            view.append(KIND, record, expect_revision=revision)
            return record

        return self.ledger.atomic(step)

    def begin_diagnosis(self, incident_id, diagnosis_key: str) -> dict:
        return self._move(incident_id,
                          lambda current, view: _diagnosed(current, diagnosis_key))

    def link_recovery(self, incident_id, request_id) -> dict:
        return self._move(incident_id, lambda current, view: _linked(current, request_id))

    def recovery_versions(self, view, incident_id, request_id) -> list[tuple]:
        """The incident's versions a recovery request from it writes, read through the
        locked `view` and appending nothing (L1-19, L1-64): for an `open` incident its
        `investigating` version with the diagnosis `recovery-requested`, then its
        `recovering` version linking the request; for one already `investigating` or
        `recovering`, only the latter. Each is `(kind, record, expected revision, ())`,
        as `append_all` takes it; the caller puts the request between the two. A
        resolved incident is CONFLICT; one the ledger does not hold, or one of the other
        environment (which this environment's 운영 never lists, as `_expected` treats
        another environment's backup set), NOT_FOUND."""
        try:
            identity = str(UUID(str(incident_id)))
        except ValueError:
            raise OperationsError("NOT_FOUND") from None
        current = view.get(KIND, identity)
        if current is None or current.get("environment") != self.environment:
            raise OperationsError("NOT_FOUND")
        if current["state"] == "resolved":
            raise OperationsError("CONFLICT")
        revision = view.revision(KIND, identity)
        versions = []
        if current["state"] == "open":
            current = {**_diagnosed(current, RECOVERY_REQUESTED), "revision": revision + 1}
            versions.append((KIND, current, revision, ()))
            revision += 1
        linked = {**_linked(current, request_id), "revision": revision + 1}
        versions.append((KIND, linked, revision, ()))
        return versions

    def recovery_failed(self, incident_id) -> dict:
        def change(current, view):
            if current["state"] != "recovering":
                raise OperationsError("CONFLICT")
            return {**current, "state": "investigating"}

        return self._move(incident_id, change)

    def resolve(self, incident_id, kind: str, evidence_refs: list[str], *,
                states: dict | None = None) -> dict:
        """Resolve with the evidence of `kind` (BR3.7); `states` are the capabilities'
        derived states for `capability-available`."""
        if not evidence_refs:
            raise OperationsError("EVIDENCE_REQUIRED")

        def change(current, view):
            if current["state"] == "resolved":
                raise OperationsError("CONFLICT")
            role = _role(view, current["incidentId"])
            self._require_evidence(view, current, kind, role, states or {})
            refs = list(dict.fromkeys([*current["evidenceRefs"], *evidence_refs]))[-16:]
            return {**current, "state": "resolved", "resolutionKind": kind,
                    "resolvedAt": utc_text(self.ledger.clock()), "evidenceRefs": refs}

        return self._move(incident_id, change)

    def _require_evidence(self, view, current: dict, kind: str, role: str,
                          states: dict) -> None:
        if kind == "capability-available":
            if role != "ordinary" or any(
                getattr(states.get(name), "state", None) != "available"
                for name in current["capabilities"]
            ):
                raise OperationsError("EVIDENCE_REQUIRED")
            for request in current["recoveryRequestIds"]:
                recovery = view.get("recovery-request", request)
                if recovery is None or recovery["state"] != "succeeded":
                    raise OperationsError("EVIDENCE_REQUIRED")
            if _backstop_copies_open(view, current):
                # A copy still in place past its backstop keeps its incident open until
                # it is gone (BR9.17); v1's stores once their deletion is recorded.
                raise OperationsError("EVIDENCE_REQUIRED")
        elif kind == "abort-reviewed":
            if role != "abort" or not _abort_reviewed(view, current["incidentId"]):
                raise OperationsError("EVIDENCE_REQUIRED")
        elif kind == "rollback-copy-settled":
            if role != "rollback-copy":
                raise OperationsError("EVIDENCE_REQUIRED")
        elif kind == "environment-stopped":
            if role != "ordinary" or current["environment"] != "live":
                raise OperationsError("EVIDENCE_REQUIRED")
        else:
            raise OperationsError("INVALID_ARGUMENT")


def _diagnosed(current: dict, diagnosis_key: str) -> dict:
    """The rule for a diagnosis: only an `open` incident moves to `investigating`."""
    if current["state"] != "open":
        raise OperationsError("CONFLICT")
    return {**current, "state": "investigating", "diagnosisKey": diagnosis_key}


def _linked(current: dict, request_id) -> dict:
    """The rule for a link: an `investigating` or `recovering` incident moves to
    `recovering` with the request among its recovery requests."""
    if current["state"] not in ("investigating", "recovering"):
        raise OperationsError("CONFLICT")
    linked = list(dict.fromkeys([*current["recoveryRequestIds"], str(request_id)]))
    return {**current, "state": "recovering", "recoveryRequestIds": linked}


BACKSTOP_SUFFIX = ":backstop"


def _backstop_copies_open(reader, incident: dict) -> bool:
    """Whether a retained copy whose backstop signal the incident carries
    (`retained-copy:<copyId>:backstop`, the disposal pass's) is still open."""
    from .retained_copies import KIND as COPY
    from .retained_copies import is_open

    for correlation in incident["correlationIds"]:
        if not (correlation.startswith(COPY + ":") and correlation.endswith(BACKSTOP_SUFFIX)):
            continue
        copy_id = correlation[len(COPY) + 1:-len(BACKSTOP_SUFFIX)]
        record = reader.get(COPY, copy_id)
        if record is not None and is_open(record):
            return True
    return False


def _role(reader, incident_id: str) -> str:
    """`abort`, `rollback-copy` or `ordinary`, from the CutoverRecord."""
    for cutover in reader.records("cutover-record"):
        if cutover.get("abortIncidentId") == incident_id:
            return "abort"
        if cutover.get("rollbackCopyIncidentId") == incident_id:
            return "rollback-copy"
    return "ordinary"


def _abort_reviewed(reader, incident_id: str) -> bool:
    """Your review of the abort whose incident this is, recorded as a decision."""
    cutovers = [
        record for record in reader.records("cutover-record")
        if record.get("abortIncidentId") == incident_id
    ]
    return any(
        approval["step"] == "abort-review" and approval["decision"] == "approved"
        and approval["subjectRef"] == cutover["cutoverId"]
        for cutover in cutovers
        for approval in reader.records("maintainer-approval")
    )


class ToleranceWatcher:
    """Opens incidents by observability-design § 3.2's tolerances, every 60 seconds."""

    def __init__(self, incidents: Incidents, readiness, policy,
                 clock: Callable[[], dt.datetime], *, log=None):
        self.incidents, self.readiness, self.policy, self.clock = (
            incidents, readiness, policy, clock
        )
        self.since: dict[str, dt.datetime] = {}
        self.signalled: set[str] = set()
        # Signals the damaged ledger could not take, each written as one counted
        # `incident.unrecordable` line.
        self.unrecorded = 0
        self.settled: list[str] = []
        self.log = log

    def _tolerance(self, capability: str, state: str) -> int | None:
        """Seconds a state may last before an incident opens, or None for never."""
        if capability in REQUIRED:
            if state == "unavailable":
                return 0
            if state in ("degraded", "unknown", "stale"):
                return self.policy.required_incident_seconds
            return None
        if capability == CUTOVER and state == "unavailable":
            return self.policy.cutover_incident_seconds
        if capability == ISOLATION and state in ("unavailable", "unknown", "stale"):
            return self.policy.isolation_incident_seconds
        return None

    def settle_ledger_damage(self, states: dict) -> list[str]:
        """Resolve the repaired ledger's `ledger-damaged` incidents as
        `capability-available` once the ledger check passes again."""
        state = states.get(LEDGER)
        if state is None or state.state != "available":
            return []
        try:
            pending = [
                record["incidentId"] for record in self.incidents.ledger.records(KIND)
                if _unresolved(record) and record["openedBy"] == LEDGER_DAMAGED
                and record["environment"] == self.incidents.environment
            ]
        except LedgerDamaged:
            return []
        observed = ("" if state.observed_at is None
                    else ":" + utc_text(state.observed_at))
        settled = []
        for incident in pending:
            try:
                self.incidents.resolve(incident, "capability-available",
                                       [f"observation:{LEDGER}{observed}"], states=states)
            except OperationsError:
                continue  # resolved meanwhile, or another capability it names is not back
            settled.append(incident)
        return settled

    def run_once(self, now: dt.datetime | None = None) -> list[str]:
        now = now or self.clock()
        states = self.readiness.states()
        self.settled = self.settle_ledger_damage(states)
        opened = []
        for capability, state in sorted(states.items()):
            tolerance = self._tolerance(capability, state.state)
            if tolerance is None:
                self.since.pop(capability, None)
                self.signalled.discard(capability)
                continue
            since = self.since.setdefault(capability, now)
            if capability in self.signalled:
                continue
            reason = None
            # storage.capacity's counts are failed connections and transactions, not job
            # failures (Step 58(g), L1-29): only its tolerance opens an incident.
            if capability in REQUIRED and capability != CAPACITY and state.error_count:
                reason = "job-failure-correlated"
            elif (now - since).total_seconds() >= tolerance:
                reason = "tolerance-exceeded"
            if reason is None:
                continue
            try:
                record = self.incidents.signal(
                    capability, reason, correlation=f"capability:{capability}:{state.state}"
                )
            except LedgerDamaged as error:
                # The ledger itself is damaged: nothing can be recorded in it. The
                # damage shows as operations.ledger unavailable on every read.
                self.unrecorded += 1
                from backend.log_events import current

                (self.log or current()).exception(
                    "operations", "incident.unrecordable", error, state=capability
                )
                continue
            self.signalled.add(capability)
            opened.append(record["incidentId"])
        return opened

    async def run(self, stopping, *, seconds: float = WATCH_SECONDS) -> None:
        import asyncio

        while not stopping.is_set():
            try:
                await asyncio.to_thread(self.run_once)
            except Exception as error:  # noqa: BLE001 - the watcher keeps watching
                from backend.log_events import current

                (self.log or current()).exception("operations", "watcher.failed", error)
            try:
                await asyncio.wait_for(stopping.wait(), seconds)
            except TimeoutError:
                pass
