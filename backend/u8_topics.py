"""TopicsDigests' live production work (U8 plan Step 21; BR7.2, BR7.3, BR7.5, BR7.6, D12).

U5's files keep U5's built behaviour; their only additions are seams whose default is
that behaviour: the scheduler's three send hooks and `begin_send`'s `admission`. The
complete assembly's production builder (`backend/u8_outward.py`) composes these parts
instead, in production only:

- `PRODUCTION_REHEARSAL_TOPICS`, a plain `TopicsPolicy` under U5's 1–100 check: digests
  reach only the maintainer's verified address (BR7.5), and the soak's digests to you fit
  on one rehearsal database.
- `PRODUCTION_LIVE_TOPICS`, a `LiveTopicsPolicy`: once Resend is active in live mode,
  digests go to every subscriber who consented, and each send spends the email allowance
  of D12 (60 digests a day, 2,700 mails a month) instead of U5's per-database allocation.
  The live policy is recognised by its class only.
- `LiveDigestDelivery`, U5's delivery with no single permitted recipient, settling the
  allowance reservation on `sent`, releasing it on `failed` and keeping it on `unknown`.
- `begin_live_send`, which begins a send through `begin_send`'s `admission` with
  `AllowanceAdmission`.
- `GatedTopicsScheduler`, U5's scheduler behind the provider gate. It holds while Resend
  is not active or its adapter is the held one, records the held first effect's preview
  in live mode, sends the approved first effect strictly first, and reads the gate again
  before each send begins.

Every query here is a read under TopicsDigests' own transaction (`repository.system`).
"""

from __future__ import annotations

import dataclasses
import hashlib
import logging

from backend.modules.accounts.integrations.email_allowance import AllowanceExhausted
from backend.modules.accounts.integrations.provider_gate import require_state
from backend.modules.accounts.integrations.u8_digest_mail import HeldDigestMail
from backend.modules.topics.delivery import DigestDelivery
from backend.modules.topics.scheduler import TopicsScheduler
from backend.u5_policy import TopicsPolicy

PROVIDER = "resend"
HOOKS = ("_send_queue", "_may_begin_send", "_begin_send")
LOGGER = logging.getLogger("docsuri.u8.topics")


@dataclasses.dataclass(frozen=True)
class LiveTopicsPolicy(TopicsPolicy):
    """The live policy. It adds no field: it refuses anything but real delivery with an
    integer allocation of 0, then checks every other field with U5's own rules."""

    def __post_init__(self):
        if self.synthetic_only is not False:
            raise ValueError("the live policy is real delivery")
        if type(self.real_send_limit) is not int or self.real_send_limit != 0:
            raise ValueError("the live policy spends the email allowance, not an allocation")
        values = {field.name: getattr(self, field.name)
                  for field in dataclasses.fields(TopicsPolicy)}
        # U5's rules, on the same values with the smallest allocation they accept.
        TopicsPolicy(**{**values, "real_send_limit": 1})


PRODUCTION_REHEARSAL_TOPICS = TopicsPolicy(
    policy_id="u5-production-rehearsal",
    synthetic_only=False,
    real_send_limit=100,
    real_evidence_retention_days=30,
)
PRODUCTION_LIVE_TOPICS = LiveTopicsPolicy(
    policy_id="u5-production-live",
    synthetic_only=False,
    real_send_limit=0,
    real_evidence_retention_days=30,
)


def is_live(policy) -> bool:
    return isinstance(policy, LiveTopicsPolicy)


class LiveDigestDelivery(DigestDelivery):
    """U5's delivery under the live policy: no single permitted recipient, and each
    attempt settles or releases the reservation its start took."""

    def __init__(self, transactions, corpus, *, mail, unsubscribe, policy, allowance):
        if not is_live(policy):
            raise ValueError("the live delivery takes the live policy only")
        if allowance is None:
            raise ValueError("the live delivery needs the email allowance")
        if getattr(mail, "gate", None) is None:
            raise ValueError("the live delivery needs an adapter behind the provider gate")
        super().__init__(transactions, corpus, mail=mail, unsubscribe=unsubscribe,
                         policy=policy)
        self.allowance = allowance

    def recipient_scope(self):
        """None: the scheduler holds every run until Resend is active in live mode, then
        serves every subscriber who consented (BR7.6)."""
        return None

    def first_effect_content(self, run, recipient) -> bytes:
        """The exact content a send of this prepared run would submit (BR7.3)."""
        return self.mail.preview_content(recipient, run["presentation"], run["request_key"])

    def attempt(self, sending, topic):
        reservation = sending.get("allowance_reservation")
        if reservation is None:
            raise ValueError("a live send carries its allowance reservation")
        terminal = super().attempt(sending, topic)
        if terminal is not None:
            if terminal["state"] == "sent":
                self.allowance.settle(reservation)
            elif terminal["state"] == "failed":
                self.allowance.release(reservation)
        return terminal


class AllowanceAdmission:
    """`begin_send`'s admission under the live policy: one place in the email allowance,
    reserved by the run's request key. A retried transaction keeps the first reservation;
    a full day or month leaves the run prepared to wait for the reset (BR7.4)."""

    def __init__(self, allowance):
        self.allowance = allowance
        self.reservation = None

    def __call__(self, run) -> bool:
        if self.reservation is None:
            try:
                self.reservation = self.allowance.reserve("digest", str(run["request_key"]))
            except AllowanceExhausted:
                return False
        return True

    def give_back(self) -> None:
        """Release the place, only when one was taken; nothing was attempted."""
        if self.reservation is not None:
            reservation, self.reservation = self.reservation, None
            self.allowance.release(reservation)


def begin_live_send(repository, run_id, *, policy, allowance):
    """Begin one live send. The sending row carries its reservation for the delivery to
    settle or release; a start that returns nothing or raises gives the place back."""
    if not is_live(policy):
        raise ValueError("a live send takes the live policy only")
    admission = AllowanceAdmission(allowance)
    try:
        sending = repository.begin_send(
            run_id, "real", real_send_limit=0,
            evidence_retention_days=policy.real_evidence_retention_days,
            admission=admission,
        )
    except BaseException:
        admission.give_back()
        raise
    if sending is None:
        admission.give_back()
        return None
    if admission.reservation is None:
        raise ValueError("a live send began without its allowance reservation")
    return dict(sending, allowance_reservation=admission.reservation)


class GatedTopicsScheduler(TopicsScheduler):
    """U5's scheduler behind the provider gate (BR7.2, BR7.3, BR7.6), through its three
    send hooks. Without the gate and its ports it refuses to start."""

    def __init__(self, transactions, preparation, delivery, *, policy, gate, recipients,
                 first_effects):
        missing = [hook for hook in HOOKS if not callable(TopicsScheduler.__dict__.get(hook))]
        if missing:
            raise ValueError("U5's scheduler lacks the send hooks " + ", ".join(missing))
        if gate is None or recipients is None or first_effects is None:
            raise ValueError("the gated scheduler needs the gate and its ports")
        if is_live(policy) != isinstance(delivery, LiveDigestDelivery) or (
            delivery.policy is not policy
        ):
            raise ValueError("the policy and the delivery do not belong together")
        if getattr(delivery.mail, "gate", None) is not gate:
            raise ValueError("the digest adapter reads another gate")
        super().__init__(transactions, preparation, delivery, policy=policy)
        self.gate, self.recipients, self.first_effects = gate, recipients, first_effects
        self.live = is_live(policy)

    # --- the gate ------------------------------------------------------------------------

    def _held_adapter(self) -> bool:
        return isinstance(self.delivery.mail, HeldDigestMail)

    def _open(self) -> bool:
        """Whether a send may begin now: Resend active, a real adapter, and the live
        policy only in live mode."""
        if require_state(self.gate, PROVIDER) != "active" or self._held_adapter():
            return False
        return not (self.live and self.gate.mode != "live")

    # --- U5's hooks ----------------------------------------------------------------------

    def _send_queue(self):
        if (
            self.gate.mode == "live"
            and require_state(self.gate, PROVIDER) == "held"
            and not self._held_adapter()
        ):
            self._record_first_effects()
        if not self._open():
            return []  # held: runs stay prepared and nothing is spent
        queued = super()._send_queue()
        return self._first_effect_queue(queued) if self.live else queued

    def _may_begin_send(self):
        """The gate read again just before a send begins: a hold that arrived during the
        pass leaves the run prepared."""
        return self._open()

    def _begin_send(self, run):
        if self.live:
            return begin_live_send(self.repository, run["id"], policy=self.policy,
                                   allowance=self.delivery.allowance)
        return super()._begin_send(run)

    # --- the first effect (BR7.3) --------------------------------------------------------

    def _preview(self, row, email) -> bytes:
        return self.delivery.mail.preview_content(email, row["presentation"], row["request_key"])

    def _maintainer_email(self):
        """The maintainer's address, the adapter's one permitted recipient: it scopes the
        maintainer's runs in the query itself."""
        return getattr(self.delivery.mail, "permitted_recipient", None)

    def _maintainers_runs(self, limit):
        """Prepared runs addressed to the maintainer, with the content a send would make.
        The address scopes the query, so other owners' runs never fill the page."""
        email = self._maintainer_email()
        if not email:
            return []
        found = []
        for run in self.repository.prepared_runs(limit, recipient=email):
            if not self.recipients.is_maintainer_account(run["account_id"]):
                continue
            facts = self.repository.system(
                lambda conn, run_id=run["id"]: conn.execute(
                    "SELECT presentation,request_key FROM topics.digest_run "
                    "WHERE id=%s AND state='prepared'", (run_id,),
                ).fetchone()
            )
            recipient = self.repository.digest_recipient(run["account_id"])
            if facts and facts["presentation"] and recipient["email"]:
                found.append((run, self._preview(facts, recipient["email"])))
        return found

    def _maintainers_settled(self, limit):
        """The maintainer's most recently moved runs that are no longer prepared, with the
        content a send of each would have made."""
        email = self._maintainer_email()
        if not email:
            return []
        rows = self.repository.system(
            lambda conn: conn.execute(
                "SELECT r.id,r.state,r.presentation,r.request_key,t.account_id "
                "FROM topics.digest_run r JOIN topics.followed_topic t ON t.id=r.topic_id "
                "WHERE r.state<>'prepared' AND "
                "(SELECT email FROM accounts.digest_recipient(t.account_id))=%s "
                "ORDER BY r.updated_at DESC,r.id LIMIT %s",
                (email, limit),
            ).fetchall()
        )
        return [
            (row, self._preview(row, email)) for row in rows
            if row["presentation"] and self.recipients.is_maintainer_account(row["account_id"])
        ]

    def _record_first_effects(self):
        """Each prepared run addressed to the maintainer is the held first effect; its
        exact content becomes the preview your decision approves. The same content gives
        the same preview, so every pass may record it again."""
        failure = None
        try:
            for _, content in self._maintainers_runs(self.policy.page_size):
                self.first_effects.record_preview(PROVIDER, content)
        except Exception as error:  # noqa: BLE001 - reduced to its class name below
            failure = type(error).__name__
        if failure is not None:
            # Nothing is sent while held, so a preview that could not be kept only waits.
            LOGGER.warning("first-effect preview not recorded (%s)", failure)

    def _first_effect_queue(self, queued):
        """The approved first effect goes strictly first.

        - While the approved run is prepared, it is the only run this pass may attempt.
        - If it was discarded or came out empty before any attempt, nothing goes: another
          subscriber's digest never takes its place (a new decision is needed).
        - Once it has been attempted, every other run is served as usual.
        - With no approved digest while Resend is active in live mode, nothing goes.
        """
        approved = self.first_effects.approved_content(PROVIDER)
        if approved is None:
            return []
        for run, content in self._maintainers_runs(self.policy.page_size):
            if hashlib.sha256(content).hexdigest() == approved:
                return [run]
        for run, content in self._maintainers_settled(self.policy.page_size):
            if hashlib.sha256(content).hexdigest() == approved:
                return [] if run["state"] in ("discarded", "empty") else queued
        return queued
