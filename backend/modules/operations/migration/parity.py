"""The parity report (U8 plan Step 31; BR8.10, BR8.9, Workflow 9 step 4).

For each kind the report holds the source count, what was imported, unchanged and
updated, what your decisions mapped, what was skipped by reason and excluded by
decision, and two order-independent checksums over the compared normalized fields: the
source side's, from the digests the owners answered each import with, and the target
side's, from each owner's own parity read of what it stores. A kind reconciles only when
its counts add up and the two checksums match. Every skipped or excluded record is named
by kind and source id, and records a final run meets for the first time are listed
apart (`newInFinal`). The `paper` entry also holds `limits` (U8 plan Step 68(i), L1-79):
each corpus limit's value, whether an import checks it, the largest value measured among
the papers the run imported or found already imported, and how many papers it refused.

The report holds no password, hash of a password, token, email address or content: only
counts, reason keys, source identifiers and checksums. It is written owner-only (0600)
into the profile's evidence folder, and its digest goes to the ledger with the run.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable, Iterable
from pathlib import Path

import rfc8785

from backend.import_parity import parity_digest

from .phases import Owners, Tally

# The kinds an owner holds, and the owner parity read that answers for each.
TARGET_KINDS = {
    "account": lambda owners, now: owners.accounts.parity("account", now=now),
    "identity-link": lambda owners, now: owners.accounts.parity("identity-link", now=now),
    "preferences": lambda owners, now: owners.settings.parity(now=now),
    "paper": lambda owners, now: owners.papers.imports.parity(now=now),
    "saved-paper": lambda owners, now: owners.saved.parity(now=now),
    # The grants by outcome (the person's decision of 2026-10-23).
    "usage-grant": lambda owners, now: owners.usage.imported_parity(now=now),
}
EMPTY = parity_digest([])


def kind_entry(tally: Tally, target: dict | None, *, new_in_final: set[tuple[str, str]]) -> dict:
    entry = tally.as_dict()
    landed = tally.imported + tally.unchanged + tally.updated
    accounted = landed + tally.mapped + sum(tally.skipped.values()) + sum(
        tally.excluded.values())
    entry["sourceChecksum"] = parity_digest(tally.digests)
    if target is None:
        entry["targetChecksum"] = EMPTY
        reconciles = accounted == tally.source and landed == 0
    else:
        entry["targetChecksum"] = target["digest"]
        reconciles = (accounted == tally.source and target["count"] == landed
                      and target["digest"] == entry["sourceChecksum"])
    entry["reconciles"] = reconciles
    entry["misfits"] = [
        {"kind": kind, "sourceId": source, "reasonKey": reason,
         "newInFinal": (kind, reason) in new_in_final}
        for kind, source, reason in tally.misfits
    ]
    return entry


def build(run_id: str, tallies: dict[str, Tally], owners: Owners, *, now,
          new_in_final: Iterable[tuple[str, str]] = ()) -> dict:
    fresh = set(new_in_final)
    kinds = []
    for name in sorted(tallies):
        reader = TARGET_KINDS.get(name)
        target = reader(owners, now) if reader is not None else None
        kinds.append(kind_entry(tallies[name], target, new_in_final=fresh))
    return {
        "runId": run_id, "kinds": kinds,
        "reconciles": all(item["reconciles"] for item in kinds),
        "newInFinal": sorted({f"{kind}:{reason}" for kind, reason in fresh}),
    }


def misfit_pairs(report: dict) -> set[tuple[str, str]]:
    return {(item["kind"], item["reasonKey"]) for entry in report["kinds"]
            for item in entry["misfits"]}


def report_digest(report: dict) -> str:
    return hashlib.sha256(rfc8785.dumps(report)).hexdigest()


def write(folder: Path, report: dict) -> tuple[str, str]:
    """The report written owner-only into the evidence folder; its file name and digest."""
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    payload = rfc8785.dumps(report)
    name = f"parity-{report['runId']}.json"
    path = folder / name
    pending = folder / f".{name}.pending"
    descriptor = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(pending, path)
    return f"evidence/migration/{name}", hashlib.sha256(payload).hexdigest()


Reader = Callable[[Owners, object], dict]
