"""Production fails closed without U8's parts, and U8's parts hold at the scheduler (U8
plan Step 22, "U8's lines out of U5's files", items 3–6 and 10).

On the composed realm's own stores, through U5's and U8's real classes; Resend is a fake
under the real adapter and the ledger is a private folder.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import logging
from types import SimpleNamespace
from uuid import uuid4

import pytest
from test_first_effects import ORIGIN, Digests, LiveGate, Recording, Resend

from backend.modules.accounts.integrations.u8_digest_mail import (
    GatedResendDigestMail,
    HeldDigestMail,
)
from backend.modules.operations.ledger import Ledger
from backend.modules.topics import scheduler as u5_scheduler
from backend.modules.topics.delivery import DigestDelivery
from backend.modules.topics.errors import TopicsError
from backend.modules.topics.scheduler import TopicsScheduler
from backend.u8_host import PROVIDER_SECRETS
from backend.u8_outward import DIGEST_SENDER, _rolling_unsubscribe, digest_mail, topics_parts
from backend.u8_topics import (
    PRODUCTION_LIVE_TOPICS,
    PRODUCTION_REHEARSAL_TOPICS,
    AllowanceAdmission,
    GatedTopicsScheduler,
    LiveDigestDelivery,
    begin_live_send,
)


class Gate(LiveGate):
    """A gate whose mode and Resend answer the test sets."""

    def __init__(self, maintainer, *, mode="rehearsal", resend="active"):
        super().__init__(maintainer)
        self.mode, self.resend = mode, resend


@pytest.fixture
def operations_ledger(tmp_path, clock):
    folder = tmp_path / "operations-ledger"
    folder.mkdir(mode=0o700)
    value = Ledger.open(folder, clock=clock)
    yield value
    value.close()


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


@pytest.fixture
def unsubscribe(transactions):
    return _rolling_unsubscribe()(transactions, origin=ORIGIN,
                                  clock=lambda: dt.datetime.now(dt.UTC))


def real_sends(repository) -> int:
    return repository.system(lambda conn: conn.execute(
        "SELECT count(*) AS n FROM topics.send_log_entry WHERE path_kind='real'"
    ).fetchone()["n"])


def held_parts(rig, gate, policy, mail):
    """U8's production parts over the rig's realm, with `mail` in place of its adapter."""
    entry = SimpleNamespace(verifier=lambda purpose, value: hashlib.sha256(
        f"{purpose}:{value}".encode()).hexdigest())
    return topics_parts(
        rig.repository.transactions, entry, None, None, policy=policy, mail=mail,
        unsubscribe=rig.parts["delivery"].unsubscribe, activation=gate,
        allowance=rig.allowance,
    )


# --- 3. Without U8's parts, production fails closed --------------------------------------


def test_u5s_plain_parts_under_the_live_policy_refuse_at_begin_send(
    transactions, digests, authority, unsubscribe,
):
    gate = Gate(authority.account_id, mode="live")
    rig = digests(gate, PRODUCTION_LIVE_TOPICS, authority)
    mine = rig.prepared(authority)
    gate.approved = hashlib.sha256(rig.content(mine)).hexdigest()
    delivery = DigestDelivery(transactions, None, policy=PRODUCTION_LIVE_TOPICS, mail=rig.mail,
                              unsubscribe=unsubscribe)
    scheduler = TopicsScheduler(transactions, None, delivery, policy=PRODUCTION_LIVE_TOPICS)
    before = real_sends(rig.repository)
    with pytest.raises(TopicsError) as refused:
        scheduler._send_prepared({"sent": 0, "failed": 0, "unknown": 0})
    assert (refused.value.code, refused.value.current) == (
        "INVALID_ARGUMENT", {"field": "realSendAllocation"})
    assert rig.resend.posts == [] and rig.state(mine) == "prepared"
    assert real_sends(rig.repository) == before


def test_the_gated_scheduler_refuses_parts_that_do_not_belong_together(
    transactions, digests, authority, unsubscribe, monkeypatch,
):
    gate = Gate(authority.account_id, mode="live")
    live = digests(gate, PRODUCTION_LIVE_TOPICS, authority, allowance=Recording())
    plain = DigestDelivery(transactions, None, policy=PRODUCTION_LIVE_TOPICS, mail=live.mail,
                           unsubscribe=unsubscribe)
    ports = {"gate": gate, "recipients": gate, "first_effects": gate}
    with pytest.raises(ValueError, match="belong together"):
        GatedTopicsScheduler(transactions, None, plain, policy=PRODUCTION_LIVE_TOPICS, **ports)
    with pytest.raises(ValueError, match="belong together"):
        GatedTopicsScheduler(transactions, None, live.parts["delivery"],
                             policy=PRODUCTION_REHEARSAL_TOPICS, **ports)
    for missing in ports:
        with pytest.raises(ValueError, match="gate and its ports"):
            GatedTopicsScheduler(transactions, None, live.parts["delivery"],
                                 policy=PRODUCTION_LIVE_TOPICS, **{**ports, missing: None})
    other = Gate(authority.account_id, mode="live")
    with pytest.raises(ValueError, match="another gate"):
        GatedTopicsScheduler(transactions, None, live.parts["delivery"],
                             policy=PRODUCTION_LIVE_TOPICS,
                             **{**ports, "gate": other})
    for hook in ("_send_queue", "_may_begin_send", "_begin_send"):
        monkeypatch.delattr(u5_scheduler.TopicsScheduler, hook)
        with pytest.raises(ValueError, match=hook):
            GatedTopicsScheduler(transactions, None, live.parts["delivery"],
                                 policy=PRODUCTION_LIVE_TOPICS, **ports)
        monkeypatch.undo()


def test_the_gated_digest_adapter_refuses_its_missing_ports():
    gate = Gate(uuid4())
    base = {"api_key": "re_" + uuid4().hex, "sender": "digest@fixture.example.com",
            "unsubscribe_url": ORIGIN, "permitted_recipient": "maintainer@fixture.example.com",
            "gate": gate, "recipients": gate, "account_of": {}.get}
    assert GatedResendDigestMail(**base).gate is gate
    for missing in ("gate", "recipients", "account_of"):
        with pytest.raises(ValueError, match="needs the gate"):
            GatedResendDigestMail(**{**base, missing: None})


# --- 4. Rehearsal holds at the scheduler ---------------------------------------------------


@pytest.mark.parametrize("resend", ["unavailable", "held"])
def test_rehearsal_holds_at_the_scheduler_behind_a_closed_gate(digests, authority, resend):
    gate = Gate(authority.account_id, mode="rehearsal", resend=resend)
    rig = digests(gate, PRODUCTION_REHEARSAL_TOPICS, authority)
    mine = rig.prepared(authority)
    before = real_sends(rig.repository)
    for _ in range(2):
        rig.parts["scheduler"].run_once()
    assert rig.state(mine) == "prepared" and rig.resend.posts == []
    assert real_sends(rig.repository) == before and gate.previews == []


def test_the_held_adapter_behind_an_active_gate_begins_nothing(digests, authority):
    gate = Gate(authority.account_id, mode="rehearsal", resend="active")
    rig = digests(gate, PRODUCTION_REHEARSAL_TOPICS, authority, allowance=Recording())
    mine = rig.prepared(authority)
    held = HeldDigestMail(permitted_recipient=rig.maintainer, gate=gate)
    parts = held_parts(rig, gate, PRODUCTION_REHEARSAL_TOPICS, held)
    before = real_sends(rig.repository)
    parts["scheduler"].run_once()
    assert rig.state(mine) == "prepared" and rig.resend.posts == []
    assert real_sends(rig.repository) == before
    # Live mode with an approved digest and the held adapter: the pass completes, and
    # nothing is sent.
    live = Gate(authority.account_id, mode="live", resend="active")
    live.approved = "a" * 64
    live_held = HeldDigestMail(permitted_recipient=rig.maintainer, gate=live)
    parts = held_parts(rig, live, PRODUCTION_LIVE_TOPICS, live_held)
    result = parts["scheduler"].run_once()
    assert result["sent"] == result["failed"] == result["unknown"] == 0
    assert rig.state(mine) == "prepared" and real_sends(rig.repository) == before
    assert rig.allowance.reserved == [] and rig.resend.posts == []


# --- 5. The production composition picks U8's parts ---------------------------------------


def test_topics_parts_pick_the_live_delivery_only_under_the_live_policy(digests, authority):
    live = digests(Gate(authority.account_id, mode="live"), PRODUCTION_LIVE_TOPICS, authority)
    assert isinstance(live.parts["scheduler"], GatedTopicsScheduler)
    assert type(live.parts["delivery"]) is LiveDigestDelivery
    rehearsal = digests(Gate(authority.account_id), PRODUCTION_REHEARSAL_TOPICS, authority)
    assert isinstance(rehearsal.parts["scheduler"], GatedTopicsScheduler)
    assert type(rehearsal.parts["delivery"]) is DigestDelivery
    gate = Gate(authority.account_id)
    environment = {PROVIDER_SECRETS["provider.resend"]: "re_" + uuid4().hex,  # per run
                   DIGEST_SENDER: "digest@fixture.example.com"}
    mail = digest_mail(environment, origin=ORIGIN, maintainer=live.maintainer,
                       activation=gate, account_of={}.get)
    assert isinstance(mail, GatedResendDigestMail) and mail.gate is gate
    gate.resend = "unavailable"
    held = digest_mail(environment, origin=ORIGIN, maintainer=live.maintainer,
                       activation=gate, account_of={}.get)
    assert isinstance(held, HeldDigestMail) and held.gate is gate


# --- 6. The admission's guards -------------------------------------------------------------


def test_an_admission_called_twice_keeps_one_reservation_and_releases_it_once():
    allowance = Recording()
    admission = AllowanceAdmission(allowance)
    run = {"request_key": uuid4()}
    assert admission(run) and admission(run)
    assert len(allowance.reserved) == 1
    admission.give_back()
    admission.give_back()
    assert allowance.released == allowance.reserved
    exhausted = AllowanceAdmission(Recording(exhausted="daily"))
    assert exhausted(run) is False and exhausted.reservation is None
    exhausted.give_back()  # nothing taken: nothing given back


def test_a_retried_start_keeps_its_first_reservation(digests, authority):
    gate = Gate(authority.account_id, mode="live")
    rig = digests(gate, PRODUCTION_LIVE_TOPICS, authority, allowance=Recording())
    mine = rig.prepared(authority)
    real = rig.repository.system
    attempts = []

    class Retry(Exception):
        pass

    def retrying(work):
        if not attempts:
            attempts.append("first")

            def then_fail(conn):
                work(conn)
                raise Retry

            with pytest.raises(Retry):
                real(then_fail)  # rolled back: as if the transaction were retried
        return real(work)

    rig.repository.system = retrying
    sending = begin_live_send(rig.repository, mine["id"], policy=PRODUCTION_LIVE_TOPICS,
                              allowance=rig.allowance)
    rig.repository.system = real
    assert sending["state"] == "sending" and len(rig.allowance.reserved) == 1
    assert sending["allowance_reservation"] == rig.allowance.reserved[0]
    assert rig.allowance.released == []
    rig.repository.finish_send(mine["id"], "failed", failure_reason="test-cleanup")


def test_a_sending_row_without_a_reservation_is_refused_and_nothing_is_posted(
    digests, authority,
):
    gate = Gate(authority.account_id, mode="live")
    rig = digests(gate, PRODUCTION_LIVE_TOPICS, authority, allowance=Recording())
    mine = rig.prepared(authority)

    class Ignoring:
        """A fixed-answer stub for a refusal that real data cannot reach (your answer of
        2026-11-11, "Rewrite, keep two"): a start that never asks its admission answers a
        sending row without its allowance reservation, which U5's real begin_send never
        does. It is passed only to the start whose refusal the test asserts."""

        def begin_send(self, run_id, path_kind, **options):
            return {"state": "sending"}

    with pytest.raises(ValueError, match="without its allowance reservation"):
        begin_live_send(Ignoring(), mine["id"], policy=PRODUCTION_LIVE_TOPICS,
                        allowance=rig.allowance)
    with pytest.raises(ValueError, match="carries its allowance reservation"):
        rig.parts["delivery"].attempt({"id": mine["id"]}, {"account_id": authority.account_id})
    assert rig.resend.posts == [] and rig.state(mine) == "prepared"
    with pytest.raises(ValueError, match="live policy only"):
        begin_live_send(rig.repository, mine["id"], policy=PRODUCTION_REHEARSAL_TOPICS,
                        allowance=rig.allowance)


# --- 10. The paths no test reached ---------------------------------------------------------


def test_a_preview_that_cannot_be_recorded_is_logged_by_its_class_name(
    digests, authority, caplog,
):
    gate = Gate(authority.account_id, mode="live", resend="held")
    rig = digests(gate, PRODUCTION_LIVE_TOPICS, authority, allowance=Recording())
    mine = rig.prepared(authority)

    def broken(provider, content):
        raise PermissionError("the preview folder is not writable: /private/path")

    gate.record_preview = broken
    with caplog.at_level(logging.WARNING, logger="docsuri.u8.topics"):
        rig.parts["scheduler"].run_once()
    assert "first-effect preview not recorded (PermissionError)" in caplog.text
    assert "/private/path" not in caplog.text
    assert rig.resend.posts == [] and rig.state(mine) == "prepared"


def test_with_no_approved_digest_while_resend_is_active_in_live_mode_nothing_goes(
    digests, authority, authority_b,
):
    gate = Gate(authority.account_id, mode="live", resend="active")
    rig = digests(gate, PRODUCTION_LIVE_TOPICS, authority, allowance=Recording())
    mine, theirs = rig.prepared(authority), rig.prepared(authority_b)
    assert gate.approved_content("resend") is None
    for _ in range(2):
        rig.parts["scheduler"].run_once()
    assert (rig.state(mine), rig.state(theirs)) == ("prepared", "prepared")
    assert rig.resend.posts == [] and rig.allowance.reserved == []


def test_the_fake_resend_is_the_only_transport(digests, authority):
    """The rig's adapter posts only through the fake it was given."""
    rig = digests(Gate(authority.account_id), PRODUCTION_REHEARSAL_TOPICS, authority)
    assert isinstance(rig.resend, Resend) and rig.mail._client_factory is rig.resend


# --- 11. The digest breaker over provider.resend (U8 plan Step 162(f); L4-11) -------------------


class StoredResend:
    """provider.resend's state, derived as the composition derives it
    (`readiness.observed_state`, production's policy) from observations stored in a
    production stand-in's own database, read at the real clock: the clock each stored
    observation's age is built against."""

    CAPABILITY = "provider.resend"

    def __init__(self, standin):
        from backend.modules.operations.observation_store import ObservationStore

        self.store = ObservationStore(standin.transactions)

    def __call__(self) -> dict[str, dict]:
        from backend.modules.operations.readiness import observed_state
        from backend.u8_policy import PRODUCTION_OPERATIONS

        row = self.store.latest([self.CAPABILITY]).get(self.CAPABILITY)
        return {self.CAPABILITY: observed_state(
            self.CAPABILITY, row, dt.datetime.now(dt.UTC), PRODUCTION_OPERATIONS).brief()}

    def observe(self, outcome: str, *, age: int = 0) -> str:
        """One observation, as the provider's producer records it; the state it gives."""
        from backend.modules.operations.observations import Observations
        from backend.u8_registry import CAPABILITY_BY_ID

        producer = CAPABILITY_BY_ID[self.CAPABILITY].producer
        observations = Observations(self.store)
        row = observations.make(
            self.CAPABILITY, producer, outcome,
            reason=None if outcome == "available" else "provider-unreachable",
            observed_at=dt.datetime.now(dt.UTC) - dt.timedelta(seconds=age))
        assert observations.record(producer, [row])["written"] == 1
        return self()[self.CAPABILITY]["state"]


def test_while_resend_is_observed_unavailable_due_digests_stay_prepared_and_nothing_reaches_resend(  # noqa: E501
        realm, digests, authority):
    """Reliability-design § 10 (lines 133-137, 143: "digests wait"), L4-11: the adapter
    and the scheduler read one digest breaker. While provider.resend is observed
    unavailable a prepared digest stays prepared, no allowance is reserved and nothing is
    posted; with `unknown` and `stale` a digest is sent as built; once Resend is observed
    available the waiting digest is sent. A start during the outage still builds the real
    adapter."""
    from backend.u8_outward import digest_gate, state_reader
    from tests.u8_service_operations_integration.host_flows import production_stand_in

    activation = Gate(authority.account_id, mode="live", resend="active")
    gate = digest_gate(activation)
    with production_stand_in(realm) as standin:
        states = StoredResend(standin)
        gate.bind(state_reader(states))
        rig = digests(gate, PRODUCTION_LIVE_TOPICS, authority, allowance=Recording())
        scheduler = rig.parts["scheduler"]
        assert scheduler.gate is gate and rig.mail.gate is gate

        # Nothing observed (unknown): the approved first digest is sent as built.
        assert states()["provider.resend"]["state"] == "unknown"
        first = rig.prepared(authority)
        activation.approved = hashlib.sha256(rig.content(first)).hexdigest()
        rig.passes_until(lambda: rig.state(first) == "sent")
        assert rig.resend.posts == [rig.maintainer] and len(rig.allowance.reserved) == 1
        # Stale (an `unavailable` observation older than 900 s): sent as built.
        assert states.observe("unavailable", age=901) == "stale"
        second = rig.prepared(authority)
        rig.passes_until(lambda: rig.state(second) == "sent")
        assert len(rig.resend.posts) == 2 and len(rig.allowance.reserved) == 2

        # Observed unavailable: the digest waits, and nothing is reserved or posted.
        assert states.observe("unavailable") == "unavailable"
        assert activation.state("resend") == "active"  # the activation never moved
        waiting = rig.prepared(authority)
        sends = real_sends(rig.repository)
        for _ in range(3):
            result = scheduler.run_once()
            assert result["sent"] == result["failed"] == result["unknown"] == 0
        assert rig.state(waiting) == "prepared"
        assert len(rig.resend.posts) == 2 and len(rig.allowance.reserved) == 2
        assert real_sends(rig.repository) == sends and activation.previews == []
        # A start during the outage still builds the real adapter, on the same gate.
        environment = {PROVIDER_SECRETS["provider.resend"]: "re_" + uuid4().hex,  # per run
                       DIGEST_SENDER: "digest@fixture.example.com"}
        mail = digest_mail(environment, origin=ORIGIN, maintainer=rig.maintainer,
                           activation=activation, account_of={}.get, gate=gate)
        assert isinstance(mail, GatedResendDigestMail) and mail.gate is gate
        assert gate.state("resend") == "unavailable"

        # The probe passes: the waiting digest is sent.
        assert states.observe("available") == "available"
        rig.passes_until(lambda: rig.state(waiting) == "sent")
        assert len(rig.resend.posts) == 3 and len(rig.allowance.reserved) == 3
