"""Protected delivery can be read while the supervised application owns its lock."""

import fcntl
import json
import os
import sys
from types import SimpleNamespace

import pytest

from scripts import u2_browser_fixtures as helper

pytestmark = pytest.mark.u2_operations


@pytest.fixture(scope="session", autouse=True)
def exclusive_environment():
    """Lock mechanics use a temporary directory and no database connection."""
    yield


@pytest.mark.parametrize("action", ["proof", "totp"])
def test_private_lookup_while_host_lock_held(tmp_path, monkeypatch, capsys, action):
    profile = SimpleNamespace(
        root=tmp_path, realm="account-controls", database_name="docsuri_u2", run_id="test-run"
    )
    monkeypatch.setattr(helper.LocalProfile, "load", lambda _: profile)
    monkeypatch.setattr(helper, "OwnerTransactions", lambda _: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(helper, "ControlEntryService", lambda *_: object())
    monkeypatch.setattr(helper, "proof_for", lambda *_: {"proof": "private-only"})
    monkeypatch.setattr(helper, "totp", lambda *_: "123456")
    helper.private_json(
        tmp_path / "browser-fixtures.json",
        {
            "runId": "test-run",
            "accounts": {"admin": {"email": "fixture@example.org", "seed": "private"}},
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "helper",
            "--environment-file",
            str(tmp_path / "environment.json"),
            "--action",
            action,
            "--alias",
            "admin",
            "--purpose",
            "verify",
        ],
    )
    fd = os.open(tmp_path / "fixture-run.lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        helper.main()
    finally:
        os.close(fd)
    output = json.loads(capsys.readouterr().out)
    assert set(output) == {"runId", "privateFile"}
    assert helper.private_json(tmp_path / "browser-proof.json")["proof"] in {
        "private-only",
        "123456",
    }
    assert (tmp_path / "browser-proof.json").stat().st_mode & 0o777 == 0o600
