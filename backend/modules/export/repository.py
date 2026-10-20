"""Owner-scoped store for every ApprovedExport record (U6), shaped like
`TopicsRepository`.

`run(authority, action)` rechecks live session authority through `transactions.guard`
(purpose `local-research`, because an export sends a research result; security design
§3) before the owner unit touches a row, inside `transactions.run("export", …)`.
`system(action)` runs the worker's and the lane's units as the service.

Rules every unit follows:

- a unit is one closure that may be re-run after a serialization retry and never
  calls Notion (D8);
- argument checks run before the transaction and raise
  `ExportError("INVALID_ARGUMENT", current={"field": …})`;
- savepoints translate unique and check violations into the operation's own codes;
- a foreign record and an absent one raise the same `LookupError`;
- worker and lane units return None when the record moved on.

The units live in one module per concern and are composed here:

- `connection_store.ConnectionUnits`: the owner's connection, the pending
  reservation, revocation and availability (BR1.3–BR1.6, R-01–R-03, D16);
- `preview_store.PreviewUnits`: preview pairs and frozen revisions (BR2.3, BR2.5);
- `approval_store.ApprovalUnits`: approve, bind, cancel and settle (BR3, BR4.5, BR5);
- `effect_reads.EffectReadUnits`: the effect read and the export history (A2, A4);
- `lane_store.LaneUnits`: hand-over, claim, outcomes, scans, orphans and pace (§8, §9);
- `housekeeping_store.HousekeepingUnits`: the pass's bounded batches (D4, BR2.6).
"""

from uuid import UUID

from backend.transactions import Authority, OwnerTransactions, guard
from backend.u6_policy import SYNTHETIC_EXPORT, ExportPolicy

from .approval_store import ApprovalUnits
from .connection_store import ConnectionSlot, ConnectionUnits, SealedToken
from .effect_reads import EffectReadUnits
from .housekeeping_store import HousekeepingUnits
from .lane_store import (
    CheckResult,
    Claimed,
    ClaimRefused,
    LaneUnits,
    PaceSlot,
    WriteOutcome,
)
from .preview_store import PreviewFacts, PreviewUnits, RenderedRevision
from .store_support import Replay, replay_input_hash, require_uuid, session_current

__all__ = [
    "CheckResult",
    "Claimed",
    "ClaimRefused",
    "ConnectionSlot",
    "ExportRepository",
    "PaceSlot",
    "PreviewFacts",
    "RenderedRevision",
    "Replay",
    "SealedToken",
    "WriteOutcome",
    "replay_input_hash",
]


class ExportRepository(
    ConnectionUnits,
    PreviewUnits,
    ApprovalUnits,
    EffectReadUnits,
    LaneUnits,
    HousekeepingUnits,
):
    def __init__(self, transactions: OwnerTransactions, policy: ExportPolicy = SYNTHETIC_EXPORT):
        if not isinstance(policy, ExportPolicy):
            raise TypeError("an ExportPolicy is required")
        self.transactions = transactions
        self.policy = policy

    def run(self, authority: Authority, action):
        def guarded(conn):
            guard(conn, authority)
            return action(conn)

        return self.transactions.run("export", guarded)

    def system(self, action):
        return self.transactions.run("export", action)

    def session_is_current(self, account_id: UUID, session_id: UUID) -> bool:
        """Whether an approving session is still current, by AccountAccess's own guard
        (BR3.3, BR3.7). False is the definite 42501 answer; any other fault propagates,
        so the caller treats it as could-not-check."""
        require_uuid(account_id, "accountId")
        require_uuid(session_id, "sessionId")
        return self.system(lambda conn: session_current(conn, account_id, session_id))
