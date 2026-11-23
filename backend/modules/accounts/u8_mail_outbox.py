"""AccountAccess's account-mail outbox and its sender (U8 plan Step 53(h); your answer of
2026-11-02, L1-69 "Send from an outbox").

The four signed-out mail requests (registration, password reset, verification and
reactivation) store their message with its proof, in the proof's own transaction, and
answer at once, the same for every address. The sender, a thread of the host, sends it
afterwards through the entry's composed account mail, keeping reliability-design § 10's
tries. This is the "owned responsibility with known/unknown disposition" through which
U2's SD2-02 has an external send go.

- `queue(conn, ...)` writes one row, `ON CONFLICT (message_key) DO NOTHING`, its payload
  stored only protected under `account-mail:<key>`; a row holds no address.
- `AccountMailSender(entry, *, record_failure=None).run_once()` is one pass:
  1. ends, unsent, each row whose message its completion would no longer accept (its
     proof or challenge consumed or expired by the database's clock, or its account's
     state or revisions changed), before it reads the hold;
  2. reads the hold (`held_for_all`, default false) and sends nothing while it holds;
  3. takes the due rows one at a time, oldest first, each in one short transaction that
     locks the account `FOR NO KEY UPDATE`, then the proof or challenge `FOR SHARE`, then
     the row `FOR UPDATE SKIP LOCKED` (SD2-01's lock order), stamps `attempted_at` and
     reads the address from the account row;
  4. calls `deliver()` once per row taken, reading the hold again before each row:
     `accepted` deletes the row and names a local mailbox's delivery; `over_allowance`
     ends it unsent; `held` ends it only on a definite refusal (`refused(key)`, L1-73)
     and otherwise keeps it for a try `RETRY_SECONDS` later; an exception is logged by
     its type only (`accounts`, `mail.failed`) and records one failed run (L1-70). Each
     ending transaction locks in the same order as a take: account, then proof or
     challenge, then the row.
- `start()` runs passes on a daemon thread: one at once, then whenever the entry's
  `mail_waiting` is set, and otherwise every `WAKE_SECONDS`. The thread writes the beat
  (`accounts.mail_sender_beat`) on the wall clock at the start of every pass and before
  every delivery; `stop()` ends the loop after the delivery in flight, joins the thread
  and deletes the beat. `run_once()` alone writes no beat.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import threading
from collections.abc import Callable
from uuid import UUID

from backend.modules.accounts.integrations.account_mail import AccountMessage

OWNER = "accounts"
RETRY_SECONDS = 60.0
WAKE_SECONDS = 10.0
STOP_JOIN_SECONDS = 60.0

_REFERENCES = (
    "SELECT o.message_key,o.purpose,o.challenge_id,o.control_proof_id,"
    "coalesce(c.account_id,p.account_id) AS account_id FROM accounts.mail_outbox o "
    "LEFT JOIN accounts.challenge c ON c.id=o.challenge_id "
    "LEFT JOIN accounts.control_proof p ON p.id=o.control_proof_id"
)


def _wall_now() -> dt.datetime:
    """Real UTC time in every profile: the beat is another process's liveness (L1-68)."""
    return dt.datetime.now(dt.UTC)


def queue(conn, *, entry, message_key: str, purpose: str, payload: dict,
          now: dt.datetime, challenge_id: UUID | None = None,
          control_proof_id: UUID | None = None) -> None:
    """Store one waiting message in the caller's transaction. The payload, which holds no
    address, is stored only as `protect("account-mail:" + key, payload)` with its key
    version; a retried operation keeps one row."""
    protected = entry.protect("account-mail:" + str(message_key), payload)
    conn.execute(
        "INSERT INTO accounts.mail_outbox(message_key,purpose,challenge_id,control_proof_id,"
        "protected_payload,key_version,queued_at) VALUES(%s,%s,%s,%s,%s,%s,%s) "
        "ON CONFLICT (message_key) DO NOTHING",
        (message_key, purpose, challenge_id, control_proof_id, protected,
         entry.protection_version(protected), now),
    )


def beat_reader(transactions) -> Callable[[], dt.datetime | None]:
    """The sender's beat for ServiceOperations' background-work check: its `beat_at`, or
    None, in one short `accounts` read. The producer sees only this callable."""

    def read() -> dt.datetime | None:
        row = transactions.run(
            OWNER,
            lambda conn: conn.execute(
                "SELECT beat_at FROM accounts.mail_sender_beat WHERE singleton"
            ).fetchone(),
        )
        return None if row is None else row["beat_at"]

    return read


def accepts(purpose: str, account: dict | None, proof: dict | None) -> bool:
    """True while the message's completion would still accept it, by the checks that
    need no proof (`proof["live"]` is `expires_at > clock_timestamp()`)."""
    if account is None or proof is None or not proof["live"]:
        return False
    if proof["account_id"] != account["id"]:
        return False
    if purpose == "verification":
        return (not proof["consumed"] and account["active"] and not account["verified"]
                and proof["authority_revision"] == account["authority_revision"])
    if proof["consumed_at"] is not None:
        return False
    revisions = (proof["authority_revision"] == account["authority_revision"]
                 and proof["lifecycle_revision"] == account["lifecycle_revision"])
    if purpose == "password-reset":
        return account["active"] and account["lifecycle_state"] == "active" and revisions
    if purpose == "reactivation":
        return account["lifecycle_state"] == "withdrawn" and revisions
    return False


def _proof_table(reference: dict) -> tuple[str, UUID]:
    if reference["challenge_id"] is not None:
        return "challenge", reference["challenge_id"]
    return "control_proof", reference["control_proof_id"]


class AccountMailSender:
    """The host's sender of the outbox's messages (L1-69)."""

    def __init__(self, entry, *, record_failure: Callable[[], None] | None = None):
        self.entry = entry
        self.record_failure = record_failure
        self._stopping = threading.Event()
        self._thread: threading.Thread | None = None

    # --- one pass --------------------------------------------------------------------

    def run_once(self) -> None:
        """One pass on the caller's thread; it writes no beat."""
        self._pass(beat=False)

    def _pass(self, *, beat: bool) -> None:
        if beat:
            self._beat()
        self._end_unaccepted()
        if self._held():
            return
        cutoff = self.entry.clock() - dt.timedelta(seconds=RETRY_SECONDS)
        keys = self.entry.transactions.run(
            OWNER,
            lambda conn: [row["message_key"] for row in conn.execute(
                "SELECT message_key FROM accounts.mail_outbox WHERE attempted_at IS NULL "
                "OR attempted_at<=%s ORDER BY queued_at,message_key", (cutoff,),
            ).fetchall()],
        )
        for index, key in enumerate(keys):
            if beat and self._stopping.is_set():
                return
            if index and self._held():
                return
            self._one(key, beat=beat)

    def _held(self) -> bool:
        held_for_all = getattr(self.entry.account_mail, "held_for_all", None)
        return bool(callable(held_for_all) and held_for_all())

    def _end_unaccepted(self) -> None:
        """Step 1: end, unsent, every row its completion would no longer accept. It calls
        no provider, and takes the accounts in id order, then their proofs."""

        def end(conn):
            references = conn.execute(_REFERENCES).fetchall()
            if not references:
                return
            accounts = {row["id"]: row for row in conn.execute(
                "SELECT * FROM accounts.account WHERE id=ANY(%s) ORDER BY id "
                "FOR NO KEY UPDATE",
                (sorted({r["account_id"] for r in references if r["account_id"]}),),
            ).fetchall()}
            proofs = {}
            for table in ("challenge", "control_proof"):
                wanted = sorted({_proof_table(r)[1] for r in references
                                 if _proof_table(r)[0] == table})
                if wanted:
                    proofs |= {row["id"]: row for row in conn.execute(
                        f"SELECT *,expires_at>clock_timestamp() AS live FROM accounts.{table} "
                        "WHERE id=ANY(%s) ORDER BY id FOR SHARE", (wanted,),
                    ).fetchall()}
            for reference in references:
                proof = proofs.get(_proof_table(reference)[1])
                if not accepts(reference["purpose"], accounts.get(reference["account_id"]),
                               proof):
                    conn.execute("DELETE FROM accounts.mail_outbox WHERE message_key=%s",
                                 (reference["message_key"],))

        self.entry.transactions.run(OWNER, end)

    def _one(self, key, *, beat: bool) -> None:
        try:
            taken = self._take(key)
            if taken is None:
                return
            if beat:
                self._beat()
            payload = self.entry.reveal("account-mail:" + str(key), taken["protected_payload"])
            account_mail = self.entry.account_mail
            delivery = account_mail.deliver(AccountMessage(
                taken["purpose"], str(key), taken["account_id"],
                {**payload, "email": taken["email"]},
            ))
            self._finish(taken, delivery, account_mail)
        except Exception as error:  # noqa: BLE001 - logged by type, the row kept
            from backend.log_events import log_exception

            log_exception(OWNER, "mail.failed", error)
            self._failed()

    def _take(self, key) -> dict | None:
        """Step 3: take one due row in SD2-01's lock order, or None."""
        now = self.entry.clock()
        cutoff = now - dt.timedelta(seconds=RETRY_SECONDS)

        def take(conn):
            reference = conn.execute(
                _REFERENCES + " WHERE o.message_key=%s", (key,)
            ).fetchone()
            if reference is None or reference["account_id"] is None:
                return None
            account = conn.execute(
                "SELECT * FROM accounts.account WHERE id=%s FOR NO KEY UPDATE",
                (reference["account_id"],),
            ).fetchone()
            table, proof_id = _proof_table(reference)
            proof = conn.execute(
                f"SELECT *,expires_at>clock_timestamp() AS live FROM accounts.{table} "
                "WHERE id=%s FOR SHARE", (proof_id,),
            ).fetchone()
            row = conn.execute(
                "SELECT * FROM accounts.mail_outbox WHERE message_key=%s "
                "FOR UPDATE SKIP LOCKED", (key,),
            ).fetchone()
            if row is None:
                return None
            if row["attempted_at"] is not None and row["attempted_at"] > cutoff:
                return None
            if not accepts(row["purpose"], account, proof):
                conn.execute("DELETE FROM accounts.mail_outbox WHERE message_key=%s", (key,))
                return None
            conn.execute(
                "UPDATE accounts.mail_outbox SET attempted_at=%s WHERE message_key=%s",
                (now, key),
            )
            return {
                "message_key": str(key),
                "purpose": row["purpose"],
                "challenge_id": row["challenge_id"],
                "control_proof_id": row["control_proof_id"],
                "protected_payload": bytes(row["protected_payload"]),
                "account_id": account["id"], "email": account["email"],
            }

        return self.entry.transactions.run(OWNER, take)

    def _finish(self, taken: dict, delivery: str, account_mail) -> None:
        key = taken["message_key"]
        if delivery == "accepted":
            artifact_of = getattr(account_mail, "artifact_of", None)
            artifact = artifact_of(key) if callable(artifact_of) else None
            self._delete(key, taken, artifact)
            return
        if delivery == "over_allowance":
            # Its place was taken since the request's check: it ends unsent.
            self._delete(key, taken, None)
            return
        refused = getattr(account_mail, "refused", None)
        if callable(refused) and refused(key):
            # A definite refusal ends after its one delivery (L1-73); its place was
            # already released by `deliver()`. Otherwise the row keeps its retry.
            self._delete(key, taken, None)

    def _delete(self, key: str, taken: dict, artifact) -> None:
        """End a taken row in SD2-01's lock order, as `_take` does: the account
        `FOR NO KEY UPDATE`, then its proof (`FOR NO KEY UPDATE` when its payload is
        rewritten to name the delivery) or challenge `FOR SHARE`, and the row last. A local
        mailbox's delivery is named only while that proof or challenge is still the taken
        account's; otherwise only the row is deleted."""
        entry = self.entry
        table, proof_id = _proof_table(taken)
        strength = ("FOR NO KEY UPDATE" if table == "control_proof" and artifact is not None
                    else "FOR SHARE")

        def write(conn):
            account = conn.execute(
                "SELECT id FROM accounts.account WHERE id=%s FOR NO KEY UPDATE",
                (taken["account_id"],),
            ).fetchone()
            proof = conn.execute(
                f"SELECT account_id FROM accounts.{table} WHERE id=%s {strength}", (proof_id,),
            ).fetchone()
            conn.execute("DELETE FROM accounts.mail_outbox WHERE message_key=%s", (key,))
            if artifact is None or account is None or proof is None:
                return
            if proof["account_id"] != account["id"]:
                return
            if taken["challenge_id"] is not None:
                conn.execute(
                    "INSERT INTO accounts.delivery VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                    (taken["challenge_id"], artifact.name, artifact.sha256, artifact.size),
                )
            else:
                entry._name_delivery(conn, taken["control_proof_id"], artifact)

        entry.transactions.run(OWNER, write)

    def _failed(self) -> None:
        if self.record_failure is not None:
            self.record_failure()

    def _beat(self) -> None:
        moment = _wall_now()
        self.entry.transactions.run(
            OWNER,
            lambda conn: conn.execute(
                "INSERT INTO accounts.mail_sender_beat(singleton,beat_at) VALUES(true,%s) "
                "ON CONFLICT (singleton) DO UPDATE SET beat_at=excluded.beat_at", (moment,),
            ),
        )

    # --- the thread ----------------------------------------------------------------------

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("the account-mail sender is already started")
        self._stopping.clear()
        self._thread = threading.Thread(
            target=self._loop, name="account-mail-sender", daemon=True
        )
        self._thread.start()

    def _loop(self) -> None:
        first = True
        while not self._stopping.is_set():
            if not first:
                waiting = self.entry.mail_waiting
                # Read at each wait, so a test that sets the module's value is obeyed.
                waiting.wait(WAKE_SECONDS)
                waiting.clear()
                if self._stopping.is_set():
                    return
            first = False
            try:
                self._pass(beat=True)
            except Exception as error:  # noqa: BLE001 - logged by type; the next pass runs
                from backend.log_events import log_exception

                log_exception(OWNER, "mail.pass-failed", error)
                self._failed()

    async def stop(self) -> None:
        """End the loop after the delivery in flight, join the thread off the event loop
        for at most 60 s, then delete the beat in a guarded step."""
        self._stopping.set()
        self.entry.mail_waiting.set()
        thread, self._thread = self._thread, None
        if thread is not None:
            await asyncio.to_thread(thread.join, STOP_JOIN_SECONDS)
        try:
            self.entry.transactions.run(
                OWNER,
                lambda conn: conn.execute("DELETE FROM accounts.mail_sender_beat"),
            )
        except Exception as error:  # noqa: BLE001 - a beat left behind ages past 90 s
            from backend.log_events import log_exception

            log_exception(OWNER, "mail.beat-unremoved", error)
