"""Deliberate executor/transport faults, not normal model-quality evidence."""

import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from backend.modules.summarization.worker import (
    ExecutionInterrupted,
    ExecutionRefused,
    PaperWorker,
    PreparedExecution,
    WorkerIntervention,
)

pytestmark = pytest.mark.u1_component


class DiagnosticExecutor:
    def __init__(self, *, wait=False, refuses=None, confirm_stop=True):
        self.wait = wait
        self.refuses = refuses
        self.confirm_stop = confirm_stop
        self.started = threading.Event()
        self.release = threading.Event()
        self.finished = threading.Event()
        self.calls = 0
        self.aborts = 0
        self.deadline = None

    def run(self, bound, deadline):
        self.calls += 1
        self.deadline = deadline
        self.started.set()
        try:
            if self.wait:
                self.release.wait(2)
            if self.refuses:
                raise ExecutionRefused(self.refuses)
            return PreparedExecution(b"diagnostic-only", {}, {"diagnostic": True})
        finally:
            self.finished.set()

    def abort_owned(self):
        self.aborts += 1
        self.release.set()

    def stopped(self):
        return not self.started.is_set() or (self.finished.is_set() and self.confirm_stop)


def setup(executor, *, seconds=1):
    binding = {"operationId": str(uuid4()), "inputHash": "a" * 64}
    claim = {
        "binding": binding,
        "workerId": str(uuid4()),
        "leaseId": str(uuid4()),
        "fence": 1,
        "leaseRevision": str(uuid4()),
    }
    claims = Mock()
    claims.acquire.return_value = {"claim": claim}
    claims.read_input.return_value = {"remainingSeconds": seconds, "jobRevision": str(uuid4())}
    claims.renew.return_value = {"claim": dict(claim)}
    admission = Mock()
    admission.assistance.complete.return_value = {"state": "succeeded"}
    admission.assistance.fail.return_value = {"state": "failed"}
    worker = PaperWorker(uuid4(), claims, admission, executor)
    # Compressed diagnostic time only; production constants remain 10s / 5s.
    worker.HEARTBEAT_SECONDS = 0.01
    worker.STOP_SECONDS = 0.1
    return SimpleNamespace(worker=worker, binding=binding, claims=claims, admission=admission)


def test_diagnostic_success_uses_constructed_identity_and_settles_after_commit():
    executor = DiagnosticExecutor()
    s = setup(executor)
    before = time.monotonic()
    assert s.worker.run(s.binding) == {"state": "succeeded"}
    assert s.claims.acquire.call_args.args == (s.binding, s.worker.worker_id)
    assert before < executor.deadline <= time.monotonic() + 1
    s.admission.assistance.complete.assert_called_once()
    s.admission.settle_terminal.assert_called_once()
    assert executor.aborts == 0 and executor.stopped()


def test_current_lease_renews_while_executor_is_blocked():
    executor = DiagnosticExecutor(wait=True)
    s = setup(executor)

    def renewed(claim, **kwargs):
        assert executor.started.is_set() and not executor.finished.is_set()
        executor.release.set()
        return {"claim": dict(claim, leaseRevision=str(uuid4()))}

    s.claims.renew.side_effect = renewed
    s.worker.run(s.binding)
    s.claims.renew.assert_called_once()
    assert executor.aborts == 0


def test_lease_loss_aborts_and_confirms_stop_without_any_terminal_fact():
    executor = DiagnosticExecutor(wait=True)
    s = setup(executor)
    s.claims.renew.side_effect = PermissionError("replaced worker")
    with pytest.raises(ExecutionInterrupted):
        s.worker.run(s.binding)
    assert executor.aborts == 1 and executor.stopped()
    s.admission.assistance.complete.assert_not_called()
    s.admission.assistance.fail.assert_not_called()
    s.admission.settle_terminal.assert_not_called()


def test_original_deadline_aborts_even_while_renewal_reply_is_delayed():
    executor = DiagnosticExecutor(wait=True)
    s = setup(executor, seconds=0.04)

    def slow_renew(claim, **kwargs):
        assert executor.finished.wait(0.5), "deadline timer must stop computation during DB wait"
        return {"claim": claim}

    s.claims.renew.side_effect = slow_renew
    with pytest.raises(ExecutionInterrupted):
        s.worker.run(s.binding)
    assert executor.aborts == 1 and executor.stopped()
    s.admission.assistance.fail.assert_not_called()
    s.admission.settle_terminal.assert_not_called()


def test_unconfirmed_stop_quarantines_worker_and_prevents_new_acquisition():
    executor = DiagnosticExecutor(wait=True, confirm_stop=False)
    s = setup(executor)
    s.claims.renew.side_effect = PermissionError("lost authority")
    with pytest.raises(WorkerIntervention):
        s.worker.run(s.binding)
    executor.confirm_stop = True
    with pytest.raises(WorkerIntervention):
        s.worker.run(s.binding)
    assert executor.calls == 1
    s.claims.acquire.assert_called_once()
    s.admission.assistance.complete.assert_not_called()


def test_conclusive_insufficient_output_records_failure_before_settlement():
    s = setup(DiagnosticExecutor(refuses="insufficient-result"))
    assert s.worker.run(s.binding) == {"state": "failed"}
    assert s.admission.assistance.fail.call_args.args[-1] == "insufficient-result"
    s.admission.assistance.complete.assert_not_called()
    s.admission.settle_terminal.assert_called_once()


def test_unknown_completion_reply_never_creates_failure_or_releases_usage():
    s = setup(DiagnosticExecutor())
    s.admission.assistance.complete.side_effect = ConnectionError("committed reply lost")
    with pytest.raises(ConnectionError):
        s.worker.run(s.binding)
    s.admission.assistance.fail.assert_not_called()
    s.admission.settle_terminal.assert_not_called()


def test_exhausted_original_budget_starts_no_executor():
    executor = DiagnosticExecutor()
    s = setup(executor, seconds=0)
    with pytest.raises(ExecutionInterrupted):
        s.worker.run(s.binding)
    assert executor.calls == 0
    s.admission.assistance.fail.assert_not_called()


def test_timer_start_failure_still_aborts_begun_execution(monkeypatch):
    executor = DiagnosticExecutor(wait=True)
    s = setup(executor)

    class FailedTimer:
        def __init__(self, *args):
            pass

        def start(self):
            assert executor.started.wait(0.5)
            raise RuntimeError("deliberate watchdog thread exhaustion")

        def cancel(self):
            pass

        def join(self, **kwargs):
            raise AssertionError("must not join an unstarted timer")

    monkeypatch.setattr("backend.modules.summarization.worker.threading.Timer", FailedTimer)
    with pytest.raises(ExecutionInterrupted):
        s.worker.run(s.binding)
    assert executor.aborts == 1 and executor.stopped()
    s.admission.assistance.complete.assert_not_called()
    s.admission.assistance.fail.assert_not_called()


def test_abort_thread_start_failure_quarantines_without_unbounded_inline_abort(monkeypatch):
    executor = DiagnosticExecutor(wait=True)
    s = setup(executor, seconds=0.01)
    original_start = threading.Thread.start

    def fail_supervisors(thread):
        if thread.name == "docsuri-owned-execution":
            return original_start(thread)
        assert executor.started.wait(0.5)
        raise RuntimeError("deliberate supervisor thread exhaustion")

    monkeypatch.setattr(threading.Thread, "start", fail_supervisors)
    try:
        with pytest.raises(WorkerIntervention, match="abort supervisor"):
            s.worker.run(s.binding)
        assert executor.aborts == 0  # No potentially blocking synchronous fallback.
        with pytest.raises(WorkerIntervention):
            s.worker.run(s.binding)
        s.claims.acquire.assert_called_once()
        s.admission.assistance.complete.assert_not_called()
    finally:
        # Only the diagnostic executor's explicit test-owned release; production
        # quarantine cannot claim that abort was ever acknowledged.
        executor.release.set()
        assert executor.finished.wait(0.5)
