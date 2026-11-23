"""First effects and the live bounds (U8 plan Step 22; BR7.3, BR7.6, BR9.5, BR9.7, D12).

In live mode with admission maintainer-only each outward provider is held. The owning
module holds its first effect, addressed to the maintainer, and records its exact content
as a preview: U5's scheduler for the first digest, and U8's `FirstExportPreviews` pass for
the first export, from the effect's bound content. Your decision on that digest, appended
to the ledger as `platform.decision.record` leaves it, activates the provider; a decision
on any other digest is refused. The effect then goes, before anything else. An abort
clears every approval, and U5's and U6's bounds lift only once their provider is active
in live mode.

Everything runs on the composed realm's own stores, through the owners' real services,
with ServiceOperations' ledger in a private folder; Resend and Notion are fakes under
the real adapters.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
import pytest

from backend.modules.accounts.integrations.account_mail import (
    AccountMessage,
    ResendAccountMail,
)
from backend.modules.accounts.integrations.u8_digest_mail import GatedResendDigestMail
from backend.modules.export import notion_session
from backend.modules.export.errors import ExportError
from backend.modules.export.notion_adapter import StoreContentPort
from backend.modules.operations.allowance import KIND, LedgerAllowance
from backend.modules.operations.errors import OperationsError
from backend.modules.operations.ledger import Ledger
from backend.modules.operations.producers import ProviderProducer
from backend.modules.operations.provider_activation import ActivationSettings, ProviderActivation
from backend.modules.topics.repository import TopicsRepository
from backend.u6_policy import production_live_export, real_activation_export
from backend.u8_outward import (
    FirstExportPreviews,
    _rolling_unsubscribe,
    export_policy,
    export_preview,
    topics_parts,
    topics_policy,
)
from backend.u8_policy import SYNTHETIC_OPERATIONS
from backend.u8_topics import (
    PRODUCTION_LIVE_TOPICS,
    PRODUCTION_REHEARSAL_TOPICS,
    begin_live_send,
    is_live,
)
from tests.u6_approved_export import lane_flows as lf
from tests.u8_service_operations_integration import cutover_flows as cf
from tests.u8_service_operations_integration.host_flows import (
    production_stand_in,
    standin_account,
)

ORIGIN = "https://127.0.0.1:18110"
FREE_TERMS = "notion-free:2026-10-01:" + "f" * 64
PROVIDERS = frozenset({"google", "orcid", "resend", "models", "notion"})
MAX_PASSES = 12


class Resend:
    """Resend's `/emails` over a fake transport: every accepted message, in order."""

    def __init__(self):
        self.posts = []

    def __call__(self, **options):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, endpoint, *, headers, json):
        self.posts.append(json["to"][0])
        return httpx.Response(200, json={"id": str(uuid4())})


@pytest.fixture
def operations_ledger(tmp_path, clock):
    folder = tmp_path / "operations-ledger"
    folder.mkdir(mode=0o700)
    value = Ledger.open(folder, clock=clock)
    yield value
    value.close()


@pytest.fixture
def activation(operations_ledger, clock, tmp_path):
    """ProviderActivation over the ledger for one maintainer, started in a chosen mode."""
    (tmp_path / "evidence").mkdir(mode=0o700)

    def start(mode: str, maintainer: UUID) -> ProviderActivation:
        settings = ActivationSettings(mode, maintainer, PROVIDERS,
                                      tmp_path / "evidence" / "previews")
        value = ProviderActivation(operations_ledger, settings, clock=clock)
        value.start()
        return value

    return start


def decide(ledger, clock, provider: str, digest: str) -> tuple[str, dict]:
    """Your decision on the subject `cutover decide` shows, as `platform.decision.record`
    leaves it in the ledger (Workflow 18): its approval id and its subject, for
    `approve` (`cutover_flows.provider_decision`, U8 plan Step 107(c)).

    Each test that approves first brings the ledger's CutoverRecord to `switching`
    (`cutover_flows.switching`, which moves the clock on by the soak's week) before its
    activation, its rig or its lane is built, so every token, preview and row is made on
    the moved clock and every decision follows the switch's check, as `approve` binds
    an approval to the current switch."""
    return cf.provider_decision(ledger, provider, now=clock(), preview_digest=digest)


# --- Digests (U5) ------------------------------------------------------------------------


def email_of(connect, authority) -> str:
    with connect("accounts") as conn:
        return conn.execute("SELECT email FROM accounts.account WHERE id=%s",
                            (authority.account_id,)).fetchone()["email"]


def email_of_run(rig, authority) -> str:
    return rig.repository.digest_recipient(authority.account_id)["email"]


class Digests:
    """U5's production parts for one policy, over the realm, with its own topics."""

    def __init__(self, transactions, connect, clock, gate, ledger, policy, maintainer, *,
                 allowance=None, resend=None):
        self.repository = TopicsRepository(transactions)
        self.resend = resend or Resend()
        self.maintainer = email_of(connect, maintainer)
        # The composition's account lookup (AccountAccess's `account_of`); the fixture
        # accounts' `.invalid` addresses are outside the wire's email format.
        accounts = {self.maintainer: maintainer.account_id}
        self.mail = GatedResendDigestMail(
            api_key="re_" + uuid4().hex,  # generated per run (L1-36)
            sender="digest@fixture.example.com",
            unsubscribe_url=ORIGIN, permitted_recipient=self.maintainer,
            client_factory=self.resend, gate=gate, recipients=gate,
            account_of=accounts.get,
        )
        self.allowance = allowance or LedgerAllowance(ledger, SYNTHETIC_OPERATIONS)
        unsubscribe = _rolling_unsubscribe()(transactions, origin=ORIGIN, clock=clock)
        # The entry stands in for AccountAccess's: by the plan's row "U2's controls in the
        # complete app", the settings router's personal controls derive their cursor key
        # from the entry's verifier, as the production entry gives it.
        entry = SimpleNamespace(verifier=lambda purpose, value: hashlib.sha256(
            f"{purpose}:{value}".encode()).hexdigest())
        self.parts = topics_parts(
            transactions, entry, None, None, policy=policy, mail=self.mail,
            unsubscribe=unsubscribe, activation=gate, allowance=self.allowance,
        )
        self.topics = []

    def prepared(self, authority) -> dict:
        topic = self.repository.follow(authority, "first-" + uuid4().hex[:12], "첫 효과")[
            "topic"]["id"]
        self.topics.append((authority, topic))
        start = dt.date(2026, 10, 1)
        run, _ = self.repository.prepare_run(
            topic, start, start + dt.timedelta(days=6), 1,
            [{"title": "합성 논문", "publishedOn": start.isoformat()}],
        )
        return run

    def content(self, run) -> bytes:
        facts = self.repository.system(lambda conn: conn.execute(
            "SELECT presentation,request_key,topic_id FROM topics.digest_run WHERE id=%s",
            (run["id"],)).fetchone())
        owner = self.repository.system(lambda conn: conn.execute(
            "SELECT account_id FROM topics.followed_topic WHERE id=%s",
            (facts["topic_id"],)).fetchone())["account_id"]
        email = self.repository.digest_recipient(owner)["email"]
        return self.mail.preview_content(email, facts["presentation"], facts["request_key"])

    def state(self, run) -> str:
        return self.repository.system(lambda conn: conn.execute(
            "SELECT state FROM topics.digest_run WHERE id=%s", (run["id"],)
        ).fetchone()["state"])

    def passes_until(self, condition) -> None:
        for _ in range(MAX_PASSES):
            self.parts["scheduler"].run_once()
            if condition():
                return
        raise AssertionError("the scheduler did not reach the expected state")

    def close(self) -> None:
        for authority, topic in self.topics:
            self.repository.unsubscribe(authority, topic)


@pytest.fixture
def digests(transactions, connect, clock, operations_ledger):
    opened = []

    def make(gate, policy, maintainer, **options):
        value = Digests(transactions, connect, clock, gate, operations_ledger, policy,
                        maintainer, **options)
        opened.append(value)
        return value

    yield make
    for value in opened:
        value.close()


def test_the_first_digest_is_held_with_its_preview_and_sent_first_on_your_decision(
    digests, activation, authority, authority_b, operations_ledger, clock,
):
    cf.switching(operations_ledger, clock)
    gate = activation("live", authority.account_id)
    rig = digests(gate, PRODUCTION_LIVE_TOPICS, authority)
    mine, theirs = rig.prepared(authority), rig.prepared(authority_b)
    rig.parts["scheduler"].run_once()
    # Held: nothing leaves, the runs stay prepared, and only your run is previewed.
    assert rig.resend.posts == [] and gate.state("resend") == "held"
    assert (rig.state(mine), rig.state(theirs)) == ("prepared", "prepared")
    digest = hashlib.sha256(rig.content(mine)).hexdigest()
    assert digest in gate.previews_of("resend")
    assert hashlib.sha256(rig.content(theirs)).hexdigest() not in gate.previews_of("resend")
    # A decision on another digest is refused and changes nothing.
    with pytest.raises(OperationsError):
        gate.approve("resend", *decide(operations_ledger, clock, "resend", "0" * 64))
    rig.parts["scheduler"].run_once()
    assert rig.resend.posts == [] and gate.approved_content("resend") is None
    # Your decision on that digest: the approved first effect goes before anything else.
    gate.approve("resend", *decide(operations_ledger, clock, "resend", digest))
    assert gate.approved_content("resend") == digest and gate.bounds_lifted("resend")
    rig.parts["scheduler"].run_once()
    assert rig.resend.posts[:1] == [rig.maintainer] and rig.state(mine) == "sent"
    # Then the bound has lifted: a subscriber who consented is served, through the allowance.
    rig.passes_until(lambda: rig.state(theirs) == "sent")
    assert email_of_run(rig, authority_b) in rig.resend.posts
    counts = rig.allowance.counts()
    assert counts["daily"] >= 2 and counts["daily"] == len(rig.resend.posts)


def test_an_abort_clears_the_approvals_and_the_next_switch_holds_again(
    digests, activation, authority, authority_b, operations_ledger, clock,
):
    cf.switching(operations_ledger, clock)
    gate = activation("live", authority.account_id)
    rig = digests(gate, PRODUCTION_LIVE_TOPICS, authority)
    mine = rig.prepared(authority)
    rig.parts["scheduler"].run_once()
    gate.approve("resend", *decide(operations_ledger, clock, "resend",
                                   hashlib.sha256(rig.content(mine)).hexdigest()))
    preview = gate.record_preview("notion", b'{"first":"export"}')
    gate.approve("notion", *decide(operations_ledger, clock, "notion", preview))
    # The abort: every outward and sign-in approval is cleared (BR9.5).
    gate.clear_approvals(mode="rehearsal")
    for provider in ("resend", "notion"):
        assert gate.approved_content(provider) is None and not gate.bounds_lifted(provider)
    # The live policy never sends outside live mode.
    later = rig.prepared(authority_b)
    rig.parts["scheduler"].run_once()
    assert rig.resend.posts == [] and rig.state(later) == "prepared"
    # The next switch: live again, each provider is held until a new decision.
    again = activation("live", authority.account_id)
    assert again.state("resend") == again.state("notion") == "held"
    assert again.approved_content("resend") is None


def test_u5s_bound_lifts_only_once_resend_is_active_in_live_mode(
    transactions, digests, activation, authority, authority_b,
):
    # Rehearsal: only your address is served; another subscriber's run never starts, and
    # the per-database 1–100 allocation still bounds every real attempt. The realm
    # persists across phases, so the allocation is the next one past those spent.
    rehearsal = activation("rehearsal", authority.account_id)
    repository = TopicsRepository(transactions)
    spent = repository.system(lambda conn: conn.execute(
        "SELECT count(*) AS n FROM topics.send_log_entry WHERE path_kind='real'"
    ).fetchone()["n"])
    ahead = len(repository.prepared_runs(50, recipient=repository.digest_recipient(
        authority.account_id)["email"]))
    limit = spent + ahead + 1  # every run of yours already queued, then this test's one
    if limit > 100:
        pytest.fail("the realm's real-send allocation is spent; a fresh realm is required")
    policy = dataclasses.replace(PRODUCTION_REHEARSAL_TOPICS, real_send_limit=limit)
    assert not is_live(policy) and PRODUCTION_REHEARSAL_TOPICS.real_send_limit == 100
    bounded = digests(rehearsal, policy, authority)
    mine, theirs = bounded.prepared(authority), bounded.prepared(authority_b)
    bounded.passes_until(lambda: bounded.state(mine) == "sent")
    assert bounded.state(theirs) == "prepared"
    assert set(bounded.resend.posts) == {bounded.maintainer}
    sent = len(bounded.resend.posts)
    again = bounded.prepared(authority)  # the allocation is spent: it stays prepared
    bounded.parts["scheduler"].run_once()
    assert bounded.state(again) == "prepared" and len(bounded.resend.posts) == sent
    assert bounded.parts["delivery"].recipient_scope() == bounded.maintainer
    bounded.close()
    # Live and held: nobody, the maintainer included, receives anything.
    live = activation("live", authority.account_id)
    lifted = digests(live, PRODUCTION_LIVE_TOPICS, authority)
    held = lifted.prepared(authority_b)
    lifted.parts["scheduler"].run_once()
    assert lifted.resend.posts == [] and lifted.state(held) == "prepared"
    assert lifted.parts["delivery"].recipient_scope() is None
    assert not lifted.mail.bounds_lifted() and not lifted.mail.permits(email_of_run(lifted,
                                                                                    authority_b))


def test_the_production_policies_follow_the_mode_and_never_a_synthetic_profile():
    from backend.u8_host import PolicyUnresolved

    live, rehearsal = (SimpleNamespace(is_production=True, mode=mode)
                       for mode in ("live", "rehearsal"))
    assert topics_policy(live) is PRODUCTION_LIVE_TOPICS
    assert topics_policy(rehearsal) is PRODUCTION_REHEARSAL_TOPICS
    settings = SimpleNamespace(activation_destination_id="a" * 32,
                               free_terms_reference=FREE_TERMS)
    assert export_policy(rehearsal, settings).activation_destination_id == "a" * 32
    lifted = export_policy(live, settings)
    assert (lifted.activation_destination_id, lifted.production_live) == (None, True)
    assert not lifted.synthetic_only
    for synthetic in (SimpleNamespace(is_production=False, mode="live"),):
        with pytest.raises(PolicyUnresolved):
            topics_policy(synthetic)
        with pytest.raises(PolicyUnresolved):
            export_policy(synthetic, settings)
    # The live export policy names no destination and keeps the free terms and limits.
    with pytest.raises(ValueError):
        type(lifted)(policy_id="x", production_live=True, free_terms_reference=FREE_TERMS,
                     activation_destination_id="b" * 32)
    with pytest.raises(ValueError):
        production_live_export(free_terms_reference="")


# --- U5's live branches, through U5's own code (U5's re-check, Major and Minors) ----------


class LiveGate:
    """A live gate for U5's live branches: Resend's answer is set by the test, and the
    approved first effect's digest is the one the test approves."""

    mode = "live"

    def __init__(self, maintainer):
        self.maintainer, self.resend, self.approved, self.previews = maintainer, "active", None, []

    def state(self, provider: str) -> str:
        return self.resend if provider == "resend" else "active"

    def is_maintainer_account(self, account_id) -> bool:
        return account_id == self.maintainer

    def is_maintainer_connection(self, connection_id) -> bool:
        return False

    def record_preview(self, provider: str, content: bytes) -> str:
        digest = hashlib.sha256(content).hexdigest()
        self.previews.append(digest)
        return digest

    def approved_content(self, provider: str) -> str | None:
        return self.approved if self.resend == "active" else None


class Recording:
    """An email allowance that records each reservation, release and settlement, and
    can be exhausted or made to fail one step."""

    def __init__(self, *, exhausted: str | None = None, failing: str | None = None):
        self.exhausted, self.failing = exhausted, failing
        self.reserved, self.released, self.settled = [], [], []

    def reserve(self, kind, message_key):
        from backend.modules.accounts.integrations.email_allowance import AllowanceExhausted

        if self.exhausted:
            raise AllowanceExhausted(self.exhausted)
        reservation = ("reservation", kind, message_key)
        self.reserved.append(reservation)
        return reservation

    def release(self, token):
        if self.failing == "release":
            raise RuntimeError("release failed")
        self.released.append(token)

    def settle(self, token):
        if self.failing == "settle":
            raise RuntimeError("settle failed")
        self.settled.append(token)


class Answering(Resend):
    """Resend answering every message with one status."""

    def __init__(self, status: int):
        super().__init__()
        self.status = status

    async def post(self, endpoint, *, headers, json):
        self.posts.append(json["to"][0])
        if self.status == 200:
            return httpx.Response(200, json={"id": str(uuid4())})
        return httpx.Response(self.status, json={"name": "validation_error"})


def outcome(rig, run) -> dict:
    return rig.repository.system(lambda conn: conn.execute(
        "SELECT r.state,o.failure_reason FROM topics.digest_run r LEFT JOIN "
        "topics.delivery_outcome o ON o.run_id=r.id WHERE r.id=%s", (run["id"],)).fetchone())


def live_rig(digests, authority, **options):
    """The live policy behind a live gate whose first effect is the maintainer's run."""
    gate = LiveGate(authority.account_id)
    rig = digests(gate, PRODUCTION_LIVE_TOPICS, authority, **options)
    mine = rig.prepared(authority)
    gate.approved = hashlib.sha256(rig.content(mine)).hexdigest()
    return gate, rig, mine


SEND_LOG = "INSERT INTO topics.send_log_entry"


class Raising:
    """A connection on which one statement raises (a raise-only statement-failure
    injection); every other statement runs on the realm as usual."""

    def __init__(self, conn, fragment: str, error: Exception):
        self.conn, self.fragment, self.error = conn, fragment, error

    def execute(self, statement, params=None, **options):
        if self.fragment in statement:
            raise self.error
        return self.conn.execute(statement, params, **options)

    def transaction(self):
        return self.conn.transaction()


def raising(monkeypatch, repository, fragment: str, error: Exception):
    real = repository.system
    monkeypatch.setattr(repository, "system", lambda work: real(
        lambda conn: work(Raising(conn, fragment, error))))


def blocking_unknown(rig, run) -> dict:
    """Another run of `run`'s topic, left with an unreconciled unknown outcome through the
    topics owner's own operations (Step 98(d)): prepared for a window that ends before
    `run`'s begins, then begun on the local sink and finished `unknown`, so the allowance
    records no reservation for it. Its send log holds no receipt, so the scheduler's
    reconciliation leaves it unknown, and the sending transition's guard against such an
    outcome finds no row for `run`."""
    start = run["window_start"] - dt.timedelta(days=30)
    other, adopted = rig.repository.prepare_run(
        run["topic_id"], start, start + dt.timedelta(days=6), run["settings_revision"],
        [{"title": "합성 논문", "publishedOn": start.isoformat()}])
    assert adopted is False
    assert rig.repository.begin_send(other["id"], "local-sink")["state"] == "sending"
    assert rig.repository.finish_send(other["id"], "unknown")["state"] == "unknown"
    return other


def resolve(rig, other) -> None:
    """The unknown outcome resolved, so the next sending transition succeeds."""
    assert rig.repository.reconcile_run(other["id"], "failed")["state"] == "failed"


def begin(rig, run):
    return begin_live_send(rig.repository, run["id"], policy=PRODUCTION_LIVE_TOPICS,
                           allowance=rig.allowance)


def test_an_exhausted_allowance_leaves_the_run_prepared(digests, authority):
    for limit in ("daily", "monthly"):
        _, rig, mine = live_rig(digests, authority, allowance=Recording(exhausted=limit))
        rig.parts["scheduler"].run_once()
        assert rig.state(mine) == "prepared" and rig.resend.posts == []
        assert rig.allowance.reserved == rig.allowance.released == []
        rig.close()


def test_a_definite_refusal_releases_and_an_unknown_outcome_keeps_the_reservation(
    digests, authority,
):
    _, refused, mine = live_rig(digests, authority, allowance=Recording(),
                                resend=Answering(422))
    refused.parts["scheduler"].run_once()
    assert outcome(refused, mine) == {"state": "failed",
                                      "failure_reason": "delivery-path-refused"}
    assert refused.allowance.released == refused.allowance.reserved != []
    assert refused.allowance.settled == []
    refused.close()
    _, unknown, other = live_rig(digests, authority, allowance=Recording(),
                                 resend=Answering(503))
    unknown.parts["scheduler"].run_once()
    assert unknown.state(other) == "unknown" and len(unknown.allowance.reserved) == 1
    assert unknown.allowance.released == unknown.allowance.settled == []
    unknown.close()
    _, accepted, sent = live_rig(digests, authority, allowance=Recording())
    accepted.parts["scheduler"].run_once()
    assert accepted.state(sent) == "sent"
    assert accepted.allowance.settled == accepted.allowance.reserved != []
    accepted.close()


def test_begin_send_releases_the_reservation_when_it_returns_none_or_raises(
    digests, authority, monkeypatch,
):
    _, rig, mine = live_rig(digests, authority, allowance=Recording())
    # A guard stops the sending transition after the reservation: None, and released.
    other = blocking_unknown(rig, mine)
    assert begin(rig, mine) is None and rig.state(mine) == "prepared"
    assert rig.allowance.released == rig.allowance.reserved and len(rig.allowance.reserved) == 1
    resolve(rig, other)
    # `begin` raising after the reservation: the transaction rolls back, it releases.
    raising(monkeypatch, rig.repository, SEND_LOG,
            RuntimeError("the send log could not be written"))
    with pytest.raises(RuntimeError, match="send log"):
        begin(rig, mine)
    monkeypatch.undo()
    assert rig.state(mine) == "prepared"
    assert rig.allowance.released == rig.allowance.reserved and len(rig.allowance.reserved) == 2
    # Then it begins normally, keeping its reservation for the delivery to settle.
    sending = begin(rig, mine)
    assert sending["state"] == "sending" and len(rig.allowance.released) == 2
    rig.repository.finish_send(mine["id"], "failed", failure_reason="test-cleanup")


def test_a_failing_settle_or_release_surfaces_after_the_outcome_is_kept(
    digests, authority, monkeypatch,
):
    _, settling, mine = live_rig(digests, authority, allowance=Recording(failing="settle"))
    with pytest.raises(RuntimeError, match="settle failed"):
        settling.parts["scheduler"].run_once()
    # The send was recorded before the settlement failed; it is never sent again.
    assert settling.state(mine) == "sent" and settling.resend.posts == [settling.maintainer]
    settling.close()
    _, releasing, mine = live_rig(digests, authority, allowance=Recording(failing="release"))
    other = blocking_unknown(releasing, mine)
    with pytest.raises(RuntimeError, match="release failed"):
        begin(releasing, mine)
    assert releasing.state(mine) == "prepared"  # nothing was attempted
    resolve(releasing, other)
    _, refusing, theirs = live_rig(digests, authority, allowance=Recording(failing="release"),
                                   resend=Answering(422))
    with pytest.raises(RuntimeError, match="release failed"):
        refusing.parts["scheduler"].run_once()
    assert outcome(refusing, theirs) == {"state": "failed",
                                         "failure_reason": "delivery-path-refused"}


def test_the_live_digest_parts_refuse_to_be_built_without_their_ports(
    transactions, digests, authority,
):
    from backend.modules.topics.errors import TopicsError
    from backend.u8_topics import GatedTopicsScheduler, LiveDigestDelivery

    for options in ({"synthetic_only": True}, {"real_send_limit": 5},
                    {"real_evidence_retention_days": 0}, {"real_send_limit": False}):
        with pytest.raises(ValueError):
            dataclasses.replace(PRODUCTION_LIVE_TOPICS, **options)
    gate, rig, mine = live_rig(digests, authority)
    unsubscribe = _rolling_unsubscribe()(transactions, origin=ORIGIN,
                                         clock=lambda: dt.datetime.now(dt.UTC))
    with pytest.raises(ValueError, match="email allowance"):
        LiveDigestDelivery(transactions, None, policy=PRODUCTION_LIVE_TOPICS, mail=rig.mail,
                           unsubscribe=unsubscribe, allowance=None)
    with pytest.raises(ValueError, match="live policy only"):
        LiveDigestDelivery(transactions, None, policy=PRODUCTION_REHEARSAL_TOPICS,
                           mail=rig.mail, unsubscribe=unsubscribe, allowance=Recording())
    ungated = SimpleNamespace(path_kind="real", gate=None, permitted_recipient=rig.maintainer)
    with pytest.raises(ValueError, match="provider gate"):
        LiveDigestDelivery(transactions, None, policy=PRODUCTION_LIVE_TOPICS, mail=ungated,
                           unsubscribe=unsubscribe, allowance=Recording())
    delivery = rig.parts["delivery"]
    for missing in ("gate", "recipients", "first_effects"):
        ports = {"gate": gate, "recipients": gate, "first_effects": gate, missing: None}
        with pytest.raises(ValueError, match="gate and its ports"):
            GatedTopicsScheduler(transactions, None, delivery, policy=PRODUCTION_LIVE_TOPICS,
                                 **ports)
    for path, limit in (("local-sink", 0), ("real", 3)):
        with pytest.raises(TopicsError):
            rig.repository.begin_send(mine["id"], path, real_send_limit=limit,
                                      evidence_retention_days=30 if path == "real" else None,
                                      admission=lambda run: True)
    assert rig.state(mine) == "prepared"


def test_a_hold_arriving_mid_pass_leaves_the_run_prepared_or_names_its_true_reason(
    digests, authority, monkeypatch,
):
    # Before the send begins: the gate is read again, and the run stays prepared.
    gate, rig, mine = live_rig(digests, authority, allowance=Recording())
    scheduler = rig.parts["scheduler"]
    approved = gate.approved

    def answer_then_hold(provider):
        gate.resend = "held"  # the hold lands after the queue was chosen
        return approved

    monkeypatch.setattr(gate, "approved_content", answer_then_hold)
    scheduler.run_once()
    monkeypatch.undo()
    assert rig.state(mine) == "prepared" and rig.resend.posts == []
    assert rig.allowance.reserved == []
    # After the send began: nothing leaves, the run fails with its true reason (never
    # `recipient-not-permitted`), and the reservation is released.
    gate.resend = "active"
    started = scheduler.repository.begin_send

    def begin_then_hold(*args, **options):
        value = started(*args, **options)
        gate.resend = "held"
        return value

    monkeypatch.setattr(scheduler.repository, "begin_send", begin_then_hold)
    scheduler.run_once()
    assert outcome(rig, mine) == {"state": "failed", "failure_reason": "provider-held"}
    assert rig.resend.posts == []
    assert rig.allowance.released == rig.allowance.reserved != []


def test_the_approved_first_effect_goes_strictly_first(
    digests, authority, authority_b, monkeypatch,
):
    # Blocked: a guard stops the approved run's sending transition; another
    # subscriber's run does not take its place.
    gate, rig, mine = live_rig(digests, authority, allowance=Recording())
    theirs = rig.prepared(authority_b)
    scheduler = rig.parts["scheduler"]
    other = blocking_unknown(rig, mine)
    for _ in range(3):
        scheduler.run_once()
    assert rig.state(other) == "unknown"
    assert (rig.state(mine), rig.state(theirs)) == ("prepared", "prepared")
    assert rig.resend.posts == [] and rig.allowance.released == rig.allowance.reserved
    resolve(rig, other)
    # Unblocked: the approved run goes first, then the other subscriber is served.
    rig.passes_until(lambda: rig.state(mine) == "sent")
    assert rig.resend.posts[0] == rig.maintainer
    rig.passes_until(lambda: rig.state(theirs) == "sent")
    rig.close()
    # Discarded before any attempt: the approved effect can no longer leave, so nothing
    # goes until a new decision.
    gate, rig, mine = live_rig(digests, authority, allowance=Recording())
    theirs = rig.prepared(authority_b)
    topic = rig.topics[0][1]
    rig.repository.discard_prepared_runs(topic)
    assert rig.state(mine) == "discarded"
    for _ in range(3):
        rig.parts["scheduler"].run_once()
    assert rig.state(theirs) == "prepared" and rig.resend.posts == []
    rig.close()


def test_the_maintainers_first_effect_is_found_behind_a_full_page_of_other_runs(
    digests, authority, authority_b,
):
    gate = LiveGate(authority.account_id)
    rig = digests(gate, PRODUCTION_LIVE_TOPICS, authority, allowance=Recording())
    others = [rig.prepared(authority_b) for _ in range(51)]
    mine = rig.prepared(authority)  # the newest: behind 51 older runs of another owner
    assert rig.parts["scheduler"].repository.prepared_runs(50)[-1]["id"] != mine["id"]
    gate.approved = hashlib.sha256(rig.content(mine)).hexdigest()
    rig.parts["scheduler"].run_once()
    assert rig.state(mine) == "sent" and rig.resend.posts == [rig.maintainer]
    assert all(rig.state(run) == "prepared" for run in others)


def real_sends(connect) -> int:
    with connect("topics") as conn:
        return conn.execute("SELECT count(*) AS n FROM topics.send_log_entry WHERE "
                            "path_kind='real'").fetchone()["n"]


def account_message(maintainer) -> AccountMessage:
    """One account message to the maintainer's account, keyed by its own uuid."""
    key = str(uuid4())
    return AccountMessage("password-reset", key, maintainer, {
        "challengeId": str(uuid4()), "proof": "proof-" + uuid4().hex,
        "flowBinding": str(uuid4()), "email": "maintainer@fixture.example.com",
    })


def test_account_mail_and_a_live_digest_spend_one_daily_count_through_their_adapters(
    digests, authority, clock, connect, operations_ledger,
):
    """D12 (Step 85(g)): account mail and a live digest share one day's count through
    their own adapters: 60 account messages hold the digest, 90 stop account mail, and the
    UTC day's turn sends the waiting digest once.

    The day is taken from the real clock, ten days ahead: U5 accepts an unsubscribe link
    only while it expires after the database's own clock, and the link issued here
    expires 30 days after the pinned clock."""
    day = dt.datetime.now(dt.UTC).date() + dt.timedelta(days=10)
    clock.now = dt.datetime.combine(day, dt.time(23, 0), tzinfo=dt.UTC)
    gate, rig, mine = live_rig(digests, authority)  # the rig's real LedgerAllowance
    assert (rig.allowance.policy.digest_daily_limit,
            rig.allowance.policy.account_mail_daily_limit,
            rig.allowance.policy.mail_monthly_limit) == (60, 90, 2700)
    # The host process holds its own handle on the same ledger folder.
    account_ledger = Ledger.open(operations_ledger.store.folder, clock=clock)
    try:
        account_resend = Resend()
        mail = ResendAccountMail(
            api_key="re_" + uuid4().hex, sender="account@fixture.example.com",
            origin=ORIGIN, allowance=LedgerAllowance(account_ledger, SYNTHETIC_OPERATIONS),
            gate=gate, recipients=gate, client_factory=account_resend,
        )
        maintainer = authority.account_id
        assert [mail.deliver(account_message(maintainer)) for _ in range(60)] == [
            "accepted"] * 60
        sends = real_sends(connect)
        rig.parts["scheduler"].run_once()
        assert rig.state(mine) == "prepared" and rig.resend.posts == []
        assert [item for item in operations_ledger.records(KIND)
                if item["mailKind"] == "digest"] == []
        producer = ProviderProducer("provider.resend", operations_ledger,
                                    allowance=rig.allowance)
        observed = producer.observe(clock.now)
        assert (observed.outcome, observed.reason, observed.limitations) == (
            "degraded", "allowance-exhausted", ("allowance-exhausted",))
        assert [mail.deliver(account_message(maintainer)) for _ in range(30)] == [
            "accepted"] * 30
        assert mail.deliver(account_message(maintainer)) == "over_allowance"
        assert len(account_resend.posts) == 90 and rig.resend.posts == []
        # 00:00:00Z of the next UTC day, always 09:00 in Seoul (which keeps no daylight
        # saving time): the waiting digest goes once.
        turned = day + dt.timedelta(days=1)
        clock.now = dt.datetime.combine(turned, dt.time(0, 0), tzinfo=dt.UTC)
        rig.parts["scheduler"].run_once()
        assert rig.resend.posts == [rig.maintainer] and rig.state(mine) == "sent"
        [reservation] = [item for item in operations_ledger.records(KIND)
                         if item["mailKind"] == "digest"]
        assert (reservation["state"], reservation["day"]) == ("settled", turned.isoformat())
        assert turned.isoformat() != day.isoformat()  # the UTC day turned
        assert real_sends(connect) == sends + 1
        assert producer.observe(clock.now).outcome == "available"
        assert mail.deliver(account_message(maintainer)) == "accepted"
    finally:
        account_ledger.close()
        rig.close()


def test_productions_scheduler_stores_the_due_instant_and_a_held_run_reads_late_from_it(
    realm, activation, operations_ledger, clock,
):
    """L4-9: production's own parts (`topics_parts`, the gated scheduler under the live
    policy) prepare a due delivery through U5's due path, so its run holds the due
    instant, never NULL. Held, the run stays prepared, and `topics.digest` counts it from
    that instant. The `Digests` rig stands on a production stand-in of its own: the
    realm's store holds this file's other pending runs, which no schedule prepared.

    It passes on a reading worked out from the window and the current settings too: it
    shows what production's scheduler stores, not the lateness fix."""
    from backend.modules.operations.producers import DigestProducer
    from backend.u8_policy import PRODUCTION_OPERATIONS
    from tests.u8_service_operations_integration.host_flows import (
        digest_due_topic,
        digest_run_of,
    )

    day = dt.datetime.now(dt.UTC).date() + dt.timedelta(days=10)
    hours, second = dt.timedelta(hours=2), dt.timedelta(seconds=1)
    with production_stand_in(realm) as standin:
        maintainer = standin_account(standin, "first-digest", grant=False)
        gate = activation("live", maintainer.account_id)
        rig = Digests(standin.transactions, standin.connect, clock, gate, operations_ledger,
                      PRODUCTION_LIVE_TOPICS, maintainer)
        path = digest_due_topic(standin, "due-subscriber", day)
        at = dt.datetime(day.year, day.month, day.day, 9, 17, tzinfo=dt.UTC)
        with standin.connect("topics") as conn:
            due = conn.execute("SELECT due_at FROM topics.next_occurrence(%s,%s)",
                               (path.topic, at)).fetchone()["due_at"]
        assert due == at - dt.timedelta(minutes=17)
        scheduler = rig.parts["scheduler"]
        scheduler._now = lambda: at  # U5's clock, pinned on the instance
        assert scheduler.run_once()["prepared"] == 1
        run = digest_run_of(path)
        assert (run["state"], run["scheduled_at"], run["window_end"]) == ("prepared", due, day)
        assert rig.resend.posts == [] and gate.state("resend") == "held"
        producer = DigestProducer(standin.transactions, PRODUCTION_OPERATIONS)
        on_time, late = producer.observe(due + hours), producer.observe(due + hours + second)
        assert (on_time.outcome, on_time.reason) == ("available", None)
        assert (late.outcome, late.reason) == ("degraded", "digest-delivery-late")


# --- Exports (U6) ------------------------------------------------------------------------


@pytest.fixture
def gate_installed(monkeypatch):
    monkeypatch.setattr(notion_session, "_INSTALLED_GATE", {})
    return lambda gate: notion_session.install_provider_gate(gate, gate)


class Connected:
    """The gate the connection was configured under before the window opened: Notion
    active. The live policy holds every operation with no gate at all."""

    mode = "live"

    def state(self, provider: str) -> str:
        return "active"

    def is_maintainer_connection(self, connection_id) -> bool:
        return False

    def is_maintainer_account(self, account_id) -> bool:
        return False


@pytest.fixture
def export_stand_in(realm):
    """A database of the test's own (your answer of 2026-11-11, "Own database"): a
    production stand-in, where the real `due_items` query answers only this test's rows,
    so the preview pass reads U6's store unchanged; and its maintainer's account."""
    with production_stand_in(realm) as standin:
        yield standin, standin_account(standin, "first-export", grant=False)


def test_the_first_export_is_held_with_its_preview_and_written_on_your_decision(
    export_stand_in, tmp_path, activation, gate_installed, operations_ledger, clock,
):
    standin, authority = export_stand_in
    connect = standin.connect
    cf.switching(operations_ledger, clock)
    lr = lf.build(standin.transactions, connect, authority, tmp_path, fresh=False,
                  policy=production_live_export(free_terms_reference=FREE_TERMS))
    gate_installed(Connected())
    lr.rig.configure()  # connected before the window opens
    gate = activation("live", authority.account_id)
    gate_installed(gate)
    # The maintainer prepares the first export in the window: browser reads still run.
    flow = lf.pressed(lr, configure=False)
    assert lr.lane.run_item(lf.item(flow["effect"])) == "waiting"
    assert lr.fake.writes == [] and lf.attempts(connect, flow["effect"]) == []
    # The U8 pass records the waiting export's exact bound content as the preview.
    effect = lf.effect_id(flow["effect"])
    content = StoreContentPort(lr.repo)
    assert [row["id"] for row in lr.repo.due_items(lr.clock(), limit=100)] == [effect]
    previews = FirstExportPreviews(lr.repo, content, gate, clock=lr.clock)
    assert previews.run_once() == {"recorded": 1}
    digest = hashlib.sha256(export_preview(content.bound_content(effect))).hexdigest()
    assert gate.previews_of("notion") == frozenset({digest})
    # A decision on another digest is refused; the export keeps waiting, nothing written.
    with pytest.raises(OperationsError):
        gate.approve("notion", *decide(operations_ledger, clock, "notion", "1" * 64))
    assert lr.lane.run_item(lf.item(lf.row(connect, flow["effect"]))) == "waiting"
    assert lr.fake.writes == []
    # Your decision on that digest: the one write goes, to a page outside any test bound.
    gate.approve("notion", *decide(operations_ledger, clock, "notion", digest))
    assert previews.run_once() == {"recorded": 0}  # active: no more previews
    assert lr.lane.run_item(lf.item(lf.row(connect, flow["effect"]))) == "succeeded"
    assert len(lr.fake.writes) == 1 and lf.row(connect, flow["effect"])["state"] == "succeeded"


def test_u6s_bound_stays_in_rehearsal_and_lifts_only_in_live_mode(
    transactions, connect, authority, tmp_path, activation, gate_installed,
):
    # Rehearsal: U6's real activation keeps its one activation page.
    lr = lf.build(transactions, connect, authority, tmp_path,
                  policy=real_activation_export(activation_destination_id="c" * 32,
                                                free_terms_reference=FREE_TERMS))
    lr.rig.configure()
    gate_installed(activation("rehearsal", authority.account_id))
    with pytest.raises(ExportError) as refused:
        lr.rig.preview(lr.rig.page())
    assert refused.value.code == "FORBIDDEN"
    # Live and held: a background read through your own connection waits; another
    # owner's connection is held outright.
    live = activation("live", authority.account_id)
    gate_installed(live)
    other = notion_session.StoredConnection(account_id=uuid4(), connection_id=uuid4())
    assert notion_session.provider_hold(other, interactive=True) == (
        notion_session.CAUSE_PROVIDER_HELD)
    own = notion_session.StoredConnection(account_id=authority.account_id,
                                          connection_id=uuid4())
    assert notion_session.provider_hold(own) == notion_session.CAUSE_PROVIDER_HELD
    assert notion_session.provider_hold(own, interactive=True) is None


def test_an_unclear_export_effect_counts_from_its_acceptance(export_stand_in, tmp_path):
    """L4-3 (option 1): an effect accepted 20 hours before its one write became unclear
    is `export-effect-late` one second past 24 hours from its acceptance, although U6's
    own age for it, counted from its attempt's deadline, is still about four hours.
    Both instants are read from the stored rows; neither is edited."""
    from backend.modules.export.fake_notion import Answer
    from backend.modules.operations.producers import ExportProducer
    from backend.u8_policy import PRODUCTION_OPERATIONS
    from tests.u6_approved_export import notion_flows as nf

    standin, authority = export_stand_in
    connect = standin.connect
    lr = lf.build(standin.transactions, connect, authority, tmp_path, fresh=False,
                  policy=nf.policy(write_deadline_seconds=1))
    flow = lf.pressed(lr)
    lr.clock.advance(20 * 3600)
    lr.fake.queue("pages.create", Answer.slow(3))
    assert lr.lane.run_item(lf.item(flow["effect"])) == "unknown"
    [attempt] = lf.attempts(connect, flow["effect"])
    with connect("export") as conn:
        row = conn.execute("SELECT state, accepted_at FROM export.effect WHERE id=%s",
                           (lf.effect_id(flow["effect"]),)).fetchone()
    accepted, deadline = row["accepted_at"], attempt["deadline_at"]
    assert row["state"] == "unknown" and deadline - accepted >= dt.timedelta(hours=20)
    bound = PRODUCTION_OPERATIONS.export_degraded_after_seconds
    assert bound == 24 * 3600
    edge = accepted + dt.timedelta(seconds=bound)
    producer = ExportProducer(standin.transactions, PRODUCTION_OPERATIONS)
    on_time, late = producer.observe(edge), producer.observe(edge + dt.timedelta(seconds=1))
    assert (on_time.outcome, on_time.reason) == ("available", None)
    assert (late.outcome, late.reason, late.limitations) == (
        "degraded", "export-effect-late", ("export-effect-late",))
    # U6's own two ages at that instant: no accepted effect, and the unknown one's
    # settling wait, counted from its attempt's deadline, well under the bound.
    status = standin.transactions.run("export", lambda conn: conn.execute(
        "SELECT export.status_counts(%s) AS status",
        (edge + dt.timedelta(seconds=1),)).fetchone()["status"])
    assert status["oldestAcceptedSeconds"] is None
    assert 0 < status["oldestUnknownSeconds"] <= 4 * 3600 + 1


# --- Without the provider gate: fail closed (U6's re-check, Major) -------------------------


def test_the_live_export_policy_holds_every_operation_without_the_gate(
    transactions, connect, authority, tmp_path, gate_installed,
):
    lr = lf.build(transactions, connect, authority, tmp_path,
                  policy=production_live_export(free_terms_reference=FREE_TERMS))
    gate_installed(Connected())
    flow = lf.pressed(lr)  # connected and pressed while a gate was installed
    gate_installed(None)  # the gate is lost: a composition without ServiceOperations
    assert notion_session._INSTALLED_GATE == {}
    # The held first export can never be sent before your decision: the lane waits,
    # no attempt is claimed and nothing is written.
    for _ in range(3):
        assert lr.lane.run_item(lf.item(lf.row(connect, flow["effect"]))) == "waiting"
    assert lr.fake.writes == [] and lf.attempts(connect, flow["effect"]) == []
    own = notion_session.StoredConnection(account_id=authority.account_id,
                                          connection_id=uuid4())
    for interactive in (False, True):
        assert notion_session.provider_hold(own, interactive=interactive, live=True) == (
            notion_session.CAUSE_PROVIDER_HELD)
        # Every other policy keeps the built behaviour with no gate (earlier assemblies).
        assert notion_session.provider_hold(own, interactive=interactive) is None


def test_a_live_registration_without_service_operations_composes_no_outward_path(
    transactions, monkeypatch, tmp_path,
):
    """A live production registration in which ServiceOperations is unavailable: the
    export (which requires only research-workspace and topics-digests) and the digests
    are each unavailable with `policy-unresolved`, account mail is held and no gate is
    left installed, so nothing can be sent."""
    from backend.modules.accounts.integrations.account_mail import (
        AccountMessage,
        HeldAccountMail,
        LocalAccountMail,
    )
    from backend.u8_host import (
        BUILDERS,
        MANIFEST,
        BuildContext,
        PolicyUnresolved,
        applied_digests,
        register,
        wire_adapters,
    )

    monkeypatch.setattr(notion_session, "_INSTALLED_GATE", {})
    notion_session.install_provider_gate(Connected(), Connected())  # a stale gate
    sent = []

    class Mailbox:
        def publish(self, payload):
            sent.append(payload)

    entry = SimpleNamespace(account_mail=LocalAccountMail(Mailbox()))

    def lost(ctx):
        raise PolicyUnresolved("ServiceOperations is unavailable")

    stubs = {
        "paper-journey": lambda ctx: {"entry": SimpleNamespace()},
        "account-controls": lambda ctx: {"entry": entry},
        "paper-corpus": lambda ctx: {"corpus_repository": None, "worker": None},
        "research-workspace": lambda ctx: {"worker": None, "service": None},
        "platform-control": lambda ctx: {},
        "service-operations": lost,
    }
    builders = {name: (revision, stubs.get(name, build))
                for name, (revision, build) in BUILDERS.items()}
    # Topics stands active in a second pass, so the export's own check is what refuses.
    profile = SimpleNamespace(is_production=True, mode="live", root=tmp_path,
                              run_id="docsuri-v2-" + "0" * 16, origin=ORIGIN,
                              maintainer_account=uuid4())
    known = applied_digests(transactions)
    ctx = BuildContext(profile, transactions, lambda: dt.datetime.now(dt.UTC))
    activations = register(MANIFEST, ctx, known, builders=builders)
    assert activations["service-operations"].reason == "policy-unresolved"
    assert activations["topics-digests"].reason == "policy-unresolved"
    assert activations["approved-export"].activation == "unavailable"
    with_topics = {**builders, "topics-digests": (BUILDERS["topics-digests"][0],
                                                  lambda ctx: {"worker": None})}
    ctx = BuildContext(profile, transactions, lambda: dt.datetime.now(dt.UTC))
    activations = register(MANIFEST, ctx, known, builders=with_topics)
    assert activations["topics-digests"].activation == "active"
    assert activations["approved-export"].reason == "policy-unresolved"
    assert "approved-export" not in ctx.parts and "service-operations" not in ctx.parts
    # Account mail: held, nothing published even to the local mailbox; no gate remains.
    wire_adapters({name: value for name, value in ctx.parts.items() if name != "ledger"},
                  profile)
    assert isinstance(entry.account_mail, HeldAccountMail)
    message = AccountMessage("verification", str(uuid4()), uuid4(),
                             {"email": "member@fixture.invalid"})
    assert entry.account_mail.deliver(message) == "held" and sent == []
    assert notion_session._INSTALLED_GATE == {}
