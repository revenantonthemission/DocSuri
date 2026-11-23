"""Retained copies: every copy that may hold personal data outside the live service, in
the operations ledger (U8 plan Steps 29 and 31; BR4.5, BR9.12, BR9.17, BR4.10).

A copy is recorded as a `retained-copy` before anything is written to it, with every
location it will occupy (BR9.12). Its earliest disposal point is fixed when it is
recorded:

- for `v1-final-snapshot`, `v1-stores` and `rolled-back-v2-database`, the date your
  decision approved (`disposalApprovalId` required);
- for every other kind, its backstop date from the operations policy, by which the copy
  is disposed even if its disposal event never comes (NFR3.12's table).

A copy then moves only forward: `complete` records its checksum when copying finished;
`disposal_pending` keeps `disposalPendingSince` when a disposal could not complete;
`disposed` records `disposedAt` with the receipt of PlatformControl's disposal
operation, and `disposed_by_agent` with the backup agent's own receipt when its
unattended pass deleted the file on its catalogue's terms (Step 33); `backstop_of` and
`past_backstop` read each copy's backstop date for the disposal pass; `retire` closes
it with `retiredWithVolumeAt` when its volume is retired as lost for good (BR4.10);
`returned_to_service` ends a `v1-stores` copy when a rollback returns v1 to service
(BR9.7).

`receipt_facts` turns a PlatformControl receipt (as `Operator.execute` returns it) into
the binding facts every receipt-bearing ledger record repeats: operation, target, input
hash and outcome (decision "PlatformControl's store in production").
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Iterable
from uuid import UUID, uuid4

from .errors import OperationsError
from .ledger import Ledger, utc_text

KIND = "retained-copy"
# The policy field of each kind's backstop (NFR3.12; u8_policy).
BACKSTOPS = {
    "dry-run-snapshot": "dry_run_copy_backstop_seconds",
    "rehearsal-database": "rehearsal_database_backstop_seconds",
    "import-database": "import_database_backstop_seconds",
    "scratch-restore": "scratch_restore_backstop_seconds",
    "v1-final-snapshot": "final_snapshot_backstop_seconds",
    "v1-stores": "v1_stores_backstop_seconds",
    "rolled-back-v2-database": "rolled_back_backstop_seconds",
}
# The kinds whose disposal date your decision approves (BR9.12).
DECIDED_KINDS = frozenset({"v1-final-snapshot", "v1-stores", "rolled-back-v2-database"})
# The kinds whose files are on the backup volume (closed when it is retired, BR4.10).
VOLUME_KINDS = frozenset({"dry-run-snapshot", "v1-final-snapshot", "rolled-back-v2-database"})
CLOSED = ("disposedAt", "retiredWithVolumeAt", "returnedToServiceAt")


def _parse(text: str) -> dt.datetime:
    return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))


def receipt_facts(receipt: dict, *, now: dt.datetime) -> dict:
    """The binding facts of one PlatformControl receipt, as a ledger record repeats them."""
    outcome = receipt.get("outcome")
    if outcome not in ("accepted", "running", "succeeded", "failed", "unknown"):
        raise ValueError("receipt outcome outside C10's vocabulary")
    return {
        "receiptId": str(UUID(str(receipt["receiptId"]))),
        "operationId": str(UUID(str(receipt["operationId"]))),
        "operation": str(receipt["operation"]),
        "targetId": str(receipt["targetId"]),
        "inputHash": str(receipt["inputHash"]),
        "outcome": outcome,
        "confirmedAt": utc_text(now),
    }


def is_open(record: dict) -> bool:
    """A copy still counted: neither disposed, retired nor returned to service."""
    return not any(name in record for name in CLOSED)


class RetainedCopies:
    def __init__(self, ledger: Ledger, policy, *, clock: Callable[[], dt.datetime] | None = None):
        self.ledger, self.policy = ledger, policy
        self.clock = clock or ledger.clock

    # --- reading -------------------------------------------------------------------

    def get(self, copy_id) -> dict | None:
        return self.ledger.get(KIND, str(copy_id))

    def undisposed(self, kind: str | None = None) -> list[dict]:
        return [
            record for record in self.ledger.records(KIND)
            if is_open(record) and (kind is None or record["kind"] == kind)
        ]

    def backstop(self, kind: str, now: dt.datetime) -> dt.datetime:
        if kind not in BACKSTOPS:
            raise OperationsError("INVALID_INPUT")
        return now + dt.timedelta(seconds=getattr(self.policy, BACKSTOPS[kind]))

    def due(self, now: dt.datetime | None = None) -> list[dict]:
        """Open copies whose disposal point has passed."""
        moment = now or self.clock()
        return [record for record in self.undisposed()
                if _parse(record["disposeAfter"]) <= moment]

    # --- the record's versions -----------------------------------------------------

    def record(self, kind: str, source_ref: str, locations: Iterable[str], *,
               staging_location: str | None = None, dispose_after: dt.datetime | None = None,
               approval_id=None, copy_id=None) -> dict:
        """Record a copy before anything is written to it (BR9.12)."""
        now = self.clock()
        places = list(dict.fromkeys(locations))
        if kind in DECIDED_KINDS:
            if dispose_after is None or approval_id is None:
                raise OperationsError("POLICY_UNRESOLVED")
            point = dispose_after
        else:
            if dispose_after is not None or approval_id is not None:
                raise OperationsError("INVALID_INPUT")
            point = self.backstop(kind, now)
        record = {
            "copyId": str(copy_id or uuid4()), "kind": kind, "sourceRef": source_ref,
            "createdAt": utc_text(now), "locations": places, "disposeAfter": utc_text(point),
        }
        if staging_location is not None:
            record["stagingLocation"] = staging_location
        if approval_id is not None:
            record["disposalApprovalId"] = str(approval_id)

        def step(view):
            prior = view.get(KIND, record["copyId"])
            if prior is not None:
                return prior
            view.append(KIND, record, expect_revision=0)
            return record

        return self.ledger.atomic(step)

    def _version(self, copy_id, change: Callable[[dict], dict], *,
                 receipts: tuple[dict, ...] = ()) -> dict:
        identity = str(UUID(str(copy_id)))

        def step(view):
            current = view.get(KIND, identity)
            if current is None:
                raise OperationsError("NOT_FOUND")
            record = change(dict(current))
            if record == current:
                return current
            view.append(KIND, record, expect_revision=view.revision(KIND, identity),
                        receipts=receipts)
            return record

        return self.ledger.atomic(step)

    def complete(self, copy_id, *, checksum: str | None = None,
                 source_database_bytes: int | None = None,
                 staging_removed_at: dt.datetime | None = None,
                 part_sizes: dict[str, int] | None = None) -> dict:
        """Copying finished: its checksum and completion time (snapshot kinds), and a
        snapshot's size by part (`partSizes`, outside its parts file and digest, NFR7.14)."""
        now = self.clock()

        def change(record: dict) -> dict:
            if not is_open(record):
                raise OperationsError("CONFLICT")
            if "completedAt" in record:
                return record
            record["completedAt"] = utc_text(now)
            if checksum is not None:
                record["checksum"] = checksum
            if source_database_bytes is not None:
                record["sourceDatabaseBytes"] = source_database_bytes
            if staging_removed_at is not None:
                record["stagingRemovedAt"] = utc_text(staging_removed_at)
            if part_sizes is not None:
                record["partSizes"] = {str(name): int(size) for name, size in part_sizes.items()}
            return record

        return self._version(copy_id, change)

    def disposal_pending(self, copy_id, *, failed: bool = False) -> dict:
        """The disposal point was reached but the disposal could not complete; the copy
        stays counted in erasure evidence (BR9.17). `disposalPendingSince` keeps the
        first time; a failed attempt (`failed`: a removal that did not settle applied, a
        `dispose-due` refused or unreachable) also records `lastDisposalFailedAt` at each
        attempt (U8 plan Step 64(i))."""
        now = self.clock()

        def change(record: dict) -> dict:
            if not is_open(record):
                return record
            record.setdefault("disposalPendingSince", utc_text(now))
            if failed:
                record["lastDisposalFailedAt"] = utc_text(now)
            return record

        return self._version(copy_id, change)

    def disposed_by_verification(self, copy_id, verification_id: str) -> dict:
        """A scratch database the verification recorded before its restore, dropped
        through the scheduler's database login (or refused before anything was created):
        closed citing that verification, since there is no PlatformControl receipt to
        cite (U8 plan Step 64(d))."""
        now = self.clock()

        def change(record: dict) -> dict:
            if "disposedAt" in record:
                return record
            if not is_open(record):
                raise OperationsError("CONFLICT")
            record.pop("disposalPendingSince", None)
            record["disposedAt"] = utc_text(now)
            record["disposalVerificationRef"] = f"verification:{verification_id}"
            return record

        return self._version(copy_id, change)

    def redated(self, copy_id, *, dispose_after: dt.datetime, approval: dict) -> dict:
        """A decided copy's date moved by your re-dating decision (L1-3): the new
        `disposeAfter`, at most its kind's backstop, with that decision's approval and
        receipt. Any other kind is refused (`INVALID_INPUT`), a closed copy too
        (`CONFLICT`)."""
        receipt_ref = str(UUID(str(approval["operatorReceiptRef"])))
        approval_id = str(UUID(str(approval["approvalId"])))

        def change(record: dict) -> dict:
            if record["kind"] not in DECIDED_KINDS:
                raise OperationsError("INVALID_INPUT")
            if not is_open(record):
                raise OperationsError("CONFLICT")
            if dispose_after > self.backstop_of(record):
                raise OperationsError("INVALID_INPUT",
                                      current={"reasonKey": "past-the-backstop"})
            record["disposeAfter"] = utc_text(dispose_after)
            record["disposalApprovalId"] = approval_id
            record["redateReceiptRef"] = receipt_ref
            return record

        return self._version(copy_id, change)

    def disposed(self, copy_id, receipt: dict) -> dict:
        """Disposed through its one path, on the receipt of PlatformControl's disposal
        operation (BR9.17)."""
        now = self.clock()
        if receipt.get("outcome") != "succeeded":
            raise OperationsError("CONFLICT")
        facts = receipt_facts(receipt, now=now)

        def change(record: dict) -> dict:
            if "disposedAt" in record:
                return record
            if not is_open(record):
                raise OperationsError("CONFLICT")
            record.pop("disposalPendingSince", None)
            record["disposedAt"] = utc_text(now)
            record["disposalReceiptRef"] = facts["receiptId"]
            return record

        return self._version(copy_id, change, receipts=(facts,))

    def disposed_in_person(self, copy_id, receipt: dict, check_ref: str) -> dict:
        """v1's stores, deleted by the operator by hand at the approved date: the
        deletion recorded with its time, the receipt of the in-person check that bound
        it, and that check's evidence (the person's decision of 2026-10-22, BR9.17). The
        system never deletes v1's data itself."""
        now = self.clock()
        if receipt.get("outcome") != "succeeded":
            raise OperationsError("CONFLICT")
        facts = receipt_facts(receipt, now=now)

        def change(record: dict) -> dict:
            if record["kind"] != "v1-stores":
                raise OperationsError("INVALID_INPUT")
            if "disposedAt" in record:
                return record
            if not is_open(record):
                raise OperationsError("CONFLICT")
            if _parse(record["disposeAfter"]) > now:
                raise OperationsError("CONFLICT", current={"reasonKey": "before-approved-date"})
            record.pop("disposalPendingSince", None)
            record["disposedAt"] = utc_text(now)
            record["disposalReceiptRef"] = facts["receiptId"]
            record["disposalCheckRef"] = check_ref
            return record

        return self._version(copy_id, change, receipts=(facts,))

    def disposed_by_agent(self, copy_id, agent_ref: str) -> dict:
        """The backup agent deleted the copy's file on its catalogue's terms in the
        unattended disposal pass; its receipt (the path it reported disposed) sets
        `disposedAt` (Workflow 19 step 9, BR9.17)."""
        now = self.clock()

        def change(record: dict) -> dict:
            if "disposedAt" in record:
                return record
            if not is_open(record):
                raise OperationsError("CONFLICT")
            record.pop("disposalPendingSince", None)
            record["disposedAt"] = utc_text(now)
            record["disposalAgentRef"] = agent_ref
            return record

        return self._version(copy_id, change)

    def backstop_of(self, record: dict) -> dt.datetime:
        """The copy's backstop date: by its kind's backstop after it was recorded, which
        for a decided kind lies beyond the date your decision approved (NFR3.12)."""
        return _parse(record["createdAt"]) + dt.timedelta(
            seconds=getattr(self.policy, BACKSTOPS[record["kind"]]))

    def past_backstop(self, now: dt.datetime | None = None) -> list[dict]:
        """Open copies still in place after their backstop date."""
        moment = now or self.clock()
        return [record for record in self.undisposed() if self.backstop_of(record) < moment]

    def retire(self, copy_id, *, at: dt.datetime | None = None,
               receipt_ref: str | None = None) -> dict:
        """Closed with its retired volume (BR4.10), citing the retirement decision's
        receipt (`retirementReceiptRef`, L1-18)."""
        moment = at or self.clock()

        def change(record: dict) -> dict:
            if not is_open(record):
                return record
            record["retiredWithVolumeAt"] = utc_text(moment)
            if receipt_ref is not None:
                record["retirementReceiptRef"] = str(UUID(str(receipt_ref)))
            return record

        return self._version(copy_id, change)

    def returned_to_service(self, copy_id) -> dict:
        """A rollback returned v1 to service: its stores stop counting (BR9.7)."""
        now = self.clock()

        def change(record: dict) -> dict:
            if record["kind"] != "v1-stores":
                raise OperationsError("INVALID_INPUT")
            if not is_open(record):
                return record
            record["returnedToServiceAt"] = utc_text(now)
            return record

        return self._version(copy_id, change)
