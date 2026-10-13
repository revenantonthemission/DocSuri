"""Both lock orders and crash boundaries on the original accepting-owner row."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import psycopg
import pytest

pytestmark = pytest.mark.u2_database


def admission(connect, owner):
    operation = uuid4()
    with connect("assistance") as conn:
        conn.execute("INSERT INTO assistance.admission(operation_id,account_id,intent_hash,intent,disposition) "
            "VALUES(%s,%s,%s,'{}','open')", (operation, owner, 'a'*64))
    return operation


@pytest.mark.parametrize("winner", ["accepted", "rejected"])
def test_first_committed_owner_transition_excludes_opposite(connect, identities, winner):
    operation = admission(connect, identities["a"])
    first, second = connect("assistance"), connect("assistance")
    started = Event()
    first.execute("SELECT operation_id FROM assistance.admission WHERE operation_id=%s FOR UPDATE", (operation,))
    first.execute("UPDATE assistance.admission SET disposition=%s,reservation_id=%s WHERE operation_id=%s",
        (winner, uuid4() if winner == "accepted" else None, operation))

    def competing_transition():
        started.set()
        row = second.execute("SELECT * FROM assistance.admission WHERE operation_id=%s FOR UPDATE", (operation,)).fetchone()
        # The accepting owner must make this decision under the same lock.
        assert row["disposition"] == winner
        with pytest.raises(psycopg.errors.CheckViolation):
            second.execute("UPDATE assistance.admission SET disposition=%s,reservation_id=%s WHERE operation_id=%s",
                ("rejected" if winner == "accepted" else "accepted", uuid4(), operation))
        second.rollback()
        return row

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(competing_transition)
        assert started.wait(1)
        first.commit()
        row = future.result(timeout=3)
    assert (row["closure_ref"] is not None) == (winner == "rejected")


def test_crash_before_commit_leaves_admission_open(connect, identities):
    operation = admission(connect, identities["a"])
    conn = connect("assistance")
    conn.execute("UPDATE assistance.admission SET disposition='rejected' WHERE operation_id=%s", (operation,))
    conn.close()  # Simulate losing the owning connection before commit.
    with connect("assistance") as recovered:
        row = recovered.execute("SELECT * FROM assistance.admission WHERE operation_id=%s", (operation,)).fetchone()
        assert row["disposition"] == "open" and row["closure_ref"] is None


def test_crash_after_commit_preserves_exact_closure(connect, identities):
    operation = admission(connect, identities["a"])
    conn = connect("assistance")
    original = conn.execute("UPDATE assistance.admission SET disposition='rejected' WHERE operation_id=%s RETURNING closure_ref,closed_at", (operation,)).fetchone()
    conn.commit()
    conn.close()
    with connect("assistance") as recovered:
        assert recovered.execute("SELECT closure_ref,closed_at FROM assistance.admission WHERE operation_id=%s", (operation,)).fetchone() == original


def test_generation_cannot_replace_closed_operation(connect, identities):
    operation = admission(connect, identities["a"])
    with connect("assistance") as conn:
        conn.execute("UPDATE assistance.admission SET disposition='rejected' WHERE operation_id=%s", (operation,))
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute("UPDATE assistance.admission SET generation=2 WHERE operation_id=%s", (operation,))


def test_closure_evidence_cannot_be_rebound(connect, identities):
    operation = admission(connect, identities["a"])
    with connect("assistance") as conn:
        conn.execute("UPDATE assistance.admission SET disposition='rejected' WHERE operation_id=%s", (operation,))
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute("UPDATE assistance.admission SET closure_ref=%s WHERE operation_id=%s", (uuid4(), operation))


def test_missing_admission_yields_no_closure(connect):
    with connect("assistance") as conn:
        assert conn.execute("SELECT closure_ref FROM assistance.admission WHERE operation_id=%s AND disposition='rejected'", (uuid4(),)).fetchone() is None


def test_current_withdrawal_denies_old_session(connect, identities):
    with connect("accounts") as conn:
        conn.execute("UPDATE accounts.account SET lifecycle_state='withdrawn' WHERE id=%s", (identities["a"],))
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("SELECT accounts.guard_session(%s,%s,'account-control')", (identities["a"], identities["session"]))
