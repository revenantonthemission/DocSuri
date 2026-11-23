"""U2's files take their built defaults (U8 plan Step 44; the person's decision of
2026-10-24, "Move, scope tools, test U2").

U8's complete-realm and production parts are U8's own modules. U2's twelve files keep
only allowlist values, the values of the person's decision of 2026-10-22 and seams whose
default is U2's built behaviour, so U2's realm and every earlier realm run U2's built
code. Each seam is shown at its default here, without a database where the seam needs
none: capacity's rule, the lifecycle worker's selection, hooks and participant table,
the routers' default parts and their refusal of a complete realm, `for_realm`, U2's key
recovery and key folder, the second factor's hooks, `begin`'s hook, the acknowledgement
step, the lifecycle service's signature, the reservation's owner and the boundary's busy
answer's message key. U8's own refusals follow: `CompletePolicy` and the first sign-in
under a built policy.
"""

from __future__ import annotations

import dataclasses
import inspect
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from backend import local_profile
from backend.control_runtime import ControlCapacity
from backend.control_worker import SET_ASIDE, ControlWorker
from backend.local_browser import COMPLETE_ORIGIN, CONTROLS_ORIGIN
from backend.local_profile import LocalProfile, key_folder, verifier_key_path
from backend.modules.accounts import control_key_recovery
from backend.modules.accounts.control_http import control_router
from backend.modules.accounts.control_policy import (
    SYNTHETIC_POLICY,
    ControlPolicy,
    PolicyUnavailable,
    for_realm,
)
from backend.modules.accounts.local_http import account_router
from backend.modules.accounts.services.control_identity import (
    ControlIdentityService,
    FixtureIdentityProvider,
)
from backend.modules.accounts.services.control_lifecycle import ControlLifecycleService
from backend.modules.accounts.services.control_mfa import ControlMfaService
from backend.modules.accounts.services.first_sign_in import FirstSignIn
from backend.modules.accounts.u8_control_policy import (
    PRODUCTION_POLICY,
    U8_SYNTHETIC_POLICY,
    CompletePolicy,
)
from backend.modules.accounts.u8_identity import ArrivalIdentityService
from backend.modules.plans.control_service import ControlUsageService
from tests.u8_service_operations_integration.built_files import changed_from_built

ROOT = Path(__file__).resolve().parents[3]
MIB = 1024 * 1024
U2_RUN = Path("/tmp/docsuri-u2-run")
U2_PROFILE = SimpleNamespace(realm="account-controls", origin=CONTROLS_ORIGIN,
                             run_id="docsuri-u2-" + "0" * 16, database_name="docsuri_u2",
                             expires_at=4_000_000_000.0, root=U2_RUN)
COMPLETE_PROFILE = SimpleNamespace(realm="service-operations", origin=COMPLETE_ORIGIN,
                                   run_id="docsuri-u8-" + "0" * 16, database_name="docsuri_u8",
                                   expires_at=4_000_000_000.0, root=Path("/tmp/docsuri-u8-run"))


def stand_in_entry(profile, policy=SYNTHETIC_POLICY, **extra):
    """An entry service as U2's routers read it, with no database behind it."""
    return SimpleNamespace(
        control_policy=policy, transactions=SimpleNamespace(profile=profile),
        verifier=lambda purpose, value: "00" * 32, **extra)


# --- Capacity ---------------------------------------------------------------------------


def test_capacity_keeps_the_built_512_mib_rule_and_starts_closed():
    capacity = ControlCapacity(SimpleNamespace())
    assert capacity.admitting is False and capacity.last_bytes is None
    limit = 512 * MIB * 4 // 5
    assert capacity._admits(limit - 1) is True
    assert capacity._admits(limit) is False
    assert not hasattr(capacity, "budget")


# --- The lifecycle worker ----------------------------------------------------------------


def test_the_worker_keeps_its_built_table_selection_and_hooks(transactions):
    entry = SimpleNamespace(transactions=transactions)
    lifecycle = SimpleNamespace(manifest=(), revision="u2-owners-v1")
    worker = ControlWorker(entry, lifecycle, None, None)
    assert set(worker.participants) == {
        "AccountAccess", "Library", "Personalization", "UsageEntitlements",
        "DiscoveryCitations", "PaperAssistance", "TopicsDigests",
    }
    # The built selection: the request identifiers only, in acceptance order.
    source = inspect.getsource(ControlWorker._open_requests)
    assert "SELECT r.id FROM accounts.lifecycle_request r" in source
    assert "ORDER BY r.accepted_at,r.id LIMIT %s" in source
    assert worker._open_requests(4) == []  # no request carries this revision
    calls = []
    assert worker._guarded("lifecycle-scope", "x", lambda: calls.append(1) or "done") == "done"
    assert calls == [1]
    with pytest.raises(ZeroDivisionError):  # a failure ends the pass, as built
        worker._guarded("lifecycle-scope", "x", lambda: 1 / 0)
    assert worker._acknowledgement_options({"retainedUntil": "2026-11-01T00:00:00Z"}) == {}
    assert SET_ASIDE is not None and not hasattr(worker, "set_aside")
    for name in ("_waits", "_requests", "_waiting_participants", "_select"):
        assert not hasattr(worker, name), name


# --- The routers ---------------------------------------------------------------------------


def paths(router) -> list[str]:
    return [route.path for route in router.routes]


def test_the_routers_default_parts_serve_u2s_realm():
    entry = stand_in_entry(U2_PROFILE)
    routes = paths(control_router(entry, SimpleNamespace()))
    assert "/api/v2/c02/access-begin-mfa-enrollment" in routes
    assert "/api/v2/identity/callback/{provider}" in routes
    assert len(routes) == len(set(routes))  # no route of a complete realm in front
    accounts = paths(account_router(entry))
    assert accounts.count("/api/v2/c02/access-login") == 1


def test_without_u8s_parts_the_routers_refuse_a_complete_realm():
    entry = stand_in_entry(COMPLETE_PROFILE, U8_SYNTHETIC_POLICY)
    with pytest.raises(PolicyUnavailable):
        control_router(entry, SimpleNamespace())
    with pytest.raises(PolicyUnavailable):
        account_router(entry)
    # A part missing is the same as none: all three are needed.
    with pytest.raises(PolicyUnavailable):
        control_router(entry, SimpleNamespace(), identities=object(), mfa=object())
    # An entry without account controls (U1's, which every earlier realm builds on)
    # keeps the built account router in any realm.
    plain = SimpleNamespace(transactions=SimpleNamespace(profile=COMPLETE_PROFILE))
    assert "/api/v2/c02/access-login" in paths(account_router(plain))


# --- The policy, key recovery and the key folder -------------------------------------------


def test_for_realm_keeps_u2s_policy_and_takes_the_complete_ones_from_u8():
    assert for_realm("account-controls") is SYNTHETIC_POLICY
    assert for_realm("service-operations") is U8_SYNTHETIC_POLICY
    assert for_realm("production") is PRODUCTION_POLICY
    for other in ("research-workspace", "journey", "diagnostic", "topics-digests"):
        assert for_realm(other) is None


def test_u2s_policy_binds_only_u2s_realm():
    fields = {field.name: getattr(SYNTHETIC_POLICY, field.name)
              for field in dataclasses.fields(ControlPolicy)}
    for change in ({"policy_id": "u8-synthetic-v1"}, {"realm": "service-operations"},
                   {"policy_id": "docsuri-production-v1", "realm": "production"}):
        with pytest.raises(PolicyUnavailable):
            ControlPolicy(**{**fields, **change})
    with pytest.raises(PolicyUnavailable):
        SYNTHETIC_POLICY.require_realm("service-operations")
    for name in ("d1_shaped", "full_session_seconds", "entry_limits", "limited_session_seconds"):
        assert not hasattr(SYNTHETIC_POLICY, name), name


def test_u2s_key_recovery_and_key_folder_are_as_built(tmp_path):
    with pytest.raises(ValueError, match="owned recovery root required"):
        control_key_recovery.recover(tmp_path, "docsuri-u2-" + "0" * 16,
                                     expected_digest="0" * 64, expected_generation=1)
    assert "def recover_production" not in inspect.getsource(control_key_recovery)
    # Its built bytes, by the digest pinned at the branch base (never `HEAD`, which in CI
    # already holds every change).
    assert changed_from_built(["backend/modules/accounts/control_key_recovery.py"]) == {}
    u2 = LocalProfile(tmp_path, "docsuri-u2-" + "0" * 16, CONTROLS_ORIGIN, 15449, 0.0,
                      "docsuri_u2", "account-controls")
    assert key_folder(u2, "control-keys") == tmp_path
    assert verifier_key_path(u2) == tmp_path / "account-verifier.key"
    assert u2.is_production is False
    for name in ("ProductionProfile", "ProfileRefused", "custody_failure",
                 "PRODUCTION_ORIGIN", "PRODUCTION_LISTEN_PORT"):
        assert not hasattr(local_profile, name), name


# --- The second factor's hooks ---------------------------------------------------------------


class Recorder:
    """A pass-through recorder over the realm's own connection (L1-35's call-through
    kind, Step 98(d)): each statement is recorded, then run on the realm, and its answer
    returned unchanged."""

    def __init__(self, conn):
        self.conn, self.calls = conn, []

    def execute(self, query, params=()):
        self.calls.append((query, params))
        return self.conn.execute(query, params)


class RolledBack(Exception):  # noqa: N818 - ends a test's transaction, its rows undone
    """Raised at the end of a test's own accounts transaction, so nothing it wrote stays."""


def test_the_second_factors_hooks_are_the_built_statements(transactions):
    reauthenticated = []
    entry = stand_in_entry(U2_PROFILE, reauthenticate=lambda authority, password: (
        reauthenticated.append((authority, password))))
    mfa = ControlMfaService(entry)
    probe = "probe-" + uuid4().hex[:12]  # generated per run (L1-36)
    mfa._reauthenticate("authority", probe)
    assert reauthenticated == [("authority", probe)]
    challenge = uuid4()

    def hooks(conn):
        recorder = Recorder(conn)
        assert mfa._confirmed(recorder, SimpleNamespace(session_id=uuid4(),
                                                        account_id=uuid4())) is None
        assert mfa._admit_continuation({"role": "member"}) is None
        assert recorder.calls == []  # neither writes anything
        # No session holds the challenge's identifier: the built update finds no row.
        assert mfa._full_session(recorder, {"role": "administrator"}, challenge) is None
        return recorder.calls

    [(query, params)] = transactions.run("accounts", hooks)
    assert "expires_at=clock_timestamp()+(%s*interval '1 second')" in query
    assert params == (SYNTHETIC_POLICY.session_seconds, challenge)
    assert "setup" not in inspect.signature(ControlMfaService.begin).parameters


def test_begins_hook_does_nothing_and_writes_nothing(transactions):
    class Unwritten:
        profile = U2_PROFILE

        def run(self, owner, work):
            raise AssertionError("the hook wrote a record")

    entry = SimpleNamespace(control_policy=SYNTHETIC_POLICY, transactions=Unwritten())
    service = ControlIdentityService(
        entry, {name: FixtureIdentityProvider(name) for name in ("google", "orcid")})
    unconfigured = SimpleNamespace(unconfigured=True)
    assert service._check_adapter(unconfigured) is None  # U2's start has no such refusal
    assert service.providers["google"].callback.startswith("https://127.0.0.1:18049/")
    # The start's hook in its transaction and the refused finish's hook do nothing, and the
    # realm keeps U2's 20 open flows (the person's decisions of 2026-10-25, "Cap per
    # address, raise site cap" and "Count every start, free places at once").
    def start(conn):
        recorder = Recorder(conn)
        assert service._admit_start(recorder, uuid4()) is None
        return recorder.calls

    assert transactions.run("accounts", start) == []
    assert service._finish_refused(uuid4()) is None  # `Unwritten` fails on any write
    assert ControlIdentityService.flow_capacity == service.flow_capacity == 20
    for gone in ("_check_start", "_mark_start"):
        assert not hasattr(ControlIdentityService, gone), gone
    source = inspect.getsource(ControlIdentityService.begin)
    assert "count >= self.flow_capacity" in source and "client_address" not in source
    # `_admit_start` runs in the start's transaction, right after its flow is written.
    assert source.index("INSERT INTO accounts.identity_flow") < source.index(
        "self._admit_start(conn, identifier)") < source.index("return {")
    # `_finish_refused` runs only when a claimed flow's finish is refused, before the
    # refusal is raised again.
    complete = inspect.getsource(ControlIdentityService.complete)
    handler = complete[complete.index('outcome = self.transactions.run("accounts", finish)'):]
    assert handler.index("except Exception:") < handler.index(
        "self._finish_refused(identifier)") < handler.index("raise")


def test_in_u2s_own_service_a_refused_finish_stays_exchanging(transactions, provider_starts):
    """U2's built `complete` in the composed database: an identity no link holds is
    refused after the provider's answer, and the flow stays `exchanging`, as built."""
    from backend.modules.accounts.u8_entry import CompleteControlEntryService
    from tests.u8_service_operations_integration.conftest import provider_answer

    entry = CompleteControlEntryService(transactions, U8_SYNTHETIC_POLICY)
    service = ControlIdentityService(
        entry, {name: FixtureIdentityProvider(name) for name in ("google", "orcid")})
    binding = provider_starts.binding()
    with provider_starts.at():
        accepted = provider_starts.track(
            service.begin(None, "orcid", "sign_in", binding, "account"))
    code = provider_answer(service, accepted, "unlinked-" + uuid4().hex)
    with pytest.raises(PermissionError, match="verified identity link required"):
        service.complete(UUID(accepted["flowId"]), accepted["state"], binding, code,
                         service.providers["orcid"].callback, None)

    def read(conn):
        return conn.execute(
            "SELECT disposition,client_address_digest FROM accounts.identity_flow WHERE id=%s",
            (UUID(accepted["flowId"]),)).fetchone()

    assert transactions.run("accounts", read) == {"disposition": "exchanging",
                                                  "client_address_digest": None}


def test_the_acknowledgement_step_and_the_lifecycle_signature_are_as_built():
    parameters = inspect.signature(ControlLifecycleService.acknowledge).parameters
    assert list(parameters) == ["self", "ticket", "evidence", "reason"]
    step = inspect.signature(ControlLifecycleService._acknowledge_in).parameters
    assert step["recorded"].default is None


def test_a_reservations_owner_is_paper_assistance_as_the_column_default():
    assert ControlUsageService.operation_owner == "PaperAssistance"
    source = (ROOT / "backend/modules/plans/u2_controls.sql").read_text()
    assert "operation_owner text NOT NULL DEFAULT 'PaperAssistance'" in source


# --- U8's own refusals ------------------------------------------------------------------------


def complete_fields(**changes) -> dict:
    fields = {field.name: getattr(U8_SYNTHETIC_POLICY, field.name)
              for field in dataclasses.fields(CompletePolicy)}
    return {**fields, **changes}


@pytest.mark.parametrize(("changes", "error"), [
    ({"realm": "production"}, PolicyUnavailable),
    ({"policy_id": "u2-synthetic-v1", "realm": "account-controls"}, PolicyUnavailable),
    ({"member_session_seconds": None}, ValueError),
    ({"administrator_session_seconds": None}, ValueError),
    ({"max_accounts": 21}, ValueError),
    ({"lease_seconds": 10}, ValueError),  # the attempt no longer precedes the lease
    ({"proof_seconds": 30}, ValueError),  # the material would outlive the proof
])
def test_complete_policy_refuses_each_unbound_or_unbounded_value(changes, error):
    with pytest.raises(error):
        CompletePolicy(**complete_fields(**changes))
    production = {field.name: getattr(PRODUCTION_POLICY, field.name)
                  for field in dataclasses.fields(CompletePolicy)}
    with pytest.raises(ValueError):
        CompletePolicy(**{**production, "max_accounts": 501})


def test_the_first_sign_in_refuses_a_built_policy_instead_of_failing_on_it():
    with pytest.raises(ValueError, match="D1-shaped"):
        FirstSignIn(stand_in_entry(U2_PROFILE))


def test_begins_error_order_under_u8s_arrival_service():
    """Step 44's correction: the refusals keep their built order. An unknown provider is
    an input error, a link without its owner a permission error, and an unconfigured
    adapter's sign-in a timeout; none writes anything."""
    class Unwritten:
        profile = COMPLETE_PROFILE

        def run(self, owner, work):
            raise AssertionError("a refused start wrote a record")

    unconfigured = {name: SimpleNamespace(name=name, unconfigured=True,
                                          callback=COMPLETE_ORIGIN + "/sign-in/callback/" + name)
                    for name in ("google", "orcid")}
    entry = SimpleNamespace(control_policy=U8_SYNTHETIC_POLICY, transactions=Unwritten(),
                            identity_providers=unconfigured,
                            _admit=lambda: pytest.fail("no limit is counted for a refusal"))
    service = ArrivalIdentityService(
        entry, {name: FixtureIdentityProvider(name) for name in ("google", "orcid")})
    with pytest.raises(ValueError):
        service.begin(None, "elsewhere", "sign_in", "binding", "account")
    with pytest.raises(PermissionError):
        service.begin(None, "google", "link", "binding", "account")
    with pytest.raises(TimeoutError):
        service.begin(None, "google", "sign_in", "binding", "account")
    with pytest.raises(PermissionError):  # U2's own entry is not a complete realm's
        ArrivalIdentityService(stand_in_entry(U2_PROFILE), {
            name: FixtureIdentityProvider(name) for name in ("google", "orcid")})


FLOW_INSERT = (
    "INSERT INTO accounts.identity_flow(id,account_id,provider,intent,state_hash,"
    "binding_hash,callback_id,return_route,secret_ciphertext,key_version,expires_at) "
    "VALUES(%s,%s,'google','sign_in',%s,%s,'u8-test','account',%s,'v1',"
    "clock_timestamp()+interval '10 minutes')")


def written_flow(conn, binding: str, account=None, digest: str | None = None):
    """A pending identity flow, written in the test's own transaction as the start writes
    it (Step 98(d): `_admit_start` runs on the realm, never on a connection that answers
    its counts)."""
    import secrets

    identifier = uuid4()
    conn.execute(FLOW_INSERT, (identifier, account, secrets.token_hex(32), binding,
                               secrets.token_bytes(16)))
    if digest is not None:
        conn.execute("UPDATE accounts.identity_flow SET client_address_digest=%s WHERE id=%s",
                     (digest, identifier))
    return identifier


def counts(places=1, unfinished=1, starts=1, unfinished_wait=300, starts_wait=300) -> dict:
    return {"open": places, "unfinished": unfinished, "starts": starts,
            "unfinished_wait": unfinished_wait, "starts_wait": starts_wait}


def test_u8s_start_counts_every_start_under_its_bucket_and_a_link_under_its_account_too(
        transactions, authority):
    """The complete realms' start (the person's decision of 2026-10-25, "Count every
    start, free places at once"): `_admit_start`, after the flow is written, stores the
    bucket's digest, closes the browser's older pending flows and judges the address's,
    the account's and the site's counts, each with the new flow included. No sign-in
    budget is touched."""
    import hashlib
    import secrets

    from backend.modules.accounts.entry_limits import client_address
    from backend.modules.accounts.u8_identity import (
        _HOOKS,
        BUCKET_OPEN,
        BUCKET_STARTS,
        BUCKET_UNFINISHED,
        COMPLETE_FLOW_CAPACITY,
        SITE_OPEN,
        SITE_STARTS,
        IdentityStartLimited,
        start_bucket,
    )
    from backend.transactions import Busy

    entry = stand_in_entry(COMPLETE_PROFILE, U8_SYNTHETIC_POLICY,
                           _admit=lambda: pytest.fail("a start counted a sign-in budget"))
    entry.verifier = lambda purpose, value: hashlib.sha256(
        f"{purpose}:{value}".encode()).hexdigest()
    service = ArrivalIdentityService(
        entry, {name: FixtureIdentityProvider(name) for name in ("google", "orcid")})
    assert (BUCKET_OPEN, BUCKET_UNFINISHED, BUCKET_STARTS, SITE_OPEN, SITE_STARTS) == (
        3, 10, 30, 200, 600)
    assert service.flow_capacity == COMPLETE_FLOW_CAPACITY == 201
    assert ControlIdentityService.flow_capacity == 20
    assert _HOOKS == ("_check_adapter", "_admit_start", "_finish_refused", "_require_issuer",
                      "_authorization_url", "_replay", "_sign_in_outcome")
    assert issubclass(IdentityStartLimited, Busy)
    account = authority.account_id
    # A bucket of the test's own: no other flow of the realm carries its digest.
    address = f"2001:db8:{secrets.randbelow(0xffff):x}:9::/64"
    digest = entry.verifier("identity-flow-address", start_bucket(address))

    def admitted(account_id):
        """One start on the realm, in a transaction rolled back at its end."""
        binding = secrets.token_hex(32)

        def start(conn):
            flow = written_flow(conn, binding, account_id)
            recorder = Recorder(conn)
            service._admit_start(recorder, flow)
            raise RolledBack(flow, binding, recorder.calls)

        with pytest.raises(RolledBack) as ended:
            transactions.run("accounts", start)
        return ended.value.args

    with client_address(address):
        flow, binding, calls = admitted(None)
        statements = [query for query, _ in calls]
        assert calls[1] == (
            "UPDATE accounts.identity_flow SET client_address_digest=%s WHERE id=%s",
            (digest, flow))
        assert "OFFSET 2" in statements[2] and calls[2][1] == (binding,)
        assert "client_address_digest=%s" in statements[3] and calls[3][1] == (digest,)
        assert "WHERE expires_at>clock_timestamp()" in statements[4]
        assert len(calls) == 5  # no account count for a guest
        _flow, _binding, calls = admitted(account)
        assert "account_id=%s" in calls[4][0] and calls[4][1] == (account,)

        # Three open flows of other browsers already in the bucket: the fourth start is
        # refused for its places, and its transaction rolls back.
        def crowded(conn):
            for _ in range(BUCKET_OPEN):
                written_flow(conn, secrets.token_hex(32), digest=digest)
            service._admit_start(Recorder(conn),
                                 written_flow(conn, secrets.token_hex(32), account))

        with pytest.raises(IdentityStartLimited) as refused:
            transactions.run("accounts", crowded)
        assert (refused.value.reason, refused.value.retry_after_seconds) == ("places", 30)
    service._check_adapter(SimpleNamespace(unconfigured=False))  # counts no budget


def test_u8s_start_limits_judge_each_count_and_bound_each_wait():
    from backend.modules.accounts.entry_limits import REFUSAL
    from backend.modules.accounts.u8_identity import (
        IdentityStartLimited,
        _judge,
        start_bucket,
    )

    for given, bucket in (("198.51.100.7", "198.51.100.7"), ("unknown", "unknown"),
                          ("2001:db8:1:2::/64", "2001:db8:1::/48"),
                          ("2001:db8:1:2::a", "2001:db8:1::/48"),
                          ("2001:db8::/32", "2001:db8::/32")):
        assert start_bucket(given) == bucket
    _judge(counts(places=3, unfinished=10, starts=30))  # at every limit: admitted
    _judge(counts(places=200, unfinished=999, starts=600), site=True)
    cases = [
        (counts(places=4), False, "places", 30),
        (counts(unfinished=11, unfinished_wait=42), False, "unfinished-starts", 42),
        (counts(starts=31, starts_wait=7), False, "starts", 7),
        (counts(places=201), True, "site-places", 30),
        (counts(starts=601, starts_wait=0.2), True, "site-starts", 1),
    ]
    for given, site, reason, wait in cases:
        holder = {}
        token = REFUSAL.set(holder)
        try:
            with pytest.raises(IdentityStartLimited) as refused:
                _judge(given, site=site)
        finally:
            REFUSAL.reset(token)
        assert (refused.value.reason, refused.value.retry_after_seconds) == (reason, wait)
        assert holder == {"retryAfterSeconds": wait}  # the boundary's `Retry-After`
    assert IdentityStartLimited("starts", 900).retry_after_seconds == 300
    assert IdentityStartLimited("conflict", 1).retry_after_seconds == 1
    with pytest.raises(ValueError):
        IdentityStartLimited("identity start limit", 1)


# --- The busy answer's seam (the person's decision of 2026-10-26, "Keep it, list the seam") --


def test_the_boundarys_busy_branch_without_a_message_key_answers_request_rate_limited():
    """`backend/local_browser.py`'s `Busy` branch at its default: a `Busy` that names no
    `message_key`, or names none (`None`), answers U2's built `request.rate_limited`, with
    no wait in its body, on U2's own origin; only a key the exception names (U8's
    `IdentityStartLimited`) replaces it."""
    import json

    from fastapi import APIRouter, FastAPI
    from fastapi.testclient import TestClient

    from backend.local_browser import boundary_route, error_response
    from backend.transactions import Busy

    class NamesNone(Busy):
        message_key = None

    router = APIRouter(route_class=boundary_route(CONTROLS_ORIGIN))

    @router.get("/seam/{kind}")
    async def refuse(kind: str):
        if kind == "plain":
            raise Busy("process connection allocation exhausted")
        if kind == "none":
            raise NamesNone("process connection allocation exhausted")
        named = Busy("identity start limit")
        named.message_key = "identity-start.places"
        raise named

    app = FastAPI()
    app.include_router(router)
    with TestClient(app, base_url=CONTROLS_ORIGIN, follow_redirects=False) as client:
        for kind in ("plain", "none"):
            answer = client.get(f"/seam/{kind}")
            assert answer.status_code == 429, answer.text
            body = answer.json()
            assert (body["code"], body["messageKey"], body["retryable"]) == (
                "RATE_LIMITED", "request.rate_limited", True)
            assert "retryAfterSeconds" not in body
        named = client.get("/seam/named")
        assert (named.status_code, named.json()["messageKey"]) == (429, "identity-start.places")
    # The answer's builder itself: no key given is the code's built key.
    for given in ({}, {"message_key": None}):
        built = json.loads(error_response(429, "RATE_LIMITED", **given).body)
        assert built["messageKey"] == "request.rate_limited"
        assert "retryAfterSeconds" not in built
