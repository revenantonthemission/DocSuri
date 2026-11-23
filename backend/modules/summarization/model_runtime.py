"""The production model runtime and the real assistance executor (U8 plan Step 21; A7,
BR6.11, BR7.7, P2, P3; performance-design § 3.3).

`SharedModelRuntime` is the client of the one shared model runtime production runs as a
system launch job (`http://127.0.0.1:11434`). It is not U1's owned synthetic supervisor
(`docsuri_ops.local_models.LocalModelRuntime`), which keeps its own root, port and
lifetime rules unchanged:

- **Model evidence (ModelEvidence).** A model is used only while the digest the runtime
  reports for it (`/api/tags`) equals the digest the release pins for it
  (`MODEL_PINS`). A model the release does not pin is never used. The digest is checked
  inside every request's own deadline (`verify`, bounded by the time the request has
  left); a mismatch raises `ModelEvidenceMismatch` (`model-evidence-mismatch`). Because
  the runtime checks each request itself (`verifies_each_request`), the embedder makes no
  second check of its own, so a query's embedding keeps its 2 s bound.
- **Residency, per model** (your decision of 2026-10-24, "Build the research executor").
  The search model is sent with `keep_alive: -1` and re-pinned by `pin_resident` (the
  workers' producer calls it every 60 seconds). The research model, qwen3:8b, is sent
  with 300 seconds (`u8_policy.research_model_keep_alive_seconds`), so it loads when a
  job needs it and unloads after five idle minutes; `pin_resident` refuses it.
- **One model job at a time.** The runtime holds a lane of one. `work` takes the lane
  first and only then starts its deadline; with `wait=0` it raises `LaneBusy` at once,
  so the model lane never queues behind another job. A work item nested inside the one
  this thread holds keeps the outer deadline. PaperAssistance's worker runs its executor
  on a thread of its own, so the lane's holder hands its work item to that one thread
  (`hand_over`) rather than letting it wait for a lane the holder already has.
- **The circuit breaker** (reliability-design § 10; L4-11). The runtime takes an optional
  reader of provider.models' state (`observed`, set by the composition or a tool after
  construction; without one nothing changes). `held()` reads it afresh: only `unavailable`
  holds, and a read that raises holds nothing. Every operation that sends a request
  (`tags`, `verify`, `infer`, `resident`, `pin_resident`) reads it once first and, when
  held, raises `ProviderHeld` before any client is built. A caller that has just read the
  state itself (search's breaker) wraps its call in `checked()`, so it costs one read.
- **Typed failures.** `RuntimeUnreachable`, `RuntimeRefused` (with its status) and
  `RequestTooLarge` are `ModelUnavailable`s, so PaperAssistance's handlers are unchanged;
  a timeout stays `TimeoutError`.
- **The network.** `network_transport()` is the one place a transport is built, so the
  test-wide guard replaces it; tests hand in a stand-in transport instead. The base
  address must be plain HTTP on `127.0.0.1`.

`ProductionAssistanceExecutor` is PaperAssistance's real executor: it wraps v1's
`GroundedLocalAssistant` (`qwen3:8b`) on this runtime, and runs only while the readiness
marker records the reviewed real-model evidence for assistance (BR7.7) and the runtime
reports the pinned digest. It has the shape of `OwnedExecutor`, so the dispatch takes it
in place of the synthetic executor; the composed realm keeps the synthetic one (BR7.1).
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from collections.abc import Callable
from contextlib import contextmanager
from urllib.parse import urlsplit

import httpx
from backend.modules.summarization.local_assistant import GroundedLocalAssistant
from backend.modules.summarization.local_result import encode_result
from backend.modules.summarization.worker import ExecutionRefused, PreparedExecution
from backend.u8_policy import PRODUCTION_OPERATIONS
from docsuri_ops.local_models import MODEL_PINS, ModelUnavailable

RUNTIME_URL = "http://127.0.0.1:11434"
GENERATION_MODEL = "qwen3:8b"
EMBEDDING_MODEL = "bge-m3:latest"
# Each model's residency (performance-design § 3.3): the search model stays loaded, the
# research model unloads after its idle seconds.
KEEP_ALIVE = {
    EMBEDDING_MODEL: PRODUCTION_OPERATIONS.search_model_keep_alive,
    GENERATION_MODEL: PRODUCTION_OPERATIONS.research_model_keep_alive_seconds,
}
MAX_REQUEST_BYTES = 16384
MAX_RESPONSE_BYTES = 4_000_000
TAGS_SECONDS = 3.0
# A request given no deadline of its own (an import's batch) is still bounded.
REQUEST_SECONDS = 60.0
WORK_SECONDS = 90.0
# How long an availability answer is kept (the model lane asks at most this often).
AVAILABILITY_SECONDS = 30.0
ENDPOINTS = {GENERATION_MODEL: "/api/chat", EMBEDDING_MODEL: "/api/embed"}


class ModelEvidenceMismatch(ModelUnavailable):
    """The runtime's digest for a model differs from the release's pin, or the release
    pins no such model (`model-evidence-mismatch`)."""

    reason = "model-evidence-mismatch"


class RuntimeUnreachable(ModelUnavailable):
    """The runtime did not take the connection (a stopped job, a reload)."""

    reason = "model-runtime-unreachable"


class ProviderHeld(RuntimeUnreachable):
    """provider.models is observed unavailable, so the request was never sent (the
    circuit breaker, reliability-design § 10; L4-11). A `RuntimeUnreachable`, so every
    handler of a runtime that did not take the connection treats it the same way."""

    reason = "provider-held"


class RuntimeRefused(ModelUnavailable):
    """The runtime answered with a status other than 200: a 5xx is the runtime's own
    trouble, a 4xx a request it would not take."""

    reason = "model-runtime-refused"

    def __init__(self, message: str, *, status: int):
        super().__init__(message)
        self.status = status


class RequestTooLarge(ModelUnavailable):
    """Our own request passed its byte bound; it was never sent."""

    reason = "model-request-too-large"


class LaneBusy(RuntimeError):
    """Another model job holds the lane, and the caller would not wait for it."""


def network_transport() -> httpx.BaseTransport:
    """The one place the runtime client builds its transport; reached only as a module
    attribute, so the test-wide guard replaces it for the whole run."""
    return httpx.HTTPTransport(retries=0)


def _require_loopback(base_url: str) -> str:
    address = urlsplit(base_url)
    if (
        address.scheme != "http"
        or address.hostname != "127.0.0.1"
        or address.port is None
        or address.path not in ("", "/")
        or address.query
        or address.username
    ):
        raise ValueError("the model runtime is plain HTTP on 127.0.0.1")
    return f"http://127.0.0.1:{address.port}"


class SharedModelRuntime:
    # The evidence check runs inside every request (`infer`), so a caller makes none of
    # its own (`LocalEmbeddings` reads this).
    verifies_each_request = True

    def __init__(self, *, base_url: str = RUNTIME_URL, pins: dict | None = None,
                 transport_factory: Callable[[], httpx.BaseTransport] | None = None,
                 clock: Callable[[], float] = time.monotonic,
                 observed: Callable[[], str] | None = None):
        self.base_url = _require_loopback(base_url)
        self.pins = dict(MODEL_PINS if pins is None else pins)
        self._transport_factory = transport_factory
        self._clock = clock
        # provider.models' state as ServiceOperations derives it; None reads nothing.
        self.observed = observed
        self._checked = threading.local()
        # Reentrant: one work item holds the lane across its section calls.
        self._lane = threading.RLock()
        self._held = threading.local()
        # The lane's work item handed to one other thread (`hand_over`): PaperAssistance's
        # worker runs its executor on a thread of its own.
        self._hand_lock = threading.Lock()
        self._hand: dict | None = None
        self.last_response: dict | None = None

    @contextmanager
    def hand_over(self):
        """While the lane's holder waits on work that runs on one thread of its own
        (PaperAssistance's worker runs the executor so), the first other thread that
        asks for the lane takes the holder's work item, with its deadline, instead of
        waiting for the lane; every further thread still finds the lane held."""
        deadline = getattr(self._held, "deadline", None)
        if deadline is None:
            raise ValueError("only the lane's holder hands its work item over")
        with self._hand_lock:
            if self._hand is not None:
                raise ValueError("the work item is already handed over")
            self._hand = {"deadline": deadline, "thread": None, "spent": False}
        try:
            yield deadline
        finally:
            with self._hand_lock:
                self._hand = None

    def _handed(self) -> float | None:
        """The handed work item's deadline, when this thread is (or becomes) the one
        thread it was handed to. The thread is held by its object, never its reusable
        identifier, and once its work item ends the hand-over is spent."""
        me = threading.current_thread()
        with self._hand_lock:
            hand = self._hand
            if hand is None or hand["spent"] or hand["thread"] not in (None, me):
                return None
            hand["thread"] = me
            return hand["deadline"]

    def _spend_hand(self) -> None:
        with self._hand_lock:
            if self._hand is not None and self._hand["thread"] is threading.current_thread():
                self._hand["spent"] = True

    @contextmanager
    def work(self, seconds: float = WORK_SECONDS, *, wait: float | None = None):
        """One model work item holds the lane of one for at most `seconds`, and yields
        its monotonic deadline. The lane is taken first (waiting at most `wait`, or
        `seconds` when no wait is given) and only then does the deadline start; with
        `wait=0` a held lane raises `LaneBusy` at once. Nested inside a work item this
        thread holds, it keeps the outer deadline."""
        if not 0 < seconds <= WORK_SECONDS:
            raise ValueError("work deadline exceeds finite allocation")
        if wait is not None and not 0 <= wait <= WORK_SECONDS:
            raise ValueError("lane wait outside its allocation")
        outer = getattr(self._held, "deadline", None)
        in_hand = getattr(self._held, "handed", False)
        base = (outer if in_hand else None) if outer is not None else self._handed()
        if base is not None:
            # The holder's work item, handed to this thread (and work nested in it): no
            # second lane is taken, and the handed deadline holds.
            self._held.deadline = min(base, self._clock() + seconds)
            self._held.handed = True
            try:
                yield self._held.deadline
            finally:
                self._held.deadline, self._held.handed = outer, in_hand
                if outer is None:
                    self._spend_hand()  # the handed work item itself has ended
            return
        timeout = seconds if wait is None else wait
        taken = self._lane.acquire(blocking=False) if timeout == 0 else self._lane.acquire(
            timeout=timeout)
        if not taken:
            raise LaneBusy("another model job holds the lane")
        deadline = self._clock() + seconds if outer is None else min(
            outer, self._clock() + seconds)
        self._held.deadline = deadline
        try:
            yield deadline
        finally:
            self._held.deadline = outer
            self._lane.release()

    # --- the circuit breaker ---------------------------------------------------------

    def held(self) -> bool:
        """Whether provider.models is observed `unavailable`, read afresh. Every other
        state, no reader, and a read that raises (logged as one event) hold nothing."""
        reader = self.observed
        if reader is None:
            return False
        try:
            return reader() == "unavailable"
        except Exception as error:  # noqa: BLE001 - an unreadable state shows no outage
            from backend.log_events import log_exception

            log_exception("models", "breaker.state-unreadable", error,
                          reason="provider.models")
            return False

    @contextmanager
    def checked(self):
        """A caller that has just read provider.models' state itself marks its own call,
        on its own thread, so the operations inside it read the state no second time."""
        outer = getattr(self._checked, "on", False)
        self._checked.on = True
        try:
            yield
        finally:
            self._checked.on = outer

    def _require_serving(self) -> None:
        if not getattr(self._checked, "on", False) and self.held():
            raise ProviderHeld("provider.models is observed unavailable")

    # --- transport -----------------------------------------------------------------

    def _client(self, timeout: float) -> httpx.Client:
        transport = (self._transport_factory or network_transport)()
        return httpx.Client(transport=transport, base_url=self.base_url, trust_env=False,
                            timeout=timeout, follow_redirects=False)

    def _call(self, path: str, body: dict | None, timeout: float) -> dict:
        if timeout <= 0:
            raise TimeoutError("model deadline reached")
        try:
            with self._client(timeout) as client:
                response = (client.get(path) if body is None else client.post(path, json=body))
        except httpx.TimeoutException as error:
            raise TimeoutError("model runtime did not answer in time") from error
        except httpx.HTTPError as error:
            raise RuntimeUnreachable("model runtime unreachable") from error
        if response.status_code != 200:
            raise RuntimeRefused("model runtime answer refused", status=response.status_code)
        if len(response.content) > MAX_RESPONSE_BYTES:
            raise ModelUnavailable("model runtime answer exceeds its bound")
        try:
            value = response.json()
        except ValueError as error:
            raise ModelUnavailable("model runtime answer is not JSON") from error
        if not isinstance(value, dict) or value.get("error"):
            raise ModelUnavailable("model runtime answer refused")
        return value

    # --- model evidence --------------------------------------------------------------

    def tags(self, *, timeout: float = TAGS_SECONDS) -> dict[str, str]:
        """Each model the runtime holds, by name, with the digest it reports."""
        self._require_serving()
        return self._tags(timeout)

    def _tags(self, timeout: float) -> dict[str, str]:
        models = self._call("/api/tags", None, min(TAGS_SECONDS, timeout)).get("models")
        if not isinstance(models, list):
            raise ModelUnavailable("model runtime tags malformed")
        return {
            item["name"]: item["digest"]
            for item in models
            if isinstance(item, dict) and isinstance(item.get("name"), str)
            and isinstance(item.get("digest"), str)
        }

    def verify(self, model: str, *, timeout: float = TAGS_SECONDS) -> str:
        """The pinned digest, once the runtime reports exactly it; otherwise refused. The
        tags answer is bounded by `timeout` (at most `TAGS_SECONDS`)."""
        self._require_serving()
        return self._verify(model, timeout)

    def _verify(self, model: str, timeout: float) -> str:
        """`verify` without the breaker's read, for an operation that has made it."""
        pin = self.pins.get(model)
        if pin is None:
            raise ModelEvidenceMismatch("the release pins no such model")
        if self._tags(timeout).get(model) != pin:
            raise ModelEvidenceMismatch("the runtime's digest differs from the pin")
        return pin

    # --- requests --------------------------------------------------------------------

    def infer(self, *, model: str, body: dict, work_deadline: float | None = None,
              timeout: float | None = None) -> dict:
        """One model request: the lane, the evidence check inside the request's own
        deadline, then the request with the model's keep-alive. `work_deadline` is
        monotonic; `timeout` bounds this call."""
        if model not in ENDPOINTS or body.get("model") != model:
            raise ModelUnavailable("request model outside policy")
        request = {**body, "keep_alive": KEEP_ALIVE[model]}
        if len(json.dumps(request).encode()) > MAX_REQUEST_BYTES:
            raise RequestTooLarge("model request allocation exceeded")
        now = self._clock()
        remaining = min(
            work_deadline - now if work_deadline is not None else REQUEST_SECONDS,
            timeout if timeout is not None else REQUEST_SECONDS,
        )
        if remaining <= 0:
            raise TimeoutError("model deadline reached")
        # The breaker, read once for the whole operation, before the lane and any client.
        self._require_serving()
        # Inside a work item handed to this thread, the holder's lane already covers it.
        in_hand = getattr(self._held, "handed", False)
        if not in_hand and not self._lane.acquire(timeout=remaining):
            raise TimeoutError("another model job holds the lane")
        try:
            self._verify(model, min(TAGS_SECONDS, remaining - (self._clock() - now)))
            left = remaining - (self._clock() - now)
            response = self._call(ENDPOINTS[model], request, left)
        finally:
            if not in_hand:
                self._lane.release()
        if response.get("model") != model:
            raise ModelUnavailable("model response identity mismatch")
        self.last_response = response
        return response

    def resident(self, *, timeout: float = TAGS_SECONDS) -> dict[str, int]:
        """Each loaded model's resident size in bytes (`/api/ps`), for the research
        review's memory reading (U8 plan Step 37)."""
        self._require_serving()
        models = self._call("/api/ps", None, min(TAGS_SECONDS, timeout)).get("models")
        if not isinstance(models, list):
            raise ModelUnavailable("model runtime process list malformed")
        return {item["name"]: int(item["size"]) for item in models
                if isinstance(item, dict) and isinstance(item.get("name"), str)
                and isinstance(item.get("size"), int)}

    def pin_resident(self, model: str = EMBEDDING_MODEL) -> None:
        """Keep the search model loaded (`keep_alive: -1`), after its evidence check. The
        research model is never pinned: it unloads after its idle seconds."""
        if model != EMBEDDING_MODEL:
            raise ValueError("only the search model is kept resident")
        self._require_serving()
        self._verify(model, TAGS_SECONDS)
        body = {"model": model, "input": [], "keep_alive": KEEP_ALIVE[model]}
        self._call(ENDPOINTS[model], body, TAGS_SECONDS)


class ProductionAssistanceExecutor:
    """PaperAssistance's real executor on the shared runtime (BR7.7)."""

    def __init__(self, runtime: SharedModelRuntime, *, ready: Callable[[], bool],
                 clock: Callable[[], float] = time.monotonic,
                 cache_seconds: float = AVAILABILITY_SECONDS):
        self.runtime, self._ready = runtime, ready
        self._clock, self._cache_seconds = clock, cache_seconds
        self._lock = threading.Lock()
        self._active = False
        self._answer: tuple[float, bool] | None = None

    def available(self) -> bool:
        """The marker lists assistance and the runtime reports the pin; the answer is
        kept for 30 seconds by the injected clock, so the lane never polls the runtime.
        The breaker is asked first and afresh, outside the kept answer: while
        provider.models is observed unavailable the answer is False with no request, so
        the lane claims nothing (L4-11)."""
        held = getattr(self.runtime, "held", None)
        if callable(held) and held():
            return False
        now = self._clock()
        if self._answer is not None and now - self._answer[0] < self._cache_seconds:
            return self._answer[1]
        answer = False
        if self._ready():
            try:
                self.runtime.verify(GENERATION_MODEL)
                answer = True
            except (ModelUnavailable, TimeoutError):
                answer = False
        self._answer = (now, answer)
        return answer

    def run(self, bound_input: dict, absolute_monotonic_deadline: float) -> PreparedExecution:
        with self._lock:
            self._active = True
        try:
            if not self._ready():
                raise ExecutionRefused("dependency-unavailable")
            try:
                self.runtime.verify(GENERATION_MODEL)
            except (ModelUnavailable, TimeoutError):
                raise ExecutionRefused("dependency-unavailable") from None
            return self._execute(bound_input, absolute_monotonic_deadline)
        finally:
            with self._lock:
                self._active = False

    def _execute(self, bound_input: dict, deadline: float) -> PreparedExecution:
        operation = (bound_input.get("input") or {}).get("operation")
        sections = bound_input.get("sections")
        if operation not in ("summary", "translation") or not isinstance(sections, list) or not (
            1 <= len(sections) <= 8
        ):
            raise ExecutionRefused("invalid-source")
        chunks = []
        for section in sections:
            text, heading, anchor = (section.get(key) for key in ("text", "heading", "anchor"))
            if not all(isinstance(value, str) and value for value in (text, heading, anchor)):
                raise ExecutionRefused("invalid-source")
            chunks.append({"text": text, "section": heading, "anchor": anchor,
                           "textHash": hashlib.sha256(text.encode()).hexdigest()})
        if time.monotonic() >= deadline:
            raise ExecutionRefused("deadline-exceeded")
        task, language = ("summary", "en") if operation == "summary" else ("translate", "ko")
        try:
            result = GroundedLocalAssistant(self.runtime).generate(
                chunks, task=task, language=language)
        except (TimeoutError, LaneBusy):
            raise ExecutionRefused("deadline-exceeded") from None
        except (ModelUnavailable, ValueError):
            raise ExecutionRefused("insufficient-result") from None
        first = sections[0]
        content = encode_result(
            sections=[{"sectionId": first.get("sectionId") or first["anchor"],
                       "heading": first["heading"], "text": result["text"],
                       "anchor": first["anchor"]}],
            citations=result["citations"],
            definitions=[item for section in result["sections"]
                         for item in section.get("definitions", [])],
        )
        provenance = {
            "provider": "local-model-runtime", "model": result["model"],
            "modelDigest": self.runtime.pins[GENERATION_MODEL],
            "requestHash": result["requestHash"], "sourceAnchors": result["sourceAnchors"],
            "operation": operation,
        }
        return PreparedExecution(content, {"coverage": "partial", "sections": len(sections)},
                                 provenance)

    def abort_owned(self) -> None:
        """A request in flight ends at its own deadline; nothing else is owned."""
        return None

    def stopped(self) -> bool:
        with self._lock:
            return not self._active
