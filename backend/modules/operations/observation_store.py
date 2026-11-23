"""ServiceOperations' observation records: data access (U8 plan Step 7; BR3.1-BR3.6, O1).

Rows live in `operations.observation_record` (`ops/src/docsuri_ops/u8_operations.sql`)
and are written only as the operations owner's runtime login, which holds SELECT and
INSERT there and may delete only through the bounded function. Each call is one short
transaction: a bounded insert, the latest record of each named capability read on the
`(capability, observed_at DESC)` index, or one bounded deletion pass. Records carry
registered keys, counts and identifiers only, never private text (BR3.4).
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from uuid import UUID, uuid4

OWNER = "operations"
KEY = re.compile(r"[a-z][a-z0-9.-]{0,63}")


def current_request_id() -> UUID | None:
    """D13: an observation recorded while a request runs carries its identifier."""
    from backend.local_browser import CURRENT_REQUEST_ID

    value = CURRENT_REQUEST_ID.get()
    return None if value is None else UUID(value)
OUTCOMES = ("available", "degraded", "unavailable", "unknown")
MAX_INSERT = 60  # one producer's buffer (observability-design § 3.1)
MAX_CAPABILITIES = 64
MAX_LIMITATIONS = 16
MAX_DELETE = 10_000


@dataclass(frozen=True)
class ObservationRow:
    capability: str
    producer: str
    outcome: str
    observed_at: dt.datetime
    revision: int
    reason_key: str | None = None
    limitation_keys: tuple[str, ...] = ()
    error_count: int = 0
    total_count: int = 0
    # L1-46: observations this producer's buffer dropped since its process started.
    dropped_count: int = 0
    request_id: UUID | None = field(default_factory=current_request_id)
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        for name in ("capability", "producer"):
            if not isinstance(getattr(self, name), str) or not KEY.fullmatch(getattr(self, name)):
                raise ValueError(f"observation {name} outside the registered form")
        if self.outcome not in OUTCOMES:
            raise ValueError("observation outcome outside the registered set")
        if self.reason_key is not None and not KEY.fullmatch(self.reason_key):
            raise ValueError("observation reason key outside the registered form")
        if self.outcome != "available" and self.reason_key is None:
            raise ValueError("a non-available observation names its reason key")
        if len(self.limitation_keys) > MAX_LIMITATIONS or not all(
            isinstance(key, str) and KEY.fullmatch(key) for key in self.limitation_keys
        ):
            raise ValueError("observation limitation keys outside the registered form")
        if (
            type(self.error_count) is not int
            or type(self.total_count) is not int
            or not 0 <= self.error_count <= self.total_count
            or type(self.dropped_count) is not int
            or self.dropped_count < 0
        ):
            raise ValueError("observation counts outside their bounds")
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("observation revision must be positive")
        if self.observed_at.tzinfo is None:
            raise ValueError("observation time must be aware")


class ObservationStore:
    def __init__(self, transactions):
        self.transactions = transactions

    def insert(self, rows: Sequence[ObservationRow]) -> int:
        """At most one buffer of records, in one transaction. Idempotent per row id: a
        buffered row written by a commit whose outcome was unknown (`UnknownCommit`) is
        skipped when it is written again, and still counts as written."""
        rows = list(rows)
        if not 1 <= len(rows) <= MAX_INSERT or not all(
            isinstance(row, ObservationRow) for row in rows
        ):
            raise ValueError("observation insert outside its bound")

        def write(conn):
            for row in rows:
                conn.execute(
                    "INSERT INTO operations.observation_record(id,capability,producer,outcome,"
                    "reason_key,limitation_keys,error_count,total_count,dropped_count,"
                    "request_id,revision,observed_at) "
                    "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING",
                    (
                        row.id, row.capability, row.producer, row.outcome, row.reason_key,
                        list(row.limitation_keys), row.error_count, row.total_count,
                        row.dropped_count, row.request_id, row.revision, row.observed_at,
                    ),
                )
            return len(rows)

        return self.transactions.run(OWNER, write)

    def latest(self, capabilities: Sequence[str]) -> dict[str, dict]:
        """The newest record of each named capability, one index probe each. A tie on
        `observed_at` (a renewal written while the clock is held) goes to the higher
        revision. `Observations` numbers from `max(prev + 1, stamp)` and, before a
        capability's first write in a process, seeds from the revision this read returns
        for it: a restarted process then numbers above every row at the newest stored
        instant, so a same-instant renewal wins. This is not the highest revision stored:
        after a backward clock step an earlier-stamped row can carry a higher one. A row
        stamped earlier still loses to a later one, whatever its revision."""
        names = sorted(set(capabilities))
        if not 1 <= len(names) <= MAX_CAPABILITIES or not all(
            isinstance(name, str) and KEY.fullmatch(name) for name in names
        ):
            raise ValueError("capability list outside its bound")

        def read(conn):
            rows = conn.execute(
                "SELECT r.* FROM unnest(%s::text[]) AS c(capability) CROSS JOIN LATERAL ("
                "SELECT * FROM operations.observation_record o WHERE o.capability=c.capability "
                "ORDER BY o.observed_at DESC, o.revision DESC LIMIT 1) r",
                (names,),
            ).fetchall()
            return {row["capability"]: row for row in rows}

        return self.transactions.run(OWNER, read)

    def delete_old(self, now: dt.datetime, *, limit: int = 1000) -> int:
        """One bounded pass removing records older than 14 days before `now`."""
        if now.tzinfo is None or type(limit) is not int or not 1 <= limit <= MAX_DELETE:
            raise ValueError("observation deletion outside its bound")
        return self.transactions.run(
            OWNER,
            lambda conn: conn.execute(
                "SELECT operations.delete_old_observations(%s,%s) AS removed", (now, limit)
            ).fetchone()["removed"],
        )
