"""Step 18: lifecycle withdraw and erase change only the owner's topics rows (NFR2.2).

The TopicsDigests participant applies each ticket through the shared coordinator
contract under the topics login. Before and after each action the realm's superuser
reads back every row of every table outside the topics schema: the accounts ticket,
account, consent and session rows the coordinator's guard locks, the corpus rows the
eligibility read takes, the Personalization settings the preference read takes, and
every other owner's rows. All of them, and every other account's topics rows, read back
unchanged, and the participant's login holds no write grant outside topics.

The participant acts for its own synthetic account, so erasing it reaches no row any
other suite relies on.
"""

import datetime as dt
from uuid import uuid4

from psycopg import sql
from psycopg.types.json import Jsonb

from backend.modules.accounts.control_policy import SYNTHETIC_POLICY
from backend.modules.topics.control_lifecycle import TopicsDigestsLifecycleParticipant
from backend.modules.topics.repository import TopicsRepository
from tests.u5_topics_digests.conftest import _make_authority
from tests.u5_topics_digests.realm_catalog import (
    admin_connection,
    relation_privileges,
    relations,
    schema_privileges,
)

W1 = (dt.date(2026, 3, 2), dt.date(2026, 3, 8))
ITEM = {
    "versionId": "v-isolation-1",
    "paperId": "p-isolation-1",
    "title": "Isolation Paper",
    "publishedOn": "2026-03-03",
}
ROW_DIGEST = "SELECT count(*) AS n, md5(coalesce(string_agg(t::text, E'\\n' ORDER BY t::text), '')) AS rows FROM {} t"
# Every other account's topics rows, and every evidence row but this test's tickets'.
OTHER_TOPICS_ROWS = {
    "followed_topic": "account_id <> %(owner)s",
    "digest_settings": "topic_id IN (SELECT id FROM topics.followed_topic WHERE account_id <> %(owner)s)",
    "digest_run": "topic_id IN (SELECT id FROM topics.followed_topic WHERE account_id <> %(owner)s)",
    "delivery_outcome": "run_id IN (SELECT r.id FROM topics.digest_run r JOIN topics.followed_topic f "
    "ON f.id=r.topic_id WHERE f.account_id <> %(owner)s)",
    "send_log_entry": "run_id IN (SELECT r.id FROM topics.digest_run r JOIN topics.followed_topic f "
    "ON f.id=r.topic_id WHERE f.account_id <> %(owner)s)",
    "topic_delivery_watermark": "topic_id IN (SELECT id FROM topics.followed_topic WHERE account_id <> %(owner)s)",
    "email_unsubscribe": "account_id <> %(owner)s",
    "lifecycle_evidence": "request_id <> ALL(%(requests)s)",
}
# The owner's own topics rows, by the topic and run identifiers taken before erasure.
OWNER_TOPICS_ROWS = {
    "followed_topic": "id = ANY(%(topics)s)",
    "digest_settings": "topic_id = ANY(%(topics)s)",
    "digest_run": "topic_id = ANY(%(topics)s)",
    "delivery_outcome": "run_id = ANY(%(runs)s)",
    "send_log_entry": "run_id = ANY(%(runs)s)",
    "topic_delivery_watermark": "topic_id = ANY(%(topics)s)",
    "email_unsubscribe": "topic_id = ANY(%(topics)s)",
}


def unique(base):
    return f"{base}-{uuid4().hex[:10]}"


def queue_run(repository, connect, topic_id):
    with connect("topics") as conn:
        revision = conn.execute(
            "SELECT revision FROM topics.digest_settings WHERE topic_id=%s", (topic_id,)
        ).fetchone()["revision"]
    run, adopted = repository.prepare_run(topic_id, W1[0], W1[1], revision, [ITEM])
    assert adopted is False
    return run["id"]


def issue_ticket(connect, account_id, action):
    """A live, current-generation TopicsDigests ticket, written by AccountAccess's login."""
    request, revision = uuid4(), uuid4()
    with connect("accounts") as conn:
        conn.execute(
            "UPDATE accounts.account SET lifecycle_revision=%s WHERE id=%s", (revision, account_id)
        )
        conn.execute(
            "INSERT INTO accounts.lifecycle_request(id,account_id,revision,action,policy_ref,"
            "manifest_revision,manifest,disposition,reason_key) "
            "VALUES(%s,%s,%s,%s,%s,'isolation-test',%s,'pending','pending')",
            (
                request,
                account_id,
                revision,
                action,
                Jsonb(SYNTHETIC_POLICY.reference),
                Jsonb([["TopicsDigests", "live_records"]]),
            ),
        )
        conn.execute(
            "INSERT INTO accounts.lifecycle_scope(request_id,participant,scope,generation,"
            "lease_until,attempts) VALUES(%s,'TopicsDigests','live_records',1,"
            "clock_timestamp()+interval '15 seconds',1)",
            (request,),
        )
    return dict(
        request_id=request,
        account_id=account_id,
        lifecycle_revision=revision,
        participant="TopicsDigests",
        scope="live_records",
        generation=1,
        action=action,
        policy_ref=SYNTHETIC_POLICY.reference,
        manifest_revision="isolation-test",
    )


def rows_outside_topics(realm) -> dict:
    with admin_connection(realm, autocommit=True) as conn:
        tables = [row for row in relations(conn, exclude=("topics",)) if row["kind"] in ("r", "p")]
        return {
            f"{table['schema']}.{table['name']}": conn.execute(
                sql.SQL(ROW_DIGEST).format(sql.Identifier(table["schema"], table["name"]))
            ).fetchone()
            for table in tables
        }


def topics_rows(realm, wheres: dict, params: dict) -> dict:
    with admin_connection(realm, autocommit=True) as conn:
        return {
            table: conn.execute(
                sql.SQL(ROW_DIGEST + " WHERE ").format(sql.Identifier("topics", table)) + sql.SQL(where),
                params,
            ).fetchone()
            for table, where in wheres.items()
        }


def test_withdraw_and_erase_change_only_the_owners_topics_rows(transactions, connect, realm, authority_b):
    owner = _make_authority(connect, realm, suffix="lifecycle-isolation")
    repository = TopicsRepository(transactions)
    participant = TopicsDigestsLifecycleParticipant(transactions)
    delivered = repository.follow(owner, unique("isolation-delivered"), "Delivered")["topic"]["id"]
    queued = repository.follow(owner, unique("isolation-queued"), "Queued")["topic"]["id"]
    bystander = repository.follow(authority_b, unique("isolation-bystander"), "Bystander")["topic"]["id"]
    sent = queue_run(repository, connect, delivered)
    assert repository.begin_send(sent, "local-sink") is not None
    assert repository.finish_send(sent, "sent", transport_receipt="sink-isolation") is not None
    waiting = queue_run(repository, connect, queued)
    untouched = queue_run(repository, connect, bystander)
    mine = {"topics": [delivered, queued], "runs": [sent, waiting]}
    requests = []
    for action in ("withdraw", "erase"):
        ticket = issue_ticket(connect, owner.account_id, action)
        requests.append(ticket["request_id"])
        others = {"owner": owner.account_id, "requests": requests}
        outside_before = rows_outside_topics(realm)
        others_before = topics_rows(realm, OTHER_TOPICS_ROWS, others)
        result = participant.apply(ticket)
        assert result["disposition"] == "complete" and result["evidenceRef"], action
        assert rows_outside_topics(realm) == outside_before, action
        assert topics_rows(realm, OTHER_TOPICS_ROWS, others) == others_before, action
        with connect("topics") as conn:
            evidence = conn.execute(
                "SELECT evidence_ref FROM topics.lifecycle_evidence WHERE request_id=%s AND scope='live_records'",
                (ticket["request_id"],),
            ).fetchone()
            if action == "withdraw":
                statuses = conn.execute(
                    "SELECT id,status FROM topics.followed_topic WHERE id = ANY(%s)", (mine["topics"],)
                ).fetchall()
                states = conn.execute(
                    "SELECT id,state FROM topics.digest_run WHERE id = ANY(%s)", ([sent, waiting, untouched],)
                ).fetchall()
        assert evidence is not None and str(evidence["evidence_ref"]) == result["evidenceRef"], action
        if action == "withdraw":
            assert {row["id"]: row["status"] for row in statuses} == dict.fromkeys(mine["topics"], "unsubscribed")
            assert {row["id"]: row["state"] for row in states} == {
                sent: "sent",
                waiting: "discarded",
                untouched: "prepared",
            }
    # Erasure left none of the owner's topics rows, in any topics table.
    assert {table: row["n"] for table, row in topics_rows(realm, OWNER_TOPICS_ROWS, mine).items()} == dict.fromkeys(
        OWNER_TOPICS_ROWS, 0
    )
    with admin_connection(realm) as conn:
        held = relation_privileges(conn, "docsuri_topics")
        schemas = schema_privileges(conn, "docsuri_topics")
    assert {
        name: privileges - {"SELECT"}
        for name, privileges in held.items()
        if not name.startswith("topics.") and privileges - {"SELECT"}
    } == {}
    assert [name for name, privileges in schemas.items() if "CREATE" in privileges] == []
