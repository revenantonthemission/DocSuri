"""Explicit owner defaults with read-only cold start and revision-bound writes."""

from __future__ import annotations

import hashlib
import json
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from docsuri_shared.workspace import wire
from psycopg.types.json import Jsonb

from backend.transactions import Authority, OwnerTransactions, guard

POLICY = {"policyId": "synthetic-personal-settings", "revision": "1"}
VOCABULARY = "synthetic-paper-options-1"
SEARCH_DEFAULTS = {
    "modeId": "lexical",
    "orderId": "relevance",
    "filters": [],
    "vocabularyRevision": VOCABULARY,
}
ASSISTANCE_DEFAULTS = {
    "actionId": "summary",
    "languageId": "en",
    "presentationLevelId": "standard",
    "vocabularyRevision": VOCABULARY,
}


class GuardedSettingsService:
    def __init__(self, transactions: OwnerTransactions):
        self.transactions = transactions

    @staticmethod
    def _snapshot(account: UUID, row: dict | None) -> dict:
        stored = row["defaults"] if row else {}
        value = {
            "accountId": str(account),
            "settingsId": str(account),
            "revision": str(
                row["revision"] if row else uuid5(NAMESPACE_URL, str(account) + ":settings-empty:1")
            ),
            "searchDefaults": stored.get("searchDefaults", SEARCH_DEFAULTS),
            "assistanceDefaults": stored.get("assistanceDefaults", ASSISTANCE_DEFAULTS),
            "appearance": row["appearance"] if row else "system",
            "onboarding": "not_started",
            "interestIds": [],
            "policyRef": POLICY,
        }
        return wire.SettingsSnapshot.model_validate(value).model_dump(mode="json")

    def read(self, authority: Authority) -> dict:
        def read(conn):
            # Manual defaults are usable without behavioral-personalization consent.
            guard(conn, authority)
            row = conn.execute(
                "SELECT * FROM personalization.settings WHERE account_id=%s",
                (authority.account_id,),
            ).fetchone()
            return self._snapshot(authority.account_id, row)

        return self.transactions.run("personalization", read)

    def update(self, authority: Authority, operation: UUID, expected: str, changes: dict) -> dict:
        allowed = {"searchDefaults", "assistanceDefaults", "appearance"}
        if not changes or set(changes) - allowed:
            raise ValueError("unsupported settings fields")
        expected_id = UUID(expected)
        value = wire.SettingsUpdateInputHttp.model_validate(
            dict(changes, policyRef=POLICY, expectedRevision=str(expected_id))
        ).model_dump(mode="json", exclude_unset=True)
        search = value.get("searchDefaults")
        assistance = value.get("assistanceDefaults")
        if search and (
            search["vocabularyRevision"] != VOCABULARY
            or search["modeId"] not in ("lexical", "semantic")
            or search["orderId"] not in ("relevance", "newest")
            or search["filters"]
        ):
            raise ValueError("unsupported local search defaults")
        if assistance and (
            assistance["vocabularyRevision"] != VOCABULARY
            or assistance["actionId"] not in ("summary", "translate")
            or assistance["languageId"] not in ("en", "ko")
            or assistance["presentationLevelId"] != "standard"
        ):
            raise ValueError("unsupported local assistance defaults")
        fingerprint = hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()

        def write(conn):
            guard(conn, authority)
            prior = conn.execute(
                "SELECT * FROM personalization.receipt WHERE account_id=%s "
                "AND kind='settings' AND key=%s",
                (authority.account_id, operation),
            ).fetchone()
            if prior:
                if prior["intent_hash"] != fingerprint:
                    raise ValueError("settings operation conflict")
                return prior["outcome"]
            row = conn.execute(
                "SELECT * FROM personalization.settings WHERE account_id=%s FOR UPDATE",
                (authority.account_id,),
            ).fetchone()
            previous = self._snapshot(authority.account_id, row)
            if previous["revision"] != str(expected_id):
                raise ValueError("stale settings revision")
            merged = dict(previous, **changes)
            defaults = {key: merged[key] for key in ("searchDefaults", "assistanceDefaults")}
            row = conn.execute(
                "INSERT INTO personalization.settings(account_id,revision,"
                "appearance,defaults) VALUES(%s,%s,%s,%s) ON CONFLICT(account_id) DO UPDATE SET "
                "revision=excluded.revision,appearance=excluded.appearance,"
                "defaults=excluded.defaults "
                "RETURNING *",
                (authority.account_id, uuid4(), merged["appearance"], Jsonb(defaults)),
            ).fetchone()
            outcome = self._snapshot(authority.account_id, row)
            conn.execute(
                "INSERT INTO personalization.receipt(account_id,kind,key,intent_hash,outcome) "
                "VALUES(%s,'settings',%s,%s,%s)",
                (authority.account_id, operation, fingerprint, Jsonb(outcome)),
            )
            return outcome

        return self.transactions.run("personalization", write)
