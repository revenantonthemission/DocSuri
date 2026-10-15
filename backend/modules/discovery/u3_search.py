"""U3 Discovery search: versioned vocabulary, snapshot-bound windows and
disclosed lexical/semantic degradation.

A semantic request with no installed semantic capability executes the disclosed
lexical fallback (`outcome=degraded`, `effectiveModeId=lexical`); a configured
capability that fails returns an actionable unavailability. Retrieval failure is
never presented as a successful empty result. Completed qualifying authenticated
searches produce durable owner-scoped facts handed to Library (BR4.1-4.4).
"""

from __future__ import annotations

import hashlib
import json
from uuid import UUID, uuid4

from backend.modules.discovery.local_search import (
    SearchPageBuilder,
    validate_query,
)
from backend.transactions import Authority
from backend.u3_policy import (
    PROJECTION_COMPATIBILITY,
    QUERY_VOCABULARY,
    SEARCH_POLICY,
    page_size,
)
from docsuri_shared.workspace import wire


class SnapshotExpired(ValueError):
    """The requested window no longer matches the authoritative snapshot."""


class DependencyUnavailable(RuntimeError):
    """A configured retrieval dependency failed; not an empty result."""


DEGRADATION_NOTE = "의미 검색을 사용할 수 없어 어휘 검색으로 대체했습니다."


def _query_digest(query: dict) -> str:
    return hashlib.sha256(
        json.dumps(query, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class U3Search:
    def __init__(self, transactions, repository, library, *, cursor_key, semantic=None):
        self.transactions = transactions
        self.repository = repository
        self.library = library
        self.semantic = semantic
        self.builder = SearchPageBuilder(
            cursor_key,
            vocabulary=QUERY_VOCABULARY,
            policy=SEARCH_POLICY,
            compatibility=PROJECTION_COMPATIBILITY,
        )

    def search(self, authority: Authority | None, request: dict) -> dict:
        query = validate_query(
            request["query"], vocabulary=QUERY_VOCABULARY, policy=SEARCH_POLICY
        )
        limit = page_size((request.get("page") or {}).get("limit"))
        degradation = "none"
        effective_mode = None
        query_vector = None
        if query["modeId"] == "semantic":
            if self.semantic is None:
                # Disclosed fallback: lexical retrieval, explicitly degraded.
                degradation = "semantic-unavailable"
                effective_mode = "lexical"
            else:
                try:
                    query_vector = self.semantic(query["query"])
                except Exception as error:
                    raise DependencyUnavailable("semantic retrieval unavailable") from error
        execution = uuid4()
        admission = None
        if authority is not None:
            admission = self.repository.admit(
                authority, execution, _query_digest(query)
            )
        snapshot = self.repository.snapshot(authority, query=query["query"])
        expected = request.get("snapshotRevision")
        if expected is not None and expected != str(snapshot["publication"]["revision"]):
            raise SnapshotExpired("search snapshot changed")
        owner = str(authority.account_id) if authority is not None else "guest"
        snapshot_revision = snapshot["publication"]["revision"]
        response = self.builder.build(
            snapshot=snapshot,
            query=query,
            execution=str(execution),
            owner=owner,
            limit=limit,
            cursor=(request.get("page") or {}).get("cursor"),
            query_vector=query_vector,
            effective_mode=effective_mode,
        )
        if degradation != "none":
            response["outcome"] = "degraded"
            response["limitations"] = [*response["limitations"], DEGRADATION_NOTE]
        if authority is not None:
            relayed = self._relay_fact(
                authority,
                execution,
                query,
                response["hits"],
                admission,
                snapshot_revision=snapshot_revision,
                degradation=degradation,
            )
            if not relayed:
                response["limitations"] = [
                    *response["limitations"],
                    "검색 기록을 저장하지 못했습니다. 다음 검색에서 다시 시도합니다.",
                ]
        response = wire.SearchResponse.model_validate(response).model_dump(mode="json")
        return response

    def _relay_fact(
        self, authority, execution, query, hits, admission, *, snapshot_revision, degradation
    ) -> bool:
        """Durable fact plus current Library boundary; replay executes no search."""
        if admission is None:
            # The producer-assigned admission sequence is authoritative; the
            # Library boundary never supplies or trusts a caller cutoff.
            admission = self.repository.checkpoint(authority)["admissionSequence"]
        fact = self.repository.record(
            authority,
            execution,
            query,
            _query_digest(query),
            hits,
            admission,
            snapshot_revision=snapshot_revision,
            degradation=degradation,
        )
        accepted = self.library.accept_history(authority, fact)
        self.repository.acknowledge_history(authority, execution, delivered=accepted)
        return bool(accepted)

    def checkpoint(self, authority: Authority) -> dict:
        return self.repository.checkpoint(authority)

    def rerun(self, authority: Authority | None, execution: UUID) -> dict:
        """Rerun re-executes the recorded query context through the same operation."""
        row = self.repository.execution(authority, UUID(str(execution)))
        return self.search(
            authority,
            {"query": row["query"], "page": {"limit": 20}, "snapshotRevision": None},
        )
