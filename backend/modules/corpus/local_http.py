"""Canonical CorpusContent browser bindings for the explicit local journey assembly."""

from __future__ import annotations

from backend.local_browser import (
    BrowserDenied,
    boundary_route,
    optional_authority,
    post_context,
    read_payload,
)
from backend.modules.corpus.repository import CorpusRepository, content_revision
from docsuri_shared.workspace import wire
from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool

POLICY = {"policyId": "local-research", "revision": "1"}
SECTION_ALLOCATION = 512
TEXT_ALLOCATION = 262144


def _block_text(block: dict) -> str:
    kind = block.get("type")
    if kind in ("paragraph", "code"):
        return str(block.get("text", block.get("code", "")))
    if kind == "formula":
        # Literal LaTeX stays authoritative; no Unicode re-encoding.
        return str(block.get("latex", ""))
    if kind in ("figure", "table"):
        label, caption = block.get("anchorLabel"), block.get("caption")
        if kind == "table" and block.get("rows"):
            rows = [
                " | ".join(str(cell.get("text", "")) for cell in row.get("cells", []))
                for row in block["rows"]
            ]
            head = [str(v) for v in (label, caption) if v]
            return "\n".join(part for part in (*head, *rows) if part)
        return " ".join(str(value) for value in (label, caption) if value)
    if kind == "list":
        return "\n".join(str(item.get("text", "")) for item in block.get("items", []))
    return str(block.get("text", ""))


def _flatten(sections: list[dict], ancestors: tuple[str, ...] = ()) -> tuple[list[dict], int, int]:
    items: list[dict] = []
    figures = 0
    total = 0
    for section in sections:
        heading = " / ".join([*ancestors, section["title"]])
        parts, anchor = [], None
        for block in section.get("blocks", []):
            if block.get("type") == "figure":
                figures += 1
            text = _block_text(block)
            if text.strip():
                parts.append(text)
                anchor = anchor or block["id"]
        if parts:
            body = "\n\n".join(parts)
            total += len(body.encode())
            if total > TEXT_ALLOCATION:
                raise ValueError("parsed source exceeds reader allocation")
            items.append(
                {
                    "sectionId": section["id"],
                    "heading": heading,
                    "text": body,
                    "anchor": anchor or section["id"],
                }
            )
            if len(items) > SECTION_ALLOCATION:
                raise ValueError("parsed source exceeds reader section allocation")
        children, child_figures, total = _flatten(
            section.get("sections", []) or [], (*ancestors, section["title"])
        )
        figures += child_figures
        items.extend(children)
    return items, figures, total


def paper_reference(row: dict) -> dict:
    return {
        "paperId": row["paper_id"],
        "versionId": row["id"],
        "eligibilityRevision": str(row["eligibility_revision"]),
    }


def corpus_router(transactions, *, entry, activity=None) -> APIRouter:
    origin = transactions.profile.origin
    repository = CorpusRepository(transactions, files=None)
    router = APIRouter(route_class=boundary_route(origin))

    async def authenticated(request: Request):
        operation, _, authority = await post_context(
            request, origin=origin, entry=entry, anonymous=None
        )
        if authority is None:
            raise BrowserDenied(401, "UNAUTHENTICATED")
        return operation, authority

    @router.post("/api/v2/c04/resolve-paper")
    async def resolve(request: Request):
        _, _ = await authenticated(request)
        value = await read_payload(request, wire.CorpusResolveHttp)
        row = await run_in_threadpool(
            repository.identify, value["identifier"], value.get("versionLabel")
        )
        if row is None:
            raise BrowserDenied(404, "NOT_FOUND")
        eligible = bool(row["eligible"]) and not row["withdrawn"]
        return wire.CorpusIdentity.model_validate(
            {
                "paper": paper_reference(row),
                "requestedIdentifier": value["identifier"],
                "canonicalDisposition": "same" if eligible else "withdrawn",
                "metadataRevision": str(row["paper_revision"]),
                "title": row["title"],
                "sourceUrls": [row["source_url"]],
                "policy": POLICY,
            }
        ).model_dump(mode="json", exclude_none=True)

    @router.post("/api/v2/c04/read-content")
    async def read_content(request: Request):
        operation, authority = await authenticated(request)
        value = await read_payload(request, wire.CorpusReadHttp)
        # The declared caller purpose must be one the local policy admits; the
        # storage purpose stays Corpus-owned 'local-research'.
        if value["purpose"] not in ("read", "assistance"):
            raise BrowserDenied(503, "POLICY_UNRESOLVED")
        version = value["paper"]["versionId"]
        observed = (
            await run_in_threadpool(
                activity.capture, authority, operation, value["paper"], "paper-view"
            )
            if activity
            else None
        )
        view = await run_in_threadpool(repository.reader_view, version)
        rows = view["row"]
        if value["paper"]["paperId"] != rows["paper_id"]:
            raise BrowserDenied(404, "NOT_FOUND")
        if view["disposition"] != "ready":
            return wire.CorpusContentRead.model_validate(
                {
                    "availability": view["disposition"],
                    "paper": paper_reference(rows),
                    "reasonKey": "source." + view["disposition"],
                    "retryable": False,
                }
            ).model_dump(mode="json", exclude_none=True)
        sections, figures, _ = _flatten(rows["content"]["document"]["sections"])
        if activity and value["purpose"] == "read":
            await run_in_threadpool(activity.deliver, authority, observed)
        limitations = []
        if figures:
            limitations.append("그림 캡션만 제공되며 원본 이미지는 로컬 환경에 보관되지 않습니다.")
        return wire.CorpusContentRead.model_validate(
            {
                "availability": "ready",
                "content": {
                    "paper": paper_reference(rows),
                    "contentRevision": content_revision(rows),
                    "contentHash": rows["source_hash"],
                    "sections": sections,
                    "assets": [],
                    "sourceUrls": [rows["source_url"]],
                    "coverage": "complete",
                    "limitations": limitations,
                    "policy": POLICY,
                },
            }
        ).model_dump(mode="json", exclude_none=True)

    @router.get("/api/v2/papers/{paper_id}/versions/{version_id}/assets/{asset_id}")
    async def read_asset(request: Request, paper_id: str, version_id: str, asset_id: str):
        authority = await optional_authority(request, entry=entry)
        if authority is None:
            raise BrowserDenied(401, "UNAUTHENTICATED")
        view = await run_in_threadpool(repository.reader_view, version_id)
        rows = view["row"]
        if view["disposition"] != "ready" or rows["paper_id"] != paper_id:
            raise BrowserDenied(404, "FORBIDDEN")
        known = {
            block["assetRef"]["assetId"]
            for section in rows["content"]["document"]["sections"]
            for block in _walk_blocks(section)
            if block.get("type") == "figure"
        }
        if asset_id not in known:
            raise BrowserDenied(404, "NOT_FOUND")
        # No figure bytes are retained in this owned synthetic fixture realm;
        # the reader shows the caption and reports the bounded unavailability.
        raise BrowserDenied(404, "NOT_FOUND")

    return router


def _walk_blocks(section: dict):
    yield from section.get("blocks", [])
    for child in section.get("sections", []) or []:
        yield from _walk_blocks(child)
