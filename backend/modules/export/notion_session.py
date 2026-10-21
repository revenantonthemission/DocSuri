"""One Notion operation at a time, with one client per operation (security design §6).

- `network_transport()` is the single place that builds the network transport. Code
  reaches it only as a module attribute, so a test can replace it once for the run.
- `GuardedTransport` pins every request to `https://api.notion.com:443`, allows only the
  request paths U6 uses with validated identifiers, bounds each request's time, streams
  every body under the 2,000,000-byte cap, treats a redirect as an unexpected answer and
  adds no retries.
- `InteractiveGate` caps browser-driven operations at two per process and one per
  connection, refusing at once beyond either cap (D15).
- `NotionSession.run` opens the token, builds both clients, paces every request on the
  target's connection, runs the work under the operation's wall-clock budget and reduces
  every ordinary exception to a fixed `Verdict` (D10, D11). Cancellation,
  `KeyboardInterrupt` and `SystemExit` pass through.

No exception object is stored, logged or returned, and nothing keeps the token after
the operation: the value, the SDK client and its `Authorization` header are dropped
together when the HTTP client closes.
"""

import asyncio
import contextlib
import logging
import re
import threading
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID

import httpx
import notion_client

from backend.u6_policy import ExportPolicy

from .classification import (
    CAUSE_INTERACTIVE_CAP,
    COULD_NOT_CHECK,
    OK,
    BudgetSpent,
    NotConnected,
    PaceUnavailable,
    Verdict,
    classify_read,
)

NOTION_SCHEME = "https"
NOTION_HOST = "api.notion.com"
NOTION_PORT = 443
NOTION_VERSION = "2026-03-11"
SDK_LOGGER_NAME = "docsuri.export.notion_sdk"

SDK_LOGGER = logging.getLogger(SDK_LOGGER_NAME)
SDK_LOGGER.addHandler(logging.NullHandler())
SDK_LOGGER.propagate = False
SDK_LOGGER.setLevel(logging.WARNING)

# The only request paths U6 sends (security design §6.3): identifiers are 32 lowercase hex.
_ID = r"[0-9a-f]{32}"
ALLOWED_PATHS = (
    ("GET", re.compile(r"/v1/users/me")),
    ("POST", re.compile(r"/v1/search")),
    ("POST", re.compile(r"/v1/pages")),
    ("GET", re.compile(rf"/v1/pages/{_ID}")),
    ("GET", re.compile(rf"/v1/blocks/{_ID}/children")),
)
_ALLOWED_QUERY = frozenset({"page_size", "start_cursor"})


class RequestRefused(httpx.TransportError):
    """A request that the guard refused before it left: wrong origin, path or identifier."""


class UnexpectedResponse(httpx.TransportError):
    """A redirect, or a body in an encoding the guard did not ask for."""


class ResponseTooLarge(httpx.TransportError):
    """A response body past the cap, declared or streamed."""


def network_transport() -> httpx.AsyncBaseTransport:
    """The network transport: TLS verified, no environment proxies, no retries.

    Called once per operation through this module attribute; tests replace it with a
    stub that fails, so no test can reach the network.
    """
    return httpx.AsyncHTTPTransport(verify=True, trust_env=False, retries=0)


def _path_allowed(request: httpx.Request) -> bool:
    path = request.url.path
    if any(name not in _ALLOWED_QUERY for name in request.url.params):
        return False
    return any(
        request.method == method and pattern.fullmatch(path) for method, pattern in ALLOWED_PATHS
    )


class _CappedStream(httpx.AsyncByteStream):
    def __init__(self, body: bytes):
        self._body = body

    async def __aiter__(self):
        yield self._body


class GuardedTransport(httpx.AsyncBaseTransport):
    """Wraps the network transport or the fake Notion behind the same guards (§6.2)."""

    def __init__(
        self,
        inner: httpx.AsyncBaseTransport,
        *,
        cap_bytes: int,
        request_timeout: float,
        before_request: Callable[[], Awaitable[None]] | None = None,
    ):
        if not isinstance(inner, httpx.AsyncBaseTransport):
            raise TypeError("an HTTPX asynchronous transport is required")
        if type(cap_bytes) is not int or cap_bytes <= 0:
            raise ValueError("a positive response cap is required")
        if not request_timeout > 0:
            raise ValueError("a positive request timeout is required")
        self._inner = inner
        self._cap = cap_bytes
        self._timeout = request_timeout
        self._before_request = before_request

    def _check(self, request: httpx.Request) -> None:
        url = request.url
        port = url.port if url.port is not None else NOTION_PORT
        if (
            url.scheme != NOTION_SCHEME
            or url.host != NOTION_HOST
            or port != NOTION_PORT
            or url.userinfo
        ):
            raise RequestRefused("origin")
        if not _path_allowed(request):
            raise RequestRefused("path")

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self._check(request)
        # Ask for an identity body, so the cap measures exactly what is decoded.
        request.headers["Accept-Encoding"] = "identity"
        if self._before_request is not None:
            await self._before_request()
        body = None
        try:
            async with asyncio.timeout(self._timeout):
                response = await self._inner.handle_async_request(request)
                body = await self._read_capped(response)
        except TimeoutError:
            pass  # raised below, once this block has ended, so nothing is chained
        if body is None:
            raise httpx.ReadTimeout("request timeout", request=request)
        return httpx.Response(
            response.status_code,
            headers=response.headers,
            stream=_CappedStream(body),
            extensions=response.extensions,
        )

    async def _read_capped(self, response: httpx.Response) -> bytes:
        try:
            if 300 <= response.status_code < 400:
                raise UnexpectedResponse("redirect")
            encoding = response.headers.get("content-encoding", "identity").strip().lower()
            if encoding not in ("", "identity"):
                raise UnexpectedResponse("encoding")
            declared = response.headers.get("content-length")
            if declared is not None and (not declared.isdigit() or int(declared) > self._cap):
                raise ResponseTooLarge("declared")
            chunks, total = [], 0
            async for chunk in response.stream:
                total += len(chunk)
                if total > self._cap:
                    raise ResponseTooLarge("streamed")
                chunks.append(chunk)
            return b"".join(chunks)
        finally:
            await response.aclose()

    async def aclose(self) -> None:
        await self._inner.aclose()


class InteractiveGate:
    """At most N interactive operations per process and M per connection (D15).

    Thread-safe, because browser requests run in the threadpool, each operation in its
    own event loop. A refused operation never waits.
    """

    def __init__(self, per_process: int, per_connection: int):
        if min(per_process, per_connection) < 1 or per_connection > per_process:
            raise ValueError("interactive caps must be positive, per connection within process")
        self._per_process = per_process
        self._per_connection = per_connection
        self._lock = threading.Lock()
        self._held: dict[UUID, int] = {}

    @classmethod
    def for_policy(cls, policy: ExportPolicy) -> "InteractiveGate":
        return cls(policy.interactive_per_process, policy.interactive_per_connection)

    @property
    def held(self) -> int:
        with self._lock:
            return sum(self._held.values())

    def try_acquire(self, key: UUID) -> bool:
        if not isinstance(key, UUID):
            raise TypeError("the gate key is a connection id")
        with self._lock:
            if sum(self._held.values()) >= self._per_process:
                return False
            if self._held.get(key, 0) >= self._per_connection:
                return False
            self._held[key] = self._held.get(key, 0) + 1
            return True

    def release(self, key: UUID) -> None:
        with self._lock:
            count = self._held.get(key, 0)
            if count <= 1:
                self._held.pop(key, None)
            else:
                self._held[key] = count - 1


@dataclass(frozen=True)
class StoredConnection:
    """The owner's stored token, opened inside the reduced region (R-14)."""

    account_id: UUID
    connection_id: UUID

    def __post_init__(self):
        if not isinstance(self.account_id, UUID) or not isinstance(self.connection_id, UUID):
            raise TypeError("account and connection ids are required")


@dataclass(frozen=True)
class CandidateToken:
    """A token the caller holds for one check, with the connection row it is checked for:
    the pending row on a first configure, the owner's row on a replace (R-14). The value
    never appears in a representation."""

    connection_id: UUID
    value: str = field(repr=False)

    def __post_init__(self):
        if not isinstance(self.connection_id, UUID):
            raise TypeError("a connection id is required")
        if not isinstance(self.value, str) or not self.value:
            raise ValueError("a candidate token is required")


@dataclass(frozen=True)
class Opened:
    """What opening a stored envelope saw: the revision the operation opened (D16) and
    the connection state (BR1.6)."""

    revision: int
    state: str


@dataclass(frozen=True)
class SessionResult:
    """A fixed category, the work's value when it succeeded, and the reduced verdict."""

    category: str
    value: Any = None
    verdict: Verdict | None = None
    opened: Opened | None = None

    @property
    def ok(self) -> bool:
        return self.category == OK

    @property
    def cause(self) -> str | None:
        return self.verdict.cause if self.verdict is not None else None


class SessionStore(Protocol):
    def reserve_pace_slot(self, connection_id: UUID, *, remaining_seconds: float): ...

    def open_token_envelope(self, account_id: UUID, connection_id: UUID): ...


class TokenOpener(Protocol):
    def open(
        self, envelope: bytes, *, account_id: UUID, connection_id: UUID, revision: int
    ) -> str: ...


class Pacer:
    """Reserves a pace slot on the target's connection before every request (D6, §9.2)
    and waits for it outside any transaction. A slot past the remaining budget ends the
    operation with that budget's outcome; the slot stays used."""

    def __init__(self, store: SessionStore, connection_id: UUID, deadline: float, prepaid: int):
        self._store = store
        self._connection_id = connection_id
        self._deadline = deadline
        self._prepaid = prepaid
        self.reservations = 0

    def remaining(self) -> float:
        return max(0.0, self._deadline - asyncio.get_running_loop().time())

    async def wait_for_slot(self, *, at_least: float = 0.0) -> None:
        """Reserve the next slot, then wait for the later of it and `at_least` seconds
        (a stated wait). The next request then goes without another reservation."""
        slot = await asyncio.to_thread(
            self._store.reserve_pace_slot,
            self._connection_id,
            remaining_seconds=self.remaining(),
        )
        self.reservations += 1
        if slot is None:
            raise PaceUnavailable()
        wait = max(slot.wait_seconds, at_least)
        if not slot.within_budget or wait >= self.remaining():
            raise BudgetSpent()
        await asyncio.sleep(wait)
        self._prepaid += 1

    async def before_request(self) -> None:
        if self._prepaid > 0:
            self._prepaid -= 1
            return
        await self.wait_for_slot()
        self._prepaid -= 1


@dataclass(frozen=True)
class OperationContext:
    """What a unit of work may use besides the SDK client: the pacer and its clock."""

    pacer: Pacer

    def remaining(self) -> float:
        return self.pacer.remaining()


Work = Callable[[notion_client.AsyncClient, OperationContext], Awaitable[Any]]
Classifier = Callable[[BaseException], Verdict]


class NotionSession:
    """Runs one Notion operation per call, each with its own clients (D10)."""

    def __init__(
        self,
        *,
        store: SessionStore,
        vault: TokenOpener,
        policy: ExportPolicy,
        gate: InteractiveGate | None = None,
        transport_factory: Callable[[], httpx.AsyncBaseTransport] | None = None,
    ):
        if not isinstance(policy, ExportPolicy):
            raise TypeError("an ExportPolicy is required")
        self._store = store
        self._vault = vault
        self._policy = policy
        self.gate = gate if gate is not None else InteractiveGate.for_policy(policy)
        self._transport_factory = transport_factory

    @property
    def policy(self) -> ExportPolicy:
        return self._policy

    def _transport(self) -> httpx.AsyncBaseTransport:
        if self._transport_factory is not None:
            return self._transport_factory()
        # A module-global lookup at call time, so the test-wide guard replaces the source.
        return network_transport()

    async def run(
        self,
        target: StoredConnection | CandidateToken,
        budget: float,
        work: Work,
        *,
        gate_key: UUID | None = None,
        classify: Classifier = classify_read,
        request_timeout: float | None = None,
        prepaid_slots: int = 0,
    ) -> SessionResult:
        """Run `work(sdk, context)` as one operation under `budget` seconds.

        A browser-driven operation passes its connection id as `gate_key`; its slot is
        taken before anything else and released on success, error or cancellation. The
        lane passes no gate key. `prepaid_slots` counts pace slots the caller already
        reserved and waited for (the lane's write).
        """
        if not isinstance(target, (StoredConnection, CandidateToken)):
            raise TypeError("a stored connection or a candidate token is required")
        if not budget > 0:
            raise ValueError("a positive budget is required")
        if gate_key is not None and not self.gate.try_acquire(gate_key):
            refused = Verdict(COULD_NOT_CHECK, cause=CAUSE_INTERACTIVE_CAP)
            return SessionResult(COULD_NOT_CHECK, verdict=refused)
        try:
            return await self._operate(
                target, budget, work, classify, request_timeout, prepaid_slots
            )
        finally:
            if gate_key is not None:
                self.gate.release(gate_key)

    async def _open(self, target, opened_box: list) -> str:
        if isinstance(target, CandidateToken):
            return target.value
        row = await asyncio.to_thread(
            self._store.open_token_envelope, target.account_id, target.connection_id
        )
        if row is None:
            raise NotConnected()
        opened_box.append(Opened(row["revision"], row["state"]))
        return await asyncio.to_thread(
            self._vault.open,
            row["sealed_token"],
            account_id=target.account_id,
            connection_id=target.connection_id,
            revision=row["revision"],
        )

    async def _operate(self, target, budget, work, classify, request_timeout, prepaid):
        loop = asyncio.get_running_loop()
        deadline = loop.time() + budget
        # One request keeps its own timeout (NFR4.10); the budget bounds the operation.
        per_request = request_timeout or self._policy.read_timeout_seconds
        opened_box: list[Opened] = []
        http = None
        value = None
        verdict = None
        try:
            async with asyncio.timeout(budget):
                token = await self._open(target, opened_box)
                pacer = Pacer(self._store, target.connection_id, deadline, prepaid)
                http = httpx.AsyncClient(
                    transport=GuardedTransport(
                        self._transport(),
                        cap_bytes=self._policy.response_cap_bytes,
                        request_timeout=per_request,
                        before_request=pacer.before_request,
                    ),
                    follow_redirects=False,
                    trust_env=False,
                )
                sdk = notion_client.AsyncClient(
                    client=http,
                    auth=token,
                    notion_version=NOTION_VERSION,
                    retry=False,
                    timeout_ms=max(1, int(per_request * 1000)),
                    logger=SDK_LOGGER,
                    log_level=logging.WARNING,
                )
                token = None
                value = await work(sdk, OperationContext(pacer))
                sdk = None
        except Exception as error:  # reduced to a fixed verdict; the object is dropped
            verdict = classify(error)
        finally:
            if http is not None:
                # Closing drops the client's headers, and the token with them. A failure
                # to close cannot change an outcome already reached, so it is not raised.
                with contextlib.suppress(Exception):
                    await http.aclose()
        opened = opened_box[0] if opened_box else None
        if verdict is not None:
            return SessionResult(verdict.category, verdict=verdict, opened=opened)
        return SessionResult(OK, value=value, opened=opened)
