"""Purge Registry adapter — soft delete → grace period → hard delete 멱등 관리."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum


class PurgeStatus(StrEnum):
    ACTIVE = "ACTIVE"
    SOFT_DELETED = "SOFT_DELETED"
    PURGED = "PURGED"


@dataclass(frozen=True)
class PurgeRegistryEntry:
    owner_uid: int
    status: PurgeStatus
    requested_at: int  # microseconds UTC
    grace_until: int   # microseconds UTC
    purged_at: int | None
    version: int


class PurgeRegistry:
    """Owner purge 상태 관리 — soft delete → grace period → hard delete."""

    def __init__(self, pool):
        self._pool = pool

    async def request_purge(self, owner_uid: int, grace_days: int = 30) -> PurgeRegistryEntry:
        """Soft delete 요청 — 이미 SOFT_DELETED면 에러."""
        now_us = int(datetime.now(UTC).timestamp() * 1_000_000)
        grace_until = now_us + grace_days * 24 * 3600 * 1_000_000

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # Optimistic locking으로 동시 요청 방지
                row = await conn.fetchrow(
                    """
                    INSERT INTO purge_registry (owner_uid, status, requested_at,
                                               grace_until, version)
                    VALUES ($1, 'SOFT_DELETED', $2, $3, 1)
                    ON CONFLICT (owner_uid) DO UPDATE SET
                        status = EXCLUDED.status,
                        requested_at = EXCLUDED.requested_at,
                        grace_until = EXCLUDED.grace_until,
                        version = purge_registry.version + 1
                    WHERE purge_registry.status = 'ACTIVE'
                    RETURNING owner_uid, status, requested_at, grace_until,
                           purged_at, version
                    """,
                    owner_uid, now_us, grace_until,
                )

                if not row:
                    raise ValueError(f"Owner {owner_uid} is not ACTIVE or already requested purge")

                return PurgeRegistryEntry(
                    owner_uid=row['owner_uid'],
                    status=PurgeStatus(row['status']),
                    requested_at=row['requested_at'],
                    grace_until=row['grace_until'],
                    purged_at=row['purged_at'],
                    version=row['version'],
                )

    async def get_due_purges(self) -> list[PurgeRegistryEntry]:
        """grace_until 경과된 SOFT_DELETED owner 조회."""
        now_us = int(datetime.now(UTC).timestamp() * 1_000_000)
        rows = await self._pool.fetch(
            """
            SELECT owner_uid, status, requested_at, grace_until, purged_at, version
            FROM purge_registry
            WHERE status = 'SOFT_DELETED' AND grace_until < $1
            """,
            now_us,
        )

        return [
            PurgeRegistryEntry(
                owner_uid=r['owner_uid'],
                status=PurgeStatus(r['status']),
                requested_at=r['requested_at'],
                grace_until=r['grace_until'],
                purged_at=r['purged_at'],
                version=r['version'],
            )
            for r in rows
        ]

    async def mark_purged(self, owner_uid: int, expected_version: int) -> bool:
        """Hard delete 완료 표시 — optimistic locking으로 멱등 보장."""
        result = await self._pool.execute(
            """
            UPDATE purge_registry
            SET status = 'PURGED', purged_at = $1, version = version + 1
            WHERE owner_uid = $2 AND version = $3 AND status = 'SOFT_DELETED'
            """,
            int(datetime.now(UTC).timestamp() * 1_000_000),
            owner_uid,
            expected_version,
        )
        return result == "UPDATE 1"

    async def restore(self, owner_uid: int) -> bool:
        """Soft delete 복구 — ACTIVE로 복원."""
        result = await self._pool.execute(
            """
            UPDATE purge_registry
            SET status = 'ACTIVE', grace_until = 0, purged_at = NULL, version = version + 1
            WHERE owner_uid = $1 AND status = 'SOFT_DELETED'
            """,
            owner_uid,
        )
        return result == "UPDATE 1"
