"""A8: AccountAccess's lifecycle projection reports the owner's Notion pages as retained.

Follows U5's pattern: the erase request and its scope rows are seeded through
`connect("accounts")`. `ControlLifecycleService` runs over a stub entry exposing only
`control_policy` and the realm's `transactions`, and drives `claim()`, the export
participant's `apply()` and `acknowledge()` for every ApprovedExport scope. It never
calls `request()`, `status_transport()` or `inspect_limited()` and never takes the
reactivate branch of `acknowledge()`: those need U2-only schema this realm lacks.
"""

from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from backend.modules.accounts.control_policy import SYNTHETIC_POLICY
from backend.modules.accounts.services.control_lifecycle import ControlLifecycleService
from backend.modules.export.control_lifecycle import ExportLifecycleParticipant
from psycopg.types.json import Jsonb

from tests.u6_approved_export import store_flows as flows

EXPORT_SCOPES = ("live_records", "pending_work", "external_copies")
FURTHER = ("UsageEntitlements", "live_records")
MANIFEST = (*(("ApprovedExport", scope) for scope in EXPORT_SCOPES), FURTHER)
MANIFEST_REVISION = "u6-projection-test"
AUDIT_REASON = "bounded-audit-identifiers-retained"


def seed_request(connect, account: UUID, action: str) -> UUID:
    request, revision = uuid4(), uuid4()
    with connect("accounts") as conn:
        conn.execute(
            "UPDATE accounts.account SET lifecycle_revision=%s WHERE id=%s", (revision, account)
        )
        conn.execute(
            "INSERT INTO accounts.lifecycle_request(id,account_id,revision,action,policy_ref,"
            "manifest_revision,manifest,disposition,reason_key) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,'pending','owner-cleanup-pending')",
            (
                request,
                account,
                revision,
                action,
                Jsonb(SYNTHETIC_POLICY.reference),
                MANIFEST_REVISION,
                Jsonb(sorted(MANIFEST)),
            ),
        )
        for participant, scope in MANIFEST:
            conn.execute(
                "INSERT INTO accounts.lifecycle_scope(request_id,participant,scope) "
                "VALUES(%s,%s,%s)",
                (request, participant, scope),
            )
    return request


def lifecycle_service(transactions) -> ControlLifecycleService:
    entry = SimpleNamespace(control_policy=SYNTHETIC_POLICY, transactions=transactions)
    return ControlLifecycleService(entry, MANIFEST, revision=MANIFEST_REVISION)


def drive(service, participant, request: UUID, scopes=EXPORT_SCOPES) -> dict:
    """Claim, apply and acknowledge each export scope, then the further scope."""
    results = {}
    for scope in scopes:
        ticket = service.claim(request, "ApprovedExport", scope)
        result = participant.apply(ticket)
        service.acknowledge(
            ticket, evidence=UUID(result["evidenceRef"]), reason=result["reasonKey"]
        )
        results[scope] = result
    further = service.claim(request, *FURTHER)
    service.acknowledge(further, evidence=uuid4(), reason=AUDIT_REASON)
    return results


def status(service, connect, request: UUID) -> dict:
    with connect("accounts") as conn:
        row = conn.execute(
            "SELECT * FROM accounts.lifecycle_request WHERE id=%s", (request,)
        ).fetchone()
        account = conn.execute(
            "SELECT * FROM accounts.account WHERE id=%s", (row["account_id"],)
        ).fetchone()
        return service._status(conn, row, account)


def scope_dispositions(value: dict) -> dict:
    return {
        (participant["participantId"], scope["scope"]): (scope["disposition"], scope["reasonKey"])
        for participant in value["participants"]
        for scope in participant["scopes"]
    }


def test_erase_reports_external_copies_as_retained_by_policy(transactions, connect, authority):
    repo = flows.repository(transactions)
    now = flows.at()
    connection = flows.connected(repo, connect, authority, now)
    exported = flows.bound(repo, authority, connection, now)
    flows.succeed(repo, exported["effect"], now)
    service = lifecycle_service(transactions)
    participant = ExportLifecycleParticipant(transactions, clock=lambda: now)
    request = seed_request(connect, authority.account_id, "erase")

    drive(service, participant, request)
    value = status(service, connect, request)

    assert (value["action"], value["state"]) == ("erase", "complete")
    assert value["completionEvidenceRef"] == str(request)
    assert scope_dispositions(value) == {
        ("ApprovedExport", "live_records"): ("erased", "owner-scope-complete"),
        ("ApprovedExport", "pending_work"): ("erased", "owner-scope-complete"),
        ("ApprovedExport", "external_copies"): (
            "retained_by_policy",
            "external-copies-retained-by-owner",
        ),
        ("UsageEntitlements", "live_records"): ("retained_by_policy", AUDIT_REASON),
    }
    assert all(p["state"] == "acknowledged" for p in value["participants"])
    # Every ApprovedExport scope points at the evidence the participant recorded.
    with connect("export") as conn:
        evidence = {
            row["scope"]: str(row["evidence_ref"])
            for row in conn.execute(
                "SELECT scope,evidence_ref FROM export.lifecycle_evidence WHERE request_id=%s",
                (request,),
            ).fetchall()
        }
    reported = {
        scope["scope"]: scope["evidenceReference"]
        for p in value["participants"]
        if p["participantId"] == "ApprovedExport"
        for scope in p["scopes"]
    }
    assert reported == evidence
    assert flows.connection_row(connect, connection["id"]) is None


def test_withdraw_reports_every_completed_scope_as_retained(transactions, connect, authority):
    repo = flows.repository(transactions)
    now = flows.at()
    connection = flows.connected(repo, connect, authority, now)
    service = lifecycle_service(transactions)
    participant = ExportLifecycleParticipant(transactions, clock=lambda: now)
    request = seed_request(connect, authority.account_id, "withdraw")

    drive(service, participant, request)
    dispositions = scope_dispositions(status(service, connect, request))

    # Only an erase erases; a withdrawal keeps the account's records (unchanged rule).
    assert {disposition for disposition, _ in dispositions.values()} == {"retained_by_policy"}
    assert flows.connection_row(connect, connection["id"])["state"] == "disconnected"


def test_a_scope_outside_the_manifest_cannot_be_claimed(transactions, connect, authority):
    flows.fresh(connect, authority.account_id)
    service = lifecycle_service(transactions)
    participant = ExportLifecycleParticipant(transactions, clock=flows.at)
    request = seed_request(connect, authority.account_id, "erase")
    with pytest.raises(PermissionError):
        service.claim(request, "ApprovedExport", "derived_artifacts")
    ticket = service.claim(request, "ApprovedExport", "pending_work")
    result = participant.apply(ticket)
    service.acknowledge(ticket, evidence=UUID(result["evidenceRef"]), reason=result["reasonKey"])
    # A second acknowledgement with other evidence is a conflict, never a new record.
    with pytest.raises(ValueError, match="conflict"):
        service.acknowledge(ticket, evidence=uuid4(), reason=result["reasonKey"])
    value = status(service, connect, request)
    assert value["state"] == "accepted"
    pending = scope_dispositions(value)
    assert pending[("ApprovedExport", "pending_work")] == ("erased", "owner-scope-complete")
    assert pending[("ApprovedExport", "live_records")] == ("pending", "pending")
