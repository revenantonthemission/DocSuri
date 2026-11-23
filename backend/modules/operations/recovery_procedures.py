"""The recovery procedures: Workflows 5, 6 and 7 and the volume retirement, each a
sequence of PlatformControl's bound operations recorded on its RecoveryRequest (U8 plan
Step 29; BR4.2–BR4.10, BR6.6, BR9.10).

The operator tool runs them (`docsuri_ops.u8_platform.operator_tool`'s `recovery` words), as
the operator in person or, for the schedule's backups and verifications, as the
standing authority. Every platform effect goes through the operator's `execute`, which
checks A6's preconditions, binds the receipt and runs one effect through the driver the
platform profile names; nothing here touches a database, the backup volume, a service
or the tunnel itself. What the procedures record, they record in the ledger: the
request's states, BackupSets with their LedgerCopies, RestoreVerifications, and the
retained copy of a scratch database that could not be dropped (BR4.5).

- **Workflow 5, the backup** (`backup`, and `take` for a restore's own sets):
  `platform.database.backup`, then a ledger copy beside the set. A set counts only once
  its integrity passed; a failure opens an incident on `storage.capacity`.
- **Workflow 6, the verification** (`verify`): the internal-disk guard at operator
  start, the register head recorded, the agent's `verify` into a new scratch database,
  the checks in order (`Platform.scratch_checks`: every table present with its rows,
  the tombstones up to the head replayed, every tombstoned owner absent), then the
  scratch database dropped and `scratchRemovedAt` recorded. A drop that fails becomes a
  retained copy with its one-day backstop, and the verification fails. Below the
  critical floor (NFR7.18, NFR8.14; U8 plan Step 121): a restore the agent stopped there
  is recorded `failed:internal-disk-critical`, and the floor is read once more after a
  restore that succeeded, before any check, so a crossing then drops the scratch
  database and fails the verification with that reason, running no check.
- **Workflow 7, the production restore** (`restore`), the operator in person, each
  bound step shown against its bound (`Platform.steps`): maintenance route, v2 stopped,
  the pre-restore set (a successor takes none), the recreate (once), the set streamed
  back into `pg_restore -j 2`, the newer tombstones replayed (`restore_evaluate`), the
  integrity check, the post-restore set, `startAuthorizedAt`, then v2 started, ready
  and routed back. Its failure paths are Workflow 7's: failed before the recreate (v2
  restarted on the untouched database once the request has ended), `held` after it,
  `post-restore-pending` when the post-restore set fails (`retry_post_restore`), and a
  failed start or route back kept `verifying` (`finish_restore`). A held restore ends
  through a successor (`restore` of the successor) or an abandonment (`abandon`). The
  key folders are never touched (BR4.8).
- **The volume retirement** (`retire_volume`, BR4.10): your decision, then the agent's
  `prepare-volume` and `configure`, its status on that volume identity, the profile
  operation and ServiceOperations' comparison, in that order.

An effect whose outcome is unknown is reconciled from its receipt at once; one that
stays unknown leaves the request `unknown`, still active and blocking every conflicting
request, until `reconcile` settles it (BR4.4): in person for a request whose operation
your login bound, and by the standing job for a scheduled request, whose operation the
scheduler bound (`ScheduledRecovery.settle_unknown`); the store refuses each the
other's, and the in-person word then answers `operation-bound-by-another-actor` naming
the path that settles it (review finding, Minor, R16).
"""

from __future__ import annotations

import datetime as dt
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from uuid import NAMESPACE_URL, uuid5

import psycopg

from .errors import LedgerDamaged, OperationsError
from .ledger import utc_text
from .recovery import RecoveryRequests
from .retained_copies import VOLUME_KINDS, RetainedCopies, is_open, receipt_facts

STORAGE = "storage.capacity"
OPENED_BY = "job-failure-correlated"
# The backup agent's refusal below the critical floor, kept as the request's reason.
CRITICAL = "internal-disk-critical"
TRIGGERS = {"schedule": "scheduled", "administrator": "requested"}


class ProcedureFailed(Exception):
    """A step failed with a fixed reason key; the request records it."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class OutcomeUnknown(Exception):
    """An effect's outcome stayed unknown after reconciliation."""

    def __init__(self, operation_id: str):
        super().__init__(operation_id)
        self.operation_id = operation_id


def _direct(name: str, bound: float, work: Callable[[], object]) -> object:
    return work()


@dataclass
class Platform:
    """What the procedures need from the platform side, which the operator tool's
    wiring provides for the realm or the arrangement."""

    operator: object
    production: str
    labels: tuple[str, ...]
    scratch_name: Callable[[], str]
    free_bytes: Callable[[], int]
    scratch_checks: Callable[[str, list[str]], dict]
    restore_evaluate: Callable[[str, list[str]], dict]
    production_integrity: Callable[[str], dict]
    ready: Callable[[], bool]
    drop_scratch: Callable[[str], None]
    rehearsal: Callable[[], str | None] = lambda: None
    ledger_copy: Callable[[], dict] | None = None
    agent: Callable[..., dict] | None = None
    steps: Callable[[str, float, Callable[[], object]], object] = _direct
    loss_report: Callable[[str, dict], str] | None = None
    # The environment the platform serves now: live when the operator's `facts().mode`
    # is `live`, else rehearsal (U8 plan Step 64(h)); a retirement needs it.
    current_environment: Callable[[], str] | None = None

    def database_of(self, environment: str) -> str:
        if environment == "live":
            return self.production
        name = self.rehearsal()
        if name is None:
            raise ProcedureFailed("no-rehearsal-database")
        return name


_REASON = re.compile(r"[a-z][a-z0-9.-]{0,63}")


def reason_of(receipt: dict, default: str) -> str:
    """The refusal's fixed reason key, or `default` when it carries free text (U7's
    injected faults and its operator messages): a ledger record holds keys only."""
    value = receipt.get("refusal")
    return value if isinstance(value, str) and _REASON.fullmatch(value) else default


def _parse(text: str) -> dt.datetime:
    return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))


def _time(text: str) -> str:
    return utc_text(_parse(text))


class RecoveryProcedures:
    def __init__(self, requests: RecoveryRequests, platform: Platform, *, incidents,
                 tombstones, policy, copies: RetainedCopies | None = None,
                 clock: Callable[[], dt.datetime] | None = None):
        self.requests, self.platform = requests, platform
        self.ledger = requests.ledger
        self.incidents, self.tombstones, self.policy = incidents, tombstones, policy
        self.copies = copies or RetainedCopies(self.ledger, policy)
        self.clock = clock or requests.clock

    # --- effects -------------------------------------------------------------------

    def _key(self, request_id: str, step: str) -> str:
        revision = self.ledger.revision("recovery-request", request_id)
        return f"recovery:{request_id}:{step}:{revision}"

    def _recorded_refs(self, target: str, inputs: dict, key: str) -> list[str]:
        """The references an applied effect recorded beside itself (its effect record),
        read when reconciliation found it applied."""
        from docsuri_ops.u8_platform.drivers import input_hash
        from docsuri_ops.u8_platform.u8_protocols import effect_token

        operator = self.platform.operator
        token = effect_token(target, input_hash(inputs), key)
        path = operator.profile.effects_root / target / f"effect-{token}.json"
        try:
            return list(json.loads(path.read_bytes()).get("refs", []))
        except (OSError, ValueError):
            return []

    def _effect(self, operation: str, target: str, inputs: dict, *, key: str) -> dict:
        """One bound operation; an unknown outcome is reconciled from its target at once,
        and one still unknown raises `OutcomeUnknown`."""
        from docsuri_ops.platform_control.errors import ControlError
        from docsuri_ops.u8_platform.u8_protocols import PreconditionRefused

        operator = self.platform.operator
        try:
            receipt = operator.execute(operation, target, inputs, key=key)
        except PreconditionRefused as refused:
            # A6's precondition does not hold: nothing was bound and no effect ran.
            return {"outcome": "refused", "refusal": refused.reason}
        except ControlError as error:
            return {"outcome": "refused", "refusal": error.code.lower().replace("_", "-")}
        if receipt["outcome"] != "unknown":
            return receipt
        settled = operator.reconcile(receipt["operationId"])
        state = settled.get("reconciliationState")
        if state == "reconciled-applied":
            refs = self._recorded_refs(target, inputs, key)
            return {**settled, "outcome": "succeeded", "effectRefs": refs}
        if state == "reconciled-not-applied":
            return {**settled, "outcome": "failed"}
        raise OutcomeUnknown(receipt["operationId"])

    def _facts(self, receipt: dict) -> dict:
        return receipt_facts(receipt, now=self.clock())

    def _incident(self, request: dict) -> None:
        try:
            self.incidents.signal(STORAGE, OPENED_BY,
                                  correlation=f"recovery:{request['recoveryRequestId']}",
                                  environment=request["environment"])
        except LedgerDamaged:
            pass  # a damaged ledger shows as operations.ledger unavailable (BR6.10)

    def _unknown(self, request_id: str, error: OutcomeUnknown) -> dict:
        return self.requests.outcome_unknown(request_id,
                                             evidence=[f"pending:{error.operation_id}"])

    # --- Workflow 5: a backup set and its ledger copy ---------------------------------

    def backup_effect(self, environment: str, *, request: dict | None, via: str,
                      step: str = "backup", owner_key: str | None = None) -> dict:
        """The bound operation `take` runs for one set: its operation, target, inputs and
        key, and the environment. A caller that must settle an interrupted set later by
        its receipt (the release command's journal) keeps it before the set is taken."""
        database = self.platform.database_of(environment)
        if request is None:
            if not owner_key:
                raise OperationsError("INVALID_INPUT")
            key = f"{owner_key}:{step}"
        else:
            key = self._key(request["recoveryRequestId"], step)
        backup_id = str(uuid5(NAMESPACE_URL, f"docsuri-backup-set:{key}"))
        target = "database-production" if environment == "live" else "database-rehearsal"
        return {"operation": "platform.database.backup", "target": target,
                "inputs": {"database": database, "recordId": backup_id, "via": via},
                "key": key, "environment": environment}

    def take(self, environment: str, trigger: str, *, request: dict | None, via: str,
             step: str = "backup", owner_key: str | None = None,
             effect: dict | None = None) -> dict:
        """One set of the environment's database, recorded once the agent wrote it; a
        ledger copy beside it. Raises `ProcedureFailed` when the set failed or its
        integrity did not pass (the failed set is kept as evidence). A set no request
        owns (the switch's first live backup, Step 33) is keyed by `owner_key`. `effect`
        is the bound operation `backup_effect` gave, when the caller kept it first."""
        effect = effect or self.backup_effect(environment, request=request, via=via,
                                              step=step, owner_key=owner_key)
        receipt = self._effect(effect["operation"], effect["target"], effect["inputs"],
                               key=effect["key"])
        if receipt["outcome"] != "succeeded":
            raise ProcedureFailed(reason_of(receipt, "backup-failed"))
        return self.record_applied(effect, trigger, request, receipt)

    def record_applied(self, effect: dict, trigger: str, request: dict | None,
                       receipt: dict, *, taken_at: str | None = None) -> dict:
        """An applied backup's set recorded from its receipt (its effect references, or
        those its effect record kept when reconciliation found it applied), with its
        ledger copy; `ProcedureFailed` as `take` raises it. Recording twice records once
        (the set's identity is its key's). `taken_at` is the dump's own time when it is
        recorded later than it was taken (a reconciliation, U8 plan Step 64(a))."""
        from docsuri_ops.u8_platform.drivers import parse_facts

        backup_id = effect["inputs"]["recordId"]
        refs = list(receipt.get("effectRefs") or self._recorded_refs(
            effect["target"], effect["inputs"], effect["key"]))
        facts = parse_facts(refs)
        location = next((ref.removeprefix("backup-volume/") for ref in refs
                         if ref.startswith("backup-volume/")), None)
        if location is None or facts.get("recordId") != backup_id:
            raise ProcedureFailed("backup-receipt-incomplete")
        record = self._record_set(effect["environment"], trigger, request, backup_id,
                                  location, facts, receipt, taken_at=taken_at)
        if record["integrity"] != "passed":
            raise ProcedureFailed("integrity-failed")
        # A copy of this set without `verifiedAt` counts as missing, and a lone copy
        # carries no `backupId` (U8 plan Step 64(b)).
        if self.platform.ledger_copy is not None and not any(
                item.get("backupId") == backup_id and "verifiedAt" in item
                for item in self.ledger.records("ledger-copy")):
            # A copy that fails is the set's failure under a fixed reason key, which every
            # caller records (review finding, Critical, R15); the set stays recorded, and
            # recording it again takes the missing copy only.
            try:
                copied = self._ledger_copy(backup_id, receipt)
            except (ProcedureFailed, OutcomeUnknown):
                raise
            except Exception as error:  # noqa: BLE001 - any copy failure fails the set
                raise ProcedureFailed("ledger-copy-failed") from error
            if "verifiedAt" not in copied:
                raise ProcedureFailed("ledger-copy-unverified")
        return record

    def _record_set(self, environment, trigger, request, backup_id, location, facts,
                    receipt, *, taken_at: str | None = None) -> dict:
        now = taken_at or utc_text(self.clock())
        receipt_record = self._facts(receipt)

        def step(view):
            prior = view.get("backup-set", backup_id)
            if prior is not None:
                return prior
            revision = sum(1 for item in view.records("backup-set")
                           if item["environment"] == environment) + 1
            record = {
                "backupId": backup_id, "environment": environment, "revision": revision,
                "trigger": trigger,
                "takenAt": now, "checksum": facts["sha256"], "sizeBytes": int(facts["size"]),
                "sourceDatabaseBytes": int(facts.get("databaseBytes", 0)),
                "location": location, "databaseIncarnation": facts["incarnation"],
                "stagingLocation": facts["stagingLocation"],
                "retainUntil": _time(facts["disposeAfter"]),
                "integrity": facts["integrity"], "operatorReceiptRef": receipt_record["receiptId"],
            }
            if request is not None:
                record["recoveryRequestId"] = request["recoveryRequestId"]
            if "stagingRemovedAt" in facts:
                record["stagingRemovedAt"] = _time(facts["stagingRemovedAt"])
            view.append("backup-set", record, expect_revision=0, receipts=(receipt_record,))
            return record

        return self.ledger.atomic(step)

    def _ledger_copy(self, backup_id: str, receipt: dict) -> dict:
        """The ledger streamed to the agent beside the set (BR6.10)."""
        copied = self.platform.ledger_copy()
        agent, head = copied["agent"], copied["head"]
        now = utc_text(self.clock())
        record = {
            "ledgerCopyId": agent["recordId"], "backupId": backup_id, "takenAt": now,
            "location": agent["location"], "stagingLocation": agent["stagingLocation"],
            "digest": agent["sha256"], "headSequence": head["count"],
            "headDigest": head["head"], "retainUntil": _time(agent["disposeAfter"]),
            "operatorReceiptRef": str(receipt["receiptId"]),
        }
        if agent.get("stagingRemovedAt"):
            record["stagingRemovedAt"] = _time(agent["stagingRemovedAt"])
        if agent.get("integrity") == "passed":
            record["verifiedAt"] = now
        self.ledger.append("ledger-copy", record, expect_revision=0)
        return record

    # --- a lone ledger copy (L1-5, L1-48) -------------------------------------------------

    def _signal(self, correlation: str, environment: str) -> None:
        try:
            self.incidents.signal(STORAGE, OPENED_BY, correlation=correlation,
                                  environment=environment)
        except LedgerDamaged:
            pass  # a damaged ledger shows as operations.ledger unavailable (BR6.10)

    def _beside(self, receipt: dict) -> tuple[dict | None, list[str]]:
        """What an applied effect left beside its `effectReference`: its bound input
        (checked against the receipt's `inputHash`) and its effect record's refs; read
        when reconciliation found it applied (U8 plan Step 64(a), (c), (j))."""
        from docsuri_ops.u8_platform.drivers import read_input

        reference = str(receipt.get("effectReference") or "")
        if "/" not in reference:
            return None, []
        target, name = reference.split("/", 1)
        directory = self.platform.operator.profile.effects_root / target
        token = name.removeprefix("effect-").removesuffix(".json")
        try:
            inputs = read_input(directory, token, str(receipt.get("inputHash")))
        except Exception:  # noqa: BLE001 - a missing or changed input: nothing usable
            inputs = None
        try:
            refs = list(json.loads((directory / name).read_bytes()).get("refs", []))
        except (OSError, ValueError):
            refs = []
        return inputs, refs

    def ledger_copy_alone(self, environment: str, *, owner_key: str, via: str) -> dict:
        """A ledger copy on its own, through its own bound operation `platform.ledger.copy`
        on `ledger-copy` (L1-5), run to a settled outcome (`execute_settled`): an applied
        copy's receipt, replayed or reconciled, is recorded as a LedgerCopy without
        `backupId`; a failed one runs again under the next retry key. A refused or failed
        operation raises `ProcedureFailed`, one still unknown `OutcomeUnknown`; each, and
        a copy whose chain check failed, first signals `storage.capacity` (correlation
        `ledger-copy:<owner_key>`, the copy's environment). A copy's own operation
        touches no database, so it runs while a switch or a production restore holds the
        environment (L1-48)."""
        from docsuri_ops.platform_control.errors import ControlError
        from docsuri_ops.u8_platform.u8_protocols import (
            EffectUnsettled,
            PreconditionRefused,
            execute_settled,
        )

        correlation = f"ledger-copy:{owner_key}"
        inputs = {"via": via, "environment": environment}
        try:
            receipt = execute_settled(self.platform.operator, "platform.ledger.copy",
                                      "ledger-copy", inputs, key=f"{owner_key}:ledger-copy")
        except PreconditionRefused as refused:
            self._signal(correlation, environment)
            raise ProcedureFailed(refused.reason) from None
        except ControlError as error:
            self._signal(correlation, environment)
            raise ProcedureFailed(error.code.lower().replace("_", "-")) from None
        except EffectUnsettled as unsettled:
            self._signal(correlation, environment)
            held = dict(unsettled.receipt or {})
            if unsettled.kind == "failed" or held.get("reconciliationState") == (
                    "reconciled-not-applied"):
                raise ProcedureFailed(reason_of(held, "ledger-copy-failed")) from None
            if unsettled.kind == "exhausted" or "operationId" not in held:
                raise ProcedureFailed("ledger-copy-failed") from None
            raise OutcomeUnknown(str(held["operationId"])) from None
        record = self._record_lone_copy(receipt, environment)
        if record is None:
            self._signal(correlation, environment)
            raise ProcedureFailed("ledger-copy-failed")
        if "verifiedAt" not in record:
            self._signal(correlation, environment)
        return record

    def _record_lone_copy(self, receipt: dict, environment: str) -> dict | None:
        """The LedgerCopy a lone copy's applied receipt records, citing that receipt
        (outcome `succeeded`); the copy already recorded under it when it is replayed;
        None when its facts are incomplete."""
        from docsuri_ops.u8_platform.drivers import parse_facts

        refs = list(receipt.get("effectRefs") or [])
        if not any(ref.startswith("backup-volume/") for ref in refs):
            refs = self._beside(receipt)[1]
        try:
            facts = parse_facts(refs)
        except ValueError:
            return None
        location = next((ref.removeprefix("backup-volume/") for ref in refs
                         if ref.startswith("backup-volume/")), None)
        needed = ("recordId", "sha256", "stagingLocation", "disposeAfter", "headSequence",
                  "headDigest")
        if location is None or any(name not in facts for name in needed):
            return None
        settled = self._facts({**receipt, "outcome": "succeeded"})
        now = utc_text(self.clock())
        record = {
            "ledgerCopyId": facts["recordId"],
            "takenAt": _time(facts["stagingRemovedAt"]) if "stagingRemovedAt" in facts else now,
            "location": location, "stagingLocation": facts["stagingLocation"],
            "digest": facts["sha256"], "headSequence": int(facts["headSequence"]),
            "headDigest": facts["headDigest"], "retainUntil": _time(facts["disposeAfter"]),
            "operatorReceiptRef": settled["receiptId"],
        }
        if "stagingRemovedAt" in facts:
            record["stagingRemovedAt"] = _time(facts["stagingRemovedAt"])
        if facts.get("integrity") == "passed":
            record["verifiedAt"] = now

        def step(view):
            prior = view.get("ledger-copy", record["ledgerCopyId"])
            if prior is not None:
                return prior
            view.append("ledger-copy", record, expect_revision=0, receipts=(settled,))
            return record

        return self.ledger.atomic(step)

    def reconcile_interrupted(self, targets) -> list[dict]:
        """Each target's operations this actor bound that a stopped process left pending
        past their lease or unresolved, settled from their target without running
        anything again (`reconcile_unresolved`); the settled receipts. A lone copy found
        applied is recorded from its effect record, as `reconcile` records a set. A
        `ControlError` from the store leaves the rest for the next call. The store
        settles an operation only for the actor that bound it (U8 plan Step 64(j))."""
        from docsuri_ops.platform_control.errors import ControlError
        from docsuri_ops.u8_platform.u8_protocols import reconcile_unresolved

        settled: list[dict] = []
        for target in targets:
            try:
                receipts = reconcile_unresolved(self.platform.operator, target)
            except ControlError:
                continue
            for receipt in receipts:
                settled.append(receipt)
                if receipt.get("operation") == "platform.ledger.copy" and receipt.get(
                        "reconciliationState") == "reconciled-applied":
                    self._record_reconciled_copy(receipt)
        return settled

    def _record_reconciled_copy(self, receipt: dict) -> None:
        """A lone copy reconciliation found applied, recorded from its effect record. Its
        receipt is reconciled now, so no later settle lists it again: a recording that
        fails, or a copy whose chain check failed, signals `storage.capacity` here, as
        `ledger_copy_alone` does (review fix, batch 4)."""
        inputs = self._beside(receipt)[0] or {}
        environment = inputs.get("environment", "live")
        try:
            record = self._record_lone_copy(receipt, environment)
        except Exception:  # noqa: BLE001 - signalled below instead of lost
            record = None
        if record is None or "verifiedAt" not in record:
            self._signal(f"ledger-copy:reconciled:{receipt.get('operationId')}", environment)

    def backup(self, request_id, *, via: str = "standing") -> dict:
        """Run an admitted `backup.create` request (Workflow 5)."""
        request = self.requests.require(request_id)
        if request["operation"] != "backup.create":
            raise OperationsError("INVALID_INPUT")
        request = self.requests.start(request_id)
        if request["state"] != "running":
            return request
        try:
            backup = self.take(request["environment"], TRIGGERS[request["origin"]],
                               request=request, via=via)
        except OutcomeUnknown as error:
            return self._unknown(request["recoveryRequestId"], error)
        except ProcedureFailed as failure:
            self._incident(request)
            return self.requests.advance(request_id, "failed", allowed_from=("running",),
                                         evidence=[f"failed:{failure.reason}"])
        self.requests.advance(request_id, "verifying", allowed_from=("running",),
                              evidence=[f"backup:{backup['backupId']}"])
        return self.requests.advance(request_id, "succeeded", allowed_from=("verifying",))

    # --- Workflow 6: a restore verification --------------------------------------------

    def _disk_room(self, backup: dict | None) -> bool:
        """BR6.6: free space, less the source database's size at dump time, stays above
        the threshold."""
        source = 0 if backup is None else int(backup.get("sourceDatabaseBytes", 0))
        return self.platform.free_bytes() - source > self.policy.internal_disk_threshold_bytes

    def _disk_critical(self) -> bool:
        """The internal disk below the critical floor (NFR7.18, NFR8.14)."""
        return self.platform.free_bytes() < self.policy.internal_disk_critical_bytes

    def verify(self, request_id, *, via: str = "standing") -> dict:
        """Run an admitted `restore.verify` request (Workflow 6)."""
        request = self.requests.require(request_id)
        if request["operation"] != "restore.verify":
            raise OperationsError("INVALID_INPUT")
        backup = self.ledger.get("backup-set", request["targetId"])
        request = self.requests.start(request_id, disk_room=lambda _: self._disk_room(backup))
        if request["state"] != "running":
            return request
        started = utc_text(self.clock())
        try:
            head = self.tombstones.verify()
        except LedgerDamaged:
            self._incident(request)
            return self.requests.advance(request_id, "failed", allowed_from=("running",),
                                         evidence=["failed:register-damaged"])
        accounts = [item["accountId"] for item in self.tombstones.all()
                    if item["sequence"] <= head["sequence"]]
        verification_id = str(uuid5(NAMESPACE_URL, f"docsuri-verification:{request_id}"))
        from docsuri_ops.arrangement.paths import DatabaseNames
        from docsuri_ops.u8_platform.u8_protocols import database_limit_reason

        # NFR8.15's one scratch place, asked before anything is recorded or created (a
        # production name is its own prefix); the refusal is recorded as A6's was.
        limit = database_limit_reason("scratch", self.ledger,
                                      DatabaseNames(self.platform.production))
        if limit is not None:
            return self._verification_failed(request, verification_id, backup, head, started,
                                             None, limit)
        scratch = self.platform.scratch_name()
        # Every scratch restore is recorded first (NFR3.12, NFR3.7; U8 plan Step 64(d)).
        copy = self.copies.record(
            "scratch-restore", f"verification:{verification_id}", [f"database/{scratch}"],
            copy_id=uuid5(NAMESPACE_URL, f"docsuri-scratch-copy:{verification_id}"))
        kind = "live-set" if request["environment"] == "live" else "rehearsal-set"
        inputs = {"mode": "scratch", "scratchDatabase": scratch, "setKind": kind, "via": via,
                  "recordId": request["targetId"]}
        try:
            receipt = self._effect("platform.database.restore", "database-scratch", inputs,
                                   key=self._key(request_id, "verify-restore"))
        except OutcomeUnknown as error:
            return self._unknown(request_id, error)  # the copy stays open
        if receipt["outcome"] == "refused":
            # A6's precondition refused it before anything was bound or created (a
            # scratch name refused): the recorded copy is closed, and the refusal recorded
            # under its own key.
            self.copies.disposed_by_verification(copy["copyId"], verification_id)
            return self._verification_failed(request, verification_id, backup, head, started,
                                             None, reason_of(receipt, "scratch-restore-refused"))
        if receipt["outcome"] != "succeeded":
            # The restore ran and failed, possibly after the scratch database was created
            # (a pg_restore that failed part-way): it is dropped as a finished one is, and
            # its recorded copy stays open when it cannot be, so no partial restore of a
            # set's personal data is left unrecorded (BR4.5, BR9.12, NFR8.15).
            # The agent's stop below the critical floor keeps its own reason.
            removed = self._drop_scratch(copy["copyId"], scratch, verification_id)
            reason = (CRITICAL if receipt.get("refusal") == CRITICAL
                      else "scratch-restore-failed")
            return self._verification_failed(request, verification_id, backup, head, started,
                                             removed, reason)
        from docsuri_ops.u8_platform.drivers import parse_facts

        restored = parse_facts(receipt.get("effectRefs", []))
        if restored.get("setRecordId") != request["targetId"]:
            checks = {"integrity": "failed", "surviving": 0}
        elif self._disk_critical():
            # The floor crossed while the set was restored: the scratch database is
            # dropped and no check runs (U8 plan Step 121(d)).
            removed = self._drop_scratch(copy["copyId"], scratch, verification_id)
            return self._verification_failed(request, verification_id, backup, head, started,
                                             removed, CRITICAL)
        else:
            try:
                checks = self.platform.scratch_checks(scratch, accounts)
            except (RuntimeError, OSError, psycopg.Error):
                # A check that cannot finish fails the verification; the scratch copy
                # is still dropped (or kept as a retained copy) below.
                checks = {"integrity": "failed", "surviving": 0}
        removed = self._drop_scratch(copy["copyId"], scratch, verification_id)
        verified = (checks.get("integrity") == "passed" and checks.get("surviving") == 0
                    and removed is not None)
        record = {
            "verificationId": verification_id, "environment": request["environment"],
            "backupId": request["targetId"], "startedAt": started,
            "finishedAt": utc_text(self.clock()), "registerHeadSequence": head["sequence"],
            "registerHeadDigest": head["digest"],
            "integrity": "passed" if checks.get("integrity") == "passed" else "failed",
            "erasedOwnersSurviving": int(checks.get("surviving", 0)),
            "result": "verified" if verified else "failed",
            "evidenceRef": f"verification:{verification_id}",
        }
        if removed is not None:
            record["scratchRemovedAt"] = removed
        record.update(self._hnsw(restored, backup))
        self.ledger.append("restore-verification", record, expect_revision=0)
        self.requests.advance(request_id, "verifying", allowed_from=("running",),
                              evidence=[f"verification:{verification_id}"])
        if verified:
            return self.requests.advance(request_id, "succeeded", allowed_from=("verifying",))
        self._incident(request)
        return self.requests.advance(request_id, "failed", allowed_from=("verifying",),
                                     evidence=["failed:verification-failed"])

    def _verification_failed(self, request, verification_id, backup, head, started, removed,
                             reason) -> dict:
        record = {
            "verificationId": verification_id, "environment": request["environment"],
            "backupId": request["targetId"], "startedAt": started,
            "finishedAt": utc_text(self.clock()), "registerHeadSequence": head["sequence"],
            "registerHeadDigest": head["digest"], "integrity": "failed",
            "erasedOwnersSurviving": 0, "result": "failed",
            "evidenceRef": f"verification:{verification_id}",
        }
        if removed is not None:
            record["scratchRemovedAt"] = removed
        self.ledger.append("restore-verification", record, expect_revision=0)
        self._incident(request)
        return self.requests.advance(request["recoveryRequestId"], "failed",
                                     allowed_from=("running",), evidence=[f"failed:{reason}"])

    def _hnsw(self, facts: dict, backup: dict | None) -> dict:
        """The agent's timed HNSW rebuild and its projection to the footprint budget
        (Step 60(d)'s formula, in integers, rounded up); a set of 0 bytes gets the time
        and no projection, and refs that carry no time record neither (Step 64(i))."""
        value = facts.get("hnswRebuildSeconds")
        if value is None or not str(value).isdigit():
            return {}
        seconds = int(value)
        result = {"hnswRebuildSeconds": seconds}
        source = 0 if backup is None else int(backup.get("sourceDatabaseBytes", 0))
        if source > 0:
            budget = int(self.policy.footprint_budget_bytes)
            result["hnswProjectedSeconds"] = (seconds * budget + source - 1) // source
        return result

    def _drop_scratch(self, copy_id: str, scratch: str, verification_id: str) -> str | None:
        """Drop the scratch database through the scheduler's database login, which owns
        it through the disposable-databases role (Workflow 6 step 2). A drop that
        succeeds closes the copy recorded before the restore, citing the verification; one
        that fails, or whose outcome is unknown, leaves it open, still counted, until the
        disposal pass removes it at its backstop (BR4.5, BR9.12; U8 plan Step 64(d))."""
        try:
            self.platform.drop_scratch(scratch)
        except Exception:  # noqa: BLE001 - any failure leaves the recorded copy open
            return None
        self.copies.disposed_by_verification(copy_id, verification_id)
        return utc_text(self.clock())

    def remove_scratch(self, copy_id) -> dict:
        """A scratch database a failed check left behind, removed in person (U8 plan Step
        72(c), L1-23): the recovery word `remove-scratch`.

        Before any operation: an unknown copy is `NOT_FOUND`; a closed copy, or one not of
        kind `scratch-restore`, is `CONFLICT` (`not-an-open-scratch`); while any
        `restore.verify` request is active (`ACTIVE_RECOVERY`), it is `CONFLICT`
        (`scratch-in-use`), since a copy is recorded before its restore and may be the
        scratch of a check still running. Then `platform.database.remove` on
        `database-scratch` runs to a settled outcome (`execute_settled`), so a word run
        again after a failed removal runs under the next retry key; on success the copy is
        closed on that receipt (`RetainedCopies.disposed`). A refused or failed removal
        records `disposal_pending` and answers its reason; an unknown or in-progress
        outcome leaves the copy open without it."""
        from docsuri_ops.platform_control.errors import ControlError
        from docsuri_ops.u8_platform.u8_protocols import (
            ACTIVE_RECOVERY,
            UNSETTLED_REASONS,
            EffectUnsettled,
            PreconditionRefused,
            execute_settled,
        )

        try:
            record = self.copies.get(copy_id)
        except ValueError:
            record = None  # not a copy identity at all
        if record is None:
            raise OperationsError("NOT_FOUND")
        identity = record["copyId"]
        database = next((place.removeprefix("database/") for place in record["locations"]
                         if place.startswith("database/")), None)
        if record["kind"] != "scratch-restore" or not is_open(record) or database is None:
            raise OperationsError("CONFLICT", current={"reasonKey": "not-an-open-scratch"})
        if any(request["operation"] == "restore.verify" and request["state"] in ACTIVE_RECOVERY
               for request in self.ledger.records("recovery-request")):
            raise OperationsError("CONFLICT", current={"reasonKey": "scratch-in-use"})
        failed = None
        try:
            receipt = execute_settled(self.platform.operator, "platform.database.remove",
                                      "database-scratch",
                                      {"database": database, "via": "in-person"},
                                      key=f"remove-scratch:{identity}")
        except PreconditionRefused as refused:
            failed = refused.reason
        except ControlError as error:
            failed = error.code.lower().replace("_", "-")
        except EffectUnsettled as unsettled:
            if unsettled.kind == "failed":
                failed = "scratch-removal-failed"
            elif unsettled.kind == "exhausted":
                failed = UNSETTLED_REASONS["exhausted"]
            else:
                # Unknown or still in progress: nothing is known to have failed, so the
                # copy stays open without `disposalPendingSince`.
                return {"copyId": identity, "disposed": False,
                        "reason": UNSETTLED_REASONS[unsettled.kind]}
        if failed is not None:
            self.copies.disposal_pending(identity, failed=True)
            return {"copyId": identity, "disposed": False, "reason": failed}
        settled = self._facts(receipt)
        self.copies.disposed(identity, receipt)
        return {"copyId": identity, "disposed": True, "receiptId": settled["receiptId"]}

    # --- Workflow 7: the production restore --------------------------------------------

    def _bounded(self, name: str, seconds: int, work: Callable[[], object]) -> object:
        return self.platform.steps(name, seconds, work)

    def _service(self, request_id: str, action: str, step: str) -> None:
        for label in self.platform.labels:
            receipt = self._effect("platform.service.control", label,
                                   {"label": label, "action": action},
                                   key=self._key(request_id, f"{step}:{label}"))
            if receipt["outcome"] != "succeeded":
                raise ProcedureFailed(f"service-{action}-failed")
            self.requests.record(request_id, evidence=[f"{step}:{receipt['receiptId']}"])

    def _route(self, request_id: str, origin: str, step: str) -> None:
        receipt = self._effect("platform.tunnel.route", "tunnel", {"origin": origin},
                               key=self._key(request_id, step))
        if receipt["outcome"] != "succeeded":
            raise ProcedureFailed("tunnel-route-failed")
        self.requests.record(request_id, evidence=[f"{step}:{receipt['receiptId']}"])

    def restore(self, request_id) -> dict:
        """Run an admitted `restore.production` request, in person (Workflow 7)."""
        request = self.requests.require(request_id)
        if request["operation"] != "restore.production" or request["environment"] != "live":
            raise OperationsError("INVALID_INPUT")
        request = self.requests.start(request_id)
        if request["state"] != "running":
            return request
        try:
            return self._restore_steps(request)
        except OutcomeUnknown as error:
            return self._unknown(request_id, error)

    def _restore_steps(self, request: dict) -> dict:
        request_id = request["recoveryRequestId"]
        policy = self.policy
        try:
            self._bounded("route-and-stop", policy.restore_route_and_stop_seconds, lambda: (
                self._route(request_id, "maintenance", "route-maintenance"),
                self._service(request_id, "stop", "stop"),
            ))
            if "predecessorRequestId" not in request:
                pre = self._bounded("pre-restore-backup", policy.restore_pre_backup_seconds,
                                    lambda: self.take("live", "pre-restore", request=request,
                                                      via="in-person", step="pre-restore"))
                self.requests.record(request_id, preRestoreBackupId=pre["backupId"],
                                     evidence=[f"backup:{pre['backupId']}"])
        except ProcedureFailed as failure:
            return self._failed_before_recreate(request, failure.reason)
        backup = self.ledger.get("backup-set", request["targetId"])
        try:
            self._bounded("recreate-and-restore", policy.restore_recreate_and_restore_seconds,
                          lambda: self._recreate_and_restore(request_id, backup))
            self._bounded("replay-and-integrity", policy.restore_replay_and_integrity_seconds,
                          lambda: self._replay_and_check(request_id, backup))
        except ProcedureFailed as failure:
            self._incident(request)
            return self.requests.advance(request_id, "held", allowed_from=("running",),
                                         evidence=[f"held:{failure.reason}"])
        self.requests.advance(request_id, "verifying", allowed_from=("running",))
        return self._post_restore(request_id)

    def _failed_before_recreate(self, request: dict, reason: str) -> dict:
        """Nothing was restored: the request ends failed first, then v2 starts on the
        untouched database and the public address routes back (BR4.7)."""
        request_id = request["recoveryRequestId"]
        self._incident(request)
        failed = self.requests.advance(request_id, "failed", allowed_from=("running",),
                                       evidence=[f"failed:{reason}"])
        try:
            self._start_and_route_back(request_id, failed)
        except (ProcedureFailed, OutcomeUnknown):
            pass  # the maintenance notice stays until plain service control routes back
        return self.requests.require(request_id)

    def _recreate_and_restore(self, request_id: str, backup: dict) -> None:
        recreate = self._effect(
            "platform.database.recreate", "database-production",
            {"database": self.platform.production, "recoveryRequestId": request_id},
            key=self._key(request_id, "recreate"))
        if recreate["outcome"] != "succeeded":
            raise ProcedureFailed(reason_of(recreate, "recreate-failed"))
        self.requests.record(request_id, evidence=[f"recreate:{recreate['receiptId']}"])
        restored = self._effect(
            "platform.database.restore", "database-production",
            {"mode": "production", "database": self.platform.production,
             "recoveryRequestId": request_id, "setPath": backup["location"],
             "setSha256": backup["checksum"], "via": "in-person"},
            key=self._key(request_id, "restore"))
        if restored["outcome"] != "succeeded":
            raise ProcedureFailed(reason_of(restored, "restore-failed"))
        self.requests.record(request_id, evidence=[f"restore:{restored['receiptId']}"])

    def _replay_and_check(self, request_id: str, backup: dict) -> None:
        try:
            newer = [item["accountId"] for item in self.tombstones.newer_than(backup)]
            self.tombstones.verify()
        except LedgerDamaged:
            raise ProcedureFailed("register-damaged") from None
        replayed = self.platform.restore_evaluate(self.platform.production, newer)
        if replayed.get("surviving", 0) != 0:
            raise ProcedureFailed("erased-owner-surviving")
        checked = self.platform.production_integrity(self.platform.production)
        if checked.get("integrity") != "passed":
            raise ProcedureFailed("integrity-failed")
        self.requests.record(request_id, evidence=[f"replayed:{len(newer)}", "integrity:passed"])

    def _post_restore(self, request_id: str) -> dict:
        request = self.requests.require(request_id)
        try:
            post = self._bounded("post-restore-backup", self.policy.restore_post_backup_seconds,
                                 lambda: self.take("live", "post-restore", request=request,
                                                   via="in-person", step="post-restore"))
        except ProcedureFailed as failure:
            self._incident(request)
            return self.requests.advance(request_id, "post-restore-pending",
                                         allowed_from=("verifying",),
                                         evidence=[f"pending:{failure.reason}"])
        self.requests.record(request_id, postRestoreBackupId=post["backupId"],
                             evidence=[f"backup:{post['backupId']}"])
        self.requests.authorize_start(request_id)
        return self.finish_restore(request_id)

    def _start_and_route_back(self, request_id: str, request: dict) -> None:
        """v2 started, ready, and the public address routed back to it: as the request's
        own last steps while it is active, or through plain service control once it has
        ended (a failure before the recreate, an abandonment)."""

        def work() -> None:
            if request["state"] in TERMINAL_ENDS:
                self._service_after_end(request_id, "start")
            else:
                self._service(request_id, "start", "start")
            self._wait_ready()
            self._route_after(request_id, request, "v2-host", "route-back")

        self._bounded("start-and-route", self.policy.restore_start_and_route_seconds, work)

    def _service_after_end(self, request_id: str, action: str) -> None:
        """Plain service control once the request has ended: its keys stay unique to
        the request, but nothing is recorded on an ended request."""
        for label in self.platform.labels:
            receipt = self._effect("platform.service.control", label,
                                   {"label": label, "action": action},
                                   key=f"recovery:{request_id}:after-end:{action}:{label}")
            if receipt["outcome"] != "succeeded":
                raise ProcedureFailed(f"service-{action}-failed")

    def _route_after(self, request_id: str, request: dict, origin: str, step: str) -> None:
        if request["state"] not in TERMINAL_ENDS:
            self._route(request_id, origin, step)
            return
        receipt = self._effect("platform.tunnel.route", "tunnel", {"origin": origin},
                               key=f"recovery:{request_id}:after-end:{step}")
        if receipt["outcome"] != "succeeded":
            raise ProcedureFailed("tunnel-route-failed")

    def _wait_ready(self) -> None:
        if not self.platform.ready():
            raise ProcedureFailed("readiness-not-reached")

    def finish_restore(self, request_id) -> dict:
        """The request's own last steps, once `startAuthorizedAt` is recorded: v2
        started, ready and routed back; a failure keeps it `verifying` for a retry
        under this request (BR4.7)."""
        request = self.requests.require(request_id)
        if request["state"] != "verifying" or "startAuthorizedAt" not in request:
            raise OperationsError("CONFLICT", current={"state": request["state"]})
        try:
            self._start_and_route_back(request["recoveryRequestId"], request)
        except ProcedureFailed as failure:
            return self.requests.record(request_id, evidence=[f"retry:{failure.reason}"])
        except OutcomeUnknown as error:
            return self._unknown(request["recoveryRequestId"], error)
        return self.requests.advance(request_id, "succeeded", allowed_from=("verifying",),
                                     evidence=["routed-back"])

    def retry_post_restore(self, request_id) -> dict:
        """`post-restore-pending` → `verifying` under the same request and receipt, with
        no new decision, then the post-restore set again (BR4.7)."""
        self.requests.advance(request_id, "verifying", allowed_from=("post-restore-pending",),
                              evidence=["retry:post-restore"])
        try:
            return self._post_restore(str(request_id))
        except OutcomeUnknown as error:
            return self._unknown(str(request_id), error)

    def abandon(self, request_id) -> dict:
        """The abandonment's empty recreate under the still-held request, bound to your
        decision; only its receipt ends the request failed, and the same decision
        authorizes the start that follows (BR4.7, BR9.10)."""
        request = self.requests.require(request_id)
        if request["state"] != "held" or "abandonmentApprovalId" not in request:
            raise OperationsError("CONFLICT", current={"state": request["state"]})
        try:
            receipt = self._effect(
                "platform.database.recreate", "database-production",
                {"database": self.platform.production, "recoveryRequestId": request_id,
                 "abandonment": True},
                key=self._key(request_id, "abandon-recreate"))
        except OutcomeUnknown as error:
            return self._unknown(request_id, error)
        if receipt["outcome"] != "succeeded":
            return self.requests.record(request_id, evidence=["retry:abandon-recreate"])
        report = self._loss_report(request)
        ended = self.requests.abandoned(request_id, self._facts(receipt), loss_report_ref=report)
        try:
            self._start_and_route_back(request_id, ended)
        except (ProcedureFailed, OutcomeUnknown):
            pass  # the maintenance notice stays until service control routes back
        return self.requests.require(request_id)

    def _loss_report(self, request: dict) -> str:
        """The per-kind report of what the abandonment lost: identifiers and counts."""
        remaining = [item["backupId"] for item in self.ledger.records("backup-set")
                     if item["environment"] == "live" and item.get("integrity") == "passed"
                     and is_open(item)]
        report = {"recoveryRequestId": request["recoveryRequestId"],
                  "remainingPassedSets": remaining, "databaseRecreatedEmpty": True}
        if self.platform.loss_report is not None:
            return self.platform.loss_report(request["recoveryRequestId"], report)
        return f"loss-report:{request['recoveryRequestId']}"

    # --- an unknown outcome -----------------------------------------------------------

    def reconcile(self, request_id) -> dict:
        """Settle an `unknown` request from its receipt, never running the effect again:
        applied or not, a production restore whose recreate began is held, and every
        other request has failed; the operator decides what follows (BR4.4)."""
        request = self.requests.require(request_id)
        if request["state"] != "unknown":
            return request
        from docsuri_ops.platform_control.errors import ControlError

        pending = [ref.removeprefix("pending:") for ref in request["evidenceRefs"]
                   if ref.startswith("pending:")]
        if not pending:
            raise OperationsError("CONFLICT", current={"reasonKey": "no-pending-operation"})
        try:
            settled = self.platform.operator.reconcile(pending[-1])
        except ControlError as error:
            if error.code != "FORBIDDEN":
                raise
            # The store settles an operation only for the actor that bound it (your
            # decision of 2026-10-26, "Bind each login to its actor"): a scheduled
            # request's operation is the standing job's to reconcile
            # (`ScheduledRecovery.settle_unknown`, before its lane's next request), and
            # the in-person word answers which path settles it (review finding, Minor,
            # R16).
            raise OperationsError("FORBIDDEN", current={
                "reasonKey": "operation-bound-by-another-actor",
                "settledBy": "standing-job" if request["origin"] == "schedule"
                else "in-person"}) from None
        if settled.get("reconciliationState") not in ("reconciled-applied",
                                                      "reconciled-not-applied"):
            return request
        evidence = [f"reconciled:{settled.get('reconciliationState')}"]
        recreated = any(ref.startswith("recreate:") for ref in request["evidenceRefs"])
        if request["operation"] == "restore.production" and (
            recreated or "predecessorRequestId" in request
        ):
            return self.requests.settle_unknown(request_id, "held", evidence=evidence)
        if request["operation"] == "backup.create" and settled.get(
                "reconciliationState") == "reconciled-applied":
            failure = self._record_reconciled(request, settled)
            if failure is not None:
                evidence.append(f"record-failed:{failure}")
        return self.requests.settle_unknown(request_id, "failed", evidence=evidence)

    def _record_reconciled(self, request: dict, settled: dict) -> str | None:
        """An applied backup that reconciliation settled: its set and ledger copy
        recorded from what lies beside its `effectReference` (the bound input and the
        effect record's refs), with the dump's own time, so it is in every erasure's
        evidence (U8 plan Step 64(a)). The reason key when the recording failed, or
        None."""
        from docsuri_ops.u8_platform.drivers import parse_facts

        inputs, refs = self._beside(settled)
        if inputs is None or "recordId" not in inputs or not refs:
            return "backup-receipt-incomplete"
        target = str(settled.get("targetId"))
        effect = {"operation": "platform.database.backup", "target": target,
                  "inputs": inputs, "key": "", "environment": request["environment"]}
        receipt = {**settled, "outcome": "succeeded", "effectRefs": refs}
        try:
            facts = parse_facts(refs)
            taken = facts.get("stagingRemovedAt")
            self.record_applied(effect, TRIGGERS[request["origin"]], request, receipt,
                                taken_at=None if taken is None else _time(taken))
        except ProcedureFailed as failure:
            return failure.reason
        except Exception:  # noqa: BLE001 - the request still settles failed, with a reason
            return "recording-failed"
        return None

    # --- the volume retirement (BR4.10) --------------------------------------------------

    def _retirement_allowed(self) -> None:
        cutovers = self.ledger.records("cutover-record")
        state = cutovers[-1] if cutovers else None
        if state is not None and state["state"] in ("switching", "aborting"):
            raise OperationsError("CONFLICT", current={"reasonKey": "live-exclusion-held"})
        if state is not None and state["state"] == "rolling-back" and (
            "rollbackCopyPendingSince" not in state
        ):
            raise OperationsError("CONFLICT", current={"reasonKey": "rollback-not-waiting"})
        restore = self.requests.production_restore_active()
        if restore is not None and not self.requests.restore_waits():
            raise OperationsError("CONFLICT", current={"reasonKey": "restore-not-waiting"})

    def retire_volume(self, approval_id, *, mount: str, identity: str) -> dict:
        """Retire a lost backup volume and name its replacement, in the fixed order."""
        approval = self.ledger.get("maintainer-approval", str(approval_id))
        if approval is None or approval["step"] != "backup-volume-retirement" or approval[
            "decision"
        ] != "approved":
            raise OperationsError("FORBIDDEN", current={"reasonKey": "decision-required"})
        self._retirement_allowed()
        agent = self.platform.agent
        if agent is None or self.platform.current_environment is None:
            raise OperationsError("DEPENDENCY_UNAVAILABLE")
        order = ["decision"]
        agent("prepare-volume", {"mount": mount}, via="in-person")
        order.append("prepare-volume")
        agent("configure", {"mount": mount, "volumeIdentity": identity}, via="in-person")
        order.append("configure")
        status = agent("status", {}, via="in-person")
        if not status.get("available") or status.get("volumeIdentity") != identity:
            raise OperationsError("CONFLICT", current={"reasonKey": "volume-check-failed"})
        order.append("status")
        value = {"identity": identity, "mount": mount}
        receipt = self._effect("platform.profile.backup-volume", "profile",
                               {"field": "backupVolume", "value": value,
                                "approvalId": approval["approvalId"]},
                               key=f"retire-volume:{approval['approvalId']}")
        if receipt["outcome"] != "succeeded":
            raise OperationsError("CONFLICT", current={"reasonKey": "profile-change-refused"})
        order.append("profile")
        if status.get("volumeIdentity") != value["identity"]:
            raise OperationsError("CONFLICT", current={"reasonKey": "backup-volume-mismatch"})
        order.append("comparison")
        closed = self._close_retired(approval)
        result = {"order": order, "closed": closed, "receiptId": receipt["receiptId"]}
        self._take_on_replacement(approval, result)
        return result

    def _take_on_replacement(self, approval: dict, result: dict) -> None:
        """A backup and a ledger copy on the replacement at once (NFR7.11, U8 plan Step
        64(h)): first the operator's own interrupted operations on the take's targets are
        settled, so a run after an interrupted take replays a settled receipt; then a set
        of the current environment with its ledger copy, or only a lone ledger copy while
        a production restore is active, the cutover is rolling back, or the environment
        has no database to dump. A take that fails is reported (`takeFailed`), and the
        retirement stands."""
        environment = self.platform.current_environment()
        owner_key = f"retire-volume:{approval['approvalId']}"
        target = "database-production" if environment == "live" else "database-rehearsal"
        self.reconcile_interrupted((target, "ledger-copy"))
        cutovers = self.ledger.records("cutover-record")
        rolling_back = bool(cutovers) and cutovers[-1]["state"] == "rolling-back"
        lone = (self.requests.production_restore_active("live") is not None or rolling_back)
        if not lone:
            try:
                self.platform.database_of(environment)
            except ProcedureFailed:
                lone = True
        order = result["order"]
        if lone:
            order.append("ledger-copy")
            try:
                self.ledger_copy_alone(environment, owner_key=owner_key, via="in-person")
            except ProcedureFailed as failure:
                result["takeFailed"] = failure.reason
            except OutcomeUnknown:
                result["takeFailed"] = "effect-outcome-unknown"
            return
        order.append("backup")
        try:
            self.take(environment, "volume-retirement", request=None, via="in-person",
                      owner_key=owner_key)
        except (ProcedureFailed, OutcomeUnknown) as failure:
            result["takeFailed"] = getattr(failure, "reason", "effect-outcome-unknown")
            self._signal(owner_key, environment)

    def _close_retired(self, approval: dict) -> int:
        """Every undisposed record with files on the retired volume is closed with
        `retiredWithVolumeAt` and the retirement decision's receipt (BR4.10, L1-18): only
        records taken at or before your decision's `recordedAt` (a set's or ledger copy's
        `takenAt`, a retained copy's `createdAt`), since nothing reaches a lost volume
        after it, so a second run closes nothing on the replacement."""
        now = utc_text(self.clock())
        decided = _parse(str(approval.get("recordedAt") or now))
        receipt_ref = str(approval["operatorReceiptRef"])
        closed = 0
        for kind in ("backup-set", "ledger-copy"):
            for record in self.ledger.records(kind):
                if any(name in record for name in ("disposedAt", "retiredWithVolumeAt")):
                    continue
                if _parse(record["takenAt"]) > decided:
                    continue
                key = record["backupId" if kind == "backup-set" else "ledgerCopyId"]
                self.ledger.append(kind, {**record, "retiredWithVolumeAt": now,
                                          "retirementReceiptRef": receipt_ref},
                                   expect_revision=self.ledger.revision(kind, key))
                closed += 1
        for record in self.copies.undisposed():
            if record["kind"] in VOLUME_KINDS and _parse(record["createdAt"]) <= decided:
                self.copies.retire(record["copyId"], receipt_ref=receipt_ref)
                closed += 1
        return closed


TERMINAL_ENDS = frozenset({"failed", "succeeded"})
