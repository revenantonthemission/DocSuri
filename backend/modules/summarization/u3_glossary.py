"""U3 PaperAssistance glossary: normalization, virtual-empty snapshot and CAS.

An absent glossary returns a side-effect-free virtual empty snapshot with a
non-null policy-bound initial revision; a replace compare-and-swaps on the
visible revision and a failed or conflicting write preserves the previous
committed glossary (BR8.1-8.3).
"""

from __future__ import annotations

import unicodedata
from uuid import uuid4

from backend.transactions import Authority, guard
from backend.u3_policy import (
    GLOSSARY_POLICY,
    MAX_GLOSSARY_TERMS,
    MAX_TERM_BYTES,
    MAX_TERM_LENGTH,
    require_policy,
)


class GlossaryConflict(ValueError):
    """The expected revision no longer matches the committed glossary."""


class GlossaryInvalid(ValueError):
    """Terms violate the normalization policy; committed values are preserved."""


LANGUAGES = ("en", "ko")


def virtual_revision(account_id) -> str:
    """The policy-bound initial revision token for an absent glossary."""
    return f"empty:{account_id}:u3-owner-glossary-v1"


def normalize_terms(terms: list[dict]) -> list[dict]:
    """Validate and normalize one bounded term list; reject ambiguity."""
    if not isinstance(terms, list) or len(terms) > MAX_GLOSSARY_TERMS:
        raise GlossaryInvalid("glossary term allocation exceeded")
    normalized = []
    seen_sources = set()
    seen_preferred = set()
    for term in terms:
        if not isinstance(term, dict):
            raise GlossaryInvalid("malformed glossary term")
        source, preferred, language = (
            term.get("source"),
            term.get("preferred"),
            term.get("languageId"),
        )
        if language not in LANGUAGES:
            raise GlossaryInvalid("unsupported glossary language")
        source = _normalize_value(source, "source")
        preferred = _normalize_value(preferred, "preferred")
        if (
            source.casefold() in seen_sources
            or preferred.casefold() in seen_preferred
            or source.casefold() == preferred.casefold()
        ):
            raise GlossaryInvalid("duplicate or conflicting glossary term")
        seen_sources.add(source.casefold())
        seen_preferred.add(preferred.casefold())
        normalized.append(
            {
                "termId": _term_id(term.get("termId"), source, preferred, language),
                "source": source,
                "preferred": preferred,
                "languageId": language,
            }
        )
    return normalized


def _normalize_value(value, field: str) -> str:
    if not isinstance(value, str):
        raise GlossaryInvalid(f"glossary {field} must be text")
    normalized = unicodedata.normalize("NFC", value.strip())
    if not normalized:
        raise GlossaryInvalid(f"glossary {field} is empty after normalization")
    if len(normalized) > MAX_TERM_LENGTH or len(normalized.encode()) > MAX_TERM_BYTES:
        raise GlossaryInvalid(f"glossary {field} exceeds the finite term allocation")
    if any(ord(character) < 32 for character in normalized):
        raise GlossaryInvalid("glossary control character refused")
    return normalized


def _term_id(value, source: str, preferred: str, language: str) -> str:
    if value is None:
        import hashlib

        return "term-" + hashlib.sha256(
            f"{language}:{source}:{preferred}".encode()
        ).hexdigest()[:24]
    if not isinstance(value, str) or not 1 <= len(value) <= 64:
        raise GlossaryInvalid("invalid glossary term identity")
    return value


class GlossaryService:
    def __init__(self, transactions):
        self.transactions = transactions

    def read(self, authority: Authority) -> dict:
        def read(conn):
            guard(conn, authority)
            row = conn.execute(
                "SELECT revision,snapshot FROM assistance.glossary WHERE account_id=%s",
                (authority.account_id,),
            ).fetchone()
            if row is None:
                # Side-effect-free virtual empty snapshot; nothing is written.
                return {
                    "ownerId": str(authority.account_id),
                    "revision": virtual_revision(authority.account_id),
                    "normalizationPolicy": GLOSSARY_POLICY,
                    "terms": [],
                }
            return {
                "ownerId": str(authority.account_id),
                "revision": row["revision"],
                "normalizationPolicy": GLOSSARY_POLICY,
                "terms": row["snapshot"],
            }

        return self.transactions.run("assistance", read)

    def replace(self, authority: Authority, request: dict) -> dict:
        require_policy(
            request.get("normalizationPolicy"), GLOSSARY_POLICY, name="normalization policy"
        )
        expected = request.get("expectedRevision")
        if not isinstance(expected, str) or not 1 <= len(expected) <= 160:
            raise GlossaryInvalid("expected revision outside finite policy")
        normalized = normalize_terms(request.get("terms"))

        def write(conn):
            guard(conn, authority)
            row = conn.execute(
                "SELECT * FROM assistance.glossary WHERE account_id=%s FOR UPDATE",
                (authority.account_id,),
            ).fetchone()
            revision = str(uuid4())
            if row is None:
                if expected != virtual_revision(authority.account_id):
                    raise GlossaryConflict("glossary revision changed")
                conn.execute(
                    "INSERT INTO assistance.glossary(account_id,revision,snapshot,"
                    "normalization_policy) VALUES(%s,%s,%s,%s)",
                    (
                        authority.account_id,
                        revision,
                        _jsonb(normalized),
                        _jsonb(GLOSSARY_POLICY),
                    ),
                )
            else:
                if row["revision"] != expected:
                    raise GlossaryConflict("glossary revision changed")
                conn.execute(
                    "UPDATE assistance.glossary SET revision=%s,snapshot=%s WHERE "
                    "account_id=%s AND revision=%s",
                    (revision, _jsonb(normalized), authority.account_id, expected),
                )
            return {
                "ownerId": str(authority.account_id),
                "revision": revision,
                "normalizationPolicy": GLOSSARY_POLICY,
                "terms": normalized,
            }

        return self.transactions.run("assistance", write)


def _jsonb(value):
    from psycopg.types.json import Jsonb

    return Jsonb(value)
