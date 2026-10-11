"""Canonical handoff and payload-time faults; executors are diagnostic only."""

import threading
from unittest.mock import Mock

import pytest

from backend.modules.summarization.payload import encode_payload
from backend.modules.summarization.worker import ExecutionInterrupted, WorkerIntervention
from tests.u1_integrated_paper_journey.component.test_execution_payload import fixture
from tests.u1_integrated_paper_journey.component.test_worker import DiagnosticExecutor, setup

pytestmark = pytest.mark.u1_component


def canonical(executor, *, seconds=1):
    state = setup(executor, seconds=seconds)
    bound, source = fixture()
    payload = encode_payload(bound, source)
    state.binding = payload["binding"]
    state.claims.acquire.return_value["claim"]["binding"] = state.binding
    state.claims.renew.return_value["claim"]["binding"] = state.binding
    state.claims.read_input.return_value["payload"] = bound["payload"]
    state.worker.payloads = Mock(read=Mock(return_value=payload))
    return state, payload


def test_executor_receives_generated_payload_under_constructed_worker_identity():
    executor = DiagnosticExecutor()
    executor.run = Mock(wraps=executor.run)
    state, payload = canonical(executor)
    state.worker.run(state.binding)
    assert executor.run.call_args.args[0] == payload
    assert "payload" not in executor.run.call_args.args[0]
    assert state.worker.payloads.read.call_args.kwargs == {"trusted_worker": state.worker.worker_id}


def test_canonical_acceptance_cannot_use_unbound_diagnostic_executor_path():
    executor = DiagnosticExecutor()
    state, _ = canonical(executor)
    state.worker.payloads = None
    with pytest.raises(WorkerIntervention, match="guarded payload"):
        state.worker.run(state.binding)
    assert executor.calls == 0


def test_payload_authority_loss_starts_no_executor_and_publishes_no_fact():
    executor = DiagnosticExecutor()
    state, _ = canonical(executor)
    state.worker.payloads.read.side_effect = PermissionError("injected source withdrawal")
    with pytest.raises(PermissionError):
        state.worker.run(state.binding)
    assert executor.calls == 0
    state.admission.assistance.fail.assert_not_called()
    state.admission.assistance.complete.assert_not_called()


def test_heartbeat_covers_payload_assembly_before_executor_start():
    executor = DiagnosticExecutor()
    state, payload = canonical(executor)
    reading, release = threading.Event(), threading.Event()

    def read(*args, **kwargs):
        reading.set()
        assert release.wait(0.5)
        return payload

    def renew(claim, **kwargs):
        assert reading.is_set() and executor.calls == 0
        release.set()
        return {"claim": claim}

    state.worker.payloads.read.side_effect = read
    state.claims.renew.side_effect = renew
    state.worker.run(state.binding)
    assert state.claims.renew.call_count >= 1
    assert executor.calls == 1


def test_payload_delay_consumes_original_deadline_and_never_starts_executor():
    executor = DiagnosticExecutor()
    state, payload = canonical(executor, seconds=0.04)

    def read(*args, **kwargs):
        assert executor.release.wait(0.5), "same watchdog must interrupt payload delay"
        return payload

    state.worker.payloads.read.side_effect = read
    with pytest.raises(ExecutionInterrupted):
        state.worker.run(state.binding)
    assert executor.calls == 0 and executor.aborts == 1
    state.admission.assistance.fail.assert_not_called()


def test_changed_payload_binding_cannot_reach_executor():
    executor = DiagnosticExecutor()
    state, payload = canonical(executor)
    payload["binding"] = dict(payload["binding"], inputHash="c" * 64)
    with pytest.raises(ValueError, match="differs"):
        state.worker.run(state.binding)
    assert executor.calls == 0
