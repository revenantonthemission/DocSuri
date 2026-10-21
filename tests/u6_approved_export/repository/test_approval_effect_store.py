"""Approve, bind, cancel and settle (BR3.1–BR3.7, BR4.5, BR5.1, BR5.2) and the reads."""

from uuid import uuid4

import psycopg
import pytest
from backend.modules.export.errors import ExportError
from backend.modules.export.repository import CheckResult, Replay, replay_input_hash

from tests.u6_approved_export import export_rows as rows
from tests.u6_approved_export import store_flows as flows


def refused(call) -> ExportError:
    with pytest.raises(ExportError) as caught:
        call()
    return caught.value


def pair() -> dict:
    return {"artifact": uuid4(), "destination": rows.destination_id()}


def test_approval_replays_by_key_and_by_preview_revision(transactions, connect, authority):
    repo, now = flows.repository(transactions), flows.at()
    connection = flows.connected(repo, connect, authority, now)
    first = flows.prepare(repo, authority, connection, now, **(p := pair()))
    key = uuid4()
    args = (first["preview_id"], first["revision"], first["binding_hash"])
    approval = repo.record_approval(authority, key, *args, flows.APPROVAL_POLICY, now=now)
    assert approval["replayed"] is False and approval["approval"]["state"] == "approved"
    again = repo.record_approval(authority, key, *args, flows.APPROVAL_POLICY, now=now)
    other_tab = repo.record_approval(authority, uuid4(), *args, flows.APPROVAL_POLICY, now=now)
    assert again["replayed"] and other_tab["replayed"]
    assert again["approval"]["id"] == other_tab["approval"]["id"] == approval["approval"]["id"]
    assert repo.approval_replay(authority, key, *args)["approval"]["id"] == again["approval"]["id"]

    second = flows.prepare(repo, authority, connection, now, **p)
    changed = (second["preview_id"], second["revision"], second["binding_hash"])
    assert (
        refused(
            lambda: repo.record_approval(authority, key, *changed, flows.APPROVAL_POLICY, now=now)
        ).code
        == "IDEMPOTENCY_CONFLICT"
    )
    assert repo.approval_replay(authority, uuid4(), *changed) is None


def test_an_approval_needs_the_current_revision_and_no_newer_export(
    transactions, connect, authority
):
    """BR3.1 and decision "Newer succeeded export": refusals record nothing."""
    repo, start = flows.repository(transactions), flows.at()
    connection = flows.connected(repo, connect, authority, start)
    p = pair()
    stale = flows.prepare(repo, authority, connection, start, **p)
    older = flows.bound(repo, authority, connection, flows.at(1, base=start), **p)
    current = flows.prepare(repo, authority, connection, flows.at(2, base=start), **p)
    flows.succeed(repo, older["effect"], flows.at(3, base=start))  # after `current` was prepared

    def attempt(preview, binding=None):
        return refused(
            lambda: repo.record_approval(
                authority,
                uuid4(),
                preview["preview_id"],
                preview["revision"],
                binding or preview["binding_hash"],
                flows.APPROVAL_POLICY,
                now=flows.at(4, base=start),
            )
        )

    assert attempt(stale).code == "CONFLICT"
    assert attempt(current, "0" * 64).code == "CONFLICT"
    assert attempt(current).current == {"field": "newerExport"}
    with connect("export") as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM export.approval WHERE preview_id=%s AND preview_revision<>%s",
                (current["preview_id"], older["preview"]["revision"]),
            ).fetchone()["n"]
            == 0
        )
    fresh_preview = flows.prepare(repo, authority, connection, flows.at(5, base=start), **p)
    assert flows.approve(repo, authority, fresh_preview, flows.at(5, base=start))["state"] == (
        "approved"
    )


def test_binding_consumes_the_approval_atomically_and_replays(transactions, connect, authority):
    repo, now = flows.repository(transactions), flows.at()
    connection = flows.connected(repo, connect, authority, now)
    preview = flows.prepare(repo, authority, connection, now)
    approval = flows.approve(repo, authority, preview, now)
    key = uuid4()
    result = repo.bind_effect(authority, approval["id"], key, now=now)
    effect = result["effect"]
    assert result["replayed"] is False and result["approval"]["state"] == "consumed"
    assert (effect["state"], effect["revision"], effect["accepted_at"]) == ("accepted", 1, now)
    assert (effect["marker"], effect["binding_hash"]) == (
        preview["marker"],
        preview["binding_hash"],
    )
    assert repo.bind_effect(authority, approval["id"], key, now=now)["effect"]["id"] == effect["id"]
    by_approval = repo.execute_replay(authority, uuid4(), approval["id"])
    assert by_approval["replayed"] and by_approval["effect"]["id"] == effect["id"]
    other = flows.approve(repo, authority, flows.prepare(repo, authority, connection, now), now)
    assert refused(lambda: repo.bind_effect(authority, other["id"], key, now=now)).code == (
        "CONFLICT"
    )
    assert repo.execute_replay(authority, uuid4(), other["id"]) is None
    read = repo.read_approval(authority, approval["id"])
    assert read["effect"]["id"] == effect["id"] and read["revision"]["marker"] == preview["marker"]
    flows.end_session(connect, authority)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):  # the guard runs first
        repo.read_approval(authority, approval["id"])


def test_in_flight_and_unknown_pair_refusals_leave_the_approval_approved(
    transactions, connect, authority
):
    """BR5.1: CAPACITY_EXHAUSTED while one is in flight, OUTCOME_UNKNOWN for the pair."""
    repo, now = flows.repository(transactions), flows.at()
    connection = flows.connected(repo, connect, authority, now)
    p = pair()
    in_flight = flows.bound(repo, authority, connection, now, **p)
    waiting = flows.approve(repo, authority, flows.prepare(repo, authority, connection, now), now)
    assert refused(lambda: repo.bind_effect(authority, waiting["id"], uuid4(), now=now)).code == (
        "CAPACITY_EXHAUSTED"
    )
    assert flows.approval_row(connect, waiting["id"])["state"] == "approved"

    flows.uncertain(repo, in_flight["effect"], now)
    same_pair = flows.approve(
        repo, authority, flows.prepare(repo, authority, connection, now, **p), now
    )
    assert (
        refused(lambda: repo.bind_effect(authority, same_pair["id"], uuid4(), now=now)).code
        == "OUTCOME_UNKNOWN"
    )
    assert flows.approval_row(connect, same_pair["id"])["state"] == "approved"
    assert repo.bind_effect(authority, waiting["id"], uuid4(), now=now)["effect"]["state"] == (
        "accepted"
    )


def test_the_rolling_hour_refusal_carries_the_seconds_until_a_slot_frees(
    transactions, connect, authority
):
    """BR5.2 with a reduced limit of two binds per rolling hour."""
    repo, start = flows.repository(transactions, binds_per_window=2), flows.at()
    connection = flows.connected(repo, connect, authority, start)
    for offset in (0, 10):
        effect = flows.bound(repo, authority, connection, flows.at(offset, base=start))
        repo.cancel(authority, effect["approval"]["id"], 1, now=flows.at(offset, base=start))
    third = flows.approve(repo, authority, flows.prepare(repo, authority, connection, start), start)
    error = refused(
        lambda: repo.bind_effect(authority, third["id"], uuid4(), now=flows.at(20, base=start))
    )
    assert (error.code, error.retry_after) == ("CAPACITY_EXHAUSTED", 3580)
    assert flows.approval_row(connect, third["id"])["state"] == "approved"
    later = flows.at(3601, base=start)
    assert repo.bind_effect(authority, third["id"], uuid4(), now=later)["effect"]["state"] == (
        "accepted"
    )


def test_continuing_an_older_approval_after_a_newer_export_succeeded_is_refused(
    transactions, connect, authority
):
    repo, start = flows.repository(transactions), flows.at()
    connection = flows.connected(repo, connect, authority, start)
    p = pair()
    older = flows.approve(
        repo, authority, flows.prepare(repo, authority, connection, start, **p), start
    )
    newer = flows.bound(repo, authority, connection, flows.at(1, base=start), **p)
    flows.succeed(repo, newer["effect"], flows.at(2, base=start))
    error = refused(
        lambda: repo.bind_effect(authority, older["id"], uuid4(), now=flows.at(3, base=start))
    )
    assert (error.code, error.current) == ("CONFLICT", {"field": "newerExport"})
    assert flows.approval_row(connect, older["id"])["state"] == "approved"


def test_cancel_compares_the_preview_revision_or_the_effect_revision(
    transactions, connect, authority
):
    """BR3.6, A10: both compare-and-sets, and the executing and unknown refusals."""
    repo, now = flows.repository(transactions), flows.at()
    connection = flows.connected(repo, connect, authority, now)
    approval = flows.approve(repo, authority, flows.prepare(repo, authority, connection, now), now)
    assert refused(lambda: repo.cancel(authority, approval["id"], 2, now=now)).code == "CONFLICT"
    assert repo.cancel(authority, approval["id"], 1, now=now)["approval"]["state"] == "cancelled"
    assert repo.cancel(authority, approval["id"], 1, now=now)["approval"]["state"] == "cancelled"

    p = pair()
    flows.prepare(repo, authority, connection, now, **p)
    accepted = flows.bound(repo, authority, connection, now, **p)  # preview revision 2
    approval_id = accepted["approval"]["id"]
    assert refused(lambda: repo.cancel(authority, approval_id, 2, now=now)).code == "CONFLICT"
    cancelled = repo.cancel(authority, approval_id, 1, now=now)
    assert cancelled["approval"]["state"] == "consumed"
    assert (cancelled["effect"]["state"], cancelled["effect"]["outcome_reason"]) == (
        "cancelled",
        "owner-cancelled",
    )
    assert cancelled["effect"]["ended_at"] == now

    executing = flows.bound(repo, authority, connection, now)
    repo.claim(executing["effect"]["id"], 1, now=now)
    error = refused(lambda: repo.cancel(authority, executing["approval"]["id"], 2, now=now))
    assert (error.code, error.current) == ("CONFLICT", {"state": "executing"})
    with pytest.raises(LookupError):
        repo.cancel(authority, uuid4(), 1, now=now)


def test_unknown_exports_refuse_cancel_and_settle_only_once_offered(
    transactions, connect, authority
):
    """BR4.5: settlement by compare-and-set, once offered, with its replay record."""
    repo, start = flows.repository(transactions), flows.at()
    connection = flows.connected(repo, connect, authority, start)
    exported = flows.bound(repo, authority, connection, start)
    unknown = flows.uncertain(repo, exported["effect"], start)
    effect_id = unknown["id"]
    assert (
        refused(
            lambda: repo.cancel(
                authority, exported["approval"]["id"], unknown["revision"], now=start
            )
        ).code
        == "OUTCOME_UNKNOWN"
    )

    def settle(revision, key=None, *, now, url=None, disposition="delivered"):
        request = {"effectId": str(effect_id), "expectedRevision": revision, "url": url}
        replay = Replay(key or uuid4(), replay_input_hash(request))
        return repo.settle(
            authority,
            effect_id,
            revision,
            disposition,
            replay,
            assumption="Checked in Notion",
            remote_url=url,
            now=now,
        )

    early = flows.at(100, base=start)
    assert repo.read_effect(authority, effect_id, now=early)["settlementOffered"] is False
    assert refused(lambda: settle(unknown["revision"], now=early)).code == "CONFLICT"
    checked = repo.record_check(
        effect_id,
        unknown["revision"],
        CheckResult("listing-unavailable", start, "c" * 64),
        now=flows.at(300, base=start),
    )
    later = flows.at(400, base=start)
    view = repo.read_effect(authority, effect_id, now=later)
    assert view["settlementOffered"] is True and view["latestCheck"]["result"] == (
        "listing-unavailable"
    )
    assert refused(lambda: settle(checked["revision"] - 1, now=later)).code == "CONFLICT"
    key, url = uuid4(), f"https://www.notion.so/{uuid4().hex}"
    settled = settle(checked["revision"], key, now=later, url=url)
    effect = settled["effect"]
    assert (effect["state"], effect["outcome_reason"], effect["settled_by"]) == (
        "succeeded",
        "owner-settled-delivered",
        "owner",
    )
    assert effect["remote_url"] == url and effect["ended_at"] == later
    assert (
        repo.read_connection(authority)["last_destination_id"]
        == exported["effect"]["destination_id"]
    )
    replayed = settle(checked["revision"], key, now=later, url=url)
    assert replayed["replayed"] and replayed["response"] == settled["response"]
    assert refused(lambda: settle(checked["revision"] + 1, key, now=later)).code == (
        "IDEMPOTENCY_CONFLICT"
    )
    assert refused(lambda: settle(effect["revision"], now=later)).code == "CONFLICT"


def test_history_pages_newest_first_with_continuable_and_effect_facts(
    transactions, connect, authority, authority_b
):
    repo, start = flows.repository(transactions), flows.at()
    connection = flows.connected(repo, connect, authority, start)
    older = flows.bound(repo, authority, connection, start)
    flows.uncertain(repo, older["effect"], start)
    newer = flows.approve(
        repo, authority, flows.prepare(repo, authority, connection, start), flows.at(5, base=start)
    )
    first = repo.history(authority, limit=1, now=flows.at(10, base=start))
    [entry] = first["entries"]
    assert entry["approval"]["id"] == newer["id"] and entry["continuable"] is True
    assert entry["effect"] is None and entry["sourceTitle"] == "Synthetic result"
    second = repo.history(
        authority, limit=1, cursor=first["nextCursor"], now=flows.at(10, base=start)
    )
    [older_entry] = second["entries"]
    assert older_entry["approval"]["id"] == older["approval"]["id"]
    assert older_entry["effect"]["effect"]["state"] == "unknown"
    assert older_entry["effect"]["settlementOffered"] is False
    assert older_entry["continuable"] is False and second["nextCursor"] is None
    flows.fresh(connect, authority_b.account_id)
    assert repo.history(authority_b, now=start) == {"entries": [], "nextCursor": None}
    for bad in ("", "not-a-cursor", "e30"):
        assert refused(lambda bad=bad: repo.history(authority, cursor=bad, now=start)).current == {
            "field": "cursor"
        }
    assert refused(lambda: repo.history(authority, limit=21, now=start)).code == "INVALID_ARGUMENT"
