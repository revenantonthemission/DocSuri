"""Real owner connections keep a recovery slot across U3's API and worker instances.

U3 creates every owner login with CONNECTION LIMIT 2, which PostgreSQL enforces
itself. At most two operations hold the login at once: a held API normal
operation and a held recovery read. A worker normal operation queues at the
per-owner normal gate and runs only after the API operation is released, so the
API and worker operations never overlap. The gate's evidence is that recovery
gets the second slot and the queued normal operation still runs; without the
gate one of them is refused a login. The worker's gate wait is raised from the
controls default (1 s) to WAIT_SECONDS, as U4's runtime test sets
_queue_seconds, so the result does not depend on the recovery read finishing
within 1 s on a loaded host.
"""

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from backend.control_runtime import RECOVERY_REQUEST
from backend.transactions import OwnerTransactions

pytestmark = pytest.mark.u3_integration

OWNER = "corpus"
LOGIN = "docsuri_corpus"
WAIT_SECONDS = 2


def held_read(conn, entered, release, observed=None):
    row = conn.execute(
        "SELECT current_user AS role,pg_backend_pid() AS pid,"
        "(SELECT rolconnlimit FROM pg_roles WHERE rolname=current_user) AS role_limit"
    ).fetchone()
    if observed is not None:
        row = dict(row, normal_entered_first=observed.is_set())
    entered.set()
    assert release.wait(WAIT_SECONDS), "test must release the held owner read"
    return row


def test_normal_and_recovery_overlap_without_exceeding_the_owner_role_limit(realm):
    profile = realm[0]
    api = OwnerTransactions(profile)
    worker = OwnerTransactions(profile, process="worker")
    # The queued worker operation waits at the normal-owner gate; give it the
    # test's wait instead of the controls default of 1 s.
    worker._queue_seconds = WAIT_SECONDS
    api_entered, worker_entered, recovery_entered = (threading.Event() for _ in range(3))
    worker_started = threading.Event()
    release_api, release_worker, release_recovery = (threading.Event() for _ in range(3))

    def second_normal():
        worker_started.set()
        return worker.run(
            OWNER, lambda conn: held_read(conn, worker_entered, release_worker)
        )

    def recovery():
        token = RECOVERY_REQUEST.set(True)
        try:
            return api.run(
                OWNER,
                lambda conn: held_read(
                    conn, recovery_entered, release_recovery, observed=worker_entered
                ),
            )
        finally:
            RECOVERY_REQUEST.reset(token)

    try:
        with ThreadPoolExecutor(max_workers=3) as executor:
            try:
                first = executor.submit(
                    api.run, OWNER, lambda conn: held_read(conn, api_entered, release_api)
                )
                assert api_entered.wait(WAIT_SECONDS)
                second = executor.submit(second_normal)
                assert worker_started.wait(WAIT_SECONDS)
                third = executor.submit(recovery)
                # One normal operation holds the login; recovery must still get
                # the second physical slot while the other normal one waits.
                assert recovery_entered.wait(WAIT_SECONDS), "recovery was refused a slot"
                assert not worker_entered.is_set()
                release_api.set()
                first_row = first.result(timeout=WAIT_SECONDS)
                assert worker_entered.wait(WAIT_SECONDS), "queued normal operation never ran"
                release_worker.set()
                second_row = second.result(timeout=WAIT_SECONDS)
                release_recovery.set()
                third_row = third.result(timeout=WAIT_SECONDS)
            finally:
                release_api.set()
                release_worker.set()
                release_recovery.set()
        rows = (first_row, second_row, third_row)
        assert first_row["pid"] != third_row["pid"]
        assert third_row["normal_entered_first"] is False
        assert all(row["role"] == LOGIN and row["role_limit"] == 2 for row in rows)
    finally:
        api.close()
        worker.close()
