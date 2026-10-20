"""A first connect through the routes (R-02, R-03, R-13, R-14): the pending reservation
is paced like any call, is released by every other outcome of its check, refuses a
second connect while fresh, is taken over once stale, and is never shown to a reader."""

import datetime as dt
import threading
from uuid import UUID, uuid4

import pytest
from backend.modules.accounts.control_policy import SYNTHETIC_POLICY
from backend.modules.export.control_lifecycle import ExportLifecycleParticipant
from backend.modules.export.fake_notion import Answer
from psycopg.types.json import Jsonb

from tests.u6_approved_export import http_flows as hf
from tests.u6_approved_export import store_flows as flows

TAKEOVER = dt.timedelta(seconds=121)
MANIFEST_REVISION = "u6-pending-test"


@pytest.fixture
def m(realm, transactions, connect, authority, authority_b, tmp_path):
    with hf.mount(realm, transactions, connect, authority, authority_b, tmp_path) as mounted:
        yield mounted


def owner_rows(connect, account) -> list:
    with connect("export") as conn:
        return conn.execute(
            "SELECT c.id,c.state,c.revision,c.pending_holder,p.next_slot_at "
            "FROM export.connection c LEFT JOIN export.connection_pace p "
            "ON p.connection_id=c.id WHERE c.account_id=%s",
            (account,),
        ).fetchall()


def pace_of(connect, connection_id) -> dt.datetime | None:
    with connect("export") as conn:
        row = conn.execute(
            "SELECT next_slot_at FROM export.connection_pace WHERE connection_id=%s",
            (connection_id,),
        ).fetchone()
    return None if row is None else row["next_slot_at"]


def ticket(connect, account, action: str) -> dict:
    """One live AccountAccess ticket for the live_records scope, as U5 seeds its own."""
    request, lifecycle_revision = uuid4(), uuid4()
    with connect("accounts") as conn:
        conn.execute(
            "UPDATE accounts.account SET lifecycle_revision=%s WHERE id=%s",
            (lifecycle_revision, account),
        )
        conn.execute(
            "INSERT INTO accounts.lifecycle_request(id,account_id,revision,action,policy_ref,"
            "manifest_revision,manifest,disposition,reason_key) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,'pending','pending')",
            (
                request,
                account,
                lifecycle_revision,
                action,
                Jsonb(SYNTHETIC_POLICY.reference),
                MANIFEST_REVISION,
                Jsonb([["ApprovedExport", "live_records"]]),
            ),
        )
        conn.execute(
            "INSERT INTO accounts.lifecycle_scope(request_id,participant,scope,generation,"
            "lease_until,attempts) VALUES(%s,'ApprovedExport','live_records',1,"
            "clock_timestamp()+interval '1 minute',1)",
            (request,),
        )
    return {
        "request_id": request,
        "account_id": account,
        "lifecycle_revision": lifecycle_revision,
        "participant": "ApprovedExport",
        "scope": "live_records",
        "generation": 1,
        "action": action,
        "policy_ref": SYNTHETIC_POLICY.reference,
        "manifest_revision": MANIFEST_REVISION,
    }


def test_a_first_connect_is_paced_on_its_pending_row(m, connect, monkeypatch):
    reserved = []
    original = m.rig.repo.reserve_pace_slot

    def spy(connection_id, *, remaining_seconds):
        reserved.append((connection_id, pace_of(connect, connection_id)))
        return original(connection_id, remaining_seconds=remaining_seconds)

    monkeypatch.setattr(m.rig.repo, "reserve_pace_slot", spy)

    connection = m.connect_owner()

    identifier = UUID(connection["connectionId"])
    assert connection["state"] == "connected" and connection["revision"] == "1"
    assert reserved and {item[0] for item in reserved} == {identifier}
    before = reserved[0][1]
    assert before is not None  # the pace row existed before the check started (R-13)
    assert pace_of(connect, identifier) > before


@pytest.mark.parametrize("outcome", ["invalid-token", "unavailable", "protection"])
def test_every_other_outcome_of_the_check_removes_the_pending_row(
    m, connect, tmp_path, outcome
):
    body = m.configure_body()
    if outcome == "invalid-token":
        body = m.configure_body("synthetic-unknown-" + uuid4().hex)
    elif outcome == "unavailable":
        m.rig.fake.queue("users.me", Answer.error(500))
    else:
        # The key folder opened to the group: sealing is refused (security design §4.3).
        (tmp_path / "export-keys").chmod(0o750)

    code = m.refused("configure", body)

    assert code == {
        "invalid-token": "INVALID_TOKEN",
        "unavailable": "DEPENDENCY_UNAVAILABLE",
        "protection": "POLICY_UNRESOLVED",
    }[outcome]
    assert owner_rows(connect, m.authority.account_id) == []
    assert m.refused("read_connection", {}) == "NOT_FOUND"


def test_a_second_connect_during_a_fresh_check_is_conflict(m, connect):
    second = m.browser(m.own)
    answers = []
    original = m.rig.fake.handle_async_request

    async def handle(request):
        if request.url.path == "/v1/users/me" and not answers:
            # While the first check holds its fresh reservation, a second connect runs.
            worker = threading.Thread(
                target=lambda: answers.append(m.post("configure", m.configure_body(), client=second))
            )
            worker.start()
            worker.join(30)
        return await original(request)

    m.rig.fake.handle_async_request = handle

    first = m.connect_owner()

    assert len(answers) == 1
    assert (answers[0].status_code, answers[0].json()["code"]) == (409, "CONFLICT")
    assert first["state"] == "connected"
    assert m.ok("read_connection", {}) == first
    second.close()


def test_a_stale_reservation_is_taken_over(m, connect):
    stale = m.rig.repo.reserve_connection(m.authority, None, now=m.rig.clock.now - TAKEOVER)

    connection = m.connect_owner()

    assert UUID(connection["connectionId"]) == stale.connection_id
    assert (connection["state"], connection["revision"]) == ("connected", "1")
    rows = owner_rows(connect, m.authority.account_id)
    assert len(rows) == 1 and rows[0]["pending_holder"] is None


def test_a_fresh_reservation_is_conflict_and_housekeeping_removes_a_stale_one(m, connect):
    held = m.rig.repo.reserve_connection(m.authority, None, now=m.rig.clock.now)
    assert m.refused("configure", m.configure_body()) == "CONFLICT"

    swept = m.rig.repo.sweep_stale_pending(m.rig.clock.now + TAKEOVER)

    assert swept >= 1
    assert flows.connection_row(connect, held.connection_id) is None
    assert flows.pace_count(connect, held.connection_id) == 0
    assert m.connect_owner()["state"] == "connected"


def test_no_read_ever_shows_the_pending_state(m):
    m.rig.repo.reserve_connection(m.authority, None, now=m.rig.clock.now)

    answers = [
        m.post("read_connection", {}),
        m.post("list_destinations", {}),
        m.post("disconnect", {}),
        m.post("history", {}),
    ]

    assert [response.status_code for response in answers] == [404, 404, 404, 200]
    assert all("pending" not in response.text for response in answers)
    assert answers[-1].json()["entries"] == []


@pytest.mark.parametrize("action", ["withdraw", "erase"])
def test_withdrawal_and_erasure_delete_the_pending_row(m, connect, transactions, action):
    held = m.rig.repo.reserve_connection(m.authority, None, now=m.rig.clock.now)
    participant = ExportLifecycleParticipant(transactions, clock=lambda: m.rig.clock.now)

    result = participant.apply(ticket(connect, m.authority.account_id, action))

    assert result["disposition"] == "complete"
    assert flows.connection_row(connect, held.connection_id) is None
    assert flows.pace_count(connect, held.connection_id) == 0
    assert owner_rows(connect, m.authority.account_id) == []
