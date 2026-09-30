"""Owner-scoped data purge backstop for account hard-delete.

AccountDeleted is still published for asynchronous subscribers. This adapter handles
the same-RDS tables that already exist in the deployed monolith so the purge worker
does not leave first-party user data behind while subscriber infra catches up.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# SQL 식별자(테이블·컬럼)는 바인딩이 불가능하므로 f-string으로 보간된다. 값(account_id)은 항상
# :account_id로 바인딩되어 주입면은 식별자뿐이다. 호출부가 임의 spec을 넘기더라도 안전한 형태만
# 허용하도록 화이트리스트 정규식으로 검증한다(N2 — 심층 방어).
_SQL_IDENT_RE = re.compile(r"^[a-z_][a-z0-9_]*$")


@dataclass(frozen=True)
class OwnerScopedTable:
    table: str
    owner_column: str = "owner_id"
    # BR-PURGE-02: some owner rows point at a binary object in the shared object store
    # (novelty_artifacts.object_key → novelty/{owner}/{job}/...). Rows alone are not a purge —
    # the object holds the user's content. Declaring the column here makes the purge collect
    # the keys BEFORE the DELETE and remove the objects AFTER, in the required DB→object order.
    object_column: str | None = None


# Child tables first, then parent/summary rows.
OWNER_SCOPED_TABLES: tuple[OwnerScopedTable, ...] = (
    OwnerScopedTable("research_messages"),
    OwnerScopedTable("research_jobs"),
    OwnerScopedTable("novelty_messages"),
    OwnerScopedTable("novelty_progress_events"),
    OwnerScopedTable("novelty_artifacts", object_column="object_key"),
    OwnerScopedTable("novelty_notion_exports"),
    OwnerScopedTable("novelty_notion_connections"),
    OwnerScopedTable("novelty_jobs"),
    OwnerScopedTable("saved_searches"),
    OwnerScopedTable("library_items"),
    OwnerScopedTable("search_history"),
    OwnerScopedTable("user_behavior_events"),
    OwnerScopedTable("user_interest_profiles"),
    OwnerScopedTable("personalization_settings"),
    OwnerScopedTable("mypage_subscriptions"),
    OwnerScopedTable("user_glossary", "user_id"),
)


class OwnerObjectPurger(Protocol):
    """Owner-scoped object removal in the shared object store (BR-PURGE-02). Kept a port so the
    purge domain never imports boto3 and tests drive it with a fake."""

    def delete_objects(self, keys: Iterable[str]) -> int: ...


class S3ObjectPurger:
    """Delete objects by explicit key from the novelty artifact bucket.

    Explicit keys (not a prefix sweep) because ownership is proven by the DB row we just read:
    a prefix delete would remove a *different* owner's job that happens to share a prefix, and
    would race a concurrent upload. ``AWS_ENDPOINT_URL_S3`` is honoured by boto3 itself, so the
    local SeaweedFS endpoint works without code changes.
    """

    def __init__(self, bucket: str, *, client: object | None = None) -> None:
        if not bucket:
            raise ValueError("object bucket must be configured to purge owner objects")
        self._bucket = bucket
        if client is None:
            import boto3

            client = boto3.client("s3")
        self._client = client

    def delete_objects(self, keys: Iterable[str]) -> int:
        batch = [{"Key": k} for k in keys if k]
        if not batch:
            return 0
        deleted = 0
        # S3 DeleteObjects caps at 1000 keys per request; chunk to stay under the limit.
        for i in range(0, len(batch), 1000):
            chunk = batch[i : i + 1000]
            response = self._client.delete_objects(
                Bucket=self._bucket,
                Delete={"Objects": chunk, "Quiet": True},
            )
            deleted += len(response.get("Deleted", chunk))
        logger.info(
            {"event": "OwnerObjectsPurged", "objects": deleted, "bucket": self._bucket}
        )
        return deleted


def build_object_purger() -> OwnerObjectPurger | None:
    """Assembly root: no bucket configured (e.g. a deployment without novelty) → None, and the
    purge still deletes rows. Configuring the bucket opts into object purge."""
    import os

    bucket = os.getenv("DOCSURI_NOVELTY_ARTIFACT_BUCKET")
    if not bucket:
        logger.warning(
            "DOCSURI_NOVELTY_ARTIFACT_BUCKET unset: owner-object purge is disabled; rows are "
            "still deleted but stored artifacts would be orphaned."
        )
        return None
    return S3ObjectPurger(bucket)


class SqlOwnerDataPurger:
    def __init__(
        self,
        session: Session,
        tables: Iterable[OwnerScopedTable] = OWNER_SCOPED_TABLES,
        object_purger: OwnerObjectPurger | None = None,
    ) -> None:
        self._session = session
        self._object_purger = object_purger
        tables = tuple(tables)
        # N2: 식별자 화이트리스트 검증을 생성 시점에 강제한다 — 안전하지 않은 spec은 즉시 거부.
        for spec in tables:
            if not _SQL_IDENT_RE.match(spec.table) or not _SQL_IDENT_RE.match(spec.owner_column):
                raise ValueError(f"Unsafe SQL identifier in OwnerScopedTable: {spec!r}")
        self._tables = tables
        self._schema: dict[str, set[str]] | None = None  # table -> column 집합 (1회 캐시)

    def _schema_map(self) -> dict[str, set[str]]:
        """존재하는 테이블과 각 컬럼 집합을 1회 반영해 캐시한다(N3). purge가 계정마다 호출돼도
        reflection은 한 번만 수행하며, owner_column 존재 검증에도 사용한다."""
        if self._schema is None:
            insp = inspect(self._session.get_bind())
            self._schema = {t: {c["name"] for c in insp.get_columns(t)} for t in insp.get_table_names()}
        return self._schema

    def purge(self, account_id: str) -> None:
        schema = self._schema_map()
        deleted_rows = 0
        object_keys: list[str] = []

        for spec in self._tables:
            cols = schema.get(spec.table)
            if cols is None:
                continue  # 이 배포에 없는 테이블 — 건너뜀
            if spec.owner_column not in cols:
                # N3: 잘못된 owner 컬럼은 DELETE에서 터져 계정 파기를 영구 실패(→무한 재시도)시킨다.
                # 스킵 + 경보로 격리해 나머지 테이블 파기는 진행한다.
                logger.error(
                    "OwnerScopedTable %s has no column %s; skipping (check OWNER_SCOPED_TABLES).",
                    spec.table, spec.owner_column,
                )
                continue
            # BR-PURGE-02: read the object keys BEFORE the DELETE — the row is the only proof of
            # ownership, and once deleted the key is unrecoverable. Selection and deletion share
            # this transaction, so an object-delete failure rolls the rows back and the retry can
            # re-read the same keys.
            if spec.object_column is not None and spec.object_column in cols:
                rows = self._session.execute(
                    text(
                        f"SELECT {spec.object_column} FROM {spec.table} "
                        f"WHERE {spec.owner_column} = :account_id"
                    ),
                    {"account_id": account_id},
                )
                object_keys.extend(str(k) for (k,) in rows if k)
            result = self._session.execute(
                text(f"DELETE FROM {spec.table} WHERE {spec.owner_column} = :account_id"),
                {"account_id": account_id},
            )
            deleted_rows += int(result.rowcount or 0)

        self._session.flush()

        # DB → object store. Rows are already gone in this transaction; objects are removed before
        # commit so a store failure rolls both back together (no PURGED mark on a partial purge).
        purged_objects = 0
        if object_keys and self._object_purger is not None:
            purged_objects = self._object_purger.delete_objects(object_keys)
        elif object_keys:
            logger.error(
                "Owner %s has %d stored object(s) but no object purger is configured; "
                "objects are orphaned until the bucket env is set (BR-PURGE-02 gap).",
                account_id, len(object_keys),
            )

        logger.info(
            {
                "event": "OwnerScopedDataPurged",
                "accountId": account_id,
                "deletedRows": deleted_rows,
                "deletedObjects": purged_objects,
            }
        )
