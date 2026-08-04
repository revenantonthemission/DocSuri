"""backend.lambda_entry — dev-profile Lambda cron dispatcher (serverless-plan Phase 1-②)."""

from __future__ import annotations

import pytest

from backend import lambda_entry


@pytest.fixture(autouse=True)
def _hermetic_env(monkeypatch):
    """Keep dispatch tests off the developer's AWS/DB env (no secret fetch, no DSN assembly)."""
    monkeypatch.delenv("DB_SECRET_ARN", raising=False)
    monkeypatch.delenv("DB_HOST", raising=False)


def test_dispatches_personalization_maintenance(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(
        "backend.modules.personalization.maintenance.run",
        lambda: calls.append("maintenance") or 0,
    )

    result = lambda_entry.handler({"job": "personalization_maintenance"}, None)

    assert calls == ["maintenance"]
    assert result == {"job": "personalization_maintenance", "status": "ok"}


def test_dispatches_account_purge(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(
        "backend.modules.accounts.purge_worker.main",
        lambda: calls.append("purge") or 0,
    )

    result = lambda_entry.handler({"job": "account_purge"}, None)

    assert calls == ["purge"]
    assert result == {"job": "account_purge", "status": "ok"}


def test_unknown_job_raises_value_error():
    with pytest.raises(ValueError, match="unknown job"):
        lambda_entry.handler({"job": "mystery"}, None)


def test_missing_job_raises_value_error():
    with pytest.raises(ValueError, match="unknown job"):
        lambda_entry.handler({}, None)
    with pytest.raises(ValueError, match="unknown job"):
        lambda_entry.handler(None, None)


def test_nonzero_exit_status_raises(monkeypatch):
    monkeypatch.setattr("backend.modules.accounts.purge_worker.main", lambda: 2)

    with pytest.raises(RuntimeError, match="exited with status 2"):
        lambda_entry.handler({"job": "account_purge"}, None)
