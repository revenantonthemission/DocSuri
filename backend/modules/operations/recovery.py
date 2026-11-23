"""Recovery requests: the RecoveryRequest machine in the operations ledger (U8 plan Step 29;
BR4.1–BR4.10, functional-spec.md § State machine — RecoveryRequest).

Every state change is one version of the request, decided and appended while the
ledger's lock is held (`Ledger.atomic`), so a check and the append it allows are one
step for every process (BR4.4):

- **Offered** (BR4.1): only `backup.create`, `restore.verify` and `restore.production`.
  The schedule requests only the first two (BR4.2); an administrator needs a current
  second factor, checked again at operator start (`mfa_current`).
- **Identity** (BR4.9): the idempotency key is the digest of origin, requester,
  operation, target, expected revision and `submissionId`. A retry of one submission
  recovers the original request; a new submission creates a new one. The expected
  revision is the environment's backup revision for `backup.create` (the number of its
  recorded BackupSets) and the chosen set's revision for a restore; a stale one is a
  conflict.
- **Admission** (BR4.4): `backup.create` and `restore.production` conflict with each
  other and with themselves, `restore.verify` only with itself. A production restore
  needs your decision approving it (`production-restore`, subject: the request), and a
  successor names the held request it replaces: the held request keeps its hold and
  the exclusion until the successor starts running, and only one successor waits at a
  time. A switch, an abort or a rollback holds the live environment; a rehearsal
  database being removed holds the rehearsal environment's backups and verifications. A
  request that cannot be admitted yet stays `requested`, holding nothing, until it is
  admitted or expires after the start bound.
- **From an incident** (L1-19, L1-64): a request naming an incident, given the
  `Incidents`, is written in the same step as the incident's `investigating` version
  (diagnosis `recovery-requested`, for an open incident) and its `recovering` version
  linking the request, in that order, through `append_all`; every check comes first, so
  a refusal writes nothing, and a replay recovers its request and appends nothing.
- **Running**: an unknown outcome leaves the request `unknown`, still active, until
  PlatformControl's receipt settles it (`settle_unknown`); it is never run again
  blindly.

The procedures that move a request through its platform effects are in
`recovery_procedures.py`; this module only keeps the machine.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from collections.abc import Callable, Iterable
from uuid import UUID, uuid4

import rfc8785

from .errors import OperationsError
from .ledger import Ledger, utc_text
from .ledger_records import ACTIVE_RECOVERY_STATES, RECOVERY_OPERATIONS

KIND = "recovery-request"
SCHEDULE_OPERATIONS = ("backup.create", "restore.verify")
TERMINAL = frozenset({"succeeded", "failed", "cancelled", "refused", "expired"})
WAITING = frozenset({"requested", "awaiting-operator"})
# The cutover states that hold the live environment's production-affecting exclusion.
LIVE_EXCLUSION = frozenset({"switching", "aborting", "rolling-back"})
# Evidence references a precondition reads; never dropped when the list is bounded.
KEPT_PREFIXES = ("recreate:", "abandon-recreate:")
MAX_EVIDENCE = 16


def idempotency_key(*, origin: str, requester: str | None, operation: str, target: str,
                    expected_revision: int, submission_id: str) -> str:
    """BR4.9's key: the digest of the six facts that make one deliberate submission."""
    return hashlib.sha256(rfc8785.dumps({
        "origin": origin, "requester": requester, "operation": operation, "target": target,
        "expectedRevision": expected_revision, "submissionId": submission_id,
    })).hexdigest()


def conflicting(left: str, right: str) -> bool:
    """`restore.verify` conflicts only with itself; the other two with each other and
    with themselves (BR4.4)."""
    if "restore.verify" in (left, right):
        return left == right
    return True


def _parse(text: str) -> dt.datetime:
    return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))


def bounded_evidence(current: Iterable[str], added: Iterable[str]) -> list[str]:
    """The evidence list with `added` appended, at most 16 entries: the oldest ordinary
    reference goes first, and a reference a precondition reads is always kept."""
    refs = list(dict.fromkeys([*current, *added]))
    while len(refs) > MAX_EVIDENCE:
        index = next((i for i, ref in enumerate(refs) if not ref.startswith(KEPT_PREFIXES)),
                     None)
        if index is None:
            raise OperationsError("INVALID_INPUT")
        refs.pop(index)
    return refs


class RecoveryRequests:
    def __init__(self, ledger: Ledger, policy, *, clock: Callable[[], dt.datetime] | None = None,
                 mfa_current: Callable[[str, str], bool] | None = None):
        """`mfa_current(requestedBy, mfaVerifiedAt)` is AccountAccess's answer to whether
        the administrator's second factor is still current (BR3.8, BR4.2)."""
        self.ledger, self.policy = ledger, policy
        self.clock = clock or ledger.clock
        self.mfa_current = mfa_current

    # --- reading -------------------------------------------------------------------

    def get(self, request_id) -> dict | None:
        return self.ledger.get(KIND, str(request_id))

    def require(self, request_id) -> dict:
        record = self.get(request_id)
        if record is None:
            raise OperationsError("NOT_FOUND")
        return record

    def active(self, environment: str | None = None) -> list[dict]:
        return [
            record for record in self.ledger.records(KIND)
            if record["state"] in ACTIVE_RECOVERY_STATES
            and (environment is None or record["environment"] == environment)
        ]

    def unknown(self, environment: str | None = None) -> list[dict]:
        return [record for record in self.active(environment) if record["state"] == "unknown"]

    def status(self, request_id) -> dict:
        """C11's `readRecoveryStatus`: the request as the ledger holds it; reading it
        never starts, advances or cancels work (A5)."""
        record = self.require(request_id)
        value = {
            name: record[name] for name in (
                "recoveryRequestId", "environment", "origin", "operation", "state",
                "evidenceRefs", "createdAt", "updatedAt",
            )
        }
        value["revision"] = str(record["revision"])
        if "incidentId" in record:
            value["incidentId"] = record["incidentId"]
        return value

    def backup_revision(self, environment: str, reader=None) -> int:
        """The environment's backup revision: the number of its recorded BackupSets."""
        source = reader or self.ledger
        return sum(1 for item in source.records("backup-set")
                   if item["environment"] == environment)

    # --- requesting -------------------------------------------------------------------

    def _check_origin(self, origin: str, operation: str, requested_by, mfa_verified_at) -> None:
        if operation not in RECOVERY_OPERATIONS:
            raise OperationsError("INVALID_INPUT", current={"reasonKey": "not-offered"})
        if origin == "schedule":
            if operation not in SCHEDULE_OPERATIONS or requested_by is not None:
                raise OperationsError("FORBIDDEN", current={"reasonKey": "not-scheduled"})
            return
        if origin != "administrator":
            raise OperationsError("INVALID_INPUT")
        if requested_by is None or mfa_verified_at is None:
            raise OperationsError("FORBIDDEN", current={"reasonKey": "mfa-required"})
        if self.mfa_current is None or not self.mfa_current(str(requested_by),
                                                            mfa_verified_at):
            raise OperationsError("FORBIDDEN", current={"reasonKey": "mfa-not-current"})

    def _expected(self, view, environment: str, operation: str, target: str) -> int:
        if operation == "backup.create":
            return self.backup_revision(environment, view)
        backup = view.get("backup-set", target)
        if backup is None or backup["environment"] != environment:
            raise OperationsError("NOT_FOUND")
        return view.revision("backup-set", target)

    def request(self, *, origin: str, operation: str, environment: str, target_id: str,
                expected_revision: int, submission_id, requested_by=None,
                mfa_verified_at: str | None = None, incident_id=None,
                incidents=None) -> dict:
        """Record a request as `requested`, or recover the one this submission made.

        Given `incidents` (an `Incidents`) and an `incident_id`, the same step also writes
        the incident's versions (L1-19, L1-64): `Incidents.recovery_versions` reads them
        through the locked view, and `append_all` writes the `investigating` version (for
        an open incident), the request and the `recovering` version in that order, after
        checking every one, so a refusal writes nothing. A replay recovers its request
        first and appends nothing. Without `incidents` the request is recorded alone."""
        self._check_origin(origin, operation, requested_by, mfa_verified_at)
        if environment not in ("rehearsal", "live"):
            raise OperationsError("INVALID_INPUT")
        submission = str(UUID(str(submission_id)))
        requester = None if requested_by is None else str(UUID(str(requested_by)))
        key = idempotency_key(origin=origin, requester=requester, operation=operation,
                              target=target_id, expected_revision=expected_revision,
                              submission_id=submission)
        now = utc_text(self.clock())

        def step(view):
            for record in view.records(KIND):
                if record["idempotencyKey"] == key:
                    return record  # a retry of this submission recovers it
                if record["submissionId"] == submission:
                    raise OperationsError("CONFLICT", current={"reasonKey": "submission-reused"})
            current = self._expected(view, environment, operation, target_id)
            if current != expected_revision:
                raise OperationsError("CONFLICT", current={"revision": current})
            record = {
                "recoveryRequestId": str(uuid4()), "revision": 1, "environment": environment,
                "origin": origin, "operation": operation, "targetId": target_id,
                "expectedRevision": expected_revision, "submissionId": submission,
                "idempotencyKey": key, "state": "requested", "evidenceRefs": [],
                "createdAt": now, "updatedAt": now,
            }
            if requester is not None:
                record["requestedBy"], record["mfaVerifiedAt"] = requester, mfa_verified_at
            if incident_id is not None and incidents is not None:
                versions = incidents.recovery_versions(view, incident_id,
                                                       record["recoveryRequestId"])
                record["incidentId"] = versions[-1][1]["incidentId"]
                view.append_all([*versions[:-1], (KIND, record, 0, ()), versions[-1]])
                return record
            if incident_id is not None:
                record["incidentId"] = str(UUID(str(incident_id)))
            view.append(KIND, record, expect_revision=0)
            return record

        return self.ledger.atomic(step)

    # --- the machine's moves ----------------------------------------------------------

    def _write(self, view, current: dict, state: str, *, evidence: Iterable[str] = (),
               receipts: tuple[dict, ...] = (), **fields) -> dict:
        revision = view.revision(KIND, current["recoveryRequestId"])
        record = {**current, **fields, "state": state, "revision": revision + 1,
                  "updatedAt": utc_text(self.clock()),
                  "evidenceRefs": bounded_evidence(current["evidenceRefs"], evidence)}
        view.append(KIND, record, expect_revision=revision, receipts=receipts)
        return record

    def _move(self, request_id, decide: Callable[[dict, object], dict | None]) -> dict:
        """`decide(current, view)` returns the new version's arguments for `_write`, or
        None to leave the request as it is; it reads only through the locked view."""
        identity = str(UUID(str(request_id)))

        def step(view):
            current = view.get(KIND, identity)
            if current is None:
                raise OperationsError("NOT_FOUND")
            change = decide(current, view)
            if change is None:
                return current
            return self._write(view, current, **change)

        return self.ledger.atomic(step)

    def _start_bound_passed(self, record: dict) -> bool:
        since = _parse(record["updatedAt"] if record["state"] == "awaiting-operator"
                       else record["createdAt"])
        return self.clock() - since > dt.timedelta(seconds=self.policy.recovery_start_seconds)

    def _blocking(self, view, current: dict, predecessor: dict | None) -> str | None:
        """Why `current` cannot be admitted now, or None (BR4.4)."""
        for other in view.records(KIND):
            if other["recoveryRequestId"] == current["recoveryRequestId"]:
                continue
            if other["environment"] != current["environment"]:
                continue
            if predecessor is not None and other["recoveryRequestId"] == predecessor[
                "recoveryRequestId"
            ]:
                continue  # the held request this successor replaces keeps its hold
            if other["state"] in ACTIVE_RECOVERY_STATES and conflicting(
                other["operation"], current["operation"]
            ):
                return "conflicting-request-active"
        if current["environment"] == "live":
            cutovers = view.records("cutover-record")
            if cutovers and cutovers[-1]["state"] in LIVE_EXCLUSION:
                return "live-exclusion-held"
            # An install or a release rollback holds the live exclusion like a restore
            # (cicd-pipeline § 5.1, § 6).
            from .release_records import release_blocker

            blocker = release_blocker(view)
            if blocker is not None:
                return blocker
        elif current["operation"] in SCHEDULE_OPERATIONS and any(
            record["kind"] == "rehearsal-database" and "disposalPendingSince" in record
            and "disposedAt" not in record for record in view.records("retained-copy")
        ):
            return "rehearsal-database-being-removed"
        return None

    def _approval(self, view, approval_id, step: str, subject: str) -> dict | None:
        if approval_id is None:
            return None
        approval = view.get("maintainer-approval", str(approval_id))
        if approval is None or approval["step"] != step or approval["subjectRef"] != subject:
            raise OperationsError("FORBIDDEN", current={"reasonKey": "decision-not-for-subject"})
        return approval

    def _predecessor(self, view, current: dict, predecessor_id) -> dict | None:
        if predecessor_id is None:
            return None
        held = view.get(KIND, str(UUID(str(predecessor_id))))
        if (
            held is None or held["state"] != "held" or held["operation"] != "restore.production"
            or held["environment"] != current["environment"]
        ):
            raise OperationsError("CONFLICT", current={"reasonKey": "predecessor-not-held"})
        if "abandonmentApprovalId" in held:
            raise OperationsError("CONFLICT", current={"reasonKey": "predecessor-abandoning"})
        waiting = [
            other for other in view.records(KIND)
            if other.get("predecessorRequestId") == held["recoveryRequestId"]
            and other["state"] == "awaiting-operator"
            and other["recoveryRequestId"] != current["recoveryRequestId"]
        ]
        if waiting:
            raise OperationsError("CONFLICT", current={"reasonKey": "successor-waiting"})
        return held

    def admit(self, request_id, *, approval_id=None, predecessor_id=None) -> dict:
        """`requested` → `awaiting-operator`, or `refused`/`expired`; raises CONFLICT,
        leaving it `requested` and holding nothing, while something conflicting holds
        its environment."""

        def decide(current, view):
            if current["state"] != "requested":
                if current["state"] == "awaiting-operator":
                    return None
                raise OperationsError("CONFLICT", current={"state": current["state"]})
            if self._start_bound_passed(current):
                return {"state": "expired"}
            fields: dict = {}
            if current["operation"] in ("restore.verify", "restore.production"):
                backup = view.get("backup-set", current["targetId"])
                if backup is None or backup.get("integrity") != "passed" or any(
                    name in backup for name in ("disposedAt", "retiredWithVolumeAt")
                ):
                    return {"state": "refused", "evidence": ["refused:set-not-passed"]}
            predecessor = None
            if current["operation"] == "restore.production":
                approval = self._approval(view, approval_id, "production-restore",
                                          current["recoveryRequestId"])
                if approval is None:
                    raise OperationsError("POLICY_UNRESOLVED",
                                          current={"reasonKey": "decision-required"})
                if approval["decision"] != "approved":
                    return {"state": "refused", "approvalId": approval["approvalId"],
                            "evidence": ["refused:decision-declined"]}
                predecessor = self._predecessor(view, current, predecessor_id)
                fields["approvalId"] = approval["approvalId"]
                if predecessor is not None:
                    fields["predecessorRequestId"] = predecessor["recoveryRequestId"]
            elif approval_id is not None or predecessor_id is not None:
                raise OperationsError("INVALID_INPUT")
            blocking = self._blocking(view, current, predecessor)
            if blocking is not None:
                raise OperationsError("CONFLICT", current={"reasonKey": blocking,
                                                           "waiting": True})
            return {"state": "awaiting-operator", **fields}

        return self._move(request_id, decide)

    def cancel(self, request_id) -> dict:
        """An administrator cancels a request that has not started. A successor that is
        cancelled leaves its held predecessor held (BR4.7)."""

        def decide(current, view):
            if current["state"] not in WAITING:
                raise OperationsError("CONFLICT", current={"state": current["state"]})
            return {"state": "cancelled"}

        return self._move(request_id, decide)

    def refuse(self, request_id, reason: str) -> dict:
        def decide(current, view):
            if current["state"] not in WAITING:
                raise OperationsError("CONFLICT", current={"state": current["state"]})
            return {"state": "refused", "evidence": [f"refused:{reason}"]}

        return self._move(request_id, decide)

    def expire_due(self) -> list[str]:
        """The housekeeping lane: every waiting request past the start bound expires
        (Step 35 runs it hourly)."""
        expired = []
        for record in self.ledger.records(KIND):
            if record["state"] not in WAITING or not self._start_bound_passed(record):
                continue

            def decide(current, view):
                if current["state"] not in WAITING or not self._start_bound_passed(current):
                    return None
                return {"state": "expired"}

            if self._move(record["recoveryRequestId"], decide)["state"] == "expired":
                expired.append(record["recoveryRequestId"])
        return expired

    def start(self, request_id, *, disk_room: Callable[[dict], bool] | None = None) -> dict:
        """The operator starts it: `awaiting-operator` → `running`, after the
        administrator's second factor is checked again (BR4.2) and, for a verification,
        the internal-disk guard (`disk_room(request)`, BR6.6). A successor that starts
        running takes over its held predecessor's exclusion without a gap: the
        predecessor ends failed in the same step (BR4.4, BR4.7)."""
        identity = str(UUID(str(request_id)))

        def step(view):
            current = view.get(KIND, identity)
            if current is None:
                raise OperationsError("NOT_FOUND")
            if current["state"] == "running":
                return current
            if current["state"] != "awaiting-operator":
                raise OperationsError("CONFLICT", current={"state": current["state"]})
            if self._start_bound_passed(current):
                return self._write(view, current, "expired")
            if current["origin"] == "administrator" and (
                self.mfa_current is None
                or not self.mfa_current(current["requestedBy"], current["mfaVerifiedAt"])
            ):
                return self._write(view, current, "refused", evidence=["refused:mfa-not-current"])
            if current["operation"] == "restore.verify" and disk_room is not None and not (
                disk_room(current)
            ):
                return self._write(view, current, "refused",
                                   evidence=["refused:internal-disk-low"])
            predecessor = current.get("predecessorRequestId")
            if predecessor is not None:
                held = view.get(KIND, predecessor)
                if held is None or held["state"] != "held":
                    raise OperationsError("CONFLICT", current={"reasonKey": "predecessor-not-held"})
                self._write(view, held, "failed", successorRequestId=identity,
                            evidence=[f"successor:{identity}"])
            return self._write(view, current, "running")

        return self.ledger.atomic(step)

    # --- outcomes of the effects ------------------------------------------------------

    def record(self, request_id, *, evidence: Iterable[str] = (),
               receipts: tuple[dict, ...] = (), **fields) -> dict:
        """Add evidence or a field to the request in its current state."""
        refs = list(evidence)

        def decide(current, view):
            if current["state"] in TERMINAL:
                raise OperationsError("CONFLICT", current={"state": current["state"]})
            return {"state": current["state"], "evidence": refs, "receipts": receipts,
                    **fields}

        return self._move(request_id, decide)

    def advance(self, request_id, state: str, *, allowed_from: Iterable[str],
                evidence: Iterable[str] = (), receipts: tuple[dict, ...] = (),
                **fields) -> dict:
        """Move from one of `allowed_from` to `state` (the schema checks the transition
        too); moving to the state it is already in is a no-op."""
        origins = frozenset(allowed_from)
        refs = list(evidence)

        def decide(current, view):
            if current["state"] == state and not refs and not fields:
                return None
            if current["state"] not in origins:
                raise OperationsError("CONFLICT", current={"state": current["state"]})
            return {"state": state, "evidence": refs, "receipts": receipts, **fields}

        return self._move(request_id, decide)

    def outcome_unknown(self, request_id, *, evidence: Iterable[str] = ()) -> dict:
        """An effect's outcome is unknown: the request stays active, blocking every
        conflicting request, until its receipt settles it (BR4.4)."""
        return self.advance(request_id, "unknown", allowed_from=("running", "verifying", "held"),
                            evidence=evidence)

    def settle_unknown(self, request_id, state: str, *, evidence: Iterable[str] = ()) -> dict:
        """PlatformControl's receipt and evidence settle an unknown outcome."""
        if state not in ("verifying", "post-restore-pending", "held", "failed"):
            raise OperationsError("INVALID_INPUT")
        return self.advance(request_id, state, allowed_from=("unknown",), evidence=evidence)

    def authorize_start(self, request_id) -> dict:
        """`startAuthorizedAt`, recorded by the request's own last steps once its
        post-restore set has passed (BR4.7)."""
        now = utc_text(self.clock())

        def decide(current, view):
            if current["operation"] != "restore.production" or current["state"] != "verifying":
                raise OperationsError("CONFLICT", current={"state": current["state"]})
            if "startAuthorizedAt" in current:
                return None
            backup = view.get("backup-set", current.get("postRestoreBackupId"))
            if backup is None or backup.get("integrity") != "passed":
                raise OperationsError("CONFLICT", current={"reasonKey": "post-restore-not-passed"})
            return {"state": "verifying", "startAuthorizedAt": now,
                    "evidence": ["start-authorized"]}

        return self._move(request_id, decide)

    def decide_abandonment(self, request_id, approval_id) -> dict:
        """Your decision abandons a held restore: refused while a successor waits
        (BR4.7, BR9.14)."""

        def decide(current, view):
            if current["state"] != "held" or current["operation"] != "restore.production":
                raise OperationsError("CONFLICT", current={"state": current["state"]})
            approval = self._approval(view, approval_id, "restore-abandonment",
                                      current["recoveryRequestId"])
            if approval is None or approval["decision"] != "approved":
                raise OperationsError("FORBIDDEN", current={"reasonKey": "decision-required"})
            if any(
                other.get("predecessorRequestId") == current["recoveryRequestId"]
                and other["state"] in WAITING for other in view.records(KIND)
            ):
                raise OperationsError("CONFLICT", current={"reasonKey": "successor-waiting"})
            if current.get("abandonmentApprovalId") == approval["approvalId"]:
                return None
            return {"state": "held", "abandonmentApprovalId": approval["approvalId"]}

        return self._move(request_id, decide)

    def abandoned(self, request_id, receipt_facts: dict, *, loss_report_ref: str) -> dict:
        """The abandonment's recreate receipt is recorded: the request ends failed, the
        database empty, so nothing erased comes back (BR4.7)."""
        now = utc_text(self.clock())

        def decide(current, view):
            if current["state"] == "failed" and "abandonedAt" in current:
                return None
            if current["state"] != "held" or "abandonmentApprovalId" not in current:
                raise OperationsError("CONFLICT", current={"state": current["state"]})
            receipt = receipt_facts["receiptId"]
            return {"state": "failed", "abandonmentRecreateReceiptRef": receipt,
                    "abandonedAt": now, "lossReportRef": loss_report_ref,
                    "evidence": [f"abandon-recreate:{receipt}"], "receipts": (receipt_facts,)}

        return self._move(request_id, decide)

    # --- reads the other machines use ----------------------------------------------------

    def production_restore_active(self, environment: str = "live") -> dict | None:
        return next((record for record in self.active(environment)
                     if record["operation"] == "restore.production"), None)

    def restore_waits(self, environment: str = "live") -> bool:
        """A production restore waits on the backup volume or is held, the only moments
        a volume retirement may happen during a restore (BR4.10)."""
        restore = self.production_restore_active(environment)
        return restore is not None and restore["state"] in ("post-restore-pending", "held")
