"""Housekeeping batches: D4 session ends, NFR4.9 source changes, the BR2.6 trim, the
NFR1.5 purge and the R-02 stale-pending sweep."""

from uuid import uuid4

import pytest
from backend.modules.export.errors import ExportError

from tests.u6_approved_export import store_flows as flows

DAY = 86400


def housekeeping(transactions):
    return flows.repository(transactions, housekeeping_batch=1000, pending_takeover_seconds=120)


def trimmed(connect, preview) -> bool:
    row = flows.revision_row(connect, preview["preview_id"], preview["revision"])
    return row["trimmed_at"] is not None and row["rendered_blocks"] is None


def sweep_until(repo, approval_id, now):
    """Walk the keyset until the batch that holds this approval has been checked."""
    after, invalidated = None, []
    for _ in range(50):
        result = repo.invalidate_ended_sessions(now, after=after)
        invalidated += result["invalidated"]
        after = result["resumeAfter"]
        if approval_id in invalidated or after is None:
            return invalidated
    raise AssertionError("keyset walk did not finish")


def test_an_ended_session_invalidates_and_trims_its_approval_in_one_step(
    transactions, connect, authority
):
    """D4: authority-revoked with the trim in the same transaction; current sessions stay."""
    repo, now = housekeeping(transactions), flows.at()
    connection = flows.connected(repo, connect, authority, now)
    ending = flows.second_session(connect, authority)
    ended_preview = flows.prepare(repo, authority, connection, now)
    ended = flows.approve(repo, ending, ended_preview, now)
    kept_preview = flows.prepare(repo, authority, connection, now)
    kept = flows.approve(repo, authority, kept_preview, now)
    flows.end_session(connect, ending)

    assert ended["id"] in sweep_until(repo, ended["id"], now)
    row = flows.approval_row(connect, ended["id"])
    assert (row["state"], row["invalidation_reason"]) == ("invalidated", "authority-revoked")
    assert trimmed(connect, ended_preview)
    assert flows.revision_row(connect, ended_preview["preview_id"], 1)["trimmed_at"] == now
    assert flows.approval_row(connect, kept["id"])["state"] == "approved"
    assert not trimmed(connect, kept_preview)
    with pytest.raises(ExportError):
        repo.invalidate_ended_sessions(now, after=("not", "a-position"))


def test_a_source_change_invalidates_and_trims_in_its_own_transaction(
    transactions, connect, authority
):
    """NFR4.9: only approvals with a current session are offered for the source check."""
    repo, now = housekeeping(transactions), flows.at()
    connection = flows.connected(repo, connect, authority, now)
    ending = flows.second_session(connect, authority)
    stale = flows.approve(repo, ending, flows.prepare(repo, authority, connection, now), now)
    preview = flows.prepare(repo, authority, connection, now)
    current = flows.approve(repo, authority, preview, now)
    flows.end_session(connect, ending)

    offered, after = [], None
    for _ in range(50):
        page = repo.approvals_for_source_check(after=after)
        offered += page["approvals"]
        after = page["resumeAfter"]
        if after is None:
            break
    by_id = {row["id"]: row for row in offered}
    assert current["id"] in by_id and stale["id"] not in by_id
    entry = by_id[current["id"]]
    assert entry["artifact_id"] and entry["source_eligibility_revision"] == "1"

    assert repo.invalidate_open_approval(current["id"], "source-changed", now=now) is True
    assert flows.approval_row(connect, current["id"])["invalidation_reason"] == "source-changed"
    assert trimmed(connect, preview)
    assert repo.invalidate_open_approval(current["id"], "source-changed", now=now) is False
    assert repo.invalidate_open_approval(uuid4(), "source-changed", now=now) is False


def test_revisions_that_can_no_longer_be_written_are_trimmed(transactions, connect, authority):
    """Decision "Rendered copies": cancelled, connection-changed and superseded ones."""
    repo, now = housekeeping(transactions), flows.at()
    connection = flows.connected(repo, connect, authority, now)
    cancelled_preview = flows.prepare(repo, authority, connection, now)
    cancelled = flows.approve(repo, authority, cancelled_preview, now)
    repo.cancel(authority, cancelled["id"], 1, now=now)
    superseded = flows.prepare(repo, authority, connection, now)
    flows.prepare(
        repo,
        authority,
        connection,
        now,
        artifact=superseded["artifact_id"],
        destination=superseded["destination_id"],
    )
    changed_preview = flows.prepare(repo, authority, connection, now)
    flows.approve(repo, authority, changed_preview, now)
    flows.configure(repo, authority, now, expected=1)  # connection-changed

    assert repo.trim_settled_revisions(now) >= 3
    for preview in (cancelled_preview, superseded, changed_preview):
        assert trimmed(connect, preview)


def test_revisions_that_may_still_be_written_keep_their_tree(
    transactions, connect, authority, authority_b
):
    repo, now = housekeeping(transactions), flows.at()
    connection = flows.connected(repo, connect, authority, now)
    unknown = flows.bound(repo, authority, connection, now)
    flows.uncertain(repo, unknown["effect"], now)
    executing = flows.bound(repo, authority, connection, now)
    repo.claim(executing["effect"]["id"], 1, now=now)
    approved = flows.prepare(repo, authority, connection, now)
    flows.approve(repo, authority, approved, now)
    flows.prepare(  # supersedes the approved revision, which still keeps its tree
        repo,
        authority,
        connection,
        now,
        artifact=approved["artifact_id"],
        destination=approved["destination_id"],
    )
    current = flows.prepare(repo, authority, connection, now)
    other = flows.connected(repo, connect, authority_b, now)
    accepted = flows.bound(repo, authority_b, other, now)

    repo.trim_settled_revisions(now)
    for preview in (
        unknown["preview"],
        executing["preview"],
        approved,
        current,
        accepted["preview"],
    ):
        assert not trimmed(connect, preview)


def test_unapproved_previews_are_purged_after_the_retention_period(
    transactions, connect, authority
):
    """NFR1.5: seven days for a never-approved revision; an approved one is never purged."""
    repo, now = housekeeping(transactions), flows.at()
    connection = flows.connected(repo, connect, authority, now)
    expired = flows.prepare(repo, authority, connection, flows.at(-8 * DAY, base=now))
    recent = flows.prepare(repo, authority, connection, flows.at(-6 * DAY, base=now))
    kept = flows.prepare(repo, authority, connection, flows.at(-9 * DAY, base=now))
    flows.approve(repo, authority, kept, now)
    assert repo.purge_unapproved_previews(now) >= 1
    assert flows.revision_row(connect, expired["preview_id"], 1) is None
    with pytest.raises(LookupError):
        repo.read_preview(authority, expired["preview_id"])
    assert flows.revision_row(connect, recent["preview_id"], 1) is not None
    assert flows.revision_row(connect, kept["preview_id"], 1) is not None


def test_stale_pending_rows_are_swept_and_fresh_ones_kept(
    transactions, connect, authority, authority_b
):
    """R-02: only reservations past the takeover time, observed holder included."""
    repo, now = housekeeping(transactions), flows.at()
    flows.fresh(connect, authority.account_id)
    flows.fresh(connect, authority_b.account_id)
    first = repo.reserve_connection(authority, None, now=flows.at(-300, base=now))
    taken = repo.reserve_connection(authority, None, now=flows.at(-170, base=now))
    fresh = repo.reserve_connection(authority_b, None, now=flows.at(-60, base=now))
    assert taken.connection_id == first.connection_id
    assert repo.sweep_stale_pending(now) >= 1
    assert flows.connection_row(connect, taken.connection_id) is None
    assert flows.pace_count(connect, taken.connection_id) == 0
    row = flows.connection_row(connect, fresh.connection_id)
    assert row["pending_holder"] == fresh.holder
    assert flows.pace_count(connect, fresh.connection_id) == 1
    assert repo.release_pending(authority, taken.holder) is False
