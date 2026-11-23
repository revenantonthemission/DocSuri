"""The operator tool's recovery words (U8 plan Steps 29–30; BR4.2, BR4.7, BR4.10).

`recovery backup | verify | restore | retire-volume` each take one request (or the
retirement's decision) as bounded JSON and run a sequence of bound operations; anything
else is refused before a procedure runs. The production wiring is refused until the
production environment tool brings the operator's released credentials (Step 37).
"""

from __future__ import annotations

import io
import json
import sys

import pytest

from docsuri_ops.platform_control.errors import ControlError
from docsuri_ops.u8_platform import operator_tool as cli
from docsuri_ops.u8_platform.recovery_words import CONTINUATIONS, WORDS, run_word


class Procedures:
    """Records which procedure a word reached and with what."""

    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def call(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return {"called": name}

        return call


@pytest.mark.parametrize(("word", "document", "expected"), [
    ("backup", {"recoveryRequestId": "r"}, ("backup", ("r",), {"via": "in-person"})),
    ("verify", {"recoveryRequestId": "r"}, ("verify", ("r",), {"via": "in-person"})),
    ("restore", {"recoveryRequestId": "r"}, ("restore", ("r",), {})),
    ("restore", {"recoveryRequestId": "r", "continue": "finish"},
     ("finish_restore", ("r",), {})),
    ("restore", {"recoveryRequestId": "r", "continue": "retry-post-restore"},
     ("retry_post_restore", ("r",), {})),
    ("restore", {"recoveryRequestId": "r", "continue": "abandon"}, ("abandon", ("r",), {})),
    ("restore", {"recoveryRequestId": "r", "continue": "reconcile"},
     ("reconcile", ("r",), {})),
    ("retire-volume", {"approvalId": "a", "mount": "/Volumes/X", "identity": "x"},
     ("retire_volume", ("a",), {"mount": "/Volumes/X", "identity": "x"})),
    ("remove-scratch", {"copyId": "c"}, ("remove_scratch", ("c",), {})),
])
def test_each_word_runs_its_one_sequence(word, document, expected):
    procedures = Procedures()
    assert run_word(word, document, procedures) == {"called": expected[0]}
    assert procedures.calls == [expected]


@pytest.mark.parametrize(("word", "document"), [
    ("shell", {"recoveryRequestId": "r"}),
    ("backup", {}),
    ("backup", {"recoveryRequestId": "r", "continue": "finish"}),
    ("restore", {"recoveryRequestId": "r", "continue": "anything"}),
    ("retire-volume", {"approvalId": "a"}),
    ("remove-scratch", {}),
    ("remove-scratch", {"copyId": "c", "extra": 1}),
])
def test_anything_outside_the_closed_sets_is_refused_before_a_procedure_runs(word, document):
    procedures = Procedures()
    with pytest.raises(ControlError) as refused:
        run_word(word, document, procedures)
    assert refused.value.code == "INVALID_INPUT"
    assert procedures.calls == []


def test_the_closed_sets():
    assert WORDS == ("backup", "verify", "restore", "retire-volume", "remove-scratch")
    assert CONTINUATIONS == ("finish", "retry-post-restore", "abandon", "reconcile")


def run_main(monkeypatch, argv, payload: bytes) -> tuple[int, dict]:
    stdin = io.TextIOWrapper(io.BytesIO(payload))
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdin", stdin)
    monkeypatch.setattr(sys, "stdout", out)
    status = cli.main(argv)
    return status, json.loads(out.getvalue())


def test_the_production_wiring_is_refused_until_its_credentials_arrive(monkeypatch):
    status, result = run_main(monkeypatch, ["recovery", "backup", "--production"],
                              b'{"recoveryRequestId": "r"}')
    assert status == 1 and result["ok"] is False
    assert result["error"]["code"] == "POLICY_UNRESOLVED"


@pytest.mark.parametrize("payload", [b"[]", b"x" * (64 * 1024 + 1)])
def test_input_must_be_one_bounded_object(monkeypatch, payload):
    status, result = run_main(monkeypatch, ["recovery", "verify", "--production"], payload)
    assert status == 1 and result["error"]["code"] == "INVALID_INPUT"


def test_a_realm_word_answers_one_json_result(monkeypatch, realm, tmp_path):
    """Through the realm's own environment file: an unknown request is NOT_FOUND, one JSON
    document, and the realm's ledger is only read."""
    from pathlib import Path
    from uuid import uuid4

    environment = Path(realm.root) / "environment.json"
    head = Path(realm.root) / "ledger" / "head.json"

    def head_state() -> bytes | None:
        # A fresh realm (the operations lane right after `migrate`) has no ledger head
        # yet; "only read" then means it still has none.
        return head.read_bytes() if head.exists() else None

    head_before = head_state()
    status, result = run_main(
        monkeypatch, ["recovery", "backup", "--environment-file", str(environment)],
        json.dumps({"recoveryRequestId": str(uuid4())}).encode())
    assert status == 1 and result == {"ok": False, "code": "NOT_FOUND", "current": None}
    assert head_state() == head_before


def test_a_realm_never_served_answers_not_found_and_creates_no_ledger(monkeypatch, tmp_path):
    """Before the host's first start the realm has no `ledger/` folder: every word naming a
    request or an approval answers NOT_FOUND, its input is still checked first, and the
    word creates nothing."""
    from types import SimpleNamespace
    from uuid import uuid4

    from docsuri_ops.u8_platform.platform_profile import U8PlatformProfile

    # `main` reads the realm's profile from the environment file's folder; here, a realm
    # folder with no `ledger/` yet.
    monkeypatch.setattr(U8PlatformProfile, "realm", staticmethod(
        lambda root: SimpleNamespace(run_root=tmp_path, run_id="r")))
    environment = str(tmp_path / "environment.json")
    for word, document in (
            ("backup", {"recoveryRequestId": str(uuid4())}),
            ("verify", {"recoveryRequestId": str(uuid4())}),
            ("restore", {"recoveryRequestId": str(uuid4()), "continue": "finish"}),
            ("retire-volume", {"approvalId": "a", "mount": "/Volumes/x", "identity": "i"})):
        status, result = run_main(monkeypatch, ["recovery", word, "--environment-file",
                                                environment], json.dumps(document).encode())
        assert status == 1 and result == {"ok": False, "code": "NOT_FOUND", "current": None}
    status, result = run_main(monkeypatch, ["recovery", "backup", "--environment-file",
                                            environment], b"{}")
    assert result["error"]["code"] == "INVALID_INPUT"
    assert not (tmp_path / "ledger").exists()


def test_the_production_words_answer_a_refused_release(monkeypatch):
    """The maintainer's decision of 2026-11-16 ("Fix the test and answer refusals"): a
    credential release that refuses is one JSON refusal, never a traceback. A stand-in
    keychain for the release refuses, so nothing reaches this Mac's sudo or ledger."""
    from docsuri_ops.u8_platform.credential_release import ReleaseRefused

    monkeypatch.setattr("docsuri_ops.production_wiring._authorities",
                        lambda paths: {"actors": {"operator": "someone-else"}})
    asked = []

    def refused(login):
        asked.append(login)
        raise ReleaseRefused("the credential was not released")

    monkeypatch.setattr("docsuri_ops.u8_platform.credential_release.release_with_actor",
                        refused)
    status, result = run_main(monkeypatch, ["recovery", "backup", "--production"],
                              b'{"recoveryRequestId": "r"}')
    assert status == 1 and result == {"ok": False, "error": {
        "code": "POLICY_UNRESOLVED", "requestId": "unknown", "retryable": False,
        "messageKey": "policy_unresolved", "details": {"fieldNames": []}}}
    assert asked == ["platform"]
