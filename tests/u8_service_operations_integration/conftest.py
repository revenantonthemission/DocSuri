"""Fail-closed fixtures for an explicitly owned, unexpired U8 composed realm.

The realm is `service-operations` with database `docsuri_u8`, loaded only from
`DOCSURI_U8_ENVIRONMENT_FILE`. Behaviour runs through the owners' runtime logins; no
fixture writes another owner's tables by a test-only path. Fixtures that need modules
a later plan step builds import them lazily, so collection works from Step 1 on.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import json
import os
import secrets
import sys
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import psycopg
import pytest
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from backend.local_profile import LocalProfile, private_bytes
from backend.transactions import Authority, OwnerTransactions

REALM = "service-operations"
DATABASE = "docsuri_u8"
# The environment persists across phases; synthetic owners are bounded per realm.
MAX_SYNTHETIC_ACCOUNTS = 20

# The `arrangement` folder needs macOS's tools and sudo: it runs only in `ci.yml`'s
# `macos-filesystem` job, or through the tool's `arrangement` phase on this Mac, which
# set `DOCSURI_U8_ARRANGEMENT=1`. Everywhere else it is not collected at all (neither run
# nor skipped), so the Linux phases never meet it.
if os.environ.get("DOCSURI_U8_ARRANGEMENT") != "1":
    collect_ignore_glob = ["arrangement/*"]


class NetworkRefused(RuntimeError):
    """Raised by the test-wide stand-in for every network transport."""


def refuse_network_transport():
    raise NetworkRefused("tests never build a network transport")


@pytest.fixture(scope="session", autouse=True)
def no_network_transport():
    """For the whole run, building a real adapter's network transport fails, so no test
    can reach Google, ORCID, Resend or Notion (NFR6.3): Notion's transport, the Google and
    ORCID adapters' transport (Step 21), the shared Resend client (Step 21) and the shared
    model runtime's client (Step 21), so no test reaches 127.0.0.1:11434 either. Each
    adapter builds its network transport in that one place only."""
    from backend.modules.accounts.integrations import digest_email, identity_providers
    from backend.modules.export import notion_session
    from backend.modules.summarization import model_runtime

    patch = pytest.MonkeyPatch()
    patch.setattr(notion_session, "network_transport", refuse_network_transport)
    patch.setattr(identity_providers, "network_transport", refuse_network_transport)
    patch.setattr(model_runtime, "network_transport", refuse_network_transport)
    patch.setattr(digest_email, "network_client", lambda **_: refuse_network_transport())
    yield refuse_network_transport
    patch.undo()


REAL_RUN_ROOT = Path("/tmp/docsuri-u8-run")


def _real_evidence() -> set[str]:
    try:
        return {item.name for item in REAL_RUN_ROOT.glob("*-evidence-*.json")}
    except OSError:
        return set()


@pytest.fixture(autouse=True)
def no_evidence_in_the_real_run_root(request):
    """Every runner test runs on `phase_fakes` or on the `StandIn` with `RUN` at
    `tmp_path` (U8 plan Step 97(i)): an `operations/` test that leaves a new
    `*-evidence-*.json` in the real run root fails, so realm B's `verification-run` never
    meets foreign evidence."""
    if "operations" not in Path(str(request.node.path)).parts:
        yield
        return
    before = _real_evidence()
    yield
    left = sorted(_real_evidence() - before)
    if left:
        pytest.fail(f"the test left evidence in the real run root: {left}")


@pytest.fixture(scope="session")
def realm() -> LocalProfile:
    profile = LocalProfile.load(Path(os.environ["DOCSURI_U8_ENVIRONMENT_FILE"]))
    assert profile.realm == REALM and profile.database_name == DATABASE
    return profile


@pytest.fixture
def transactions(realm):
    value = OwnerTransactions(realm)
    yield value
    value.close()


@pytest.fixture
def connect(realm):
    """A raw login as `docsuri_<owner>`, bound to this run's database identity."""
    credentials = json.loads(private_bytes(realm.root / "owner-credentials.json"))
    assert credentials["runId"] == realm.run_id
    opened = []

    def open_connection(owner: str, *, autocommit: bool = False):
        conn = psycopg.connect(
            host="127.0.0.1",
            port=realm.database_port,
            dbname=realm.database_name,
            user=f"docsuri_{owner}",
            password=credentials["roles"][owner],
            connect_timeout=3,
            row_factory=dict_row,
            autocommit=autocommit,
        )
        assert (
            conn.execute("SELECT run_id FROM public.docsuri_local_identity").fetchone()["run_id"]
            == realm.run_id
        )
        if not autocommit:
            conn.commit()
        opened.append(conn)
        return conn

    yield open_connection
    for conn in opened:
        conn.close()


def _identities(realm, suffix: str):
    return [
        uuid5(NAMESPACE_URL, realm.run_id + item)
        for item in (f"u8-owner-{suffix}", f"u8-session-{suffix}", f"u8-authority-{suffix}")
    ]


def _make_account(connect, realm, *, suffix: str, administrator: bool = False) -> Authority:
    """A deterministic synthetic account with a full session, through the accounts
    owner's login. An administrator's session carries a completed second factor."""
    owner, session, revision = _identities(realm, suffix)
    with connect("accounts") as conn:
        conn.execute("LOCK TABLE accounts.account IN SHARE ROW EXCLUSIVE MODE")
        exists = conn.execute("SELECT id FROM accounts.account WHERE id=%s", (owner,)).fetchone()
        if (
            not exists
            and conn.execute("SELECT count(*) AS n FROM accounts.account").fetchone()["n"]
            >= MAX_SYNTHETIC_ACCOUNTS
        ):
            pytest.fail("Synthetic account allocation exhausted; a fresh owned realm is required")
        conn.execute(
            "INSERT INTO accounts.account(id,email,password_hash,verified,active,"
            "authority_revision,display_name) VALUES(%s,%s,'not-login-material',true,true,%s,"
            "'synthetic') ON CONFLICT(id) DO UPDATE SET active=true,verified=true,"
            "authority_revision=excluded.authority_revision",
            (owner, f"{owner}@fixture.invalid", revision),
        )
        conn.execute(
            "INSERT INTO accounts.consent(account_id,purpose,granted) VALUES(%s,'local-research',"
            "true) ON CONFLICT(account_id,purpose) DO UPDATE SET granted=true",
            (owner,),
        )
        conn.execute(
            "INSERT INTO accounts.session(id,account_id,token_hash,csrf_hash,authority_revision,"
            "expires_at) VALUES(%s,%s,%s,%s,%s,clock_timestamp()+interval '30 minutes') "
            "ON CONFLICT(id) DO UPDATE SET revoked=false,"
            "authority_revision=excluded.authority_revision,expires_at=excluded.expires_at",
            (session, owner, str(uuid4()), str(uuid4()), revision),
        )
        if administrator:
            # U2's control columns: the role, and the session's completed second factor.
            conn.execute(
                "UPDATE accounts.account SET role='administrator' WHERE id=%s", (owner,)
            )
            conn.execute(
                "UPDATE accounts.session SET purpose='full_session',mfa_at=clock_timestamp() "
                "WHERE id=%s",
                (session,),
            )
    with connect("personalization") as conn:
        conn.execute(
            "INSERT INTO personalization.settings(account_id,revision,defaults) VALUES(%s,%s,%s) "
            "ON CONFLICT(account_id) DO UPDATE SET revision=excluded.revision,"
            "defaults=personalization.settings.defaults || excluded.defaults",
            (owner, uuid4(), Jsonb({"timeZone": "UTC"})),
        )
    return Authority(owner, session)


# pytest imports this file as `u8_service_operations_integration.conftest`, and the test
# modules import it as `tests.u8_service_operations_integration.conftest`: two module
# objects in one process. A value generated at import is taken from whichever of the two
# made it first, so both hold the same one.
_MODULE_NAMES = ("u8_service_operations_integration.conftest",
                 "tests.u8_service_operations_integration.conftest")


def _process_value(attribute: str, make) -> str:
    for name in _MODULE_NAMES:
        value = getattr(sys.modules.get(name), attribute, None)
        if isinstance(value, str):
            return value
    return make()


# Generated at import, once per process (L1-36): `sign_in_account` writes this process's
# hash at each call, so a sign-in in the same process always meets it.
SIGN_IN_PASSWORD = _process_value(
    "SIGN_IN_PASSWORD", lambda: "synthetic-sign-in-" + secrets.token_hex(6))
_PASSWORD_HASH: dict[str, str] = {}


def sign_in_password_hash() -> str:
    if not _PASSWORD_HASH:
        from backend.modules.accounts.password import get_password_hasher

        _PASSWORD_HASH["value"] = get_password_hasher().hash(SIGN_IN_PASSWORD)
    return _PASSWORD_HASH["value"]


def settle_consent_obligations(realm, connect, account_id) -> None:
    """Run the lifecycle worker's own consent pass for one account's pending consent
    obligations (Personalization's boundary, PaperAssistance's research consent, then
    AccountAccess's acknowledgement), as `ControlWorker.run_once` does for every account.
    A reused sign-in account is reset only once nothing it decided is still pending, so
    the worker never meets an obligation whose consent the reset removed."""
    from types import SimpleNamespace

    from backend.artifacts import PrivateArtifacts
    from backend.control_worker import ControlWorker
    from backend.modules.accounts.control_cursor import ControlCursor
    from backend.modules.accounts.control_repository import ControlRepository
    from backend.modules.accounts.u8_control_policy import U8_SYNTHETIC_POLICY
    from backend.modules.accounts.u8_entry import CompleteControlEntryService
    from backend.modules.personalization.control_service import (
        PersonalizationControlService,
        ProducerBinding,
    )

    with connect("accounts") as conn:
        facts = conn.execute(
            "SELECT * FROM accounts.consent_obligation WHERE account_id=%s AND "
            "disposition='pending' ORDER BY accepted_at,id", (account_id,),
        ).fetchall()
    if not facts:
        return
    transactions = OwnerTransactions(realm)
    try:
        entry = CompleteControlEntryService(transactions, U8_SYNTHETIC_POLICY)
        personalization = PersonalizationControlService(
            transactions, U8_SYNTHETIC_POLICY,
            ControlCursor(bytes.fromhex(entry.verifier("cursor", "u2-controls-v1"))),
            producers=(ProducerBinding("Library"), ProducerBinding("CorpusContent")),
        )
        worker = ControlWorker(entry, SimpleNamespace(manifest=(), revision="none"),
                               personalization,
                               PrivateArtifacts.for_profile(realm, "assistance-files"))
        repository = ControlRepository(transactions, U8_SYNTHETIC_POLICY)
        for fact in facts:
            if fact["purpose"] == "personalization":
                evidence = UUID(personalization.apply_consent_boundary(fact)["evidenceRef"])
            else:
                evidence = worker.apply_research_consent(fact)
            repository.acknowledge_consent(fact["id"], fact["consent_revision"], evidence)
    finally:
        transactions.close()


@pytest.fixture
def sign_in_account(connect, realm):
    """A deterministic account in a chosen sign-in state (U8 plan Step 20), reset through
    the accounts owner's login: active and verified, `SIGN_IN_PASSWORD`, its sessions
    ended and no second factor. `consents=False` leaves it as a migrated account before
    its first sign-in (no v2 consent decision); `reset_required` marks it as an import
    without a usable password verifier. Returns the account's identity and email."""

    def make(suffix: str, *, role: str = "member", consents: bool = True,
             reset_required: bool = False) -> tuple[Authority, str]:
        authority = _make_account(
            connect, realm, suffix=suffix, administrator=role == "administrator"
        )
        # The wire's email format refuses `.invalid`; U2's HTTP tests use this domain.
        email = f"{authority.account_id}@fixture.example.com"
        with connect("accounts") as conn:
            conn.execute(
                "UPDATE accounts.account SET email=%s,password_hash=%s,verified=true,"
                "active=true,lifecycle_state='active',role=%s,reset_required=%s WHERE id=%s",
                (email, sign_in_password_hash(), role, reset_required, authority.account_id),
            )
            conn.execute("UPDATE accounts.session SET revoked=true WHERE account_id=%s",
                         (authority.account_id,))
            conn.execute(
                "UPDATE accounts.mfa_enrollment SET state='invalidated' WHERE account_id=%s "
                "AND state IN ('inactive','active')", (authority.account_id,),
            )
            # Consent rows present while the account's own decisions are settled.
            conn.execute(
                "INSERT INTO accounts.consent(account_id,purpose,granted) VALUES"
                "(%s,'local-research',true),(%s,'personalization',false) "
                "ON CONFLICT(account_id,purpose) DO NOTHING",
                (authority.account_id, authority.account_id),
            )
        settle_consent_obligations(realm, connect, authority.account_id)
        with connect("accounts") as conn:
            conn.execute("DELETE FROM accounts.consent WHERE account_id=%s",
                         (authority.account_id,))
            if consents:
                conn.execute(
                    "INSERT INTO accounts.consent(account_id,purpose,granted) VALUES"
                    "(%s,'local-research',true),(%s,'personalization',false)",
                    (authority.account_id, authority.account_id),
                )
        return authority, email

    return make


def activate_factor(connect, entry, account_id) -> str:
    """A completed second factor for `account_id`, as U2's enrolment leaves it: the seed
    protected under the entry's keyring, through the accounts owner's login. Returns the
    seed for `totp`."""
    import base64
    import secrets

    identifier, seed = uuid4(), base64.b32encode(secrets.token_bytes(20)).decode()
    protected = entry.protect("mfa:" + str(identifier), {"seed": seed, "codes": []})
    with connect("accounts") as conn:
        conn.execute(
            "UPDATE accounts.mfa_enrollment SET state='invalidated' WHERE account_id=%s "
            "AND state IN ('inactive','active')", (account_id,),
        )
        conn.execute(
            "INSERT INTO accounts.mfa_enrollment(id,account_id,key_version,ciphertext,"
            "delivery_hash,delivery_expires_at,delivered_at,state) VALUES(%s,%s,%s,%s,%s,"
            "clock_timestamp(),clock_timestamp(),'active')",
            (identifier, account_id, entry.protection_version(protected), protected,
             secrets.token_hex(32)),
        )
    return seed


def database_step(connect) -> int:
    """The TOTP step the database's clock is in (U2's factor check reads that clock)."""
    with connect("accounts") as conn:
        return int(conn.execute(
            "SELECT floor(extract(epoch FROM clock_timestamp())/30)::bigint AS step"
        ).fetchone()["step"])


ORIGIN = "https://127.0.0.1:18110"


def account_client(realm, entry, lifecycle=None, *, address: str | None = None):
    """An in-process client for AccountAccess's routers behind D7's boundary, at the
    composed realm's public authority. `address` is sent as `CF-Connecting-IP`, which the
    boundary reads on a public-origin request (D2). An entry with a first sign-in (U8's
    `CompleteControlEntryService`) gets U8's D1 routers; any other entry U2's built
    ones."""
    from fastapi.testclient import TestClient

    from backend.local_host import assemble
    from backend.modules.accounts.control_http import control_router
    from backend.modules.accounts.local_http import account_router
    from backend.modules.accounts.u8_control_http import d1_control_router
    from backend.modules.accounts.u8_local_http import d1_account_router
    from backend.production_boundary import BoundaryHosts, BuildManifest, ProductionBoundary

    d1 = getattr(entry, "first_sign_in", None) is not None
    routers = (d1_account_router(entry) if d1 else account_router(entry),)
    if lifecycle is not None:
        routers += ((d1_control_router if d1 else control_router)(entry, lifecycle),)
    boundary = ProductionBoundary(
        BoundaryHosts.for_profile(realm), BuildManifest.empty(realm.root), context=None
    )
    app = assemble(realm, routers=routers, boundary=boundary)
    headers = {"cf-connecting-ip": address} if address else {}
    return TestClient(app, base_url=ORIGIN, headers=headers, follow_redirects=False)


def post(client, path: str, body: dict, csrf: str, *, operation=None):
    return client.post(path, json=body, headers={
        "origin": ORIGIN, "x-csrf-token": csrf,
        "idempotency-key": str(operation or uuid4()),
    })


@pytest.fixture
def d1_entry(transactions, clock):
    """AccountAccess's entry service under the composed realm's D1-shaped policy, on the
    injected clock."""
    from backend.modules.accounts.u8_control_policy import U8_SYNTHETIC_POLICY
    from backend.modules.accounts.u8_entry import CompleteControlEntryService

    return CompleteControlEntryService(transactions, U8_SYNTHETIC_POLICY, clock=clock)


@pytest.fixture
def forget_waits(connect, d1_entry):
    """Emails of reused accounts whose sign-in failure rows a test leaves: removed
    afterwards, so failures never add up across tests to a wait (D2)."""
    emails: list[str] = []
    yield emails
    with connect("accounts") as conn:
        for email in emails:
            conn.execute("DELETE FROM accounts.entry_email_failure WHERE email_digest=%s",
                         (d1_entry.verifier("entry-email", email),))


@pytest.fixture
def own_address():
    """Count this test's entry attempts under an address of its own (D2), so no other
    test shares its per-address bucket."""
    from backend.modules.accounts.entry_limits import client_address

    value = f"198.18.{uuid4().int % 250 + 1}.{uuid4().int % 250 + 1}"
    with client_address(value):
        yield value


def _empty_outbox(connect) -> None:
    with connect("accounts") as conn:
        conn.execute("DELETE FROM accounts.mail_outbox")
        conn.execute("DELETE FROM accounts.mail_account_limit")


@pytest.fixture
def empty_outbox(connect):
    """AccountAccess's outbox (U8 plan Step 53(h), L1-69) and its per-account counts of
    account emails (Step 53(i), L1-71), emptied through the accounts owner's login before
    the test and again after it: no pass sends another test's message under this test's
    account mail or allowance, no served realm's sender later sends a test's message
    against the realm's own allowance, and no test inherits another's count."""
    _empty_outbox(connect)
    yield
    _empty_outbox(connect)


class ProviderStarts:
    """A test's own provider sign-in starts (U8 plan Step 20; the person's decision of
    2026-10-25, "Count every start, free places at once"). Each start counts under its
    address bucket and browser binding until its flow is deleted, so a test draws both
    from a uuid, tracks the flows it starts, and afterwards ages them past their expiry
    and runs AccountAccess's deletion pass: no later test or rerun meets them."""

    def __init__(self, connect, transactions):
        self.connect, self.transactions, self.flows = connect, transactions, []

    @staticmethod
    def address() -> str:
        """An IPv4 address of its own in 10.0.0.0/8."""
        value = uuid4().int
        return f"10.{value % 256}.{(value >> 8) % 256}.{(value >> 16) % 254 + 1}"

    @staticmethod
    def ipv6_48() -> str:
        """An IPv6 /48 of its own under 2001:db8::/32, as its prefix text (`2001:db8:x`)."""
        return f"2001:db8:{uuid4().int % 65_536:x}"

    @staticmethod
    def binding() -> str:
        return "binding-" + uuid4().hex

    @contextlib.contextmanager
    def at(self, address: str | None = None):
        """Count the enclosed starts under `address`, or under a fresh one of the test's
        own; yields the address."""
        from backend.modules.accounts.entry_limits import client_address

        value = address or self.address()
        with client_address(value):
            yield value

    def track(self, accepted: dict) -> dict:
        self.flows.append(UUID(accepted["flowId"]))
        return accepted

    def retire(self) -> None:
        if self.flows:
            with self.connect("accounts") as conn:
                conn.execute(
                    "UPDATE accounts.identity_flow SET expires_at=clock_timestamp()-"
                    "interval '2 minutes' WHERE id=ANY(%s)", (self.flows,))
        from backend.modules.accounts.u8_identity import expire_flows

        expire_flows(self.transactions, limit=10_000)


@pytest.fixture
def provider_starts(connect, transactions):
    starts = ProviderStarts(connect, transactions)
    yield starts
    starts.retire()


def provider_answer(service, accepted: dict, subject: str) -> str:
    """The fixture adapter's code for one flow, with a subject of the test's own: the
    flow's secret is read, never written, and the code is issued as the stand-in would."""
    from backend.modules.accounts.services.control_identity import IdentityClaims

    identifier = UUID(accepted["flowId"])
    provider = service.providers[accepted["provider"]]

    def read(conn):
        row = conn.execute("SELECT secret_ciphertext FROM accounts.identity_flow WHERE id=%s",
                           (identifier,)).fetchone()
        return service.entry.reveal("identity:" + str(identifier), row["secret_ciphertext"])

    secret = service.transactions.run("accounts", read)
    claims = IdentityClaims(provider.name, subject, provider.issuer, provider.audience,
                            secret["nonce"], None, {"displayName": "합성 연구자", "works": []})
    return provider.issue(claims, secret["verifier"])


@pytest.fixture
def authority(connect, realm):
    return _make_account(connect, realm, suffix="a")


@pytest.fixture
def authority_b(connect, realm):
    return _make_account(connect, realm, suffix="b")


@pytest.fixture
def administrator(connect, realm):
    return _make_account(connect, realm, suffix="admin", administrator=True)


class Clock:
    """The one injected clock: every due-time decision reads it (decision "One clock").

    Python code calls it; SQL receives the same instant as a parameter.
    """

    def __init__(self, start: dt.datetime | None = None):
        self.now = start or dt.datetime.now(dt.UTC)

    def __call__(self) -> dt.datetime:
        return self.now

    def advance(self, seconds: float) -> dt.datetime:
        self.now += dt.timedelta(seconds=seconds)
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def arrangement(tmp_path):
    """An `ArrangementPaths` and `Accounts` pair under a temporary prefix."""
    from docsuri_ops.arrangement.paths import Accounts, ArrangementPaths

    return ArrangementPaths.under(tmp_path / "prefix"), Accounts.for_tests()


@pytest.fixture
def ledger(tmp_path, clock):
    """An operations ledger in a private temporary folder."""
    from backend.modules.operations.ledger import LedgerStore

    folder = tmp_path / "ledger"
    folder.mkdir(mode=0o700)
    store = LedgerStore.open(folder, clock=clock)
    yield store
    store.close()


_UVICORN_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.access")


@pytest.fixture
def logging_state():
    """`log_events.configure` replaces the process's handlers; restore them afterwards
    (Step 80(a)). The three Uvicorn loggers start clean, so a `uvicorn.Config` built
    earlier in the process cannot hide a test's records behind its own handler."""
    import logging

    from backend import log_events

    names = (
        "", log_events.EVENTS_LOGGER, "docsuri", "backend", *log_events.QUIET_LOGGERS,
        *_UVICORN_LOGGERS,
    )
    loggers = [logging.getLogger(name) if name else logging.getLogger() for name in names]
    saved = [
        (logger, list(logger.handlers), logger.level, logger.propagate, logger.disabled)
        for logger in loggers
    ]
    current = log_events._CURRENT
    for name in _UVICORN_LOGGERS:
        logger = logging.getLogger(name)
        logger.handlers[:] = []
        logger.propagate = True
        logger.disabled = False
        logger.setLevel(logging.NOTSET)
    try:
        yield
    finally:
        for logger, handlers, level, propagate, disabled in saved:
            for handler in logger.handlers:
                if handler not in handlers:
                    handler.close()
            logger.handlers[:] = handlers
            logger.setLevel(level)
            logger.propagate = propagate
            logger.disabled = disabled
        log_events._CURRENT = current
