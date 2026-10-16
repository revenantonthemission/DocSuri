from contextlib import contextmanager

import psycopg
import pytest

from scripts import verify_docsuri_u4 as runner


def endpoint(name):
    class Connection:
        def execute(self, query):
            assert query in {"SET LOCAL statement_timeout=1000", "SELECT current_database()"}
            return self

        def fetchone(self):
            return (name,)

    return Connection()


def test_waits_for_actual_authenticated_endpoint_after_transient_bootstrap(monkeypatch):
    attempts = []

    @contextmanager
    def connect(value):
        attempts.append(value)
        if len(attempts) < 3:
            raise psycopg.OperationalError("synthetic server transition")
        yield endpoint(runner.DATABASE)

    sleeps = []
    monkeypatch.setattr(runner, "connect_admin", connect)
    monkeypatch.setattr(runner.time, "sleep", sleeps.append)
    runner.wait_database_endpoint({"runId": "synthetic"})
    assert len(attempts) == 3 and sleeps == [0.5, 0.5]


def test_wrong_database_fails_closed_without_retry(monkeypatch):
    @contextmanager
    def connect(_):
        yield endpoint("foreign")

    monkeypatch.setattr(runner, "connect_admin", connect)
    with pytest.raises(runner.Refused, match="identity differs"):
        runner.wait_database_endpoint({})


def test_endpoint_wait_retains_finite_attempt_budget(monkeypatch):
    attempts = []

    def connect(_):
        attempts.append(1)
        raise psycopg.OperationalError("synthetic unavailable; must not be printed")

    monkeypatch.setattr(runner, "connect_admin", connect)
    monkeypatch.setattr(runner.time, "sleep", lambda _: None)
    with pytest.raises(runner.Refused, match="TCP startup failed") as error:
        runner.wait_database_endpoint({})
    assert len(attempts) == 30
    assert "must not be printed" not in str(error.value)
