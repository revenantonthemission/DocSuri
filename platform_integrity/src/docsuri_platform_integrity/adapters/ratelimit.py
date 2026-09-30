"""Rate limiting middleware — client identity based token bucket."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


@dataclass
class TokenBucket:
    max_tokens: int
    refill_rate: float
    tokens: float
    last_refill: float

    def consume(self, tokens: int = 1) -> bool:
        self._refill()
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def _refill(self) -> None:
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.max_tokens, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        max_tokens: int = 10,
        refill_rate: float = 2.0,
    ):
        super().__init__(app)
        self.max_tokens = max_tokens
        self.refill_rate = refill_rate
        self.buckets: dict[str, TokenBucket] = {}

    def _get_client_identity(self, request: Request) -> str:
        identity = request.headers.get("X-Client-Identity")
        if identity:
            return identity

        client_ip = request.client.host if request.client else "unknown"
        return f"ip:{hashlib.sha256(client_ip.encode()).hexdigest()[:16]}"

    def _get_bucket(self, identity: str, task_type: str) -> TokenBucket:
        key = f"{identity}:{task_type}"
        if key not in self.buckets:
            self.buckets[key] = TokenBucket(
                max_tokens=10,
                refill_rate=2.0,
                tokens=10.0,
                last_refill=time.time(),
            )
        return self.buckets[key]

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in ("/healthz", "/health"):
            return await call_next(request)

        task_type = self._extract_task_type(request.url.path)
        if not task_type:
            return await call_next(request)

        identity = self._get_client_identity(request)
        bucket = self._get_bucket(identity, task_type)

        if not bucket.consume(1):
            from fastapi import HTTPException
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={"Retry-After": "1"},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = str(int(bucket.tokens))
        reset_time = int(
            bucket.last_refill + (bucket.max_tokens - bucket.tokens) / bucket.refill_rate
        )
        response.headers["X-RateLimit-Reset"] = str(reset_time)
        return response

    def _extract_task_type(self, path: str) -> str | None:
        if "/translate" in path:
            return "translate"
        if "/summarize" in path:
            return "summarize"
        if "/novelty" in path:
            return "novelty"
        if "/evidence" in path:
            return "evidence"
        if "/jobs" in path:
            return "job"
        return None
