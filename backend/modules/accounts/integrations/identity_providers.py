"""Real Google and ORCID sign-in (U8 plan Step 21; A7, BR7.1, BR7.2, BR7.8, D3).

`GoogleIdentityProvider` and `OrcidIdentityProvider` implement the identity-provider port
`services/control_identity.py` defines (`name`, `issuer`, `audience`, `callback`,
`exchange`), on top of v1's `GoogleOidcVerifier` and `OrcidOidcVerifier`
(`integrations/oidc.py`): v1's PKCE, authorization address, audience, issuer and nonce
checks, ORCID's JWKS RS256 verification and expiry, and its 10-second limit. No second
verifier is written; only v1's transport calls are routed through an injectable HTTP
client, so a test hands in a fake transport and the test-wide guard refuses the network.

- The client secrets come from the production profile's private environment; only the
  production profile selects these adapters (the composition puts them on the entry as
  `identity_providers`), and every synthetic profile keeps the fixtures.
- Each registers the workspace page `/sign-in/callback/{provider}` as its callback (D3).
- A link is made only to a verified v2 account: the provider's email is never used to
  find or link one (`ControlIdentityService` links only by provider and subject).
- A provider that does not answer leaves the flow refused with a plain, retryable
  deadline answer and marks the adapter unreachable, which its capability's producer
  reports as `provider-unreachable` (the sign-in button is disabled, BR7.2).
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable

import httpx

from ..models import DomainException
from ..services.control_identity import IdentityClaims
from ..u8_identity import ARRIVAL_PATH
from .account_mail import run_to_completion
from .oidc import (
    GOOGLE_TOKEN_URL,
    GOOGLE_TOKENINFO_URL,
    GoogleOidcVerifier,
    OrcidOidcVerifier,
    pkce_challenge,
)

GOOGLE_ISSUER = "https://accounts.google.com"
ORCID_ISSUER = "https://orcid.org"
TIMEOUT_SECONDS = 10.0
REACHABLE_AFTER_SECONDS = 300.0


def network_transport() -> httpx.AsyncBaseTransport:
    """The one place these adapters build a network transport. Code reaches it only as
    a module attribute, so the test-wide guard replaces it for the whole run."""
    return httpx.AsyncHTTPTransport()


def network_client(**options) -> httpx.AsyncClient:
    """The adapters' one guarded client builder over `network_transport`. The
    composition wraps it to count the adapters' answered calls and hands it to the
    production probes (U8 plan Step 56), reached as a module attribute at call time."""
    return httpx.AsyncClient(transport=network_transport(), trust_env=False, **options)


class ProviderUnreachable(TimeoutError):
    """The provider did not answer in time; the flow is refused, never completed."""

    def __init__(self, provider: str):
        super().__init__(f"{provider} did not answer")
        self.provider = provider


class _RoutedGoogle(GoogleOidcVerifier):
    """v1's Google verifier; only its two calls go through the given client."""

    def __init__(self, client_id, client_secret, *, client_factory):
        super().__init__(client_id, client_secret, timeout=TIMEOUT_SECONDS)
        self._client_factory = client_factory

    async def _exchange_code(self, code, redirect_uri, code_verifier=None) -> str:
        data = {
            "code": code, "client_id": self._client_id, "client_secret": self._client_secret,
            "redirect_uri": redirect_uri, "grant_type": "authorization_code",
        }
        if code_verifier:
            data["code_verifier"] = code_verifier
        async with self._client_factory(timeout=self._timeout) as client:
            resp = await client.post(GOOGLE_TOKEN_URL, data=data)
        if resp.status_code != 200:
            raise DomainException("소셜 로그인 토큰 교환에 실패했습니다.")
        id_token = resp.json().get("id_token")
        if not id_token:
            raise DomainException("소셜 로그인 응답에 id_token이 없습니다.")
        return id_token

    async def _fetch_tokeninfo(self, id_token: str) -> dict:
        async with self._client_factory(timeout=self._timeout) as client:
            resp = await client.get(GOOGLE_TOKENINFO_URL, params={"id_token": id_token})
        if resp.status_code != 200:
            raise DomainException("소셜 로그인 토큰 검증에 실패했습니다.")
        return resp.json()


class _RoutedOrcid(OrcidOidcVerifier):
    """v1's ORCID verifier (JWKS RS256 kept as v1 has it); only its calls are routed."""

    def __init__(self, client_id, client_secret, *, client_factory):
        super().__init__(client_id, client_secret, env="prod", timeout=TIMEOUT_SECONDS)
        self._client_factory = client_factory

    async def _exchange_code(self, code, redirect_uri, code_verifier=None) -> str:
        data = {
            "code": code, "client_id": self._client_id, "client_secret": self._client_secret,
            "redirect_uri": redirect_uri, "grant_type": "authorization_code",
        }
        if code_verifier:
            data["code_verifier"] = code_verifier
        async with self._client_factory(timeout=self._timeout) as client:
            resp = await client.post(f"{self._base}/oauth/token", data=data,
                                     headers={"Accept": "application/json"})
        if resp.status_code != 200:
            raise DomainException("소셜 로그인 토큰 교환에 실패했습니다.")
        id_token = resp.json().get("id_token")
        if not id_token:
            raise DomainException("소셜 로그인 응답에 id_token이 없습니다.")
        return id_token

    async def _fetch_jwks(self, *, force: bool = False) -> dict:
        now = time.time()
        if self._jwks_cache is not None and not force and now - self._jwks_cached_at < 3600:
            return self._jwks_cache
        async with self._client_factory(timeout=self._timeout) as client:
            resp = await client.get(self._jwks_url)
        if resp.status_code != 200:
            raise DomainException("소셜 로그인 토큰 검증 키를 가져오지 못했습니다.")
        try:
            jwks = resp.json()
        except json.JSONDecodeError as error:
            raise DomainException("소셜 로그인 토큰 검증 키 형식이 올바르지 않습니다.") from error
        if not isinstance(jwks.get("keys"), list):
            raise DomainException("소셜 로그인 토큰 검증 키 형식이 올바르지 않습니다.")
        self._jwks_cache, self._jwks_cached_at = jwks, now
        return jwks


class _RealIdentityProvider:
    name: str
    issuer: str

    def __init__(self, verifier, *, client_id: str, origin: str, clock=time.monotonic):
        if not client_id or not origin.startswith("https://"):
            raise ValueError("a real identity adapter needs its client and public origin")
        self._verifier = verifier
        self.audience = client_id
        self.callback = origin + ARRIVAL_PATH + self.name
        self._clock = clock
        self._unreachable_since: float | None = None

    def authorization_url(self, *, state: str, nonce: str, verifier: str) -> str:
        """The provider's authorization address for one flow, with PKCE S256 (v1's)."""
        return self._verifier.build_authorization_url(
            self.callback, state, nonce, code_challenge=pkce_challenge(verifier)
        )

    def exchange(self, code: str, *, verifier: str, nonce: str) -> IdentityClaims:
        try:
            claims = run_to_completion(asyncio.wait_for(
                self._verifier.exchange_and_verify(code, self.callback, nonce, verifier),
                timeout=TIMEOUT_SECONDS,
            ))
        except (TimeoutError, httpx.TimeoutException, httpx.TransportError) as error:
            self._unreachable_since = self._clock()
            raise ProviderUnreachable(self.name) from error
        except DomainException as error:
            self._unreachable_since = None
            raise PermissionError("provider claims unavailable") from error
        self._unreachable_since = None
        return IdentityClaims(
            provider=self.name,
            subject=claims.subject,
            issuer=self.issuer,
            audience=self.audience,
            nonce=nonce,  # v1 refused the token unless its nonce equals this one
            verified_email=claims.email if claims.email_verified else None,
            profile={"displayName": claims.name or "", "works": []},
        )

    def reachable(self) -> bool:
        """False after the provider failed to answer, until it answers again or five
        minutes pass (the next renewal then shows what a sign-in finds)."""
        if self._unreachable_since is None:
            return True
        return self._clock() - self._unreachable_since >= REACHABLE_AFTER_SECONDS


class GoogleIdentityProvider(_RealIdentityProvider):
    name, issuer = "google", GOOGLE_ISSUER

    def __init__(self, *, client_id: str, client_secret: str, origin: str,
                 client_factory: Callable[..., httpx.AsyncClient] | None = None, **options):
        verifier = _RoutedGoogle(client_id, client_secret,
                                 client_factory=client_factory or network_client)
        super().__init__(verifier, client_id=client_id, origin=origin, **options)


class OrcidIdentityProvider(_RealIdentityProvider):
    name, issuer = "orcid", ORCID_ISSUER

    def __init__(self, *, client_id: str, client_secret: str, origin: str,
                 client_factory: Callable[..., httpx.AsyncClient] | None = None, **options):
        verifier = _RoutedOrcid(client_id, client_secret,
                                client_factory=client_factory or network_client)
        super().__init__(verifier, client_id=client_id, origin=origin, **options)


SECRET_KEYS = {
    "google": ("googleClientId", "googleClientSecret"),
    "orcid": ("orcidClientId", "orcidClientSecret"),
}
ADAPTERS = {"google": GoogleIdentityProvider, "orcid": OrcidIdentityProvider}
ISSUERS = {"google": GOOGLE_ISSUER, "orcid": ORCID_ISSUER}


class UnconfiguredIdentityProvider:
    """A provider the production profile has no real adapter for (no client or secret in
    its private environment; BR6.7, BR7.1, NFR4.5). It is registered at the arrival page
    like a real adapter, so the fixture is never chosen in its place, and it reports
    itself unconfigured: `ArrivalIdentityService.begin` refuses it, as a provider timeout
    is refused, before anything is written. It holds no secret and reaches no network."""

    unconfigured = True

    def __init__(self, name: str, *, origin: str):
        if name not in ADAPTERS:
            raise ValueError("unsupported provider")
        self.name, self.issuer, self.audience = name, ISSUERS[name], "unconfigured"
        self.callback = origin + ARRIVAL_PATH + name

    def exchange(self, code: str, *, verifier: str, nonce: str) -> IdentityClaims:
        raise ProviderUnreachable(self.name)

    def reachable(self) -> bool:
        return False


def production_identity_providers(profile, environment: dict, *,
                                  client_factories: dict | None = None) -> dict:
    """Both providers for the production profile: the real adapter its private
    environment configures, or `UnconfiguredIdentityProvider` for a provider whose client
    or secret is missing (BR6.7; your decision of 2026-10-24, so no fixture is ever
    chosen in production). A synthetic profile gets none, so it keeps the fixtures
    (BR7.1). `client_factories` (U8 plan Step 56(c)) gives a real adapter its client
    factory by provider name; the composition hands in its counting wrapper."""
    if not getattr(profile, "is_production", False):
        return {}
    factories = client_factories or {}
    chosen = {}
    for name, (client_key, secret_key) in SECRET_KEYS.items():
        client_id, secret = environment.get(client_key), environment.get(secret_key)
        if isinstance(client_id, str) and client_id and isinstance(secret, str) and (
            len(secret) >= 16
        ):
            chosen[name] = ADAPTERS[name](client_id=client_id, client_secret=secret,
                                          origin=profile.origin,
                                          client_factory=factories.get(name))
        else:
            chosen[name] = UnconfiguredIdentityProvider(name, origin=profile.origin)
    return chosen
