"""The lifecycle worker passes over a request whose parts only wait (U8 plan Step 18;
your decision of 2026-10-22).

A part can wait up to 24 hours for its restore verification. U8's
`CompleteLifecycleWorker.run_once` passes over a request whose open parts all wait on a
participant that is not ready
(ServiceOperations, through `GatedLifecycle`), so the wait spends no attempt and holds
back no later request. The order, the bound and every other selection rule are U2's,
and with no participant that can wait the selection is exactly U2's.

Everything runs through AccountAccess's own `ControlLifecycleService` and the complete
assembly's lifecycle worker in the composed realm, on its real operations ledger. The
two accounts are deterministic by suffix, so the realm's account budget holds.
"""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.control_worker import ControlWorker
from backend.modules.accounts.password import get_password_hasher
from backend.modules.operations.ledger import utc_text
from backend.modules.operations.tombstones import Tombstones
from backend.transactions import Authority
from backend.u8_host import compose
from backend.u8_workers import CompleteLifecycleWorker
from tests.u8_service_operations_integration.conftest import _make_account
from tests.u8_service_operations_integration.integration.test_lifecycle_manifest import (
    expire_leases,
    record_backup_set,
    record_verification,
    request_row,
    scopes,
)

PASSWORD = "synthetic-waiting-" + uuid4().hex[:12]  # per run (L1-36)
SERVICE = "ServiceOperations"
DRAIN_PASSES = 12


@pytest.fixture
def composition(realm):
    value = compose(realm, process="workers")
    yield value
    value.close()


@pytest.fixture
def account(connect, realm):
    def make(suffix: str) -> Authority:
        authority = _make_account(connect, realm, suffix=suffix)
        with connect("accounts") as conn:
            conn.execute(
                "UPDATE accounts.account SET lifecycle_state='active',active=true,"
                "password_hash=%s WHERE id=%s",
                (get_password_hasher().hash(PASSWORD), authority.account_id),
            )
        return authority

    return make


def start(composition, connect, authority, action: str) -> str:
    service = composition.parts["account-controls"]["lifecycle"]
    with connect("accounts") as conn:
        revision = conn.execute("SELECT lifecycle_revision FROM accounts.account WHERE id=%s",
                                (authority.account_id,)).fetchone()["lifecycle_revision"]
    return service.request(authority, uuid4(), revision, action, PASSWORD)["requestId"]


def drain(worker) -> None:
    """Run the worker until nothing but waiting requests is left to work on, so the
    test's own requests are the next to be selected."""
    for _ in range(DRAIN_PASSES):
        if not worker._requests(4):
            return
        worker.run_once(limit=4)
    pytest.fail("the realm kept work that is not waiting; it could not be drained")


def waiting_parts(state: dict) -> dict:
    return {key: row for key, row in state.items() if row["disposition"] != "complete"}


def test_a_waiting_request_spends_no_attempt_holds_back_no_later_one_then_completes(
    composition, connect, account,
):
    worker = composition.worker.lifecycle
    ledger = composition.parts["service-operations"]["ledger"]
    first = account("waiting-first")
    later = account("waiting-later")
    # An erase whose restore enforcement waits for a verification covering its tombstone.
    waiting = start(composition, connect, first, "erase")
    drain(worker)
    parts = waiting_parts(scopes(connect, waiting))
    assert parts and {participant for participant, _ in parts} == {SERVICE}
    attempts = {key: row["attempts"] for key, row in parts.items()}
    assert all(count == 1 for count in attempts.values())  # one claim each, then waits
    expire_leases(connect, waiting)  # each waiting part could be claimed again now
    assert worker._waits(request_row(connect, waiting))
    # Under U2's own selection the waiting request is first in line: with a bound of one
    # it would be selected on every pass and the later request never.
    assert any(worker._waits(row) for row in worker._select(1))
    assert worker._requests(4) == []  # nothing that is not waiting is left

    later_request = start(composition, connect, later, "withdraw")
    # The selection reads one bounded page at a time, past every waiting request ahead,
    # until it reaches the later request.
    pages, select = [], worker._select

    def recorded(limit, after=None):
        page = select(limit, after)
        pages.append((limit, None if after is None else after["id"], len(page)))
        return page

    worker._select = recorded
    try:
        chosen = worker._requests(1)
    finally:
        del worker._select
    assert [str(row["id"]) for row in chosen] == [later_request]
    assert len(pages) >= 2 and all(limit == 1 for limit, _, _ in pages)
    assert pages[0][1] is None and all(after is not None for _, after, _ in pages[1:])
    summary = worker.run_once(limit=1)
    assert summary["requestsInspected"] == 1
    later_state = scopes(connect, later_request)
    assert all(row["disposition"] == "complete" for (participant, _), row in
               later_state.items() if participant != SERVICE)
    # The waiting request spent nothing while it was passed over.
    assert {key: row["attempts"] for key, row in
            waiting_parts(scopes(connect, waiting)).items()} == attempts

    # Once the participant is ready, the request completes on the next pass.
    register = Tombstones(ledger)
    if not any(item["environment"] == "live" and item["integrity"] == "passed"
               for item in ledger.records("backup-set")):
        record_backup_set(ledger, retain_until=utc_text(ledger.clock()
                                                        + dt.timedelta(days=14)))
    backup = next(item for item in ledger.records("backup-set")
                  if item["environment"] == "live" and item["integrity"] == "passed")
    record_verification(ledger, register.head(), backup["backupId"])
    assert not worker._waits(request_row(connect, waiting))
    for _ in range(DRAIN_PASSES):
        worker.run_once(limit=4)
        if request_row(connect, waiting)["disposition"] == "complete":
            break
    final = scopes(connect, waiting)
    assert all(row["disposition"] == "complete" for row in final.values())
    assert all(final[key]["attempts"] == count + 1 for key, count in attempts.items())


def test_with_no_participant_that_can_wait_the_selection_is_exactly_u2s(
    composition, connect, monkeypatch,
):
    controls = composition.parts["account-controls"]
    plain = CompleteLifecycleWorker(controls["entry"], controls["lifecycle"],
                                    controls["personalization"],
                                    composition.parts["paper-journey"]["assistance_files"])
    # U2's table, as an earlier realm has it: no participant its manifest names can wait.
    plain.participants = {name: item for name, item in plain.participants.items()
                          if not callable(getattr(item, "ready", None))}
    assert not plain._waiting_participants()

    def never(*_args, **_kwargs):
        raise AssertionError("U2's selection never asks whether a part waits")

    monkeypatch.setattr(plain, "_requests", never)
    monkeypatch.setattr(plain, "_waits", never)
    for limit in (1, 4):
        u2 = [row["id"] for row in plain.transactions.run("accounts", lambda conn, n=limit: (
            conn.execute(
                "SELECT r.id FROM accounts.lifecycle_request r "
                "JOIN accounts.account a ON a.id=r.account_id "
                "WHERE r.revision=a.lifecycle_revision AND r.disposition<>'complete' "
                "AND r.manifest_revision=%s AND EXISTS (SELECT 1 FROM "
                "accounts.lifecycle_scope s WHERE s.request_id=r.id AND "
                "s.disposition<>'complete' AND s.attempts<3 AND (s.lease_until IS NULL OR "
                "s.lease_until<=clock_timestamp())) ORDER BY r.accepted_at,r.id LIMIT %s",
                (plain.lifecycle.revision, n),
            ).fetchall()))]
        assert [row["id"] for row in plain._select(limit)] == u2
        assert [row["id"] for row in plain._open_requests(limit)] == u2
    # The complete assembly's worker can wait; it is the only one that asks.
    assert composition.worker.lifecycle._waiting_participants()
    # An earlier realm's worker, over U2's manifest (`local_host.assemble`'s pairs) and the
    # full table without ServiceOperations' participant, never asks either.
    u2_manifest = SimpleNamespace(revision="u2-owners-v1", manifest=(
        ("AccountAccess", "live_records"), ("AccountAccess", "derived_artifacts"),
        ("Library", "live_records"), ("Personalization", "live_records"),
        ("Personalization", "derived_artifacts"), ("Personalization", "pending_work"),
        ("UsageEntitlements", "live_records"), ("PaperAssistance", "live_records"),
        ("PaperAssistance", "derived_artifacts"), ("PaperAssistance", "pending_work"),
        ("DiscoveryCitations", "live_records"), ("ServiceOperations", "backups"),
        ("ServiceOperations", "restore_enforcement"),
    ))
    earlier = ControlWorker(controls["entry"], u2_manifest, controls["personalization"],
                            composition.parts["paper-journey"]["assistance_files"])
    assert "ServiceOperations" not in earlier.participants
    # U2's built worker has no waiting-part selection at all: its one query is the built
    # selection (`_open_requests`).
    assert not hasattr(earlier, "_waiting_participants")
    assert not hasattr(earlier, "_waits")


def test_a_bound_outside_one_to_four_is_still_refused_before_any_selection(composition):
    worker = composition.worker.lifecycle
    for limit in (0, 5, "4", 2.0):
        with pytest.raises(ValueError):
            worker.run_once(limit=limit)
