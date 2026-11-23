"""C11 over HTTP (U8 plan Step 40; A5, BR3.8, BR4.1, BR4.9), and the dashboard's contents
over a real operations ledger (U8 plan Step 61; L1-35, L1-41, L1-45).

Each C11 route answers only an administrator whose second factor is current. An
administrator without one gets FORBIDDEN (the workspace shows its MFA prompt), and
everyone else the ordinary not-found answer, with no count or identifier. The dashboard
holds observability-design § 4's contents as C11 items; `request-recovery` replays one
submission idempotently and answers a stale revision with CONFLICT; the status read
never moves a request; no route records a decision.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import secrets
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5

import pytest
from docsuri_shared.workspace import wire

from backend.modules.operations.dashboard import Dashboard
from backend.modules.operations.http import policy_reference
from backend.modules.operations.incidents import Incidents
from backend.modules.operations.ledger import utc_text
from backend.modules.operations.producers import LANES, BackgroundWorkProducer
from backend.modules.operations.readiness import CapabilityState
from backend.modules.operations.recovery import RecoveryRequests
from backend.modules.operations.retained_copies import RetainedCopies
from backend.u8_policy import PRODUCTION_OPERATIONS, ROUTE_CLASSES, SYNTHETIC_OPERATIONS
from backend.u8_registry import CAPABILITY_BY_ID
from docsuri_ops.standing.availability import AvailabilityRecord
from tests.u8_service_operations_integration.host_flows import (
    administrator,
    call,
    complete_host,
    lapse_second_factor,
    member,
)
from tests.u8_service_operations_integration.recovery_flows import (
    advance_cutover,
    cutover_record,
    open_ledger,
    receipt,
    set_record,
)

pytestmark = pytest.mark.usefixtures("own_address")
ROUTES = {
    "/api/v2/c11/read-dashboard": {"page": {"limit": 10}},
    "/api/v2/c11/list-incidents": {"page": {"limit": 10}},
    "/api/v2/c11/read-recovery-status": {"recoveryRequestId": str(uuid4())},
}
REFUSAL_KEYS = {"code", "requestId", "retryable", "messageKey"}


@pytest.fixture
def host(realm, own_address):
    with complete_host(realm, address=own_address) as value:
        yield value


@pytest.fixture
def admin(host, sign_in_account, connect):
    authority, _ = administrator(host, sign_in_account, connect)
    return authority


def submission(host, **changes) -> dict:
    composition = host.composition
    requests = RecoveryRequests(composition.ledger, composition.policy)
    value = {
        "operation": "backup.create", "targetId": composition.environment,
        "expectedRevision": str(requests.backup_revision(composition.environment)),
        "origin": "administrator", "submissionId": str(uuid4()),
        "policy": policy_reference(composition.policy),
    }
    return {**value, **changes}


def cancel(host, request_id: str) -> None:
    """Leave no request waiting in the realm's ledger after the test."""
    composition = host.composition
    RecoveryRequests(composition.ledger, composition.policy).cancel(request_id)


def test_a_member_gets_not_found_and_an_administrator_without_mfa_forbidden(
    host, sign_in_account, connect,
):
    member(host, sign_in_account)
    for path, body in {**ROUTES, "/api/v2/c11/request-recovery": submission(host)}.items():
        answer = call(host.client, path, body)
        assert (answer.status_code, answer.json()["code"]) == (404, "NOT_FOUND"), path
        assert set(answer.json()) <= REFUSAL_KEYS
    host.client.cookies.clear()
    authority, _ = administrator(host, sign_in_account, connect)
    lapse_second_factor(connect, authority.account_id)
    for path, body in ROUTES.items():
        answer = call(host.client, path, body)
        assert (answer.status_code, answer.json()["code"]) == (403, "FORBIDDEN"), path
        assert set(answer.json()) <= REFUSAL_KEYS
    host.client.cookies.clear()
    assert call(host.client, "/api/v2/c11/read-dashboard", ROUTES[
        "/api/v2/c11/read-dashboard"]).status_code == 401


def test_the_dashboard_holds_each_capability_and_the_email_counts(host, admin):
    from backend.u8_host import operations_dashboard

    answer = call(host.client, "/api/v2/c11/read-dashboard", {"page": {"limit": 200}})
    assert answer.status_code == 200, answer.text
    page = wire.OpsDashboardPage.model_validate(answer.json()).model_dump(mode="json")
    capabilities = {item["capability"]: item for item in page["items"]}
    states = host.composition.readiness_view().states()
    assert set(states) <= set(capabilities)
    for name, state in states.items():
        item = capabilities[name]
        expected = "unknown" if state.state == "stale" else state.state
        assert item["status"] == expected
        if state.observed_at is not None:
            assert item["freshness"] in ("current", "stale") and item["ageSeconds"] >= 0
    allowance = capabilities["operations.email-allowance"]
    assert {entry.split(":")[0] for entry in allowance["limitations"]} == {"daily", "monthly"}
    assert not any("@" in str(value) for item in page["items"] for value in item.values())
    # Step 61(d): the host's dashboard holds the realm's operations policy.
    dashboard = operations_dashboard(host.composition,
                                     host.composition.parts["service-operations"])
    assert dashboard.policy == SYNTHETIC_OPERATIONS
    # Paged for its snapshot; another snapshot's cursor or a tampered one is refused.
    first = call(host.client, "/api/v2/c11/read-dashboard", {"page": {"limit": 2}}).json()
    assert len(first["items"]) == 2 and first["page"]["nextCursor"]
    second = call(host.client, "/api/v2/c11/read-dashboard",
                  {"page": {"limit": 2, "cursor": first["page"]["nextCursor"]}}).json()
    assert {item["observationId"] for item in second["items"]}.isdisjoint(
        {item["observationId"] for item in first["items"]})
    refused = call(host.client, "/api/v2/c11/read-dashboard",
                   {"page": {"limit": 2, "cursor": "not-a-cursor!"}})
    assert refused.status_code == 422
    filtered = call(host.client, "/api/v2/c11/read-dashboard",
                    {"page": {"limit": 50}, "capability": "operations.ledger"}).json()
    assert [item["capability"] for item in filtered["items"]] == ["operations.ledger"]
    incidents = call(host.client, "/api/v2/c11/list-incidents", {"page": {"limit": 20}})
    assert incidents.status_code == 200
    wire.OpsIncidentReadPage.model_validate(incidents.json())


def test_request_recovery_replays_one_submission_and_refuses_a_stale_revision(host, admin):
    body = submission(host)
    first = call(host.client, "/api/v2/c11/request-recovery", body)
    assert first.status_code == 200, first.text
    receipt_value = wire.JobReceipt.model_validate(first.json()).model_dump(mode="json")
    try:
        assert receipt_value["state"] == "accepted"
        again = call(host.client, "/api/v2/c11/request-recovery", body)
        assert again.status_code == 200 and again.json()["jobId"] == receipt_value["jobId"]
        stale = call(host.client, "/api/v2/c11/request-recovery", submission(
            host, expectedRevision=str(int(body["expectedRevision"]) + 1)))
        assert (stale.status_code, stale.json()["code"]) == (409, "CONFLICT")
        reused = call(host.client, "/api/v2/c11/request-recovery",
                      {**body, "operation": "restore.verify", "targetId": str(uuid4())})
        assert reused.status_code in (404, 409)
        for operation in ("database.drop", "platform.decision.record"):
            assert call(host.client, "/api/v2/c11/request-recovery",
                        submission(host, operation=operation)).status_code == 422
        assert call(host.client, "/api/v2/c11/request-recovery",
                    submission(host, policy={"policyId": "other", "revision": "1"})
                    ).status_code == 503
        # The status read answers the request as the ledger holds it, and moves nothing.
        status = call(host.client, "/api/v2/c11/read-recovery-status",
                      {"recoveryRequestId": receipt_value["jobId"]})
        assert status.status_code == 200, status.text
        value = wire.OpsRecoveryStatus.model_validate(status.json()).model_dump(mode="json")
        assert (value["state"], value["origin"], value["operation"]) == (
            "requested", "administrator", "backup.create")
        assert call(host.client, "/api/v2/c11/read-recovery-status",
                    {"recoveryRequestId": receipt_value["jobId"]}).json()["revision"] == (
            value["revision"])
        missing = call(host.client, "/api/v2/c11/read-recovery-status",
                       {"recoveryRequestId": str(uuid4())})
        assert missing.status_code == 404
    finally:
        cancel(host, receipt_value["jobId"])


def test_a_request_is_admitted_while_the_realms_clock_stands_ahead(host, admin):
    """The recovery journey found it: the second factor's time is the database's, and
    the realm's delegated clock stood an hour ahead after the earlier journeys, so every
    administrator request was refused as `mfa-not-current`. Its age is now measured on the
    database's clock."""
    from backend.u8_host import CLOCK_FILE

    profile = host.composition.profile
    path = profile.root / CLOCK_FILE
    previous = path.read_bytes() if path.exists() else None
    ahead = dt.datetime.now(dt.UTC) + dt.timedelta(hours=1)
    descriptor = os.open(path.with_name(path.name + ".test"),
                         os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump({"runId": profile.run_id, "instant": ahead.isoformat()}, stream)
    os.replace(path.with_name(path.name + ".test"), path)
    request_id = None
    try:
        assert host.composition.clock() == ahead
        answer = call(host.client, "/api/v2/c11/request-recovery", submission(host))
        assert answer.status_code == 200, answer.text
        request_id = answer.json()["jobId"]
    finally:
        if previous is None:
            path.unlink(missing_ok=True)
        else:
            path.write_bytes(previous)
        if request_id is not None:
            cancel(host, request_id)


def recovery_requests_with(ledger, submission_id: str) -> list[dict]:
    return [record for record in ledger.records("recovery-request")
            if record["submissionId"] == submission_id]


def test_a_recovery_request_from_an_open_incident_is_linked(host, admin):
    """Step 89(b) (L1-19, L1-64): a request from an open incident is written in one ledger
    step with the incident's investigating and recovering versions; a refusal writes
    nothing, a replay appends nothing, and a resolved incident, or one of the other
    environment (the batch-7 review), is refused before any request exists."""
    from backend.modules.operations.incidents import RECOVERY_REQUESTED
    from backend.modules.operations.recovery import WAITING

    composition = host.composition
    ledger = composition.ledger
    here = composition.environment
    other = "rehearsal" if here == "live" else "live"
    incidents = Incidents(ledger, environment=here)
    elsewhere = Incidents(ledger, environment=other)
    path = "/api/v2/c11/request-recovery"
    used: list[str] = []  # every submissionId this test sent
    signalled: list[tuple[Incidents, str]] = []

    def send(value: dict):
        used.append(value["submissionId"])
        return call(host.client, path, value)

    try:
        opened = incidents.signal("platform.status", "tolerance-exceeded")
        incident_id = opened["incidentId"]
        signalled.append((incidents, incident_id))
        assert opened["state"] == "open"
        open_revision = ledger.revision("service-incident", incident_id)
        foreign = elsewhere.signal("platform.status", "tolerance-exceeded")
        foreign_id = foreign["incidentId"]
        signalled.append((elsewhere, foreign_id))
        foreign_revision = ledger.revision("service-incident", foreign_id)
        _linked_body_checks(host, ledger, send, incident_id, open_revision, foreign_id,
                            foreign_revision, RECOVERY_REQUESTED, incidents)
    finally:
        # Clean-up, test-only: every request a submission of this test recorded and still
        # waiting is cancelled, then each incident it signalled is resolved, so the
        # realm's ledger holds nothing unresolved from this test.
        for submitted in used:
            for record in recovery_requests_with(ledger, submitted):
                current = ledger.get("recovery-request", record["recoveryRequestId"])
                if current["state"] in WAITING:
                    cancel(host, record["recoveryRequestId"])
        for owner, identity in signalled:
            current = ledger.get("service-incident", identity)
            if current["state"] == "resolved":
                continue
            if current["environment"] == "live":
                owner.resolve(identity, "environment-stopped", ["test:step-89b-cleanup"])
            else:
                # `environment-stopped` is live's alone; the other environment's incident,
                # which no request ever linked, is resolved by its capability's state.
                owner.resolve(identity, "capability-available", ["test:step-89b-cleanup"],
                              states={name: CapabilityState(name, "available", None)
                                      for name in current["capabilities"]})


def _linked_body_checks(host, ledger, send, incident_id, open_revision, foreign_id,
                        foreign_revision, recovery_requested, incidents) -> None:
    """The body of Step 89(b)'s test, run inside its clean-up."""

    def unchanged() -> None:
        current = ledger.get("service-incident", incident_id)
        assert current["state"] == "open"
        assert ledger.revision("service-incident", incident_id) == open_revision
        assert "diagnosisKey" not in current and current["recoveryRequestIds"] == []

    # A refused request writes nothing (L1-64).
    body = submission(host, incidentId=incident_id)
    stale = {**body, "expectedRevision": str(int(body["expectedRevision"]) + 1),
             "submissionId": str(uuid4())}
    answer = send(stale)
    assert (answer.status_code, answer.json()["code"]) == (409, "CONFLICT")
    unchanged()
    assert recovery_requests_with(ledger, stale["submissionId"]) == []
    missing = submission(host, incidentId=incident_id, operation="restore.verify",
                         targetId=str(uuid4()), expectedRevision="1")
    answer = send(missing)
    assert (answer.status_code, answer.json()["code"]) == (404, "NOT_FOUND")
    unchanged()
    assert recovery_requests_with(ledger, missing["submissionId"]) == []
    # An unresolved incident of the other environment, named in a request that would
    # otherwise be accepted (the batch-7 review): not found, nothing written.
    named_elsewhere = submission(host, incidentId=foreign_id)
    answer = send(named_elsewhere)
    assert (answer.status_code, answer.json()["code"]) == (404, "NOT_FOUND")
    current = ledger.get("service-incident", foreign_id)
    assert current["state"] == "open" and current["recoveryRequestIds"] == []
    assert "diagnosisKey" not in current
    assert ledger.revision("service-incident", foreign_id) == foreign_revision
    assert recovery_requests_with(ledger, named_elsewhere["submissionId"]) == []
    unchanged()
    # The request from the open incident: one ledger step, in L1-19's order.
    head = ledger.head.count
    first = send(body)
    assert first.status_code == 200, first.text
    job = first.json()["jobId"]
    current = ledger.get("service-incident", incident_id)
    assert current["state"] == "recovering"
    assert ledger.revision("service-incident", incident_id) == open_revision + 2
    assert current["diagnosisKey"] == recovery_requested == "recovery-requested"
    assert current["recoveryRequestIds"] == [job]
    entries = ledger.store.entries_after(head)
    steps = [(entry.kind, entry.record.get("state")) for entry in entries]
    assert steps == [("service-incident", "investigating"),
                     ("recovery-request", "requested"),
                     ("service-incident", "recovering")]
    assert entries[1].record["recoveryRequestId"] == job
    assert entries[1].record["incidentId"] == incident_id
    # A replay of the same submission appends nothing.
    replayed = send(body)
    assert replayed.status_code == 200 and replayed.json()["jobId"] == job
    assert ledger.get("service-incident", incident_id)["recoveryRequestIds"] == [job]
    assert ledger.revision("service-incident", incident_id) == open_revision + 2
    # A second request from the now-recovering incident (L1-64).
    again = send(submission(host, incidentId=incident_id))
    assert again.status_code == 200, again.text
    second_job = again.json()["jobId"]
    assert second_job != job
    current = ledger.get("service-incident", incident_id)
    assert current["state"] == "recovering"
    assert ledger.revision("service-incident", incident_id) == open_revision + 3
    assert current["recoveryRequestIds"] == [job, second_job]
    # Both requests cancelled and the incident resolved, then a resolved incident is
    # refused before any request exists (L1-64).
    cancel(host, job)
    cancel(host, second_job)
    incidents.resolve(incident_id, "environment-stopped", ["test:step-89b-cleanup"])
    resolved_revision = ledger.revision("service-incident", incident_id)
    late = submission(host, incidentId=incident_id)
    answer = send(late)
    assert (answer.status_code, answer.json()["code"]) == (409, "CONFLICT")
    assert recovery_requests_with(ledger, late["submissionId"]) == []
    replayed = send(body)
    assert replayed.status_code == 200 and replayed.json()["jobId"] == job
    assert ledger.revision("service-incident", incident_id) == resolved_revision


def test_the_incident_list_holds_at_most_50_rows(tmp_path, clock):
    """Step 89(d) (L1-63): `list-incidents` answers at most 50 a page, the open one first,
    and the next page the one left out; `read()` keeps its page of up to 200."""
    from backend.modules.operations.dashboard import INCIDENT_LIMIT, MAX_LIMIT

    clock.now = NOW
    ledger = open_ledger(tmp_path, clock)
    incidents = Incidents(ledger, environment="live")
    opened = []
    for index in range(51):
        clock.now = NOW + dt.timedelta(seconds=index)
        record = incidents.signal("platform.status", "tolerance-exceeded")
        opened.append(record["incidentId"])
        if index < 50:
            incidents.resolve(record["incidentId"], "environment-stopped", ["test:step-89d"])
    dashboard = Dashboard(States(), ledger, environment="live", clock=clock)
    first = dashboard.incidents({"page": {"limit": 200}})
    wire.OpsIncidentReadPage.model_validate(first)
    assert (INCIDENT_LIMIT, MAX_LIMIT) == (50, 200)
    assert len(first["items"]) == 50 and first["page"]["nextCursor"]
    assert first["items"][0]["incidentId"] == opened[-1]  # the open one first
    assert dashboard.incidents({"page": {}})["items"] == first["items"]
    rest = dashboard.incidents({"page": {"limit": 200, "cursor": first["page"]["nextCursor"]}})
    assert len(rest["items"]) == 1 and rest["page"]["nextCursor"] is None
    both = [item["incidentId"] for item in first["items"] + rest["items"]]
    assert sorted(both) == sorted(opened)


# --- the dashboard's contents over a real ledger (Step 61) ------------------------------

NOW = dt.datetime(2026, 10, 31, 16, 0, tzinfo=dt.UTC)  # 2026-11-01 01:00 in Seoul


class States:
    """A readiness view over fixed derived states: the dashboard reads only `states()`."""

    def __init__(self, *states: CapabilityState):
        self.value = {state.capability: state for state in states}

    def states(self) -> dict:
        return dict(self.value)


class Lanes:
    """A lane reader over fixed answers (`LaneCounts.read`'s shape); None is a lane whose
    read failed."""

    def __init__(self, answers: dict):
        self.answers = answers

    def read(self, now, *, lanes=LANES) -> dict:
        return {lane: self.answers.get(lane) for lane in lanes}


class Allowance:
    @staticmethod
    def counts():
        return {"day": "2026-10-23", "month": "2026-10", "daily": 0, "monthly": 12}


def fresh_ledger(tmp_path, name: str, clock):
    """A second real ledger in the test's own folder."""
    folder = tmp_path / name
    folder.mkdir()
    return open_ledger(folder, clock)


def grouped(dashboard: Dashboard) -> dict[str, list[dict]]:
    page = wire.OpsDashboardPage.model_validate(dashboard.read({"page": {"limit": 200}}))
    found: dict[str, list[dict]] = {}
    for item in page.model_dump(mode="json")["items"]:
        found.setdefault(item["capability"], []).append(item)
    return found


def standing(dashboard: Dashboard) -> dict:
    [item] = grouped(dashboard)["operations.standing-job"]
    return item


def verification(ledger, backup_id: str, at: dt.datetime, result: str = "verified",
                 **fields) -> dict:
    record = {"verificationId": fields.pop("verificationId", str(uuid4())),
              "environment": "live", "backupId": backup_id, "startedAt": utc_text(at),
              "finishedAt": utc_text(at), "registerHeadSequence": 4,
              "registerHeadDigest": secrets.token_hex(32),
              "evidenceRef": f"verification/{secrets.token_hex(4)}", "result": result,
              "integrity": "passed" if result == "verified" else "failed", **fields}
    if result == "verified":
        record.update(erasedOwnersSurviving=0, scratchRemovedAt=utc_text(at))
    ledger.append("restore-verification", record, expect_revision=0)
    return record


def isolation_file(folder, checked: dt.datetime, labels: list[str], **fields) -> dict:
    folder.mkdir(parents=True, exist_ok=True)
    value = {"resultId": str(uuid4()), "checkedAt": checked.isoformat(), "items": [],
             "passed": True,
             "stopRecords": [{"label": label, "receiptId": str(uuid4()),
                              "stoppedAt": checked.isoformat(),
                              "expiresAt": (checked + dt.timedelta(days=1)).isoformat()}
                             for label in labels], **fields}
    (folder / f"{checked:%Y%m%dT%H%M%SZ}.json").write_text(json.dumps(value))
    return value


def latency_lines(folder, now: dt.datetime, rows: list[dict]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{now:%Y-%m-%d}.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows) + "not-json\n")


def scheduled(ledger, clock, at: dt.datetime, *, operation: str = "backup.create",
              environment: str = "live", target: str | None = None, end: str = "failed",
              evidence=(), disk_room=None, before_end=None) -> str:
    """One standing-job request through RecoveryRequests' own moves, at `at`."""
    clock.now = at
    requests = RecoveryRequests(ledger, PRODUCTION_OPERATIONS, clock=clock)
    target = target or environment
    expected = (requests.backup_revision(environment) if operation == "backup.create"
                else ledger.revision("backup-set", target))
    request_id = requests.request(origin="schedule", operation=operation,
                                  environment=environment, target_id=target,
                                  expected_revision=expected,
                                  submission_id=uuid4())["recoveryRequestId"]
    if end == "cancelled":
        requests.cancel(request_id)
    if end in ("requested", "cancelled"):
        return request_id
    requests.admit(request_id)
    if end == "awaiting-operator" or requests.start(
            request_id, disk_room=disk_room)["state"] != "running":
        return request_id
    if before_end is not None:
        before_end(request_id)
    requests.advance(request_id, "failed", allowed_from=("running",), evidence=evidence)
    return request_id


def test_the_dashboard_items_for_sets_verifications_requests_counts_and_summaries(
    tmp_path, clock,
):
    now = clock()
    stamp = utc_text(now)
    ledger = open_ledger(tmp_path, clock)
    live = set_record(ledger, now=now, database="docsuri_v2")
    for days in (20, 30):  # its retainUntil moved later twice: three versions
        live = {**live, "retainUntil": utc_text(now + dt.timedelta(days=days))}
        ledger.append("backup-set", live,
                      expect_revision=ledger.revision("backup-set", live["backupId"]))
    set_record(ledger, now=now, database="docsuri_v2", disposedAt=stamp)
    set_record(ledger, now=now, environment="rehearsal", integrity="failed",
               trigger="requested", database="docsuri_v2_rehearsal_0123456789ab")
    verification(ledger, live["backupId"], now)
    request_id = scheduled(ledger, clock, now, end="awaiting-operator")
    incidents = Incidents(ledger, environment="live")
    unresolved = incidents.signal("storage.capacity", "tolerance-exceeded")
    incidents.begin_diagnosis(unresolved["incidentId"], "disk-low")
    incidents.link_recovery(unresolved["incidentId"], request_id)
    done = incidents.signal("operations.ledger", "operator")
    incidents.resolve(done["incidentId"], "capability-available", ["e1"], states={
        "operations.ledger": CapabilityState("operations.ledger", "available", None)})
    latency = tmp_path / "latency"
    latency_lines(latency, now.astimezone(dt.UTC), [
        {"window": stamp, "class": "read", "count": 100, "p95Ms": 120.5, "errors5xx": 3},
        {"window": stamp, "class": "search", "count": 5, "p95Ms": 340.0, "errors5xx": 1},
        {"window": stamp, "class": "health", "count": 0, "p95Ms": None, "errors5xx": 0}])
    readiness = States(CapabilityState("storage.capacity", "stale", "observation-stale", (),
                                       400, now, 2, 40))
    dashboard = Dashboard(readiness, ledger, environment="live", clock=clock,
                          allowance=Allowance(), latency_folder=latency,
                          availability_folder=tmp_path / "availability")
    by_capability = grouped(dashboard)
    capacity = by_capability["storage.capacity"][0]
    assert (capacity["status"], capacity["freshness"], capacity["ageSeconds"]) == (
        "unknown", "stale", 400)
    assert "error-rate-permille:50" in capacity["limitations"]
    assert [item["evidenceRef"] for item in by_capability["operations.backup-set"]] == [
        live["backupId"]]
    shown = by_capability["operations.backup-set"][0]
    assert f"revision:{ledger.revision('backup-set', live['backupId'])}" in shown["limitations"]
    assert "revision:3" in shown["limitations"]
    assert f"retain-until:{ledger.get('backup-set', live['backupId'])['retainUntil']}" in (
        shown["limitations"])
    live_sets = RecoveryRequests(ledger, PRODUCTION_OPERATIONS).backup_revision("live")
    assert by_capability["operations.backup-revision"][0]["limitations"] == [
        f"revision:{live_sets}"] == ["revision:2"]
    assert by_capability["operations.restore-verification"][0]["status"] == "available"
    request = by_capability["operations.recovery-request"][0]
    stored = ledger.get("recovery-request", request_id)
    assert (stored["state"], stored["revision"]) == ("awaiting-operator", 2)
    assert request["status"] == "degraded" and "state:awaiting-operator" in request["limitations"]
    assert by_capability["operations.email-allowance"][0]["limitations"] == ["daily:0",
                                                                             "monthly:12"]
    latency_items = {item["component"]: item for item in by_capability["operations.latency"]}
    assert "p95-ms:120" in latency_items["read"]["limitations"]
    assert "error-rate-permille:30" in latency_items["read"]["limitations"]
    assert latency_items["read"]["status"] == "degraded"
    assert {"p95-ms:340", "error-rate-permille:200"} <= set(
        latency_items["search"]["limitations"])
    assert latency_items["search"]["status"] == "degraded"
    assert "p95-ms:unknown" in latency_items["health"]["limitations"]
    assert latency_items["health"]["status"] == "available"
    assert not any(entry.startswith("error-rate-permille:")
                   for entry in latency_items["health"]["limitations"])
    assert "operations.availability" not in by_capability  # no record line yet
    listed = wire.OpsIncidentReadPage.model_validate(dashboard.incidents({"page": {}})
                                                     ).model_dump(mode="json")["items"]
    opened = ledger.get("service-incident", unresolved["incidentId"])
    assert opened["state"] == "recovering"
    assert [item["incidentId"] for item in listed] == [unresolved["incidentId"],
                                                       done["incidentId"]]
    assert {"opened:" + opened["openedAt"], "role:ordinary", "diagnosis:disk-low",
            f"recovery:{request_id}"} == set(listed[0]["evidenceRefs"])
    assert listed[1]["resolutionKind"] == "capability-available"
    assert dashboard.incidents({"page": {}, "capability": "operations.ledger"})["items"][0][
        "incidentId"] == done["incidentId"]


def test_the_dashboard_reads_the_months_availability(tmp_path, clock):
    from docsuri_ops.standing.lanes import slot_of

    folder = tmp_path / "availability"
    AvailabilityRecord(folder).append(slot_of(clock() - dt.timedelta(minutes=10)), True, "ok")
    dashboard = Dashboard(States(), open_ledger(tmp_path, clock), environment="live",
                          clock=clock, availability_folder=folder)
    [item] = [item for item in dashboard.items()
              if item["capability"] == "operations.availability"]
    assert any(entry.startswith("availability-permille:") for entry in item["limitations"])
    assert any(entry.startswith("budget-left-seconds:") for entry in item["limitations"])


def test_the_dashboard_holds_every_part_of_section_4(tmp_path, clock):
    clock.now = NOW
    ledger = open_ledger(tmp_path, clock)
    sets = [set_record(ledger, now=NOW - dt.timedelta(hours=hours), database=database)
            for hours, database in ((3, "docsuri_v2"), (2, "docsuri_v2"),
                                    (1, "docsuri_v2_rehearsal_0123456789ab"))]
    times = [(60, 1200), (135, 2700), (180, 3600), (90, None)]
    checks = []
    for index, (rebuild, projected) in enumerate(times):
        fields = {"hnswRebuildSeconds": rebuild}
        if projected is not None:
            fields["hnswProjectedSeconds"] = projected
        checks.append(verification(ledger, sets[0]["backupId"],
                                   NOW - dt.timedelta(minutes=10 * (index + 1)), **fields))
    for _ in range(2):
        scheduled(ledger, clock, NOW, end="requested")
    incidents = Incidents(ledger, environment="live")
    done = incidents.signal("operations.ledger", "operator")
    incidents.resolve(done["incidentId"], "capability-available", ["e1"], states={
        "operations.ledger": CapabilityState("operations.ledger", "available", None)})
    unresolved = incidents.signal("storage.capacity", "tolerance-exceeded")
    isolation = tmp_path / "isolation"
    older = isolation_file(isolation, NOW - dt.timedelta(minutes=60), ["dev.docsuri.worker-purge"])
    newer = isolation_file(isolation, NOW - dt.timedelta(minutes=10),
                           ["dev.docsuri.api", "dev.docsuri.web"])
    availability = tmp_path / "availability"
    record = AvailabilityRecord(availability)
    start = dt.datetime(2026, 10, 31, 15, 0, tzinfo=dt.UTC)  # 2026-11-01 00:00 in Seoul
    for slot in range(12):
        if slot == 7:
            continue  # missing
        down = slot == 4
        record.append(start + dt.timedelta(minutes=5 * slot), not down,
                      "public-unreachable" if down else "ok")
    latency = tmp_path / "latency"
    rows = []
    for minutes, count, errors, p95 in ((10, 1, 0, 10.0), (5, 4, 1, 20.0)):
        window = utc_text(NOW - dt.timedelta(minutes=minutes))
        rows += [{"window": window, "class": name, "count": count, "p95Ms": p95,
                  "errors5xx": errors} for name in ROUTE_CLASSES]
    latency_lines(latency, NOW, rows)
    states = States(CapabilityState("storage.capacity", "degraded", "disk-low", ("disk-low",),
                                    30, NOW, 2, 8),
                    CapabilityState("operations.ledger", "available", None, (), 10, NOW))
    dashboard = Dashboard(states, ledger, environment="live", clock=clock,
                          policy=PRODUCTION_OPERATIONS, latency_folder=latency,
                          availability_folder=availability, isolation_folder=isolation)
    found = grouped(dashboard)
    capacity, ledger_item = found["storage.capacity"][0], found["operations.ledger"][0]
    assert (capacity["status"], capacity["ageSeconds"]) == ("degraded", 30)
    assert capacity["limitations"] == ["disk-low", "disk-low", "error-rate-permille:250"]
    assert (ledger_item["status"], ledger_item["ageSeconds"], ledger_item["limitations"]) == (
        "available", 10, [])
    shown = {item["evidenceRef"]: item for item in found["operations.backup-set"]}
    assert set(shown) == {item["backupId"] for item in sets}
    for item in sets:
        assert f"retain-until:{item['retainUntil']}" in shown[item["backupId"]]["limitations"]
        assert shown[item["backupId"]]["component"] == item["databaseIncarnation"]
    checked = {item["evidenceRef"]: item["limitations"]
               for item in found["operations.restore-verification"]}
    for record_value, (rebuild, projected) in zip(checks, times, strict=True):
        limitations = checked[record_value["verificationId"]]
        assert "restore-bound-seconds:2700" in limitations
        assert f"hnsw-rebuild-seconds:{rebuild}" in limitations
        projections = [entry for entry in limitations if entry.startswith("hnsw-projected")]
        assert projections == ([] if projected is None
                               else [f"hnsw-projected-seconds:{projected}"])
        assert ("hnsw-projection-past-bound" in limitations) == (projected == 3600)
    [result] = found["operations.isolation-result"]
    assert result["evidenceRef"] == f"isolation:{newer['resultId']}"
    assert result["limitations"] == [f"stop:{stop['label']}:{stop['expiresAt']}"
                                     for stop in newer["stopRecords"]]
    assert older["resultId"] not in json.dumps(found)
    [month] = found["operations.availability"]
    assert {"availability-permille:833", "budget-left-seconds:25200"} <= set(
        month["limitations"])
    for item in found["operations.latency"]:
        assert dt.datetime.fromisoformat(item["observedAt"]) == NOW - dt.timedelta(minutes=5)
        assert {"p95-ms:20", "count:4", "error-rate-permille:250"} <= set(item["limitations"])
    assert len(found["operations.latency"]) == len(ROUTE_CLASSES)
    assert dashboard.incidents({"page": {}})["items"][0]["incidentId"] == (
        unresolved["incidentId"])


def test_the_whole_dashboard_fits_one_read(tmp_path, clock):
    clock.now = NOW
    ledger = open_ledger(tmp_path, clock)
    sets = [set_record(ledger, now=NOW - dt.timedelta(minutes=index + 1),
                       database="docsuri_v2") for index in range(21)]
    for index in range(6):
        verification(ledger, sets[0]["backupId"], NOW - dt.timedelta(minutes=index + 1))
    for _ in range(21):
        scheduled(ledger, clock, NOW, end="requested")
    latency = tmp_path / "latency"
    latency_lines(latency, NOW, [{"window": utc_text(NOW), "class": name, "count": 1,
                                  "p95Ms": 5.0, "errors5xx": 0} for name in ROUTE_CLASSES])
    availability = tmp_path / "availability"
    AvailabilityRecord(availability).append(NOW - dt.timedelta(minutes=5), True, "ok")
    isolation = tmp_path / "isolation"
    isolation_file(isolation, NOW, [])
    states = States(*(CapabilityState(name, "available", None, (), 1, NOW)
                      for name in CAPABILITY_BY_ID))
    dashboard = Dashboard(states, ledger, environment="live", clock=clock,
                          allowance=Allowance(), latency_folder=latency,
                          availability_folder=availability, isolation_folder=isolation,
                          lane_counts=Lanes({lane: (0, 1) for lane in LANES}))
    page = dashboard.read({"page": {"limit": 200}})
    wire.OpsDashboardPage.model_validate(page)
    counted: dict[str, int] = {}
    for item in page["items"]:
        counted[item["capability"]] = counted.get(item["capability"], 0) + 1
    assert counted["operations.backup-set"] == 20 and counted["operations.backup-revision"] == 1
    assert counted["operations.restore-verification"] == 5
    assert counted["operations.recovery-request"] == 20
    assert sum(counted[name] for name in CAPABILITY_BY_ID) == 25
    assert counted["operations.latency"] == 9 and counted["operations.lane"] == 6
    for name in ("operations.email-allowance", "operations.availability",
                 "operations.standing-job", "operations.isolation-result"):
        assert counted[name] == 1, name
    assert len(page["items"]) == 90 and page["page"]["nextCursor"] is None


def test_the_dashboard_counts_the_first_month_from_admission_opening(tmp_path, clock):
    clock.now = dt.datetime(2026, 11, 16, 1, 0, tzinfo=dt.UTC)
    ledger = open_ledger(tmp_path, clock)
    record = cutover_record(ledger, "preparing")
    for state in ("rehearsing", "ready-to-switch", "switching"):
        record = advance_cutover(ledger, record, state)
    record = advance_cutover(ledger, record, "switched",
                             admissionOpenedAt="2026-11-15T15:00:00.000Z")
    folder = tmp_path / "availability"
    folder.mkdir()
    lines = []
    slot, end = dt.datetime(2026, 10, 31, 15, tzinfo=dt.UTC), dt.datetime(2026, 11, 16, 1,
                                                                          tzinfo=dt.UTC)
    down_from, missing = dt.datetime(2026, 11, 15, 12, tzinfo=dt.UTC), dt.datetime(
        2026, 11, 15, 20, tzinfo=dt.UTC)
    while slot < end:
        if slot != missing:
            down = down_from <= slot < down_from + dt.timedelta(minutes=5 * 36)
            lines.append(json.dumps({"reason": "public-unreachable" if down else "ok",
                                     "slot": utc_text(slot).replace(".000", ""),
                                     "up": not down}, sort_keys=True))
        slot += dt.timedelta(minutes=5)
    (folder / "2026-11.jsonl").write_text("\n".join(lines) + "\n")

    def month_item() -> list[str]:
        dashboard = Dashboard(States(), ledger, environment="live", clock=clock,
                              availability_folder=folder)
        [item] = grouped(dashboard)["operations.availability"]
        return item["limitations"]

    assert {"availability-permille:991", "budget-left-seconds:12600"} <= set(month_item())
    advance_cutover(ledger, record, "switched", admissionOpenedAt="2026-10-20T00:00:00.000Z")
    assert {"availability-permille:991", "budget-left-seconds:14700"} <= set(month_item())


def test_the_dashboard_counts_slots_of_the_policys_length(tmp_path, clock):
    clock.now = dt.datetime(2026, 10, 31, 15, 1, 40, tzinfo=dt.UTC)
    folder = tmp_path / "availability"
    record = AvailabilityRecord(folder, slot_seconds=5)
    start = dt.datetime(2026, 10, 31, 15, tzinfo=dt.UTC)
    for index in range(20):
        if index == 11:
            continue  # missing
        down = index == 3
        record.append(start + dt.timedelta(seconds=5 * index), not down,
                      "local-unreachable" if down else "ok")
    dashboard = Dashboard(States(), open_ledger(tmp_path, clock), environment="live",
                          clock=clock, availability_folder=folder, policy=SYNTHETIC_OPERATIONS)
    [item] = grouped(dashboard)["operations.availability"]
    assert {"availability-permille:900", "budget-left-seconds:25910"} <= set(item["limitations"])


def test_the_standing_jobs_last_run_and_failures(tmp_path, clock):
    folder = tmp_path / "availability"
    folder.mkdir()
    (folder / "2026-11.jsonl").write_text("")
    AvailabilityRecord(folder).append(dt.datetime(2026, 10, 31, 14, 55, tzinfo=dt.UTC), False,
                                      "public-unreachable")
    clock.now = dt.datetime(2026, 10, 31, 15, 2, tzinfo=dt.UTC)
    empty = Dashboard(States(), fresh_ledger(tmp_path, "empty", clock), environment="live",
                      clock=clock, availability_folder=folder)
    item = standing(empty)
    assert (dt.datetime.fromisoformat(item["observedAt"]), item["ageSeconds"],
            item["status"]) == (dt.datetime(2026, 10, 31, 14, 55, tzinfo=dt.UTC), 420,
                                "available")
    clock.now = dt.datetime(2026, 10, 31, 15, 5, 1, tzinfo=dt.UTC)
    item = standing(empty)
    assert (item["ageSeconds"], item["status"]) == (601, "degraded")
    assert "standing-job-late" in item["limitations"]

    hour = dt.timedelta(hours=1)
    ledger = open_ledger(tmp_path, clock)
    copies = RetainedCopies(ledger, PRODUCTION_OPERATIONS, clock=clock)
    expired = scheduled(ledger, clock, NOW - 50 * hour, end="requested")
    scheduled(ledger, clock, NOW - 25 * hour)  # failed, outside the 24 hours
    clock.now = NOW - 10 * hour
    passed = set_record(ledger, now=clock(), database="docsuri_v2")
    scheduled(ledger, clock, NOW - 6 * hour, before_end=lambda request: set_record(
        ledger, now=clock(), database="docsuri_v2", integrity="failed",
        recoveryRequestId=request))
    clock.now = NOW - 5 * hour
    mfa = {"current": True}
    admin_requests = RecoveryRequests(ledger, PRODUCTION_OPERATIONS, clock=clock,
                                      mfa_current=lambda who, at: mfa["current"])
    refused = admin_requests.request(
        origin="administrator", operation="backup.create", environment="live",
        target_id="live", expected_revision=admin_requests.backup_revision("live"),
        submission_id=uuid4(), requested_by=uuid4(), mfa_verified_at=utc_text(clock()))
    admin_requests.admit(refused["recoveryRequestId"])
    mfa["current"] = False
    assert admin_requests.start(refused["recoveryRequestId"])["evidenceRefs"] == [
        "refused:mfa-not-current"]
    set_record(ledger, now=clock(), database="docsuri_v2", integrity="failed",
               trigger="first-live")
    scheduled(ledger, clock, NOW - 4 * hour, operation="restore.verify",
              target=passed["backupId"], before_end=lambda request: verification(
                  ledger, passed["backupId"], clock(), result="failed",
                  verificationId=str(uuid5(NAMESPACE_URL, f"docsuri-verification:{request}"))))
    scheduled(ledger, clock, NOW - 3.5 * hour, operation="restore.verify",
              target=passed["backupId"], evidence=["failed:register-damaged"])
    low = scheduled(ledger, clock, NOW - 3 * hour, operation="restore.verify",
                    target=passed["backupId"], disk_room=lambda request: False)
    assert ledger.get("recovery-request", low)["evidenceRefs"] == ["refused:internal-disk-low"]
    clock.now = NOW - 2 * hour
    RecoveryRequests(ledger, PRODUCTION_OPERATIONS, clock=clock).admit(expired)
    assert ledger.get("recovery-request", expired)["state"] == "expired"
    scheduled(ledger, clock, NOW - 1.5 * hour, end="cancelled")
    scheduled(ledger, clock, NOW - hour, environment="rehearsal")
    clock.now = NOW - hour
    set_record(ledger, now=clock(), database="docsuri_v2", lastDisposalFailedAt=utc_text(clock()))
    clock.now = NOW - 49 * hour
    scratch = copies.record("scratch-restore", "scratch/one", ["database/docsuri_u8s1"])
    clock.now = NOW - 48 * hour
    copies.disposal_pending(scratch["copyId"])
    clock.now = NOW - 3 * hour
    pending = ledger.get("retained-copy", scratch["copyId"])
    ledger.append("retained-copy", {**pending, "lastDisposalFailedAt": utc_text(clock())},
                  expect_revision=ledger.revision("retained-copy", scratch["copyId"]))
    clock.now = NOW - 61 * 24 * hour
    in_use = copies.record("rehearsal-database", "rehearsal/one",
                           ["database/docsuri_v2_rehearsal_00000000aaaa"])
    clock.now = NOW - 24 * hour
    copies.disposal_pending(in_use["copyId"])
    clock.now = NOW
    AvailabilityRecord(folder).append(NOW - dt.timedelta(minutes=5), True, "ok")
    dashboard = Dashboard(States(), ledger, environment="live", clock=clock,
                          availability_folder=folder)
    item = standing(dashboard)
    assert {"failed-backups:2", "failed-verifications:3", "failed-disposals:2"} <= set(
        item["limitations"])
    assert item["status"] == "degraded" and "standing-job-late" not in item["limitations"]

    # The rehearsal dashboard, with a waiting rehearsal set of a removed database.
    removed = copies.record("rehearsal-database", "rehearsal/two",
                            ["database/docsuri_v2_rehearsal_00000000bbbb"])
    copies.disposal_pending(removed["copyId"])
    copies.disposed(removed["copyId"], receipt("platform.database.drop", "rehearsal", now=NOW))
    set_record(ledger, now=NOW - hour, environment="rehearsal",
               database="docsuri_v2_rehearsal_00000000bbbb",
               lastDisposalFailedAt=utc_text(NOW - hour))
    rehearsal = Dashboard(States(), ledger, environment="rehearsal", clock=clock,
                          availability_folder=folder)
    assert {"failed-backups:1", "failed-verifications:0", "failed-disposals:1"} <= set(
        standing(rehearsal)["limitations"])

    # No line at all: unknown, with the counts still shown.
    bare = tmp_path / "no-lines"
    bare.mkdir()
    item = standing(Dashboard(States(), ledger, environment="live", clock=clock,
                              availability_folder=bare))
    assert item["status"] == "unknown" and item["limitations"][0] == "standing-job-unrecorded"
    assert "failed-backups:2" in item["limitations"] and item.get("ageSeconds") is None


def test_the_dashboard_shows_failed_jobs_per_lane(tmp_path, clock):
    clock.now = NOW
    answers = {"research": (1, 4), "assistance": (0, 2), "topics": (1, 3), "export": (0, 1),
               "corpus": (0, 0), "lifecycle": (1, 2)}
    lanes = Lanes(answers)
    dashboard = Dashboard(States(), open_ledger(tmp_path, clock), environment="live",
                          clock=clock, lane_counts=lanes)
    items = grouped(dashboard)["operations.lane"]
    assert [item["component"] for item in items] == list(LANES)
    for item in items:
        failed, terminal = answers[item["component"]]
        assert item["limitations"] == [f"failed:{failed}", f"terminal:{terminal}"]
        assert item["status"] == ("degraded" if failed else "available")
    producer = BackgroundWorkProducer(lambda: {"state": "idle", "timeouts": 0},
                                      wall_clock=lambda: NOW, scheduler_pass=lambda: NOW,
                                      lane_counts=lanes)
    observed = producer.observe(NOW)
    assert (observed.outcome, observed.error_count, observed.total_count) == ("available", 3, 12)
    counted = Dashboard(States(CapabilityState("background.work", "available", None, (), 5, NOW,
                                               3, 12)),
                        fresh_ledger(tmp_path, "second", clock), environment="live",
                        clock=clock)
    assert "error-rate-permille:250" in grouped(counted)["background.work"][0]["limitations"]


def test_the_dashboard_names_missing_observations(tmp_path, clock):
    clock.now = NOW
    states = States(
        CapabilityState("storage.capacity", "available", None, (), 5, NOW, dropped_count=1),
        CapabilityState("operations.ledger", "available", None, (), 5, NOW, dropped_count=0))
    found = grouped(Dashboard(states, open_ledger(tmp_path, clock), environment="live",
                              clock=clock))
    assert "missing-observations:1" in found["storage.capacity"][0]["limitations"]
    assert not any(entry.startswith("missing-observations:")
                   for entry in found["operations.ledger"][0]["limitations"])


def test_a_failing_source_degrades_only_its_own_item(tmp_path, clock):
    clock.now = NOW
    ledger = open_ledger(tmp_path, clock)
    set_record(ledger, now=NOW, database="docsuri_v2")
    availability, isolation = tmp_path / "availability", tmp_path / "isolation"
    AvailabilityRecord(availability).append(NOW - dt.timedelta(minutes=5), True, "ok")
    isolation_file(isolation, NOW - dt.timedelta(hours=1), ["dev.docsuri.api"])
    answers = {lane: (0, 1) for lane in LANES} | {"export": None}
    dashboard = Dashboard(States(CapabilityState("operations.ledger", "available", None)),
                          ledger, environment="live", clock=clock,
                          availability_folder=availability, isolation_folder=isolation,
                          lane_counts=Lanes(answers))

    def present(found: dict) -> None:
        for name in ("operations.ledger", "operations.backup-set", "operations.standing-job",
                     "operations.isolation-result", "operations.lane"):
            assert found.get(name), name

    found = grouped(dashboard)
    present(found)
    lanes = {item["component"]: item for item in found["operations.lane"]}
    assert (lanes["export"]["status"], lanes["export"]["limitations"]) == (
        "unknown", ["lane-count-unavailable"])
    assert all(lanes[lane]["limitations"] == ["failed:0", "terminal:1"]
               for lane in LANES if lane != "export")
    newest = isolation / f"{NOW:%Y%m%dT%H%M%SZ}.json"
    for broken in ("not-json", json.dumps({"resultId": str(uuid4()),
                                           "checkedAt": NOW.isoformat(), "items": []})):
        newest.write_text(broken)
        found = grouped(dashboard)
        present(found)
        [result] = found["operations.isolation-result"]
        assert (result["status"], result["limitations"]) == (
            "unknown", ["isolation-result-unreadable"])
    month = availability / "2026-11.jsonl"
    month.chmod(0)
    try:
        found = grouped(dashboard)
        present(found)
        item = found["operations.standing-job"][0]
        assert item["status"] == "unknown"
        assert item["limitations"][0] == "availability-record-unreadable"
    finally:
        month.chmod(0o644)


def test_no_route_records_a_decision(host, admin):
    inventory = host.app.state.route_inventory
    c11 = sorted(path for _, path in inventory if path.startswith("/api/v2/c11/"))
    assert c11 == ["/api/v2/c11/list-incidents", "/api/v2/c11/read-dashboard",
                   "/api/v2/c11/read-recovery-status", "/api/v2/c11/request-recovery"]
    assert not any("decision" in path or "approv" in path
                   for _, path in inventory if path.startswith(("/api/v2/c11/", "/api/v2/c01/")))
    refused = call(host.client, "/api/v2/c11/request-recovery",
                   {**submission(host), "decision": "approved"})
    assert refused.status_code == 422


# --- NFR9.7: a health and an error-rate signal per component (Step 89(a)) --------------------

# NFR9.7's ten rows, as the test holds them: component, health signal, error-rate signal.
NFR9_7 = (
    ("v2 host", "health route (liveness, readiness)", "share of 5xx answers per route class"),
    ("v2 workers and scheduler", "background.work, with lanes behind their deadline",
     "failed jobs per lane over 24 hours"),
    ("Maintenance server", "answering on `127.0.0.1:18201` (heartbeat during maintenance)",
     "failed requests"),
    ("Standing job", "its last successful run time",
     "failed backups, verifications and disposals"),
    ("v2's PostgreSQL instance", "storage.capacity (footprint against the budget)",
     "failed connections and transactions seen by the host"),
    ("Model runtime", "provider.models (reachable, digest equals the pin)",
     "failed model jobs over 24 hours"),
    ("Tunnel", "the heartbeat through the public address; operations.cutover",
     "failed heartbeat probes"),
    ("Backup agent", "its status check in platform.status",
     "failed writes and disposals in its receipts"),
    ("Runtime isolation check", "platform.isolation", "failed items per check (limitations)"),
    ("Providers (Google, ORCID, Resend, Notion)", "each provider's capability",
     "refusals and over-limit answers"),
)
REQUIREMENTS = (Path(__file__).resolve().parents[3] / "aidlc/spaces/default/intents/"
                "261016-finish-v2-rebuild/construction/u8-service-operations-integration/"
                "nfr-requirements/observability-requirements.md")
HALF = "error-rate-permille:500"
# Each provider's host, where its probe's one uncredentialed request goes (L1-11).
PROBE_HOSTS = {"google": "accounts.google.com", "orcid": "orcid.org",
               "resend": "api.resend.com", "notion": "api.notion.com"}
MAINTENANCE_NOTICE = (b"<!doctype html><html lang=\"ko\"><title>DocSuri</title>"
                      b"<h1>notice</h1></html>")


def requirement_rows() -> tuple:
    """NFR9.7's table in the approved observability requirements, row by row."""
    text = REQUIREMENTS.read_text()
    section = text[text.index("**NFR9.7**"):]
    rows = []
    for line in section.splitlines()[1:]:
        if rows and not line.startswith("|"):
            break
        if line.startswith("|") and not line.startswith(("| Component", "|---")):
            rows.append(tuple(cell.strip() for cell in line.strip("|").split("|")))
    return tuple(rows)


class RecordedProviders:
    """A recording `httpx.MockTransport` per provider, on its adapter's module attribute:
    Google's and ORCID's discovery documents answer 200, Resend and Notion 401 (below 500,
    so their probes pass); any other host is refused and recorded as elsewhere."""

    def __init__(self):
        self.requests: dict[str, list] = {name: [] for name in (*PROBE_HOSTS, "elsewhere")}

    def transport(self, *providers: str):
        import httpx

        def handle(request):
            for provider in providers:
                if request.url.host == PROBE_HOSTS[provider]:
                    self.requests[provider].append(request)
                    if provider in ("google", "orcid"):
                        return httpx.Response(200,
                                              json={"issuer": f"https://{request.url.host}"})
                    return httpx.Response(401, json={"object": "error", "status": 401})
            self.requests["elsewhere"].append(request)
            raise httpx.ConnectError("not this provider's host", request=request)

        return httpx.MockTransport(handle)


class RaisingOnce:
    """The release's real `Pages`, whose `answer` raises once when armed (the injected
    fault); everything else is the real object's."""

    def __init__(self, pages):
        self.pages, self.armed = pages, False

    def answer(self, path: str):
        if self.armed:
            self.armed = False
            raise RuntimeError("an injected fault before the answer")
        return self.pages.answer(path)

    def __getattr__(self, name: str):
        return getattr(self.pages, name)


class HeldClock:
    def __init__(self, now: dt.datetime):
        self.now = now

    def __call__(self) -> dt.datetime:
        return self.now


def seed_research_jobs(standin, at: dt.datetime) -> None:
    """Row 2's inputs: one failed and one succeeded research job, written through the
    research owner's login, both changed at `at`."""
    owner, context = standin.maintainer, uuid4()
    with standin.connect("research") as conn:
        conn.execute("INSERT INTO research.context(id,owner_id,purpose) "
                     "VALUES(%s,%s,'novelty')", (context, owner))
        for state in ("failed", "succeeded"):
            conn.execute(
                "INSERT INTO research.job(id,owner_id,context_id,authority_session,kind,"
                "operation_key,input_hash,input,scope,policy,state,accepted_at,updated_at,"
                "usage_id,error_code) VALUES(%s,%s,%s,%s,'novelty-analysis',%s,%s,'{}','{}',"
                "'{}',%s,%s,%s,%s,%s)",
                (uuid4(), owner, context, uuid4(), str(uuid4()), secrets.token_hex(32),
                 state, at, at, uuid4(), "DEADLINE_EXCEEDED" if state == "failed" else None))


def seed_counts(folder, policy, at: dt.datetime) -> None:
    """One count line per kind in Step 51(a)'s format through the counts' own writer, each
    1 failed of 2: PostgreSQL's (row 5) and each provider's refusals in its answered calls
    (row 10). No `mail.sender` line, so row 2's figure stays the lanes' own."""
    from backend.u8_counts import ProcessCounts

    counts = ProcessCounts(folder, "host", policy=policy, clock=lambda: at)
    for kind in ("postgresql.connection", "provider.google", "provider.orcid",
                 "provider.resend", "provider.notion"):
        counts.record(kind, failed=True)
        counts.record(kind, failed=False)
    counts.close()


def standing_backups(ledger, policy, clock, environment: str, database: str) -> None:
    """Rows 4 and 8's inputs: two scheduled `backup.create` requests through
    RecoveryRequests' own moves, one failed with its own failed-integrity set and one
    succeeded with its own passed set, each set citing its receipt facts."""
    from tests.u8_service_operations_integration import recovery_flows as rf

    requests = RecoveryRequests(ledger, policy, clock=clock)
    for outcome in ("failed", "succeeded"):
        identity = requests.request(
            origin="schedule", operation="backup.create", environment=environment,
            target_id=environment, expected_revision=requests.backup_revision(environment),
            submission_id=uuid4())["recoveryRequestId"]
        requests.admit(identity)
        assert requests.start(identity)["state"] == "running"
        if outcome == "succeeded":
            requests.advance(identity, "verifying", allowed_from=("running",))
            requests.advance(identity, "succeeded", allowed_from=("verifying",))
        else:
            requests.advance(identity, "failed", allowed_from=("running",))
        rf.set_record(ledger, environment=environment, now=clock(), database=database,
                      integrity="passed" if outcome == "succeeded" else "failed",
                      recoveryRequestId=identity)


def maintenance_counts(tmp_path, now: dt.datetime) -> tuple[dict, tuple]:
    """Row 3: Step 74's server on an ephemeral loopback port, its log under `tmp_path` on
    an injected clock. The heartbeat's own probe gets the notice (answered); a second GET
    fails once `Pages.answer` raises. Returns the window's counted line and the heartbeat's
    classification of the notice."""
    import http.client

    from backend import maintenance_server as maintenance
    from docsuri_ops.standing import heartbeat

    build = tmp_path / "maintenance-build"
    build.mkdir()
    (build / "maintenance.html").write_bytes(MAINTENANCE_NOTICE)
    (build / "privacy.html").write_bytes(b"<h1>privacy</h1>")
    (build / "terms.html").write_bytes(b"<h1>terms</h1>")
    opened = maintenance.window_start(now)
    clock = HeldClock(opened + dt.timedelta(seconds=150))
    logs = tmp_path / "maintenance-logs"
    log = maintenance.CountedLog(logs, clock=clock)
    pages = RaisingOnce(maintenance.Pages.load(build))
    server = maintenance.MaintenanceServer(pages, port=0, public_authority="127.0.0.1:18110",
                                           log=log)
    server.start()
    try:
        port = server.httpd.server_address[1]
        notice = heartbeat.probe(f"http://127.0.0.1:{port}/health/ready")
        pages.armed = True
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        try:
            connection.request("GET", "/health/ready", headers={"Host": "127.0.0.1:18111"})
            with pytest.raises(http.client.RemoteDisconnected):
                connection.getresponse()
        finally:
            connection.close()
    finally:
        server.stop()
    clock.now = opened + maintenance.WINDOW
    assert log.flush() is True
    [line] = [json.loads(raw) for raw in (logs / maintenance.LOG_NAME).read_text().splitlines()]
    return line, (notice, heartbeat.classify(notice, heartbeat.Answer("answered", 200)))


def test_each_component_has_a_health_and_an_error_rate_signal(realm, tmp_path, monkeypatch):
    """Step 89(a) (NFR9.7): on production composed in rehearsal, with no host started, each
    of NFR9.7's ten components shows its health signal and its error-rate signal, seeded
    with one failure and one success through its producer's real input, so each figure
    reads 1 of 2. A producer whose real input is this Mac's own reads a pinned value; the
    24 h count readers read the test's own folder."""
    import httpx

    from backend.modules.accounts.integrations import digest_email, identity_providers
    from backend.modules.export import notion_session
    from backend.modules.operations import producers as p
    from backend.modules.operations.observation_store import ObservationStore
    from backend.modules.operations.observations import Observations
    from backend.request_context import LATENCY_FOLDER
    from backend.u8_host import (
        POSTGRESQL_KINDS,
        availability_folder,
        counts_reader,
        operations_dashboard,
        worker_producers,
    )
    from backend.u8_provider_probes import count_reader
    from docsuri_ops.standing.lanes import slot_of
    from tests.u8_service_operations_integration.host_flows import production_composition

    assert NFR9_7 == requirement_rows() and len(NFR9_7) == 10
    providers = RecordedProviders()
    monkeypatch.setattr(identity_providers, "network_transport",
                        lambda: providers.transport("google", "orcid"))
    monkeypatch.setattr(digest_email, "network_client", lambda **options: httpx.AsyncClient(
        transport=providers.transport("resend"), **options))
    monkeypatch.setattr(notion_session, "network_transport",
                        lambda: providers.transport("notion"))
    module_gate = notion_session._INSTALLED_GATE
    with production_composition(realm) as env:
        composition, standin = env.composition, env.standin
        # The composition's provider gate lives in production_composition's own dict.
        assert notion_session._INSTALLED_GATE is not module_gate
        composed_gate = notion_session._INSTALLED_GATE.get("gate")
        assert composed_gate is not None
        operations = composition.parts["service-operations"]
        ledger, policy = operations["ledger"], composition.policy
        environment = composition.environment
        assert environment == "rehearsal" and composition.profile.is_production
        root = composition.profile.root
        now = composition.clock()
        seeded = now - dt.timedelta(minutes=10)
        # Row 1: one latency window of class `read`, 2 answers, one of them a 5xx.
        latency = root.joinpath(*LATENCY_FOLDER)
        latency_lines(latency, seeded.astimezone(dt.UTC), [
            {"window": utc_text(seeded), "class": "read", "count": 2, "p95Ms": 80.0,
             "errors5xx": 1}])
        # Row 2: the lanes' one failed and one succeeded job, and a fresh scheduler pass.
        seed_research_jobs(standin, seeded)
        p.write_scheduler_pass(root / "evidence", dt.datetime.now(dt.UTC))
        # Rows 5 and 10: the count lines, in a folder the test owns.
        counted = tmp_path / "counts"
        seed_counts(counted, policy, seeded)
        # Rows 4 and 8: the standing job's two scheduled backups.
        standing_backups(ledger, policy, composition.clock, environment, standin.database)
        # Rows 4 and 7: two heartbeat lines within 24 hours, one ok and one where the public
        # path failed while the host answered.
        availability = availability_folder(composition)
        from docsuri_ops.standing.availability import AvailabilityRecord

        record = AvailabilityRecord(availability, slot_seconds=policy.availability_slot_seconds)
        older = slot_of(now - dt.timedelta(minutes=10), policy.availability_slot_seconds)
        newest = slot_of(now - dt.timedelta(minutes=5), policy.availability_slot_seconds)
        assert record.append(older, True, "ok")
        assert record.append(newest, False, "public-unreachable")
        # Row 9: the newest isolation result, `filter` failed and `programs` passed.
        isolation_file(p.isolation_folder(composition.profile, composition.arrangement), now,
                       [], passed=False, items=[{"item": "filter", "passed": False},
                                                {"item": "programs", "passed": True}])

        producers = worker_producers(
            composition, lambda: {"state": "idle", "passes": 1, "timeouts": 0})
        pinned = pin_producers(producers, composition, counted, POSTGRESQL_KINDS,
                               counts_reader, count_reader)
        assert pinned == {"storage.capacity", "background.work", "platform.status",
                          "provider.google", "provider.orcid", "provider.resend",
                          "provider.notion"}, pinned
        producers.append(p.HostErrorRateProducer(latency))
        store = ObservationStore(composition.transactions)
        schedule = p.ProducerSchedule(producers, Observations(store), policy, composition.clock)
        observed = schedule.run_due(composition.clock())
        assert schedule.refused == 0
        states = composition.readiness_view().states()
        dashboard = operations_dashboard(composition, operations)
        found = grouped(dashboard)
        signals = component_signals(states, found, store, utc_text(newest))
        line, (notice, classified) = maintenance_counts(tmp_path, now)
        signals["Maintenance server"] = (
            notice == heartbeat_answer() and classified == (False, "maintenance"),
            line == {"window": line["window"], "answered": 1, "failed": 1, "refused": 0})
        assert set(signals) == {row[0] for row in NFR9_7}
        missing = {component: pair for component, pair in signals.items() if pair != (True, True)}
        assert missing == {}, (missing, observed, utc_text(newest),
                               found.get("operations.standing-job"))
        # Each probe answered through its provider's recording transport (L1-11).
        assert providers.requests["elsewhere"] == []
        for name, host in PROBE_HOSTS.items():
            assert any(request.url.host == host and "authorization" not in request.headers
                       for request in providers.requests[name]), name
    # Once the composition closes, the module's own gate is back, untouched (batch 7's
    # re-review): no later test meets the closed composition's gate.
    assert notion_session._INSTALLED_GATE is module_gate
    assert module_gate.get("gate") is not composed_gate


def heartbeat_answer():
    from docsuri_ops.standing.heartbeat import Answer

    return Answer("answered", 503, True)


def pin_producers(producers: list, composition, counted, postgresql_kinds, counts_reader,
                  count_reader) -> set[str]:
    """The pins of Step 89(a): this Mac's own inputs and every 24 h count reader. Returns
    the capabilities pinned."""
    from backend.modules.operations import producers as p

    expected = getattr(composition.profile, "backup_identity", None) or None
    pinned = set()
    for producer in producers:
        if isinstance(producer, p.CapacityProducer):
            producer.volume_state = lambda: "mounted"
            producer.agent_status = lambda: {
                "volumeIdentity": expected, "available": True, "freeBytes": 10 ** 13,
                "catalogue": "intact", "findings": []}
            producer._free = lambda: 10 ** 13  # plentiful: this Mac's disk never decides
            producer.counts = counts_reader(counted, postgresql_kinds)
        elif isinstance(producer, p.BackgroundWorkProducer):
            producer.sender_counts = counts_reader(counted, ("mail.sender",))
        elif isinstance(producer, p.PlatformStatusProducer):
            # PlatformControl's inspect reader and the agent's status read this Mac's
            # store, which the stand-in does not provision: row 8's pinned answers.
            producer.inspect = lambda: {"outcome": "pass"}
            producer.agent_status = lambda: {"findings": ["backup-volume-low"]}
        elif isinstance(producer, p.ProviderProducer):
            producer.counts = count_reader(counted, producer.capability, composition.clock)
        else:
            continue
        pinned.add(producer.capability)
    return pinned


def component_signals(states: dict, found: dict, store, newest_slot: str) -> dict:
    """Each component but the maintenance server: (its health signal shows, its error-rate
    signal shows), read from Readiness, the Dashboard and the observation store."""

    def capability(name: str, state: str, reason=None, *, rate: bool = True) -> bool:
        current = states.get(name)
        if current is None or current.state != state or (
                reason is not None and current.reason != reason):
            return False
        [item] = found.get(name, [None])
        return item is not None and (not rate or HALF in item["limitations"])

    def rated(name: str) -> bool:
        current = states.get(name)
        return current is not None and (current.error_count, current.total_count) == (1, 2)

    latency = {item["component"]: item for item in found.get(LATENCY_ITEM, [])}
    lanes = {item["component"]: item for item in found.get(LANE_ITEM, [])}
    host_row = store.latest(["public.static"]).get("public.static") or {}
    [standing_item] = found.get("operations.standing-job", [{}])
    isolation = states.get("platform.isolation")
    signals = {
        "v2 host": (
            capability("public.static", "available"),
            HALF in latency.get("read", {}).get("limitations", [])
            and (host_row.get("error_count"), host_row.get("total_count")) == (1, 2)),
        "v2 workers and scheduler": (
            capability("background.work", "available") and rated("background.work"),
            lanes.get("research", {}).get("limitations") == ["failed:1", "terminal:2"]),
        "Standing job": (
            # The same instant as the newest line's slot, whatever form the page's model
            # gives the time.
            standing_item.get("observedAt") is not None
            and dt.datetime.fromisoformat(standing_item["observedAt"].replace("Z", "+00:00"))
            == dt.datetime.fromisoformat(newest_slot.replace("Z", "+00:00")),
            standing_item.get("limitations") == [
                "failed-backups:1", "failed-verifications:0", "failed-disposals:0"]),
        "v2's PostgreSQL instance": (
            capability("storage.capacity", "available", rate=False),
            rated("storage.capacity") and capability("storage.capacity", "available")),
        "Model runtime": (
            capability("provider.models", "available", rate=False),
            rated("provider.models") and capability("provider.models", "available")),
        "Tunnel": (
            capability("operations.cutover", "available", rate=False)
            and bool(found.get("operations.availability")),
            rated("operations.cutover") and capability("operations.cutover", "available")),
        "Backup agent": (
            capability("platform.status", "degraded", "backup-volume-low", rate=False),
            rated("platform.status")
            and capability("platform.status", "degraded", "backup-volume-low")),
        "Runtime isolation check": (
            isolation is not None and (isolation.state, isolation.reason) == (
                "unavailable", "runtime-isolation-lapsed"),
            isolation is not None and isolation.limitations == ("isolation-filter",)),
        "Providers (Google, ORCID, Resend, Notion)": (
            all(capability(name, "available", rate=False) for name in p_names()),
            all(rated(name) and capability(name, "available") for name in p_names())),
    }
    return signals


LATENCY_ITEM, LANE_ITEM = "operations.latency", "operations.lane"


def p_names() -> tuple[str, ...]:
    return ("provider.google", "provider.orcid", "provider.resend", "provider.notion")


# --- record 102: the readers see the classes the host recorded (Step 130(d); L2-2) -------


def test_the_dashboard_and_the_hosts_5xx_rate_read_the_classes_the_host_recorded(
    host, admin, tmp_path,
):
    from backend.modules.operations.producers import HostErrorRateProducer
    from tests.u8_service_operations_integration.host_flows import fresh_client

    latency = host.app.state.latency
    # The running host's own producer reads the folder the recorder writes.
    schedule = host.app.state.host_producers
    assert [(type(producer), producer.folder) for producer in schedule.producers] == [
        (HostErrorRateProducer, latency.folder)]

    latency.flush()  # closes the window that holds the sign-in
    sizes = {path.name: path.stat().st_size for path in latency.folder.glob("*.jsonl")}
    for _ in range(3):
        assert host.client.get("/api/v2/session").status_code == 200
    with fresh_client(host, address="198.18.251.13") as stranger:
        assert stranger.get(f"/api/v2/jobs/{uuid4()}/events").status_code == 401
    for _ in range(2):
        assert host.client.get("/api/v2/no-such-route").status_code == 503
    day = latency.flush()

    written = day.read_bytes()[sizes.get(day.name, 0):].decode()
    lines = {json.loads(raw)["class"]: json.loads(raw) for raw in written.splitlines()}
    assert {name: (lines[name]["count"], lines[name]["errors5xx"]) for name in ROUTE_CLASSES} == {
        **dict.fromkeys(ROUTE_CLASSES, (0, 0)), "read": (3, 0), "stream": (1, 0),
        "static": (2, 2)}
    assert all(isinstance(line["p95Ms"], (int, float))
               for line in lines.values() if line["count"] > 0)

    answer = call(host.client, "/api/v2/c11/read-dashboard",
                  {"page": {"limit": 50}, "capability": "operations.latency"})
    assert answer.status_code == 200, answer.text
    items = {item["component"]: item for item in answer.json()["items"]}
    assert {"count:3", "errors-5xx:0"} <= set(items["read"]["limitations"])
    assert "count:1" in items["stream"]["limitations"]
    assert {"count:2", "errors-5xx:2", "error-rate-permille:1000"} <= set(
        items["static"]["limitations"])
    assert items["static"]["status"] == "degraded"

    # The same lines alone, with the lines other tests left in the realm's folder kept out.
    copy = tmp_path / "latency"
    copy.mkdir()
    (copy / day.name).write_text(written)
    observed = HostErrorRateProducer(copy).observe(host.composition.clock())
    assert (observed.error_count, observed.total_count) == (2, 2)
