"""A failing item is set aside (U8 plan Step 18; the person's decision of 2026-10-23,
"Set it aside, record it").

In the complete realms the chained worker and the lifecycle worker handle an item whose
processing fails the same way: an operations incident records the item's kind and
identity, never its content; the item gives up its turn; the rest of the pass carries on;
the item is retried on the next pass within its usual attempt limit, and at that limit the
built rule applies. An earlier realm's worker keeps the built behaviour.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from backend.control_worker import SET_ASIDE, ControlWorker
from backend.modules.operations.incidents import Incidents
from backend.transactions import Authority
from backend.u8_workers import (
    CompleteLifecycleWorker,
    CompletePassIncomplete,
    CompleteWorker,
    chain_steps,
)
from tests.u8_service_operations_integration import recovery_flows as rf
from tests.u8_service_operations_integration.conftest import SIGN_IN_PASSWORD
from tests.u8_service_operations_integration.host_flows import (
    MEMBER,
    complete_host,
    member,
    session_of,
)

pytestmark = pytest.mark.usefixtures("own_address")


@pytest.fixture
def host(realm, own_address):
    with complete_host(realm, address=own_address) as value:
        yield value


def correlations(host) -> list[str]:
    composition = host.composition
    incidents = Incidents(composition.parts["service-operations"]["ledger"],
                          environment=composition.environment)
    found = incidents.open_for("background.work")
    return [] if found is None else found["correlationIds"]


class Boom(RuntimeError):
    pass


def test_a_failing_step_records_an_incident_and_the_rest_of_the_pass_completes(
        host, monkeypatch):
    composition = host.composition
    execution = composition.parts["research-workspace"]["execution"]
    scheduler = composition.parts["topics-digests"]["scheduler"]
    calls = {"research": 0, "digests": 0}

    def failing_step():
        calls["research"] += 1
        raise Boom("synthetic failure with private text that is never recorded")

    def digests(limit=1):
        calls["digests"] += 1

    monkeypatch.setattr(execution, "step", failing_step)
    monkeypatch.setattr(scheduler, "run_once", digests)
    summaries = composition.worker.run_once(4)
    # The step gave up its turn; the steps after it (the digests) ran.
    assert "research-execution" in summaries["chained"]["setAside"]
    assert "digest-schedule" in summaries["chained"]["steps"]
    assert calls == {"research": 1, "digests": 1}
    recorded = correlations(host)
    assert "worker-item:research-execution:pass" in recorded
    assert not any("private" in value for value in recorded)
    # Retried on the next pass.
    composition.worker.run_once(4)
    assert calls == {"research": 2, "digests": 2}


def lifecycle_request(host, sign_in_account, connect):
    """A withdrawal of a member through AccountAccess, as the account page requests it."""
    signed, _ = member(host, sign_in_account, MEMBER)
    composition = host.composition
    authority = Authority(signed.account_id, session_of(connect, signed.account_id))
    revision = composition.transactions.run("accounts", lambda conn: conn.execute(
        "SELECT lifecycle_revision FROM accounts.account WHERE id=%s",
        (authority.account_id,)).fetchone()["lifecycle_revision"])
    outcome = composition.parts["account-controls"]["lifecycle"].request(
        authority, uuid4(), revision, "withdraw", SIGN_IN_PASSWORD)
    return outcome["requestId"]


def test_a_failing_scope_is_retried_each_pass_and_its_attempt_limit_applies(
        host, sign_in_account, connect, monkeypatch):
    composition = host.composition
    request = lifecycle_request(host, sign_in_account, connect)
    worker = composition.worker.lifecycle
    library = worker.participants["Library"]
    applied = []

    def failing_apply(ticket):
        applied.append(ticket["scope"])
        raise Boom("library scope failure")

    monkeypatch.setattr(library, "apply", failing_apply)
    realm = composition.profile

    def scope_rows():
        with rf.admin(realm, realm.database_name) as conn:
            return conn.execute(
                "SELECT scope,attempts,disposition FROM accounts.lifecycle_scope "
                "WHERE request_id=%s AND participant='Library' ORDER BY scope",
                (request,)).fetchall()

    for _ in range(4):
        composition.worker.run_once(4)
        # The lease of a set-aside scope runs out before the next pass, as time would.
        with rf.admin(realm, realm.database_name) as conn:
            conn.execute("UPDATE accounts.lifecycle_scope SET lease_until=NULL "
                         "WHERE request_id=%s AND participant='Library'", (request,))
    rows = scope_rows()
    assert rows and all(row[1] == 3 for row in rows), rows  # the built limit of 3
    assert all(row[2] != "complete" for row in rows)
    assert len(applied) == 3 * len(rows)  # never claimed again once at its limit
    recorded = correlations(host)
    assert any(value.startswith(f"worker-item:lifecycle-scope:{request}:Library:")
               for value in recorded)


def test_an_earlier_realms_worker_keeps_the_built_behaviour():
    class Failing:
        def run_once(self, limit=1):
            raise Boom("built failure")

    built = CompleteWorker(Failing())
    with pytest.raises(CompletePassIncomplete):
        built.run_once(1)
    # U2's built hook calls the work once and lets its failure end the pass; U2's worker
    # has no recorder at all.
    worker = ControlWorker.__new__(ControlWorker)
    assert not hasattr(worker, "set_aside")
    calls = []

    def failing():
        calls.append(1)
        raise Boom("built failure")

    with pytest.raises(Boom):
        worker._guarded("lifecycle-scope", "x", failing)
    assert calls == [1]
    # U8's lifecycle worker keeps the built behaviour until a recorder is set.
    complete = CompleteLifecycleWorker.__new__(CompleteLifecycleWorker)
    assert complete.set_aside is None
    with pytest.raises(Boom):
        complete._guarded("lifecycle-scope", "x", Failing().run_once)


def test_a_recorder_is_refused_with_a_lifecycle_worker_that_is_not_u8s():
    class Chained:
        def run_once(self, limit=1):
            return {}

    plain = ControlWorker.__new__(ControlWorker)
    with pytest.raises(TypeError):
        CompleteWorker(Chained(), plain, set_aside=lambda *args: None)


def test_set_aside_records_by_kind_and_identity_and_keeps_pending_evidence():
    from backend.control_worker import PendingLifecycleEvidence

    seen = []
    worker = CompleteLifecycleWorker.__new__(CompleteLifecycleWorker)
    worker.set_aside = lambda kind, identity, error: seen.append((kind, identity))
    assert worker._guarded("consent-obligation", "id-1", lambda: 1 / 0) is SET_ASIDE
    assert seen == [("consent-obligation", "id-1")]
    with pytest.raises(PendingLifecycleEvidence):
        worker._guarded("lifecycle-scope", "id-2",
                        lambda: (_ for _ in ()).throw(PendingLifecycleEvidence("waits")))


def test_the_chain_is_walked_into_its_own_steps_innermost_first(host):
    names = [name for name, _ in chain_steps(host.composition.worker.chained, 1)]
    assert names == ["corpus-runs", "assistance-dispatch", "dispositions",
                     "assistance-admissions", "assistance-execution", "research-execution",
                     "research-expiry", "digest-schedule", "export-pass"]
