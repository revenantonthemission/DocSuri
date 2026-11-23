"""Step 20 (i): the topics probe U5 added to backend/local_observation.py.

U5 added one owner probe there: counts of the topics store's followed topics, runs and
send attempts, and the presence of its run guard, read through the topics owner's own
login. The default observation set leaves topics out, so a host that does not install
topics never probes a store it lacks; a host that installs topics asks for it, and its
readiness derives from that observation. Evidence is counts only.
"""

import json
import time
from uuid import uuid4

from backend import local_observation
from backend.local_observation import OBSERVATION_SECONDS, PROBES, observe_all, probe_owner
from backend.modules.topics.repository import TopicsRepository
from backend.transactions import OwnerTransactions
from tests.u5_topics_digests.realm_catalog import admin_connection

EVIDENCE = {"topics", "runs", "sends", "guard_functions"}
# The probe's third count reads this table; denying its SELECT denies the probe.
DENIED_TABLE = "topics.send_log_entry"
TOPICS_LOGIN = "docsuri_topics"


def store_counts(connect):
    with connect("topics") as conn:
        return dict(
            conn.execute(
                "SELECT (SELECT count(*) FROM topics.followed_topic) AS topics,"
                "(SELECT count(*) FROM topics.digest_run) AS runs,"
                "(SELECT count(*) FROM topics.send_log_entry) AS sends"
            ).fetchone()
        )


def test_the_topics_probe_counts_its_own_store(transactions, connect):
    observed = probe_owner(transactions, "topics")
    assert observed["capability"] == "topics" and observed["disposition"] == "available"
    assert set(observed["evidence"]) == EVIDENCE
    assert all(type(value) is int for value in observed["evidence"].values())
    assert {key: observed["evidence"][key] for key in ("topics", "runs", "sends")} == (
        store_counts(connect)
    )
    # Exactly the run guard the topics store's safety depends on.
    assert observed["evidence"]["guard_functions"] == 1
    assert observed["expiresAt"] - observed["observedAt"] == OBSERVATION_SECONDS


def test_topics_is_observed_only_where_it_is_installed(transactions):
    default = observe_all(transactions)
    assert "topics" not in default
    assert set(default) == set(PROBES) - {"research", "topics", "export"}
    installed = observe_all(transactions, {"accounts", "topics"})
    assert set(installed) == {"accounts", "topics"}
    assert installed["topics"]["disposition"] == "available"


def test_readiness_reprobes_a_failed_topics_observation_and_records_it(transactions):
    now = time.time()
    failed = {
        "capability": "topics",
        "disposition": "unavailable",
        "observedAt": now,
        "expiresAt": now + OBSERVATION_SECONDS,
        "evidence": {"reasonKey": "observation.probeFailed"},
    }
    local_observation.record(transactions, {"topics": failed})
    assert local_observation.fresh(transactions)["topics"]["disposition"] == "unavailable"
    report = local_observation.readiness(transactions, {"topics"})
    assert report["ready"] is True and report["missing"] == []
    [row] = report["observations"]
    assert row["capability"] == "topics" and row["status"] == "available"
    assert set(row["evidence"]) == EVIDENCE
    # The fresh probe replaced the failed observation in the operations store.
    stored = local_observation.fresh(transactions)["topics"]
    assert stored["disposition"] == "available" and set(stored["evidence"]) == EVIDENCE


def test_an_unreachable_topics_store_is_never_ready(realm):
    closed = OwnerTransactions(realm)
    closed.close()
    observed = probe_owner(closed, "topics")
    assert observed["disposition"] == "unavailable"
    assert observed["evidence"] == {"reasonKey": "observation.storeUnavailable"}
    report = local_observation.readiness(closed, {"topics"})
    assert report["ready"] is False and report["missing"] == ["topics"]
    assert report["observations"] == [
        {
            "capability": "topics",
            "status": "unknown",
            "reasonKey": "observation.storeUnavailable",
        }
    ]


def table_access(conn):
    row = conn.execute(
        "SELECT has_table_privilege(%(role)s, %(table)s, 'SELECT') AS table_select,"
        " has_any_column_privilege(%(role)s, %(table)s, 'SELECT') AS column_select,"
        " (SELECT relacl::text FROM pg_class WHERE oid = %(table)s::regclass) AS acl",
        {"role": TOPICS_LOGIN, "table": DENIED_TABLE},
    ).fetchone()
    return row


def test_a_denied_topics_store_is_recorded_as_store_denied_with_the_reason_key_only(
    realm, transactions
):
    with admin_connection(realm, autocommit=True) as admin:
        granted = table_access(admin)
        assert granted["table_select"] is True
        try:
            # A real denial on the realm, never a mocked one: the topics login loses
            # SELECT on one table the probe reads.
            admin.execute(f"REVOKE SELECT ON {DENIED_TABLE} FROM {TOPICS_LOGIN}")
            denied = table_access(admin)
            assert denied["table_select"] is False and denied["column_select"] is False
            observed = probe_owner(transactions, "topics")
            local_observation.record(transactions, {"topics": observed})
            stored = local_observation.fresh(transactions)["topics"]
        finally:
            admin.execute(f"GRANT SELECT ON {DENIED_TABLE} TO {TOPICS_LOGIN}")
            assert table_access(admin)["acl"] == granted["acl"]
    assert observed["capability"] == "topics" and observed["disposition"] == "unavailable"
    assert observed["evidence"] == {"reasonKey": "observation.storeDenied"}
    assert stored["disposition"] == "unavailable"
    assert stored["evidence"] == {"reasonKey": "observation.storeDenied"}
    # Neither the observation nor the stored row carries the error's text.
    for text in (json.dumps(observed), json.dumps(stored["evidence"])):
        assert "permission" not in text and "send_log_entry" not in text
        assert TOPICS_LOGIN not in text
    # With the grant restored the probe reads again; the stored observation is current.
    restored = probe_owner(transactions, "topics")
    assert restored["disposition"] == "available" and set(restored["evidence"]) == EVIDENCE
    local_observation.record(transactions, {"topics": restored})


def test_a_recorded_topics_observation_holds_its_four_counts_and_no_identifier(
    transactions, authority, connect
):
    key, name = f"observation-topic-{uuid4().hex[:10]}", "Observation Topic"
    topic_id = TopicsRepository(transactions).follow(authority, key, name)["topic"]["id"]
    with connect("accounts") as conn:
        email = conn.execute(
            "SELECT email FROM accounts.account WHERE id=%s", (authority.account_id,)
        ).fetchone()["email"]
    observed = probe_owner(transactions, "topics")
    local_observation.record(transactions, {"topics": observed})
    stored = local_observation.fresh(transactions)["topics"]
    assert stored["disposition"] == "available"
    assert set(stored["evidence"]) == EVIDENCE
    assert all(type(value) is int for value in stored["evidence"].values())
    assert stored["evidence"]["topics"] >= 1
    text = json.dumps(stored["evidence"])
    for private in (str(authority.account_id), str(authority.session_id), str(topic_id), key, name, email):
        assert private not in text
    TopicsRepository(transactions).unsubscribe(authority, topic_id)
