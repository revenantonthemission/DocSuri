"""The real Google and ORCID adapters (U8 plan Step 22; A7, BR7.1, BR7.2, BR7.8, D3).

Every provider answer is recorded and served through a fake transport (`httpx.
MockTransport`) handed to the adapter; the test-wide guard refuses the adapters' own
network transport. ORCID's ID tokens are RS256 tokens signed by a key made for the test,
checked by v1's JWKS verification; Google's claims come from its recorded tokeninfo
answer, as v1's verifier asks for them. The sign-in flow runs through AccountAccess's
own identity service in the composed realm.
"""

from __future__ import annotations

import base64
import datetime as dt
import json
import time
from secrets import token_hex
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from uuid import UUID, uuid4

import httpx
import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from backend.modules.accounts.integrations import identity_providers
from backend.modules.accounts.integrations.identity_providers import (
    GoogleIdentityProvider,
    OrcidIdentityProvider,
    ProviderUnreachable,
    UnconfiguredIdentityProvider,
    production_identity_providers,
)
from backend.modules.accounts.integrations.oidc import pkce_challenge
from backend.modules.accounts.services.control_identity import FixtureIdentityProvider
from backend.modules.accounts.u8_identity import ArrivalIdentityService
from backend.modules.operations.ledger import Ledger
from backend.modules.operations.producers import ProviderProducer
from tests.u8_service_operations_integration.conftest import ProviderStarts

REFUSED = "tests never build a network transport"
CLIENT_ID = "docsuri-test-client.apps.example"
# Generated per run (L1-36), in the shapes the adapters read.
SECRET = "test-client-secret-" + token_hex(5)
GOOGLE_ID_TOKEN = "google-opaque-" + token_hex(8)


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def jwk(key, kid: str = "test-key") -> dict:
    numbers = key.public_key().public_numbers()
    return {"kty": "RSA", "kid": kid, "alg": "RS256", "use": "sig",
            "n": b64(numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")),
            "e": b64(numbers.e.to_bytes(3, "big"))}


def signed(claims: dict, key=KEY, kid: str = "test-key") -> str:
    header = b64(json.dumps({"alg": "RS256", "kid": kid}).encode())
    body = b64(json.dumps(claims).encode())
    signature = key.sign(f"{header}.{body}".encode(), padding.PKCS1v15(), hashes.SHA256())
    return f"{header}.{body}.{b64(signature)}"


class Provider:
    """The recorded answers of one provider, served through a fake transport."""

    def __init__(self, kind: str, claims: dict | None = None, *, fail: Exception | None = None,
                 token_key=KEY):
        self.kind, self.claims, self.fail, self.token_key = kind, claims or {}, fail, token_key
        self.requests: list[httpx.Request] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.fail is not None:
            raise self.fail
        path = request.url.path
        if self.kind == "google" and path == "/token":
            return httpx.Response(200, json={"id_token": GOOGLE_ID_TOKEN})
        if self.kind == "google" and path == "/tokeninfo":
            return httpx.Response(200, json=self.claims)
        if self.kind == "orcid" and path == "/oauth/token":
            return httpx.Response(200, json={"id_token": signed(self.claims, self.token_key)})
        if self.kind == "orcid" and path == "/oauth/jwks":
            return httpx.Response(200, json={"keys": [jwk(KEY)]})
        return httpx.Response(404)

    def factory(self, **options) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handle), **options)


def adapter(kind: str, provider: Provider, origin: str = "https://127.0.0.1:18110", **options):
    kind_class = GoogleIdentityProvider if kind == "google" else OrcidIdentityProvider
    return kind_class(client_id=CLIENT_ID, client_secret=SECRET, origin=origin,
                      client_factory=provider.factory, **options)


def google_claims(nonce: str, **changes) -> dict:
    return {"aud": CLIENT_ID, "iss": "https://accounts.google.com", "nonce": nonce,
            "sub": "google-subject-1", "email": "researcher@fixture.example.com",
            "email_verified": "true", **changes}


def orcid_claims(nonce: str, **changes) -> dict:
    return {"aud": CLIENT_ID, "iss": "https://orcid.org", "nonce": nonce,
            "sub": "0000-0002-0000-0001", "name": "합성 연구자",
            "exp": int(time.time()) + 600, **changes}


# 1. A valid sign-in yields the verified identity -----------------------------------------


def test_a_valid_google_sign_in_yields_the_verified_identity():
    provider = Provider("google", google_claims("n-1"))
    claims = adapter("google", provider).exchange("code-1", verifier="v" * 43, nonce="n-1")
    assert (claims.provider, claims.subject, claims.issuer, claims.audience) == (
        "google", "google-subject-1", "https://accounts.google.com", CLIENT_ID)
    assert claims.verified_email == "researcher@fixture.example.com" and claims.nonce == "n-1"
    exchange = parse_qs(provider.requests[0].content.decode())
    assert exchange["code_verifier"] == ["v" * 43]  # PKCE, as v1's verifier sends it
    assert exchange["redirect_uri"] == ["https://127.0.0.1:18110/sign-in/callback/google"]


def test_a_valid_orcid_sign_in_yields_its_subject_and_no_email():
    provider = Provider("orcid", orcid_claims("n-2"))
    claims = adapter("orcid", provider).exchange("code-2", verifier="w" * 43, nonce="n-2")
    assert (claims.provider, claims.subject, claims.issuer) == (
        "orcid", "0000-0002-0000-0001", "https://orcid.org")
    assert claims.verified_email is None and claims.profile["displayName"] == "합성 연구자"
    assert [request.url.path for request in provider.requests] == ["/oauth/token", "/oauth/jwks"]


def test_an_unverified_google_email_is_never_carried():
    provider = Provider("google", google_claims("n-3", email_verified="false"))
    assert adapter("google", provider).exchange(
        "code", verifier="v" * 43, nonce="n-3").verified_email is None


# 2. A wrong audience, issuer, nonce or signature is refused ------------------------------


@pytest.mark.parametrize(("kind", "changes"), [
    ("google", {"aud": "someone-else"}), ("google", {"iss": "https://evil.example"}),
    ("google", {"nonce": "replayed"}), ("google", {"sub": None}),
    ("orcid", {"aud": "someone-else"}), ("orcid", {"iss": "https://sandbox.orcid.org"}),
    ("orcid", {"nonce": "replayed"}), ("orcid", {"exp": int(time.time()) - 5}),
])
def test_a_wrong_claim_is_refused(kind, changes):
    claims = {**(google_claims if kind == "google" else orcid_claims)("expected"), **changes}
    with pytest.raises(PermissionError):
        adapter(kind, Provider(kind, claims)).exchange("code", verifier="v" * 43,
                                                         nonce="expected")


def test_an_orcid_token_signed_by_another_key_is_refused():
    provider = Provider("orcid", orcid_claims("n-4"), token_key=OTHER_KEY)
    with pytest.raises(PermissionError):
        adapter("orcid", provider).exchange("code", verifier="v" * 43, nonce="n-4")


# 3. A link is made only to a verified account --------------------------------------------


def identities(entry, provider: Provider) -> ArrivalIdentityService:
    entry.identity_providers = {"google": adapter("google", provider,
                                                  origin=entry.transactions.profile.origin)}
    return ArrivalIdentityService(
        entry, {name: FixtureIdentityProvider(name) for name in ("google", "orcid")})


def sign_in_through(service, provider: Provider, subject: str, email: str, starts):
    """One sign-in, from a browser and an address of the test's own (Step 20 item 9)."""
    binding = starts.binding()
    with starts.at():
        accepted = starts.track(service.begin(None, "google", "sign_in", binding, "account"))
    address = service.fixture_authorization(accepted)
    query = {key: values[0] for key, values in parse_qs(urlsplit(address).query).items()}
    provider.claims = google_claims(query["nonce"], sub=subject, email=email)
    return service.complete(UUID(accepted["flowId"]), accepted["state"], binding,
                            "recorded-code", service.providers["google"].callback, None)


def test_a_link_is_made_only_to_a_verified_account(connect, d1_entry, sign_in_account,
                                                   provider_starts):
    account, email = sign_in_account("sign-in-member")
    provider = Provider("google")
    service = identities(d1_entry, provider)
    subject, link = f"google-{uuid4().hex}", uuid4()
    # The provider's verified email matches the account, but no link exists: refused.
    with pytest.raises(PermissionError):
        sign_in_through(service, provider, subject, email, provider_starts)
    with connect("accounts") as conn:
        assert not conn.execute("SELECT 1 FROM accounts.identity_link WHERE subject=%s",
                                (subject,)).fetchone()
        conn.execute("INSERT INTO accounts.identity_link(id,account_id,provider,subject) "
                     "VALUES(%s,%s,'google',%s)", (link, account.account_id, subject))
    try:
        signed_in = sign_in_through(service, provider, subject, "anyone@fixture.example.com",
                                    provider_starts)
        assert signed_in.public["state"] == "authenticated"
        assert signed_in.public["session"]["accountId"] == str(account.account_id)
        with connect("accounts") as conn:
            conn.execute("UPDATE accounts.account SET verified=false WHERE id=%s",
                         (account.account_id,))
        with pytest.raises(PermissionError):
            sign_in_through(service, provider, subject, email, provider_starts)
    finally:
        with connect("accounts") as conn:
            conn.execute("DELETE FROM accounts.identity_link WHERE id=%s", (link,))
            conn.execute("UPDATE accounts.account SET verified=true WHERE id=%s",
                         (account.account_id,))


def test_the_authorization_address_carries_pkce_and_the_workspace_page(d1_entry,
                                                                       provider_starts):
    service = identities(d1_entry, Provider("google"))
    with provider_starts.at():
        accepted = provider_starts.track(service.begin(
            None, "google", "sign_in", provider_starts.binding(), "search"))
    address = urlsplit(service.fixture_authorization(accepted))
    assert (address.scheme, address.netloc) == ("https", "accounts.google.com")
    query = {key: values[0] for key, values in parse_qs(address.query).items()}
    assert query["redirect_uri"] == (d1_entry.transactions.profile.origin
                                     + "/sign-in/callback/google")
    assert query["state"] == accepted["state"] and query["client_id"] == CLIENT_ID
    assert query["code_challenge_method"] == "S256" and len(query["code_challenge"]) == 43
    assert query["code_challenge"] != pkce_challenge("not-the-flow-verifier")


# 4. A timeout leaves the provider unavailable ---------------------------------------------


@pytest.fixture
def activation_ledger(tmp_path, clock):
    folder = tmp_path / "operations-ledger"
    folder.mkdir(mode=0o700)
    value = Ledger.open(folder, clock=clock)
    yield value
    value.close()


@pytest.mark.parametrize("kind", ["google", "orcid"])
def test_a_timeout_leaves_the_provider_unavailable_until_it_answers(kind, activation_ledger):
    moments = [1000.0]
    provider = Provider(kind, fail=httpx.ReadTimeout("no answer"))
    real = adapter(kind, provider, clock=lambda: moments[0])
    with pytest.raises(ProviderUnreachable) as refused:
        real.exchange("code", verifier="v" * 43, nonce="n")
    assert isinstance(refused.value, TimeoutError)  # the browser gets the deadline answer
    assert not real.reachable()
    producer = ProviderProducer("provider." + kind, activation_ledger, reachable=real.reachable)
    observed = producer.observe(dt.datetime.now(dt.UTC))
    assert (observed.outcome, observed.reason) == ("unavailable", "provider-unreachable")
    moments[0] += 300  # the next renewal sees it again
    assert real.reachable()
    provider.fail = None
    provider.claims = (google_claims if kind == "google" else orcid_claims)("n")
    real.exchange("code", verifier="v" * 43, nonce="n")
    assert producer.observe(dt.datetime.now(dt.UTC)).outcome == "available"


# Selection and the network guard ---------------------------------------------------------


def test_only_the_production_profile_selects_the_real_adapters(realm):
    environment = {"googleClientId": CLIENT_ID, "googleClientSecret": SECRET,
                   "orcidClientId": "APP-TEST", "orcidClientSecret": SECRET}
    assert production_identity_providers(realm, environment) == {}
    production = SimpleNamespace(is_production=True, origin="https://docsuri.rvnnt.dev")
    chosen = production_identity_providers(production, environment)
    assert {name: item.callback for name, item in chosen.items()} == {
        "google": "https://docsuri.rvnnt.dev/sign-in/callback/google",
        "orcid": "https://docsuri.rvnnt.dev/sign-in/callback/orcid"}
    # A refused short secret, generated per run (L1-36).
    partial = production_identity_providers(production, {**environment,
                                                         "orcidClientSecret": token_hex(2)})
    # The provider without its secret is registered unconfigured, never as a fixture
    # (your decision of 2026-10-24).
    assert isinstance(partial["google"], GoogleIdentityProvider)
    assert isinstance(partial["orcid"], UnconfiguredIdentityProvider)
    assert partial["orcid"].callback == "https://docsuri.rvnnt.dev/sign-in/callback/orcid"


# No fixture sign-in in production (Step 22 gains; your decision of 2026-10-24) ------------


def test_under_the_production_profile_no_fixture_adapter_is_ever_chosen():
    from backend.u8_host import PolicyUnresolved, require_no_fixture

    production = SimpleNamespace(is_production=True, origin="https://docsuri.rvnnt.dev")
    for environment in ({}, {"googleClientId": CLIENT_ID, "googleClientSecret": SECRET}):
        chosen = production_identity_providers(production, environment)
        assert set(chosen) == {"google", "orcid"}
        assert not any(isinstance(item, FixtureIdentityProvider) for item in chosen.values())
        require_no_fixture(chosen)  # what `build_account_controls` checks in production
    with pytest.raises(PolicyUnresolved):
        require_no_fixture({"google": FixtureIdentityProvider("google"),
                            "orcid": UnconfiguredIdentityProvider("orcid",
                                                                  origin=production.origin)})
    with pytest.raises(PolicyUnresolved):
        require_no_fixture({"google": UnconfiguredIdentityProvider(
            "google", origin=production.origin)})


class Unwritten:
    """Owner transactions that fail the test if anything is written."""

    profile = SimpleNamespace(origin="https://docsuri.rvnnt.dev")

    def run(self, owner, work):
        raise AssertionError("an unconfigured provider's begin wrote a record")


def test_an_unconfigured_providers_begin_is_refused_before_any_record_is_written(tmp_path):
    origin = "https://docsuri.rvnnt.dev"
    entry = SimpleNamespace(
        transactions=Unwritten(), control_policy=SimpleNamespace(d1_shaped=True),
        identity_providers={name: UnconfiguredIdentityProvider(name, origin=origin)
                            for name in ("google", "orcid")})
    service = ArrivalIdentityService(
        entry, {name: FixtureIdentityProvider(name) for name in ("google", "orcid")})
    # The unconfigured adapters replace the fixtures at the arrival page.
    assert all(isinstance(item, UnconfiguredIdentityProvider)
               for item in service.providers.values())
    for name in ("google", "orcid"):
        with pytest.raises(TimeoutError):  # refused as a provider timeout is
            service.begin(None, name, "sign_in", ProviderStarts.binding(), "account")
    unconfigured = service.providers["google"]
    assert unconfigured.reachable() is False
    with pytest.raises(ProviderUnreachable):
        unconfigured.exchange("code", verifier="v" * 43, nonce="n")
    # U8 plan Step 107(d): in production a configured adapter's start reads the
    # provider's activation first, before anything is written.
    from backend.modules.accounts.u8_control_policy import Admission

    entry.identity_providers = {"google": adapter("google", Provider("google"), origin=origin),
                                "orcid": UnconfiguredIdentityProvider("orcid", origin=origin)}
    entry.control_policy = SimpleNamespace(d1_shaped=True, realm="production")
    production = ArrivalIdentityService(
        entry, {name: FixtureIdentityProvider(name) for name in ("google", "orcid")})

    def begin():
        production.begin(None, "google", "sign_in", ProviderStarts.binding(), "account")

    with pytest.raises(TimeoutError):  # production without an identity gate
        begin()
    gates = LiveGates(tmp_path)
    try:
        failed = gates.make(uuid4())
        failed.fail_verification("google")
        entry.identity_gate = failed
        with pytest.raises(TimeoutError):
            begin()
        entry.identity_gate = gates.make(uuid4())  # google held
        with pytest.raises(AssertionError, match="wrote a record"):
            begin()  # a held provider still starts in the window
        entry.admission = Admission("open")
        with pytest.raises(TimeoutError):
            begin()
    finally:
        gates.close()


# Step 54(g)-(i): ten seconds a call, no retry, and a timed-out sign-in ends (L1-27) ------


class Recording(Provider):
    """A provider whose client factory records its options; per path, an answer may be
    replaced by an exception or a status."""

    def __init__(self, kind: str, claims: dict | None = None, *, answers=None, **options):
        super().__init__(kind, claims, **options)
        self.answers = dict(answers or {})
        self.options: list[dict] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        answer = self.answers.get(request.url.path)
        if answer is None:
            return super().handle(request)
        self.requests.append(request)
        if isinstance(answer, Exception):
            raise answer
        return httpx.Response(answer, json={"error": "server_error"})

    def factory(self, **options) -> httpx.AsyncClient:
        self.options.append(options)
        return super().factory(**options)

    def paths(self) -> list[str]:
        return [request.url.path for request in self.requests]


class AsyncioProxy:
    """`identity_providers`' own `asyncio` attribute, recording each `wait_for` timeout."""

    def __init__(self, real):
        self.real, self.timeouts = real, []

    def wait_for(self, awaitable, timeout):
        self.timeouts.append(timeout)
        return self.real.wait_for(awaitable, timeout)

    def __getattr__(self, name):
        return getattr(self.real, name)


TEN = {"connect": 10.0, "read": 10.0, "write": 10.0, "pool": 10.0}


def test_each_call_and_the_exchange_have_ten_seconds(monkeypatch):
    assert identity_providers.TIMEOUT_SECONDS == 10.0
    proxy = AsyncioProxy(identity_providers.asyncio)
    monkeypatch.setattr(identity_providers, "asyncio", proxy)
    google = Recording("google", google_claims("n-g"))
    adapter("google", google).exchange("code", verifier="v" * 43, nonce="n-g")
    orcid = Recording("orcid", orcid_claims("n-o"))
    adapter("orcid", orcid).exchange("code", verifier="v" * 43, nonce="n-o")
    assert google.paths() == ["/token", "/tokeninfo"]
    assert orcid.paths() == ["/oauth/token", "/oauth/jwks"]
    for provider in (google, orcid):
        assert provider.options == [{"timeout": 10.0}] * 2
        assert [request.extensions["timeout"] for request in provider.requests] == [TEN] * 2
    assert proxy.timeouts == [10.0, 10.0]


def test_no_failure_is_retried():
    for failure in (httpx.ReadTimeout("slow"), httpx.ConnectError("refused")):
        for kind, first, second in (("google", "/token", "/tokeninfo"),
                                    ("orcid", "/oauth/token", "/oauth/jwks")):
            claims = (google_claims if kind == "google" else orcid_claims)("n")
            at_token = Recording(kind, claims, answers={first: failure})
            with pytest.raises(ProviderUnreachable):
                adapter(kind, at_token).exchange("code", verifier="v" * 43, nonce="n")
            assert at_token.paths() == [first]
            at_second = Recording(kind, claims, answers={second: failure})
            with pytest.raises(ProviderUnreachable):
                adapter(kind, at_second).exchange("code", verifier="v" * 43, nonce="n")
            assert at_second.paths() == [first, second]
    for kind, first, second in (("google", "/token", "/tokeninfo"),
                                ("orcid", "/oauth/token", "/oauth/jwks")):
        claims = (google_claims if kind == "google" else orcid_claims)("n")
        for path in (first, second):
            failing = Recording(kind, claims, answers={path: 500})
            with pytest.raises(PermissionError):
                adapter(kind, failing).exchange("code", verifier="v" * 43, nonce="n")
            assert failing.paths().count(path) == 1
    # ORCID asks for its keys a second time only when the token's key is not among them.
    known = Recording("orcid", orcid_claims("n"))
    adapter("orcid", known).exchange("code", verifier="v" * 43, nonce="n")
    assert known.paths().count("/oauth/jwks") == 1
    unknown_key = Recording("orcid", orcid_claims("n"))
    original = unknown_key.handle

    def rotated(request):
        if request.url.path == "/oauth/token":
            unknown_key.requests.append(request)
            return httpx.Response(200, json={"id_token": signed(
                orcid_claims("n"), kid="rotated-key")})
        return original(request)

    unknown_key.handle = rotated
    with pytest.raises(PermissionError):
        adapter("orcid", unknown_key).exchange("code", verifier="v" * 43, nonce="n")
    assert unknown_key.paths().count("/oauth/jwks") == 2


def test_a_timed_out_sign_in_ends_and_signing_in_again_is_a_new_exchange(
    connect, d1_entry, sign_in_account, provider_starts,
):
    account, _ = sign_in_account("sign-in-member")
    provider = Recording("google", answers={"/token": httpx.ReadTimeout("slow")})
    service = identities(d1_entry, provider)
    subject, link = f"google-{uuid4().hex}", uuid4()
    with connect("accounts") as conn:
        conn.execute("INSERT INTO accounts.identity_link(id,account_id,provider,subject) "
                     "VALUES(%s,%s,'google',%s)", (link, account.account_id, subject))
    try:
        starts = []
        for _ in range(2):
            binding = provider_starts.binding()
            with provider_starts.at():
                accepted = provider_starts.track(
                    service.begin(None, "google", "sign_in", binding, "account"))
            address = service.fixture_authorization(accepted)
            query = {key: values[0] for key, values in parse_qs(urlsplit(address).query).items()}
            starts.append((accepted, binding, query))
        (timed, timed_binding, timed_query), (again, binding, query) = starts
        callback = service.providers["google"].callback
        with pytest.raises(TimeoutError):  # the deadline answer
            service.complete(UUID(timed["flowId"]), timed["state"], timed_binding,
                             "timed-out-code", callback, None)
        sent = len(provider.requests)
        with pytest.raises(PermissionError):  # never exchanged again
            service.complete(UUID(timed["flowId"]), timed["state"], timed_binding,
                             "timed-out-code", callback, None)
        assert len(provider.requests) == sent
        assert sum("timed-out-code" in request.content.decode()
                   for request in provider.requests) == 1
        # A new sign-in is a new exchange: a new state, nonce and code challenge.
        assert again["state"] != timed["state"]
        assert query["nonce"] != timed_query["nonce"]
        assert query["code_challenge"] != timed_query["code_challenge"]
        provider.answers.clear()
        provider.claims = google_claims(query["nonce"], sub=subject)
        before = len(provider.requests)
        signed_in = service.complete(UUID(again["flowId"]), again["state"], binding,
                                     "new-code", callback, None)
        assert signed_in.public["state"] == "authenticated"
        tokens = [request for request in provider.requests[before:]
                  if request.url.path == "/token"]
        assert len(tokens) == 1
        verifier = parse_qs(tokens[0].content.decode())["code_verifier"][0]
        assert pkce_challenge(verifier) == query["code_challenge"]
    finally:
        with connect("accounts") as conn:
            conn.execute("DELETE FROM accounts.identity_link WHERE id=%s", (link,))


# 5. Sign-in reads the provider's activation (U8 plan Step 107(d); BR7.8, CP-3) ------------


class LiveGates:
    """Live ProviderActivations of the test's own, each on a ledger of its own in a
    `tmp_path` folder (0700) with a conftest `Clock()` of its own, so the switch's week
    never moves `d1_entry`'s clock; every provider configured, started: `google` held."""

    def __init__(self, tmp_path):
        self.tmp, self.ledgers = tmp_path, []

    def make(self, maintainer: UUID):
        from backend.modules.operations.provider_activation import (
            PROVIDERS,
            ActivationSettings,
            ProviderActivation,
        )
        from tests.u8_service_operations_integration.conftest import Clock

        folder = self.tmp / f"identity-gate-{len(self.ledgers)}"
        folder.mkdir(mode=0o700)
        (folder / "ledger").mkdir(mode=0o700)
        clock = Clock()
        ledger = Ledger.open(folder / "ledger", clock=clock)
        self.ledgers.append(ledger)
        settings = ActivationSettings("live", maintainer, frozenset(PROVIDERS),
                                      folder / "previews")
        activation = ProviderActivation(ledger, settings, clock=clock)
        activation.start()
        return activation

    def close(self) -> None:
        for ledger in self.ledgers:
            ledger.close()


def started(service, starts, authority=None, intent: str = "sign_in"):
    """A Google start from a browser and an address of the test's own."""
    binding = starts.binding()
    with starts.at():
        accepted = service.begin(authority, "google", intent, binding, "account")
    return starts.track(accepted), binding


def finished(service, provider: Provider, flow, subject: str, authority=None):
    """The provider's answer for `subject`, and the flow's completion."""
    accepted, binding = flow
    address = service.fixture_authorization(accepted)
    query = {key: values[0] for key, values in parse_qs(urlsplit(address).query).items()}
    provider.claims = google_claims(query["nonce"], sub=subject,
                                    email=f"{subject}@fixture.example.com")
    return service.complete(UUID(accepted["flowId"]), accepted["state"], binding,
                            "recorded-code", service.providers["google"].callback, authority)


def flow_count(connect) -> int:
    with connect("accounts") as conn:
        return conn.execute("SELECT count(*) AS n FROM accounts.identity_flow").fetchone()["n"]


def denied_without_session(connect, flow) -> bool:
    identifier = UUID(flow[0]["flowId"])
    with connect("accounts") as conn:
        row = conn.execute("SELECT disposition FROM accounts.identity_flow WHERE id=%s",
                           (identifier,)).fetchone()
        session = conn.execute("SELECT 1 FROM accounts.session WHERE flow_id=%s",
                               (identifier,)).fetchone()
    return row["disposition"] == "denied" and session is None


def link_of(connect, subject: str):
    with connect("accounts") as conn:
        return conn.execute("SELECT id FROM accounts.identity_link WHERE subject=%s",
                            (subject,)).fetchone()


def test_a_held_sign_in_provider_admits_only_the_maintainer_in_live_mode(
        connect, d1_entry, sign_in_account, provider_starts, tmp_path, monkeypatch):
    from backend.modules.accounts.u8_control_policy import Admission
    from tests.u8_service_operations_integration import cutover_flows as cf
    from tests.u8_service_operations_integration.conftest import activate_factor

    maintainer, _ = sign_in_account("held-google-maintainer", role="administrator")
    other, _ = sign_in_account("held-google-administrator", role="administrator")
    member, member_email = sign_in_account("held-google-member")
    for account in (maintainer, other):
        activate_factor(connect, d1_entry, account.account_id)
    subjects = {account.account_id: f"google-{uuid4().hex}"
                for account in (maintainer, other, member)}
    links = [uuid4() for _ in subjects]
    provider = Provider("google")
    service = identities(d1_entry, provider)
    gates = LiveGates(tmp_path)
    try:
        with connect("accounts") as conn:
            for link, (account_id, subject) in zip(links, subjects.items(), strict=True):
                conn.execute("INSERT INTO accounts.identity_link(id,account_id,provider,"
                             "subject) VALUES(%s,%s,'google',%s)", (link, account_id, subject))
        gate = gates.make(maintainer.account_id)
        monkeypatch.setattr(d1_entry, "identity_gate", gate, raising=False)
        monkeypatch.setattr(d1_entry, "admission", Admission("maintainer-only"))
        # The maintainer signs in through held Google in the window.
        mine = finished(service, provider, started(service, provider_starts),
                        subjects[maintainer.account_id])
        assert mine.public["state"] == "mfa_required"
        # Another administrator, admitted by admission, is refused at the outcome.
        flow = started(service, provider_starts)
        with pytest.raises(PermissionError):
            finished(service, provider, flow, subjects[other.account_id])
        assert denied_without_session(connect, flow)
        # A member's flow started in the window and completed after opening: the outcome
        # reads the gate again.
        flow = started(service, provider_starts)
        monkeypatch.setattr(d1_entry, "admission", Admission("open"))
        with pytest.raises(PermissionError):
            finished(service, provider, flow, subjects[member.account_id])
        assert denied_without_session(connect, flow)
        # Once admission opens, held Google starts for nobody: the member's browser and
        # the maintainer's.
        before = flow_count(connect)
        for _ in range(2):
            with pytest.raises(TimeoutError):
                started(service, provider_starts)
        assert flow_count(connect) == before
        # Google approved on a provider-sign-in decision in the switch.
        cf.switching(gate.ledger, gate.clock)
        gate.approve("google", *cf.provider_decision(gate.ledger, "google", now=gate.clock()))
        signed = finished(service, provider, started(service, provider_starts),
                          subjects[member.account_id])
        assert signed.public["state"] == "authenticated"
        assert member_email.startswith(str(member.account_id))
    finally:
        gates.close()
        with connect("accounts") as conn:
            conn.execute("DELETE FROM accounts.identity_link WHERE id=ANY(%s)", (links,))


def test_a_link_through_a_held_provider_starts_and_completes_only_for_the_maintainer(
        connect, d1_entry, authority, provider_starts, tmp_path, monkeypatch):
    provider = Provider("google")
    service = identities(d1_entry, provider)
    gates = LiveGates(tmp_path)
    made: list[str] = []
    try:
        others = gates.make(uuid4())  # a gate whose maintainer is another account
        monkeypatch.setattr(d1_entry, "identity_gate", others, raising=False)
        before = flow_count(connect)
        with pytest.raises(TimeoutError):
            started(service, provider_starts, authority, "link")
        assert flow_count(connect) == before
        mine = gates.make(authority.account_id)
        d1_entry.identity_gate = mine
        flow = started(service, provider_starts, authority, "link")
        d1_entry.identity_gate = others  # the gate is read again at completion
        subject = f"google-{uuid4().hex}"
        with pytest.raises(PermissionError):
            finished(service, provider, flow, subject, authority)
        assert link_of(connect, subject) is None
        d1_entry.identity_gate = mine
        second = f"google-{uuid4().hex}"
        made.append(second)
        linked = finished(service, provider, started(service, provider_starts, authority,
                                                     "link"), second, authority)
        assert linked["provider"] == "google" and link_of(connect, second) is not None
    finally:
        gates.close()
        with connect("accounts") as conn:
            conn.execute("DELETE FROM accounts.identity_link WHERE subject=ANY(%s)", (made,))


def test_an_adapter_without_a_fake_transport_reaches_no_network():
    # The guard's exception, matched by its message: the conftest module is loaded by
    # pytest under its own name.
    real = GoogleIdentityProvider(client_id=CLIENT_ID, client_secret=SECRET,
                                  origin="https://127.0.0.1:18110")
    with pytest.raises(RuntimeError, match=REFUSED):
        real.exchange("code", verifier="v" * 43, nonce="n")
    with pytest.raises(RuntimeError, match=REFUSED):
        identity_providers.network_transport()


# 6. The sign-in providers' circuit breaker (U8 plan Step 162(f); L4-11) -------------------------


class StoredStates:
    """The sign-in providers' states, derived as the composition derives them
    (`readiness.observed_state`, production's policy) from observations stored in a
    production stand-in's own database, read at the real clock: the clock each stored
    observation's age is built against."""

    CAPABILITIES = ("provider.google", "provider.orcid")

    def __init__(self, standin):
        from backend.modules.operations.observation_store import ObservationStore

        self.store = ObservationStore(standin.transactions)

    def __call__(self) -> dict[str, dict]:
        from backend.modules.operations.readiness import observed_state
        from backend.u8_policy import PRODUCTION_OPERATIONS

        latest = self.store.latest(list(self.CAPABILITIES))
        now = dt.datetime.now(dt.UTC)
        return {name: observed_state(name, latest.get(name), now,
                                     PRODUCTION_OPERATIONS).brief()
                for name in self.CAPABILITIES}

    def observe(self, kind: str, outcome: str, *, age: int = 0) -> None:
        """One observation of the provider, as its producer records it."""
        from backend.modules.operations.observations import Observations
        from backend.u8_registry import CAPABILITY_BY_ID

        capability = "provider." + kind
        producer = CAPABILITY_BY_ID[capability].producer
        observations = Observations(self.store)
        row = observations.make(
            capability, producer, outcome,
            reason=None if outcome == "available" else "provider-unreachable",
            observed_at=dt.datetime.now(dt.UTC) - dt.timedelta(seconds=age))
        assert observations.record(producer, [row])["written"] == 1


def rehearsal_activation(folder, maintainer: UUID):
    """A rehearsal ProviderActivation on a ledger of its own: every provider active."""
    from backend.modules.operations.provider_activation import (
        PROVIDERS,
        ActivationSettings,
        ProviderActivation,
    )
    from tests.u8_service_operations_integration.conftest import Clock

    folder.mkdir(mode=0o700)
    (folder / "ledger").mkdir(mode=0o700)
    clock = Clock()
    ledger = Ledger.open(folder / "ledger", clock=clock)
    activation = ProviderActivation(
        ledger, ActivationSettings("rehearsal", maintainer, frozenset(PROVIDERS),
                                   folder / "previews"), clock=clock)
    activation.start()
    return activation, ledger


def claims_of(kind: str, nonce: str, subject: str) -> dict:
    if kind == "google":
        return google_claims(nonce, sub=subject, email=f"{subject}@fixture.example.com")
    return orcid_claims(nonce, sub=subject)


def begun(service, starts, kind: str):
    binding = starts.binding()
    with starts.at():
        accepted = service.begin(None, kind, "sign_in", binding, "account")
    return starts.track(accepted), binding


def completed(service, provider: Provider, kind: str, flow, subject: str):
    accepted, binding = flow
    address = service.fixture_authorization(accepted)
    query = {key: values[0] for key, values in parse_qs(urlsplit(address).query).items()}
    provider.claims = claims_of(kind, query["nonce"], subject)
    return service.complete(UUID(accepted["flowId"]), accepted["state"], binding,
                            "recorded-code", service.providers[kind].callback, None)


def disposition_of(connect, flow) -> str:
    with connect("accounts") as conn:
        return conn.execute("SELECT disposition FROM accounts.identity_flow WHERE id=%s",
                            (UUID(flow[0]["flowId"]),)).fetchone()["disposition"]


@pytest.mark.parametrize(("kind", "subject"), [
    ("google", "google-breaker-subject-162"), ("orcid", "0000-0002-0000-0162")],
    ids=["google", "orcid"])
def test_while_a_sign_in_provider_is_observed_unavailable_no_start_is_written_and_no_exchange_is_called(  # noqa: E501
        realm, connect, d1_entry, sign_in_account, provider_starts, tmp_path, monkeypatch,
        kind, subject):
    """Reliability-design § 10 (lines 133-137, 141), L4-11: while provider.google or
    provider.orcid is observed unavailable, a sign-in start is refused with the deadline
    answer before anything is written, and a flow started earlier is refused at its
    completion before any token request and stays pending; once the provider is observed
    available it completes. `unknown` and `stale` start as built."""
    from backend.u8_outward import ObservedProviderGate, sign_in_gate
    from tests.u8_service_operations_integration import host_flows

    # The file's own member account (a realm holds 20 synthetic accounts; no new one).
    account, _ = sign_in_account("sign-in-member")
    provider, link = Provider(kind), uuid4()
    d1_entry.identity_providers = {kind: adapter(
        kind, provider, origin=d1_entry.transactions.profile.origin)}
    service = ArrivalIdentityService(
        d1_entry, {name: FixtureIdentityProvider(name) for name in ("google", "orcid")})
    activation, ledger = rehearsal_activation(tmp_path / "identity-breaker", account.account_id)
    with connect("accounts") as conn:
        conn.execute("DELETE FROM accounts.identity_link WHERE provider=%s AND subject=%s",
                     (kind, subject))
        conn.execute("INSERT INTO accounts.identity_link(id,account_id,provider,subject) "
                     "VALUES(%s,%s,%s,%s)", (link, account.account_id, kind, subject))
    try:
        with host_flows.production_stand_in(realm) as standin:
            states = StoredStates(standin)
            gate = sign_in_gate(activation, states)
            assert isinstance(gate, ObservedProviderGate) and gate.activation is activation
            monkeypatch.setattr(d1_entry, "identity_gate", gate, raising=False)
            capability = "provider." + kind

            assert states()[capability]["state"] == "unknown"
            earlier = begun(service, provider_starts, kind)  # unknown: starts as built
            states.observe(kind, "unavailable", age=901)
            assert states()[capability]["state"] == "stale"
            begun(service, provider_starts, kind)  # stale: starts as built

            states.observe(kind, "unavailable")
            assert states()[capability] == {"state": "unavailable",
                                            "reason": "provider-unreachable"}
            assert activation.state(kind) == "active"  # the activation never moved
            before = flow_count(connect)
            with pytest.raises(TimeoutError):  # the deadline answer
                begun(service, provider_starts, kind)
            assert flow_count(connect) == before  # no start was written
            with pytest.raises(TimeoutError):
                completed(service, provider, kind, earlier, subject)
            assert provider.requests == []  # no token request, no exchange
            assert disposition_of(connect, earlier) == "pending"

            states.observe(kind, "available")
            signed_in = completed(service, provider, kind, earlier, subject)
            assert signed_in.public["state"] == "authenticated"
            assert [request.url.path for request in provider.requests][0] in (
                "/token", "/oauth/token")
    finally:
        ledger.close()
        with connect("accounts") as conn:
            conn.execute("DELETE FROM accounts.identity_link WHERE id=%s", (link,))
