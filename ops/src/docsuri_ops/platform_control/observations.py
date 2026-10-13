"""Observations bridge: pull-based outcome exposure and the C11 coordination item.

U8 pulls evidence and receipts through C10 (`inspectEvidence`/`readReceipt`). Any
push of bounded, privacy-safe observations into the operations view would use the
operations owner's C11 `recordObservation` contract and requires U7 to be a
registered provider; that is a recorded coordination item, not an implemented
push. A local status view derives counts from the receipt store.
"""

from __future__ import annotations

from typing import Any

from . import enums
from .store import Store

C11_COORDINATION_ITEM = (
    "U7 exposes operation outcomes through C10 pull; a push into the operations "
    "view uses C11 recordObservation and requires U7 provider registration "
    "(recorded coordination item; not implemented in this unit)."
)


def status_summary(store: Store, actor: str, authority_id: str) -> dict[str, Any]:
    """A bounded, privacy-safe status view, target-scope bounded to the caller."""
    counts = store.status_counts(actor, authority_id)
    unresolved = store.list_unresolved(actor, authority_id)
    return {
        "counts": {
            key: int(counts.get(key, 0))
            for key in ("authorized", "executing", *enums.TERMINAL_STATES)
        },
        "unresolvedCount": len(unresolved),
        "unresolvedOperations": [item.get("operationId") for item in unresolved],
        "coordinationItem": C11_COORDINATION_ITEM,
    }
