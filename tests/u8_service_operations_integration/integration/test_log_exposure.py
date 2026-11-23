"""No secret reaches any log, observation, incident or ledger record (U8 plan Step 86;
D11 "never logged", the unit-test instructions' exposure test; L1-36, L1-69, L1-70).

One run drives the flows that handle secrets through the complete host, with every logger
captured at DEBUG, and then looks for each secret it used in every place a record could
land: the host's log file, standard output and error, every captured record, the
observation rows and incident records the run wrote, and the ledgers. A second test forces
three database failures and reads the realm database's own log.
"""

from __future__ import annotations

import contextlib
import json
import logging
import secrets
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import psycopg
import pytest

from backend import log_events
from backend.local_browser import SESSION_COOKIE
from backend.modules.accounts.integrations.account_mail import LocalAccountMail
from backend.modules.accounts.local_http import ENTRY_COOKIE, ENTRY_POLICY
from backend.modules.accounts.u8_mail_outbox import RETRY_SECONDS, AccountMailSender
from backend.modules.operations.allowance import KIND as ALLOWANCE
from backend.modules.operations.allowance import LedgerAllowance
from backend.modules.operations.incidents import KIND as INCIDENT
from backend.modules.operations.incidents import Incidents
from backend.modules.operations.ledger import Ledger
from backend.transactions import Authority
from backend.u8_policy import SYNTHETIC_OPERATIONS
from tests.u8_service_operations_integration.conftest import (
    ORIGIN,
    SIGN_IN_PASSWORD,
    post,
)
from tests.u8_service_operations_integration.host_flows import (
    ADMINISTRATOR,
    MEMBER,
    OTHER_MEMBER,
    complete_host,
    fresh_client,
    session_of,
)
from tests.u8_service_operations_integration.integration.test_signed_in_search import (
    query as search_query,
)

pytestmark = pytest.mark.usefixtures("own_address", "empty_outbox")
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
OWN_PREFIXES = ("docsuri.", "backend.")
SDK_LOGGER = "docsuri.export.notion_sdk"
LOG_SETTINGS = {
    "log_min_messages": "log",
    "log_error_verbosity": "terse",
    "log_min_error_statement": "panic",
    "log_statement": "none",
    "log_min_duration_statement": "-1",
    "log_parameter_max_length": "0",
    "log_parameter_max_length_on_error": "0",
}


# --- every logger at DEBUG, each record captured once ----------------------------------


class Capture(logging.Handler):
    def __init__(self):
        super().__init__(logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def own(record: logging.LogRecord) -> bool:
    return record.name.startswith(OWN_PREFIXES) or record.name in ("docsuri", "backend")


def record_text(record: logging.LogRecord) -> str:
    """`docsuri.*` and `backend.*` records by `getMessage()`; every other record as
    `ThirdPartyFormatter` writes it (the template, the error type and the location)."""
    if own(record):
        return record.getMessage()
    return log_events.ThirdPartyFormatter().format(record)


@contextlib.contextmanager
def debug_capture():
    """The root and every `logging.Logger` in `loggerDict` at DEBUG, one capture handler on
    the root and on each logger whose `propagate` is False, and each logger's level,
    handlers and `propagate` flag restored afterwards (Step 86(b), (d))."""
    logging.getLogger(SDK_LOGGER)  # U6's SDK logger, present before the capture starts
    root = logging.getLogger()
    loggers = [root] + [
        logger for logger in list(logging.Logger.manager.loggerDict.values())
        if isinstance(logger, logging.Logger)
    ]
    saved = [(logger, logger.level, list(logger.handlers), logger.propagate)
             for logger in loggers]
    capture = Capture()
    try:
        for logger in loggers:
            logger.setLevel(logging.DEBUG)
            if logger is root or not logger.propagate:
                logger.addHandler(capture)
        yield capture
    finally:
        for logger, level, handlers, propagate in saved:
            logger.handlers[:] = handlers
            logger.setLevel(level)
            logger.propagate = propagate


@contextlib.contextmanager
def httpcore_quiet():
    """The test's own browser leg to the identity stand-in, a leg v2 never runs: httpcore
    writes its trace text itself, so every `httpcore*` logger is held at WARNING for it."""
    names = ["httpcore"] + [name for name in logging.Logger.manager.loggerDict
                            if name.startswith("httpcore.")]
    loggers = [logging.getLogger(name) for name in names]
    for logger in loggers:
        logger.setLevel(logging.WARNING)
    try:
        yield
    finally:
        for logger in loggers:
            logger.setLevel(logging.DEBUG)


# --- the realm's records ------------------------------------------------------------------


def sender_lines(folder: Path) -> list[dict]:
    lines = []
    for path in sorted(folder.glob("*.jsonl")) if folder.is_dir() else ():
        lines += [json.loads(raw) for raw in path.read_text().splitlines() if raw.strip()]
    return sorted((line for line in lines if line.get("kind") == "mail.sender"),
                  key=lambda line: json.dumps(line, sort_keys=True))


def mailbox_proof(entry, challenge_id) -> dict:
    """The local mailbox's message for one proof (after a sender pass)."""
    for path in entry.mail.root.glob("*.blob"):
        value = json.loads(path.read_text())
        if value.get("challengeId") == str(challenge_id):
            return value
    raise AssertionError("no mail for the proof")


def csrf_of(client) -> str:
    return client.get("/api/v2/session").json()["csrfToken"]


def entry_token(client) -> str:
    value = client.cookies.get(ENTRY_COOKIE)
    assert value
    return value


def account_row(connect, account_id) -> dict:
    with connect("accounts") as conn:
        return conn.execute("SELECT * FROM accounts.account WHERE id=%s",
                            (account_id,)).fetchone()


def session_ids(connect, accounts) -> set:
    with connect("accounts") as conn:
        return {row["id"] for row in conn.execute(
            "SELECT id FROM accounts.session WHERE account_id=ANY(%s)", (list(accounts),))}


# --- the flows ------------------------------------------------------------------------------


class Values:
    """Every checked value, and every email, which is checked in any letter case."""

    def __init__(self):
        self.exact: dict[str, str] = {}
        self.emails: set[str] = set()

    def add(self, name: str, value) -> None:
        value = str(value)
        assert len(value) >= 8, name  # a value short enough to occur by chance is useless
        self.exact[f"{name}#{len(self.exact)}"] = value

    def email(self, value: str) -> None:
        self.emails.add(value.lower())

    def found_in(self, text: str) -> list[str]:
        lower = text.lower()
        return ([name for name, value in self.exact.items() if value in text]
                + [f"email:{email}" for email in self.emails if email in lower])


def orcid_sign_in(host, realm, connect, transactions, sign_in_account, provider_starts,
                  values: Values, standin) -> uuid.UUID:
    """A migrated ORCID-only account's first sign-in through the identity stand-in, as
    test_first_sign_in.py's provider-only flow drives it. Returns the link to delete."""
    import httpx

    from tests.u8_service_operations_integration.integration.test_first_sign_in import (
        provider_only,
    )
    from u8_identity_standin import Identity, client_context, page_target

    account, email = sign_in_account(OTHER_MEMBER, consents=False)
    values.email(email)
    subject = f"0000-0002-{uuid4().int % 10_000:04d}-{uuid4().int % 10_000:04d}"
    link = provider_only(connect, transactions, account, subject)
    standin.sign_in_as("orcid", Identity(subject))
    policy = host.composition.parts["account-controls"]["entry"].control_policy
    with (provider_starts.at() as address,
          httpx.Client(verify=client_context(realm), timeout=10) as browser,
          fresh_client(host, address=address) as client):
        values.add("orcid-address", address)
        csrf = csrf_of(client)
        values.add("orcid-entry", entry_token(client))
        values.add("orcid-csrf", csrf)
        begun = post(client, "/api/v2/c02/access-begin-identity-flow", {
            "provider": "orcid", "intent": "sign_in", "returnRouteId": "account",
            "policyRef": policy.reference,
        }, csrf)
        assert begun.status_code == 200, begun.text
        redirect = provider_starts.track(begun.json())
        with httpcore_quiet():
            page = browser.get(page_target(redirect["authorizationUrl"]))
        assert page.status_code == 302, page.text
        back = urlsplit(page.headers["location"])
        query = {key: items[0] for key, items in parse_qs(back.query).items()}
        values.add("orcid-code", query["code"])
        values.add("orcid-state", query["state"])
        arrived = client.get("/api/v2/identity/callback/orcid", params={
            "flow": redirect["flowId"], "state": query["state"], "code": query["code"]})
        assert arrived.status_code == 200, arrived.text
        assert arrived.json()["state"] == "consent_pending"
        values.add("orcid-session", client.cookies[SESSION_COOKIE])
    return link


def reset_flow(host, connect, address, values: Values, email: str, new_password: str) -> None:
    """A reset request and its completion from one guest client, with one pass of the
    host's sender between them, since the request answers before its mail leaves (L1-69)."""
    entry = host.composition.parts["account-controls"]["entry"]
    with fresh_client(host, address=address) as guest:
        csrf = csrf_of(guest)
        values.add("reset-entry", entry_token(guest))
        values.add("reset-csrf", csrf)
        operation = uuid4()
        requested = post(guest, "/api/v2/c02/access-request-password-reset", {
            "email": email, "policyRef": entry.control_policy.reference}, csrf,
            operation=operation)
        assert requested.status_code == 200, requested.text
        host.app.state.account_mail_sender.run_once()
        identifier, _, _ = entry._mail_identity("password-reset", operation)
        mail = mailbox_proof(entry, identifier)
        values.add("reset-proof", mail["proof"])
        values.add("reset-binding", mail["flowBinding"])
        completed = post(guest, "/api/v2/c02/access-complete-password-reset", {
            "verification": {key: mail[key] for key in ("challengeId", "proof", "flowBinding")},
            "newPassword": new_password,
        }, csrf_of(guest))
        assert completed.status_code == 200, completed.text


def verification_flow(host, connect, address, values: Values, account_id, email) -> None:
    """The verification of a reused account made unverified, with one pass of the host's
    sender between its request and its completion."""
    entry = host.composition.parts["account-controls"]["entry"]
    with connect("accounts") as conn:
        conn.execute("UPDATE accounts.account SET verified=false WHERE id=%s", (account_id,))
    with fresh_client(host, address=address) as guest:
        csrf = csrf_of(guest)
        values.add("verify-entry", entry_token(guest))
        operation = uuid4()
        requested = post(guest, "/api/v2/c02/access-request-verification", {
            "email": email, "policyRef": ENTRY_POLICY}, csrf, operation=operation)
        assert requested.status_code == 200, requested.text
        host.app.state.account_mail_sender.run_once()
        challenge, _, _ = entry._mail_identity("verification", operation)
        mail = mailbox_proof(entry, challenge)
        values.add("verify-proof", mail["proof"])
        values.add("verify-binding", mail["flowBinding"])
        verified = post(guest, "/api/v2/c02/access-verify-email", {
            "verification": {key: mail[key] for key in ("challengeId", "proof", "flowBinding")},
        }, csrf_of(guest))
        assert verified.status_code == 200, verified.text
    assert account_row(connect, account_id)["verified"] is True


def signed_in_flows(host, values: Values, *, wrong: str, member_email: str,
                    other_email: str, question: str, search: str, body_text: str) -> None:
    client = host.client
    entry = host.composition.parts["account-controls"]["entry"]
    csrf_of(client)  # the bootstrap sets the entry cookie
    values.add("member-entry", entry_token(client))
    refused = post(client, "/api/v2/c02/access-login", {
        "email": member_email, "password": wrong, "policyRef": ENTRY_POLICY}, csrf_of(client))
    assert refused.status_code in (401, 403), refused.text
    signed = post(client, "/api/v2/c02/access-login", {
        "email": member_email, "password": SIGN_IN_PASSWORD, "policyRef": ENTRY_POLICY},
        csrf_of(client))
    assert signed.status_code == 200 and signed.json()["state"] == "authenticated", signed.text
    values.add("member-session", client.cookies[SESSION_COOKIE])
    csrf = csrf_of(client)
    values.add("member-csrf", csrf)
    found = post(client, "/api/v2/c05/search",
                 {"query": search_query(search), "page": {"limit": 5}}, csrf)
    assert found.status_code == 200, found.text
    malformed = client.post("/api/v2/c05/search", content=(
        '{"query": {"query": "' + body_text + '", "modeId": ').encode(), headers={
        "origin": ORIGIN, "x-csrf-token": csrf, "idempotency-key": str(uuid4()),
        "content-type": "application/json"})
    assert malformed.status_code == 422, malformed.text
    # The email change to another fixture account's address: the request is sent, and the
    # completion's pre-check refuses it.
    operation = uuid4()
    asked = post(client, "/api/v2/c02/access-request-email-change", {
        "currentProof": SIGN_IN_PASSWORD, "newEmail": other_email,
        "policyRef": entry.control_policy.reference}, csrf, operation=operation)
    assert asked.status_code == 200, asked.text
    identifier, _, _ = entry._mail_identity("email-change", operation)
    mail = mailbox_proof(entry, identifier)
    values.add("email-change-proof", mail["proof"])
    values.add("email-change-binding", mail["flowBinding"])
    completed = post(client, "/api/v2/c02/access-complete-email-change", {
        "verification": {key: mail[key] for key in ("challengeId", "proof", "flowBinding")},
    }, csrf_of(client))
    # The completion's pre-check raises PermissionError, which the account routes answer
    # as FORBIDDEN.
    assert completed.status_code in (403, 404), completed.text
    assert completed.json()["code"] == "FORBIDDEN", completed.text
    # A research question under a policy that is not the research policy's reference.
    research = host.composition.parts["research-workspace"]["service"]
    policy = dict(research.policy.reference(), revision="999")
    context = str(uuid4())
    turn = post(client, "/api/v2/c07/accept-research-turn", {
        "sessionId": str(uuid4()), "mode": "question", "text": question, "policy": policy,
        "scope": {"contextId": context, "publicPapers": [], "attachmentIds": [],
                  "webReferences": [], "scopePolicy": research.policy.reference()},
    }, csrf_of(client))
    assert (turn.status_code, turn.json()["code"]) == (503, "POLICY_UNRESOLVED"), turn.text


def notion_flow(transactions, connect, authority, tmp_path, values: Values) -> None:
    """A Notion connection through U6's real ExportService, NotionAdapter and NotionSession
    over a FakeNotion of the test's own; a second configure is refused with INVALID_TOKEN
    by a queued `users.me` answer whose `additional_data` carries the token."""
    from backend.modules.export.fake_notion import Answer
    from tests.u6_approved_export import service_flows as sf

    rig = sf.build(transactions, connect, authority, tmp_path)
    values.add("notion-token", rig.token)
    configured = rig.configure()
    rig.fake.queue("users.me", Answer.error(401, additional={"token": rig.token,
                                                            "detail": rig.token}))
    code = sf.refuse("configure", lambda: rig.configure(expected=configured["revision"]))
    assert code == "INVALID_TOKEN"


def worker_failure(host, monkeypatch, question: str) -> dict:
    """One worker pass whose research step raises with the planted question."""
    composition = host.composition
    execution = composition.parts["research-workspace"]["execution"]

    def failing_step():
        raise RuntimeError(question)

    monkeypatch.setattr(execution, "step", failing_step)
    try:
        return composition.worker.run_once(4)
    finally:
        monkeypatch.undo()


def producer_pass(host) -> None:
    from backend.modules.operations.observation_store import ObservationStore
    from backend.modules.operations.observations import Observations
    from backend.modules.operations.producers import ProducerSchedule
    from backend.u8_host import worker_producers

    composition = host.composition
    status = {"state": "running", "timeouts": 0}
    ProducerSchedule(
        worker_producers(composition, loop_status=lambda: status),
        Observations(ObservationStore(composition.transactions)),
        composition.policy, composition.clock,
    ).run_due()


def forced_sender_failure(host, connect, address, values: Values, email: str, question: str,
                          tmp_path) -> Path:
    """A second reset request, then one pass of a sender the test builds over the host's
    entry whose account mail raises with that request's proof, its address and the planted
    question; its failure counts in a folder of the test's own (L1-70). The row is then
    aged by RETRY_SECONDS through the accounts owner's login and the host's sender sends
    it with the account mail restored, so no row waits."""
    from backend.u8_counts import ProcessCounts

    composition = host.composition
    entry = composition.parts["account-controls"]["entry"]
    operation = uuid4()
    with fresh_client(host, address=address) as guest:
        asked = post(guest, "/api/v2/c02/access-request-password-reset", {
            "email": email, "policyRef": entry.control_policy.reference}, csrf_of(guest),
            operation=operation)
        assert asked.status_code == 200, asked.text
    _, _, key = entry._mail_identity("password-reset", operation)
    with connect("accounts") as conn:
        row = conn.execute("SELECT protected_payload FROM accounts.mail_outbox "
                           "WHERE message_key=%s", (key,)).fetchone()
    proof = entry.reveal("account-mail:" + str(key), bytes(row["protected_payload"]))["proof"]
    values.add("failed-proof", proof)

    class Raising:
        def deliver(self, message):
            raise RuntimeError(f"{proof} {message.payload['email']} {question}")

    folder = tmp_path / "evidence"
    counts = ProcessCounts(folder, "host", policy=composition.policy, clock=composition.clock)
    restored = entry.account_mail
    entry.account_mail = Raising()
    try:
        AccountMailSender(
            entry, record_failure=lambda: counts.record("mail.sender", failed=True)
        ).run_once()
    finally:
        entry.account_mail = restored
        counts.close()
    with connect("accounts") as conn:
        waiting = conn.execute("SELECT attempted_at FROM accounts.mail_outbox "
                               "WHERE message_key=%s", (key,)).fetchone()
        assert waiting is not None and waiting["attempted_at"] is not None
        conn.execute("UPDATE accounts.mail_outbox SET attempted_at=attempted_at-"
                     "(%s * interval '1 second') WHERE message_key=%s", (RETRY_SECONDS, key))
    host.app.state.account_mail_sender.run_once()
    with connect("accounts") as conn:
        assert conn.execute("SELECT 1 FROM accounts.mail_outbox WHERE message_key=%s",
                            (key,)).fetchone() is None
    return folder


# --- (b) --------------------------------------------------------------------------------------


def test_no_secret_reaches_any_log_observation_incident_or_ledger_record(
    realm, connect, transactions, sign_in_account, own_address, forget_waits, provider_starts,
    logging_state, capfd, tmp_path, monkeypatch, clock,
):
    from backend.modules.accounts.integrations.identity_providers import OrcidIdentityProvider
    from backend.u8_counts import counts_over
    from u8_identity_standin import CLIENTS, IdentityStandin, RecordedAnswers

    del logging_state  # restores the fixed set of loggers after the test's own restore
    values = Values()
    wrong, new_password = ("Wrong-" + secrets.token_hex(12) + "-7!Q",
                           "New-" + secrets.token_hex(12) + "-9!Z")
    question = "planted-question-" + secrets.token_hex(12)
    search = "planted-search-" + secrets.token_hex(12)
    body_text = "planted-body-" + secrets.token_hex(12)
    orcid_secret = "orcid-secret-" + secrets.token_urlsafe(24)
    canary_argument = "planted-argument-" + secrets.token_hex(12)
    for name, value in (("wrong-password", wrong), ("new-password", new_password),
                        ("right-password", SIGN_IN_PASSWORD), ("question", question),
                        ("search", search), ("body", body_text),
                        ("orcid-client-secret", orcid_secret),
                        ("psycopg-argument", canary_argument), ("address", own_address)):
        values.add(name, value)

    member, member_email = sign_in_account(MEMBER)
    admin, admin_email = sign_in_account(ADMINISTRATOR)
    migrated, migrated_email = sign_in_account(OTHER_MEMBER)
    forget_waits.append(member_email)
    for email in (member_email, admin_email, migrated_email):
        values.email(email)
    values.add("admin-hash-before", account_row(connect, admin.account_id)["password_hash"])
    accounts = (member.account_id, admin.account_id, migrated.account_id)
    sessions_before = session_ids(connect, accounts)

    realm_evidence = Path(realm.root) / "evidence"
    realm_lines_before = sender_lines(realm_evidence)
    ledger_folder = tmp_path / "own-ledger"
    ledger_folder.mkdir(mode=0o700)
    own_ledger = Ledger.open(ledger_folder, clock=clock)
    standin = IdentityStandin(realm)
    answers = RecordedAnswers(standin)
    exchanged: list[tuple[dict, dict]] = []
    handle = answers.handle

    def recording(request):
        answer = handle(request)
        form = {key: items[0] for key, items in parse_qs(request.content.decode()).items()}
        try:
            body = json.loads(answer.content or b"{}")
        except ValueError:
            body = {}
        exchanged.append((form, body if isinstance(body, dict) else {}))
        return answer

    answers.handle = recording

    def prepare(composition):
        entry = composition.parts["account-controls"]["entry"]
        providers = dict(getattr(entry, "identity_providers", None) or {})
        providers["orcid"] = OrcidIdentityProvider(
            client_id=CLIENTS["orcid"], client_secret=orcid_secret, origin=realm.origin,
            client_factory=answers.client_factory)
        entry.identity_providers = providers
        entry.account_mail = LocalAccountMail(
            entry.mail, allowance=LedgerAllowance(own_ledger, SYNTHETIC_OPERATIONS))

    link = None
    captured = None
    try:
        with complete_host(realm, address=own_address, prepare=prepare) as host:
            composition = host.composition
            started = composition.clock()
            operations_ledger = composition.parts["service-operations"]["ledger"]
            log_folder = tmp_path / "logs"
            log_events.configure("host", log_folder, production=False)
            with debug_capture() as captured, standin.running():
                # Positive controls written into the log first.
                canary = uuid4()
                log_events.log_event("host", "exposure.canary", objectId=canary)
                logging.getLogger("psycopg").warning("exposure canary %s", canary_argument)

                signed_in_flows(host, values, wrong=wrong, member_email=member_email,
                                other_email=admin_email, question=question, search=search,
                                body_text=body_text)
                member_authority = Authority(member.account_id,
                                             session_of(connect, member.account_id))
                reset_flow(host, connect, own_address, values, admin_email, new_password)
                values.add("admin-hash-after",
                           account_row(connect, admin.account_id)["password_hash"])
                verification_flow(host, connect, own_address, values, migrated.account_id,
                                  migrated_email)
                link = orcid_sign_in(host, realm, connect, transactions, sign_in_account,
                                     provider_starts, values, standin)
                # A registration of a taken address.
                with fresh_client(host, address=own_address) as guest:
                    registered = post(guest, "/api/v2/c02/access-register", {
                        "email": member_email, "password": wrong, "displayName": "연구자",
                        "policyRef": ENTRY_POLICY}, csrf_of(guest))
                    assert registered.status_code == 200, registered.text
                summaries = worker_failure(host, monkeypatch, question)
                notion_flow(transactions, connect, member_authority, tmp_path, values)
                sdk = logging.getLogger(SDK_LOGGER)
                assert sdk.level == logging.WARNING and sdk.propagate is False
                assert any(isinstance(handler, logging.NullHandler)
                           for handler in sdk.handlers)
                producer_pass(host)
                own_evidence = forced_sender_failure(host, connect, own_address, values,
                                                     member_email, question, tmp_path)
            now = composition.clock()
            for form, body in exchanged:
                for name in ("code_verifier", "client_secret"):
                    if form.get(name):
                        values.add(f"exchange-{name}", form[name])
                if body.get("id_token"):
                    values.add("exchange-id-token", body["id_token"])
            assert any(form.get("code_verifier") for form, _ in exchanged)
            # The ID token is one of Step 86(b)'s checked values: an exchange answer must
            # have carried it and it must be among the values (the batch-7 review).
            id_tokens = [body["id_token"] for _, body in exchanged if body.get("id_token")]
            assert id_tokens, "no recorded token exchange answer carried an id_token"
            assert set(id_tokens) <= set(values.exact.values())
            with connect("operations") as conn:
                observations = conn.execute(
                    "SELECT * FROM operations.observation_record WHERE observed_at>=%s",
                    (started,)).fetchall()
            incidents = operations_ledger.records(INCIDENT)
            open_work = Incidents(operations_ledger, environment=composition.environment
                                  ).open_for("background.work")
            realm_ledger_text = (operations_ledger.store.folder / "ledger.jsonl").read_text()
        with connect("accounts") as conn:
            for row in conn.execute(
                "SELECT id,token_hash,csrf_hash FROM accounts.session WHERE account_id=ANY(%s)",
                (list(accounts),),
            ):
                if row["id"] not in sessions_before:
                    values.add("session-token-hash", row["token_hash"])
                    values.add("session-csrf-hash", row["csrf_hash"])
        own_ledger_text = (ledger_folder / "ledger.jsonl").read_text()
        reservations = own_ledger.records(ALLOWANCE)
    finally:
        own_ledger.close()
        if link is not None:
            with connect("accounts") as conn:
                conn.execute("DELETE FROM accounts.identity_link WHERE id=%s", (link,))
        # The reused accounts back to their reset state.
        for suffix in (MEMBER, ADMINISTRATOR, OTHER_MEMBER):
            sign_in_account(suffix)
    out, err = capfd.readouterr()
    host_log = (tmp_path / "logs" / "host.log").read_text()

    # Positive controls: the absence checks below cannot pass on an empty capture.
    lines = [json.loads(raw) for raw in host_log.splitlines() if raw.strip()]
    assert any(line.get("event") == "exposure.canary" and line.get("objectId") == str(canary)
               for line in lines)
    assert any(line.get("logger") == "psycopg" and line.get("template") == "exposure canary %s"
               for line in lines)
    assert "research-execution" in summaries["chained"]["setAside"]
    assert any(line.get("event") == "item.set-aside" and line.get("errorType") == "RuntimeError"
               for line in lines)
    assert open_work is not None
    assert "worker-item:research-execution:pass" in open_work["correlationIds"]
    assert observations, "the producer pass wrote no observation row"
    assert reservations, "the test's own ledger holds no reservation"
    failed = [line for line in lines if line.get("component") == "accounts"
              and line.get("event") == "mail.failed"]
    assert len(failed) == 1 and failed[0]["errorType"] == "RuntimeError"
    assert counts_over(own_evidence, ("mail.sender",), now) == {"mail.sender": (1, 1)}
    own_lines = "\n".join(path.read_text() for path in sorted(own_evidence.glob("*.jsonl")))
    assert own_lines and values.found_in(own_lines) == []
    assert sender_lines(realm_evidence) == realm_lines_before
    assert len(captured.records) > 100

    places = {
        "host.log": host_log,
        "stdout": out,
        "stderr": err,
        "observations": "\n".join(json.dumps(row, default=str) for row in observations),
        "incidents": "\n".join(json.dumps(record, default=str) for record in incidents),
        "realm-ledger": realm_ledger_text,
        "own-ledger": own_ledger_text,
    }
    for index, record in enumerate(captured.records):
        places[f"record:{index}:{record.name}"] = record_text(record)
    found = {place: hits for place, text in places.items() if (hits := values.found_in(text))}
    assert found == {}


# --- (c) --------------------------------------------------------------------------------------


def test_forced_failures_leave_no_test_value_in_the_realm_database_log(
    realm, connect, sign_in_account,
):
    with connect("accounts") as conn:
        shown = {name: next(iter(conn.execute(f"SHOW {name}").fetchone().values()))
                 for name in LOG_SETTINGS}
    assert shown == LOG_SETTINGS, (
        "the realm database predates security-design § 7.2's log settings; "
        "set up a fresh realm", shown)
    _, email = sign_in_account(MEMBER)
    marker_one, marker_two = ("marker-" + secrets.token_hex(12),
                              "marker" + secrets.token_hex(12))
    with connect("accounts") as conn:
        with pytest.raises(psycopg.errors.UniqueViolation):
            conn.execute(
                "INSERT INTO accounts.account(id,email,password_hash,display_name) "
                "VALUES(%s,%s,'x','x')", (uuid4(), email))
        conn.rollback()
        with pytest.raises(psycopg.errors.InvalidTextRepresentation):
            conn.execute("SELECT %s::uuid", (marker_one,))
        conn.rollback()
        with pytest.raises(psycopg.errors.DivisionByZero):
            conn.execute(f"SELECT 1/(length('{marker_two}')-length('{marker_two}'))")
        conn.rollback()
        assert conn.execute("SELECT count(*) AS n FROM accounts.account WHERE email=%s",
                            (email,)).fetchone()["n"] == 1
    # The realm's container is named by its runId; integration phases run only on Docker.
    logs = subprocess.run(["docker", "logs", realm.run_id], capture_output=True, timeout=60,
                          check=False)
    assert logs.returncode == 0, logs.stderr.decode()[-2000:]
    text = logs.stdout.decode(errors="replace") + logs.stderr.decode(errors="replace")
    assert "database system is ready to accept connections" in text
    for value in (marker_one, marker_two, email):
        assert value not in text
    assert not [line for line in text.splitlines() if "DETAIL:" in line or "STATEMENT:" in line]
