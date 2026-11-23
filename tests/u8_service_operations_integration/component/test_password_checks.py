"""Password checks run one at a time and wait at most two seconds (U8 plan Step 54(f);
NFR8.3).

Every `hasher.hash` and `hasher.verify` call the complete entry makes runs while the one
process-wide `BoundedSemaphore(1)` is held, and every acquire waits at most 2 s. The test
wraps the real semaphore in a pass-through recorder; each entry is built before the
semaphore is recorded, because its constructor hashes a dummy password.
"""

from __future__ import annotations

import contextvars
import threading
import time
from uuid import uuid4

import pytest

from backend.modules.accounts.services.control_entry import ControlEntryService
from backend.modules.accounts.services.guarded_entry import GuardedEntryService
from backend.modules.accounts.u8_control_policy import U8_SYNTHETIC_POLICY
from backend.modules.accounts.u8_entry import CompleteControlEntryService
from backend.transactions import Busy
from tests.u8_service_operations_integration.conftest import SIGN_IN_PASSWORD

pytestmark = pytest.mark.usefixtures("own_address")


class Recorded:
    """A pass-through recorder of the real semaphore: each acquire's timeout, and which
    thread holds it now."""

    def __init__(self, real, *, refuse: bool = False):
        self.real, self.refuse = real, refuse
        self.timeouts: list[float | None] = []
        self.holder: int | None = None

    def acquire(self, blocking: bool = True, timeout: float | None = None) -> bool:
        self.timeouts.append(timeout)
        if self.refuse:
            return False
        acquired = self.real.acquire(blocking, timeout) if timeout is not None else (
            self.real.acquire(blocking))
        if acquired:
            self.holder = threading.get_ident()
        return acquired

    def release(self) -> None:
        self.holder = None
        self.real.release()


class CheckedHasher:
    """The entry's hasher, each call checked to run while the semaphore is held; `verify`
    can be slowed, and records when each call started and ended."""

    def __init__(self, inner, recorder: Recorded, *, slow: float = 0.0):
        self.inner, self.recorder, self.slow = inner, recorder, slow
        self.calls: list[tuple[str, bool]] = []
        self.spans: list[tuple[float, float]] = []
        self.lock = threading.Lock()

    def _held(self) -> bool:
        return self.recorder.holder == threading.get_ident()

    def hash(self, password: str) -> str:
        with self.lock:
            self.calls.append(("hash", self._held()))
        return self.inner.hash(password)

    def verify(self, encoded: str, password: str) -> bool:
        started = time.monotonic()
        with self.lock:
            self.calls.append(("verify", self._held()))
        if self.slow:
            time.sleep(self.slow)
        try:
            return self.inner.verify(encoded, password)
        finally:
            with self.lock:
                self.spans.append((started, time.monotonic()))

    def __getattr__(self, name):
        return getattr(self.inner, name)


def test_password_checks_run_one_at_a_time_and_wait_two_seconds(
    transactions, sign_in_account, monkeypatch, clock,
):
    _, email = sign_in_account("sign-in-member")
    # One semaphore per process: every entry class shares the same object.
    assert (GuardedEntryService._credential_work is ControlEntryService._credential_work
            is CompleteControlEntryService._credential_work)
    entry = CompleteControlEntryService(transactions, U8_SYNTHETIC_POLICY, clock=clock)
    assert entry._credential_work is GuardedEntryService._credential_work
    recorder = Recorded(GuardedEntryService._credential_work)
    monkeypatch.setattr(GuardedEntryService, "_credential_work", recorder)
    hasher = CheckedHasher(entry.hasher, recorder)
    entry.hasher = hasher

    signed_in = entry.login(email, SIGN_IN_PASSWORD, flow_binding="d1")
    assert signed_in.public["state"] == "authenticated"
    entry._hash_password(f"Synthetic-{uuid4().hex[:12]}-A1!")  # generated per run (L1-36)
    assert {name for name, _ in hasher.calls} == {"hash", "verify"}
    assert all(held for _, held in hasher.calls)
    assert recorder.timeouts and set(recorder.timeouts) == {2}

    # Two concurrent sign-ins, `verify` slowed to 0.3 s: the second starts after the first.
    slowed = CheckedHasher(hasher.inner, recorder, slow=0.3)
    entry.hasher = slowed
    answers, errors = [], []

    def sign_in():
        try:
            answers.append(entry.login(email, SIGN_IN_PASSWORD, flow_binding="d1"))
        except Exception as error:  # noqa: BLE001 - reported by the assertion below
            errors.append(error)

    workers = [threading.Thread(target=contextvars.copy_context().run, args=(sign_in,))
               for _ in range(2)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=10)
    assert errors == [] and len(answers) == 2
    assert all(answer.public["state"] == "authenticated" for answer in answers)
    first, second = sorted(slowed.spans)
    assert second[0] >= first[1]
    assert all(held for _, held in slowed.calls)
    assert set(recorder.timeouts) == {2}

    # A recorder whose acquire refuses: the busy answer, and the hasher is never called.
    refusing = Recorded(recorder.real, refuse=True)
    monkeypatch.setattr(GuardedEntryService, "_credential_work", refusing)
    untouched = CheckedHasher(hasher.inner, refusing)
    entry.hasher = untouched
    for call, args in ((entry._matches_password, ("encoded", SIGN_IN_PASSWORD)),
                       (entry._hash_password, (f"Synthetic-{uuid4().hex[:12]}-A1!",))):
        with pytest.raises(Busy, match="local credential work allocation exhausted"):
            call(*args)
    assert untouched.calls == [] and refusing.timeouts == [2, 2]
