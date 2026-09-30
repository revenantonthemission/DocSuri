"""Authorization recheck service with 1-minute TTL cache."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol


class AuthorizationService(Protocol):
    async def recheck(self, caller: str, job_id: str, action: str) -> bool: ...


@dataclass
class AuthzCache:
    """1-minute TTL cache for authorization decisions."""
    _cache: dict[str, tuple[bool, float]] = {}

    def get(self, caller: str, job_id: str, action: str) -> bool | None:
        key = f"{caller}:{job_id}:{action}"
        if key in self._cache:
            allowed, expires = self._cache[key]
            if time.time() < expires:
                return allowed
            else:
                del self._cache[key]
        return None

    def set(self, caller: str, job_id: str, action: str, allowed: bool) -> None:
        key = f"{caller}:{job_id}:{action}"
        self._cache[key] = (allowed, time.time() + 60)  # 1 minute TTL


class AuthorizationServiceImpl:
    """Authorization service with 1-minute TTL cache."""

    def __init__(self):
        self.cache = AuthzCache()
        # In production, this would check DB for job ownership, permissions, etc.
        self._job_owners: dict[str, str] = {}  # job_id -> owner_uid

    def register_job_owner(self, job_id: str, owner_uid: str) -> None:
        self._job_owners[job_id] = owner_uid

    def revoke_job_access(self, job_id: str) -> None:
        """Mark job as having revoked access (e.g., owner account disabled)."""
        if job_id in self._job_owners:
            del self._job_owners[job_id]

    async def recheck(self, caller: str, job_id: str, action: str) -> bool:
        """Recheck authorization with 1-minute cache."""
        # Check cache first
        cached = self._cache.get(job_id, action)
        if cached is not None:
            return cached

        # Check job ownership
        owner = self._job_owners.get(job_id)
        if not owner:
            allowed = False
        else:
            # Owner can perform any action on their job
            allowed = (caller == owner)

        # Cache result (1-minute TTL)
        self._cache.set(job_id, action, allowed)
        return allowed

    def register_job(self, job_id: str, owner: str) -> None:
        """Register a new job with its owner."""
        self._job_owners[job_id] = owner
