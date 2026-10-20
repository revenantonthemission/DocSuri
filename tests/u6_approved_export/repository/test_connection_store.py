"""The owner's single connection: reservation, takeover, compare-and-sets and revocation."""

from uuid import uuid4

import pytest
from backend.modules.export.errors import ExportError

from tests.u6_approved_export import store_flows as flows


def refusal(call) -> str:
    with pytest.raises(ExportError) as caught:
        call()
    return caught.value.code


def test_first_configure_reserves_a_pending_row_with_its_pace_row(transactions, connect, authority):
    """R-13: the reservation and its pace row exist before any token check starts."""
    repo, now = flows.repository(transactions), flows.at()
    flows.fresh(connect, authority.account_id)
    slot = repo.reserve_connection(authority, None, now=now)
    row = flows.connection_row(connect, slot.connection_id)
    assert slot.pending and (slot.expected_revision, slot.next_revision) == (0, 1)
    assert (row["state"], row["revision"], row["pending_holder"]) == ("pending", 0, slot.holder)
    assert row["pending_started_at"] == now and row["account_id"] == authority.account_id
    assert flows.pace_count(connect, slot.connection_id) == 1
    with pytest.raises(LookupError):
        repo.read_connection(authority)  # a reservation reads as not connected


def test_a_fresh_pending_row_refuses_a_second_configure(transactions, connect, authority):
    """R-03: a second configure racing a held check answers CONFLICT."""
    repo, now = flows.repository(transactions), flows.at()
    flows.fresh(connect, authority.account_id)
    slot = repo.reserve_connection(authority, None, now=now)
    assert refusal(lambda: repo.reserve_connection(authority, None, now=flows.at(30))) == "CONFLICT"
    assert refusal(lambda: repo.reserve_connection(authority, 0, now=flows.at(30))) == "CONFLICT"
    assert refusal(lambda: repo.reserve_connection(authority, 3, now=flows.at(500))) == "CONFLICT"
    assert flows.connection_row(connect, slot.connection_id)["pending_holder"] == slot.holder


def test_takeover_needs_the_takeover_time_on_the_passed_clock(transactions, connect, authority):
    repo, now = flows.repository(transactions, pending_takeover_seconds=120), flows.at()
    flows.fresh(connect, authority.account_id)
    first = repo.reserve_connection(authority, None, now=now)
    early = flows.at(119, base=now)
    assert refusal(lambda: repo.reserve_connection(authority, None, now=early)) == "CONFLICT"
    taken = repo.reserve_connection(authority, None, now=flows.at(121, base=now))
    row = flows.connection_row(connect, first.connection_id)
    assert taken.connection_id == first.connection_id and taken.holder != first.holder
    assert row["pending_holder"] == taken.holder
    assert row["pending_started_at"] == flows.at(121, base=now)
    assert flows.pace_count(connect, first.connection_id) == 1


def test_a_check_whose_row_moved_on_stores_nothing_and_deletes_nothing(
    transactions, connect, authority
):
    """R-02: a taken-over or removed reservation leaves the new holder's rows intact."""
    repo, now = flows.repository(transactions, pending_takeover_seconds=120), flows.at()
    flows.fresh(connect, authority.account_id)
    stale = repo.reserve_connection(authority, None, now=now)
    holder = repo.reserve_connection(authority, None, now=flows.at(200, base=now))
    request = flows.configure_request(None)
    stored = lambda slot: repo.store_configured(  # noqa: E731
        authority, slot, flows.sealed(), flows.replay_for(request), now=now
    )
    assert refusal(lambda: stored(stale)) == "CONFLICT"
    assert repo.release_pending(authority, stale.holder) is False
    row = flows.connection_row(connect, stale.connection_id)
    assert (row["state"], row["pending_holder"]) == ("pending", holder.holder)
    assert flows.pace_count(connect, stale.connection_id) == 1
    with connect("export") as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM export.replay_record WHERE account_id=%s",
                (authority.account_id,),
            ).fetchone()["n"]
            == 0
        )

    assert repo.release_pending(authority, holder.holder) is True
    assert flows.connection_row(connect, holder.connection_id) is None
    assert flows.pace_count(connect, holder.connection_id) == 0
    assert refusal(lambda: stored(holder)) == "CONFLICT"
    assert repo.reserve_connection(authority, None, now=now).pending


def test_replace_is_a_compare_and_set_on_the_expected_revision(transactions, connect, authority):
    """BR1.3: only the expected revision is replaced; a stale slot stores nothing."""
    repo, now = flows.repository(transactions), flows.at()
    connection = flows.connected(repo, connect, authority, now)
    assert connection["revision"] == 1 and connection["state"] == "connected"
    assert refusal(lambda: repo.reserve_connection(authority, 2, now=now)) == "CONFLICT"
    assert refusal(lambda: repo.reserve_connection(authority, None, now=now)) == "CONFLICT"
    slot = repo.reserve_connection(authority, 1, now=now)
    assert not slot.pending and slot.next_revision == 2
    request = flows.configure_request(1)
    result = repo.store_configured(
        authority, slot, flows.sealed(), flows.replay_for(request), now=now
    )
    assert result["response"]["revision"] == 2
    again = flows.replay_for(request)
    assert (
        refusal(lambda: repo.store_configured(authority, slot, flows.sealed(), again, now=now))
        == "CONFLICT"
    )
    current = repo.read_connection(authority)
    assert (current["revision"], current["creation_capability"]) == (2, "unknown")


def test_unavailability_keeps_the_revision_and_configure_from_it_is_refused(
    transactions, connect, authority
):
    """BR1.6 and decision "Configure from unavailable"."""
    repo, now = flows.repository(transactions), flows.at()
    connection = flows.connected(repo, connect, authority, now)
    account, ident = authority.account_id, connection["id"]
    assert repo.set_availability(account, ident, 1, available=False) is True
    assert repo.set_availability(account, ident, 1, available=False) is False
    assert refusal(lambda: repo.reserve_connection(authority, 1, now=now)) == "CONFLICT"
    unavailable = repo.read_connection(authority)
    assert (unavailable["state"], unavailable["revision"]) == ("unavailable", 1)
    assert repo.open_token_envelope(account, ident)["state"] == "unavailable"
    assert repo.set_availability(account, ident, 2, available=True) is False
    assert repo.set_availability(account, ident, 1, available=True) is True
    assert repo.read_connection(authority)["state"] == "connected"
    assert repo.read_connection(authority)["revision"] == 1


def test_a_revocation_from_an_older_revision_is_discarded(transactions, connect, authority):
    """D16: after a replace, a 401 for the token opened at revision 1 changes nothing."""
    repo, now = flows.repository(transactions), flows.at()
    connection = flows.connected(repo, connect, authority, now)
    flows.configure(repo, authority, now, expected=1)
    replaced = repo.read_connection(authority)
    preview = flows.prepare(repo, authority, replaced, now)
    approval = flows.approve(repo, authority, preview, now)
    assert repo.revoke_connection(authority.account_id, connection["id"], 1, now=now) is None
    current = repo.read_connection(authority)
    assert (current["state"], current["revision"]) == ("connected", 2)
    assert flows.approval_row(connect, approval["id"])["state"] == "approved"
    assert repo.open_token_envelope(authority.account_id, connection["id"]) is not None


def test_a_revocation_ends_older_pending_work_but_not_unknown_exports(
    transactions, connect, authority
):
    """D16, BR1.4: one transaction clears the envelope, revokes and invalidates."""
    repo, now = flows.repository(transactions), flows.at()
    connection = flows.connected(repo, connect, authority, now)
    unknown = flows.uncertain(repo, flows.bound(repo, authority, connection, now)["effect"], now)
    accepted = flows.bound(repo, authority, connection, now)
    preview = flows.prepare(repo, authority, connection, now)
    approval = flows.approve(repo, authority, preview, now)

    result = repo.revoke_connection(authority.account_id, connection["id"], 1, now=now)
    assert result["revision"] == 2
    assert set(result["approvalsInvalidated"]) == {approval["id"]}
    assert set(result["effectsInvalidated"]) == {accepted["effect"]["id"]}
    revoked = repo.read_connection(authority)
    assert (revoked["state"], revoked["revision"]) == ("revoked", 2)
    assert repo.open_token_envelope(authority.account_id, connection["id"]) is None
    assert flows.approval_row(connect, approval["id"])["invalidation_reason"] == (
        "connection-changed"
    )
    ended = flows.effect_row(connect, accepted["effect"]["id"])
    assert (ended["state"], ended["outcome_reason"], ended["ended_at"]) == (
        "invalidated",
        "connection-changed",
        now,
    )
    assert flows.effect_row(connect, unknown["id"])["state"] == "unknown"


def test_an_executing_export_finishes_after_a_revocation(transactions, connect, authority):
    repo, now = flows.repository(transactions), flows.at()
    connection = flows.connected(repo, connect, authority, now)
    effect = flows.bound(repo, authority, connection, now)["effect"]
    claimed = repo.claim(effect["id"], effect["revision"], now=now)
    preview = flows.prepare(repo, authority, connection, now)
    approval = flows.approve(repo, authority, preview, now)
    result = repo.revoke_connection(authority.account_id, connection["id"], 1, now=now)
    assert result["effectsInvalidated"] == [] and result["approvalsInvalidated"] == [approval["id"]]
    assert flows.effect_row(connect, effect["id"])["state"] == "executing"
    assert claimed.attempt["connection_revision"] == 1


def test_disconnect_runs_the_same_invalidation_and_repeats_idempotently(
    transactions, connect, authority
):
    repo, now = flows.repository(transactions), flows.at()
    connection = flows.connected(repo, connect, authority, now)
    accepted = flows.bound(repo, authority, connection, now)
    approval = flows.approve(repo, authority, flows.prepare(repo, authority, connection, now), now)
    result = repo.disconnect(authority, now=now)
    assert (result["connection"]["state"], result["connection"]["revision"]) == ("disconnected", 2)
    assert result["approvalsInvalidated"] == [approval["id"]]
    assert result["effectsInvalidated"] == [accepted["effect"]["id"]]
    assert repo.open_token_envelope(authority.account_id, connection["id"]) is None
    repeat = repo.disconnect(authority, connection["id"], now=now)
    assert repeat["connection"]["revision"] == 2 and repeat["effectsInvalidated"] == []
    reconnected = flows.configure(repo, authority, now, expected=2)
    assert reconnected["response"]["revision"] == 3


def test_foreign_connections_read_exactly_like_absent_ones(
    transactions, connect, authority, authority_b
):
    """BR7.1: another owner's connection and a missing one raise the same LookupError."""
    repo, now = flows.repository(transactions), flows.at()
    connection = flows.connected(repo, connect, authority, now)
    flows.fresh(connect, authority_b.account_id)
    messages = set()
    for call in (
        lambda: repo.read_connection(authority_b),
        lambda: repo.read_connection(authority_b, connection["id"]),
        lambda: repo.read_connection(authority, uuid4()),
        lambda: repo.disconnect(authority_b, connection["id"], now=now),
    ):
        with pytest.raises(LookupError) as caught:
            call()
        messages.add(str(caught.value))
    assert len(messages) == 1
    assert repo.read_connection(authority)["state"] == "connected"
