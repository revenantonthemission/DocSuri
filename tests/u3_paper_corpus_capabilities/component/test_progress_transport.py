"""U3 progress transport component behavior: frames, ordering, terminal state.

Covers the recorded defect dispositions: Q-01 (ordering field present), Q-02
(result shape/semantics), Q-03 (real dispatch reachable), Q-04 (valid frames
consumed without escaped-newline artifacts).
"""

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from backend.modules.summarization.local_http import _frame, snapshot_dto
from backend.modules.summarization.local_result import decode_result, encode_result

pytestmark = pytest.mark.u3_component


def job(**overrides):
    value = {
        "id": uuid4(),
        "account_id": uuid4(),
        "state": "running",
        "revision": uuid4(),
        "sequence": 3,
        "accepted_at": datetime.now(UTC),
        "failure_code": None,
    }
    value.update(overrides)
    return value


def test_progress_frames_are_valid_sse_without_escaped_newline_artifacts():
    payload = {"jobId": "j-1", "state": "running", "sequence": 4, "note": "줄바꿈\n포함"}
    frame = _frame(4, "progress", payload).decode()
    lines = frame.split("\n\n")
    assert lines[-1] == "", "frames terminate with a blank line"
    body = lines[0].split("\n")
    assert body[0] == "id: 4"
    assert body[1] == "event: progress"
    assert body[2].startswith("data: ")
    data = json.loads(body[2][len("data: ") :])
    assert data == payload
    # No unescaped newline may appear inside a data line: splitting the frame on
    # newline yields exactly the three declared lines.
    assert len(body) == 3


def test_progress_frames_without_identifier_are_still_valid():
    frame = _frame(None, "error", {"code": "FORBIDDEN"}).decode()
    body = frame.split("\n\n")[0].split("\n")
    assert body[0] == "event: error"
    assert json.loads(body[1][len("data: ") :])["code"] == "FORBIDDEN"


def test_snapshot_exposes_the_ordering_field_and_revision():
    """Q-01: the mounted job state carries the owner-allocated ordering field."""
    for state in ("accepted", "running"):
        value = snapshot_dto(job(state=state), None)
        assert value["seq"] == 3
        assert value["state"] == state
        assert value["progress"] == {"mode": "indeterminate"}
    terminal = snapshot_dto(job(state="succeeded"), None)
    assert terminal["progress"] == {"mode": "determinate", "current": 1, "total": 1}


def test_result_reference_and_failure_are_typed_and_bounded():
    """Q-02: ready results carry a usable reference; failures carry a safe error."""
    result_row = {
        "id": uuid4(),
        "revision": uuid4(),
        "output_hash": "a" * 64,
        "availability": "retained",
    }
    value = snapshot_dto(job(state="succeeded"), {
        "resultId": str(result_row["id"]),
        "revision": str(result_row["revision"]),
        "contentHash": result_row["output_hash"],
        "mediaType": "application/json",
    })
    assert value["result"]["contentHash"] == "a" * 64
    failed = snapshot_dto(job(state="failed", failure_code="dependency-unavailable"), None)
    assert failed["error"]["code"] == "DEPENDENCY_UNAVAILABLE"
    assert failed["error"]["retryable"] is True
    unknown = snapshot_dto(job(state="failed", failure_code="mystery"), None)
    assert unknown["error"]["code"] == "INTERNAL_ERROR"
    assert unknown["error"]["retryable"] is False


def test_terminal_state_cannot_regress_through_any_event(
    transactions, accepted_job, assistance, connect
):
    """Progress and terminal state are one authoritative monotonic sequence."""
    job_row, _, _ = accepted_job()
    claims = assistance["claims"]
    claim = claims.acquire(claims.binding(job_row), uuid4())["claim"]
    with connect("assistance") as conn:
        with pytest.raises(Exception) as denial:
            conn.execute(
                "UPDATE assistance.job SET sequence=sequence-1 WHERE id=%s", (job_row["id"],)
            )
            conn.commit()
        assert "cannot regress" in str(denial.value)
        conn.rollback()
        with pytest.raises(Exception) as terminal_denial:
            conn.execute(
                "UPDATE assistance.job SET state='succeeded' WHERE id=%s AND state='running'",
                (job_row["id"],),
            )
            conn.execute(
                "UPDATE assistance.job SET state='accepted' WHERE id=%s", (job_row["id"],)
            )
            conn.commit()
        assert "cannot regress" in str(terminal_denial.value)
        conn.rollback()
    assert claim["fence"] == 1


def test_ordered_replay_recovers_without_regression(
    transactions, accepted_job, assistance, authority
):
    job_row, _, _ = accepted_job()
    claims = assistance["claims"]
    claims.acquire(claims.binding(job_row), uuid4())
    repository = assistance["repository"]
    events = repository.events(authority, job_row["id"], 0)
    assert events, "claiming appends an ordered progress event"
    # Reconnect after a known event resumes exactly after it.
    after = repository.events(authority, job_row["id"], events[-1]["sequence"])
    assert after == []
    snapshot = repository.snapshot(authority, job_row["id"])
    assert snapshot["sequence"] == events[-1]["sequence"]


def test_synthetic_result_document_roundtrips_without_fabrication():
    sections = [
        {"sectionId": "s1", "heading": "Intro", "text": "본문", "anchor": "a1"},
        {"sectionId": "s2", "heading": "Method", "text": "방법", "anchor": "a2"},
    ]
    raw = encode_result(sections=sections, citations=["a1", "a2"], definitions=[])
    document = decode_result(raw)
    assert [section["text"] for section in document["sections"]] == ["본문", "방법"]
    with pytest.raises(ValueError):
        decode_result(b'{"sections": []}')
