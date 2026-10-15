"""Deliberate owner-boundary failures; normal persistence uses repository tests."""

from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from backend.modules.summarization.admission import AssistanceAdmission
from backend.transactions import Authority, UnknownCommit

pytestmark = pytest.mark.u1_component


def owners():
    operation, reservation = uuid4(), uuid4()
    pa = SimpleNamespace(
        prepare=Mock(return_value={"disposition": "open", "intent_hash": "a" * 64}),
        accept=Mock(return_value={"id": operation}),
        settlement_proof=Mock(
            return_value={
                "operation": operation,
                "reservation": reservation,
                "disposition": "committed",
                "proofHash": "b" * 64,
            }
        ),
        confirm_settlement=Mock(),
        confirm_rejection=Mock(),
        rejected_admission_proof=Mock(return_value={"intentHash": "a" * 64, "proofHash": "c" * 64}),
    )
    usage = SimpleNamespace(
        reserve=Mock(return_value={"id": reservation}),
        reservation=Mock(return_value={"id": reservation, "intent_hash": "a" * 64}),
        settle=Mock(return_value={"diagnostic": True}),
        reject_operation=Mock(),
        transactions=SimpleNamespace(profile=SimpleNamespace(realm="journey")),
    )
    return AssistanceAdmission(pa, usage), pa, usage, Authority(uuid4(), uuid4()), operation


def test_unknown_reservation_does_not_accept_or_release():
    service, pa, usage, authority, operation = owners()
    usage.reserve.side_effect = UnknownCommit("injected reservation reply loss")
    with pytest.raises(UnknownCommit):
        service.accept(authority, operation, {"diagnostic": True})
    pa.accept.assert_not_called()
    usage.settle.assert_not_called()


def test_unknown_acceptance_never_timeout_releases():
    service, pa, usage, authority, operation = owners()
    pa.accept.side_effect = UnknownCommit("injected acceptance reply loss")
    with pytest.raises(UnknownCommit):
        service.accept(authority, operation, {"diagnostic": True})
    usage.settle.assert_not_called()


def test_rejected_original_intent_is_not_automatically_restarted():
    service, pa, usage, authority, operation = owners()
    pa.prepare.return_value["disposition"] = "rejected"
    with pytest.raises(ValueError, match="rejected"):
        service.accept(authority, operation, {})
    usage.reserve.assert_not_called()


def test_missing_terminal_proof_cannot_reach_usage_effect():
    service, pa, usage, _, operation = owners()
    pa.settlement_proof.side_effect = ValueError("no durable terminal proof")
    with pytest.raises(ValueError):
        service.settle_terminal(operation)
    usage.settle.assert_not_called()


def test_lost_settlement_reply_does_not_acknowledge_pa_obligation():
    service, pa, usage, _, operation = owners()
    usage.settle.side_effect = UnknownCommit("injected settlement reply loss")
    with pytest.raises(UnknownCommit):
        service.settle_terminal(operation)
    pa.confirm_settlement.assert_not_called()


def test_rejected_admission_cannot_release_another_input_or_create_absent_reservation():
    service, _, usage, authority, operation = owners()
    usage.reservation.return_value["intent_hash"] = "d" * 64
    with pytest.raises(ValueError, match="does not match"):
        service.release_rejected(authority, operation)
    usage.settle.assert_not_called()
    usage.reservation.return_value = None
    assert service.release_rejected(authority, operation) is None
    usage.reserve.assert_not_called()
