"""Reactivation by mail in the composed realm (U8 plan Step 22; your decision of
2026-10-23): a withdrawn account's request sends one `reactivation` message through the
realm's account mail, under the reservation and allowance rules; an unknown or active
account gets the same answer and nothing is sent; the link's proof reactivates once.

The account mail is the realm's local mailbox behind ServiceOperations' allowance, on a
ledger of the test's own, as the composition wires it (`u8_host`).
"""

from __future__ import annotations

import contextlib
from uuid import UUID, uuid4

import pytest

from backend.modules.accounts.integrations.account_mail import LocalAccountMail
from backend.modules.operations.allowance import KIND, LedgerAllowance
from backend.modules.operations.ledger import Ledger
from backend.u8_policy import SYNTHETIC_OPERATIONS
from tests.u8_service_operations_integration.conftest import SIGN_IN_PASSWORD, post
from tests.u8_service_operations_integration.host_flows import MEMBER, complete_host
from tests.u8_service_operations_integration.host_flows import member as host_member
from tests.u8_service_operations_integration.integration.test_account_routes import (
    csrf_of,
    mailed,
    member,  # noqa: F401 - the signed-in member fixture
    read_profile,
    sender_pass,
)

# Step 85(j): no outbox row outlives its test (Step 54(n)'s `empty_outbox`).
pytestmark = pytest.mark.usefixtures("own_address", "empty_outbox")


@pytest.fixture
def allowance_ledger(tmp_path, clock, d1_entry):
    """The entry's account mail as the composition wires it: the local mailbox behind an
    allowance on a ledger of this test's own."""
    folder = tmp_path / "reactivation-ledger"
    folder.mkdir(mode=0o700)
    ledger = Ledger.open(folder, clock=clock)
    previous = d1_entry.account_mail
    d1_entry.account_mail = LocalAccountMail(
        d1_entry.mail, allowance=LedgerAllowance(ledger, SYNTHETIC_OPERATIONS))
    try:
        yield ledger
    finally:
        d1_entry.account_mail = previous
        ledger.close()


def withdraw(client, d1_entry) -> None:
    before = read_profile(client)
    policy = d1_entry.control_policy.reference
    prepared = post(client, "/api/v2/c02/access-prepare-lifecycle", {
        "action": "withdraw", "expectedRevision": before["lifecycleRevision"],
        "currentProof": SIGN_IN_PASSWORD, "policyRef": policy}, csrf_of(client))
    assert prepared.status_code == 200, prepared.text
    requested = post(client, "/api/v2/c02/lifecycle-request", {
        "action": "withdraw", "confirmationRef": prepared.json()["confirmationRef"],
        "policyRef": policy}, csrf_of(client))
    assert requested.status_code == 200, requested.text


def ask(client, d1_entry, email: str, operation=None):
    answer = post(client, "/api/v2/c02/access-request-reactivation", {
        "email": email, "policyRef": d1_entry.control_policy.reference}, csrf_of(client),
        operation=operation)
    assert answer.status_code == 200, answer.text
    return answer.json()


def shape(answer: dict) -> dict:
    """An answer without its own request identifier: what it says about the account."""
    return {key: value for key, value in answer.items() if key != "requestId"}


def mailbox_files(d1_entry) -> set[str]:
    return {path.name for path in d1_entry.mail.root.glob("*.blob")}


def test_a_withdrawn_account_gets_one_reactivation_message_under_the_allowance(
    member, d1_entry, allowance_ledger,  # noqa: F811
):
    client, _, email = member
    withdraw(client, d1_entry)
    before = mailbox_files(d1_entry)
    operation = uuid4()
    first = ask(client, d1_entry, email, operation)
    sender_pass(d1_entry)  # the request answers before its message leaves (Step 85(j))
    new = mailbox_files(d1_entry) - before
    assert len(new) == 1
    message = mailed(d1_entry, "reactivate", email)
    assert {"challengeId", "proof", "flowBinding"} <= set(message)
    # A retry of the same request is the same answer and sends nothing more.
    assert ask(client, d1_entry, email, operation) == first
    sender_pass(d1_entry)
    assert mailbox_files(d1_entry) - before == new
    # One place taken, settled, for the one message that left.
    places = allowance_ledger.records(KIND)
    assert [record["state"] for record in places] == ["settled"]


def test_an_unknown_or_active_account_gets_the_same_answer_and_nothing_is_sent(
    member, d1_entry, allowance_ledger,  # noqa: F811
):
    client, _, email = member
    before = mailbox_files(d1_entry)
    active = ask(client, d1_entry, email)
    unknown = ask(client, d1_entry, f"nobody-{uuid4().hex[:12]}@u8.fixture.example.com")
    assert shape(active) == shape(unknown)
    sender_pass(d1_entry)  # nothing was queued, so a pass sends nothing (Step 85(j))
    assert mailbox_files(d1_entry) == before
    assert allowance_ledger.records(KIND) == []
    # A withdrawn account's answer says no more than the others did.
    withdraw(client, d1_entry)
    assert shape(ask(client, d1_entry, email)) == shape(active)


@contextlib.contextmanager
def planted(client, monkeypatch, identifier: UUID):
    """One request under its own literal UUID (`backend.request_context.uuid4`) and a
    planted `x-request-id`, which the boundary ignores."""
    import backend.request_context as request_context

    monkeypatch.setattr(request_context, "uuid4", lambda: identifier)
    client.headers["x-request-id"] = str(uuid4())
    try:
        yield client.headers["x-request-id"]
    finally:
        del client.headers["x-request-id"]
        monkeypatch.undo()


def test_a_lifecycle_request_records_its_origin_request_and_the_workers_log_it(
    realm, own_address, sign_in_account, connect, monkeypatch, caplog,
):
    """Step 87(e) (L1-6), on the complete host, whose boundary sets each request's
    identifier and whose transactions are the composition's."""
    import json
    import logging

    from backend.log_events import EVENTS_LOGGER

    caplog.set_level(logging.DEBUG, logger=EVENTS_LOGGER)
    with complete_host(realm, address=own_address) as host:
        client = host.client
        authority, _ = host_member(host, sign_in_account)
        before = read_profile(client)
        policy = host.composition.parts["account-controls"]["entry"].control_policy.reference
        prepare_id, request_id = uuid4(), uuid4()
        token = csrf_of(client)
        with planted(client, monkeypatch, prepare_id) as planted_prepare:
            prepared = post(client, "/api/v2/c02/access-prepare-lifecycle", {
                "action": "withdraw", "expectedRevision": before["lifecycleRevision"],
                "currentProof": SIGN_IN_PASSWORD, "policyRef": policy}, token)
        assert prepared.status_code == 200, prepared.text
        token = csrf_of(client)
        with planted(client, monkeypatch, request_id) as planted_request:
            requested = post(client, "/api/v2/c02/lifecycle-request", {
                "action": "withdraw", "confirmationRef": prepared.json()["confirmationRef"],
                "policyRef": policy}, token)
        assert requested.status_code == 200, requested.text
        lifecycle_id = requested.json()["lifecycleRequestId"]
        with connect("accounts") as conn:
            origin = conn.execute(
                "SELECT origin_request_id FROM accounts.lifecycle_request WHERE id=%s",
                (lifecycle_id,)).fetchone()["origin_request_id"]
        assert origin == request_id
        assert str(origin) not in (str(prepare_id), planted_prepare, planted_request)

        def lines() -> dict:
            found = {}
            for record in caplog.records:
                if record.name != EVENTS_LOGGER:
                    continue
                line = json.loads(record.getMessage())
                if (line.get("jobId") == lifecycle_id
                        and line["event"] in ("job.started", "job.ended")):
                    found[line["event"]] = line
            return found

        # Bounded passes outside a request, until this request's lines appear.
        for _ in range(4):
            host.composition.worker.run_once(limit=1)
            if set(lines()) == {"job.started", "job.ended"}:
                break
        found = lines()
        assert set(found) == {"job.started", "job.ended"}, found
        for line in found.values():
            assert (line["component"], line["requestId"]) == ("workers", str(request_id))
    # The shared account back to active, its sessions ended.
    sign_in_account(MEMBER)


def test_the_links_proof_reactivates_once_and_a_second_use_is_refused(
    member, d1_entry, allowance_ledger,  # noqa: F811
):
    client, _, email = member
    withdraw(client, d1_entry)
    ask(client, d1_entry, email)
    proof = mailed(d1_entry, "reactivate", email)
    body = {
        "confirmationRef": proof["challengeId"],
        "verification": {key: proof[key] for key in ("challengeId", "proof", "flowBinding")},
        "policyRef": d1_entry.control_policy.reference,
    }
    first = post(client, "/api/v2/c02/lifecycle-reactivate", body, csrf_of(client))
    assert first.status_code == 200, first.text
    assert first.json()["access"] == "reactivation_pending"
    again = dict(body)
    second = post(client, "/api/v2/c02/lifecycle-reactivate", again, csrf_of(client))
    assert second.status_code == 403, second.text
