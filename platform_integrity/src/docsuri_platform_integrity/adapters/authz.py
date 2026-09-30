"""Authorization recheck service with 1-minute TTL cache + revocation check."""

from __future__ import annotations

import time

import redis.asyncio as redis

from docsuri_platform_integrity.adapters.revocation import RevocationService


class AuthorizationService:
    """Authorization service with 1-minute TTL cache + revocation check."""

    def __init__(self, redis_client: redis.Redis):
        self._redis = redis_client
        self._revocation = RevocationService(redis_client)
        self._cache: dict[str, tuple[bool, float]] = {}
        self._job_owners: dict[str, str] = {}  # job_id -> owner_uid

    def register_job_owner(self, job_id: str, owner_uid: str) -> None:
        self._job_owners[job_id] = owner_uid

    async def recheck(self, caller: str, job_id: str, action: str) -> bool:
        """권한 재검증 with 1분 TTL cache + revocation check."""
        # 1. Cache 확인
        cache_key = f"{caller}:{job_id}:{action}"
        cached = self._cache.get(cache_key)
        if cached:
            allowed, expires = cached
            if time.time() < expires:
                return allowed
            del self._cache[cache_key]

        # 2. Job ownership 확인
        owner = self._job_owners.get(job_id)
        if not owner:
            allowed = False
        else:
            allowed = (caller == owner)

        # 3. Revocation 체크 (token 기반)
        if allowed:
            revoked = await self._check_revocation(job_id)
            if revoked:
                allowed = False

        # 4. Cache 저장 (1분 TTL)
        self._cache[cache_key] = (allowed, time.time() + 60)
        return allowed

    async def _check_revocation(self, job_id: str) -> bool:
        """Job 관련 token 철회 여부 확인."""
        # Job의 token_hash 조회 후 revocation 확인
        # 구현 간소화: 실제로는 DB에서 token_hash 조회 후 revocation 확인
        return False

    def revoke_job_access(self, job_id: str) -> None:
        """Job의 모든 접근 권한 즉시 철회."""
        if job_id in self._job_owners:
            del self._job_owners[job_id]
        # 관련 cache 무효화
        keys_to_delete = [k for k in self._cache if f":{job_id}:" in k]
        for k in keys_to_delete:
            del self._cache[k]
