"""Real owner transactions with an explicitly diagnostic executor.

These checks establish worker/accounting integration, not useful model output.
"""

from uuid import uuid4

import pytest

from backend.modules.summarization.admission import AssistanceAdmission
from backend.modules.summarization.execution import ExecutionClaims
from backend.modules.summarization.worker import ExecutionRefused, PaperWorker, PreparedExecution

pytestmark = pytest.mark.u1_repository


class DiagnosticExecutor:
    def __init__(self, *, refusal=False):
        self.refusal = refusal
        self.calls = 0

    def run(self, bound, deadline):
        self.calls += 1
        assert bound["payload"]["fixtureFamily"] == "repository-boundary"
        if self.refusal:
            raise ExecutionRefused("insufficient-result")
        return PreparedExecution(
            b"diagnostic worker fixture, not a model answer",
            {"diagnostic": True},
            {"fixtureFamily": "repository-boundary", "normalModelReadiness": False},
        )

    def abort_owned(self):
        pass

    def stopped(self):
        return True


def prepare(r, *, refusal=False):
    admission = AssistanceAdmission(r["pa"], r["usage"])
    job = admission.accept(
        r["authority"],
        uuid4(),
        {
            "versionId": r["ids"]["version"],
            "sourceHash": "a" * 64,
            "action": "summary",
            "fixtureFamily": "repository-boundary",
        },
    )
    claims = ExecutionClaims(r["pa"])
    executor = DiagnosticExecutor(refusal=refusal)
    worker = PaperWorker(uuid4(), claims, admission, executor)
    return job, worker, claims, executor


@pytest.mark.parametrize("refusal", [False, True])
def test_worker_terminal_transition_and_one_usage_effect(repositories, connect, refusal):
    r = repositories
    job, worker, claims, executor = prepare(r, refusal=refusal)
    worker.run(claims.binding(job))
    with connect("assistance") as conn:
        actual = conn.execute(
            "SELECT state,accepted_at,settlement_pending FROM assistance.job WHERE id=%s",
            (job["id"],),
        ).fetchone()
    assert actual == ("failed" if refusal else "succeeded", job["accepted_at"], False)
    reservation = r["usage"].reservation(r["authority"], job["id"])
    assert reservation["disposition"] == ("released" if refusal else "committed")
    # Duplicate delivery cannot start a second computation after terminal commit.
    with pytest.raises(ValueError):
        worker.run(claims.binding(job))
    assert executor.calls == 1
    assert r["usage"].reservation(r["authority"], job["id"]) == reservation


def test_lost_completion_reply_is_reconciled_from_owner_proof(repositories, monkeypatch):
    r = repositories
    job, worker, claims, executor = prepare(r)
    complete = r["pa"].complete

    def lost_reply(*args, **kwargs):
        complete(*args, **kwargs)
        raise ConnectionError("deliberate commit-then-lost-reply fixture")

    monkeypatch.setattr(r["pa"], "complete", lost_reply)
    with pytest.raises(ConnectionError):
        worker.run(claims.binding(job))
    assert r["usage"].reservation(r["authority"], job["id"])["disposition"] == "reserved"
    assert r["pa"].snapshot(r["authority"], job["id"])["state"] == "succeeded"
    worker.admission.reconcile_terminal()
    assert r["usage"].reservation(r["authority"], job["id"])["disposition"] == "committed"
    assert executor.calls == 1
