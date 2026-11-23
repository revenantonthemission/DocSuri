"""Personalization's A4 settings writes and parity read (U8 plan Step 7; BR8.2, BR8.3).

The import operation (Step 31) keeps only the retained vocabulary and passes it here:
appearance, language and the defaults object. The repository writes them as
Personalization's own login and compares the stored fields with the incoming ones.
`timeZoneEffectiveAt` is stamped by the owner's trigger at write time, so it is never a
compared field. The parity digest covers every account's settings, or the named ones.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from uuid import UUID

from psycopg.types.json import Jsonb

from backend.import_parity import decide, outcome, parity, stored_digest

OWNER = "personalization"
APPEARANCES = ("light", "dark", "system")
STAMPED = "timeZoneEffectiveAt"
MAX_DEFAULTS = 64
MAX_PARITY_RECORDS = 100_000


def settings_fields(*, account_id: UUID, appearance: str, language: str, defaults: dict) -> dict:
    if appearance not in APPEARANCES:
        raise ValueError("appearance outside its vocabulary")
    if not isinstance(language, str) or not 2 <= len(language) <= 16:
        raise ValueError("language outside its bound")
    if not isinstance(defaults, dict) or len(defaults) > MAX_DEFAULTS or STAMPED in defaults:
        raise ValueError("settings defaults outside their bound")
    return {
        "account": str(account_id), "appearance": appearance, "language": language,
        "defaults": defaults,
    }


def _stored(row: dict) -> dict:
    defaults = {key: value for key, value in row["defaults"].items() if key != STAMPED}
    return settings_fields(
        account_id=row["account_id"], appearance=row["appearance"], language=row["language"],
        defaults=defaults,
    )


class SettingsImports:
    def __init__(self, transactions):
        self.transactions = transactions

    def import_settings(
        self, account_id: UUID, *, appearance: str, language: str, defaults: dict
    ) -> dict:
        fields = settings_fields(
            account_id=account_id, appearance=appearance, language=language, defaults=defaults
        )
        incoming = stored_digest(fields)

        def write(conn):
            row = conn.execute(
                "SELECT * FROM personalization.settings WHERE account_id=%s FOR UPDATE",
                (account_id,),
            ).fetchone()
            disposition = decide(stored_digest(_stored(row)) if row else None, incoming)
            if disposition == "imported":
                conn.execute(
                    "INSERT INTO personalization.settings(account_id,revision,appearance,"
                    "language,defaults) VALUES(%s,gen_random_uuid(),%s,%s,%s)",
                    (account_id, appearance, language, Jsonb(defaults)),
                )
            elif disposition == "updated":
                conn.execute(
                    "UPDATE personalization.settings SET revision=gen_random_uuid(),"
                    "appearance=%s,language=%s,defaults=%s WHERE account_id=%s",
                    (appearance, language, Jsonb(defaults), account_id),
                )
            return outcome(disposition, incoming)

        return self.transactions.run(OWNER, write)

    def parity(self, *, now: dt.datetime, account_ids: Iterable[UUID] | None = None) -> dict:
        ids = None if account_ids is None else sorted({UUID(str(v)) for v in account_ids})

        def read(conn):
            rows = conn.execute(
                "SELECT * FROM personalization.settings WHERE %s::uuid[] IS NULL OR "
                "account_id=ANY(%s::uuid[]) ORDER BY account_id LIMIT %s",
                (ids, ids, MAX_PARITY_RECORDS + 1),
            ).fetchall()
            if len(rows) > MAX_PARITY_RECORDS:
                raise ValueError("parity read exceeds its bound")
            return rows

        rows = self.transactions.run(OWNER, read)
        observed = now.astimezone(dt.UTC).isoformat(timespec="microseconds").replace(
            "+00:00", "Z")
        return parity("settings", [stored_digest(_stored(row)) for row in rows], observed)
