"""Bounded ranking and owner/query/snapshot-bound pagination for local search.

The caller supplies a currently authorized Corpus snapshot. This component
does not grant access, mutate the corpus or create search-history facts.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from datetime import UTC, datetime

from backend.modules.discovery.local_embedding import cosine
from docsuri_ops.local_models import ModelUnavailable
from docsuri_shared.workspace import wire

VOCABULARY = "synthetic-paper-options-1"
POLICY = {"policyId": "synthetic-paper-search", "revision": "1"}


def validate_query(value: dict) -> dict:
    query = wire.LibraryQueryContext.model_validate(value).model_dump(mode="json")
    text = query["query"].strip()
    if not text or len(text.encode()) > 2048 or any(ord(c) < 32 for c in text):
        raise ValueError("query outside finite text policy")
    if (
        query["modeId"] not in ("lexical", "semantic")
        or query["orderId"] not in ("relevance", "newest")
        or query["vocabularyRevision"] != VOCABULARY
        or query["policyRef"] != POLICY
    ):
        raise ValueError("unknown search vocabulary or policy")
    filters = query["filters"]
    if len(filters) > 2 or len({f["filterId"] for f in filters}) != len(filters):
        raise ValueError("duplicate or excessive filters")
    for entry in filters:
        values = entry["values"]
        if entry["filterId"] == "author" and entry["operatorId"] == "contains":
            if len(values) != 1 or not isinstance(values[0], str) or not 1 <= len(values[0]) <= 100:
                raise ValueError("author filter requires one bounded name")
        elif entry["filterId"] == "year" and entry["operatorId"] == "between":
            if (
                len(values) != 2
                or any(type(v) is not int for v in values)
                or not 1800 <= values[0] <= values[1] <= 2100
            ):
                raise ValueError("year filter requires a bounded ordered interval")
        else:
            raise ValueError("unknown filter vocabulary")
    return query


class SearchPageBuilder:
    def __init__(self, cursor_key: bytes, *, clock=time.time):
        if len(cursor_key) < 32:
            raise ValueError("cursor signing key must contain at least 32 bytes")
        self.key = cursor_key
        self.clock = clock

    def build(
        self,
        *,
        snapshot: dict,
        query: dict,
        execution: str,
        owner: str,
        limit: int = 20,
        cursor: str | None = None,
        query_vector: list[float] | None = None,
    ) -> dict:
        query = validate_query(query)
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("page size outside finite allocation")
        rows = snapshot["candidates"]
        if len(rows) > 256:
            raise ValueError("projection exceeds finite allocation")
        publication = snapshot["publication"]
        revision = str(publication["revision"])
        context = {
            "owner": owner,
            "query": hashlib.sha256(json.dumps(query, sort_keys=True).encode()).hexdigest(),
            "snapshot": revision,
            "limit": limit,
            "contract": "local-search-1",
        }
        offset = self._decode(cursor, context) if cursor else 0
        best = {}
        for row in rows:
            if not self._matches(row, query["filters"]):
                continue
            if query["modeId"] == "semantic":
                if query_vector is None or row.get("embedding") is None:
                    raise ModelUnavailable("semantic projection is unavailable")
                if row.get("vector_policy") != "bge-m3-1024-pinned-1":
                    raise ModelUnavailable("semantic projection compatibility changed")
                score = cosine(query_vector, row["embedding"])
            else:
                # This score comes from the actual parameterized PostgreSQL text query.
                if "lexical_score" not in row:
                    raise ValueError("lexical snapshot must carry current query scores")
                score = float(row["lexical_score"])
            if score <= 0:
                continue
            version = row["version_id"]
            candidate = (score, -row["ordinal"], row)
            if version not in best or candidate[:2] > best[version][:2]:
                best[version] = candidate
        ranked = sorted(best.values(), key=lambda item: (-item[0], item[2]["version_id"]))
        if query["orderId"] == "newest":
            ranked.sort(key=lambda item: str(item[2].get("published_on") or ""), reverse=True)
        if offset > len(ranked):
            raise ValueError("cursor offset is outside snapshot")
        selected = ranked[offset : offset + limit]
        next_offset = offset + len(selected)
        next_cursor = self._encode(context, next_offset) if next_offset < len(ranked) else None
        hits = [self._hit(item[2], query["modeId"]) for item in selected]
        response = {
            "executionId": execution,
            "query": query,
            "hits": hits,
            "page": {"nextCursor": next_cursor, "snapshotRevision": revision},
            "publication": {
                "generationId": str(publication["generation_id"]),
                "publicationRevision": revision,
                "manifestHash": publication["manifest_hash"],
                "compatibilityRevision": "local-search-1",
                "eligibilityRevision": revision,
                "publishedAt": publication["published_at"].isoformat(),
                "complete": True,
            },
            "outcome": "complete",
            "effectiveModeId": query["modeId"],
            "limitations": [],
        }
        return wire.SearchResponse.model_validate(response).model_dump(mode="json")

    @staticmethod
    def _matches(row: dict, filters: list[dict]) -> bool:
        for entry in filters:
            if entry["filterId"] == "author":
                if not any(entry["values"][0].casefold() in a.casefold() for a in row["authors"]):
                    return False
            else:
                date = row.get("published_on")
                if date is None or not entry["values"][0] <= date.year <= entry["values"][1]:
                    return False
        return True

    @staticmethod
    def _hit(row: dict, mode: str) -> dict:
        date = row.get("published_on")
        return {
            "paper": {
                "paperId": row["paper_id"],
                "versionId": row["version_id"],
                "eligibilityRevision": str(row["eligibility_revision"]),
            },
            "title": row["title"],
            "authors": row["authors"],
            "publishedAt": datetime.combine(date, datetime.min.time(), UTC).isoformat()
            if date
            else None,
            "snippet": row["text_content"][:400],
            "sourceUrl": row["source_url"],
            "availability": "readable",
            "matchExplanation": "검색어 일치" if mode == "lexical" else "의미 유사도",
        }

    def _encode(self, context: dict, offset: int) -> str:
        raw = json.dumps(
            dict(context, offset=offset, expires=self.clock() + 300),
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        signature = hmac.digest(self.key, raw, "sha256")
        return base64.urlsafe_b64encode(raw + signature).decode()

    def _decode(self, cursor: str, context: dict) -> int:
        if not isinstance(cursor, str) or not 1 <= len(cursor) <= 2048:
            raise ValueError("cursor outside finite policy")
        try:
            data = base64.b64decode(cursor, altchars=b"-_", validate=True)
            raw, signature = data[:-32], data[-32:]
            if not hmac.compare_digest(signature, hmac.digest(self.key, raw, "sha256")):
                raise ValueError("cursor signature differs")
            value = json.loads(raw)
            if set(value) != set(context) | {"offset", "expires"}:
                raise ValueError("cursor fields differ")
            if any(value[k] != v for k, v in context.items()) or value["expires"] <= self.clock():
                raise ValueError("cursor context changed or expired")
            if type(value["offset"]) is not int or not 0 <= value["offset"] <= 256:
                raise ValueError("cursor offset outside allocation")
            return value["offset"]
        except (ValueError, TypeError, KeyError) as exc:
            raise ValueError("invalid or stale search cursor") from exc
