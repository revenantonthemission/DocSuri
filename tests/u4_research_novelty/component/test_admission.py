from uuid import uuid4

import pytest

from backend.modules.research.errors import ResearchError
from backend.modules.research.jobs import ResearchJobs
from tests.u4_research_novelty.component.test_execution import execution as execution


def test_prepare_retry_has_one_identity(execution):
    codec, authority, value = execution
    key = str(uuid4())
    first = codec.admission.prepare(authority, key, value)
    assert codec.admission.prepare(authority, key, value) == first


def test_prepare_cannot_change_input(execution):
    codec, authority, value = execution
    key = str(uuid4())
    codec.admission.prepare(authority, key, value)
    with pytest.raises(ResearchError, match="IDEMPOTENCY_CONFLICT"):
        codec.admission.prepare(authority, key, dict(value, text="changed"))


def test_reservation_before_close_is_released_once(execution):
    codec, authority, value = execution
    admission = codec.admission.prepare(authority, str(uuid4()), value)
    codec.usage.reserve(authority, admission["operation_id"], admission["input_hash"])
    proof = codec.admission.close(authority, admission["operation_id"])
    codec.usage.reject_operation(proof)
    codec.usage.reject_operation(proof)
    assert codec.usage.current(authority)["counts"] == {"released": 1}


def test_close_before_delayed_reservation_fences_it(execution):
    codec, authority, value = execution
    admission = codec.admission.prepare(authority, str(uuid4()), value)
    codec.usage.reject_operation(codec.admission.close(authority, admission["operation_id"]))
    with pytest.raises(ValueError, match="rejected"):
        codec.usage.reserve(authority, admission["operation_id"], admission["input_hash"])


def test_accepted_work_cannot_be_closed_as_rejection(execution):
    codec, authority, value = execution
    row = codec.accept(authority, str(uuid4()), value, "novelty-analysis")
    with pytest.raises(ResearchError, match="CONFLICT"):
        codec.admission.close(authority, row["id"])


def test_refused_acceptance_closes_before_usage_release(execution):
    codec, authority, value = execution
    with pytest.raises(ResearchError, match="CAPACITY_EXHAUSTED"):
        codec.admission.accept_with_usage(
            authority,
            str(uuid4()),
            value,
            "novelty-analysis",
            codec.usage,
            ResearchJobs(codec.transactions),
            queue_limit=0,
        )
    assert codec.usage.current(authority)["counts"] == {"released": 1}
