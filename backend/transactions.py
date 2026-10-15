"""Bounded owner transactions for the explicit local composition.

Eight lazy pools do not reserve eight idle connections. The process gate caps
API activity at four, worker at two and observation at one; maintenance/recovery
retain room within PostgreSQL's twelve slots. No callback performs network/model
work or commits independently.
"""

from __future__ import annotations

import json
import os
import stat
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import NullConnectionPool

from .local_profile import LocalProfile, private_bytes

T = TypeVar("T")
_GATES_LOCK = threading.Lock()
_PROCESS_GATES = {}
OWNERS = frozenset(
    (
        "accounts",
        "corpus",
        "library",
        "personalization",
        "discovery",
        "usage",
        "assistance",
        "operations",
    )
)


@dataclass(frozen=True)
class Authority:
    """Server-established identity; never constructed from a browser owner field."""

    account_id: UUID
    session_id: UUID


class Busy(RuntimeError):
    pass


class UnknownCommit(RuntimeError):
    """The caller must reconcile its original operation key before new effects."""


class DeadlineConnection:
    """Repository SQL seam with one absolute request deadline."""

    def __init__(
        self, connection: psycopg.Connection, deadline: float, *, statement_ms: int = 5000
    ):
        self.connection = connection
        self.deadline = deadline
        self.statement_ms = statement_ms

    def remaining(self) -> float:
        value = self.deadline - time.monotonic()
        if value <= 0:
            raise Busy("aggregate transaction deadline reached")
        return value

    def execute(self, query, params=None, **kwargs):
        milliseconds = max(1, min(self.statement_ms, int(self.remaining() * 1000)))
        self.connection.execute(
            "SELECT set_config('statement_timeout',%s,true)", (str(milliseconds),)
        )
        self.remaining()
        return self.connection.execute(query, params, **kwargs)


class OwnerTransactions:
    def __init__(self, profile: LocalProfile, *, process: str = "api"):
        limits = {"api": 4, "worker": 2, "observation": 1, "maintenance": 1}
        # The managed realms run an embedded supervised worker; their API and
        # worker share five normal slots, with two observation/recovery slots
        # and one runner slot reserved inside the twelve connection budget.
        controls = profile.realm in ("account-controls", "corpus-maintenance")
        if controls:
            limits = {"api": 5, "worker": 5, "observation": 2, "maintenance": 1}
        if process not in limits:
            raise ValueError("unknown bounded process role")
        path = profile.root / "owner-credentials.json"
        info = path.lstat()
        if path.is_symlink() or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
            raise ValueError("owner credentials are not private")
        value = json.loads(private_bytes(path))
        if value.get("runId") != profile.run_id or set(value.get("roles", {})) != OWNERS:
            raise ValueError("owner credential identity mismatch")
        self.profile = profile
        self._controls = controls
        self._process = process
        self._transaction_seconds = 5 if controls else 10
        self._queue_seconds = 1 if controls else 2
        self._statement_ms = 3000 if controls else 5000
        if (profile.database_name, profile.realm) not in {
            ("docsuri_u1", "diagnostic"),
            ("docsuri_u1_journey", "journey"),
            ("docsuri_u2", "account-controls"),
            ("docsuri_u3", "corpus-maintenance"),
        }:
            raise ValueError("unknown explicit database realm")
        # Separate databases do not receive separate process connection budgets.
        with _GATES_LOCK:
            self._gate = _PROCESS_GATES.setdefault(
                (
                    str(profile.root),
                    profile.run_id,
                    "api" if controls and process == "worker" else process,
                ),
                threading.BoundedSemaphore(limits[process]),
            )
        self._recovery_gate = None
        if controls and process in {"api", "worker"}:
            with _GATES_LOCK:
                self._recovery_gate = _PROCESS_GATES.setdefault(
                    (str(profile.root), profile.run_id, "observation"),
                    threading.BoundedSemaphore(2),
                )
        self._pools = {}
        self._recovery_pools = {}
        self._closed = False
        for owner in OWNERS:
            self._pools[owner] = NullConnectionPool(
                kwargs={
                    "host": "127.0.0.1",
                    "port": profile.database_port,
                    "dbname": profile.database_name,
                    "user": f"docsuri_{owner}",
                    "password": value["roles"][owner],
                    "connect_timeout": 3,
                    "row_factory": dict_row,
                    "application_name": f"docsuri-{profile.realm}-{process}-{owner}",
                },
                min_size=0,
                max_size=min(2, limits[process]),
                max_waiting=4,
                timeout=self._queue_seconds,
                reconnect_timeout=2,
                open=True,
            )

        if self._recovery_gate is not None:
            for owner, pool in self._pools.items():
                self._recovery_pools[owner] = NullConnectionPool(
                    kwargs=dict(
                        pool.kwargs, application_name=f"docsuri-{profile.realm}-recovery-{owner}"
                    ),
                    min_size=0,
                    max_size=2,
                    max_waiting=2,
                    timeout=1,
                    reconnect_timeout=2,
                    open=True,
                )

    def close(self) -> None:
        self._closed = True
        for pool in (*self._pools.values(), *self._recovery_pools.values()):
            pool.close()

    def run(self, owner: str, action: Callable[[psycopg.Connection], T]) -> T:
        deadline = time.monotonic() + self._transaction_seconds
        gate, pools = self._gate, self._pools
        if self._controls:
            from .control_runtime import RECOVERY_REQUEST, WORK_DEADLINE

            work_deadline = WORK_DEADLINE.get()
            if work_deadline is not None:
                deadline = min(deadline, work_deadline)
            if deadline <= time.monotonic():
                raise Busy("control work deadline reached")
            if RECOVERY_REQUEST.get() and self._recovery_gate is not None:
                gate, pools = self._recovery_gate, self._recovery_pools
        if self._closed or owner not in self._pools:
            raise ValueError("closed or unknown owner pool")
        if time.time() >= self.profile.expires_at:
            raise ValueError("synthetic retention expired")
        if not gate.acquire(
            timeout=min(self._queue_seconds, max(0.01, deadline - time.monotonic()))
        ):
            raise Busy("process connection allocation exhausted")
        try:
            for attempt in range(3):
                try:
                    with pools[owner].connection(
                        timeout=min(self._queue_seconds, max(0.01, deadline - time.monotonic()))
                    ) as conn:
                        conn.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
                        bounded = DeadlineConnection(
                            conn, deadline, statement_ms=self._statement_ms
                        )
                        identity = bounded.execute(
                            "SELECT run_id,current_database() AS database_name "
                            "FROM public.docsuri_local_identity"
                        ).fetchone()
                        if (
                            identity is None
                            or identity["run_id"] != self.profile.run_id
                            or identity["database_name"] != self.profile.database_name
                        ):
                            raise ValueError("database realm mismatch")
                        result = action(bounded)
                        bounded.execute(
                            "SELECT set_config('statement_timeout',%s,true)",
                            (str(max(1, int(bounded.remaining() * 1000))),),
                        )
                        bounded.remaining()
                        try:
                            conn.commit()
                        except (psycopg.OperationalError, psycopg.InterfaceError) as exc:
                            # A serialization failure is a definitive rollback;
                            # a lost connection during COMMIT has unknown outcome.
                            if isinstance(
                                exc,
                                (
                                    psycopg.errors.SerializationFailure,
                                    psycopg.errors.DeadlockDetected,
                                ),
                            ):
                                raise
                            raise UnknownCommit("reconcile original operation identity") from exc
                        return result
                except (psycopg.errors.SerializationFailure, psycopg.errors.DeadlockDetected):
                    if attempt == 2 or time.monotonic() >= deadline:
                        raise
            raise Busy("transaction retry budget exhausted")
        finally:
            gate.release()


def guard(
    conn: psycopg.Connection,
    authority: Authority,
    *,
    version: str | None = None,
    purpose: str = "local-research",
) -> UUID:
    revision = conn.execute(
        "SELECT accounts.guard_session(%s,%s,%s) AS revision",
        (authority.account_id, authority.session_id, purpose),
    ).fetchone()["revision"]
    if version is not None:
        conn.execute("SELECT corpus.guard_version(%s,%s)", (version, "local-research"))
    return revision
