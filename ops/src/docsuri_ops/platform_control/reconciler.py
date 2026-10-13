"""Receipt reconciliation: resolve an unknown effect from the target, never re-run it.

Reconciliation is a read against the recorded ``targetEffectReference``. It
records applied/not-applied without repeating the effect and never auto-promotes
an operation's outcome; when the target cannot be read the receipt stays
``unresolved`` rather than guessing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .store import Store


def _resolve_reference(target_root: Path, reference: str) -> Path | None:
    base = target_root.resolve()
    candidate = (base / reference).resolve()
    if candidate == base or base not in candidate.parents:
        return None
    return candidate


def promote_stale(store: Store) -> int:
    """Promote every over-deadline in-flight operation to ``unknown``.

    Called on the supervisor's startup path and on every receipt-read path so an
    interrupted effect is surfaced truthfully instead of staying stuck in flight.
    """
    return store.promote_in_flight()


def reconcile_unknown(
    store: Store, target_root: Path, operation_id: str, actor: str, authority_id: str
) -> dict[str, Any]:
    """Reconcile one receipt; return the receipt unchanged when nothing can be proven."""
    receipt = store.read_receipt(actor, authority_id, operation_id)
    if (
        receipt.get("outcome") != "unknown"
        or receipt.get("reconciliationState") != "unresolved"
    ):
        return receipt
    reference = receipt.get("effectReference")
    if not isinstance(reference, str) or not reference:
        return receipt
    path = _resolve_reference(target_root, reference)
    if path is None:
        return receipt
    try:
        present = path.is_file() and path.stat().st_size > 0
    except OSError:
        return receipt
    evidence = [f"target:{reference}:{'present' if present else 'absent'}"]
    return store.reconcile_receipt(
        operation_id=operation_id, applied=present, evidence=evidence
    )
