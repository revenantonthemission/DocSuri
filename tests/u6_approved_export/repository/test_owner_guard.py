"""U6:NFR1.1: every owner-facing store unit rechecks live session authority first.

Exactly nineteen owner units take an owner `Authority` (`read_connection` through
`history`, including `read_approval`): each one refuses an ended session with
AccountAccess's own `authority denied` refusal (42501) before touching a row. The
account, session and consent facts behind that guard are pinned here too. Rows a
case alters are restored in `finally`, and the function-scoped `authority` fixture
re-upserts its account, session and consent for the next test.
"""

import datetime as dt
from uuid import uuid4

import psycopg
import pytest

from backend.modules.export.repository import ConnectionSlot, Replay
from backend.transactions import Authority, guard
from tests.u6_approved_export import export_rows as rows
from tests.u6_approved_export import store_flows as flows

DENIED = "authority denied"
NOW = dt.datetime(2027, 1, 1, tzinfo=dt.UTC)
COUNTED = ("connection", "preview_revision", "approval", "effect", "replay_record")


def owner_units(repo, authority) -> dict:
    """The nineteen owner-facing units, each closing over valid-shaped arguments so the
    session guard is the only thing that can refuse the call."""
    connection = {"id": uuid4(), "revision": 1}
    replay = Replay(uuid4(), rows.hex_digest("replay"))
    slot = ConnectionSlot(uuid4(), 0, uuid4())
    preview_id, approval_id, effect_id = uuid4(), uuid4(), uuid4()
    binding = rows.hex_digest("binding")
    return {
        "read_connection": lambda: repo.read_connection(authority),
        "configure_replay": lambda: repo.configure_replay(authority, replay),
        "record_configure_refusal": lambda: repo.record_configure_refusal(
            authority, replay, "INVALID_TOKEN"
        ),
        "reserve_connection": lambda: repo.reserve_connection(authority, None, now=NOW),
        "store_configured": lambda: repo.store_configured(
            authority, slot, flows.sealed(validated_at=NOW), replay, now=NOW
        ),
        "release_pending": lambda: repo.release_pending(authority, slot.holder),
        "disconnect": lambda: repo.disconnect(authority, now=NOW),
        "add_preview_revision": lambda: repo.add_preview_revision(
            authority, flows.facts(connection), flows.render, now=NOW
        ),
        "read_preview": lambda: repo.read_preview(authority, preview_id),
        "approval_replay": lambda: repo.approval_replay(authority, uuid4(), preview_id, 1, binding),
        "record_approval": lambda: repo.record_approval(
            authority, uuid4(), preview_id, 1, binding, flows.APPROVAL_POLICY, now=NOW
        ),
        "read_approval": lambda: repo.read_approval(authority, approval_id),
        "invalidate_approval": lambda: repo.invalidate_approval(
            authority, approval_id, "source-changed", now=NOW
        ),
        "execute_replay": lambda: repo.execute_replay(authority, uuid4(), approval_id),
        "bind_effect": lambda: repo.bind_effect(authority, approval_id, uuid4(), now=NOW),
        "cancel": lambda: repo.cancel(authority, approval_id, 1, now=NOW),
        "settle": lambda: repo.settle(
            authority,
            effect_id,
            1,
            "delivered",
            replay,
            assumption="synthetic assumption",
            now=NOW,
        ),
        "read_effect": lambda: repo.read_effect(authority, effect_id, now=NOW),
        "history": lambda: repo.history(authority, now=NOW),
    }


def table_counts(connect) -> dict:
    with connect("export") as conn:
        return {
            table: conn.execute(f"SELECT count(*) AS n FROM export.{table}").fetchone()["n"]
            for table in COUNTED
        }


def refuses(repo, authority) -> None:
    with pytest.raises(psycopg.errors.InsufficientPrivilege, match=DENIED):
        repo.transactions.run("export", lambda conn: guard(conn, authority))


def test_every_owner_unit_refuses_an_ended_session_and_leaves_rows_untouched(
    transactions, connect, authority
):
    repo = flows.repository(transactions)
    before = table_counts(connect)
    flows.end_session(connect, authority)
    units = owner_units(repo, authority)
    assert len(units) == 19
    for call in units.values():
        with pytest.raises(psycopg.errors.InsufficientPrivilege, match=DENIED):
            call()
    assert table_counts(connect) == before


def test_an_expired_or_stale_session_is_refused_and_a_restored_one_passes(
    transactions, connect, authority
):
    repo = flows.repository(transactions)
    current = repo.transactions.run("export", lambda conn: guard(conn, authority))
    try:
        flows.expire_session(connect, authority)
        refuses(repo, authority)
        with connect("accounts") as conn:
            conn.execute(
                "UPDATE accounts.session SET expires_at=clock_timestamp()+interval '30 minutes' "
                "WHERE id=%s",
                (authority.session_id,),
            )
            conn.execute(
                "UPDATE accounts.account SET authority_revision=%s WHERE id=%s",
                (uuid4(), authority.account_id),
            )
        refuses(repo, authority)
    finally:
        with connect("accounts") as conn:
            conn.execute(
                "UPDATE accounts.account SET authority_revision=%s WHERE id=%s",
                (current, authority.account_id),
            )
            conn.execute(
                "UPDATE accounts.session SET revoked=false,"
                "expires_at=clock_timestamp()+interval '30 minutes' WHERE id=%s",
                (authority.session_id,),
            )
    assert repo.transactions.run("export", lambda conn: guard(conn, authority)) == current


def test_consent_and_account_flags_are_rechecked_before_every_unit(
    transactions, connect, authority
):
    repo = flows.repository(transactions)
    try:
        flows.set_consent(connect, authority.account_id, "local-research", False)
        flows.set_consent(connect, authority.account_id, "personalization", True)
        refuses(repo, authority)
        flows.set_consent(connect, authority.account_id, "local-research", True)
        flows.set_consent(connect, authority.account_id, "personalization", False)
        assert repo.transactions.run("export", lambda conn: guard(conn, authority))
        with connect("accounts") as conn:
            conn.execute(
                "UPDATE accounts.account SET active=false WHERE id=%s", (authority.account_id,)
            )
        refuses(repo, authority)
        with connect("accounts") as conn:
            conn.execute(
                "UPDATE accounts.account SET active=true,verified=false WHERE id=%s",
                (authority.account_id,),
            )
        refuses(repo, authority)
    finally:
        flows.set_consent(connect, authority.account_id, "local-research", True)
        with connect("accounts") as conn:
            conn.execute(
                "UPDATE accounts.account SET active=true,verified=true WHERE id=%s",
                (authority.account_id,),
            )


def test_a_foreign_or_preauthentication_session_never_authorises(
    transactions, connect, authority, authority_b
):
    repo = flows.repository(transactions)
    other = flows.connected(repo, connect, authority_b, flows.at())
    foreign = Authority(authority.account_id, authority_b.session_id)
    swapped = Authority(authority_b.account_id, authority.session_id)
    for wrong in (foreign, swapped):
        refuses(repo, wrong)
    try:
        with connect("accounts") as conn:
            conn.execute(
                "UPDATE accounts.session SET purpose='preauthentication' WHERE id=%s",
                (authority.session_id,),
            )
        refuses(repo, authority)
    finally:
        with connect("accounts") as conn:
            conn.execute(
                "UPDATE accounts.session SET purpose='full_session' WHERE id=%s",
                (authority.session_id,),
            )
    assert repo.read_connection(authority_b)["id"] == other["id"]


def test_a_nonexistent_account_or_session_is_refused_with_the_same_text(
    transactions, authority
):
    repo = flows.repository(transactions)
    refuses(repo, Authority(uuid4(), authority.session_id))
    refuses(repo, Authority(authority.account_id, uuid4()))
