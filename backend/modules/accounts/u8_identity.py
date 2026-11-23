"""Provider sign-in in the two complete realms (U8 plan Steps 19 and 21; D2, D3, BR7.1).

`ArrivalIdentityService` is U2's `ControlIdentityService` with the complete realms'
parts (the person's decision of 2026-10-24, "Move, scope tools, test U2"):

- every adapter registers the workspace's arrival page as its callback (D3); an adapter
  the composition configured on the entry (the real Google and ORCID adapters of
  Step 21) replaces the fixture;
- an adapter that reports itself unconfigured is refused as a provider timeout is,
  before anything is written (BR7.1);
- starting a provider sign-in has limits of its own (the person's decisions of
  2026-10-24, "Limit starts per address", and of 2026-10-25, "Cap per address, raise site
  cap" and "Count every start, free places at once"), counted from the stored flows in
  the start's own transaction, right after its flow is written (`_admit_start`). Every
  start counts under the keyed digest of its client address bucket (an IPv4 address, an
  IPv6 /48, or `unknown`), and a signed-in start, a link, also under its account: each
  holds at most 3 open flows, and within 5 minutes makes at most 10 starts that did not
  complete and 30 in all. The site holds at most 200 open flows and takes at most 600
  starts within 5 minutes, so U2's own cap (`flow_capacity`, 201 here) only backs these
  up. The same browser keeps its two latest pending flows. A refusal is the built busy
  answer (429 RATE_LIMITED) with its wait in `Retry-After` only, and writes nothing. By
  the person's decision of 2026-10-26 ("Keep it, list the seam"), the busy answer
  carries `messageKey` `identity-start.<reason>`, through `backend/local_browser.py`'s
  seam: the boundary's `Busy` branch passes an exception's `message_key` when it has one,
  and every other `Busy` keeps the built `request.rate_limited`. No start counts against
  D2's sign-in budgets;
- a sign-in refused after the provider's answer frees its place at once, as `denied`
  (`_finish_refused`), and `expire_flows` runs AccountAccess's definer function that
  deletes each flow, with its digest, a minute after it expires;
- a real adapter's authorization address, with the flow's state, nonce and PKCE
  challenge;
- admission and a migrated account's consent-pending first sign-in, its answer read
  again while that session is current, and D1's session lengths from the composition's
  clock;
- the sign-in provider's activation (U8 plan Step 106(g); BR7.8, security-design § 3.5),
  read at call time from `entry.identity_gate`, the ProviderActivation production wires:
  a start is refused as an unconfigured adapter is (in production without a gate,
  through an unavailable provider, through a held one once admission opens, and for a
  link through a held one unless the account is the maintainer's in live mode), and the
  outcome and a link's completion admit only an active provider, or a held one in live
  mode for the maintainer's own account, refusing the rest with the answer a wrong
  password gets. Production is found by the entry's policy realm, so the composed
  realm's entries, which have an admission and no gate, keep the built rules;
- the provider's circuit breaker (reliability-design § 10; L4-11): with the
  composition's derived states the gate is `u8_outward.sign_in_gate`, which answers
  `unavailable` while provider.google or provider.orcid is observed unavailable. A start
  is then refused by the check above, before anything is written, and a completion,
  sign-in or link, is refused before U2's `complete`, so no token exchange is called and
  the flow stays pending.

It refuses an entry whose policy is not D1-shaped, so it never runs in U2's realm. It never
imports the real adapters at module level (`integrations/identity_providers.py`
imports this module).
"""

from __future__ import annotations

import ipaddress
import math
from uuid import UUID, uuid4

import psycopg
from backend.modules.accounts.entry_limits import REFUSAL, current_address
from backend.modules.accounts.integrations.provider_gate import require_state
from backend.modules.accounts.services.control_identity import (
    ControlIdentityService,
    FixtureIdentityProvider,
    IdentityProvider,
)
from backend.modules.accounts.services.first_sign_in import CONSENT_PURPOSE
from backend.modules.accounts.services.guarded_entry import SessionTransport
from backend.transactions import Busy

ARRIVAL_PATH = "/sign-in/callback/"
_HOOKS = ("_check_adapter", "_admit_start", "_finish_refused", "_require_issuer",
          "_authorization_url", "_replay", "_sign_in_outcome")
# The person's decision of 2026-10-25 ("Count every start, free places at once"), for
# each address bucket and each account, within a flow's own 5 minutes.
BUCKET_OPEN = 3
BUCKET_UNFINISHED = 10
BUCKET_STARTS = 30
# For everyone together.
SITE_OPEN = 200
SITE_STARTS = 600
# U2's own count runs before the flow is written, U8's after, so U2's never refuses first.
COMPLETE_FLOW_CAPACITY = SITE_OPEN + 1
# A refusal's wait: a full place or site; simultaneous starts out of retries; at most a
# flow's life, for a count of starts.
FULL_WAIT_SECONDS = 30
CONFLICT_WAIT_SECONDS = 1
FLOW_SECONDS = 300
# Provider starts count an IPv6 address by its /48 (D2's limits keep the /64).
IPV6_START_PREFIX = 48
EXPIRY_LIMIT = 1000

# The browser's own pending flows beyond its two latest close as 'expired'.
_CLOSE_OLDER = (
    "UPDATE accounts.identity_flow SET disposition='expired' WHERE id IN (SELECT id FROM "
    "accounts.identity_flow WHERE binding_hash=%s AND disposition='pending' AND "
    "expires_at>clock_timestamp() ORDER BY expires_at DESC,id OFFSET 2)"
)
_COUNTS = (
    "SELECT count(*) FILTER (WHERE disposition IN ('pending','exchanging')) AS open,"
    "count(*) FILTER (WHERE disposition<>'complete') AS unfinished,count(*) AS starts,"
    "ceil(extract(epoch FROM min(expires_at) FILTER (WHERE disposition<>'complete')"
    "-clock_timestamp())) AS unfinished_wait,"
    "ceil(extract(epoch FROM min(expires_at)-clock_timestamp())) AS starts_wait "
    "FROM accounts.identity_flow WHERE expires_at>clock_timestamp()"
)
_ADDRESS_COUNTS = _COUNTS + " AND client_address_digest=%s"
_ACCOUNT_COUNTS = _COUNTS + " AND account_id=%s"


class IdentityStartLimited(Busy):
    """A provider sign-in start refused by one of its limits; `reason` is a fixed key. It
    is the built busy answer (a `Busy`, which every browser route answers 429
    RATE_LIMITED), and its wait goes to the request's `REFUSAL` for `Retry-After`, as
    the sign-in limits' refusals do. By the person's decision of 2026-10-25 ("Different
    text for site-wide"), the answer carries the reason as its `messageKey`
    (`identity-start.<reason>`), which the entry panel's Korean text resolves (the
    contract's common rule: Korean UI text resolves `messageKey`)."""

    REASONS = ("places", "unfinished-starts", "starts", "site-places", "site-starts",
               "conflict")
    MESSAGE_KEY_PREFIX = "identity-start."

    def __init__(self, reason: str, retry_after_seconds: float):
        if reason not in self.REASONS:
            raise ValueError("unknown identity start limit reason")
        super().__init__("identity start limit")
        self.reason = reason
        self.message_key = self.MESSAGE_KEY_PREFIX + reason
        self.retry_after_seconds = max(1, min(FLOW_SECONDS, math.ceil(retry_after_seconds)))
        holder = REFUSAL.get()
        if holder is not None:
            holder["retryAfterSeconds"] = self.retry_after_seconds


def start_bucket(address: str) -> str:
    """The bucket a provider start counts under: the sign-in limits' address key (an IPv4
    address, an IPv6 /64, or `unknown`), with IPv6 widened to its /48."""
    try:
        network = ipaddress.ip_network(address, strict=False)
    except ValueError:
        return address
    if network.version == 6 and network.prefixlen > IPV6_START_PREFIX:
        return str(network.supernet(new_prefix=IPV6_START_PREFIX))
    return address


def _judge(counts: dict, *, site: bool = False) -> None:
    """Refuse a start whose counts, its own flow included, pass a limit."""
    if counts["open"] > (SITE_OPEN if site else BUCKET_OPEN):
        raise IdentityStartLimited("site-places" if site else "places", FULL_WAIT_SECONDS)
    if not site and counts["unfinished"] > BUCKET_UNFINISHED:
        raise IdentityStartLimited("unfinished-starts", counts["unfinished_wait"])
    if counts["starts"] > (SITE_STARTS if site else BUCKET_STARTS):
        raise IdentityStartLimited("site-starts" if site else "starts", counts["starts_wait"])


def expire_flows(transactions, *, limit: int = EXPIRY_LIMIT) -> int:
    """AccountAccess's bounded deletion pass (the scheduler's `identity-flows` task): at
    most `limit` flows that expired more than a minute ago go, with their address
    digests, through the definer function the runtime login may only call."""
    if type(limit) is not int or not 1 <= limit <= 10_000:
        raise ValueError("expiry outside its bound")
    return transactions.run("accounts", lambda conn: conn.execute(
        "SELECT accounts.expire_identity_flows(%s) AS n", (limit,)).fetchone()["n"])


def arrival_callback(origin: str, provider: str) -> str:
    """D3: the workspace page each adapter registers as its redirect back, served as the
    static shell; its script continues to the API route with a same-site request."""
    return origin + ARRIVAL_PATH + provider


class ArrivalFixtureProvider(FixtureIdentityProvider):
    """U2's synthetic adapter registered at the arrival page, so the built fixture
    checks still see a fixture."""

    def __init__(self, name: str, *, callback: str):
        super().__init__(name)
        self.callback = callback


def arrival_providers(entry, providers: dict[str, IdentityProvider]) -> dict:
    """Every adapter registers the workspace page as its callback (D3). An adapter the
    composition configured on the entry (`identity_providers`) replaces the fixture; a
    fixture is registered at the page; any adapter registered elsewhere is refused."""
    origin = entry.transactions.profile.origin
    configured = getattr(entry, "identity_providers", None) or {}
    chosen = {}
    for name, provider in providers.items():
        adapter = configured.get(name, provider)
        page = arrival_callback(origin, name)
        if isinstance(adapter, FixtureIdentityProvider) and adapter.callback != page:
            adapter = ArrivalFixtureProvider(name, callback=page)
        if adapter.callback != page:
            raise ValueError("an identity adapter must register the workspace page")
        chosen[name] = adapter
    return chosen


def link_value(link: dict) -> dict:
    """C02's AccessIdentityLink for one stored link."""
    return {
        "identityLinkId": str(link["id"]),
        "provider": link["provider"],
        "providerSubject": link["subject"],
        "revision": str(link["revision"]),
        "profileAvailable": bool((link["provenance"] or {}).get("profile")),
    }


class ArrivalIdentityService(ControlIdentityService):
    # U2's own cap on open flows in the complete realms, one above the site's 200, so it
    # only backs U8's count up (U2's `begin` keeps 20 by default).
    flow_capacity = COMPLETE_FLOW_CAPACITY

    def __init__(self, entry, providers: dict[str, IdentityProvider]):
        if any(not callable(getattr(ControlIdentityService, hook, None)) for hook in _HOOKS):
            raise TypeError("U2's ControlIdentityService lacks one of its seams")
        if not isinstance(getattr(ControlIdentityService, "flow_capacity", None), int):
            raise TypeError("U2's ControlIdentityService lacks its flow capacity seam")
        if not getattr(entry.control_policy, "d1_shaped", False):
            raise PermissionError("arrival sign-in needs a complete realm's entry")
        super().__init__(entry, arrival_providers(entry, providers))

    def _check_adapter(self, adapter) -> None:
        if getattr(adapter, "unconfigured", False) is True:
            # An adapter that reports itself unconfigured is refused as a provider
            # timeout is, before anything is written (BR7.1).
            raise TimeoutError("identity provider unconfigured")

    # --- the provider's activation (U8 plan Step 106(g); BR7.8, security-design § 3.5) ---

    def _gate(self):
        """The ProviderActivation production wires on the entry, read at call time."""
        return getattr(self.entry, "identity_gate", None)

    def _production(self) -> bool:
        """Production is the entry's control policy realm, never its admission: the
        composed realm's own entries carry an admission and no gate."""
        return getattr(self.entry.control_policy, "realm", None) == "production"

    def _refuse_start(self, authority, provider: str, intent: str) -> None:
        """Before anything is written: in production without a gate, through an
        unavailable provider, through a held one once admission opens, and for a link
        through a held one unless the gate is live and the account is the maintainer's.
        A held provider's sign-in still starts while admission is maintainer-only, so
        the maintainer can sign in through it in the window."""
        if provider not in self.providers or intent not in ("sign_in", "link"):
            return  # U2's own refusal answers
        gate = self._gate()
        if gate is None:
            if self._production():
                raise TimeoutError("identity provider unavailable")
            return
        state = require_state(gate, provider)
        if state == "unavailable":
            raise TimeoutError("identity provider unavailable")
        if state != "held":
            return
        admission = getattr(self.entry, "admission", None)
        if admission is not None and admission.state == "open":
            raise TimeoutError("identity provider unavailable")
        if intent == "link" and not (
            gate.mode == "live" and authority is not None
            and gate.is_maintainer_account(authority.account_id)
        ):
            raise TimeoutError("identity provider unavailable")

    def _require_serving(self, provider: str, account_id) -> None:
        """At the outcome and at a link's completion: only an active provider, or a held
        one in live mode for the maintainer's own account; otherwise, and in production
        without a gate, the answer a wrong password gets."""
        gate = self._gate()
        if gate is None:
            if self._production():
                raise PermissionError("credentials unavailable")
            return
        state = require_state(gate, provider)
        if state == "active":
            return
        if state == "held" and gate.mode == "live" and gate.is_maintainer_account(account_id):
            return
        raise PermissionError("credentials unavailable")

    def begin(self, authority, provider: str, intent: str, binding: str, route: str) -> dict:
        """U2's start, after the provider's activation is read; simultaneous starts that
        ran out of their retries get the busy answer with a 1-second wait, not a
        conflict."""
        self._refuse_start(authority, provider, intent)
        try:
            return super().begin(authority, provider, intent, binding, route)
        except (psycopg.errors.SerializationFailure, psycopg.errors.DeadlockDetected):
            raise IdentityStartLimited("conflict", CONFLICT_WAIT_SECONDS) from None

    def complete(self, identifier: UUID, state: str, binding: str, code: str, callback: str,
                 authority) -> dict:
        """U2's completion. Through a provider the gate answers `unavailable` for (its
        circuit breaker while the provider is observed unavailable, reliability-design
        § 10; L4-11), a sign-in and a link are both refused first with the answer an
        unanswering provider gets, before U2's `complete` and so before the token
        exchange; the flow stays pending, so the same callback completes once the probe
        passes. A link through a provider that is not serving for this account is
        refused next, writing nothing. An unknown flow goes on to U2's own refusal."""
        gate = self._gate()
        if gate is not None or (authority is not None and self._production()):
            flow = self.transactions.run("accounts", lambda conn: conn.execute(
                "SELECT provider,intent FROM accounts.identity_flow WHERE id=%s",
                (identifier,)).fetchone())
            if flow is not None:
                self._refuse_completion(gate, flow, authority)
        return super().complete(identifier, state, binding, code, callback, authority)

    def _refuse_completion(self, gate, flow: dict, authority) -> None:
        if (gate is not None and flow["provider"] in self.providers
                and require_state(gate, flow["provider"]) == "unavailable"):
            raise TimeoutError("identity provider unavailable")
        if authority is not None and flow["intent"] == "link":
            self._require_serving(flow["provider"], authority.account_id)

    def _admit_start(self, conn, identifier: UUID) -> None:
        """In the start's transaction, right after its flow is written: the flow takes its
        address digest, the browser keeps its two latest pending flows, and the start is
        counted with its own flow included. A refusal rolls everything back."""
        row = conn.execute(
            "SELECT account_id,binding_hash FROM accounts.identity_flow WHERE id=%s",
            (identifier,),
        ).fetchone()
        digest = self.entry.verifier("identity-flow-address", start_bucket(current_address()))
        conn.execute("UPDATE accounts.identity_flow SET client_address_digest=%s WHERE id=%s",
                     (digest, identifier))
        conn.execute(_CLOSE_OLDER, (row["binding_hash"],))
        _judge(conn.execute(_ADDRESS_COUNTS, (digest,)).fetchone())
        if row["account_id"] is not None:
            _judge(conn.execute(_ACCOUNT_COUNTS, (row["account_id"],)).fetchone())
        _judge(conn.execute(_COUNTS).fetchone(), site=True)

    def _finish_refused(self, identifier: UUID) -> None:
        """A sign-in refused after the provider's answer frees its place at once, as
        `denied`, in its own short transaction. When that write fails, the person still
        gets the built refusal, and the flow holds its place until it expires."""

        def deny(conn):
            conn.execute(
                "UPDATE accounts.identity_flow SET disposition='denied' WHERE id=%s "
                "AND disposition='exchanging'",
                (identifier,),
            )

        try:
            self.transactions.run("accounts", deny)
        except Exception as error:  # noqa: BLE001 - logged by type; the refusal stands
            from backend.log_events import log_exception

            log_exception("accounts", "identity.denial_unrecorded", error)

    def _require_issuer(self, provider) -> None:
        if callable(getattr(provider, "authorization_url", None)):
            return
        super()._require_issuer(provider)

    def _authorization_url(self, provider, identifier: UUID, accepted: dict, secret: dict) -> str:
        """A real adapter (Step 21) gives its provider's authorization address, with the
        flow's state, nonce and PKCE challenge; the fixture keeps its protocol fixture."""
        if callable(getattr(provider, "authorization_url", None)):
            return provider.authorization_url(
                state=accepted["state"], nonce=secret["nonce"], verifier=secret["verifier"]
            )
        return super()._authorization_url(provider, identifier, accepted, secret)

    def _replay(self, row: dict, token: str, csrf: str):
        if row["intent"] == "sign_in" and (row["outcome"] or {}).get("state") == CONSENT_PURPOSE:
            # A completed first provider sign-in read again: its answer while the
            # consent-pending session it opened is still current, else no session.
            if self.entry.first_sign_in.limited_purpose(token) != CONSENT_PURPOSE:
                raise PermissionError("session unavailable")
            return SessionTransport(token, csrf, row["outcome"])
        return super()._replay(row, token, csrf)

    def _insert_session(self, conn, account, token, csrf, flow, purpose, seconds) -> dict:
        return conn.execute(
            "INSERT INTO accounts.session(id,account_id,token_hash,csrf_hash,authority_revision,"
            "expires_at,purpose,flow_id) "
            "VALUES(%s,%s,%s,%s,%s,%s::timestamptz+(%s*interval '1 second'),%s,%s) RETURNING *",
            (
                uuid4(),
                account["id"],
                self.entry.verifier("session", token),
                self.entry.verifier("csrf", csrf),
                account["authority_revision"],
                self.entry.issue_time(),
                seconds,
                purpose,
                flow,
            ),
        ).fetchone()

    def _sign_in_outcome(self, conn, account, linked, token: str, csrf: str, identifier):
        # Admission holds for a provider sign-in exactly as for a password one
        # (security-design § 3.5), before any session or continuation is issued.
        self.entry.require_admitted(account)
        # The sign-in provider's activation, read again at the outcome (BR7.8): a
        # refusal ends the flow `denied` through `_finish_refused`, with no session.
        self._require_serving(linked["provider"], account["id"])
        first = self.entry.first_sign_in
        policy = self.entry.control_policy
        if first.pending(conn, account["id"]):
            # A migrated account's first sign-in (BR8.6, decision of 2026-10-22): the
            # password path's 15-minute consent-pending session, which every guard
            # denies for anything but giving consents (NFR2.1).
            session = self._insert_session(
                conn, account, token, csrf, identifier,
                CONSENT_PURPOSE, policy.limited_session_seconds,
            )
            return dict(first.public(conn, session), identityLink=link_value(linked))
        factor = conn.execute(
            "SELECT id FROM accounts.mfa_enrollment WHERE account_id=%s AND state='active'",
            (account["id"],),
        ).fetchone()
        if account["role"] == "administrator" and not factor:
            raise PermissionError("administrator factor unavailable")
        requires_mfa = account["role"] == "administrator" or factor is not None
        session = self._insert_session(
            conn, account, token, csrf, identifier,
            "primary_mfa_continuation" if requires_mfa else "full_session",
            policy.proof_seconds if requires_mfa else policy.full_session_seconds(account["role"]),
        )
        return self.entry.public_session(session)
