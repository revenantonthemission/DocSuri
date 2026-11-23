"""Step 20 (a) and (b): a send submits exactly the run's stored presentation.

A run is prepared from eligible papers this module seeds; its presentation is rendered
from its owner's own settings and stored on the owner's run row. The send then goes
through the real delivery step and the real Resend adapter, whose HTTP client only
records (tests/u5_topics_digests/real_send.py). The submitted message is compared
whole: the stored subject, text and html, the recipient, the two List-Unsubscribe
headers and nothing else, so a changed subject or an added field (cc, bcc, reply-to)
fails. The operator's preview of the same run shows the same message, and the email
subject follows each owner's language.
"""

import datetime as dt
import hashlib
import html
import json
from uuid import UUID, uuid4

from backend.modules.personalization.guarded_service import (
    ASSISTANCE_DEFAULTS,
    GuardedSettingsService,
)
from backend.modules.topics.preparation import DigestPreparation
from backend.modules.topics.presentation import render_presentation
from backend.modules.topics.repository import TopicsRepository
from backend.modules.topics.service import TopicsService
from backend.modules.topics.unsubscribe import PREFIX
from backend.u5_real_delivery import REDACTED_TOKEN, message_preview

from tests.u5_topics_digests.real_send import (
    FAKE_KEY,
    PUBLIC,
    SENDER,
    real_path,
    recipient_of,
    send,
)

# A window no other U5 check seeds, so its selection is exactly these two papers.
WINDOW = (dt.date(2025, 6, 1), dt.date(2025, 6, 7))
PAPERS = (
    ("v-u5-message-1", "p-u5-message-1", dt.date(2025, 6, 2), "Spectral graph sparsification"),
    ("v-u5-message-2", "p-u5-message-2", dt.date(2025, 6, 4), "Expander decompositions"),
)
TOPIC_NAME = "Graph sparsification"
MESSAGE_FIELDS = ["from", "headers", "html", "subject", "text", "to"]


def seed_papers(connect):
    with connect("corpus") as conn:
        for version_id, paper_id, published, title in PAPERS:
            conn.execute(
                "INSERT INTO corpus.paper(id,title,authors,metadata,published_on,withdrawn) "
                "VALUES(%s,%s,'[]','{}',%s,false) ON CONFLICT (id) DO UPDATE "
                "SET title=excluded.title,published_on=excluded.published_on,withdrawn=false",
                (paper_id, title, published),
            )
            conn.execute(
                "INSERT INTO corpus.version(id,paper_id,source_url,source_hash,version_label,"
                "private_path,eligible,purpose,provenance,content) VALUES(%s,%s,'local://x',"
                "repeat('a',64),'v1','synthetic',true,'local-research','{}','{}') "
                "ON CONFLICT (id) DO UPDATE SET eligible=true",
                (version_id, paper_id),
            )


def configure(transactions, authority, language):
    settings = GuardedSettingsService(transactions)
    state = settings.read(authority)
    settings.update(
        authority,
        uuid4(),
        state["revision"],
        {"timeZone": "UTC", "assistanceDefaults": dict(ASSISTANCE_DEFAULTS, languageId=language)},
    )


def prepared_run(transactions, authority):
    """Follow a fresh topic and prepare WINDOW from the eligible corpus."""
    service = TopicsService(transactions)
    topic = service.follow(authority, f"u5-message-{uuid4().hex[:10]}", TOPIC_NAME)["topicId"]
    revision = service.read_topic(authority, topic)["settings"]["revision"]
    run, adopted = DigestPreparation(transactions, None).prepare(UUID(topic), WINDOW, revision)
    assert adopted is False and run["state"] == "prepared"
    return run


def stored(transactions, run_id):
    return TopicsRepository(transactions).system(
        lambda conn: conn.execute(
            "SELECT * FROM topics.digest_run WHERE id=%s", (run_id,)
        ).fetchone()
    )


def test_the_submitted_message_is_exactly_the_stored_presentation(
    transactions, realm, authority, connect
):
    seed_papers(connect)
    configure(transactions, authority, "en")
    run = prepared_run(transactions, authority)
    before = stored(transactions, run["id"])
    presentation = before["presentation"]
    # The presentation holds only the window's selected papers, rendered from the
    # owner's own settings as snapshotted on the owner's run row.
    assert [item["versionId"] for item in before["digest_content"]] == [p[0] for p in PAPERS]
    snapshot = before["preference_snapshot"]
    assert (snapshot["languageId"], snapshot["presentationLevelId"], snapshot["timeZone"]) == (
        "en",
        "standard",
        "UTC",
    )
    assert presentation == render_presentation(TOPIC_NAME, before["digest_content"], snapshot)

    recipient = recipient_of(transactions, authority.account_id)
    path = real_path(transactions, realm, recipient)
    # The operator's preview of the prepared run, before anything is sent.
    preview = message_preview(before, path.activation)
    terminal = send(transactions, path, run, authority.account_id)
    assert terminal["state"] == "sent"

    [request] = path.client.requests
    assert request["url"] == "https://api.resend.com/emails"
    assert request["headers"] == {
        "Authorization": f"Bearer {FAKE_KEY}",
        "Idempotency-Key": str(before["request_key"]),
    }
    message = request["json"]
    url = message["headers"]["List-Unsubscribe"].removeprefix("<").removesuffix(">")
    token = url.removeprefix(PUBLIC + PREFIX)
    # The link is the capability issued for this run; only its digest is stored.
    assert len(token) == 43 and url == PUBLIC + PREFIX + token
    bound = TopicsRepository(transactions).system(
        lambda conn: conn.execute(
            "SELECT run_id FROM topics.email_unsubscribe WHERE token_hash=%s",
            (hashlib.sha256(token.encode()).hexdigest(),),
        ).fetchone()
    )
    assert bound is not None and bound["run_id"] == run["id"]
    link = f'<p><a href="{html.escape(url, quote=True)}">Unsubscribe / 구독 해지</a></p>'
    assert presentation["html"].count("</body>") == 1
    assert message == {
        "from": SENDER,
        "to": [recipient],
        "subject": presentation["subject"],
        "text": presentation["text"] + f"\n\nUnsubscribe: {url}",
        "html": presentation["html"].replace("</body>", link + "</body>"),
        "headers": {
            "List-Unsubscribe": f"<{url}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        },
    }
    # Spelled out: no other field is submitted (no cc, bcc, reply-to or attachment).
    assert sorted(message) == MESSAGE_FIELDS
    # The preview showed this exact message, its single-use token redacted.
    assert json.loads(json.dumps(preview["message"]).replace(REDACTED_TOKEN, token)) == message
    # Sending neither rewrote nor copied the stored presentation.
    after = stored(transactions, run["id"])
    assert after["presentation"] == presentation and after["state"] == "sent"


def test_the_email_subject_follows_each_owners_language(
    transactions, realm, authority, authority_b, connect
):
    seed_papers(connect)
    count = len(PAPERS)
    expected = {
        "en": f"[DocSuri] '{TOPIC_NAME}' topic digest ({count})",
        "ko": f"[DocSuri] '{TOPIC_NAME}' 주제 다이제스트 ({count})",
    }
    opening = {"en": f"'{TOPIC_NAME}' topic digest", "ko": f"'{TOPIC_NAME}' 주제 다이제스트"}
    for owner, language in ((authority, "en"), (authority_b, "ko")):
        configure(transactions, owner, language)
        run = prepared_run(transactions, owner)
        path = real_path(transactions, realm, recipient_of(transactions, owner.account_id))
        assert send(transactions, path, run, owner.account_id)["state"] == "sent"
        [request] = path.client.requests
        message = request["json"]
        assert message["subject"] == expected[language]
        assert message["text"].split("\n", 1)[0] == opening[language]
        row = stored(transactions, run["id"])
        assert row["presentation"]["subject"] == expected[language]
        assert row["presentation"]["languageId"] == row["preference_snapshot"]["languageId"]
        assert row["preference_snapshot"]["languageId"] == language
