"""Owner-rights functions of schema `export`: compare-and-sets, deletes and count-only reads."""

import hashlib
import re
from uuid import uuid4

import psycopg
import pytest
from psycopg.types.json import Jsonb

from tests.u6_approved_export import export_rows as rows

ANCIENT = "clock_timestamp()-interval '10 years'"
UUID_TEXT = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def now(conn):
    return conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]


def pace_rows(conn, connection):
    return conn.execute(
        "SELECT count(*) AS n FROM export.connection_pace WHERE connection_id=%s", (connection,)
    ).fetchone()["n"]


def test_store_writes_a_first_configure_only_while_pending_and_held(connect):
    """R-02: a check whose reservation was taken over or belongs elsewhere stores nothing."""
    with connect("export") as conn:
        connection, account, holder = rows.reserve(conn)
        assert rows.store(conn, account, connection, 0, holder=uuid4()) is None
        assert rows.store(conn, uuid4(), connection, 0, holder=holder) is None
        taker = uuid4()
        conn.execute(
            "UPDATE export.connection SET pending_holder=%s,pending_started_at=clock_timestamp() "
            "WHERE account_id=%s AND state='pending' AND pending_holder=%s",
            (taker, account, holder),
        )
        assert rows.store(conn, account, connection, 0, holder=holder) is None
        assert rows.connection_row(conn, connection)["state"] == "pending"
        assert rows.store(conn, account, connection, 0, holder=taker) == 1
        row = rows.connection_row(conn, connection)
        assert (row["state"], row["revision"], row["pending_holder"]) == ("connected", 1, None)
        assert rows.store(conn, account, connection, 0, holder=taker) is None
        with pytest.raises(psycopg.errors.InvalidParameterValue), conn.transaction():
            rows.store(conn, account, connection, 0, holder=None)


def test_store_replaces_only_at_the_expected_revision_and_never_from_unavailable(connect):
    with connect("export") as conn:
        connection, account = rows.connected(conn)
        assert rows.store(conn, account, connection, 2) is None
        assert rows.store(conn, account, connection, 1) == 2
        conn.execute("UPDATE export.connection SET state='unavailable' WHERE id=%s", (connection,))
        assert rows.store(conn, account, connection, 2) is None
        assert rows.connection_row(conn, connection)["state"] == "unavailable"
        assert conn.execute(
            "SELECT export.clear_token_envelope(%s,%s,2,'disconnected') AS revision",
            (account, connection),
        ).fetchone()["revision"] == 3
        assert rows.store(conn, account, connection, 3) == 4
        assert rows.connection_row(conn, connection)["state"] == "connected"


def test_clear_is_a_compare_and_set_on_the_revision(connect):
    with connect("export") as conn:
        connection, account = rows.connected(conn)
        clear = "SELECT export.clear_token_envelope(%s,%s,%s,%s) AS revision"
        assert conn.execute(clear, (account, connection, 2, "revoked")).fetchone()["revision"] is None
        assert conn.execute(clear, (uuid4(), connection, 1, "revoked")).fetchone()["revision"] is None
        assert rows.connection_row(conn, connection)["state"] == "connected"
        with pytest.raises(psycopg.errors.InvalidParameterValue), conn.transaction():
            conn.execute(clear, (account, connection, 1, "pending"))
        assert conn.execute(clear, (account, connection, 1, "revoked")).fetchone()["revision"] == 2
        assert conn.execute(clear, (account, connection, 2, "revoked")).fetchone()["revision"] is None
        row = rows.connection_row(conn, connection)
        assert (row["state"], row["revision"]) == ("revoked", 2)


def test_release_and_sweep_are_compare_and_sets_on_the_holder(connect):
    with connect("export") as conn:
        connection, account, holder = rows.reserve(conn)
        release = "SELECT export.release_pending(%s,%s) AS released"
        assert conn.execute(release, (account, uuid4())).fetchone()["released"] is False
        assert rows.connection_row(conn, connection) and pace_rows(conn, connection) == 1
        assert conn.execute(release, (account, holder)).fetchone()["released"] is True
        assert rows.connection_row(conn, connection) is None and pace_rows(conn, connection) == 0

        stale, _, _ = rows.reserve(conn, started_at=ANCIENT)
        fresh, _, _ = rows.reserve(conn)
        taken, _, _ = rows.reserve(conn, started_at=ANCIENT)
        conn.execute(
            "UPDATE export.connection SET pending_holder=%s,pending_started_at=clock_timestamp() "
            "WHERE id=%s",
            (uuid4(), taken),
        )
        stored, _ = rows.connected(conn)
        removed = conn.execute(
            "SELECT export.sweep_stale_pending(%s,120,1000) AS removed", (now(conn),)
        ).fetchone()["removed"]
        assert removed >= 1
        assert rows.connection_row(conn, stale) is None and pace_rows(conn, stale) == 0
        for kept in (fresh, taken, stored):
            assert rows.connection_row(conn, kept) is not None and pace_rows(conn, kept) == 1
        with pytest.raises(psycopg.errors.InvalidParameterValue), conn.transaction():
            conn.execute("SELECT export.sweep_stale_pending(%s,0,10)", (now(conn),))


def test_purge_removes_only_unapproved_revisions_past_retention(connect):
    with connect("export") as conn:
        connection, account = rows.connected(conn)
        old = conn.execute(f"SELECT {ANCIENT} AS t").fetchone()["t"]
        approved = rows.preview(conn, connection, account, prepared_at=old)
        rows.approve(conn, approved)
        superseded = rows.preview(
            conn,
            connection,
            account,
            artifact=approved["artifact"],
            destination=approved["destination"],
            prepared_at=old,
        )
        lonely = rows.preview(conn, connection, account, prepared_at=old)
        fresh = rows.preview(conn, connection, account)
        removed = conn.execute(
            "SELECT export.purge_unapproved_previews(%s,7,1000) AS removed", (now(conn),)
        ).fetchone()["removed"]
        assert removed >= 2

        def present(facts):
            return conn.execute(
                "SELECT count(*) AS n FROM export.preview_revision WHERE preview_id=%s AND revision=%s",
                (facts["preview_id"], facts["revision"]),
            ).fetchone()["n"]

        def pair(facts):
            return conn.execute(
                "SELECT count(*) AS n FROM export.preview_pair WHERE preview_id=%s",
                (facts["preview_id"],),
            ).fetchone()["n"]

        assert (present(approved), present(superseded), present(lonely), present(fresh)) == (1, 0, 0, 1)
        assert (pair(approved), pair(lonely), pair(fresh)) == (1, 0, 1)
        with pytest.raises(psycopg.errors.InvalidParameterValue), conn.transaction():
            conn.execute("SELECT export.purge_unapproved_previews(%s,0,10)", (now(conn),))


def seed_account_records(conn, account):
    """A full export history for one account: every table erase must clear."""
    bound = rows.exported(conn, account)
    attempt = rows.claim(conn, bound["effect"])
    rows.end_attempt(conn, attempt, "uncertain")
    rows.advance(conn, bound["effect"], "unknown")
    conn.execute(
        "INSERT INTO export.reconciliation_check(id,effect_id,checked_at,window_start,result,"
        "evidence_hash) VALUES(%s,%s,clock_timestamp(),clock_timestamp(),'not-found',repeat('d',64))",
        (uuid4(), bound["effect"]),
    )
    conn.execute(
        "INSERT INTO export.replay_record(account_id,operation,operation_key,input_hash,response) "
        "VALUES(%s,'configure',%s,repeat('a',64),%s)",
        (account, uuid4(), Jsonb({"revision": 1})),
    )
    rows.preview(conn, bound["connection"], account)  # an unapproved revision as well
    return bound


ACCOUNT_TABLES = (
    "SELECT count(*) AS n FROM export.connection WHERE account_id=%s",
    "SELECT count(*) AS n FROM export.preview_pair WHERE account_id=%s",
    "SELECT count(*) AS n FROM export.approval WHERE account_id=%s",
    "SELECT count(*) AS n FROM export.effect WHERE account_id=%s",
    "SELECT count(*) AS n FROM export.replay_record WHERE account_id=%s",
)


def remaining(conn, account, effect):
    counts = [conn.execute(query, (account,)).fetchone()["n"] for query in ACCOUNT_TABLES]
    for table in ("attempt", "reconciliation_check"):
        counts.append(
            conn.execute(
                f"SELECT count(*) AS n FROM export.{table} WHERE effect_id=%s", (effect,)
            ).fetchone()["n"]
        )
    return counts


def erase(conn, ticket):
    """Erase, then commit: the guard's share lock on the account would block the next ticket."""
    conn.execute("SELECT export.erase_account_records(%s,%s,%s,%s,%s)", ticket)
    conn.commit()


def test_erase_refuses_without_an_erase_ticket_and_removes_only_that_account(connect, authority):
    """BR6.2: every export row of the account goes; another account and the counts stay."""
    account = authority.account_id
    with connect("export") as conn:
        erase(conn, rows.lifecycle_ticket(connect, account, "erase"))  # earlier runs' rows
        bound = seed_account_records(conn, account)
        other = rows.exported(conn)
        conn.commit()
        with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
            erase(conn, (uuid4(), account, 1, Jsonb({}), "unknown"))
        conn.commit()
        withdraw = rows.lifecycle_ticket(connect, account, "withdraw")
        with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
            erase(conn, withdraw)
        assert all(count > 0 for count in remaining(conn, account, bound["effect"]))
        conn.commit()
        ticket = rows.lifecycle_ticket(connect, account, "erase")
        conn.execute(
            "INSERT INTO export.lifecycle_counts(request_id,scope,action,reason_key,"
            "pages_possibly_created) VALUES(%s,'live_records','erase','owner-scope-complete',1)",
            (ticket[0],),
        )
        erase(conn, ticket)
        assert remaining(conn, account, bound["effect"]) == [0] * 7
        assert pace_rows(conn, bound["connection"]) == 0
        assert remaining(conn, other["account"], other["effect"])[:4] == [1, 1, 1, 1]
        assert conn.execute(
            "SELECT pages_possibly_created FROM export.lifecycle_counts WHERE request_id=%s",
            (ticket[0],),
        ).fetchone()["pages_possibly_created"] == 1


def test_lifecycle_release_pending_needs_a_withdraw_or_erase_ticket(connect, authority_b):
    account = authority_b.account_id
    with connect("export") as conn:
        erase(conn, rows.lifecycle_ticket(connect, account, "erase"))  # earlier runs' rows
        connection, _, _ = rows.reserve(conn, account)
        release = "SELECT export.lifecycle_release_pending(%s,%s,%s,%s,%s,%s) AS removed"

        def ticket(action, scope):
            conn.commit()  # release any guard lock on the account before seeding a ticket
            request, owner, generation, policy, manifest = rows.lifecycle_ticket(
                connect, account, action, scopes=(scope,)
            )
            return (request, owner, scope, generation, policy, manifest)

        reactivate = ticket("reactivate", "pending_work")
        with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
            conn.execute(release, reactivate)
        external = ticket("withdraw", "external_copies")
        with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
            conn.execute(release, external)
        assert rows.connection_row(conn, connection)["state"] == "pending"
        withdraw = ticket("withdraw", "pending_work")
        assert conn.execute(release, withdraw).fetchone()["removed"] == 1
        assert rows.connection_row(conn, connection) is None and pace_rows(conn, connection) == 0


def test_reseal_is_a_compare_and_set_on_the_envelope_that_keeps_the_revision(connect, operator):
    with connect("export") as conn:
        connection, account = rows.connected(conn)
        version = conn.execute(
            "SELECT token_key_version FROM export.open_token_envelope(%s,%s)", (account, connection)
        ).fetchone()["token_key_version"]
    page = operator.execute(
        "SELECT * FROM export.token_envelopes_for_reseal(%s,10)", (version,)
    ).fetchall()
    assert [row["connection_id"] for row in page] == [connection]
    assert (page[0]["account_id"], page[0]["revision"]) == (account, 1)
    current = hashlib.sha256(bytes(page[0]["sealed_token"])).hexdigest()
    new_version = rows.key_version()
    reseal = "SELECT export.reseal_token(%s,%s,%s,%s) AS resealed"
    assert operator.execute(
        reseal, (connection, "0" * 64, rows.envelope(new_version), new_version)
    ).fetchone()["resealed"] is False
    with pytest.raises(psycopg.errors.CheckViolation), operator.transaction():
        operator.execute(reseal, (connection, current, rows.envelope(new_version), version))
    assert operator.execute(
        reseal, (connection, current, rows.envelope(new_version), new_version)
    ).fetchone()["resealed"] is True
    operator.commit()
    with connect("export") as conn:
        opened = conn.execute(
            "SELECT * FROM export.open_token_envelope(%s,%s)", (account, connection)
        ).fetchone()
        assert (opened["revision"], opened["token_key_version"]) == (1, new_version)


def test_key_counts_and_status_counts_carry_no_identifiers(connect):
    with connect("export") as conn:
        connection, account = rows.connected(conn)
        counts = conn.execute("SELECT * FROM export.token_key_counts()").fetchall()
        assert counts and all(set(row) == {"token_key_version", "sealed_tokens"} for row in counts)
        assert all(re.fullmatch(r"u6-[0-9a-f]{32}", row["token_key_version"]) for row in counts)
        rows.exported(conn)
        conn.execute(
            "INSERT INTO export.lane_status(outcome) VALUES('pass-complete') "
            "ON CONFLICT(singleton) DO UPDATE SET outcome=excluded.outcome,observed_at=clock_timestamp()"
        )
        status = conn.execute(
            "SELECT export.status_counts(%s) AS status", (now(conn),)
        ).fetchone()["status"]
        assert set(status) == {
            "effects",
            "oldestAcceptedSeconds",
            "oldestUnknownSeconds",
            "connections",
            "lane",
        }
        assert status["effects"]["accepted"] >= 1 and status["connections"]["connected"] >= 1
        assert status["lane"]["outcome"] == "pass-complete"
        text = str(status) + str(counts)
        assert not UUID_TEXT.search(text)
        assert str(account) not in text and str(connection) not in text
