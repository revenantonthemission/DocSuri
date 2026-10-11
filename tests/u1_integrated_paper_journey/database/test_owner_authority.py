from __future__ import annotations

import threading
import time
from uuid import uuid4

import psycopg
import pytest

pytestmark = pytest.mark.u1_database


@pytest.mark.parametrize(
    "owner",
    [
        "accounts",
        "corpus",
        "library",
        "personalization",
        "discovery",
        "usage",
        "assistance",
        "operations",
    ],
)
def test_every_runtime_role_has_own_receipts_and_no_foreign_mutation(connect, identities, owner):
    foreign = "corpus.version" if owner == "accounts" else "accounts.account"
    field = "eligible" if owner == "accounts" else "active"
    conn = connect(owner)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute(f"UPDATE {foreign} SET {field}=false")
    conn.rollback()
    conn.execute(
        f"INSERT INTO {owner}.receipt(account_id,kind,key,intent_hash,outcome) VALUES(%s,%s,%s,%s,%s)",
        (identities["a"], "role-positive-control", uuid4(), "a" * 64, "{}"),
    )
    conn.commit()
    assert conn.execute(
        "SELECT rolsuper,rolcreatedb,rolcreaterole,rolbypassrls FROM pg_roles WHERE rolname=current_user"
    ).fetchone() == (False, False, False, False)


def test_guard_functions_have_fixed_nonlogin_owners_and_safe_search_path(connect, identities):
    with connect("library") as conn:
        rows = conn.execute(
            "SELECT p.proname,p.prosecdef,p.proconfig,r.rolcanlogin FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace JOIN pg_roles r ON r.oid=p.proowner WHERE n.nspname IN ('accounts','corpus') AND p.proname IN ('guard_session','guard_execution','guard_version','guard_paper_reference')"
        ).fetchall()
        assert len(rows) == 4
        assert all(
            security and config == ["search_path=pg_catalog"] and not login
            for _, security, config, login in rows
        )


def save(conn, ids, *, key=None, expected=None):
    return conn.execute(
        "SELECT library.save_paper(%s,%s,%s,%s,%s,%s)",
        (ids["a"], ids["session"], ids["paper"], ids["version"], key or uuid4(), expected),
    ).fetchone()[0]


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE accounts.account SET active=false",
        "DELETE FROM accounts.account",
        "UPDATE corpus.version SET eligible=false",
        "DELETE FROM corpus.version",
        "SELECT password_hash FROM accounts.account",
        "SET ROLE docsuri_accounts_owner",
        "CREATE TABLE public.unowned(id integer)",
        "CREATE SCHEMA unowned",
    ],
)
def test_foreign_mutation_and_privilege_escape_denied(connect, identities, statement):
    with connect("library") as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(statement)
    with connect("library") as conn:
        assert save(conn, identities)["paperId"] == identities["paper"]


@pytest.mark.parametrize(
    "account,session,purpose",
    [("b", "session", "local-research"), ("a", "session", "arbitrary-purpose")],
)
def test_guard_cannot_widen_authority(connect, identities, account, session, purpose):
    with connect("library") as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                "SELECT accounts.guard_session(%s,%s,%s)",
                (identities[account], identities[session], purpose),
            )


def test_no_account_access_function_for_operations(connect, identities):
    with connect("operations") as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                "SELECT accounts.guard_session(%s,%s,%s)",
                (identities["a"], identities["session"], "local-research"),
            )


def test_guarded_write_and_receipt_rollback_together(connect, identities):
    conn = connect("library")
    key = uuid4()
    save(conn, identities, key=key)
    conn.rollback()
    assert (
        conn.execute(
            "SELECT count(*) FROM library.saved_paper WHERE account_id=%s", (identities["a"],)
        ).fetchone()[0]
        == 0
    )
    assert (
        conn.execute("SELECT count(*) FROM library.receipt WHERE key=%s", (key,)).fetchone()[0] == 0
    )


def test_absent_cas_replay_after_later_mutation(connect, identities):
    conn = connect("library")
    key = uuid4()
    original = save(conn, identities, key=key)
    conn.commit()
    later = save(conn, identities, expected=original["revision"])
    conn.commit()
    assert later["revision"] != original["revision"]
    assert save(conn, identities, key=key) == original
    conn.commit()
    with pytest.raises(psycopg.errors.SerializationFailure):
        save(conn, identities)
    conn.rollback()
    with pytest.raises(psycopg.errors.UniqueViolation):
        save(conn, identities, key=key, expected=later["revision"])


def test_revocation_denies_even_exact_receipt_replay(connect, identities):
    conn = connect("library")
    key = uuid4()
    save(conn, identities, key=key)
    conn.commit()
    with connect("accounts") as authority:
        authority.execute(
            "UPDATE accounts.account SET active=false WHERE id=%s", (identities["a"],)
        )
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        save(conn, identities, key=key)


def revoke(conn, ids, kind):
    if kind == "account":
        conn.execute("UPDATE accounts.account SET active=false WHERE id=%s", (ids["a"],))
    elif kind == "session":
        conn.execute("UPDATE accounts.session SET revoked=true WHERE id=%s", (ids["session"],))
    elif kind == "consent":
        conn.execute(
            "UPDATE accounts.consent SET granted=false WHERE account_id=%s AND purpose='local-research'",
            (ids["a"],),
        )
    else:
        conn.execute("UPDATE corpus.version SET eligible=false WHERE id=%s", (ids["version"],))


def assert_blocked(observer, waiter, holder):
    deadline = time.monotonic() + 1.5
    while time.monotonic() < deadline:
        row = observer.execute("SELECT pg_blocking_pids(%s)", (waiter,)).fetchone()[0]
        observer.commit()
        if holder in row:
            return
        time.sleep(0.01)
    pytest.fail("expected real PostgreSQL lock dependency not observed")


@pytest.mark.parametrize("kind", ["account", "session", "consent", "source"])
@pytest.mark.parametrize("effect_first", [True, False])
def test_revocation_effect_orders_use_same_transaction_locks(
    connect, identities, kind, effect_first
):
    target = connect("library")
    authority = connect("corpus" if kind == "source" else "accounts")
    observer = connect("operations")
    outcome = []
    if effect_first:
        save(target, identities)

        def later():
            try:
                revoke(authority, identities, kind)
                authority.commit()
                outcome.append("revoked")
            except psycopg.Error as exc:
                outcome.append(exc.sqlstate)

        thread = threading.Thread(target=later)
        thread.start()
        assert_blocked(observer, authority.info.backend_pid, target.info.backend_pid)
        target.commit()
        thread.join(3)
        assert outcome == ["revoked"]
        assert (
            target.execute(
                "SELECT count(*) FROM library.saved_paper WHERE account_id=%s", (identities["a"],)
            ).fetchone()[0]
            == 1
        )
    else:
        revoke(authority, identities, kind)

        def later():
            try:
                save(target, identities)
                target.commit()
                outcome.append("wrongly-committed")
            except psycopg.Error as exc:
                target.rollback()
                outcome.append(exc.sqlstate)

        thread = threading.Thread(target=later)
        thread.start()
        assert_blocked(observer, target.info.backend_pid, authority.info.backend_pid)
        authority.commit()
        thread.join(3)
        assert outcome[0] in ("40001", "42501")
        assert (
            target.execute(
                "SELECT count(*) FROM library.saved_paper WHERE account_id=%s", (identities["a"],)
            ).fetchone()[0]
            == 0
        )
    assert not thread.is_alive()
