"""U5's seams take U5's built defaults (U8 plan Step 22, "U8's lines out of U5's files").

U5's files hold only seams whose default is U5's built behaviour: the scheduler's three
send hooks, `begin_send`'s `admission`, the shared Resend client and the production
profile's mail root. U8's live parts live in U8's own modules. Also here: the guards of
U8's own parts that need no realm (the live policy, the moved verifier-key read and the
held digest adapter).
"""

from __future__ import annotations

import asyncio
import dataclasses
import os
import secrets
from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.modules.accounts.integrations import digest_email
from backend.modules.accounts.integrations.digest_email import DigestMailResult, ResendClient
from backend.modules.accounts.integrations.u8_digest_mail import (
    PROVIDER_HELD,
    HeldDigestMail,
    ProviderHeldResult,
)
from backend.modules.accounts.services.guarded_entry import GuardedEntryService
from backend.modules.accounts.u8_verifier_key import verifier_key_revision
from backend.modules.topics.errors import TopicsError
from backend.modules.topics.repository import TopicsRepository
from backend.modules.topics.scheduler import TopicsScheduler
from backend.u5_policy import REAL_DEMONSTRATION_TOPICS
from backend.u8_topics import PRODUCTION_LIVE_TOPICS, LiveTopicsPolicy

MAINTAINER = "maintainer@fixture.example.com"


# --- U5's built scheduler over a real TopicsRepository (Step 98(d), L1-56) ----------------
#
# A module-scoped production stand-in, whose topics store holds no real send-log row, so
# U5's allocation of 1 counts nothing spent. Each test prepares a run of its own, for an
# account of its own; call-through spies on `prepared_runs` and `begin_send` record their
# arguments and return the real answers.


@pytest.fixture(scope="module")
def standin(realm):
    from tests.u8_service_operations_integration import host_flows

    with host_flows.production_stand_in(realm) as value:
        yield value


class RecordedDelivery:
    """The real path for one recipient; `attempt` records the run and sends nothing."""

    def __init__(self, recipient: str):
        self.recipient, self.attempts = recipient, []

    def recipient_scope(self):
        return self.recipient

    def path_kind(self):
        return "real"

    def attempt(self, sending, run):
        self.attempts.append((sending["id"], run["id"]))
        return None


def prepared_scheduler(standin, monkeypatch, suffix: str):
    """U5's built scheduler over the stand-in's real repository, one run prepared for an
    account of the test's own, and the call-through spies' record."""
    import datetime as dt

    from tests.u8_service_operations_integration import host_flows

    authority = host_flows.standin_account(standin, suffix, grant=False)
    repository = TopicsRepository(standin.transactions)
    recipient = repository.digest_recipient(authority.account_id)["email"]
    topic = repository.follow(authority, "seam-" + uuid4().hex[:12], "U5 seam")["topic"]["id"]
    start = dt.date(2026, 10, 1)
    run, _ = repository.prepare_run(topic, start, start + dt.timedelta(days=6), 1,
                                    [{"title": "합성 논문", "publishedOn": start.isoformat()}])
    delivery = RecordedDelivery(recipient)
    scheduler = TopicsScheduler(standin.transactions, None, delivery,
                                policy=REAL_DEMONSTRATION_TOPICS)
    calls = []
    prepared_runs = scheduler.repository.prepared_runs
    begin_send = scheduler.repository.begin_send

    def recorded_prepared_runs(limit=10, *, recipient=None):
        calls.append(("prepared_runs", limit, recipient))
        return prepared_runs(limit, recipient=recipient)

    def recorded_begin_send(run_id, path_kind, **options):
        calls.append(("begin_send", run_id, path_kind, options))
        return begin_send(run_id, path_kind, **options)

    monkeypatch.setattr(scheduler.repository, "prepared_runs", recorded_prepared_runs)
    monkeypatch.setattr(scheduler.repository, "begin_send", recorded_begin_send)
    return SimpleNamespace(scheduler=scheduler, run=run, recipient=recipient, calls=calls,
                           delivery=delivery, repository=repository)


def run_state(repository, run_id) -> dict:
    return repository.system(lambda conn: conn.execute(
        "SELECT r.state,(SELECT count(*) FROM topics.send_log_entry l WHERE l.run_id=r.id) "
        "AS logs FROM topics.digest_run r WHERE r.id=%s", (run_id,)).fetchone())


def test_u5s_scheduler_asks_for_its_built_queue_and_begins_with_its_built_arguments(
        standin, monkeypatch):
    rig = prepared_scheduler(standin, monkeypatch, "u5-seam-begin")
    assert rig.scheduler._may_begin_send() is True
    rig.scheduler._send_prepared({"sent": 0, "failed": 0, "unknown": 0})
    assert rig.calls == [
        ("prepared_runs", 6, rig.recipient),
        ("begin_send", rig.run["id"], "real",
         {"real_send_limit": 1, "evidence_retention_days": 30}),
    ]
    # No admission is ever passed by U5's own scheduler.
    assert all("admission" not in call[-1] for call in rig.calls if call[0] == "begin_send")
    # The real answer: the run in `sending` with its send-log row, handed to the delivery.
    assert run_state(rig.repository, rig.run["id"]) == {"state": "sending", "logs": 1}
    assert rig.delivery.attempts == [(rig.run["id"], rig.run["id"])]


def test_u5s_send_step_stops_when_a_send_may_not_begin(standin, monkeypatch):
    """The hook is read before each start: a scheduler that says no begins nothing."""
    rig = prepared_scheduler(standin, monkeypatch, "u5-seam-stop")
    rig.scheduler._may_begin_send = lambda: False
    rig.scheduler._send_prepared({})
    assert [call[0] for call in rig.calls] == ["prepared_runs"]
    assert run_state(rig.repository, rig.run["id"]) == {"state": "prepared", "logs": 0}
    assert rig.delivery.attempts == []


def unconnected_repository():
    """A TopicsRepository whose transaction hands the work no connection: U5's allocation
    check runs before any statement, so it refuses without a database."""
    return TopicsRepository(SimpleNamespace(run=lambda owner, work: work(None)))


def test_begin_send_refuses_an_allocation_of_0_without_an_admission_and_101_with_one():
    repository = unconnected_repository()
    with pytest.raises(TopicsError) as without:
        repository.begin_send(uuid4(), "real", real_send_limit=0, evidence_retention_days=30)
    assert (without.value.code, without.value.current) == (
        "INVALID_ARGUMENT", {"field": "realSendAllocation"})
    for limit, path in ((101, "real"), (1, "real"), (0, "local-sink")):
        with pytest.raises(TopicsError) as given:
            repository.begin_send(uuid4(), path, real_send_limit=limit,
                                  evidence_retention_days=30 if path == "real" else None,
                                  admission=lambda run: True)
        assert given.value.current == {"field": "realSendAllocation"}


def test_guarded_entry_builds_the_built_mail_root_for_a_non_production_profile(transactions):
    entry = GuardedEntryService(transactions)
    assert not getattr(transactions.profile, "is_production", False)
    assert entry.mail.root == transactions.profile.root / "verification-mail"


def test_u5s_digest_result_still_refuses_provider_held():
    with pytest.raises(ValueError, match="unsupported refusal reason"):
        DigestMailResult("refused", refusal_reason=PROVIDER_HELD)
    held = ProviderHeldResult("refused", refusal_reason=PROVIDER_HELD)
    assert (held.state, held.failure_reason) == ("refused", PROVIDER_HELD)
    for wrong in ({"state": "accepted"}, {"refusal_reason": "recipient-not-permitted"},
                  {"provider_status": 422, "provider_error": "validation_error"}):
        with pytest.raises(ValueError):
            ProviderHeldResult(**{"state": "refused", "refusal_reason": PROVIDER_HELD, **wrong})


class Factory:
    def __init__(self):
        self.options, self.posts = [], []

    def __call__(self, **options):
        self.options.append(options)
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, endpoint, *, headers, json):
        self.posts.append((endpoint, headers["Idempotency-Key"], json))
        return SimpleNamespace(status_code=200)


def test_the_shared_resend_client_uses_an_injected_factory_whenever_one_is_given():
    factory = Factory()
    client = ResendClient("re_" + uuid4().hex, client_factory=factory)  # per run (L1-36)
    answer = asyncio.run(client.post({"to": [MAINTAINER]}, "key-1", timeout=2.5))
    assert answer.status_code == 200
    assert factory.options == [{"timeout": 2.5}]
    assert factory.posts == [(digest_email.RESEND_ENDPOINT, "key-1", {"to": [MAINTAINER]})]
    # Without a factory it builds the network client in the one guarded place.
    with pytest.raises(RuntimeError, match="network transport"):
        asyncio.run(ResendClient("re_" + uuid4().hex).post({}, "key-2", timeout=1.0))
    with pytest.raises(ValueError):
        ResendClient("")


# --- U8's own parts that need no realm -----------------------------------------------------


def test_the_live_policy_refuses_any_allocation_but_the_integer_0():
    assert isinstance(PRODUCTION_LIVE_TOPICS, LiveTopicsPolicy)
    assert PRODUCTION_LIVE_TOPICS.real_send_limit == 0
    for options in ({"real_send_limit": False}, {"real_send_limit": 1},
                    {"synthetic_only": True}, {"real_evidence_retention_days": 31},
                    {"sends_per_pass": 2}):
        with pytest.raises(ValueError):
            dataclasses.replace(PRODUCTION_LIVE_TOPICS, **options)


def key_file(folder, *, mode=0o600, content=None):
    # The key is generated per run; a test that needs a short key passes its own length.
    content = secrets.token_bytes(32) if content is None else content
    path = folder / "account-verifier.key"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(content)
    os.chmod(path, mode)
    return path


def test_the_moved_key_read_applies_the_constructors_custody_checks(tmp_path, monkeypatch):
    good = key_file(tmp_path)
    assert len(verifier_key_revision(good)) == 32
    assert verifier_key_revision(tmp_path / "missing.key") == "absent"
    # Mode.
    loose = tmp_path / "loose"
    loose.mkdir()
    with pytest.raises(ValueError, match="custody"):
        verifier_key_revision(key_file(loose, mode=0o640))
    # One link only.
    linked = tmp_path / "linked"
    linked.mkdir()
    first = key_file(linked)
    os.link(first, linked / "second.key")
    with pytest.raises(ValueError, match="custody"):
        verifier_key_revision(first)
    # Never a symlink.
    pointer = tmp_path / "pointer.key"
    pointer.symlink_to(good)
    with pytest.raises(ValueError, match="custody"):
        verifier_key_revision(pointer)
    # The owner.
    real = os.getuid()
    monkeypatch.setattr(os, "getuid", lambda: real + 1)
    with pytest.raises(ValueError, match="custody"):
        verifier_key_revision(good)
    monkeypatch.undo()
    # An incomplete key.
    short = tmp_path / "short"
    short.mkdir()
    with pytest.raises(ValueError, match="incomplete"):
        verifier_key_revision(key_file(short, content=secrets.token_bytes(31)))


def test_the_held_digest_adapter_permits_nobody_takes_no_preview_and_refuses_every_send():
    gate = SimpleNamespace(mode="live", state=lambda provider: "active")
    held = HeldDigestMail(permitted_recipient=MAINTAINER, gate=gate)
    assert held.path_kind == "real" and held.gate is gate
    assert held.permitted_recipient == MAINTAINER
    assert not held.permits(MAINTAINER) and not held.bounds_lifted()
    with pytest.raises(ValueError, match="no first effect"):
        held.preview_content(MAINTAINER, {}, uuid4())
    for recipient in (MAINTAINER, "other@fixture.example.com"):
        answer = asyncio.run(held.send(recipient, {}, uuid4()))
        assert (answer.state, answer.refusal_reason) == ("refused", PROVIDER_HELD)
    for options in ({"permitted_recipient": MAINTAINER, "gate": None},
                    {"permitted_recipient": "", "gate": gate}):
        with pytest.raises(ValueError):
            HeldDigestMail(**options)
