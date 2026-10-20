"""The Notion adapter: the only code that asks Notion anything (logical-components §2).

Six operations, each one `NotionSession` operation with its own clients and budget:

- `identify`: the token's bot user (workspace name, workspace id, integration id);
- `list_destinations`: shared pages, paged by hand, plus a direct read of
  `lastDestinationId` inside the same gated operation (BR1.5, S2);
- `read_destination`: one page request and its first children request (BR1.5);
- `create_page`: the only write, after the bound-content check (D12, BR4.1, BR4.2);
- `read_back`: the three checks of a "saved but busy" answer (BR4.2, §8.3);
- `scan`: the reconciliation scan for the effect's marker (BR4.4, §9.4).

Every read follows the read-retry rule (NFR4.6, §9.3). A stored-token 401 revokes the
connection by compare-and-set on the revision the operation opened (D16, BR1.4); a
custody fault makes it unavailable and a later successful open makes it connected again,
both at an unchanged revision (BR1.6). Results are frozen values holding fixed
categories, validated identifiers and bounded text; never an exception or a token.

The workspace identifier of `ExportDestination.workspaceId` is the bot user's
`bot.workspace_id` ("Retrieve your token's bot user", Notion API reference, Notion-Version
2026-03-11, checked 2026-10-20). The integration identity, which is also the writer
identity of every page this connection creates, is the bot user's `id`.
"""

import asyncio
import datetime as dt
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID

from docsuri_shared.workspace import execution

from backend.u6_policy import ExportPolicy

from .classification import (
    COULD_NOT_CHECK,
    CREATED,
    NOT_CONNECTED,
    NOT_READABLE,
    OK,
    PROTECTION_UNAVAILABLE,
    RATE_LIMITED,
    REFUSAL_CONTENT_REJECTED,
    REFUSAL_TOKEN_INVALID,
    REFUSED,
    RETRYABLE,
    TOKEN_INVALID,
    UNCERTAIN,
    ReducedError,
    Verdict,
    classify_read,
    classify_write,
    normalise_id,
)
from .lane_store import CheckResult, WriteOutcome
from .notion_session import (
    CandidateToken,
    NotionSession,
    OperationContext,
    SessionResult,
    StoredConnection,
)
from .rendering import content_hash
from .store_support import canonical_digest

ADAPTER_REVISION = "notion-client-3.1.0+notion-2026-03-11"
PAGE_SIZE = 100
# Bounds of one listing and one scan; reaching one makes the result incomplete.
MAX_SEARCH_PAGES = 10
MAX_SCAN_BLOCKS = 5000
MAX_CHILD_PAGES = 20
MAX_OTHER_MARKED = 10
TEXT_LIMIT = 2000
SKIPPED_CONTAINERS = frozenset({"child_page", "child_database"})
_WORKSPACE_ID = re.compile(r"[0-9A-Za-z][0-9A-Za-z-]{0,127}")
_NOTION_URL = re.compile(r"https://(?:www\.)?notion\.(?:so|site)/[^\s]{1,2000}")

LISTING_UNAVAILABLE = "listing-unavailable"
LISTING_INCOMPLETE = "listing-incomplete"
MARKER_FOUND = "marker-found"
NOT_FOUND = "not-found"


def _utc_now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


# -- ports and results -----------------------------------------------------------------


class AdapterStore(Protocol):
    def revoke_connection(self, account_id, connection_id, opened_revision, *, now): ...

    def set_availability(self, account_id, connection_id, opened_revision, *, available): ...


@dataclass(frozen=True)
class BoundContent:
    """The frozen tree of the effect's preview revision, as the content port returns it."""

    body: Mapping
    content_hash: str
    marker: str
    destination_id: str


class ContentPort(Protocol):
    def bound_content(self, effect_id: UUID) -> BoundContent | None: ...


class StoreContentPort:
    """The content port over the store's effect binding (the frozen tree, D12)."""

    def __init__(self, repository):
        self._repository = repository

    def bound_content(self, effect_id: UUID) -> BoundContent | None:
        binding = self._repository.effect_binding(effect_id)
        if binding is None or binding["revision"].get("rendered_blocks") is None:
            return None
        return BoundContent(
            body=binding["revision"]["rendered_blocks"],
            content_hash=binding["revision"]["rendered_content_hash"],
            marker=binding["effect"]["marker"],
            destination_id=binding["effect"]["destination_id"],
        )


@dataclass(frozen=True)
class Identification:
    category: str
    workspace_name: str | None = None
    workspace_id: str | None = None
    integration_id: str | None = None
    revoked: bool = False


@dataclass(frozen=True)
class ListedDestination:
    destination_id: str
    title: str | None
    context: str | None
    readable: bool | None
    creation_capability: str
    writable: bool


@dataclass(frozen=True)
class Listing:
    category: str
    destinations: tuple[ListedDestination, ...] = ()
    complete: bool = False
    last_destination_id: str | None = None
    last_destination_readable: bool | None = None
    revoked: bool = False


@dataclass(frozen=True)
class DestinationRead:
    category: str
    readable: bool | None = None
    title: str | None = None
    context: str | None = None
    revoked: bool = False


@dataclass(frozen=True)
class WriteRequest:
    """The A6 write request plus the writer identity the attempt records."""

    effect_id: UUID
    approval_id: UUID
    connection_id: UUID
    destination_id: str
    artifact: Mapping
    preview_hash: str
    writer_identity: str

    def provider_request(self, content: BoundContent) -> execution.ProviderNotionRequest:
        return execution.ProviderNotionRequest.model_validate(
            {
                "effectId": str(self.effect_id),
                "approvalId": str(self.approval_id),
                "connectionId": str(self.connection_id),
                "destinationId": self.destination_id,
                "artifact": dict(self.artifact),
                "previewHash": self.preview_hash,
                "contentHash": content.content_hash,
                "marker": content.marker,
            }
        )


@dataclass(frozen=True)
class WriteResult:
    """One classified write. `outcome` is None when nothing could be sent because the
    connection held no openable token (`category` names why); `sent` is False whenever
    no create request left."""

    category: str
    effect_id: UUID
    outcome: WriteOutcome | None
    sent: bool
    retry_after_seconds: int | None = None
    refusal: str | None = None
    revoked: bool = False

    def provider_result(self) -> execution.ProviderNotionResult | None:
        """The A6 write result, or None for rate-limited (a C12 retry_later outcome)."""
        if self.outcome is None or self.category == RATE_LIMITED:
            return None
        disposition = {CREATED: "committed", REFUSED: "rejected"}.get(self.category, "unknown")
        return execution.ProviderNotionResult(
            effectId=str(self.effect_id),
            remotePageId=self.outcome.remote_reference,
            disposition=disposition,
            providerRequestId=self.outcome.provider_request_id,
            refusalClass=self.refusal,
        )

    def provider_outcome(self) -> execution.ProviderOutcome | None:
        """The C12 provider outcome: rate-limited is `retry_later` with its existing
        `retryAfterSeconds`; no new field is used."""
        if self.outcome is None:
            return None
        outcome = {
            CREATED: "succeeded",
            REFUSED: "rejected",
            RATE_LIMITED: "retry_later",
        }.get(self.category, "unknown")
        return execution.ProviderOutcome(
            requestId=str(self.effect_id),
            adapterRevision=ADAPTER_REVISION,
            outcome=outcome,
            responseSchemaId="ProviderNotionResult",
            validatedPayload=self.provider_result(),
            remoteReference=self.outcome.remote_reference,
            retryAfterSeconds=self.retry_after_seconds if self.category == RATE_LIMITED else None,
            evidenceRefs=[],
        )


@dataclass(frozen=True)
class ReadBack:
    category: str
    passed: bool = False
    remote_url: str | None = None
    revoked: bool = False


@dataclass(frozen=True)
class ScanRequest:
    effect_id: UUID
    destination_id: str
    marker: str
    writer_identities: frozenset
    first_attempt_started_at: dt.datetime


@dataclass(frozen=True)
class ScanOutcome:
    result: str
    check: CheckResult
    evidence: execution.ProviderEffectEvidence
    revoked: bool = False


@dataclass
class _ListingProgress:
    entries: list = field(default_factory=list)
    finished: bool = False
    last_readable: bool | None = None


@dataclass
class _ScanProgress:
    candidates: list = field(default_factory=list)
    found: list = field(default_factory=list)
    finished: bool = False
    root_unreadable: bool = False


# -- answer parsing --------------------------------------------------------------------


def _malformed() -> ReducedError:
    return ReducedError(Verdict(COULD_NOT_CHECK, cause="response"))


def _require_mapping(value) -> Mapping:
    if not isinstance(value, Mapping):
        raise _malformed()
    return value


def _rich_text(runs) -> str:
    if not isinstance(runs, list):
        return ""
    parts = []
    for run in runs:
        if not isinstance(run, Mapping):
            continue
        text = run.get("plain_text")
        if not isinstance(text, str):
            content = run.get("text")
            text = content.get("content") if isinstance(content, Mapping) else None
        parts.append(text if isinstance(text, str) else "")
    return "".join(parts)


def _bounded(text: str | None) -> str | None:
    if not isinstance(text, str):
        return None
    text = text.strip()
    return text[:TEXT_LIMIT] if text else None


def page_title(page: Mapping) -> str | None:
    """The page's title property as plain text; None for an untitled page."""
    properties = page.get("properties")
    if not isinstance(properties, Mapping):
        return None
    for value in properties.values():
        if isinstance(value, Mapping) and value.get("type") == "title":
            return _bounded(_rich_text(value.get("title")))
    return None


def block_text(block: Mapping) -> str:
    kind = block.get("type")
    content = block.get(kind) if isinstance(kind, str) else None
    return _rich_text(content.get("rich_text")) if isinstance(content, Mapping) else ""


def _parent_page(page: Mapping) -> str | None:
    parent = page.get("parent")
    if isinstance(parent, Mapping) and parent.get("type") == "page_id":
        return normalise_id(parent.get("page_id"))
    return None


def _creator(value: Mapping) -> str | None:
    created_by = value.get("created_by")
    return normalise_id(created_by.get("id")) if isinstance(created_by, Mapping) else None


def _created_time(value: Mapping) -> dt.datetime | None:
    raw = value.get("created_time")
    if not isinstance(raw, str):
        return None
    try:
        parsed = dt.datetime.fromisoformat(raw)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _trashed(value: Mapping) -> bool:
    return value.get("in_trash") is True or value.get("archived") is True


def _page_url(value) -> str | None:
    return value if isinstance(value, str) and _NOTION_URL.fullmatch(value) else None


def _context(page: Mapping, titles: Mapping[str, str | None]) -> str:
    """Enough location context to tell same-titled pages apart (BR1.5)."""
    parent = page.get("parent")
    kind = parent.get("type") if isinstance(parent, Mapping) else None
    if kind == "workspace":
        return "워크스페이스 최상위"
    reference = normalise_id(parent.get(kind)) if isinstance(kind, str) else None
    if kind == "page_id" and reference is not None:
        title = titles.get(reference)
        return f"상위 페이지: {title}" if title else f"상위 페이지 · {reference[:8]}"
    if kind in ("database_id", "data_source_id") and reference is not None:
        return f"데이터베이스 항목 · {reference[:8]}"
    if kind == "block_id" and reference is not None:
        return f"블록 안 · {reference[:8]}"
    return "위치 정보 없음"


def _list_results(answer) -> tuple[list, str | None, bool]:
    answer = _require_mapping(answer)
    results = answer.get("results")
    if not isinstance(results, list):
        raise _malformed()
    has_more = answer.get("has_more") is True
    cursor = answer.get("next_cursor")
    if has_more and not (isinstance(cursor, str) and cursor):
        raise _malformed()
    return [item for item in results if isinstance(item, Mapping)], cursor, has_more


# -- the adapter -----------------------------------------------------------------------


class NotionAdapter:
    def __init__(
        self,
        session: NotionSession,
        store: AdapterStore,
        *,
        content: ContentPort | None = None,
        clock: Callable[[], dt.datetime] = _utc_now,
    ):
        self._session = session
        self._store = store
        self._content = content
        self._clock = clock

    @property
    def policy(self) -> ExportPolicy:
        return self._session.policy

    # -- shared steps ----------------------------------------------------------------

    async def _read(self, ctx: OperationContext, call: Callable[[], Any]):
        """One read under the read-retry rule (NFR4.6, §9.3): a 429 that is not blocked,
        or a 529, is retried at most `read_retries` times inside the budget, each time
        after the later of Notion's stated wait and the next pace slot. Any other end
        raises the reduced verdict, after its `except` block has ended."""
        retries = 0
        while True:
            verdict = None
            try:
                return await call()
            except Exception as error:  # reduced at once; the object is dropped here
                verdict = classify_read(error)
            if verdict.category != RETRYABLE:
                raise ReducedError(verdict) from None
            if retries >= self.policy.read_retries:
                spent = Verdict(COULD_NOT_CHECK, cause="retries-spent")
                raise ReducedError(spent) from None
            retries += 1
            await ctx.pacer.wait_for_slot(at_least=float(verdict.retry_after or 0))

    async def _children(self, sdk, ctx, block_id: str, cursor: str | None):
        def call():
            return sdk.blocks.children.list(
                block_id=block_id, page_size=PAGE_SIZE, start_cursor=cursor
            )

        return _list_results(await self._read(ctx, call))

    async def _last_block(self, sdk, ctx, page_id: str) -> Mapping | None:
        """The last top-level block of a page, paging to the end (bounded)."""
        cursor, last = None, None
        for _ in range(MAX_CHILD_PAGES):
            results, cursor, has_more = await self._children(sdk, ctx, page_id, cursor)
            if results:
                last = results[-1]
            if not has_more:
                return last
        raise ReducedError(Verdict(COULD_NOT_CHECK, cause="bound"))

    async def _probe(self, sdk, ctx, destination_id: str) -> tuple[bool, Mapping]:
        """A direct read: the page, then its first children request (BR1.5). True when
        both answer; NOT_READABLE when Notion refuses or the page is in the trash."""
        page = _require_mapping(
            await self._read(ctx, lambda: sdk.pages.retrieve(page_id=destination_id))
        )
        if normalise_id(page.get("id")) != destination_id:
            raise _malformed()
        if _trashed(page):
            raise ReducedError(Verdict(NOT_READABLE))
        await self._read(
            ctx, lambda: sdk.blocks.children.list(block_id=destination_id, page_size=1)
        )
        return True, page

    async def _settle_connection(self, target, result: SessionResult) -> bool:
        """Connection side effects of one stored-token operation. True when a revocation
        took effect. Side-effect failures never become exceptions of the operation."""
        if not isinstance(target, StoredConnection) or result.opened is None:
            return False
        opened = result.opened
        try:
            if result.category == TOKEN_INVALID or (
                result.verdict is not None and result.verdict.refusal == REFUSAL_TOKEN_INVALID
            ):
                revoked = await asyncio.to_thread(
                    self._store.revoke_connection,
                    target.account_id,
                    target.connection_id,
                    opened.revision,
                    now=self._clock(),
                )
                return revoked is not None
            available = None
            if result.category == PROTECTION_UNAVAILABLE and opened.state == "connected":
                available = False
            elif result.category != PROTECTION_UNAVAILABLE and opened.state == "unavailable":
                available = True
            if available is not None:
                await asyncio.to_thread(
                    self._store.set_availability,
                    target.account_id,
                    target.connection_id,
                    opened.revision,
                    available=available,
                )
        except Exception:  # noqa: BLE001 - the operation's own outcome stands (D16)
            return False
        return False

    # -- identify --------------------------------------------------------------------

    async def identify(
        self, target: StoredConnection | CandidateToken, *, gate_key: UUID | None = None
    ) -> Identification:
        """The token's bot user: workspace name, `bot.workspace_id` and the bot's id."""

        async def work(sdk, ctx):
            me = _require_mapping(await self._read(ctx, sdk.users.me))
            bot = me.get("bot")
            integration = normalise_id(me.get("id"))
            if me.get("type") != "bot" or not isinstance(bot, Mapping) or integration is None:
                raise _malformed()
            raw = bot.get("workspace_id")
            workspace_id = normalise_id(raw) or (
                raw if isinstance(raw, str) and _WORKSPACE_ID.fullmatch(raw) else None
            )
            if workspace_id is None:
                raise _malformed()
            return Identification(
                OK,
                workspace_name=_bounded(bot.get("workspace_name")),
                workspace_id=workspace_id,
                integration_id=integration,
            )

        result = await self._session.run(
            target, self.policy.token_check_budget_seconds, work, gate_key=gate_key
        )
        revoked = await self._settle_connection(target, result)
        if result.ok:
            return result.value
        return Identification(result.category, revoked=revoked)

    # -- list destinations -----------------------------------------------------------

    async def list_destinations(
        self,
        target: StoredConnection,
        *,
        creation_capability: str = "unknown",
        last_destination_id: str | None = None,
        gate_key: UUID | None = None,
    ) -> Listing:
        """Shared pages, searched by hand with `page_size=100` and bounded, plus a direct
        read of `lastDestinationId`, as one operation. The listing is incomplete when
        the pages, the retries or the budget run out; entries found so far are kept."""
        if creation_capability not in ("unknown", "confirmed", "refused"):
            raise ValueError("creation capability unknown")
        last = normalise_id(last_destination_id) if last_destination_id else None
        progress = _ListingProgress()

        async def work(sdk, ctx):
            if last is not None:
                progress.last_readable = await self._probe_readable(sdk, ctx, last)
            cursor = None
            for _ in range(MAX_SEARCH_PAGES):
                try:
                    results, cursor, has_more = await self._search_page(sdk, ctx, cursor)
                except ReducedError as reduced:
                    if reduced.verdict.category == TOKEN_INVALID:
                        raise
                    return
                progress.entries.extend(results)
                if not has_more:
                    progress.finished = True
                    return

        result = await self._session.run(
            target, self.policy.listing_budget_seconds, work, gate_key=gate_key
        )
        revoked = await self._settle_connection(target, result)
        if result.category in (TOKEN_INVALID, NOT_CONNECTED, PROTECTION_UNAVAILABLE):
            return Listing(result.category, revoked=revoked)
        entries = self._entries(progress, creation_capability, last)
        return Listing(
            OK if result.ok else COULD_NOT_CHECK,
            destinations=entries,
            complete=result.ok and progress.finished,
            last_destination_id=last,
            last_destination_readable=progress.last_readable,
        )

    async def _probe_readable(self, sdk, ctx, destination_id: str) -> bool | None:
        verdict = None
        try:
            await self._probe(sdk, ctx, destination_id)
            return True
        except ReducedError as reduced:
            verdict = reduced.verdict
        if verdict.category == TOKEN_INVALID:
            raise ReducedError(verdict) from None
        return False if verdict.category == NOT_READABLE else None

    async def _search_page(self, sdk, ctx, cursor):
        def call():
            return sdk.search(
                filter={"property": "object", "value": "page"},
                page_size=PAGE_SIZE,
                start_cursor=cursor,
            )

        return _list_results(await self._read(ctx, call))

    @staticmethod
    def _entries(progress, capability: str, last: str | None) -> tuple:
        pages = {}
        for page in progress.entries:
            page_id = normalise_id(page.get("id"))
            if page.get("object") == "page" and page_id and not _trashed(page):
                pages.setdefault(page_id, page)
        titles = {page_id: page_title(page) for page_id, page in pages.items()}
        entries = []
        for page_id, page in pages.items():
            readable = progress.last_readable if page_id == last else None
            entries.append(
                ListedDestination(
                    destination_id=page_id,
                    title=titles[page_id],
                    context=_context(page, titles),
                    readable=readable,
                    creation_capability=capability,
                    writable=readable is not False and capability != "refused",
                )
            )
        return tuple(entries)

    # -- read one destination -----------------------------------------------------------

    async def read_destination(
        self, target: StoredConnection, destination_id: str, *, gate_key: UUID | None = None
    ) -> DestinationRead:
        """Confirms the connection can read the page and its children (BR1.5)."""
        page_id = normalise_id(destination_id)
        if page_id is None:
            return DestinationRead(NOT_READABLE, readable=False)

        async def work(sdk, ctx):
            _, page = await self._probe(sdk, ctx, page_id)
            return DestinationRead(
                OK, readable=True, title=page_title(page), context=_context(page, {})
            )

        result = await self._session.run(
            target, self.policy.page_read_budget_seconds, work, gate_key=gate_key
        )
        revoked = await self._settle_connection(target, result)
        if result.ok:
            return result.value
        readable = False if result.category == NOT_READABLE else None
        return DestinationRead(result.category, readable=readable, revoked=revoked)

    # -- create a page -------------------------------------------------------------------

    def _content_check(self, request: WriteRequest, content: BoundContent | None) -> bool:
        """D12: the recomputed hash equals the bound one, the marker is the last
        top-level block and the parent is the bound destination."""
        if content is None or not isinstance(content.body, Mapping):
            return False
        try:
            recomputed = content_hash(content.body)
        except (TypeError, ValueError):
            return False
        children = content.body.get("children")
        last = children[-1] if isinstance(children, list) and children else None
        return (
            recomputed == content.content_hash
            and isinstance(last, Mapping)
            and block_text(last) == content.marker
            and normalise_id(content.destination_id) == request.destination_id
        )

    async def create_page(
        self, target: StoredConnection, request: WriteRequest, *, deadline_seconds: float
    ) -> WriteResult:
        """The one write: under the bound destination, until `deadline_seconds` (the
        attempt's `deadlineAt`). The lane has already reserved and waited for its pace
        slot. A content mismatch sends nothing and is refused as content-rejected."""
        if self._content is None:
            raise RuntimeError("the content port is required for writes")
        content = await asyncio.to_thread(self._content.bound_content, request.effect_id)
        if not self._content_check(request, content):
            refused = WriteOutcome("refused", reason=REFUSAL_CONTENT_REJECTED)
            return WriteResult(
                REFUSED, request.effect_id, refused, sent=False, refusal=REFUSAL_CONTENT_REJECTED
            )
        request.provider_request(content)

        async def work(sdk, ctx):
            return await sdk.pages.create(
                parent={"page_id": request.destination_id},
                properties=content.body["properties"],
                children=content.body["children"],
            )

        result = await self._session.run(
            target,
            deadline_seconds,
            work,
            classify=classify_write,
            request_timeout=deadline_seconds,
            prepaid_slots=1,
        )
        revoked = await self._settle_connection(target, result)
        if result.category in (NOT_CONNECTED, PROTECTION_UNAVAILABLE):
            return WriteResult(result.category, request.effect_id, None, sent=False)
        if result.ok:
            return self._created_answer(target, request, content, result.value, revoked)
        return await self._unwritten_answer(target, request, content, result.verdict, revoked)

    def _created_answer(self, target, request, content, page, revoked) -> WriteResult:
        page = page if isinstance(page, Mapping) else {}
        page_id = normalise_id(page.get("id"))
        request_id = page.get("request_id") if isinstance(page.get("request_id"), str) else None
        if page_id is None or _parent_page(page) != request.destination_id:
            uncertain = WriteOutcome("uncertain", provider_request_id=_safe_id(request_id))
            return WriteResult(UNCERTAIN, request.effect_id, uncertain, sent=True, revoked=revoked)
        outcome = WriteOutcome(
            "created",
            provider_request_id=_safe_id(request_id),
            creator_confirmed=_creator(page) == normalise_id(request.writer_identity),
            remote_reference=page_id,
            remote_url=_page_url(page.get("url")),
        )
        return WriteResult(CREATED, request.effect_id, outcome, sent=True, revoked=revoked)

    async def _unwritten_answer(self, target, request, content, verdict, revoked):
        request_id = _safe_id(verdict.request_id)
        if verdict.category == REFUSED:
            outcome = WriteOutcome(
                "refused", provider_request_id=request_id, reason=verdict.refusal
            )
            return WriteResult(
                REFUSED,
                request.effect_id,
                outcome,
                sent=True,
                refusal=verdict.refusal,
                revoked=revoked,
            )
        if verdict.category == RATE_LIMITED:
            wait = max(1, verdict.retry_after or 0)
            outcome = WriteOutcome(
                "rate-limited",
                provider_request_id=request_id,
                retry_at=self._clock() + dt.timedelta(seconds=wait),
            )
            return WriteResult(
                RATE_LIMITED, request.effect_id, outcome, sent=True, retry_after_seconds=wait
            )
        if verdict.committed_page_id is not None:
            back = await self.read_back(
                target,
                page_id=verdict.committed_page_id,
                destination_id=request.destination_id,
                writer_identity=request.writer_identity,
                marker=content.marker,
            )
            if back.passed:
                outcome = WriteOutcome(
                    "created",
                    provider_request_id=request_id,
                    creator_confirmed=True,
                    remote_reference=verdict.committed_page_id,
                    remote_url=back.remote_url,
                )
                return WriteResult(CREATED, request.effect_id, outcome, sent=True)
        uncertain = WriteOutcome("uncertain", provider_request_id=request_id)
        return WriteResult(UNCERTAIN, request.effect_id, uncertain, sent=True)

    # -- read-back -----------------------------------------------------------------------

    async def read_back(
        self,
        target: StoredConnection,
        *,
        page_id: str,
        destination_id: str,
        writer_identity: str,
        marker: str,
    ) -> ReadBack:
        """BR4.2's three checks, under the read-back budget: the page is under the bound
        destination, created by this attempt's writer, with the marker last."""
        page_ref = normalise_id(page_id)
        writer = normalise_id(writer_identity)
        if page_ref is None or writer is None:
            return ReadBack(COULD_NOT_CHECK)

        async def work(sdk, ctx):
            page = _require_mapping(
                await self._read(ctx, lambda: sdk.pages.retrieve(page_id=page_ref))
            )
            if _parent_page(page) != destination_id or _creator(page) != writer:
                return ReadBack(OK, passed=False)
            last = await self._last_block(sdk, ctx, page_ref)
            passed = last is not None and block_text(last) == marker
            return ReadBack(OK, passed=passed, remote_url=_page_url(page.get("url")))

        result = await self._session.run(target, self.policy.read_back_budget_seconds, work)
        revoked = await self._settle_connection(target, result)
        return result.value if result.ok else ReadBack(result.category, revoked=revoked)

    # -- reconciliation scan --------------------------------------------------------------

    def window_start(self, first_attempt: dt.datetime) -> dt.datetime:
        """The first attempt's start minute less the clock margin (BR4.4)."""
        minute = first_attempt.replace(second=0, microsecond=0)
        return minute - dt.timedelta(seconds=self.policy.clock_margin_seconds)

    async def scan(self, target: StoredConnection, request: ScanRequest) -> ScanOutcome:
        """Scan the destination for the effect's marker, descending into every block with
        children except child pages and child databases (§9.4). Ends in one of four
        results; a marker found mid-scan is a definite answer even if the scan stops."""
        destination = normalise_id(request.destination_id)
        writers = frozenset(filter(None, map(normalise_id, request.writer_identities)))
        window = self.window_start(request.first_attempt_started_at)
        progress = _ScanProgress()

        async def work(sdk, ctx):
            await self._walk(sdk, ctx, destination, writers, window, progress)
            for candidate in progress.candidates:
                last = await self._last_block(sdk, ctx, candidate["id"])
                if last is not None and block_text(last) == request.marker:
                    progress.found.append(candidate)
            progress.finished = True

        if destination is None:
            result = SessionResult(NOT_READABLE)
            revoked = False
        else:
            result = await self._session.run(target, self.policy.scan_budget_seconds, work)
            revoked = await self._settle_connection(target, result)
        return self._scan_outcome(request, window, progress, result, revoked)

    async def _walk(self, sdk, ctx, destination, writers, window, progress) -> None:
        pending, visited = [destination], 0
        while pending:
            container = pending.pop(0)
            cursor = None
            while True:
                try:
                    results, cursor, has_more = await self._children(sdk, ctx, container, cursor)
                except ReducedError as reduced:
                    if container == destination and reduced.verdict.category == NOT_READABLE:
                        progress.root_unreadable = True
                    raise
                for block in results:
                    visited += 1
                    if visited > MAX_SCAN_BLOCKS:
                        raise ReducedError(Verdict(COULD_NOT_CHECK, cause="bound"))
                    self._visit(block, writers, window, pending, progress)
                if not has_more:
                    break

    @staticmethod
    def _visit(block, writers, window, pending, progress) -> None:
        block_id = normalise_id(block.get("id"))
        kind = block.get("type")
        if block_id is None or _trashed(block):
            return
        if kind == "child_page":
            created = _created_time(block)
            if _creator(block) in writers and created is not None and created >= window:
                progress.candidates.append({"id": block_id, "created": created})
            return
        if block.get("has_children") is True and kind not in SKIPPED_CONTAINERS:
            pending.append(block_id)

    def _scan_outcome(self, request, window, progress, result, revoked) -> ScanOutcome:
        found = sorted(progress.found, key=lambda item: (item["created"], item["id"]))
        if found:
            outcome = MARKER_FOUND
        elif result.ok and progress.finished:
            outcome = NOT_FOUND
        elif progress.root_unreadable or result.category in (
            TOKEN_INVALID,
            NOT_READABLE,
            NOT_CONNECTED,
            PROTECTION_UNAVAILABLE,
        ):
            outcome = LISTING_UNAVAILABLE
        else:
            outcome = LISTING_INCOMPLETE
        evidence_hash = canonical_digest(
            {
                "effectId": str(request.effect_id),
                "result": outcome,
                "windowStart": window.isoformat(),
                "candidates": sorted(item["id"] for item in progress.candidates),
                "found": [item["id"] for item in found],
                "complete": bool(result.ok and progress.finished),
            }
        )
        first = found[0]["id"] if found else None
        others = [
            {"remoteReference": item["id"], "remoteUrl": f"https://www.notion.so/{item['id']}"}
            for item in found[1 : 1 + MAX_OTHER_MARKED]
        ]
        check = CheckResult(
            result=outcome,
            window_start=window,
            evidence_hash=evidence_hash,
            remote_reference=first,
            remote_url=f"https://www.notion.so/{first}" if first else None,
            other_marked_pages=others,
        )
        evidence = execution.ProviderEffectEvidence(
            effectId=str(request.effect_id),
            disposition="committed" if found else "unknown",
            remoteReference=first,
            evidenceHash=evidence_hash,
            observedAt=self._clock(),
            scanComplete=bool(result.ok and progress.finished),
        )
        return ScanOutcome(outcome, check, evidence, revoked=revoked)


_PROVIDER_ID = re.compile(r"[0-9A-Za-z][0-9A-Za-z._:-]{0,127}")


def _safe_id(value) -> str | None:
    return value if isinstance(value, str) and _PROVIDER_ID.fullmatch(value) else None
