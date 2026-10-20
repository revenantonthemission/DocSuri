"""The ApprovedExport lifecycle participant over the real realm (BR6.1-BR6.5, BR7.2).

Tickets are seeded through `connect("accounts")` the way U5 seeds its own, with a live
lease, so every call runs AccountAccess's real lifecycle guard. Every test starts from
`store_flows.fresh()` and asserts only on its own account's rows and on its own
request's evidence, never on realm-wide totals.
"""

import datetime as dt
from uuid import UUID, uuid4

import psycopg
import pytest
from backend.modules.accounts.control_policy import SYNTHETIC_POLICY
from backend.modules.export.control_lifecycle import (
    COUNT_FIELDS,
    EXTERNAL_COPIES_REASON,
    ExportLifecycleParticipant,
)
from psycopg.types.json import Jsonb

from tests.u6_approved_export import store_flows as flows

ALL_SCOPES = ("live_records", "pending_work", "external_copies")
MANIFEST_REVISION = "u6-lifecycle-test"
NOW = dt.datetime(2026, 9, 24, 12, 0, tzinfo=dt.UTC)


def seed(connect, account: UUID, action: str, scopes=ALL_SCOPES) -> dict:
    """One live lifecycle request for the account; returns its ticket per scope."""
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
                Jsonb([["ApprovedExport", scope] for scope in scopes]),
            ),
        )
        for scope in scopes:
            conn.execute(
                "INSERT INTO accounts.lifecycle_scope(request_id,participant,scope,generation,"
                "lease_until,attempts) VALUES(%s,'ApprovedExport',%s,1,"
                "clock_timestamp()+interval '1 minute',1)",
                (request, scope),
            )
    return {
        scope: {
            "request_id": request,
            "account_id": account,
            "lifecycle_revision": lifecycle_revision,
            "participant": "ApprovedExport",
            "scope": scope,
            "generation": 1,
            "action": action,
            "policy_ref": SYNTHETIC_POLICY.reference,
            "manifest_revision": MANIFEST_REVISION,
        }
        for scope in scopes
    }


def participant(transactions) -> ExportLifecycleParticipant:
    return ExportLifecycleParticipant(transactions, clock=lambda: NOW)


def counts_of(connect, request: UUID) -> dict:
    with connect("export") as conn:
        rows = conn.execute(
            "SELECT * FROM export.lifecycle_counts WHERE request_id=%s", (request,)
        ).fetchall()
    return {row["scope"]: row for row in rows}


def numbers(row: dict) -> dict:
    return {field: row[field] for field in COUNT_FIELDS}


def account_rows(connect, account: UUID) -> dict:
    tables = ("connection", "preview_pair", "approval", "effect", "replay_record")
    with connect("export") as conn:
        return {
            table: conn.execute(
                f"SELECT count(*) AS n FROM export.{table} WHERE account_id=%s", (account,)
            ).fetchone()["n"]
            for table in tables
        }


def open_work(repo, connect, authority, now) -> dict:
    """A connected owner with one page exported, one unknown export, one accepted export
    and one approved, unconsumed approval (BR5.1 allows one in flight)."""
    connection = flows.connected(repo, connect, authority, now)
    exported = flows.bound(repo, authority, connection, now)
    flows.succeed(repo, exported["effect"], now)
    unknown = flows.bound(repo, authority, connection, now)
    flows.uncertain(repo, unknown["effect"], now)
    accepted = flows.bound(repo, authority, connection, now)
    preview = flows.prepare(repo, authority, connection, now)
    approval = flows.approve(repo, authority, preview, now)
    return {
        "connection": connection,
        "exported": exported,
        "unknown": unknown,
        "accepted": accepted,
        "preview": preview,
        "approval": approval,
    }


def test_withdraw_disconnects_and_ends_pending_work(transactions, connect, authority):
    repo = flows.repository(transactions)
    now = flows.at()
    work = open_work(repo, connect, authority, now)
    tickets = seed(connect, authority.account_id, "withdraw")

    result = participant(transactions).apply(tickets["live_records"])

    assert result["disposition"] == "complete" and result["reasonKey"] == "owner-scope-complete"
    assert UUID(result["evidenceRef"])
    approval = flows.approval_row(connect, work["approval"]["id"])
    assert (approval["state"], approval["invalidation_reason"]) == (
        "invalidated",
        "account-withdrawn",
    )
    effect = flows.effect_row(connect, work["accepted"]["effect"]["id"])
    assert (effect["state"], effect["outcome_reason"], effect["ended_at"]) == (
        "invalidated",
        "account-withdrawn",
        NOW,
    )
    for preview in (work["preview"], work["accepted"]["preview"]):
        assert (
            flows.revision_row(connect, preview["preview_id"], preview["revision"])["trimmed_at"]
            == NOW
        )
    connection = flows.connection_row(connect, work["connection"]["id"])
    assert connection["state"] == "disconnected"
    assert connection["revision"] == work["connection"]["revision"] + 1
    assert repo.open_token_envelope(authority.account_id, work["connection"]["id"]) is None
    assert flows.effect_row(connect, work["exported"]["effect"]["id"])["state"] == "succeeded"
    assert numbers(counts_of(connect, tickets["live_records"]["request_id"])["live_records"]) == {
        "approvals_invalidated": 1,
        "effects_invalidated": 1,
        "exports_in_flight": 0,
        "exports_unknown": 1,
        "pages_exported": 0,
        "pages_possibly_created": 0,
    }


def test_executing_export_finishes_and_unknown_is_kept(transactions, connect, authority):
    repo = flows.repository(transactions)
    now = flows.at()
    connection = flows.connected(repo, connect, authority, now)
    unknown = flows.bound(repo, authority, connection, now)
    flows.uncertain(repo, unknown["effect"], now)
    running = flows.bound(repo, authority, connection, now)
    claimed = repo.claim(running["effect"]["id"], running["effect"]["revision"], now=now)
    tickets = seed(connect, authority.account_id, "withdraw")

    participant(transactions).apply(tickets["pending_work"])

    assert flows.effect_row(connect, unknown["effect"]["id"])["state"] == "unknown"
    executing = flows.effect_row(connect, running["effect"]["id"])
    assert (executing["state"], executing["revision"]) == ("executing", claimed.effect["revision"])
    # The revision the lane holds keeps its tree: the write in hand still needs it.
    revision = flows.revision_row(
        connect, running["preview"]["preview_id"], running["preview"]["revision"]
    )
    assert revision["trimmed_at"] is None
    recorded = counts_of(connect, tickets["pending_work"]["request_id"])["pending_work"]
    assert (recorded["exports_in_flight"], recorded["exports_unknown"]) == (1, 1)
    assert (recorded["approvals_invalidated"], recorded["effects_invalidated"]) == (0, 0)


def test_withdraw_deletes_the_pending_reservation(transactions, connect, authority):
    repo = flows.repository(transactions)
    flows.fresh(connect, authority.account_id)
    slot = repo.reserve_connection(authority, None, now=flows.at())
    assert slot.pending and flows.pace_count(connect, slot.connection_id) == 1
    tickets = seed(connect, authority.account_id, "withdraw")

    participant(transactions).apply(tickets["pending_work"])

    assert flows.connection_row(connect, slot.connection_id) is None
    assert flows.pace_count(connect, slot.connection_id) == 0
    # A configure that still holds the old reservation can no longer store anything.
    assert repo.release_pending(authority, slot.holder) is False


def test_reactivate_changes_nothing_and_refuses_other_scopes(transactions, connect, authority):
    repo = flows.repository(transactions)
    now = flows.at()
    connection = flows.connected(repo, connect, authority, now)
    preview = flows.prepare(repo, authority, connection, now)
    approval = flows.approve(repo, authority, preview, now)
    tickets = seed(connect, authority.account_id, "reactivate")
    lifecycle = participant(transactions)

    results = {scope: lifecycle.apply(tickets[scope]) for scope in ALL_SCOPES}

    assert all(result["disposition"] == "complete" for result in results.values())
    assert flows.approval_row(connect, approval["id"])["state"] == "approved"
    current = flows.connection_row(connect, connection["id"])
    assert (current["state"], current["revision"]) == ("connected", connection["revision"])
    recorded = counts_of(connect, tickets["live_records"]["request_id"])
    assert {scope: row["action"] for scope, row in recorded.items()} == dict.fromkeys(
        ALL_SCOPES, "reactivate"
    )
    assert all(not any(numbers(row).values()) for row in recorded.values())
    outside = dict(tickets["live_records"], scope="derived_artifacts")
    with pytest.raises(PermissionError):
        lifecycle.apply(outside)
    with pytest.raises(PermissionError):
        lifecycle.apply(dict(tickets["live_records"], participant="TopicsDigests"))


def test_repeated_ticket_returns_the_recorded_evidence(transactions, connect, authority):
    repo = flows.repository(transactions)
    now = flows.at()
    connection = flows.connected(repo, connect, authority, now)
    first_preview = flows.prepare(repo, authority, connection, now)
    flows.approve(repo, authority, first_preview, now)
    tickets = seed(connect, authority.account_id, "withdraw")
    lifecycle = participant(transactions)
    first = lifecycle.apply(tickets["live_records"])
    after_first = flows.connection_row(connect, connection["id"])
    again = lifecycle.apply(tickets["live_records"])

    assert again == first
    # The replay runs no effect: the connection does not move again.
    assert flows.connection_row(connect, connection["id"]) == after_first
    recorded = counts_of(connect, tickets["live_records"]["request_id"])
    assert list(recorded) == ["live_records"]
    assert recorded["live_records"]["approvals_invalidated"] == 1
    with connect("export") as conn:
        evidence = conn.execute(
            "SELECT count(*) AS n FROM export.lifecycle_evidence WHERE request_id=%s",
            (tickets["live_records"]["request_id"],),
        ).fetchone()["n"]
    assert evidence == 1
    # A ticket bound to another policy is refused by AccountAccess's guard.
    bound = dict(tickets["live_records"], policy_ref={"policyId": "other", "revision": "1"})
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        lifecycle.apply(bound)


def test_erase_removes_every_row_and_keeps_count_only_evidence(transactions, connect, authority):
    repo = flows.repository(transactions)
    now = flows.at()
    work = open_work(repo, connect, authority, now)
    effect_ids = [work[name]["effect"]["id"] for name in ("exported", "unknown", "accepted")]
    tickets = seed(connect, authority.account_id, "erase")
    lifecycle = participant(transactions)

    for scope in ALL_SCOPES:
        lifecycle.apply(tickets[scope])

    assert account_rows(connect, authority.account_id) == {
        "connection": 0,
        "preview_pair": 0,
        "approval": 0,
        "effect": 0,
        "replay_record": 0,
    }
    with connect("export") as conn:
        attempts = conn.execute(
            "SELECT count(*) AS n FROM export.attempt WHERE effect_id=ANY(%s)", (effect_ids,)
        ).fetchone()["n"]
        pace = conn.execute(
            "SELECT count(*) AS n FROM export.connection_pace WHERE connection_id=%s",
            (work["connection"]["id"],),
        ).fetchone()["n"]
    assert (attempts, pace) == (0, 0)
    recorded = counts_of(connect, tickets["live_records"]["request_id"])
    assert set(recorded) == set(ALL_SCOPES)
    for row in recorded.values():
        assert set(row) == {"request_id", "scope", "action", "reason_key", "recorded_at"} | set(
            COUNT_FIELDS
        )
        assert all(type(row[field]) is int and row[field] >= 0 for field in COUNT_FIELDS)
        assert row["action"] == "erase"
    assert numbers(recorded["live_records"]) == {
        "approvals_invalidated": 1,
        "effects_invalidated": 1,
        "exports_in_flight": 0,
        "exports_unknown": 1,
        "pages_exported": 1,
        "pages_possibly_created": 1,
    }


def test_external_copies_carry_the_retained_reason(transactions, connect, authority):
    repo = flows.repository(transactions)
    now = flows.at()
    connection = flows.connected(repo, connect, authority, now)
    exported = flows.bound(repo, authority, connection, now)
    flows.succeed(repo, exported["effect"], now)
    tickets = seed(connect, authority.account_id, "withdraw")

    result = participant(transactions).apply(tickets["external_copies"])

    assert result["reasonKey"] == EXTERNAL_COPIES_REASON == "external-copies-retained-by-owner"
    recorded = counts_of(connect, tickets["external_copies"]["request_id"])["external_copies"]
    assert recorded["reason_key"] == EXTERNAL_COPIES_REASON
    assert (recorded["pages_exported"], recorded["pages_possibly_created"]) == (1, 0)
    # Nothing DocSuri holds about the owner's page changes (BR6.4).
    assert flows.effect_row(connect, exported["effect"]["id"])["state"] == "succeeded"
    assert flows.connection_row(connect, connection["id"])["state"] == "connected"


@pytest.mark.parametrize(
    "order",
    [ALL_SCOPES, ("external_copies", "pending_work", "live_records")],
    ids=["live-first", "external-first"],
)
def test_the_erase_report_is_the_same_in_any_scope_order(transactions, connect, authority, order):
    repo = flows.repository(transactions)
    open_work(repo, connect, authority, flows.at())
    tickets = seed(connect, authority.account_id, "erase")
    lifecycle = participant(transactions)

    for scope in order:
        lifecycle.apply(tickets[scope])

    recorded = counts_of(connect, tickets["live_records"]["request_id"])
    withdraw = {
        "approvals_invalidated": 1,
        "effects_invalidated": 1,
        "exports_in_flight": 0,
        "exports_unknown": 1,
    }
    pages = {"pages_exported": 1, "pages_possibly_created": 1}
    assert numbers(recorded["live_records"]) == {**withdraw, **pages}
    assert numbers(recorded["pending_work"]) == {
        **withdraw,
        "pages_exported": 0,
        "pages_possibly_created": 0,
    }
    assert numbers(recorded["external_copies"]) == {
        **dict.fromkeys(withdraw, 0),
        **pages,
    }
    assert account_rows(connect, authority.account_id)["effect"] == 0
