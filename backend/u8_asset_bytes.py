"""A paper's asset bytes through C13's byte route (U8 plan Step 127; D7, record 60, L2-9).

The rule (security-design § 4, 'Paper assets'): a paper asset's bytes are delivered from
the workspace's own origin, never through a presigned or third-party address, with the
caller's session and the version's eligibility checked again on every delivery, and with
`Cache-Control: no-store` and `X-Content-Type-Options: nosniff` (the browser boundary's
route class adds both to every answer).

The route is C13's `deliverPaperidAsset`, `GET /api/v2/papers/{paper_id}/versions/
{version_id}/assets/{asset_id}`, the template U1's journey assembly registers; this module
serves it from U8's own composition, so U1's module stays as built. Its dispositions come
in U1's order:

1. no current session: 401 `UNAUTHENTICATED`, before any identifier check or corpus read;
2. an identifier outside C13's `Id` form (1-128 characters, no control character), an
   unknown, withdrawn or ineligible version, or a version of another paper: 404
   `FORBIDDEN`, checked before the asset id is parsed;
3. an asset id that is no UUID, an asset of another version, an asset row without
   private bytes, or bytes that are missing or altered: 404 `NOT_FOUND`; missing or
   altered bytes also write one `corpus` `asset.unavailable` warning.

Where the bytes are: the corpus owner's private artifact store (`corpus-files`), each
asset's bytes named by the asset's own id (`<id hex>.blob`), whose custody, size and
SHA-256 the store checks against the asset row; no schema changes. Production holds no
asset bytes (figures are archive-only, functional-spec), so there every request is
refused. Only PNG, JPEG and WebP go out inline; every other type, SVG among them, goes
out as `application/octet-stream` with `Content-Disposition: attachment`.

The store is shared: `corpus-files` also holds PaperAssistance's private per-user
results. Corpus bytes are kept apart from them only because the corpus owner alone
writes `corpus.asset` rows and a row's hash and size must match the file (a residual
risk recorded with Step 144).

This module imports nothing from `docsuri_shared` and defines no `BaseModel`,
`TypedDict` or `RootModel` class, so the shared Python consumer inventory does not list it.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

from .artifacts import Artifact, ArtifactUnavailable
from .local_browser import BrowserDenied, boundary_route, optional_authority
from .log_events import log_event
from .transactions import guard

ROUTE = "/api/v2/papers/{paper_id}/versions/{version_id}/assets/{asset_id}"
# C13's `Id`: 1-128 characters, no control character.
ID_LENGTH = 128
# C13 derives the type from approved metadata and forces unsafe types to an attachment.
INLINE = frozenset({"image/png", "image/jpeg", "image/webp"})
ATTACHMENT_TYPE = "application/octet-stream"


class AssetUnavailable(RuntimeError):
    """No intact bytes for this asset of this version (404 `NOT_FOUND`)."""


@dataclass(frozen=True)
class Delivery:
    content: bytes
    media_type: str
    attachment: bool


def _require_identifier(value: str) -> None:
    """C13's `Id` form, before any SQL: a refusal answers as an unknown version does."""
    if not isinstance(value, str) or not 0 < len(value) <= ID_LENGTH:
        raise PermissionError("identifier outside the contract's Id form")
    if any(unicodedata.category(character) == "Cc" for character in value):
        raise PermissionError("identifier outside the contract's Id form")


class AssetBytes:
    """One asset's bytes, under the caller's session and the version's eligibility."""

    def __init__(self, transactions, files):
        self.transactions = transactions
        self.files = files

    def deliver(self, authority, paper_id: str, version_id: str, asset_id: str) -> Delivery:
        for value in (paper_id, version_id, asset_id):
            _require_identifier(value)
        handle, row = self.transactions.run(
            "corpus", lambda conn: self._row(conn, authority, paper_id, version_id, asset_id)
        )
        # Outside the transaction: no connection is held while the file is read.
        if row is None or row["storage"] != "private" or not row["byte_length"]:
            raise AssetUnavailable("no private bytes for this asset")
        try:
            content = self.files.read(
                Artifact(handle.hex + ".blob", row["content_hash"], row["byte_length"])
            )
        except ArtifactUnavailable:
            log_event("corpus", "asset.unavailable", "warning", objectId=handle,
                      reason="artifact-unavailable")
            raise AssetUnavailable("asset bytes missing or altered") from None
        media_type = row["media_type"]
        if media_type in INLINE:
            return Delivery(content, media_type, attachment=False)
        return Delivery(content, ATTACHMENT_TYPE, attachment=True)

    @staticmethod
    def _row(conn, authority, paper_id: str, version_id: str, asset_id: str):
        # The session and the version's eligibility, in the transaction that reads.
        guard(conn, authority, version=version_id)
        version = conn.execute(
            "SELECT paper_id FROM corpus.version WHERE id=%s", (version_id,)
        ).fetchone()
        if version is None or version["paper_id"] != paper_id:
            raise PermissionError("version of another paper")
        # Only now is the asset id parsed (U1's order).
        try:
            handle = UUID(asset_id)
        except ValueError:
            raise AssetUnavailable("asset id is no UUID") from None
        row = conn.execute(
            "SELECT id, media_type, content_hash, storage, byte_length FROM corpus.asset "
            "WHERE id=%s AND version_id=%s",
            (handle, version_id),
        ).fetchone()
        return handle, row


def asset_router(transactions, *, entry, assets: AssetBytes) -> APIRouter:
    """C13's byte route behind the shared browser boundary."""
    router = APIRouter(route_class=boundary_route(transactions.profile.origin))

    @router.get(ROUTE)
    async def deliver_paper_asset(
        request: Request, paper_id: str, version_id: str, asset_id: str
    ) -> Response:
        authority = await optional_authority(request, entry=entry)
        if authority is None:
            raise BrowserDenied(401, "UNAUTHENTICATED")
        try:
            delivery = await run_in_threadpool(
                assets.deliver, authority, paper_id, version_id, asset_id
            )
        except AssetUnavailable:
            raise BrowserDenied(404, "NOT_FOUND") from None
        headers = {"Content-Disposition": "attachment"} if delivery.attachment else {}
        return Response(delivery.content, media_type=delivery.media_type, headers=headers)

    return router
