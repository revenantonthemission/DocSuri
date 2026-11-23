"""Time Machine's two fixed-path exclusions (U8 plan Step 37; security-design § 6.7,
NFR3.7, Workflow 20 step 3).

As root, `tmutil addexclusion -p` for `/Library/DocSuri/` as a whole and OrbStack's
data folder, so no Time Machine backup holds v2's keys, credentials, database, ledger or
logs, or v1's data. A fixed-path exclusion holds whatever the folder contains later.
The isolation check's `isolation-backups` item confirms both with `tmutil isexcluded`
every 5 minutes; `missing` is the installer's own check of the same.
"""

from __future__ import annotations

from docsuri_ops.isolation_check import EXCLUSIONS


def missing(tools, exclusions: tuple[str, ...] = EXCLUSIONS) -> list[str]:
    """The exclusions that do not hold now (unknown counts as not holding)."""
    return [path for path in exclusions if tools.excluded(path) is not True]


def exclude(tools, path: str) -> None:
    if path not in EXCLUSIONS:
        raise ValueError("only the two fixed exclusions are set")
    tools.exclude(path)
