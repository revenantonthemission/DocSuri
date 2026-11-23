"""Provider probes and failure counts at U8's composition seams (U8 plan Step 56; L1-11,
"Active free checks"; L1-12, "At the U8 seams").

- **The probes.** On the production profile only, each observation of a configured
  provider makes one request that carries no credential: Google's and ORCID's discovery
  documents pass on a 200; Resend's `/emails` and Notion's `/v1/users/me` pass on any
  answer below 500, 401 included, with no `Authorization` header. Notion's goes through
  U6's `GuardedTransport` (its origin and path pins), with U6's response cap and a 5.0 s
  request timeout. A synthetic profile builds no probe.
- **The factory.** Each probe takes its base factory: a client factory for Google,
  ORCID and Resend, a transport factory for Notion. Production hands each probe its
  adapter's one guarded network builder, looked up as a module attribute at call time
  (`production_probes`), so no fifth network builder exists and no probe is counted.
- **The deadline.** One whole-probe deadline, `PROBE_SECONDS`. `run_bounded` builds the
  client or transport on the calling thread (a factory that raises fails before any
  wait), runs the request on a daemon thread, which sets `done` when it ends, and calls
  the injected `waiter(done, POLL_SECONDS)` while `done` is unset and the injected
  monotonic clock has moved less than the deadline. An answer found once the clock has
  moved the deadline or more counts as no answer. The request also carries httpx's own
  timeout of the same length, so an abandoned call ends by itself.
- **The counts.** `counting_client_factory` adds one response hook to each client its
  base builds; `counting_transport_factory` returns a new delegating transport over
  `base()` on every call. Every answered call adds 1 to its kind's total; an answered
  4xx (a refusal, or a 429 over the limit) also adds 1 to its errors. A transport error,
  a guard refusal or `NetworkRefused` adds to neither. Each adds to its process's
  `u8_counts` writer, under `provider.google`, `provider.orcid`, `provider.resend` or
  `provider.notion`.
"""

from __future__ import annotations

import asyncio
import dataclasses
import threading
import time
from collections.abc import Callable

import httpx

PROBE_SECONDS = 5.0
REPIN_SECONDS = 10.0
POLL_SECONDS = 0.1

# Each provider's one uncredentialed request, and how its answer passes.
DISCOVERY, BELOW_500 = "discovery", "below-500"
PROBE_REQUESTS = {
    "provider.google": ("https://accounts.google.com/.well-known/openid-configuration",
                        DISCOVERY),
    "provider.orcid": ("https://orcid.org/.well-known/openid-configuration", DISCOVERY),
    "provider.resend": ("https://api.resend.com/emails", BELOW_500),
    "provider.notion": ("https://api.notion.com/v1/users/me", BELOW_500),
}
COUNTED_KINDS = tuple(PROBE_REQUESTS)

Clock = Callable[[], float]
Waiter = Callable[[threading.Event, float], object]


class ProbeDeadline(TimeoutError):
    """No answer within the deadline, or an answer found past it."""


def _wait(done: threading.Event, step: float) -> object:
    return done.wait(step)


def run_bounded(build: Callable[[], object], work: Callable[[object], object], *,
                seconds: float, clock: Clock | None = None,
                waiter: Waiter | None = None) -> object:
    """`work(build())` under one whole deadline of `seconds` on the injected clock.
    `build` runs on the calling thread; `work` on a daemon thread. Raises
    `ProbeDeadline`, or what `build` or `work` raised."""
    clock = clock or time.monotonic
    waiter = waiter or _wait
    built = build()
    done, box = threading.Event(), {}

    def target() -> None:
        try:
            box["value"] = work(built)
        except BaseException as error:  # noqa: BLE001 - handed to the calling thread
            box["error"] = error
        finally:
            done.set()

    started = clock()
    threading.Thread(target=target, name="u8-provider-probe", daemon=True).start()
    while not done.is_set() and clock() - started < seconds:
        waiter(done, POLL_SECONDS)
    if clock() - started >= seconds or not done.is_set():
        raise ProbeDeadline("no answer within the deadline")
    if "error" in box:
        raise box["error"]
    return box["value"]


def _response_cap() -> int:
    from .u6_policy import ExportPolicy

    return next(item.default for item in dataclasses.fields(ExportPolicy)
                if item.name == "response_cap_bytes")


class ProviderProbe:
    """One provider's uncredentialed check; calling it answers whether it passed. Every
    failure (no answer within the deadline, a transport error, a guard refusal,
    `NetworkRefused`, a 5xx or a discovery document that does not answer 200) is False."""

    def __init__(self, capability: str, base_factory: Callable, *,
                 seconds: float = PROBE_SECONDS, clock: Clock | None = None,
                 waiter: Waiter | None = None):
        if capability not in PROBE_REQUESTS:
            raise ValueError("no probe for this capability")
        self.capability = capability
        self.url, self.rule = PROBE_REQUESTS[capability]
        self.base_factory = base_factory
        self.seconds, self.clock, self.waiter = seconds, clock, waiter

    def _client(self) -> httpx.AsyncClient:
        if self.capability == "provider.notion":
            from .modules.export.notion_session import GuardedTransport

            transport = GuardedTransport(self.base_factory(), cap_bytes=_response_cap(),
                                         request_timeout=self.seconds)
            return httpx.AsyncClient(transport=transport, follow_redirects=False,
                                     trust_env=False, timeout=self.seconds)
        return self.base_factory(timeout=self.seconds)

    def _request(self, client: httpx.AsyncClient) -> int:
        async def fetch() -> int:
            async with client:
                response = await client.get(self.url)
                return response.status_code

        return asyncio.run(fetch())

    def passed(self, status: int) -> bool:
        return status == 200 if self.rule == DISCOVERY else status < 500

    def __call__(self) -> bool:
        try:
            status = run_bounded(self._client, self._request, seconds=self.seconds,
                                 clock=self.clock, waiter=self.waiter)
        except Exception:  # noqa: BLE001 - every failed probe reads unavailable
            return False
        return self.passed(int(status))


# --- production's base factories, each looked up as a module attribute at call time -----


def identity_client(**options) -> httpx.AsyncClient:
    from .modules.accounts.integrations import identity_providers

    return identity_providers.network_client(**options)


def resend_client(**options) -> httpx.AsyncClient:
    from .modules.accounts.integrations import digest_email

    return digest_email.network_client(**options)


def notion_transport() -> httpx.AsyncBaseTransport:
    from .modules.export import notion_session

    return notion_session.network_transport()


BASE_FACTORIES = {
    "provider.google": identity_client, "provider.orcid": identity_client,
    "provider.resend": resend_client, "provider.notion": notion_transport,
}


def production_probe(capability: str, **options) -> ProviderProbe:
    """The probe `worker_producers` gives a production profile's provider producer."""
    return ProviderProbe(capability, BASE_FACTORIES[capability], **options)


# --- the counting layers ----------------------------------------------------------------


def _record(counts, kind: str, status: int) -> None:
    counts.record(kind, failed=400 <= status < 500)


def counting_client_factory(base: Callable[..., httpx.AsyncClient], kind: str,
                            counts) -> Callable[..., httpx.AsyncClient]:
    """`base`'s clients, each with one response hook that counts its answers; `base`
    unchanged when no writer is given."""
    if counts is None:
        return base

    def factory(**options) -> httpx.AsyncClient:
        client = base(**options)

        async def count(response: httpx.Response) -> None:
            _record(counts, kind, response.status_code)

        hooks = client.event_hooks
        client.event_hooks = {**hooks, "response": [*hooks.get("response", []), count]}
        return client

    return factory


class CountingTransport(httpx.AsyncBaseTransport):
    """Delegates every request to its inner transport and counts each answer."""

    def __init__(self, inner: httpx.AsyncBaseTransport, kind: str, counts):
        self._inner, self._kind, self._counts = inner, kind, counts

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        response = await self._inner.handle_async_request(request)
        _record(self._counts, self._kind, response.status_code)
        return response

    async def aclose(self) -> None:
        await self._inner.aclose()


def counting_transport_factory(base: Callable[[], httpx.AsyncBaseTransport], kind: str,
                               counts) -> Callable[[], httpx.AsyncBaseTransport]:
    """A new counting transport over `base()` on every call; `base` unchanged when no
    writer is given."""
    if counts is None:
        return base

    def factory() -> httpx.AsyncBaseTransport:
        return CountingTransport(base(), kind, counts)

    return factory


def count_reader(folder, kind: str, clock: Callable) -> Callable[[], tuple[int, int]]:
    """u8_counts' 24-hour `(errors, total)` of every process's count files for `kind`."""
    from .u8_counts import counts_over

    def read() -> tuple[int, int]:
        return counts_over(folder, (kind,), clock())[kind]

    return read
