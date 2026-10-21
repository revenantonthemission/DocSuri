"""An HTTP-level stand-in for Notion, under the real SDK and behind `GuardedTransport`.

`FakeNotion` answers the five requests U6 sends (`GET /v1/users/me`, `POST /v1/search`,
`GET /v1/pages/{id}`, `GET /v1/blocks/{id}/children`, `POST /v1/pages`) in the shapes
the 2026-03-11 API reference documents, including its error bodies:

- 401 `unauthorized`, 403 `restricted_resource` (with `additional_data.block_limit`
  `block_creation` for a workspace block limit), 404 `object_not_found`, 400
  `validation_error`, 409 `conflict_error`, 429 `rate_limited` with `Retry-After` and
  `additional_data.retry_after` (and `rate_limit_reason` `public_api_request_blocked`
  when blocked), 500, 502, 503 `service_unavailable` (with
  `additional_data.committed_resource_id` when a create was saved), 504 and 529
  `service_overload`.

Scenarios are set with methods (tests) or loaded from a private, run-bound
`fake-notion.json` (synthetic compositions). The content hash of every create is
computed with the backend's own `rendering.content_hash`; the fake never reads test
data. The request log stays in memory and is never logged.
"""

import asyncio
import datetime as dt
import hashlib
import json
import time
from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID, uuid4

import httpx

from .classification import normalise_id
from .rendering import content_hash

PAGE_SIZE_MAX = 100
OVER_CAP_BYTES = 2_100_000
HANG_SECONDS = 3600

# Answer kinds a scenario can queue for an operation.
ERROR = "error"
SLOW = "slow"
HANG = "hang"
OVERSIZE_DECLARED = "oversize-declared"
OVERSIZE_STREAMED = "oversize-streamed"
REDIRECT = "redirect"
SAVED_BUSY = "saved-busy"
TIMEOUT_AFTER_SUCCESS = "timeout-after-success"
LOST_AFTER_SUCCESS = "lost-after-success"

# Operations an answer can be queued for.
OPERATIONS = ("users.me", "search", "pages.retrieve", "blocks.children", "pages.create")

_ERROR_CODES = {
    400: "validation_error",
    401: "unauthorized",
    403: "restricted_resource",
    404: "object_not_found",
    409: "conflict_error",
    429: "rate_limited",
    500: "internal_server_error",
    502: "bad_gateway",
    503: "service_unavailable",
    504: "gateway_timeout",
    529: "service_overload",
}


@dataclass(frozen=True)
class Answer:
    """One scripted answer. `status` and `code` shape an error body; `seconds` is a
    delay for slow answers or a stated wait for 429 and 529."""

    kind: str
    status: int | None = None
    code: str | None = None
    additional: Mapping | None = None
    seconds: float | None = None

    @classmethod
    def error(cls, status: int, *, code: str | None = None, additional=None, wait=None):
        return cls(ERROR, status, code or _ERROR_CODES.get(status), additional, wait)

    @classmethod
    def rate_limited(cls, *, wait: int = 1, blocked: bool = False):
        additional = {"retry_after": str(wait)}
        if blocked:
            additional["rate_limit_reason"] = "public_api_request_blocked"
        else:
            additional["rate_limit_reason"] = "public_api_request_rate_limit"
        return cls(ERROR, 429, "rate_limited", additional, wait)

    @classmethod
    def overloaded(cls, *, wait: int = 1):
        return cls(ERROR, 529, "service_overload", {"retry_after": str(wait)}, wait)

    @classmethod
    def block_limit(cls):
        return cls(ERROR, 403, "restricted_resource", {"block_limit": "block_creation"})

    @classmethod
    def slow(cls, seconds: float):
        return cls(SLOW, seconds=seconds)

    @classmethod
    def of(cls, kind: str):
        return cls(kind)


@dataclass(frozen=True)
class LoggedRequest:
    """Method, path, the Authorization value, the body hash, and for a create the
    content hash the fake computed. Kept in memory only."""

    method: str
    path: str
    authorization: str | None
    body_hash: str | None
    content_hash: str | None
    at: float


@dataclass
class _Bot:
    bot_id: str
    workspace_id: str
    workspace_name: str | None


@dataclass
class _Node:
    """A page or a block; pages carry a title, blocks a type and text."""

    node_id: str
    kind: str
    parent_id: str | None
    created_by: str
    created_time: dt.datetime
    title: str | None = None
    text: str | None = None
    children: list = field(default_factory=list)
    readable: bool = True
    is_page: bool = False


class _Stream(httpx.AsyncByteStream):
    def __init__(self, size: int):
        self._size = size

    async def __aiter__(self):
        sent = 0
        while sent < self._size:
            chunk = b"x" * min(65536, self._size - sent)
            sent += len(chunk)
            yield chunk


def _minute(value: dt.datetime) -> str:
    return value.replace(second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M:00.000Z")


def _hyphenated(node_id: str) -> str:
    return str(UUID(hex=node_id))


def _run(text: str) -> dict:
    return {
        "type": "text",
        "text": {"content": text, "link": None},
        "annotations": {
            "bold": False,
            "italic": False,
            "strikethrough": False,
            "underline": False,
            "code": False,
            "color": "default",
        },
        "plain_text": text,
        "href": None,
    }


def _text_of(runs) -> str:
    if not isinstance(runs, list):
        return ""
    return "".join(
        run.get("text", {}).get("content", "") for run in runs if isinstance(run, Mapping)
    )


class FakeNotion(httpx.AsyncBaseTransport):
    """The fake Notion transport. Never touches the network."""

    def __init__(self, *, clock: Callable[[], dt.datetime] | None = None):
        self._clock = clock or (lambda: dt.datetime.now(dt.UTC))
        self._bots: dict[str, _Bot] = {}
        self._nodes: dict[str, _Node] = {}
        self._queues: dict[tuple[str, str | None], deque] = {}
        self._search_mode = "complete"
        self._search_page_size = PAGE_SIZE_MAX
        self._expected_hash: dict[str | None, str] = {}
        self._page_read_limits: dict[str, int] = {}
        self._page_reads: dict[str, int] = {}
        self._busy_after_create: set[str] = set()
        self._created_under: set[str] = set()
        self.requests: list[LoggedRequest] = []

    # -- scenario -------------------------------------------------------------------

    def add_token(
        self, token: str, *, bot_id: str, workspace_id: str, workspace_name: str | None = None
    ) -> None:
        """Map a synthetic token to a bot identity."""
        if normalise_id(bot_id) is None:
            raise ValueError("bot ids are 32 hex digits")
        self._bots[token] = _Bot(normalise_id(bot_id), workspace_id, workspace_name)

    def add_page(
        self,
        page_id: str | None = None,
        *,
        title: str | None = None,
        parent_id: str | None = None,
        readable: bool = True,
        created_by: str | None = None,
        created_time: dt.datetime | None = None,
    ) -> str:
        """A page; under a parent it also appears as that parent's `child_page` block."""
        node_id = normalise_id(page_id) if page_id else uuid4().hex
        if node_id is None:
            raise ValueError("page ids are 32 hex digits")
        node = _Node(
            node_id,
            "child_page",
            normalise_id(parent_id) if parent_id else None,
            normalise_id(created_by) if created_by else uuid4().hex,
            created_time or self._clock(),
            title=title,
            readable=readable,
            is_page=True,
        )
        self._nodes[node_id] = node
        if node.parent_id is not None:
            self._nodes[node.parent_id].children.append(node_id)
        return node_id

    def add_block(
        self, parent_id: str, kind: str = "paragraph", *, text: str = "", block_id=None
    ) -> str:
        """A block under a page or a block: paragraph, toggle, column_list, column…"""
        node_id = normalise_id(block_id) if block_id else uuid4().hex
        parent = normalise_id(parent_id)
        node = _Node(node_id, kind, parent, uuid4().hex, self._clock(), text=text)
        self._nodes[node_id] = node
        self._nodes[parent].children.append(node_id)
        return node_id

    def queue(self, operation: str, answer: Answer, *, target: str | None = None) -> None:
        """Answer the next request of `operation` (optionally for one page) with `answer`."""
        if operation not in OPERATIONS:
            raise ValueError("unknown operation")
        key = (operation, normalise_id(target) if target else None)
        self._queues.setdefault(key, deque()).append(answer)

    def set_search(self, mode: str = "complete", *, page_size: int = PAGE_SIZE_MAX) -> None:
        """`complete`; `partial` (the second search page answers 500); `unavailable`."""
        if mode not in ("complete", "partial", "unavailable"):
            raise ValueError("unknown search mode")
        self._search_mode = mode
        self._search_page_size = page_size

    def expect_content_hash(self, value: str, *, parent_id: str | None = None) -> None:
        """A create whose content hash differs is refused as `validation_error`."""
        self._expected_hash[normalise_id(parent_id) if parent_id else None] = value

    def limit_page_reads(self, page_id: str, normal: int) -> None:
        """The first `normal` page requests of this page, with their children requests,
        answer normally; every later request for it answers 503."""
        self._page_read_limits[normalise_id(page_id)] = normal

    def busy_children_after_create(self, page_id: str) -> None:
        """Once a create under this page has been answered, its children answer 503."""
        self._busy_after_create.add(normalise_id(page_id))

    def page(self, page_id: str) -> _Node | None:
        return self._nodes.get(normalise_id(page_id))

    @property
    def writes(self) -> list[LoggedRequest]:
        return [
            entry for entry in self.requests if entry.method == "POST" and entry.path == "/v1/pages"
        ]

    def pages_under(self, parent_id: str) -> list[str]:
        parent = self._nodes.get(normalise_id(parent_id))
        if parent is None:
            return []
        return [child for child in parent.children if self._nodes[child].is_page]

    # -- loading a run-bound scenario ---------------------------------------------------

    @classmethod
    def from_scenario(cls, scenario: Mapping, *, run_id: str, clock=None) -> "FakeNotion":
        """Build from a `fake-notion.json` mapping bound to this run."""
        if not isinstance(scenario, Mapping) or scenario.get("runId") != run_id:
            raise ValueError("the fake Notion scenario belongs to another run")
        fake = cls(clock=clock)
        for token, bot in scenario.get("tokens", {}).items():
            fake.add_token(
                token,
                bot_id=bot["botId"],
                workspace_id=bot["workspaceId"],
                workspace_name=bot.get("workspaceName"),
            )
        for page in scenario.get("pages", []):
            fake._load_page(page)
        search = scenario.get("search", {})
        fake.set_search(search.get("mode", "complete"), page_size=search.get("pageSize", 100))
        return fake

    def _load_page(self, page: Mapping) -> None:
        page_id = self.add_page(
            page["id"],
            title=page.get("title"),
            parent_id=page.get("parentId"),
            readable=page.get("readable", True),
            created_by=page.get("createdBy"),
        )
        for block in page.get("blocks", []):
            self.add_block(page_id, block.get("type", "paragraph"), text=block.get("text", ""))
        if "normalPageReads" in page:
            self.limit_page_reads(page_id, int(page["normalPageReads"]))
        if page.get("busyChildrenAfterCreate"):
            self.busy_children_after_create(page_id)
        for answer in page.get("createAnswers", []):
            self.queue("pages.create", Answer.error(int(answer["status"])), target=page_id)

    @classmethod
    def load(cls, path: Path, *, run_id: str, clock=None) -> "FakeNotion":
        """Load the private, run-bound scenario file (mode 0600, owned by this user)."""
        from backend.local_profile import private_bytes

        return cls.from_scenario(json.loads(private_bytes(path)), run_id=run_id, clock=clock)

    # -- transport ------------------------------------------------------------------------

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        body = await request.aread()
        operation, target = self._route(request)
        parsed = json.loads(body) if body else None
        created_hash = None
        if operation == "pages.create" and isinstance(parsed, Mapping):
            created_hash = self._hash_of(parsed)
        self.requests.append(
            LoggedRequest(
                request.method,
                request.url.path,
                request.headers.get("authorization"),
                hashlib.sha256(body).hexdigest() if body else None,
                created_hash,
                time.monotonic(),
            )
        )
        answer = self._next_answer(operation, target)
        if answer is not None and answer.kind == SLOW:
            await asyncio.sleep(answer.seconds or 0)
            answer = None
        if answer is not None and answer.kind == HANG:
            await asyncio.sleep(HANG_SECONDS)
        if answer is not None and answer.kind in (OVERSIZE_DECLARED, OVERSIZE_STREAMED, REDIRECT):
            return self._special(answer)
        return self._answer(request, operation, target, parsed, created_hash, answer)

    async def aclose(self) -> None:
        """The fake outlives every operation's client; closing a client leaves it as is."""

    def _route(self, request: httpx.Request) -> tuple[str | None, str | None]:
        parts = request.url.path.strip("/").split("/")
        method = request.method
        if method == "GET" and parts == ["v1", "users", "me"]:
            return "users.me", None
        if method == "POST" and parts == ["v1", "search"]:
            return "search", None
        if method == "POST" and parts == ["v1", "pages"]:
            return "pages.create", None
        if method == "GET" and len(parts) == 3 and parts[:2] == ["v1", "pages"]:
            return "pages.retrieve", normalise_id(parts[2])
        if method == "GET" and len(parts) == 4 and parts[1] == "blocks" and parts[3] == "children":
            return "blocks.children", normalise_id(parts[2])
        return None, None

    def _next_answer(self, operation, target) -> Answer | None:
        for key in ((operation, target), (operation, None)):
            queued = self._queues.get(key)
            if queued:
                return queued.popleft()
        return None

    @staticmethod
    def _special(answer: Answer) -> httpx.Response:
        if answer.kind == REDIRECT:
            return httpx.Response(302, headers={"location": "https://example.invalid/"})
        if answer.kind == OVERSIZE_DECLARED:
            return httpx.Response(
                200, headers={"content-length": str(OVER_CAP_BYTES)}, content=b"{}"
            )
        return httpx.Response(200, stream=_Stream(OVER_CAP_BYTES))

    # -- answers ---------------------------------------------------------------------------

    @staticmethod
    def _json(status: int, payload: Mapping, headers: Mapping | None = None) -> httpx.Response:
        data = {**payload, "request_id": str(uuid4())}
        return httpx.Response(status, headers=dict(headers or {}), json=data)

    def _error(self, answer: Answer) -> httpx.Response:
        status = answer.status or 500
        payload = {
            "object": "error",
            "status": status,
            "code": answer.code,
            "message": "synthetic answer",
        }
        if answer.additional:
            payload["additional_data"] = dict(answer.additional)
        headers = {}
        if status in (429, 529) and answer.seconds is not None:
            headers["retry-after"] = str(int(answer.seconds))
        return self._json(status, payload, headers)

    def _plain_error(self, status: int, additional=None) -> httpx.Response:
        return self._error(Answer.error(status, additional=additional))

    def _bot(self, request: httpx.Request) -> _Bot | None:
        value = request.headers.get("authorization", "")
        return self._bots.get(value[7:]) if value.startswith("Bearer ") else None

    def _answer(self, request, operation, target, parsed, created_hash, answer):
        bot = self._bot(request)
        if operation is None:
            return self._plain_error(400, {"reason": "unsupported"})
        if operation == "pages.create":
            # A scripted error still counts as a create answered under its parent.
            return self._create(bot, parsed, created_hash, answer)
        if answer is not None and answer.kind == ERROR:
            return self._error(answer)
        if bot is None:
            return self._plain_error(401)
        handlers = {
            "users.me": lambda: self._me(bot),
            "search": lambda: self._search(parsed),
            "pages.retrieve": lambda: self._retrieve(target),
            "blocks.children": lambda: self._children(target, request),
        }
        return handlers[operation]()

    def _me(self, bot: _Bot) -> httpx.Response:
        return self._json(
            200,
            {
                "object": "user",
                "id": _hyphenated(bot.bot_id),
                "name": "DocSuri synthetic",
                "avatar_url": None,
                "type": "bot",
                "bot": {
                    "owner": {"type": "workspace", "workspace": True},
                    "workspace_name": bot.workspace_name,
                    "workspace_id": bot.workspace_id,
                    "workspace_limits": {"max_file_upload_size_in_bytes": 5_242_880},
                },
            },
        )

    def _page_object(self, node: _Node) -> dict:
        parent = (
            {"type": "page_id", "page_id": _hyphenated(node.parent_id)}
            if node.parent_id
            else {"type": "workspace", "workspace": True}
        )
        title = [_run(node.title)] if node.title else []
        return {
            "object": "page",
            "id": _hyphenated(node.node_id),
            "created_time": _minute(node.created_time),
            "last_edited_time": _minute(node.created_time),
            "created_by": {"object": "user", "id": _hyphenated(node.created_by)},
            "last_edited_by": {"object": "user", "id": _hyphenated(node.created_by)},
            "parent": parent,
            "in_trash": False,
            "properties": {"title": {"id": "title", "type": "title", "title": title}},
            "url": f"https://www.notion.so/{node.node_id}",
        }

    def _block_object(self, node: _Node) -> dict:
        parent = self._nodes.get(node.parent_id)
        parent_ref = (
            {"type": "page_id", "page_id": _hyphenated(node.parent_id)}
            if parent is not None and parent.is_page
            else {"type": "block_id", "block_id": _hyphenated(node.parent_id)}
        )
        if node.is_page:
            content = {"title": node.title or ""}
        else:
            content = {"rich_text": [_run(node.text)] if node.text else [], "color": "default"}
        return {
            "object": "block",
            "id": _hyphenated(node.node_id),
            "parent": parent_ref,
            "created_time": _minute(node.created_time),
            "created_by": {"object": "user", "id": _hyphenated(node.created_by)},
            "has_children": bool(node.children),
            "in_trash": False,
            "type": node.kind,
            node.kind: content,
        }

    @staticmethod
    def _list(results: list, cursor: str | None, kind: str) -> httpx.Response:
        return FakeNotion._json(
            200,
            {
                "object": "list",
                "results": results,
                "next_cursor": cursor,
                "has_more": cursor is not None,
                "type": kind,
                kind: {},
            },
        )

    def _search(self, parsed) -> httpx.Response:
        if self._search_mode == "unavailable":
            return self._plain_error(503)
        start = 0
        cursor = parsed.get("start_cursor") if isinstance(parsed, Mapping) else None
        if cursor is not None:
            start = int(cursor)
            if self._search_mode == "partial":
                return self._plain_error(500)
        pages = [node for node in self._nodes.values() if node.is_page]
        size = min(self._search_page_size, int(parsed.get("page_size", 100)))
        chunk = pages[start : start + size]
        following = str(start + size) if start + size < len(pages) else None
        return self._list(
            [self._page_object(node) for node in chunk], following, "page_or_data_source"
        )

    def _counted_busy(self, page_id: str, *, page_request: bool) -> bool:
        limit = self._page_read_limits.get(page_id)
        if limit is None:
            return False
        if page_request:
            self._page_reads[page_id] = self._page_reads.get(page_id, 0) + 1
        return self._page_reads.get(page_id, 0) > limit

    def _retrieve(self, target: str | None) -> httpx.Response:
        node = self._nodes.get(target) if target else None
        if node is None or not node.is_page:
            return self._plain_error(404)
        if self._counted_busy(target, page_request=True):
            return self._plain_error(503)
        if not node.readable:
            return self._plain_error(403)
        return self._json(200, self._page_object(node))

    def _children(self, target: str | None, request: httpx.Request) -> httpx.Response:
        node = self._nodes.get(target) if target else None
        if node is None:
            return self._plain_error(404)
        if self._counted_busy(target, page_request=False):
            return self._plain_error(503)
        if target in self._busy_after_create and target in self._created_under:
            return self._plain_error(503)
        if not node.readable:
            return self._plain_error(403)
        start = int(request.url.params.get("start_cursor", "0"))
        size = min(PAGE_SIZE_MAX, int(request.url.params.get("page_size", "100")))
        chunk = node.children[start : start + size]
        following = str(start + size) if start + size < len(node.children) else None
        return self._list([self._block_object(self._nodes[i]) for i in chunk], following, "block")

    # -- create -----------------------------------------------------------------------------

    @staticmethod
    def _hash_of(parsed: Mapping) -> str | None:
        try:
            return content_hash(
                {"properties": parsed.get("properties"), "children": parsed.get("children")}
            )
        except (TypeError, ValueError):
            return None

    def _create(self, bot: _Bot | None, parsed, created_hash, answer) -> httpx.Response:
        parent_ref = parsed.get("parent") if isinstance(parsed, Mapping) else None
        parent_id = (
            normalise_id(parent_ref.get("page_id")) if isinstance(parent_ref, Mapping) else None
        )
        parent = self._nodes.get(parent_id) if parent_id else None
        if parent_id is not None:
            self._created_under.add(parent_id)
        scripted = self._next_answer("pages.create", parent_id) if answer is None else answer
        if scripted is not None and scripted.kind == ERROR:
            return self._error(scripted)
        if bot is None:
            return self._plain_error(401)
        if parent is None or not parent.is_page:
            return self._plain_error(404)
        if not parent.readable:
            return self._plain_error(403)
        expected = self._expected_hash.get(parent_id, self._expected_hash.get(None))
        if created_hash is None or (expected is not None and expected != created_hash):
            return self._plain_error(400)
        node = self._materialise(bot, parent_id, parsed)
        return self._after_create(node, scripted)

    def _materialise(self, bot: _Bot, parent_id: str, parsed: Mapping) -> _Node:
        title = _text_of(parsed["properties"].get("title"))
        page_id = self.add_page(title=title or None, parent_id=parent_id, created_by=bot.bot_id)
        self._add_tree(page_id, parsed["children"], bot.bot_id)
        return self._nodes[page_id]

    def _add_tree(self, parent_id: str, blocks: list, creator: str) -> None:
        for block in blocks:
            kind = block.get("type", "paragraph")
            content = block.get(kind, {})
            block_id = self.add_block(parent_id, kind, text=_text_of(content.get("rich_text")))
            self._nodes[block_id].created_by = creator
            self._add_tree(block_id, content.get("children", []), creator)

    def _after_create(self, node: _Node, scripted: Answer | None) -> httpx.Response:
        if scripted is None:
            return self._json(200, self._page_object(node))
        if scripted.kind == SAVED_BUSY:
            additional = {
                "retry_guidance": "Read the object again to confirm the saved change.",
                "committed_resource_id": _hyphenated(node.node_id),
            }
            return self._plain_error(503, additional)
        if scripted.kind == TIMEOUT_AFTER_SUCCESS:
            raise httpx.ReadTimeout("synthetic timeout after success")
        if scripted.kind == LOST_AFTER_SUCCESS:
            raise httpx.RemoteProtocolError("synthetic lost response")
        return self._json(200, self._page_object(node))
