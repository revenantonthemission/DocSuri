from __future__ import annotations

import ipaddress
import time
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .request_context import RequestContext
from .security_headers import apply_security_headers


def _route_label(request: Request) -> str:
    """Bounded path label for metric dimensions — the matched route template, not the raw URL.

    ``request.url.path`` embeds ids/slugs → unbounded CloudWatch dimension cardinality (every
    distinct id becomes a separate custom metric: cost blowout against the $1600 cap, and too
    fragmented to alarm on). The route template (e.g. ``/library/history/{id}``) is bounded;
    unmatched requests (404s, scanners) collapse to a single ``unmatched`` label.

    Pre-routing short-circuits (429 rate-limit, 401 auth) also land as ``unmatched`` because no
    route is matched before they return — that's intentional: routing-before-rate-limit would
    invert the gateway order. Those abuse signals are alarmed on via the ``status`` dimension
    (429/401 are distinct from 404), not per-route.
    """
    route = request.scope.get("route")
    return getattr(route, "path", None) or "unmatched"


def install_gateway_middleware(
    app: FastAPI,
    *,
    observability=None,
    rate_limiter=None,
    session_manager=None,
    production: bool = True,
    trust_proxy_headers: bool = False,
    trusted_proxy_count: int = 1,
    trust_cloudflare_headers: bool = False,
) -> None:
    from .auth import inject_principal

    @app.middleware("http")
    async def _u6_gateway(request: Request, call_next):
        start_time = time.perf_counter()
        request_id = request.headers.get("X-Request-ID") or uuid4().hex
        request.state.request_id = request_id
        request.state.context = RequestContext(request_id=request_id)

        async def _run_gateway():
            if rate_limiter is not None:
                key = _rate_limit_key(
                    request,
                    trust_proxy_headers=trust_proxy_headers,
                    trusted_proxy_count=trusted_proxy_count,
                    trust_cloudflare_headers=trust_cloudflare_headers,
                )
                if not rate_limiter.allow(str(key)):
                    response = JSONResponse(
                        status_code=429,
                        content={"message": "Too many requests.", "requestId": request_id},
                    )
                    response.headers["X-Request-ID"] = request_id
                    # RFC 6585 §4: a 429 MUST carry Retry-After so a well-behaved client knows when
                    # to retry instead of hot-looping against the limit. Absent here, API consumers
                    # back off blindly and the abusive pattern is indistinguishable from a retry bug.
                    retry_after = _retry_after_seconds(rate_limiter)
                    if retry_after is not None:
                        response.headers["Retry-After"] = str(retry_after)
                    apply_security_headers(response)
                    return response

            # Auth injection: resolve session cookie → Principal on request.state.
            # When session_manager is None (dev/test without Redis), skip auth injection
            # and let downstream handlers use their own fallback (e.g. X-User-Id header).
            if session_manager is not None:
                auth_response = await inject_principal(
                    request, call_next, session_manager=session_manager
                )
                auth_response.headers["X-Request-ID"] = request_id
                apply_security_headers(auth_response)
                return auth_response

            # call_next may raise — handled by the SINGLE outer handler below so both the auth
            # and no-auth branches share one error path (US-R4: previously only this branch
            # caught, so production exceptions emitted no error metric or latency).
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            apply_security_headers(response)
            return response

        response = None
        try:
            response = await _run_gateway()
            return response
        except Exception as exc:
            _emit_error(observability, request_id, exc)
            if not production:
                raise
            response = JSONResponse(
                status_code=500,
                content={
                    "message": "Something went wrong. Please try again.",
                    "requestId": request_id,
                },
            )
            response.headers["X-Request-ID"] = request_id
            apply_security_headers(response)
            return response
        finally:
            # Emit exactly once per request, on EVERY path including exceptions (status="500"
            # when an exception propagated without a response). Errors are derived downstream
            # from the 5xx status tag — NOT from a separate error-log count — so a single
            # failure isn't double-counted. (US-R4)
            if observability is not None:
                try:
                    duration = time.perf_counter() - start_time
                    status = str(response.status_code) if response is not None else "500"
                    dims = {
                        "method": request.method,
                        "path": _route_label(request),
                        "status": status,
                    }
                    observability.emit_metric("gateway.request.latency", duration, dims)
                    observability.emit_metric("gateway.request.throughput", 1.0, dims)
                except Exception:
                    pass


# Cloudflare stamps these on every proxied request. They are only consulted when the deployment
# opts in (CLOUDFLARE_TRUSTED=1), because an unverified client can set arbitrary headers: trusting
# CF-Connecting-IP by default would let any caller mint unlimited rate-limit buckets by rotating it.
# See the same reasoning as the X-Forwarded-For leftmost-hop rejection in _forwarded_client.
_CF_CLIENT_IP_HEADERS = ("CF-Connecting-IP", "True-Client-IP")


def _rate_limit_key(
    request: Request,
    *,
    trust_proxy_headers: bool = False,
    trusted_proxy_count: int = 1,
    trust_cloudflare_headers: bool = False,
) -> str:
    if trust_cloudflare_headers:
        cf_client = _cloudflare_client(request)
        if cf_client is not None:
            return cf_client

    if trust_proxy_headers:
        forwarded = _forwarded_client(request, trusted_proxy_count)
        if forwarded is not None:
            return forwarded

    client = getattr(request, "client", None)
    host = getattr(client, "host", None)
    return str(host or "unknown-client")


def _cloudflare_client(request: Request) -> str | None:
    """Right-most valid IP among the Cloudflare client headers.

    A caller may send several of these; we take the last valid one rather than the first so an
    upstream-inserted duplicate cannot shadow the edge-stamped value. Non-IP values are rejected so
    a garbage header cannot become a bucket of its own.
    """
    for header in _CF_CLIENT_IP_HEADERS:
        raw = request.headers.get(header)
        if not raw:
            continue
        hops = [hop.strip() for hop in raw.split(",") if hop.strip()]
        for candidate in reversed(hops):
            if _is_ip(candidate):
                return candidate
    return None


def _forwarded_client(request: Request, trusted_proxy_count: int) -> str | None:
    raw = request.headers.get("X-Forwarded-For")
    if not raw:
        return None
    hops = [hop.strip() for hop in raw.split(",") if hop.strip()]
    # The LEFTMOST entry is fully client-controlled (spoofable) — keying on it lets an attacker
    # rotate it to evade per-IP limits. Trust only what our own proxies stamped: count
    # `trusted_proxy_count` from the right and take the hop our outermost trusted proxy recorded.
    # Require a valid IP so a spoofed/garbage value can't mint unlimited rate-limit buckets.
    idx = len(hops) - max(trusted_proxy_count, 1)
    if idx < 0:
        return None  # fewer hops than trusted proxies → header is not trustworthy
    candidate = hops[idx]
    return candidate if _is_ip(candidate) else None


def _is_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


def _retry_after_seconds(rate_limiter) -> int | None:
    """Seconds until the rate-limit window rolls over, or None if the limiter can't say.

    Limiter implementations expose their window as ``window_seconds``; when absent we omit the
    header rather than guess a value, since an understated Retry-After invites a retry storm.
    """
    window = getattr(rate_limiter, "window_seconds", None)
    if window is None:
        return None
    try:
        seconds = int(window)
    except (TypeError, ValueError):
        return None
    return max(seconds, 1)


def _emit_error(observability, request_id: str, exc: Exception) -> None:
    if observability is None:
        return
    emit_log = getattr(observability, "emit_log", None)
    if emit_log is None:
        return
    emit_log(
        {
            "eventId": f"gateway-error:{request_id}",
            "requestId": request_id,
            "level": "error",
            "errorType": type(exc).__name__,
        }
    )
