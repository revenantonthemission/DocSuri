"""Canonical Discovery browser search binding over the eligible published corpus."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
from pathlib import Path
from uuid import uuid4

from backend.local_browser import (
    BrowserDenied,
    boundary_route,
    optional_authority,
    read_payload,
    require_post_headers,
)
from backend.modules.accounts.control_cursor import ControlCursor
from backend.modules.accounts.control_policy import SYNTHETIC_POLICY
from backend.modules.discovery.guarded_repository import GuardedDiscoveryRepository
from backend.modules.discovery.local_search import SearchPageBuilder, validate_query
from backend.modules.library.control_service import ControlLibraryService
from backend.modules.library.repository.guarded import GuardedLibraryRepository
from docsuri_ops.local_models import ModelUnavailable
from docsuri_shared.workspace import wire
from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool

CURSOR_KEY = "search-cursor.key"


def cursor_key(root: Path) -> bytes:
    """Owner-created signing key for snapshot-bound cursors; never leaves private root."""
    path = root / CURSOR_KEY
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(secrets.token_bytes(32))
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as stream:
        raw = stream.read(33)
    if len(raw) != 32:
        raise ValueError("cursor signing key is not the exact private allocation")
    return raw


def discovery_router(transactions, *, entry, anonymous, embed_query=None) -> APIRouter:
    origin = transactions.profile.origin
    repository = GuardedDiscoveryRepository(transactions)
    key = cursor_key(transactions.profile.root)
    library = (
        ControlLibraryService(transactions, SYNTHETIC_POLICY, ControlCursor(key))
        if transactions.profile.realm == "account-controls"
        else GuardedLibraryRepository(transactions)
    )
    builder = SearchPageBuilder(key)
    router = APIRouter(route_class=boundary_route(origin))

    @router.post("/api/v2/c05/search")
    async def search(request: Request):
        require_post_headers(request, origin)
        authority = await optional_authority(request, entry=entry)
        if authority is None:
            # Guest search requires the bound anonymous entry flow CSRF.
            anonymous.read(
                request.cookies.get("docsuri_entry", ""),
                csrf=request.headers.get("x-csrf-token", ""),
            )
        value = await read_payload(request, wire.SearchRequestHttp)
        query = validate_query(value["query"])
        limit = value["page"].get("limit") or 20
        if type(limit) is not int or not 1 <= limit <= 100:
            raise BrowserDenied(422, "INVALID_ARGUMENT")
        execution = uuid4()
        admission = None
        if authority is not None and transactions.profile.realm == "account-controls":
            digest = hashlib.sha256(
                json.dumps(query, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            admission = await run_in_threadpool(repository.admit, authority, execution, digest)
        snapshot = await run_in_threadpool(repository.snapshot, authority, query=query["query"])
        if value.get("snapshotRevision") is not None and value["snapshotRevision"] != str(
            snapshot["publication"]["revision"]
        ):
            raise BrowserDenied(410, "SNAPSHOT_EXPIRED")
        query_vector = None
        if query["modeId"] == "semantic":
            if embed_query is None:
                raise BrowserDenied(503, "DEPENDENCY_UNAVAILABLE")
            try:
                vector, *_ = await run_in_threadpool(embed_query, query["query"])
            except ModelUnavailable:
                raise BrowserDenied(503, "DEPENDENCY_UNAVAILABLE") from None
            query_vector = vector
        owner = str(authority.account_id) if authority else "guest"
        response = builder.build(
            snapshot=snapshot,
            query=query,
            execution=str(execution),
            owner=owner,
            limit=limit,
            cursor=value["page"].get("cursor"),
            query_vector=query_vector,
        )
        if authority is not None:
            try:
                relayed = await run_in_threadpool(
                    _relay_fact,
                    authority,
                    execution,
                    query,
                    response["hits"],
                    repository,
                    library,
                    admission,
                )
            except Exception:
                relayed = False
            if not relayed:
                response["limitations"] = [
                    *response["limitations"],
                    "검색 기록을 저장하지 못했습니다. 다음 검색에서 다시 시도합니다.",
                ]
                response = wire.SearchResponse.model_validate(response).model_dump(mode="json")
        return response

    return router


def _relay_fact(authority, execution, query, hits, repository, library, admission=None):
    """Durable search fact plus current Library boundary; a clear suppresses older facts."""
    if admission is None:
        library.ensure_boundary(authority)
        admission = library.history_boundary(authority)["generation"]
    digest = hashlib.sha256(
        json.dumps(query, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    fact = repository.record(
        authority,
        execution,
        query,
        digest,
        hits,
        admission,
    )
    accepted = library.accept_history(authority, fact)
    repository.acknowledge_history(authority, execution, delivered=accepted)
    return bool(accepted)
