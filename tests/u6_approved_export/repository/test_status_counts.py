"""U6:logical-components:watch-counts: counts and ages only, on the caller's clock (L1-4).

The realm persists across phases, so every arrangement runs on the early `EPOCH`
(earlier than any other test's clock): the realm's accumulated real-time rows sort
after this file's, `min()` picks this file's rows for the exact ages, and the 24 h
windows assert changes against a baseline taken in the same arrangement. Both owners
are erased in `finally`, so no early-dated due item survives. The lane block's time is the
database clock at the status write, and never follows the caller's clock.
"""

import datetime as dt
import json
import re

import psycopg
import pytest

from backend.modules.export.errors import ExportError
from backend.modules.export.repository import Claimed, WriteOutcome
from tests.u6_approved_export import export_rows as rows
from tests.u6_approved_export import lane_flows as lf
from tests.u6_approved_export import store_flows as flows

EPOCH = dt.datetime(1990, 1, 1, tzinfo=dt.UTC)
DAY = dt.timedelta(hours=24)
SECOND = dt.timedelta(seconds=1)
INSIDE, EDGE, OUTSIDE = EPOCH + DAY - SECOND, EPOCH + DAY, EPOCH + DAY + SECOND
EFFECT_KEYS = (
    "accepted",
    "executing",
    "unknown",
    "succeededLast24h",
    "failedLast24h",
    "cancelledLast24h",
    "invalidatedLast24h",
)


def moved(after: dict, before: dict, leaving: str, entering: str) -> None:
    assert after[leaving] == before[leaving] - 1
    assert after[entering] == before[entering] + 1


def changes(after: dict, before: dict) -> dict:
    """The effect keys that moved, with their deltas; both blocks hold exactly the seven."""
    assert set(after) == set(before) == set(EFFECT_KEYS)
    return {key: after[key] - before[key] for key in EFFECT_KEYS if after[key] != before[key]}


def database_now(connect) -> dt.datetime:
    """The realm's own clock, the one the lane status record stamps."""
    with connect("export") as conn:
        return conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]


def effect_states(connect) -> dict:
    with connect("export") as conn:
        return {
            row["state"]: row["n"]
            for row in conn.execute("SELECT state,count(*) AS n FROM export.effect GROUP BY state")
        }


def test_last_24h_counts_move_their_states_by_one_at_the_window_edges(
    transactions, connect, authority
):
    repo = flows.repository(transactions)
    try:
        connection = flows.connected(repo, connect, authority, EPOCH)
        baseline = repo.status_counts(EPOCH)["effects"]
        flows.succeed(repo, flows.bound(repo, authority, connection, EPOCH)["effect"], EPOCH)
        cancelled = flows.bound(repo, authority, connection, EPOCH)["effect"]
        repo.cancel(authority, cancelled["approval_id"], cancelled["revision"], now=EPOCH)
        inside = repo.status_counts(EPOCH + DAY - dt.timedelta(seconds=1))["effects"]
        assert inside["succeededLast24h"] == baseline["succeededLast24h"] + 1
        assert inside["cancelledLast24h"] == baseline["cancelledLast24h"] + 1
        outside = repo.status_counts(EPOCH + DAY + dt.timedelta(seconds=1))["effects"]
        assert outside["succeededLast24h"] == baseline["succeededLast24h"]
        assert outside["cancelledLast24h"] == baseline["cancelledLast24h"]
    finally:
        flows.fresh(connect, authority.account_id)


def test_executing_and_unknown_move_by_exactly_one_through_a_claim_and_an_uncertain_answer(
    transactions, connect, authority
):
    repo = flows.repository(transactions)
    try:
        connection = flows.connected(repo, connect, authority, EPOCH)
        base = repo.status_counts(EPOCH)["effects"]
        effect = flows.bound(repo, authority, connection, EPOCH)["effect"]
        assert changes(repo.status_counts(EPOCH)["effects"], base) == {"accepted": 1}
        claimed = repo.claim(effect["id"], effect["revision"], now=EPOCH)
        assert isinstance(claimed, Claimed)
        assert changes(repo.status_counts(EPOCH)["effects"], base) == {"executing": 1}
        repo.record_write_outcome(
            effect["id"],
            claimed.attempt["id"],
            claimed.effect["revision"],
            WriteOutcome("uncertain"),
            now=EPOCH,
        )
        assert flows.effect_row(connect, effect["id"])["state"] == "unknown"
        assert changes(repo.status_counts(EPOCH)["effects"], base) == {"unknown": 1}
    finally:
        flows.fresh(connect, authority.account_id)


def test_failed_and_invalidated_effects_count_once_inside_24h_and_not_from_the_edge_on(
    transactions, connect, authority
):
    repo = flows.repository(transactions)
    try:
        connection = flows.connected(repo, connect, authority, EPOCH)
        before = {when: repo.status_counts(when)["effects"] for when in (INSIDE, EDGE, OUTSIDE)}
        failing = flows.bound(repo, authority, connection, EPOCH)["effect"]
        repo.end_unwritten(failing["id"], failing["revision"], "dependency-unavailable", now=EPOCH)
        # An owner has one effect in flight, so the second bind follows the first end.
        ending = flows.bound(repo, authority, connection, EPOCH)["effect"]
        repo.end_unwritten(ending["id"], ending["revision"], "authority-revoked", now=EPOCH)
        preview = flows.prepare(repo, authority, connection, EPOCH)
        approval = flows.approve(repo, authority, preview, EPOCH)
        assert repo.invalidate_open_approval(approval["id"], "source-changed", now=EPOCH) is True

        failed = flows.effect_row(connect, failing["id"])
        ended = flows.effect_row(connect, ending["id"])
        assert (failed["state"], failed["outcome_reason"], failed["ended_at"]) == (
            "failed",
            "dependency-unavailable",
            EPOCH,
        )
        assert (ended["state"], ended["outcome_reason"], ended["ended_at"]) == (
            "invalidated",
            "authority-revoked",
            EPOCH,
        )
        invalidated = flows.approval_row(connect, approval["id"])
        assert (invalidated["state"], invalidated["invalidation_reason"]) == (
            "invalidated",
            "source-changed",
        )
        assert changes(repo.status_counts(INSIDE)["effects"], before[INSIDE]) == {
            "failedLast24h": 1,
            "invalidatedLast24h": 1,
        }
        assert changes(repo.status_counts(EDGE)["effects"], before[EDGE]) == {}
        assert changes(repo.status_counts(OUTSIDE)["effects"], before[OUTSIDE]) == {}
    finally:
        flows.fresh(connect, authority.account_id)


def test_ages_count_from_the_expected_instants(transactions, connect, authority, authority_b):
    repo = flows.repository(transactions)
    try:
        connection = flows.connected(repo, connect, authority, EPOCH)
        other = flows.connected(repo, connect, authority_b, EPOCH)
        flows.bound(repo, authority, connection, EPOCH)
        elsewhere = flows.bound(repo, authority_b, other, EPOCH)["effect"]
        flows.uncertain(repo, elsewhere, EPOCH)
        status = repo.status_counts(EPOCH + dt.timedelta(seconds=1000))
        assert status["oldestAcceptedSeconds"] == 1000
        assert status["oldestUnknownSeconds"] == 910
    finally:
        flows.fresh(connect, authority.account_id)
        flows.fresh(connect, authority_b.account_id)


def test_ages_are_none_without_that_state_and_a_null_clock_is_refused(
    transactions, connect, authority, authority_b
):
    repo = flows.repository(transactions)
    try:
        flows.fresh(connect, authority.account_id)
        flows.fresh(connect, authority_b.account_id)
        status = repo.status_counts(EPOCH)
        states = effect_states(connect)
        assert (status["oldestAcceptedSeconds"] is None) == (states.get("accepted", 0) == 0)
        assert (status["oldestUnknownSeconds"] is None) == (states.get("unknown", 0) == 0)
        with connect("export") as conn:
            with pytest.raises(psycopg.errors.InvalidParameterValue, match="caller clock"):
                conn.execute("SELECT export.status_counts(NULL)")
    finally:
        flows.fresh(connect, authority.account_id)
        flows.fresh(connect, authority_b.account_id)


def test_connection_counts_follow_each_state_and_pending_stays_unwatched(
    transactions, connect, authority
):
    repo = flows.repository(transactions)
    try:
        flows.connected(repo, connect, authority, EPOCH)
        base = repo.status_counts(EPOCH)["connections"]
        repo.disconnect(authority, now=EPOCH)
        after_disconnect = repo.status_counts(EPOCH)["connections"]
        moved(after_disconnect, base, "connected", "disconnected")
        row = repo.read_connection(authority)
        assert row["state"] == "disconnected"
        flows.configure(repo, authority, EPOCH, expected=row["revision"])
        before_revoke = repo.status_counts(EPOCH)["connections"]
        opened = repo.read_connection(authority)
        assert repo.revoke_connection(
            authority.account_id, opened["id"], opened["revision"], now=EPOCH
        )
        after_revoke = repo.status_counts(EPOCH)["connections"]
        moved(after_revoke, before_revoke, "connected", "revoked")
        flows.configure(
            repo, authority, EPOCH, expected=repo.read_connection(authority)["revision"]
        )
        before_unavailable = repo.status_counts(EPOCH)["connections"]
        reopened = repo.read_connection(authority)
        assert repo.set_availability(
            authority.account_id, reopened["id"], reopened["revision"], available=False
        )
        after_unavailable = repo.status_counts(EPOCH)["connections"]
        moved(after_unavailable, before_unavailable, "connected", "unavailable")
        with connect("export") as conn:
            rows.reserve(conn)  # a pending reservation exists, unwatched (L1-4)
        status = repo.status_counts(EPOCH)
        with connect("export") as conn:
            total = conn.execute("SELECT count(*) AS n FROM export.connection").fetchone()["n"]
            pending = conn.execute(
                "SELECT count(*) AS n FROM export.connection WHERE state='pending'"
            ).fetchone()["n"]
        assert sum(status["connections"].values()) == total - pending
    finally:
        flows.fresh(connect, authority.account_id)


def test_the_lane_block_is_a_category_and_the_whole_json_holds_no_identifiers(
    transactions, connect, authority
):
    repo = flows.repository(transactions)
    try:
        connection = flows.connected(repo, connect, authority, EPOCH)
        with pytest.raises(ExportError) as caught:
            repo.record_lane_status("")
        assert caught.value.code == "INVALID_ARGUMENT"
        with pytest.raises(ExportError) as caught:
            repo.record_lane_status("x" * 65)
        assert caught.value.code == "INVALID_ARGUMENT"
        repo.record_lane_status("waiting")
        status = repo.status_counts(EPOCH)
        assert set(status["lane"]) == {"outcome", "observedAt"}
        assert status["lane"]["outcome"] == "waiting"
        dump = json.dumps(status, default=str)
        assert "Synthetic" not in dump
        assert re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}", dump) is None
        assert str(authority.account_id) not in dump
        assert str(connection["id"]) not in dump
    finally:
        flows.fresh(connect, authority.account_id)


def test_the_lane_block_reports_when_the_lane_recorded_its_last_outcome(transactions, connect):
    repo = flows.repository(transactions)
    repo.record_lane_status("stopped")  # the singleton row exists, so the next record updates
    first = lf.latest_lane_status(connect)
    before = database_now(connect)
    repo.record_lane_status("skipped")
    after = database_now(connect)
    recorded = lf.latest_lane_status(connect)

    assert recorded["outcome"] == "skipped"
    assert first["observed_at"] < recorded["observed_at"]
    assert before <= recorded["observed_at"] <= after
    for clock in (EPOCH, after + dt.timedelta(seconds=90)):
        lane = repo.status_counts(clock)["lane"]
        assert lane["outcome"] == "skipped"
        assert dt.datetime.fromisoformat(lane["observedAt"]) == recorded["observed_at"]
