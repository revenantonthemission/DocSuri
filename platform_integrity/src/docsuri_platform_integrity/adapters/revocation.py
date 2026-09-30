"""Revocation Service — Redis Pub/Sub으로 즉시 전파."""

from __future__ import annotations

import json
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass

import redis.asyncio as redis


@dataclass(frozen=True)
class RevocationEvent:
    token_hash: str
    revoked_at: int  # microseconds UTC
    reason: str


class RevocationService:
    """Consent/token 철회 발행/구독."""

    def __init__(self, redis_client: redis.Redis):
        self._redis = redis_client

    async def revoke(self, token_hash: str, reason: str = "USER_REQUEST") -> None:
        """철회 발행 + 로컬 cache 즉시 무효화."""
        await self._redis.publish(
            f"revoke:{token_hash}",
            json.dumps({
                "token_hash": token_hash,
                "revoked_at": int(time.time() * 1_000_000),
                "reason": reason
            })
        )
        # 로컬 cache 즉시 무효화
        await self._redis.delete(f"unsubscribe:{token_hash}")
        await self._redis.delete(f"consent:{token_hash}")

    async def subscribe(self) -> AsyncGenerator[dict]:
        """철회 이벤트 구독 — 모든 worker에서 실행."""
        pubsub = self._redis.pubsub()
        await pubsub.psubscribe("revoke:*")
        
        async for message in pubsub.listen():
            if message["type"] == "pmessage":
                token_hash = message["channel"].decode().split(":")[1]
                event_data = json.loads(message["data"])
                yield {
                    "token_hash": token_hash,
                    "revoked_at": event_data["revoked_at"],
                    "reason": event_data["reason"]
                }


class RevocationSubscriber:
    """Worker에서 실행되는 철회 구독자."""

    def __init__(self, redis_client, cache: dict):
        self._redis = redis_client
        self._cache = cache

    async def start(self):
        pubsub = self._redis.pubsub()
        await pubsub.psubscribe("revoke:*")
        
        async for message in pubsub.listen():
            if message["type"] == "pmessage":
                token_hash = message["channel"].decode().split(":")[1]
                # 로컬 cache 즉시 무효화
                self.cache.pop(f"unsubscribe:{token_hash}", None)
                self.cache.pop(f"consent:{token_hash}", None)
                # 진행 중 job은 다음 authz_recheck에서 감지
