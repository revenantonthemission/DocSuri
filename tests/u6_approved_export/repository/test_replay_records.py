"""Security design §3: the configure replay record keeps no token-derived material."""

import hashlib
import re
from uuid import uuid4

import pytest
from backend.modules.export.errors import ExportError
from backend.modules.export.repository import Replay, replay_input_hash
from backend.modules.export.store_support import canonical_digest

from tests.u6_approved_export import store_flows as flows

HEX64 = re.compile(r"[0-9a-f]{64}")
RESPONSE_KEYS = {"connectionId", "state", "revision", "code"}


def records(connect, account):
    with connect("export") as conn:
        return conn.execute(
            "SELECT * FROM export.replay_record WHERE account_id=%s AND operation='configure'",
            (account,),
        ).fetchall()


def first_configure(repo, authority, now, token):
    request = flows.configure_request(None, token)
    replay = flows.replay_for(request)
    slot = repo.reserve_connection(authority, None, now=now)
    result = repo.store_configured(authority, slot, flows.sealed(), replay, now=now)
    return request, replay, result


def test_the_configure_record_holds_no_token_digest_or_salted_digest(
    transactions, connect, authority
):
    repo, now = flows.repository(transactions), flows.at()
    flows.fresh(connect, authority.account_id)
    token = "secret_" + uuid4().hex
    request, replay, result = first_configure(repo, authority, now, token)
    [record] = records(connect, authority.account_id)
    assert set(record) == {
        "account_id",
        "operation",
        "operation_key",
        "input_hash",
        "response",
        "created_at",
    }
    without_token = {k: v for k, v in request.items() if k != "token"}
    assert record["input_hash"] == canonical_digest(without_token) == replay.input_hash
    assert record["input_hash"] == replay_input_hash({**request, "token": "other"})
    text = repr(record)
    assert token not in text
    assert hashlib.sha256(token.encode()).hexdigest() not in text
    assert HEX64.findall(text) == [record["input_hash"]]  # no other digest of any kind
    assert set(record["response"]) <= RESPONSE_KEYS
    assert record["response"] == result["response"]
    assert record["response"]["state"] == "connected" and record["response"]["revision"] == 1


def test_a_replay_returns_the_original_response(transactions, connect, authority):
    repo, now = flows.repository(transactions), flows.at()
    flows.fresh(connect, authority.account_id)
    _, replay, result = first_configure(repo, authority, now, "first-token")
    assert repo.configure_replay(authority, replay) == result["response"]
    slot = repo.reserve_connection(authority, 1, now=now)
    again = repo.store_configured(authority, slot, flows.sealed(), replay, now=now)
    assert again == {"replayed": True, "response": result["response"]}
    assert repo.read_connection(authority)["revision"] == 1  # nothing stored twice
    assert repo.configure_replay(authority, flows.replay_for({"other": 1})) is None


def test_another_expected_revision_under_the_same_key_is_an_idempotency_conflict(
    transactions, connect, authority
):
    repo, now = flows.repository(transactions), flows.at()
    flows.fresh(connect, authority.account_id)
    _, replay, _ = first_configure(repo, authority, now, "first-token")
    changed = Replay(replay.operation_key, replay_input_hash(flows.configure_request(1)))
    with pytest.raises(ExportError) as caught:
        repo.configure_replay(authority, changed)
    assert caught.value.code == "IDEMPOTENCY_CONFLICT"
    slot = repo.reserve_connection(authority, 1, now=now)
    with pytest.raises(ExportError) as caught:
        repo.store_configured(authority, slot, flows.sealed(), changed, now=now)
    assert caught.value.code == "IDEMPOTENCY_CONFLICT"
    assert repo.read_connection(authority)["revision"] == 1


def test_another_token_under_the_same_key_returns_the_original(transactions, connect, authority):
    repo, now = flows.repository(transactions), flows.at()
    flows.fresh(connect, authority.account_id)
    _, replay, result = first_configure(repo, authority, now, "first-token")
    other = Replay(
        replay.operation_key, replay_input_hash(flows.configure_request(None, "second-token"))
    )
    assert other == replay
    assert repo.configure_replay(authority, other) == result["response"]


def test_a_definite_refusal_keeps_only_its_code(transactions, connect, authority):
    """A check refused as INVALID_TOKEN releases its reservation and records the code."""
    repo, now = flows.repository(transactions), flows.at()
    flows.fresh(connect, authority.account_id)
    request = flows.configure_request(None, "refused-token")
    replay = flows.replay_for(request)
    slot = repo.reserve_connection(authority, None, now=now)
    assert repo.release_pending(authority, slot.holder, refusal=(replay, "INVALID_TOKEN")) is True
    assert repo.configure_replay(authority, replay) == {"code": "INVALID_TOKEN"}
    [record] = records(connect, authority.account_id)
    assert record["response"] == {"code": "INVALID_TOKEN"}
    assert flows.connection_row(connect, slot.connection_id) is None
