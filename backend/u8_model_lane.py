"""The shared model runtime's lane of one in the workers (U8 plan Step 21; your decision
of 2026-10-24, "Build the research executor"; performance-design § 3.3).

One thread takes research's `execute_next` and paper assistance's
`dispatch.run_once(limit=1)` in turn. A turn asks each owner, in order, whether it has
claimable work and whether its executor is available, and only then takes the runtime's
lane with `runtime.work(90, wait=0)`, before any claim, and runs one item with that work
item's deadline. The lane runs outside the workers pass's deadline, so every owner
transaction keeps its own 5 s bound while model time is bounded by 90 s.

- A failing item is set aside as an incident (`set_aside(kind, identity, error)`), and
  the next owner runs.
- A turn in which nothing ran sleeps `poll_seconds`: every owner skipped, busy, idle or
  set aside, or paper assistance executing nothing (`{"executed": 0, ...}`, only
  deferred). Consecutive turns with a set-aside and nothing run back off, doubling the
  sleep up to `BACKOFF_CEILING_SECONDS`, so an outage (the database stopped during a
  restore, a rollback's recreate or a restart) neither spins a core nor floods the log
  and the ledger lock.
- A thread that stopped without being asked reads `lane-behind-deadline` on
  `background.work` (`status()`).
- Building the lane starts nothing; `stop()` returns within `stop_seconds` (10 s) and
  leaves an item in hand to its lease.
- The clock and the sleep are injected, so tests make no real waits.

Production only (`model_lane(composition)`): the composed realm keeps its synthetic
executors in the workers pass (BR7.1). This module imports no ServiceOperations module.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass

WORK_SECONDS = 90.0
# The longest sleep after repeated set-aside turns (the lane's poll bound).
BACKOFF_CEILING_SECONDS = 60.0
# What an owner's turn reports when it ran no item.
NO_WORK = frozenset({"skipped", "busy", "idle", "set-aside"})


def ran_an_item(value: object) -> bool:
    """Whether one owner's turn ran an item: research's outcome other than `NO_WORK`, or
    paper assistance's pass with at least one item executed (a pass that only deferred
    ran nothing)."""
    if isinstance(value, dict):
        return bool(value.get("executed"))
    return value not in NO_WORK


@dataclass(frozen=True)
class LaneOwner:
    """One owner of model work: whether it has claimable work, whether its executor is
    available, and how one item runs with the work item's deadline."""

    name: str
    claimable: Callable[[], bool]
    available: Callable[[], bool]
    run_one: Callable[[float], object]


class ModelLane:
    def __init__(self, owners, *, runtime, set_aside: Callable[[str, str, BaseException], None],
                 clock: Callable[[], float], sleep: Callable[[float], None] | None = None,
                 poll_seconds: float = 2.0, stop_seconds: float = 10.0):
        self.owners = tuple(owners)
        if not self.owners or len({owner.name for owner in self.owners}) != len(self.owners):
            raise ValueError("the lane needs distinct owners")
        if not (0 < poll_seconds <= 60 and 0 < stop_seconds <= 10):
            raise ValueError("lane timing outside its bound")
        self.runtime, self.set_aside, self.clock = runtime, set_aside, clock
        self.poll_seconds, self.stop_seconds = poll_seconds, stop_seconds
        self._stopping = threading.Event()
        self._sleep = sleep or self._stopping.wait
        self._thread: threading.Thread | None = None
        self.turns = 0
        self.last: dict[str, object] = {}
        self._quiet_set_asides = 0

    # --- one turn ---------------------------------------------------------------------

    def turn(self) -> dict[str, object]:
        """Each owner in order: claimable, then available, then the lane, then one item.
        Returns what each owner did this turn (`skipped`, `busy`, its item's outcome, or
        `set-aside`)."""
        from backend.modules.summarization.model_runtime import LaneBusy

        done: dict[str, object] = {}
        for owner in self.owners:
            if self._stopping.is_set():
                break
            try:
                if not (owner.claimable() and owner.available()):
                    done[owner.name] = "skipped"
                    continue
                with self.runtime.work(WORK_SECONDS, wait=0) as deadline:
                    done[owner.name] = owner.run_one(deadline)
            except LaneBusy:
                done[owner.name] = "busy"
            except Exception as error:  # noqa: BLE001 - recorded by kind, never its content
                done[owner.name] = "set-aside"
                self.set_aside(f"model-lane:{owner.name}", "turn", error)
        self.turns += 1
        self.last = done
        return done

    # --- the thread -------------------------------------------------------------------

    def pause_after(self, done: dict[str, object]) -> float | None:
        """How long to sleep after a turn: None when an item ran; `poll_seconds` after a
        quiet turn; doubling, up to the ceiling, for each further quiet turn that set an
        owner aside."""
        if any(ran_an_item(value) for value in done.values()):
            self._quiet_set_asides = 0
            return None
        if "set-aside" not in done.values():
            self._quiet_set_asides = 0
            return self.poll_seconds
        self._quiet_set_asides += 1
        factor = 2 ** min(self._quiet_set_asides - 1, 16)
        # `poll_seconds` is at most 60 s (the constructor's bound), so the ceiling holds.
        return min(self.poll_seconds * factor, BACKOFF_CEILING_SECONDS)

    def _run(self) -> None:
        while not self._stopping.is_set():
            pause = self.pause_after(self.turn())
            if pause is not None and not self._stopping.is_set():
                self._sleep(pause)

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("the model lane runs once")
        self._thread = threading.Thread(target=self._run, name="docsuri-model-lane",
                                        daemon=True)
        self._thread.start()

    def stop(self) -> bool:
        """Ask the thread to stop and wait at most `stop_seconds`; an item in hand is
        left to its lease. True once the thread has ended."""
        self._stopping.set()
        if self._thread is None:
            return True
        self._thread.join(self.stop_seconds)
        return not self._thread.is_alive()

    def status(self) -> dict:
        """`deadline` once the thread has ended without being asked (the workers'
        `background.work` then reads `lane-behind-deadline`)."""
        if self._thread is None:
            return {"state": "idle"}
        if self._thread.is_alive():
            return {"state": "running", "turns": self.turns}
        return {"state": "stopped" if self._stopping.is_set() else "deadline"}


def lane_owners(composition) -> list[LaneOwner]:
    """Research first, then paper assistance, from the production composition."""
    owners = []
    research = composition.parts.get("research-workspace") or {}
    execution = research.get("execution")
    if execution is not None and callable(getattr(execution, "execute_next", None)):
        owners.append(LaneOwner(
            "research", execution.claimable, execution.provider.available,
            lambda deadline: execution.execute_next(deadline=deadline),
        ))
    corpus = composition.parts.get("paper-corpus") or {}
    dispatch, runtime = corpus.get("dispatch"), corpus.get("runtime")
    if dispatch is not None and callable(getattr(dispatch.executor, "available", None)):
        def assist(deadline: float):
            # PaperAssistance's worker runs the executor on a thread of its own, so the
            # lane hands its work item to that one thread for this item.
            with runtime.hand_over():
                return dispatch.run_once(limit=1)

        owners.append(LaneOwner(
            "assistance", lambda: bool(dispatch.repository.pending(1)),
            dispatch.executor.available, assist,
        ))
    return owners


def model_lane(composition, *, clock=None, sleep=None) -> ModelLane | None:
    """The production composition's lane, built but not started; None in any synthetic
    profile, or while no owner has a real executor on the runtime."""
    import time

    if not getattr(composition.profile, "is_production", False):
        return None
    corpus = composition.parts.get("paper-corpus") or {}
    runtime = corpus.get("runtime")
    owners = lane_owners(composition)
    if runtime is None or not owners:
        return None
    from backend.u8_host import lane_set_aside

    return ModelLane(owners, runtime=runtime, set_aside=lane_set_aside(composition),
                     clock=clock or time.monotonic, sleep=sleep)
