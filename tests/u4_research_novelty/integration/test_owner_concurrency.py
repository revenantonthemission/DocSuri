"""Real owner connections keep recovery room across API and worker instances."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor

from backend.control_runtime import RECOVERY_REQUEST
from backend.transactions import OwnerTransactions


def test_normal_and_recovery_overlap_without_exceeding_the_owner_role_limit(realm):
    api = OwnerTransactions(realm)
    worker = OwnerTransactions(realm, process="worker")
    normal_entered, recovery_entered, worker_entered = (threading.Event() for _ in range(3))
    worker_started = threading.Event()
    release_normal, release_recovery = threading.Event(), threading.Event()

    def read(conn, entered, release=None):
        row = conn.execute(
            "SELECT current_user AS role,pg_backend_pid() AS pid,"
            "(SELECT rolconnlimit FROM pg_roles WHERE rolname=current_user) AS role_limit"
        ).fetchone()
        entered.set()
        if release is not None:
            assert release.wait(2), "test must release the bounded owner read"
        return row

    def recovery():
        token = RECOVERY_REQUEST.set(True)
        try:
            return api.run("research", lambda conn: read(conn, recovery_entered, release_recovery))
        finally:
            RECOVERY_REQUEST.reset(token)

    def third_normal():
        worker_started.set()
        return worker.run("research", lambda conn: read(conn, worker_entered))

    try:
        with ThreadPoolExecutor(max_workers=3) as executor:
            try:
                first = executor.submit(
                    api.run, "research", lambda conn: read(conn, normal_entered, release_normal)
                )
                assert normal_entered.wait(1)
                second = executor.submit(recovery)
                assert recovery_entered.wait(1)
                third = executor.submit(third_normal)
                assert worker_started.wait(1)
                # Both physical role slots are occupied. The worker must wait
                # inside local admission instead of trying a third connection.
                time.sleep(0.05)
                assert not worker_entered.is_set() and not third.done()
                release_normal.set()
                first_row = first.result(timeout=1)
                third_row = third.result(timeout=1)
                assert worker_entered.is_set() and not release_recovery.is_set()
                release_recovery.set()
                second_row = second.result(timeout=1)
            finally:
                release_normal.set()
                release_recovery.set()
        assert first_row["pid"] != second_row["pid"]
        assert all(
            row["role"] == "docsuri_research" and row["role_limit"] == 2
            for row in (first_row, second_row, third_row)
        )
    finally:
        api.close()
        worker.close()
