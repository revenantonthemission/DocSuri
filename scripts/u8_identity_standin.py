"""The composed realm's identity stand-in: Google's and ORCID's authorization pages.

Mocking rules of the U8 unit-test instructions and Step 43 ("The stand-ins"), built early
in Step 20, whose provider first sign-in test runs through it:

- it serves on `https://localhost:18114`, a different site from the realm's public origin
  `https://127.0.0.1:18110`, so a browser treats its redirect back as cross-site (D3). It
  listens on the loopback addresses only and terminates TLS with its own certificate for
  `localhost`, made once per run in the run root (`identity-standin-tls.crt` and `.key`,
  0600);
- its two pages sit at the paths of the real addresses v1's verifiers build: Google's
  `/o/oauth2/v2/auth` and ORCID's `/oauth/authorize`. A page checks the authorization
  request: the realm's registered client, the workspace page `/sign-in/callback/{provider}`
  as `redirect_uri`, `response_type=code`, the scope, a state, a nonce and an S256 PKCE
  challenge;
- it redirects back with `code` and `state`, or with `error` and `state` when the scenario
  says the person refused. A Google sign-in's redirect also carries `scope`, `authuser`
  and `prompt`, as Google's own does (R-09);
- token exchange and ID-token verification run against recorded answers signed with test
  keys (`RecordedAnswers`): a fake transport for the real adapters that answers the token,
  tokeninfo and JWKS calls for a code this stand-in issued, once, only for its client,
  its redirect and the PKCE verifier its challenge was made from;
- it refuses the production profile.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import datetime as dt
import hashlib
import json
import os
import secrets
import ssl
import sys
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT, ROOT / "ops/src"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

# The repository's own packages resolve only once the paths above are on sys.path.
from backend.local_profile import LocalProfile, private_bytes  # noqa: E402

PORT = 18114
HOST = "localhost"
ORIGIN = f"https://{HOST}:{PORT}"
# The pages, at the paths of the real addresses (v1's `integrations/oidc.py`).
PAGES = {"/o/oauth2/v2/auth": "google", "/oauth/authorize": "orcid"}
SCOPES = {"google": "openid email", "orcid": "openid"}
# The keys each provider's success redirect adds beside `code` and `state`: Google's
# granted scopes, its account index and the prompt it showed; ORCID adds none.
RETURN_EXTRAS = {
    "google": {
        "scope": "email openid https://www.googleapis.com/auth/userinfo.email",
        "authuser": "0",
        "prompt": "consent",
    },
    "orcid": {},
}
# The realm's registered clients (the production profile names the real ones).
CLIENTS = {"google": "docsuri-realm.apps.example", "orcid": "APP-DOCSURIREALM0001"}
ISSUERS = {"google": "https://accounts.google.com", "orcid": "https://orcid.org"}
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
ORCID_TOKEN_URL = "https://orcid.org/oauth/token"
ORCID_JWKS_URL = "https://orcid.org/oauth/jwks"
CERTIFICATE, KEY = "identity-standin-tls.crt", "identity-standin-tls.key"
ERRORS = ("access_denied",)
MAX_HEAD = 8 * 1024
MAX_CODES = 64
TOKEN_SECONDS = 600
TIMEOUT_SECONDS = 30
KID = "identity-standin"


def require_realm(profile) -> None:
    """The stand-in serves the composed realm only, never the production profile."""
    if getattr(profile, "is_production", False) or profile.realm != "service-operations":
        raise ValueError("the identity stand-in serves only the composed realm")


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _challenge(verifier: str) -> str:
    return _b64(hashlib.sha256(verifier.encode("ascii")).digest())


def _write_private(path: Path, content: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def _certificate_valid(path: Path) -> bool:
    certificate = x509.load_pem_x509_certificate(path.read_bytes())
    names = certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    return (names.get_values_for_type(x509.DNSName) == [HOST]
            and certificate.not_valid_after_utc > dt.datetime.now(dt.UTC))


def prepare_certificate(profile) -> tuple[Path, Path]:
    """The run's own certificate for `localhost`, made once in the run root and valid
    until the run expires, shaped as the run's transport certificate is."""
    require_realm(profile)
    certificate, key = profile.root / CERTIFICATE, profile.root / KEY
    present = [path.exists() or path.is_symlink() for path in (certificate, key)]
    if any(present):
        if not all(present) or any(
            path.is_symlink() or path.stat().st_mode & 0o077 for path in (certificate, key)
        ):
            raise ValueError("identity stand-in certificate custody differs")
        if _certificate_valid(certificate):
            return certificate, key
        raise ValueError("identity stand-in certificate is no longer valid for this run")
    now = dt.datetime.now(dt.UTC)
    expiry = dt.datetime.fromtimestamp(profile.expires_at, dt.UTC)
    if not now < expiry:
        raise ValueError("the run has expired")
    private = ec.generate_private_key(ec.SECP256R1())
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, HOST)])
    made = (
        x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
        .public_key(private.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=1)).not_valid_after(expiry)
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(HOST)]), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .sign(private, hashes.SHA256())
    )
    _write_private(key, private.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption()))
    _write_private(certificate, made.public_bytes(serialization.Encoding.PEM))
    return certificate, key


def tls_context(profile) -> ssl.SSLContext:
    certificate, key = prepare_certificate(profile)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(certificate, key)
    return context


def client_context(profile) -> ssl.SSLContext:
    """A browser's trust for the stand-in: its run certificate only."""
    certificate, _ = prepare_certificate(profile)
    return ssl.create_default_context(cafile=str(certificate))


@dataclass(frozen=True)
class Identity:
    subject: str
    email: str | None = None
    name: str = "합성 연구자"


@dataclass
class Authorization:
    provider: str
    client_id: str
    redirect_uri: str
    nonce: str
    challenge: str
    identity: Identity
    used: bool = field(default=False)


class IdentityStandin:
    """The stand-in for one composed realm: who signs in at each provider, and the codes
    it issued."""

    def __init__(self, profile, *, port: int = PORT, clients: dict | None = None):
        require_realm(profile)
        self.profile, self.port = profile, port
        self.clients = dict(clients or CLIENTS)
        self.context = tls_context(profile)
        self._scenario: dict[str, Identity | str] = {}
        self.issued: dict[str, Authorization] = {}
        self._lock = threading.Lock()

    def sign_in_as(self, provider: str, identity: Identity) -> None:
        self._known(provider)
        self._scenario[provider] = identity

    def refuse(self, provider: str, error: str = "access_denied") -> None:
        self._known(provider)
        if error not in ERRORS:
            raise ValueError("unregistered provider error")
        self._scenario[provider] = error

    @staticmethod
    def _known(provider: str) -> None:
        if provider not in CLIENTS:
            raise ValueError("unsupported provider")

    def callback(self, provider: str) -> str:
        return self.profile.origin + "/sign-in/callback/" + provider

    def redirect(self, target: str) -> str:
        """The `Location` a page answers for one request target, or ValueError."""
        address = urlsplit(target)
        provider = PAGES.get(address.path)
        if provider is None:
            raise LookupError("no such page")
        query = parse_qs(address.query, strict_parsing=True)
        if any(len(values) != 1 for values in query.values()):
            raise ValueError("each parameter once")
        value = {key: values[0] for key, values in query.items()}
        state = value.get("state", "")
        if (
            value.get("client_id") != self.clients[provider]
            or value.get("redirect_uri") != self.callback(provider)
            or value.get("response_type") != "code"
            or value.get("scope") != SCOPES[provider]
            or value.get("code_challenge_method") != "S256"
            or len(value.get("code_challenge", "")) != 43
            or not 16 <= len(state) <= 256
            or not 16 <= len(value.get("nonce", "")) <= 256
        ):
            raise ValueError("authorization request outside the registration")
        chosen = self._scenario.get(provider)
        if chosen is None:
            raise ValueError("no identity signs in at this provider")
        if isinstance(chosen, str):
            return value["redirect_uri"] + "?" + urlencode({"error": chosen, "state": state})
        code = secrets.token_urlsafe(32)
        with self._lock:
            if len(self.issued) >= MAX_CODES:
                raise ValueError("finite code capacity")
            self.issued[code] = Authorization(provider, value["client_id"], value["redirect_uri"],
                                              value["nonce"], value["code_challenge"], chosen)
        return value["redirect_uri"] + "?" + urlencode(
            {"code": code, "state": state, **RETURN_EXTRAS[provider]})

    def redeem(self, code: str, *, provider: str, client_id: str, redirect_uri: str,
               verifier: str) -> Authorization:
        """A token exchange's checks: an issued, unused code for this client and redirect,
        and the PKCE verifier its challenge was made from."""
        with self._lock:
            found = self.issued.get(code)
            if (
                found is None
                or found.used
                or found.provider != provider
                or found.client_id != client_id
                or found.redirect_uri != redirect_uri
                or _challenge(verifier) != found.challenge
            ):
                raise PermissionError("authorization code unavailable")
            found.used = True
            return found

    async def handle(self, reader, writer) -> None:
        try:
            head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), TIMEOUT_SECONDS)
            if len(head) > MAX_HEAD:
                raise ValueError("request head outside the bound")
            lines = head.decode("latin-1").split("\r\n")
            parts = lines[0].split(" ")
            hosts = [line.split(":", 1)[1].strip() for line in lines[1:]
                     if line.lower().startswith("host:")]
            if len(parts) != 3 or parts[0] != "GET" or hosts != [f"{HOST}:{PORT}"]:
                raise ValueError("one GET for the stand-in's own authority")
            try:
                location = self.redirect(parts[1])
            except LookupError:
                return await _answer(writer, 404, "Not Found")
            writer.write(
                f"HTTP/1.1 302 Found\r\nlocation: {location}\r\ncache-control: no-store\r\n"
                "content-length: 0\r\nconnection: close\r\n\r\n".encode("latin-1")
            )
            await writer.drain()
        except (ValueError, asyncio.IncompleteReadError, asyncio.LimitOverrunError):
            await _answer(writer, 400, "Bad Request")
        except (TimeoutError, ConnectionError, ssl.SSLError):
            pass
        finally:
            writer.close()

    async def _start(self):
        return await asyncio.start_server(self.handle, HOST, self.port, ssl=self.context,
                                          limit=MAX_HEAD)

    async def serve(self) -> None:
        server = await self._start()
        async with server:
            await server.serve_forever()

    @contextmanager
    def running(self):
        """Serve from a background thread for the length of the block (tests)."""
        loop, stopping = asyncio.new_event_loop(), None
        started, failure = threading.Event(), []

        def main() -> None:
            nonlocal stopping
            asyncio.set_event_loop(loop)

            async def serve() -> None:
                nonlocal stopping
                stopping = asyncio.Event()
                server = await self._start()
                started.set()
                async with server:
                    await stopping.wait()

            try:
                loop.run_until_complete(serve())
            except BaseException as error:  # noqa: BLE001 - re-raised in the caller
                failure.append(error)
                started.set()
            finally:
                loop.close()

        thread = threading.Thread(target=main, daemon=True)
        thread.start()
        started.wait(10)
        if failure:
            raise failure[0]
        try:
            yield self
        finally:
            loop.call_soon_threadsafe(stopping.set)
            thread.join(10)


async def _answer(writer, status: int, reason: str) -> None:
    body = json.dumps({"code": "INVALID_ARGUMENT" if status == 400 else "NOT_FOUND"}).encode()
    writer.write(
        f"HTTP/1.1 {status} {reason}\r\ncontent-type: application/json\r\n"
        f"content-length: {len(body)}\r\nconnection: close\r\n\r\n".encode() + body
    )
    await writer.drain()


class RecordedAnswers:
    """The providers' token, tokeninfo and JWKS answers for the stand-in's codes, served
    through a fake transport the real adapters are given (`client_factory`). ORCID's ID
    tokens are RS256 tokens signed by a key made for this run of the stand-in; Google's
    claims come from its tokeninfo answer, as v1's verifier asks for them."""

    def __init__(self, standin: IdentityStandin):
        self.standin = standin
        self._key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self._google_tokens: dict[str, dict] = {}
        self.requests: list[httpx.Request] = []

    def client_factory(self, **options) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handle), **options)

    def _claims(self, found: Authorization) -> dict:
        claims = {"aud": found.client_id, "iss": ISSUERS[found.provider], "nonce": found.nonce,
                  "sub": found.identity.subject, "exp": int(time.time()) + TOKEN_SECONDS}
        if found.provider == "google":
            claims.update(email=found.identity.email, email_verified="true")
        else:
            claims["name"] = found.identity.name
        return claims

    def _redeem(self, request: httpx.Request, provider: str) -> Authorization | None:
        form = {key: values[0] for key, values in parse_qs(request.content.decode()).items()}
        if form.get("grant_type") != "authorization_code":
            return None
        try:
            return self.standin.redeem(
                form.get("code", ""), provider=provider, client_id=form.get("client_id", ""),
                redirect_uri=form.get("redirect_uri", ""), verifier=form.get("code_verifier", ""))
        except PermissionError:
            return None

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        address = str(request.url.copy_with(query=None))
        if request.method == "POST" and address in (GOOGLE_TOKEN_URL, ORCID_TOKEN_URL):
            provider = "google" if address == GOOGLE_TOKEN_URL else "orcid"
            found = self._redeem(request, provider)
            if found is None:
                return httpx.Response(400, json={"error": "invalid_grant"})
            if provider == "google":
                token = "standin-" + secrets.token_urlsafe(24)
                self._google_tokens[token] = self._claims(found)
                return httpx.Response(200, json={"id_token": token})
            return httpx.Response(200, json={"id_token": self._signed(self._claims(found))})
        if request.method == "GET" and address == GOOGLE_TOKENINFO_URL:
            claims = self._google_tokens.get(request.url.params.get("id_token", ""))
            return httpx.Response(200, json=claims) if claims else httpx.Response(400)
        if request.method == "GET" and address == ORCID_JWKS_URL:
            return httpx.Response(200, json={"keys": [self._jwk()]})
        return httpx.Response(404)

    def _signed(self, claims: dict) -> str:
        header = _b64(json.dumps({"alg": "RS256", "kid": KID}).encode())
        body = _b64(json.dumps(claims).encode())
        signature = self._key.sign(f"{header}.{body}".encode(), padding.PKCS1v15(),
                                   hashes.SHA256())
        return f"{header}.{body}.{_b64(signature)}"

    def _jwk(self) -> dict:
        numbers = self._key.public_key().public_numbers()
        return {"kty": "RSA", "kid": KID, "alg": "RS256", "use": "sig",
                "n": _b64(numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")),
                "e": _b64(numbers.e.to_bytes(3, "big"))}


def page_target(authorization_url: str) -> str:
    """The stand-in's page for a real adapter's authorization address: the same path and
    query at the stand-in's authority, as the realm's name resolution would give it."""
    address = urlsplit(authorization_url)
    if address.scheme != "https" or address.path not in PAGES or (
        f"{address.scheme}://{address.netloc}{address.path}"
        not in ("https://accounts.google.com/o/oauth2/v2/auth", "https://orcid.org/oauth/authorize")
    ):
        raise ValueError("not a registered provider authorization address")
    return f"{ORIGIN}{address.path}?{address.query}"


def load_scenario(standin: IdentityStandin, path: Path) -> None:
    """Who signs in at each provider, from a private JSON file: `{provider: {"subject":
    ..., "email": ...}}` for a sign-in, or `{provider: "access_denied"}` for a refusal."""
    for provider, chosen in json.loads(private_bytes(path, maximum=4096)).items():
        if isinstance(chosen, str):
            standin.refuse(provider, chosen)
        else:
            standin.sign_in_as(provider, Identity(chosen["subject"], chosen.get("email")))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--environment-file", required=True, type=Path)
    parser.add_argument("--scenario", type=Path)
    args = parser.parse_args()
    standin = IdentityStandin(LocalProfile.load(args.environment_file))
    if args.scenario is not None:
        load_scenario(standin, args.scenario)
    asyncio.run(standin.serve())


if __name__ == "__main__":
    main()
