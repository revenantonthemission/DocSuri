"""The complete realms' owner transactions (U8 plan Step 51(b); L1-6, L1-29).

`CompleteTransactions(profile, *, process='api', counts=None)` is `OwnerTransactions`
for the composed realm and the production realm only; it refuses any other profile
before `OwnerTransactions` reads anything. `OwnerTransactions` itself stays as built, so
no earlier realm changes.

- **Request identifier (L1-6).** While `CURRENT_REQUEST_ID` holds a UUID, each attempt of
  a run first sets `docsuri.request_id` for that transaction only, so the owners' column
  defaults record the accepting request inside its own transaction. Any other value is
  never set, so the defaults' `::uuid` cast cannot fail.
- **Counts (L1-29).** Each run is counted once, by the exception that leaves it: every
  run adds one to `postgresql.connection`'s total, every run that is not a failed
  connection one to `postgresql.transaction`'s, and the failed kinds also add to their
  failed count (`failure_of`). Whether the action had begun is judged for the attempt
  that raised: each attempt's look-up of its owner pool, right before it connects,
  marks the run's attempt as not begun again, so a connect that fails on a retried
  attempt counts as a failed connection.
- **Gate observation (Step 114(b)).** `observe_gates(observer)`, default off, wraps this
  instance's process, recovery and owner gates in `backend.u8_gate_waits.ObservedGate`,
  which calls each semaphore through and reports its waits and holds; it is refused
  outside the composed realm, nothing in `backend/` calls it, and only the served realm
  started with `--observe-gates` (the `capacity-burst` phase) turns it on.
- **Login timing (Step 134(b); NFR8.3, performance-design § 2.3).** `login_seconds(owner)`
  times one SCRAM login through that owner's own pool, taking no gate and counting
  nothing; it is refused outside the composed realm before any connection, nothing in
  `backend/` calls it, and only the `performance` phase does, with the served realm
  stopped.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from contextvars import ContextVar
from typing import TypeVar
from uuid import UUID

import psycopg
from psycopg_pool import PoolTimeout

from .local_browser import CURRENT_REQUEST_ID
from .local_profile import LocalProfile
from .transactions import Busy, DeadlineReached, OwnerTransactions, UnknownCommit, complete_realm

T = TypeVar("T")
CONNECTION, TRANSACTION = "postgresql.connection", "postgresql.transaction"
CONNECTION_BUSY = frozenset({
    "process connection allocation exhausted",
    "owner connection allocation exhausted",
})
TRANSACTION_BUSY = frozenset({
    "aggregate transaction deadline reached",
    "transaction retry budget exhausted",
})


def failure_of(error: BaseException | None, *, began: bool) -> str | None:
    """`connection`, `transaction` or None (not counted as failed) for the exception that
    left a run; `began` says whether the wrapped action had started."""
    if error is None:
        return None
    # The entry, identity and mail limits (Busy's other subclasses) are never counted; a
    # passed transaction deadline (`DeadlineReached`, Step 68(h)) is the failed
    # transaction the plain deadline Busy was.
    if type(error) in (Busy, DeadlineReached):
        message = str(error)
        if message in CONNECTION_BUSY:
            return "connection"
        if message in TRANSACTION_BUSY:
            return "transaction"
        return None
    if isinstance(error, PoolTimeout):
        return "connection"
    if isinstance(error, UnknownCommit):
        return "transaction"
    if isinstance(error, (psycopg.OperationalError, psycopg.InterfaceError)):
        return "transaction" if began else "connection"
    return None


def request_identifier() -> str | None:
    """The current request's identifier when it is a UUID in canonical form."""
    value = CURRENT_REQUEST_ID.get()
    if not isinstance(value, str):
        return None
    try:
        parsed = UUID(value)
    except ValueError:
        return None
    return value if str(parsed) == value else None


# The running attempt's "the action has begun" cell, one per `run` (a nested run inside
# an action sets its own and restores the outer one).
_ATTEMPT: ContextVar[list[bool] | None] = ContextVar("u8_owner_attempt", default=None)


class _AttemptPools(dict):
    """The owner pools. `OwnerTransactions.run` looks its pool up once per attempt, right
    before that attempt connects, so the look-up marks the attempt as not begun."""

    def __getitem__(self, owner):
        cell = _ATTEMPT.get()
        if cell is not None:
            cell[0] = False
        return super().__getitem__(owner)


class CompleteTransactions(OwnerTransactions):
    def __init__(self, profile: LocalProfile, *, process: str = "api", counts=None):
        if not complete_realm(profile.database_name, profile.realm):
            raise ValueError("not a complete realm")
        super().__init__(profile, process=process)
        self._pools = _AttemptPools(self._pools)
        self._recovery_pools = _AttemptPools(self._recovery_pools)
        self._counts = counts
        self._observed = False

    def observe_gates(self, observer) -> None:
        """This instance's gates, each called through an `ObservedGate` (Step 114(b)):
        the same shared semaphores, bounds, queue and `Busy` answers, every take timed.
        `OwnerTransactions.run` reads these attributes at each call."""
        from .u8_gate_waits import ObservedGate, require_observable

        require_observable(self.profile)
        if self._observed:
            raise ValueError("gates already observed")
        self._observed = True
        self._gate = ObservedGate(self._gate, "process", "*", observer)
        if self._recovery_gate is not None:
            self._recovery_gate = ObservedGate(self._recovery_gate, "recovery", "*", observer)
        self._normal_owner_gates = {
            owner: ObservedGate(gate, "normal-owner", owner, observer)
            for owner, gate in self._normal_owner_gates.items()}
        self._owner_gates = {
            owner: ObservedGate(gate, "owner", owner, observer)
            for owner, gate in self._owner_gates.items()}

    @property
    def owners(self) -> tuple[str, ...]:
        """This instance's owner logins, in name order."""
        return tuple(sorted(self._pools))

    def login_seconds(self, owner: str, *, clock: Callable[[], float] = time.perf_counter
                      ) -> float:
        """The seconds one login takes through `owner`'s own pool (NFR8.3; plan Step
        134(b)): from `clock()` until the connection is ready. The pool's keyword
        arguments demand SCRAM; the connection runs no statement and closes as the block
        ends. No gate is taken and nothing is counted: it times a login, not a
        transaction. With `connection(timeout=1)` psycopg_pool sets `connect_timeout` to
        1 and psycopg raises it to its 2 s floor, so one login waits at most about 2 s."""
        from .u8_gate_waits import require_observable

        try:
            require_observable(self.profile)
        except ValueError:
            raise ValueError("login timing serves the composed realm only") from None
        if self._closed or owner not in self._pools:
            raise ValueError("closed or unknown owner pool")
        if time.time() >= self.profile.expires_at:
            raise ValueError("synthetic retention expired")
        started = clock()
        with self._pools[owner].connection(timeout=self._queue_seconds):
            return clock() - started

    def close(self) -> None:
        if self._counts is not None:
            self._counts.close()
        super().close()

    def run(self, owner: str, action: Callable[[psycopg.Connection], T]) -> T:
        attempt = [False]  # [0]: the raising attempt's action had begun

        def wrapped(bounded):
            attempt[0] = True
            identifier = request_identifier()
            if identifier is not None:
                bounded.execute("SELECT set_config('docsuri.request_id', %s, true)",
                                (identifier,))
            return action(bounded)

        counted = self._counts is not None and not self._closed
        token = _ATTEMPT.set(attempt)
        try:
            result = super().run(owner, wrapped)
        except BaseException as error:
            if counted:
                self._count(failure_of(error, began=attempt[0]))
            raise
        finally:
            _ATTEMPT.reset(token)
        if counted:
            self._count(None)
        return result

    def _count(self, failure: str | None) -> None:
        self._counts.record(CONNECTION, failed=failure == "connection")
        if failure != "connection":
            self._counts.record(TRANSACTION, failed=failure == "transaction")
