"""The TopicsDigests lifecycle participant over the real realm
(`backend/modules/topics/control_lifecycle.py`): a withdrawal unsubscribes and discards
queued work, and an erasure removes every digest fact for the account, each with its
reported disposition.

Moved unchanged from `test_topics_logic.py` (plan Step 35, decision L3-1), whose last
test it was; the file name keeps it last among the topics-flow files, since its erasure
removes the shared owner's topics rows. The participant's other five tests are in
`repository/test_lifecycle_participant.py` (3), `repository/test_lifecycle_isolation.py`
and `integration/test_email_unsubscribe.py`. An autouse fixture quiets the persistent
realm first, as in the other topics-flow files."""

from uuid import uuid4

import pytest
from backend.modules.accounts.control_policy import SYNTHETIC_POLICY
from backend.modules.topics.control_lifecycle import TopicsDigestsLifecycleParticipant
from backend.modules.topics.repository import TopicsRepository
from psycopg.types.json import Jsonb

from tests.u5_topics_digests.topics_flow import (
    ITEM,
    W1,
    build,
    follow_topic,
    quiet_realm_rows,
    revision_of,
)


@pytest.fixture(autouse=True)
def quiet_realm(connect):
    quiet_realm_rows(connect)


def test_lifecycle_disposition_reporting(transactions, authority, connect):
    service, _, _ = build(transactions)
    repository = TopicsRepository(transactions)
    _, topic_id = follow_topic(service, authority, base="lifecycle-topic")
    revision = revision_of(connect, topic_id)
    queued, _ = repository.prepare_run(topic_id, W1[0], W1[1], revision, [ITEM])
    participant = TopicsDigestsLifecycleParticipant(transactions)

    def ticket(action):
        request, lifecycle_revision = uuid4(), uuid4()
        with connect("accounts") as conn:
            conn.execute(
                "UPDATE accounts.account SET lifecycle_revision=%s WHERE id=%s",
                (lifecycle_revision, authority.account_id),
            )
            conn.execute(
                "INSERT INTO accounts.lifecycle_request(id,account_id,revision,action,"
                "policy_ref,manifest_revision,manifest,disposition,reason_key) "
                "VALUES(%s,%s,%s,%s,%s,'owner-effect-test',%s,'pending','pending')",
                (
                    request,
                    authority.account_id,
                    lifecycle_revision,
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
            account_id=authority.account_id,
            lifecycle_revision=lifecycle_revision,
            participant="TopicsDigests",
            scope="live_records",
            generation=1,
            action=action,
            policy_ref=SYNTHETIC_POLICY.reference,
            manifest_revision="owner-effect-test",
        )

    result = participant.apply(ticket("withdraw"))
    assert result["evidenceRef"] and result["disposition"] == "complete"
    with connect("topics") as conn:
        status = conn.execute(
            "SELECT status FROM topics.followed_topic WHERE id=%s", (topic_id,)
        ).fetchone()["status"]
        discarded = conn.execute(
            "SELECT state FROM topics.digest_run WHERE id=%s", (queued["id"],)
        ).fetchone()["state"]
    assert status == "unsubscribed" and discarded == "discarded"
    # The erase disposition removes every digest fact for the account.
    erased = participant.apply(ticket("erase"))
    assert erased["disposition"] == "complete"
    with connect("topics") as conn:
        remaining = conn.execute(
            "SELECT count(*) AS n FROM topics.followed_topic WHERE account_id=%s",
            (authority.account_id,),
        ).fetchone()["n"]
    assert remaining == 0
