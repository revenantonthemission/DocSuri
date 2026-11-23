"""The test harness acting as you in the browser journeys (U8 plan Step 43; decision
"Recording your decisions in the realm": the harness acts as the maintainer, the web
application records no decision).

    backend/.venv/bin/python -m tests.u8_service_operations_integration.browser_harness \
        <word> < input.json

Each word is one of your operator actions on the composed realm, through the realm's own
operator, its bound operations, receipts and ledger, exactly as the operator tool runs
them; one JSON line answers `{"ok": true, "result": …}` or `{"ok": false, "reason": …}`:

- `advance-clock` `{seconds}`: the delegated fixture clock (`u8-fixture-clock.json`) the
  composed realm's one clock reads, moved forward from the later of its instant and now;
- `clock` `{}`: that clock as it reads now, unmoved;
- `service` `{name, action}`: PlatformControl's service control of the realm's `workers`
  or `scheduler` (`platform.service.control`), which the served realm's supervisor acts on;
- `recovery` `{word, recoveryRequestId}`: the operator's recovery word (`backup`,
  `verify`) on an administrator's admitted request;
- `proof` `{email, purpose}`: the newest delivered link of a synthetic account, read from
  the realm's local mailbox as U2's journeys read it, once it waits no longer: it first
  waits, at most 60 s (`PROOF_WAIT_SECONDS`), until the served realm's sender has sent
  every queued message of the account (L1-69);
- `tombstones` `{}`: the erasure register's account ids, read only;
- `lifecycle` `{accountId}`: a synthetic account's lifecycle requests and their
  participants' scopes, read only;
- `digests` `{accountId}`: a synthetic account's followed topics by `topicId`, each with
  its status and its digest runs' states, times, item counts, delivery outcomes and
  send-log path kinds, read only;
- `exports` `{accountId}`: a synthetic account's export approvals and effects with their
  states and their invalidation or outcome reasons, read only;
- `job` `{jobId}`: one research job's state and its artifact count, read only;
- `stage` `{word, …}`: a word of the cutover stage the migration and cutover journeys run
  against (`tests/u8_service_operations_integration/cutover_stage.py`), over its private
  socket in the run root.

It refuses the production profile and every environment but the composed realm's.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import socket
import sys
import time
import uuid
from pathlib import Path

RUN = Path("/tmp/docsuri-u8-run").resolve()
CLOCK_FILE = "u8-fixture-clock.json"
CLOCK_AHEAD = dt.timedelta(days=2)
LABELS = {"workers": "dev.docsuri.u8.run.workers", "scheduler": "dev.docsuri.u8.run.scheduler"}
STAGE_SOCKET = "cutover-stage.sock"
MAX_INPUT = 64 * 1024


class HarnessRefused(RuntimeError):
    pass


def profile():
    from docsuri_ops.u8_platform.platform_profile import U8PlatformProfile

    value = U8PlatformProfile.realm(RUN)
    if value.is_production:
        raise HarnessRefused("the harness never acts on the production profile")
    return value


def now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def advance_clock(document: dict) -> dict:
    from backend.local_profile import private_bytes
    from u8_fixtures import write_private

    seconds = document.get("seconds")
    if not isinstance(seconds, (int, float)) or not 0 < seconds <= 86400:
        raise HarnessRefused("advance-clock takes seconds within one day")
    current = now()
    run_id = profile().run_id
    path = RUN / CLOCK_FILE
    if path.exists():
        recorded = json.loads(private_bytes(path))
        if recorded.get("runId") != run_id:
            raise HarnessRefused("the fixture clock belongs to another run")
        current = max(current, dt.datetime.fromisoformat(recorded["instant"]))
    instant = current + dt.timedelta(seconds=seconds)
    if instant > now() + CLOCK_AHEAD:
        raise HarnessRefused("the fixture clock's allocation is exhausted")
    write_private(path, {"runId": run_id, "instant": instant.isoformat()})
    return {"instant": instant.isoformat()}


def read_clock(document: dict) -> dict:
    """The realm's delegated clock as it reads now (the later of its instant and now),
    without moving it: what a second factor's time step is computed against."""
    from backend.local_profile import private_bytes

    if document:
        raise HarnessRefused("clock takes no input")
    current, path = now(), RUN / CLOCK_FILE
    if path.exists():
        recorded = json.loads(private_bytes(path))
        if recorded.get("runId") != profile().run_id:
            raise HarnessRefused("the fixture clock belongs to another run")
        current = max(current, dt.datetime.fromisoformat(recorded["instant"]))
    return {"instant": current.isoformat()}


def operator_for(ledger):
    from docsuri_ops.u8_platform.u8_protocols import realm_operator

    return realm_operator(profile(), "operator", ledger, clock=now)


def service(document: dict) -> dict:
    from backend.modules.operations.ledger import Ledger

    label = LABELS.get(document.get("name"))
    action = document.get("action")
    if label is None or action not in ("start", "stop"):
        raise HarnessRefused("service takes a realm name and start or stop")
    ledger = Ledger.open(RUN / "ledger", clock=now)
    try:
        receipt = operator_for(ledger).execute(
            "platform.service.control", label, {"label": label, "action": action},
            key=f"browser-{action}-{uuid.uuid4().hex}")
    finally:
        ledger.close()
    if receipt["outcome"] != "succeeded":
        raise HarnessRefused(f"service control {receipt['outcome']}")
    return {"label": label, "action": action, "receiptId": receipt["receiptId"]}


def recovery(document: dict) -> dict:
    from backend.modules.operations.ledger import Ledger
    from docsuri_ops.u8_platform.recovery_words import realm_procedures, run_word

    word = document.get("word")
    operation = {"backup": "backup.create", "verify": "restore.verify"}.get(word)
    if operation is None:
        raise HarnessRefused("recovery takes backup or verify")
    from backend.modules.operations.http import MFA_SECONDS

    def mfa_current(requested_by: str, verified_at: str) -> bool:
        # The administrator's second factor as the served realm's C11 routes read it: a
        # request starts only within MFA_SECONDS of the factor that made it.
        # The factor's time is the database's (`control_mfa.verify`), and so is its age,
        # as the served realm reads it (`operations.http.mfa_current`).
        moment = dt.datetime.fromisoformat(verified_at.replace("Z", "+00:00"))
        return now() - moment < dt.timedelta(seconds=MFA_SECONDS)

    ledger = Ledger.open(RUN / "ledger", clock=now)
    try:
        wiring = realm_procedures(profile(), ledger, mfa_current=mfa_current)
        try:
            requests = wiring.procedures.requests
            request = document.get("recoveryRequestId")
            if request is None:
                # The administrator's newest open request of this operation (`requested`,
                # which `active` leaves out, or an active one), admitted by the operator in
                # person when it still waits.
                from backend.modules.operations.ledger_records import ACTIVE_RECOVERY_STATES

                open_states = ACTIVE_RECOVERY_STATES | {"requested"}
                waiting = sorted(
                    (item for item in ledger.records("recovery-request")
                     if item["operation"] == operation and item["environment"] == "live"
                     and item["state"] in open_states),
                    key=lambda item: item["createdAt"])
                if not waiting:
                    raise HarnessRefused(f"no active {operation} request")
                request = waiting[-1]["recoveryRequestId"]
            if requests.require(request)["state"] == "requested":
                requests.admit(request)
            result = run_word(word, {"recoveryRequestId": request}, wiring.procedures)
            answer = {"recoveryRequestId": request, "state": result.get("state"),
                      "result": result}
            if word == "verify":
                # The verification's own record: integrity and erased owners surviving.
                verification = str(uuid.uuid5(uuid.NAMESPACE_URL,
                                               f"docsuri-verification:{request}"))
                answer["verification"] = ledger.get("restore-verification", verification)
            return answer
        finally:
            wiring.close()
    finally:
        ledger.close()


def tombstones(document: dict) -> dict:
    """The erasure register's account ids (ServiceOperations' tombstones), read only."""
    from backend.modules.operations.ledger import Ledger
    from backend.modules.operations.tombstones import Tombstones

    if document:
        raise HarnessRefused("tombstones takes no input")
    ledger = Ledger.open(RUN / "ledger", clock=now)
    try:
        return {"accounts": [item["accountId"] for item in Tombstones(ledger).all()]}
    finally:
        ledger.close()


PROOF_PURPOSES = ("verify", "reactivate", "password-reset", "email-change")
SYNTHETIC_EMAIL = re.compile(r"[A-Za-z0-9._-]{1,64}@(u8\.fixture\.)?example\.com")
# How long `proof` waits for the served realm's sender (L1-69), and how often it reads.
PROOF_WAIT_SECONDS = 60
PROOF_POLL_SECONDS = 0.2


def mail_waiting(transactions, email: str) -> bool:
    """Whether AccountAccess's outbox still holds a message of the account at `email`,
    read through the accounts owner's run; it writes nothing."""

    def read(conn):
        return conn.execute(
            "SELECT 1 FROM accounts.mail_outbox o "
            "LEFT JOIN accounts.challenge c ON c.id=o.challenge_id "
            "LEFT JOIN accounts.control_proof p ON p.id=o.control_proof_id "
            "JOIN accounts.account a ON a.id=coalesce(c.account_id,p.account_id) "
            "WHERE lower(a.email)=lower(%s) LIMIT 1", (email,)).fetchone()

    return transactions.run("accounts", read) is not None


def pause() -> None:
    """One wait between two reads of the outbox."""
    time.sleep(PROOF_POLL_SECONDS)


def wait_for_sender(transactions, email: str) -> None:
    """Read again every 0.2 s until no message of the account waits, for at most
    `PROOF_WAIT_SECONDS`: the wait ends when the row does, never after a fixed sleep. A
    row that ended unsent leaves no named delivery, so `proof_for` then refuses."""
    deadline = time.monotonic() + PROOF_WAIT_SECONDS
    while mail_waiting(transactions, email):
        if time.monotonic() >= deadline:
            raise HarnessRefused("the account's mail was not sent within 60 s")
        pause()


def proof(document: dict) -> dict:
    """The newest fresh delivered link of one synthetic account from the realm's local
    mailbox (U2's own reader, `u2_browser_fixtures.proof_for`): what the person would
    open from their mail. Only the composed realm's synthetic accounts are read. It first
    waits for the served realm's sender (`wait_for_sender`, L1-69); it writes and sends
    nothing itself."""
    from backend.modules.accounts.u8_control_policy import U8_SYNTHETIC_POLICY
    from backend.modules.accounts.u8_entry import CompleteControlEntryService
    from backend.transactions import OwnerTransactions
    from u2_browser_fixtures import proof_for

    email, purpose = document.get("email"), document.get("purpose")
    # The fixtures' v2 accounts and the synthetic v1's migrated ones: both reserved
    # example.com addresses, never a person's.
    if not isinstance(email, str) or not SYNTHETIC_EMAIL.fullmatch(email):
        raise HarnessRefused("proof reads only the realm's synthetic accounts")
    if purpose not in PROOF_PURPOSES:
        raise HarnessRefused("proof takes a known link purpose")
    profile()  # the composed realm, never the production profile
    from backend.local_profile import LocalProfile

    transactions = OwnerTransactions(LocalProfile.load(RUN / "environment.json"),
                                     process="maintenance")
    try:
        wait_for_sender(transactions, email)
        value = proof_for(CompleteControlEntryService(transactions, U8_SYNTHETIC_POLICY),
                          email, purpose)
    finally:
        transactions.close()
    return {key: value[key] for key in ("challengeId", "flowBinding", "proof")}


def fixture_account_ids() -> set[str]:
    """The account ids the run's fixtures created (`fixtures/browser.json`), bound to this
    run; none when the fixtures have not run."""
    from backend.local_profile import private_bytes

    path = RUN / "fixtures" / "browser.json"
    if not path.exists():
        return set()
    record = json.loads(private_bytes(path))
    if record.get("runId") != profile().run_id:
        raise HarnessRefused("the fixture record belongs to another run")
    return {str(item["accountId"]) for item in record.get("accounts", {}).values()}


def lifecycle(document: dict) -> dict:
    """A synthetic account's lifecycle requests, newest first, each with its disposition
    and every participant's scopes, read only: what the lifecycle journeys wait on."""
    from backend.local_profile import LocalProfile
    from backend.transactions import OwnerTransactions

    profile()  # the composed realm, never the production profile
    try:
        account = uuid.UUID(str(document.get("accountId")))
    except ValueError:
        raise HarnessRefused("lifecycle takes an account id") from None
    transactions = OwnerTransactions(LocalProfile.load(RUN / "environment.json"),
                                     process="maintenance")

    # An erased account keeps no email, so a fixture account is known by the run's own
    # fixture record (`fixtures/browser.json`) as well as by its synthetic email.
    fixture_ids = fixture_account_ids()

    def read(conn):
        email = conn.execute("SELECT email FROM accounts.account WHERE id=%s",
                             (account,)).fetchone()
        synthetic = email is not None and SYNTHETIC_EMAIL.fullmatch(email["email"] or "")
        if not synthetic and str(account) not in fixture_ids:
            raise HarnessRefused("lifecycle reads only the realm's synthetic accounts")
        requests = conn.execute(
            "SELECT id,action,disposition,reason_key FROM accounts.lifecycle_request "
            "WHERE account_id=%s ORDER BY accepted_at DESC,id DESC LIMIT 10",
            (account,)).fetchall()
        return [{
            "lifecycleRequestId": str(item["id"]), "action": item["action"],
            "disposition": item["disposition"], "reasonKey": item["reason_key"],
            "scopes": [{"participant": row["participant"], "scope": row["scope"],
                        "disposition": row["disposition"], "reasonKey": row["reason_key"]}
                       for row in conn.execute(
                           "SELECT participant,scope,disposition,reason_key FROM "
                           "accounts.lifecycle_scope WHERE request_id=%s "
                           "ORDER BY participant,scope", (item["id"],)).fetchall()],
        } for item in requests]

    try:
        return {"requests": transactions.run("accounts", read)}
    finally:
        transactions.close()


def synthetic_account(transactions, document: dict, word: str) -> uuid.UUID:
    """The input's account, refused unless it is synthetic (`SYNTHETIC_EMAIL`) or in the
    run's fixture record, as `lifecycle` reads it."""
    try:
        account = uuid.UUID(str(document.get("accountId")))
    except ValueError:
        raise HarnessRefused(f"{word} takes an account id") from None
    fixture_ids = fixture_account_ids()

    def read(conn):
        return conn.execute("SELECT email FROM accounts.account WHERE id=%s",
                            (account,)).fetchone()

    email = transactions.run("accounts", read)
    synthetic = email is not None and SYNTHETIC_EMAIL.fullmatch(email["email"] or "")
    if not synthetic and str(account) not in fixture_ids:
        raise HarnessRefused(f"{word} reads only the realm's synthetic accounts")
    return account


def digests(document: dict) -> dict:
    """Each of a synthetic account's followed topics by its `topicId`, with its status
    and, for each of its digest runs, the run's state, created time, item count,
    delivery outcomes and send-log entry (its path kind, or none), read only (U8 plan
    Step 96(b)): what the digest journeys find a topic by."""
    from backend.local_profile import LocalProfile
    from backend.transactions import OwnerTransactions

    profile()  # the composed realm, never the production profile
    transactions = OwnerTransactions(LocalProfile.load(RUN / "environment.json"),
                                     process="maintenance")

    def read(conn, account):
        topics = conn.execute(
            "SELECT id,status FROM topics.followed_topic WHERE account_id=%s "
            "ORDER BY followed_at,id", (account,)).fetchall()
        answer = []
        for topic in topics:
            runs = conn.execute(
                "SELECT r.id,r.state,r.created_at,jsonb_array_length(r.digest_content) AS "
                "items,s.path_kind FROM topics.digest_run r LEFT JOIN topics.send_log_entry s "
                "ON s.run_id=r.id WHERE r.topic_id=%s ORDER BY r.created_at,r.id",
                (topic["id"],)).fetchall()
            answer.append({"topicId": str(topic["id"]), "status": topic["status"], "runs": [{
                "state": run["state"], "createdAt": run["created_at"].isoformat(),
                "items": run["items"],
                "outcomes": [{"observedState": row["observed_state"],
                              "reconciledState": row["reconciled_state"],
                              "failureReason": row["failure_reason"]}
                             for row in conn.execute(
                                 "SELECT observed_state,reconciled_state,failure_reason FROM "
                                 "topics.delivery_outcome WHERE run_id=%s ORDER BY observed_at,"
                                 "id", (run["id"],)).fetchall()],
                "sendLog": None if run["path_kind"] is None else {"pathKind": run["path_kind"]},
            } for run in runs]})
        return answer

    try:
        account = synthetic_account(transactions, document, "digests")
        return {"topics": transactions.run("topics", lambda conn: read(conn, account))}
    finally:
        transactions.close()


def exports(document: dict) -> dict:
    """A synthetic account's export approvals and effects, each with its state and its
    invalidation or outcome reason, read only (U8 plan Step 96(b))."""
    from backend.local_profile import LocalProfile
    from backend.transactions import OwnerTransactions

    profile()  # the composed realm, never the production profile
    transactions = OwnerTransactions(LocalProfile.load(RUN / "environment.json"),
                                     process="maintenance")

    def read(conn, account):
        approvals = conn.execute(
            "SELECT id,state,invalidation_reason FROM export.approval WHERE account_id=%s "
            "ORDER BY approved_at,id", (account,)).fetchall()
        effects = conn.execute(
            "SELECT id,approval_id,state,outcome_reason FROM export.effect WHERE "
            "account_id=%s ORDER BY accepted_at,id", (account,)).fetchall()
        return {
            "approvals": [{"approvalId": str(row["id"]), "state": row["state"],
                           "invalidationReason": row["invalidation_reason"]}
                          for row in approvals],
            "effects": [{"effectId": str(row["id"]), "approvalId": str(row["approval_id"]),
                         "state": row["state"], "outcomeReason": row["outcome_reason"]}
                        for row in effects],
        }

    try:
        account = synthetic_account(transactions, document, "exports")
        return transactions.run("export", lambda conn: read(conn, account))
    finally:
        transactions.close()


def job(document: dict) -> dict:
    """One research job's state and whether it holds a result, read only: what a journey
    waits on while its owner cannot read it (a revoked consent or session)."""
    from backend.local_profile import LocalProfile
    from backend.transactions import OwnerTransactions

    profile()  # the composed realm, never the production profile
    try:
        identifier = uuid.UUID(str(document.get("jobId")))
    except ValueError:
        raise HarnessRefused("job takes a job id") from None
    transactions = OwnerTransactions(LocalProfile.load(RUN / "environment.json"),
                                     process="maintenance")

    def read(conn):
        row = conn.execute("SELECT owner_id,state,error_code FROM research.job WHERE id=%s",
                           (identifier,)).fetchone()
        if row is None:
            raise HarnessRefused("no such job")
        artifacts = conn.execute(
            "SELECT count(*) AS n FROM research.artifact WHERE job_id=%s",
            (identifier,)).fetchone()["n"]
        return {"owner": row["owner_id"], "state": row["state"],
                "errorCode": row["error_code"], "artifacts": artifacts}

    def owner_email(conn, owner):
        found = conn.execute("SELECT email FROM accounts.account WHERE id=%s",
                             (owner,)).fetchone()
        return found["email"] if found else ""

    try:
        value = transactions.run("research", read)
        owner = value.pop("owner")
        if not SYNTHETIC_EMAIL.fullmatch(
                transactions.run("accounts", lambda conn: owner_email(conn, owner)) or ""):
            raise HarnessRefused("job reads only the realm's synthetic owners' jobs")
        return value
    finally:
        transactions.close()


def stage(document: dict) -> dict:
    """One word to the cutover stage over its private socket; the stage answers it."""
    path = RUN / STAGE_SOCKET
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(140)
        connection.connect(str(path))
        connection.sendall(json.dumps(document).encode() + b"\n")
        raw = b""
        while not raw.endswith(b"\n"):
            chunk = connection.recv(65536)
            if not chunk:
                break
            raw += chunk
    answer = json.loads(raw or b"{}")
    if not answer.get("ok"):
        raise HarnessRefused(str(answer.get("reason", "stage-refused")))
    return answer.get("result", {})


WORDS = {"advance-clock": advance_clock, "clock": read_clock, "service": service,
         "recovery": recovery, "proof": proof, "tombstones": tombstones,
         "lifecycle": lifecycle, "job": job, "stage": stage, "digests": digests,
         "exports": exports}


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parents[2]
    for entry in (root, root / "ingestion/src", root / "ops/src", root / "scripts"):
        if str(entry) not in sys.path:
            sys.path.insert(0, str(entry))
    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) != 1 or arguments[0] not in WORDS:
        print(json.dumps({"ok": False, "reason": "word-refused"}))
        return 1
    raw = sys.stdin.buffer.read(MAX_INPUT + 1)
    try:
        if len(raw) > MAX_INPUT:
            raise HarnessRefused("input exceeds its bound")
        document = json.loads(raw or b"{}")
        if not isinstance(document, dict):
            raise HarnessRefused("input must be one object")
        result = WORDS[arguments[0]](document)
    except Exception as error:  # noqa: BLE001 - one JSON answer for every refusal
        print(json.dumps({"ok": False, "reason": f"{type(error).__name__}: {error}"[:400]}))
        return 1
    print(json.dumps({"ok": True, "result": result}, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
