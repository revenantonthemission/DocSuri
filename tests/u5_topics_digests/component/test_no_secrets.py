"""Step 20 (e): U5 holds no key material; the provider key comes from the process
environment only, read when the real composition is assembled.

U5's configuration (its policy and capability records), the operator's activation
record and every row the topics store holds are checked for secret-bearing fields and,
after a real-path send through a recording client, for the provider key, a bearer
header and the raw cancellation capability. A source scan then shows that only the
real composition reads the provider variables, and the assembled host is shown to take
its key from the environment once, at assembly, with no other source to fall back on.
The recording client sends nothing; this is contract evidence, not delivery.
"""

import asyncio
import dataclasses
import datetime as dt
import hashlib
import json
import re
from types import SimpleNamespace
from uuid import uuid4

import pytest
from backend.modules.topics.repository import TopicsRepository
from backend.modules.topics.unsubscribe import PREFIX
from backend.u5_host import topics_contribution
from backend.u5_policy import REAL_DEMONSTRATION_TOPICS, SYNTHETIC_TOPICS, TopicsPolicy
from backend.u5_real_delivery import (
    FIELDS,
    RealDeliveryActivation,
    RealDeliveryRefused,
    assemble_u5_real,
    parse_activation,
    real_mail,
    real_topics_factory,
)
from psycopg import sql

from tests.u5_topics_digests.real_send import (
    ENVIRON,
    FAKE_KEY,
    PUBLIC,
    RecordingClient,
    activation_value,
    real_path,
    recipient_of,
    send,
)
from tests.u5_topics_digests.source_scan import environment_reads, production_modules, relative

SECRET_NAME = re.compile(
    r"secret|passw|credential|api_?key|apikey|auth|bearer|token|private_key|signing",
    re.IGNORECASE,
)
# The one stored column whose name matches, and what it holds.
NOT_KEY_MATERIAL = {("email_unsubscribe", "token_hash")}


def secret_names(names):
    return {name for name in names if SECRET_NAME.search(name)}


def test_configuration_and_activation_record_carry_no_secret_field(
    transactions, realm, authority
):
    assert secret_names(field.name for field in dataclasses.fields(TopicsPolicy)) == set()
    for policy in (SYNTHETIC_TOPICS, REAL_DEMONSTRATION_TOPICS):
        assert secret_names(dataclasses.asdict(policy)) == set()
    assert secret_names(FIELDS) == set()
    assert secret_names(field.name for field in dataclasses.fields(RealDeliveryActivation)) == set()
    value = activation_value(realm, recipient_of(transactions, authority.account_id))
    activation = parse_activation(value, realm)
    # A record carrying a credential, under any name, is refused rather than read.
    for field in ("apiKey", "resendApiKey", "RESEND_API_KEY", "token", "secret", "password"):
        with pytest.raises(RealDeliveryRefused) as refused:
            parse_activation(dict(value, **{field: FAKE_KEY}), realm)
        assert FAKE_KEY not in str(refused.value)
    # Both compositions' capability records, the real one built with a key in hand.
    mail = real_mail(activation, ENVIRON, client_factory=RecordingClient())
    for contribution in (
        topics_contribution(transactions, SimpleNamespace(), None, None),
        real_topics_factory(activation, mail)(transactions, SimpleNamespace(), None, None),
    ):
        [record] = contribution["capabilities"]
        assert secret_names([*record, *record["policy"]]) == set()
        assert FAKE_KEY not in json.dumps(record)
    assert FAKE_KEY not in json.dumps(dataclasses.asdict(activation), default=str)


def test_the_topics_store_holds_no_key_material_after_a_real_send(
    transactions, realm, authority, connect
):
    repository = TopicsRepository(transactions)
    topic = repository.follow(authority, f"u5-custody-{uuid4().hex[:10]}", "Key custody")
    run, _ = repository.prepare_run(
        topic["topic"]["id"],
        dt.date(2025, 7, 1),
        dt.date(2025, 7, 7),
        1,
        [{"title": "Key custody", "publishedOn": "2025-07-02"}],
    )
    path = real_path(transactions, realm, recipient_of(transactions, authority.account_id))
    assert send(transactions, path, run, authority.account_id)["state"] == "sent"
    [request] = path.client.requests
    # The key went into the provider request and nowhere else.
    assert request["headers"]["Authorization"] == f"Bearer {FAKE_KEY}"
    url = request["json"]["headers"]["List-Unsubscribe"].removeprefix("<").removesuffix(">")
    token = url.removeprefix(PUBLIC + PREFIX)
    assert len(token) == 43
    needles = {"the provider key": FAKE_KEY, "a bearer header": "Bearer", "the capability": token}
    with connect("topics") as conn:
        tables = [
            row["table_name"]
            for row in conn.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema='topics' AND table_type='BASE TABLE' ORDER BY 1"
            ).fetchall()
        ]
        assert {"digest_run", "send_log_entry", "delivery_outcome", "email_unsubscribe"} <= set(
            tables
        )
        columns = conn.execute(
            "SELECT table_name,column_name FROM information_schema.columns "
            "WHERE table_schema='topics'"
        ).fetchall()
        flagged = {
            (row["table_name"], row["column_name"])
            for row in columns
            if SECRET_NAME.search(row["column_name"])
        }
        assert flagged == NOT_KEY_MATERIAL
        for table in tables:
            for label, needle in needles.items():
                found = conn.execute(
                    sql.SQL("SELECT count(*) AS n FROM topics.{} t WHERE strpos(t::text,%s)>0").format(
                        sql.Identifier(table)
                    ),
                    (needle,),
                ).fetchone()["n"]
                # Labels only: a capability never appears in an assertion message.
                assert found == 0, f"{label} is stored in topics.{table}"
        # The capability is kept as its digest, bound to this run.
        stored = conn.execute(
            "SELECT run_id,token_hash FROM topics.email_unsubscribe WHERE run_id=%s",
            (run["id"],),
        ).fetchall()
    assert [row["token_hash"] for row in stored] == [hashlib.sha256(token.encode()).hexdigest()]


def test_the_provider_key_is_read_from_the_environment_once_at_assembly(
    transactions, realm, authority, monkeypatch
):
    recipient = recipient_of(transactions, authority.account_id)
    activation = parse_activation(activation_value(realm, recipient), realm)
    client = RecordingClient()
    monkeypatch.setenv("EMAIL_PROVIDER", "resend")
    monkeypatch.setenv("RESEND_API_KEY", FAKE_KEY)
    app = assemble_u5_real(realm, activation, client_factory=client)
    try:
        mail = app.state.topics_scheduler.delivery.mail
        # Removing the variable after assembly does not reach the bound adapter.
        monkeypatch.delenv("RESEND_API_KEY")
        result = asyncio.run(
            mail.send(
                recipient,
                {"subject": "S", "text": "T", "html": "<p>H</p>"},
                uuid4(),
                unsubscribe_url=PUBLIC + PREFIX + "k" * 43,
            )
        )
        assert result.state == "accepted"
        [request] = client.requests
        assert request["headers"]["Authorization"] == f"Bearer {FAKE_KEY}"
    finally:
        app.state.transactions.close()
    # Without the variable there is no other source: assembly refuses, without the key.
    with pytest.raises(RealDeliveryRefused) as refused:
        assemble_u5_real(realm, activation, client_factory=client)
    assert "RESEND_API_KEY" in str(refused.value) and FAKE_KEY not in str(refused.value)
    assert len(client.requests) == 1


def test_only_the_real_composition_reads_the_provider_environment():
    reads = {
        (relative(path), scope, read)
        for path in production_modules()
        for scope, read in environment_reads(path.read_text(), str(path))
    }
    assert reads == {
        ("backend/u5_real_delivery.py", "assemble_u5_real", "os.environ"),
        ("backend/u5_real_delivery.py", "provider_configuration", "EMAIL_PROVIDER"),
        ("backend/u5_real_delivery.py", "provider_configuration", "RESEND_API_KEY"),
    }


def test_the_environment_scan_finds_each_planted_read():
    planted = (
        "import os\n"
        "from os import getenv\n"
        "KEY = os.environ.get('RESEND_API_KEY')\n"
        "def build(environ):\n"
        "    return os.getenv('X'), environ['EMAIL_PROVIDER']\n"
        "def note():\n"
        "    return 'RESEND_API_KEY must be set'\n"
    )
    assert sorted(environment_reads(planted)) == sorted(
        [
            ("<module>", "from os import getenv"),
            ("<module>", "os.environ"),
            ("<module>", "RESEND_API_KEY"),
            ("build", "os.getenv"),
            ("build", "EMAIL_PROVIDER"),
        ]
    )
