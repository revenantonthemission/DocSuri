"""``backend.db.make_engine`` pool-mode gate (serverless-plan Phase 1-①).

``DB_POOL_MODE=null`` must swap the sized QueuePool for NullPool so idle API tasks hold no
server connections and the dev Aurora Serverless v2 cluster (min 0 ACU) can pause. Default
behavior — the U3 sized pool — must stay untouched when the variable is unset or unknown.
"""

from __future__ import annotations

import pytest
from sqlalchemy.pool import NullPool, QueuePool

from backend.db import make_engine

_PG_URL = "postgresql://docsuri_admin@db.example.internal:5432/docsuri"


def test_postgres_engine_defaults_to_sized_queue_pool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DB_POOL_MODE", raising=False)

    engine = make_engine(_PG_URL)

    assert isinstance(engine.pool, QueuePool)
    assert engine.pool.size() == 10


def test_db_pool_mode_null_uses_null_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DB_POOL_MODE", "null")

    engine = make_engine(_PG_URL)

    assert isinstance(engine.pool, NullPool)


def test_unknown_pool_mode_keeps_default_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DB_POOL_MODE", "queue")

    engine = make_engine(_PG_URL)

    assert isinstance(engine.pool, QueuePool)


def test_sqlite_ignores_pool_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DB_POOL_MODE", "null")

    engine = make_engine("sqlite://")

    assert not isinstance(engine.pool, NullPool)
