"""A tombstone replay removes what reaches the owner only through another row (U8 plan
Step 29; BR4.5).

AccountAccess's erase removes an enrolment's recovery codes through the enrolment
(`accounts.mfa_recovery` has no owner column), and a verification-email challenge's
delivery through the challenge. A replay that removed only owner-column rows would be
blocked by those rows on every pass and fail the verification of any set holding an
erased owner with a second factor. The replay runs here on a rehearsal database of the
composed schema, which no owner holds and which is dropped afterwards.
"""

from __future__ import annotations

import secrets
from pathlib import Path
from uuid import uuid4

import pytest

from backend.modules.operations import restore_checks
from docsuri_ops.migration.realm import RealmDatabases


@pytest.fixture
def scratch(realm):
    databases = RealmDatabases.for_realm(Path(realm.root))
    name = f"docsuri_u8_rehearsal_{secrets.token_hex(6)}"
    databases.create_rehearsal(name)
    try:
        with databases.admin(name) as conn:
            yield conn
    finally:
        from psycopg import sql

        with databases.admin() as conn:
            conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                sql.Identifier(name)))


def seed(conn, account) -> None:
    enrolment, challenge = uuid4(), uuid4()
    conn.execute(
        "INSERT INTO accounts.account(id,email,password_hash,verified,active,"
        "authority_revision,display_name) VALUES(%s,%s,'not-login-material',true,true,%s,"
        "'synthetic')", (account, f"{account}@fixture.invalid", uuid4()))
    conn.execute(
        "INSERT INTO accounts.mfa_enrollment(id,account_id,key_version,ciphertext,"
        "delivery_hash,delivery_expires_at,state) VALUES(%s,%s,'k1','\\x00',%s,"
        "clock_timestamp(),'active')", (enrolment, account, secrets.token_hex(32)))
    conn.execute("INSERT INTO accounts.mfa_recovery(enrollment_id,code_hash) VALUES(%s,%s),"
                 "(%s,%s)", (enrolment, "a" * 64, enrolment, "b" * 64))
    conn.execute(
        "INSERT INTO accounts.challenge(id,account_id,proof_hash,authority_revision,"
        "expires_at,purpose,delivery) VALUES(%s,%s,%s,%s,clock_timestamp(),'verify-email',"
        "'pending')", (challenge, account, secrets.token_hex(32), uuid4()))
    conn.execute("INSERT INTO accounts.delivery(challenge_id,private_path,content_hash,"
                 "byte_length) VALUES(%s,'mail/x.blob',%s,10)",
                 (challenge, "c" * 64))
    # A waiting message is one more row an owner can leave (U8 plan Steps 53(h), 85(j)):
    # the outbox has no owner column, so the replay reaches it through its challenge.
    conn.execute(
        "INSERT INTO accounts.mail_outbox(message_key,purpose,challenge_id,"
        "protected_payload,key_version,queued_at) VALUES(%s,'verification',%s,'\\x00','k1',"
        "clock_timestamp())", (uuid4(), challenge))


def count(conn, query: str, value) -> int:
    return conn.execute(query, (value,)).fetchone()[0]


def test_the_dependents_are_the_rows_without_an_owner_column(scratch):
    graph = restore_checks.dependents(scratch)
    assert ("accounts", "mfa_recovery", "enrollment_id", "id") in graph[
        ("accounts", "mfa_enrollment")]
    assert ("accounts", "delivery", "challenge_id", "id") in graph[("accounts", "challenge")]
    # The outbox's rows reach their owner through their challenge or proof (Step 85(j)).
    assert ("accounts", "mail_outbox", "challenge_id", "id") in graph[("accounts", "challenge")]
    assert ("accounts", "mail_outbox", "control_proof_id", "id") in graph[
        ("accounts", "control_proof")]
    # Erasure evidence and owner tables are never a dependent to remove.
    for children in graph.values():
        for schema, table, _, _ in children:
            assert f"{schema}.{table}" not in restore_checks.ERASURE_EVIDENCE
            assert table != "receipt"


def test_an_erased_owner_with_a_factor_and_a_mailed_challenge_is_fully_replayed(scratch):
    erased, kept = uuid4(), uuid4()
    seed(scratch, erased)
    seed(scratch, kept)
    assert restore_checks.surviving(scratch, [erased]) == 1
    result = restore_checks.replay(scratch, [erased])
    # Two recovery codes, the enrolment, the outbox row, the delivery and the challenge;
    # the account row stays as erasure evidence.
    assert result == {"replayed": 1, "removedRows": 6}
    assert restore_checks.surviving(scratch, [erased]) == 0
    waiting = ("SELECT count(*) FROM accounts.mail_outbox o JOIN accounts.challenge c ON "
               "c.id=o.challenge_id WHERE c.account_id=%s")
    assert count(scratch, waiting, erased) == 0
    assert count(scratch, waiting, kept) == 1
    assert scratch.execute("SELECT count(*) FROM accounts.mail_outbox").fetchone()[0] == 1
    recovery = ("SELECT count(*) FROM accounts.mfa_recovery r JOIN accounts.mfa_enrollment e "
                "ON e.id=r.enrollment_id WHERE e.account_id=%s")
    assert count(scratch, recovery, kept) == 2
    assert count(scratch, "SELECT count(*) FROM accounts.delivery d JOIN accounts.challenge "
                          "c ON c.id=d.challenge_id WHERE c.account_id=%s", kept) == 1
    assert scratch.execute("SELECT count(*) FROM accounts.mfa_recovery").fetchone()[0] == 2
    row = scratch.execute("SELECT active,lifecycle_state FROM accounts.account WHERE id=%s",
                          (erased,)).fetchone()
    assert row == (False, "erased")
    # Replaying again changes nothing.
    assert restore_checks.replay(scratch, [erased])["removedRows"] == 0
