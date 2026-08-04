"""SQLAlchemy engine/session seam.

This is the concrete fill for the DI seam the accounts module (U3) declares: its
``controller.get_db_session`` raises *"must be overridden by app shell"* until the shell
binds it to a real session factory (see ``backend.wiring._mount_accounts``).

The shell owns one engine per process (built at construction, disposed on shutdown); the
modules receive short-lived sessions via the FastAPI dependency.
"""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool


def make_engine(database_url: str) -> Engine:
    """Create the process-wide engine. Lazy connect — no server contact until first use."""
    # Bare `postgresql://` makes SQLAlchemy reach for psycopg2 (not installed). We ship
    # psycopg 3, so pin the dialect explicitly. Leaves `postgresql+<driver>://` and sqlite
    # untouched.
    if database_url.startswith("postgresql://"):
        database_url = "postgresql+psycopg://" + database_url[len("postgresql://") :]
    is_sqlite = database_url.startswith("sqlite")
    # check_same_thread=False: FastAPI serves a sync Session dependency across the threadpool.
    connect_args = {"check_same_thread": False} if is_sqlite else {}
    # NFR Design (U3 logical-components): Postgres connection pool — size 10 + overflow 20
    # (30 total), 3s acquire wait, recycle every 30 min (drop stale conns). SQLite uses
    # StaticPool and rejects sizing kwargs, so they are applied only for non-SQLite engines.
    pool_kwargs = (
        {}
        if is_sqlite
        else {
            "pool_size": 10,
            "max_overflow": 20,
            "pool_timeout": 3.0,
            "pool_recycle": 1800,
        }
    )
    # Scale-to-zero pooling (serverless-plan Phase 1-①): DB_POOL_MODE=null swaps the sized
    # QueuePool for NullPool — every session opens/closes a real connection, so an idle API
    # task holds nothing and the dev Aurora Serverless v2 cluster (min 0 ACU) can pause.
    # Unset (or any other value) keeps the default pool above; SQLite keeps its StaticPool.
    if not is_sqlite and os.getenv("DB_POOL_MODE") == "null":
        pool_kwargs = {"poolclass": NullPool}
    return create_engine(
        database_url,
        future=True,
        # pool_pre_ping avoids handing out a dead connection after an idle Postgres drop;
        # harmless for SQLite. SQLite gets no pool sizing (single-file, StaticPool default).
        pool_pre_ping=not is_sqlite,
        connect_args=connect_args,
        **pool_kwargs,
    )


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    """A sessionmaker the accounts dependency calls per-request (commit/rollback owned by
    the module's controller; the shell only opens and closes the session)."""
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
