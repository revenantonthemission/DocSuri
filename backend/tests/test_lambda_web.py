"""backend.lambda_web — dev-profile API Lambda web bootstrap (serverless-plan Phase 1-③)."""

from __future__ import annotations

import json
import os

import pytest

from backend import lambda_web


@pytest.fixture(autouse=True)
def _hermetic_env(monkeypatch):
    """Keep bootstrap tests off the developer's AWS/DB env (no real secret fetch or DSN)."""
    for var in ("DB_SECRET_ARN", "DB_PASSWORD", "DB_HOST", "DB_PORT", "DB_NAME", "DB_USER",
                "DATABASE_URL"):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture()
def exec_recorder(monkeypatch):
    """Replace os.execvp with a recorder — main() must never exec for real under test."""
    calls: list[tuple[str, list[str]]] = []
    monkeypatch.setattr(os, "execvp", lambda file, args: calls.append((file, list(args))))
    return calls


def test_execs_uvicorn_exactly_like_the_image_cmd(exec_recorder):
    lambda_web.main()

    assert exec_recorder == [
        (
            "python",
            [
                "python", "-m", "uvicorn", "backend.main:app",
                "--host", "0.0.0.0", "--port", "8000",
            ],
        )
    ]


def test_fetches_db_secret_and_assembles_database_url(monkeypatch, exec_recorder):
    fetched: list[str] = []

    class _FakeSecrets:
        def get_secret_value(self, SecretId):  # noqa: N803 — boto3 API shape
            fetched.append(SecretId)
            return {"SecretString": json.dumps({"password": "p@ss word"})}

    import boto3

    monkeypatch.setattr(boto3, "client", lambda service: _FakeSecrets())
    monkeypatch.setenv("DB_SECRET_ARN", "arn:aws:secretsmanager:apne2:1:secret:db-x")
    monkeypatch.setenv("DB_HOST", "db.dev.internal")
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.setenv("DB_NAME", "docsuri")
    monkeypatch.setenv("DB_USER", "docsuri_admin")

    lambda_web.main()

    assert fetched == ["arn:aws:secretsmanager:apne2:1:secret:db-x"]
    assert os.environ["DB_PASSWORD"] == "p@ss word"
    # DSN assembled from the ECS-shaped DB_* split, password URL-quoted (config.py rules).
    assert os.environ["DATABASE_URL"] == (
        "postgresql+psycopg://docsuri_admin:p%40ss%20word@db.dev.internal:5432/docsuri"
    )
    assert exec_recorder, "must still exec uvicorn after injecting credentials"


def test_existing_db_password_skips_secret_fetch(monkeypatch, exec_recorder):
    def _boom(*_a, **_k):
        raise AssertionError("secret fetch must be skipped when DB_PASSWORD is already set")

    import boto3

    monkeypatch.setattr(boto3, "client", _boom)
    monkeypatch.setenv("DB_SECRET_ARN", "arn:aws:secretsmanager:apne2:1:secret:db-x")
    monkeypatch.setenv("DB_PASSWORD", "already-there")

    lambda_web.main()

    assert os.environ["DB_PASSWORD"] == "already-there"
    assert exec_recorder
