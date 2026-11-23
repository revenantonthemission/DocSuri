"""Library's A4 saved-paper writes and parity read (U8 plan Step 7; BR8.2, BR8.3).

One saved paper per account and paper (`library.saved_paper`'s key), so saved papers
that differ only by version suffix collapse into one row; which v1 record keeps it, and
which ones answer `duplicate-by-version`, is the import operation's choice (Step 31).
The row is written as Library's own login, and the owner's trigger checks the corpus
reference: a paper that was not imported answers `refused` with
`dependency-not-migrated`, inside a savepoint, so nothing else in the call is undone.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from uuid import UUID

import psycopg

from backend.import_parity import decide, outcome, parity, stored_digest

OWNER = "library"
MAX_PARITY_RECORDS = 100_000
_REFERENCE_REFUSALS = (
    psycopg.errors.InsufficientPrivilege,
    psycopg.errors.RaiseException,
    psycopg.errors.ForeignKeyViolation,
    psycopg.errors.CheckViolation,
)


def _time(moment: dt.datetime) -> str:
    if moment.tzinfo is None:
        raise ValueError("import times must be aware")
    return moment.astimezone(dt.UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def saved_fields(*, account_id: UUID, paper_id: str, version_id: str,
                 saved_at: dt.datetime) -> dict:
    for name, value in (("paper", paper_id), ("version", version_id)):
        if not isinstance(value, str) or not 1 <= len(value) <= 160:
            raise ValueError(f"saved {name} identity outside its bound")
    return {
        "account": str(account_id), "paper": paper_id, "version": version_id,
        "savedAt": _time(saved_at),
    }


def _stored(row: dict) -> dict:
    return saved_fields(
        account_id=row["account_id"], paper_id=row["paper_id"], version_id=row["version_id"],
        saved_at=row["saved_at"],
    )


class SavedPaperImports:
    def __init__(self, transactions):
        self.transactions = transactions

    def import_saved_paper(
        self, account_id: UUID, *, paper_id: str, version_id: str, saved_at: dt.datetime
    ) -> dict:
        incoming = stored_digest(saved_fields(
            account_id=account_id, paper_id=paper_id, version_id=version_id, saved_at=saved_at
        ))

        def write(conn):
            row = conn.execute(
                "SELECT * FROM library.saved_paper WHERE account_id=%s AND paper_id=%s "
                "FOR UPDATE",
                (account_id, paper_id),
            ).fetchone()
            disposition = decide(stored_digest(_stored(row)) if row else None, incoming)
            if disposition == "unchanged":
                return outcome(disposition, incoming)
            try:
                with conn.transaction():
                    if disposition == "imported":
                        conn.execute(
                            "INSERT INTO library.saved_paper(account_id,paper_id,version_id,"
                            "revision,saved_at,disposition) VALUES(%s,%s,%s,gen_random_uuid(),"
                            "%s,'active')",
                            (account_id, paper_id, version_id, saved_at),
                        )
                    else:
                        conn.execute(
                            "UPDATE library.saved_paper SET version_id=%s,saved_at=%s,"
                            "revision=gen_random_uuid() WHERE account_id=%s AND paper_id=%s",
                            (version_id, saved_at, account_id, paper_id),
                        )
            except _REFERENCE_REFUSALS:
                return outcome(
                    "refused", stored_digest(_stored(row)) if row else incoming,
                    reason="dependency-not-migrated",
                )
            return outcome(disposition, incoming)

        return self.transactions.run(OWNER, write)

    def parity(self, *, now: dt.datetime, account_ids: Iterable[UUID] | None = None) -> dict:
        ids = None if account_ids is None else sorted({UUID(str(v)) for v in account_ids})

        def read(conn):
            rows = conn.execute(
                "SELECT * FROM library.saved_paper WHERE %s::uuid[] IS NULL OR "
                "account_id=ANY(%s::uuid[]) ORDER BY account_id,paper_id LIMIT %s",
                (ids, ids, MAX_PARITY_RECORDS + 1),
            ).fetchall()
            if len(rows) > MAX_PARITY_RECORDS:
                raise ValueError("parity read exceeds its bound")
            return rows

        rows = self.transactions.run(OWNER, read)
        return parity("saved-paper", [stored_digest(_stored(row)) for row in rows], _time(now))
