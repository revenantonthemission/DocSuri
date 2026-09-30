"""Unsubscribe Token Service — HS256 JWT 발급/검증, Redis cache."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass

import jwt
import redis.asyncio as redis


@dataclass(frozen=True)
class UnsubscribeToken:
    email: str
    token: str
    exp: int
    iat: int


class UnsubscribeTokenService:
    """HS256 JWT 기반 unsubscribe 토큰 관리."""

    JWT_ALGORITHM = "HS256"
    TOKEN_TTL_SECONDS = 24 * 3600  # 24시간

    def __init__(
        self,
        redis_client: redis.Redis,
        jwt_secret: str,
        db_pool,
    ):
        self._redis = redis_client
        self._secret = jwt_secret
        self._pool = None  # DB pool은 lazy init

    def set_db_pool(self, pool):
        self._pool = pool

    def create_token(self, email: str) -> str:
        """Unsubscribe 토큰 생성."""
        now = int(time.time())
        payload = {
            "email": email,
            "purpose": "unsubscribe",
            "exp": int(time.time()) + self.TOKEN_TTL_SECONDS,
            "iat": now,
        }
        return jwt.encode(payload, self._secret, algorithm="HS256")

    def _token_hash(self, token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    async def verify_and_consume(self, token: str) -> str | None:
        """토큰 검증 후 job_id 반환 (cache hit 시 즉시 반환)."""
        try:
            payload = jwt.decode(token, self._secret, algorithms=["HS256"])
        except jwt.InvalidTokenError:
            return None

        if payload.get("purpose") != "unsubscribe":
            return None

        _ = payload["email"]  # used for validation
        token_hash = self._token_hash(token)

        # Redis cache lookup
        cached = await self._redis.get(f"unsubscribe:{token_hash}")
        if cached:
            return cached.decode()

        # Cache miss: DB에서 job_id 조회
        async with self._pool.acquire() as conn:
            job_id = await conn.fetchval(
                "SELECT job_id FROM unsubscribe_tokens "
                "WHERE token_hash = $1 AND revoked_at IS NULL",
                self._token_hash(token),
            )

        if job_id:
            # Cache 저장 (24시간 TTL)
            await self._redis.setex(
                f"unsubscribe:{self._token_hash(token)}", 86400, job_id
            )
            return job_id
        return None

    async def revoke(self, token: str) -> bool:
        """토큰 철회."""
        try:
            jwt.decode(token, self._secret, algorithms=["HS256"])
        except jwt.InvalidTokenError:
            return False

        token_hash = self._token_hash(token)
        await self._redis.delete(f"unsubscribe:{token_hash}")

        if self._pool:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    "UPDATE unsubscribe_tokens SET revoked_at = now() WHERE token_hash = $1",
                    self._token_hash(token),
                )
        return True
