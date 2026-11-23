"""Business-flow helpers over the real realm, shared by
`component/test_topics_delivery_outcomes.py`, `component/test_topics_scheduler.py` and
`component/test_topics_withdraw_and_erase.py` (plan Step 35, decision L3-1), moved
unchanged from `test_topics_logic.py`. The three names keep the place in the collection
order that file had, with the lifecycle participant's withdraw-and-erase test last.

`quiet_realm_rows` is the body of the autouse fixture each of those files declares:
earlier runs of the suite leave active topics and queued runs behind, so every test
starts with only the topic it creates in the due page."""

import datetime as dt
from uuid import uuid4

from backend.modules.accounts.integrations.digest_email import DigestMailResult
from backend.modules.topics.delivery import DigestDelivery
from backend.modules.topics.preparation import DigestPreparation
from backend.modules.topics.scheduler import TopicsScheduler
from backend.modules.topics.service import TopicsService

W1 = (dt.date(2026, 1, 1), dt.date(2026, 1, 7))
W2 = (dt.date(2026, 1, 8), dt.date(2026, 1, 14))
W3 = (dt.date(2026, 1, 15), dt.date(2026, 1, 21))
ITEM = {
    "versionId": "v-c1",
    "paperId": "p-c1",
    "title": "Component Paper",
    "publishedOn": "2026-01-03",
}


class RefusingMail:
    path_kind = "local-sink"

    async def send(self, email, presentation, request_key):
        return DigestMailResult("refused")


class DetailedRefusalMail:
    """Returns one prepared refusal result; never touches a network."""

    path_kind = "local-sink"

    def __init__(self, result):
        self.result = result

    async def send(self, email, presentation, request_key):
        return self.result


class UnobservedMail:
    path_kind = "local-sink"

    async def send(self, email, presentation, request_key):
        raise TimeoutError("transport cut mid-send")


def quiet_realm_rows(connect):
    # The fixtures module owns the fixture-resolve topic (memberA's browser
    # fixture); component tests quiet everything except that shared fixture.
    with connect("topics") as conn:
        conn.execute(
            "UPDATE topics.followed_topic SET status='unsubscribed',updated_at="
            "clock_timestamp() WHERE status='active' "
            "AND topic_key <> 'fixture-resolve-topic'"
        )
        conn.execute(
            "UPDATE topics.digest_run SET state='discarded',updated_at=clock_timestamp() "
            "WHERE state='prepared' AND topic_id NOT IN "
            "(SELECT id FROM topics.followed_topic WHERE topic_key='fixture-resolve-topic')"
        )
        # Stale unknown outcomes from earlier suite runs would saturate the
        # reconciliation page: close them through the legal unknown->failed
        # transition and record the reconciliation on the outcome row.
        conn.execute(
            "UPDATE topics.digest_run SET state='failed',updated_at=clock_timestamp() "
            "WHERE state='unknown' AND topic_id NOT IN "
            "(SELECT id FROM topics.followed_topic WHERE topic_key='fixture-resolve-topic')"
        )
        conn.execute(
            "UPDATE topics.delivery_outcome o SET reconciled_state='failed',reconciled_at="
            "clock_timestamp() FROM topics.digest_run r WHERE o.run_id=r.id "
            "AND r.state='failed' AND o.observed_state='unknown' "
            "AND o.reconciled_state IS NULL"
        )


def build(transactions, mail=None):
    preparation = DigestPreparation(transactions, None)
    delivery = DigestDelivery(transactions, None, mail=mail)
    scheduler = TopicsScheduler(transactions, preparation, delivery)
    scheduler._now = lambda: dt.datetime.combine(
        dt.datetime.now(dt.UTC).date() + dt.timedelta(days=1), dt.time(12), tzinfo=dt.UTC
    )
    return TopicsService(transactions), scheduler, delivery


def follow_topic(service, authority, base="component-topic"):
    key = f"{base}-{uuid4().hex[:8]}"
    topic_id = service.follow(authority, key, "Component Topic")["topicId"]
    return key, topic_id


def revision_of(connect, topic_id):
    with connect("topics") as conn:
        return conn.execute(
            "SELECT revision FROM topics.digest_settings WHERE topic_id=%s", (topic_id,)
        ).fetchone()["revision"]


def make_due(connect, topic_id):
    """Move the topic's delivery time to midnight so it is due at any hour."""
    with connect("topics") as conn:
        conn.execute(
            "UPDATE topics.digest_settings SET delivery_time_local=%s,revision=revision+1 "
            "WHERE topic_id=%s",
            (dt.time(0, 0), topic_id),
        )


def run_row(connect, run_id):
    with connect("topics") as conn:
        return conn.execute(
            "SELECT r.state,o.observed_state,o.failure_reason FROM topics.digest_run r "
            "LEFT JOIN topics.delivery_outcome o ON o.run_id=r.id WHERE r.id=%s",
            (run_id,),
        ).fetchone()


def watermark_count(connect, topic_id):
    with connect("topics") as conn:
        return conn.execute(
            "SELECT count(*) AS n FROM topics.topic_delivery_watermark WHERE topic_id=%s",
            (topic_id,),
        ).fetchone()["n"]


def watermark_ids(connect, topic_id):
    with connect("topics") as conn:
        return {
            row["content_id"]
            for row in conn.execute(
                "SELECT content_id FROM topics.topic_delivery_watermark WHERE topic_id=%s",
                (topic_id,),
            ).fetchall()
        }


def seed_corpus(connect, rows):
    with connect("corpus") as conn:
        for version_id, paper_id, published, eligible in rows:
            conn.execute(
                "INSERT INTO corpus.paper(id,title,authors,metadata,published_on,withdrawn) "
                "VALUES(%s,'Synthetic Paper','[]','{}',%s,false) ON CONFLICT (id) DO UPDATE "
                "SET published_on=excluded.published_on,withdrawn=false",
                (paper_id, published),
            )
            conn.execute(
                "INSERT INTO corpus.version(id,paper_id,source_url,source_hash,version_label,"
                "private_path,eligible,purpose,provenance,content) VALUES(%s,%s,'local://x',"
                "repeat('a',64),'v1','synthetic',%s,'local-research','{}','{}') "
                "ON CONFLICT (id) DO UPDATE SET eligible=excluded.eligible",
                (version_id, paper_id, eligible),
            )
