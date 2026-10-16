"""Durable no-job release recovery across faults and revoked sessions."""

from uuid import uuid4

import pytest

from backend.modules.corpus.repository import CorpusRepository
from backend.modules.research.errors import ResearchError
from backend.modules.research.execution import ResearchExecution
from backend.modules.research.jobs import ResearchJobs
from backend.transactions import UnknownCommit


def test_closed_release_recovers_after_faults_restart_and_revocation(
    transactions, authority, connect, monkeypatch,
):
    corpus = CorpusRepository(transactions, None)
    codec = ResearchExecution(transactions, corpus)
    codec.usage.ensure_entitlement(authority)
    for fault in ("before-release", "unknown-release", "unknown-close"):
        context = codec.create_context(authority, "novelty")
        value = {
            "scope": {
                "contextId": str(context["id"]), "publicPapers": [], "attachmentIds": [],
                "webReferences": [], "scopePolicy": codec.policy.reference(),
            },
            "text": "Synthetic recovery", "inputMode": "topic", "policy": codec.policy.reference(),
        }
        key = str(uuid4())
        admission = codec.admission.prepare(authority, key, value)
        operation = admission["operation_id"]
        reject, close = codec.usage.reject_operation, codec.admission.close

        def failing_reject(proof):
            if fault == "before-release":
                raise RuntimeError("synthetic release unavailable")
            reject(proof)
            raise UnknownCommit("synthetic lost release acknowledgement")

        def failing_close(*args):
            close(*args)
            raise UnknownCommit("synthetic lost closure acknowledgement")

        with monkeypatch.context() as patch:
            if fault == "unknown-close":
                patch.setattr(codec.admission, "close", failing_close)
            else:
                patch.setattr(codec.usage, "reject_operation", failing_reject)
            with pytest.raises((RuntimeError, UnknownCommit)):
                codec.admission.accept_with_usage(
                    authority, key, value, "novelty-analysis", codec.usage,
                    ResearchJobs(transactions), queue_limit=0,
                )
        with connect("accounts") as conn:
            conn.execute("UPDATE accounts.session SET revoked=true WHERE id=%s", (authority.session_id,))
        try:
            restarted = ResearchExecution(transactions, corpus)
            with connect("research") as conn:
                pending = conn.execute(
                    "SELECT count(*) AS n FROM research.admission "
                    "WHERE state='closed' AND NOT release_reconciled"
                ).fetchone()["n"]
            assert pending <= 32  # Bounded fixture backlog; no unbounded recovery loop.
            for _ in range(pending + 1):
                restarted.step()
            with connect("research") as conn:
                row = conn.execute(
                    "SELECT state,release_reconciled FROM research.admission WHERE operation_id=%s",
                    (operation,),
                ).fetchone()
                assert row == {"state": "closed", "release_reconciled": True}
                assert conn.execute(
                    "SELECT count(*) AS n FROM research.job WHERE id=%s", (operation,),
                ).fetchone()["n"] == 0
            with connect("usage") as conn:
                released = conn.execute(
                    "SELECT * FROM usage.reservation WHERE operation_id=%s", (operation,),
                ).fetchone()
                assert released["disposition"] == "released"
                assert conn.execute(
                    "SELECT count(*) AS n FROM usage.rejected_operation WHERE operation_id=%s",
                    (operation,),
                ).fetchone()["n"] == 1
                revision = released["revision"]
            restarted.step()
            with connect("usage") as conn:
                assert conn.execute(
                    "SELECT revision FROM usage.reservation WHERE operation_id=%s", (operation,),
                ).fetchone()["revision"] == revision
        finally:
            with connect("accounts") as conn:
                conn.execute(
                    "UPDATE accounts.session SET revoked=false WHERE id=%s", (authority.session_id,),
                )
        with pytest.raises(ResearchError, match="CONFLICT"):
            codec.accept(authority, key, value, "novelty-analysis")
        with pytest.raises(ResearchError, match="CONFLICT"):
            ResearchJobs(transactions).accept(
                authority, kind="novelty-analysis", operation_key=key, value=value,
                usage_id=released["id"], operation_id=operation,
            )
