"""The production browser boundary (D7, security-design § 4; U8 plan Step 9).

TLS ends at Cloudflare's edge in production, and at the public stand-in in the composed
realm; the tunnel or the stand-in reaches the host over loopback HTTP. So the scheme is
a fact of the deployment, never of a header:

- **The scheme.** The outermost middleware sets the request's scheme to `https` for a
  request whose `Host` is exactly the profile's public authority (`docsuri.rvnnt.dev`
  in production, `127.0.0.1:18110` in the composed realm). Every other request keeps
  `http`, so it reaches the health routes and no browser route (the built route class
  refuses a non-https request). No `X-Forwarded-*` or `Forwarded` header is ever read,
  and Uvicorn runs with `proxy_headers=False` (`SERVER_SETTINGS`).
- **Host names.** The public authority, `127.0.0.1` and the listen authority; every
  other host is refused before anything else runs.
- **Headers.** The built set, plus `form-action 'self' https://accounts.google.com
  https://orcid.org`, `Strict-Transport-Security: max-age=31536000` on public-origin
  answers, `Permissions-Policy: camera=(), microphone=(), geolocation=()` and
  `Cross-Origin-Opener-Policy: same-origin`, on every answer.
- **Caching.** `public, max-age=31536000, immutable` only for files the build manifest
  (`dist/.docsuri-build.json`) lists as content-hashed, and their `.gz` copy for a
  browser that accepts gzip, with `Vary: Accept-Encoding`. Everything else is
  `no-store`.
- **The client address (D2).** For each request the boundary sets AccountAccess's
  `CLIENT_ADDRESS` from `entry_limits.address_key`: the one `CF-Connecting-IP` only on a
  public-origin request, the socket's peer on a loopback-origin one. A sign-in limit's
  refusal answers the built busy answer, and the boundary adds its wait as
  `Retry-After` (security-design § 3.2).
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path

from .local_browser import request_identifier
from .modules.accounts.entry_limits import CLIENT_ADDRESS, REFUSAL, address_key

BUILD_MANIFEST = ".docsuri-build.json"
MAX_BUILD_FILES = 4096
MAX_BUILD_MANIFEST = 1024 * 1024
IMMUTABLE = "public, max-age=31536000, immutable"
NO_STORE = "no-store"
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; "
    "frame-ancestors 'none'; form-action 'self' https://accounts.google.com https://orcid.org"
)
HSTS = "max-age=31536000"
PERMISSIONS_POLICY = "camera=(), microphone=(), geolocation=()"
# Every answer carries these (security-design § 4); the boundary replaces any value an
# inner layer set, so no route can weaken them.
FIXED_HEADERS = (
    (b"content-security-policy", CONTENT_SECURITY_POLICY.encode()),
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"no-referrer"),
    (b"permissions-policy", PERMISSIONS_POLICY.encode()),
    (b"cross-origin-opener-policy", b"same-origin"),
)
_REPLACED = frozenset(
    {name for name, _ in FIXED_HEADERS} | {b"strict-transport-security", b"cache-control"}
)
_BUILD_PATH = re.compile(r"[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*")

# Step 9's server settings (security-design § 4, reliability-design § 15): loopback
# plain HTTP, no forwarded header trusted, no access log, one worker.
SERVER_SETTINGS = {
    "host": "127.0.0.1",
    "proxy_headers": False,
    "access_log": False,
    "timeout_graceful_shutdown": 10,
    "workers": 1,
    "limit_concurrency": 32,
    "backlog": 16,
    # No `LOGGING_CONFIG` (Step 79(a)): Uvicorn's loggers keep propagating to the root
    # handler `log_events.configure` installed, which keeps only a record's type and
    # location, so a traceback never reaches standard error.
    "log_config": None,
}


def server_config(app, port: int, **extra):
    """The Uvicorn configuration every v2 listener runs with. `forwarded_allow_ips` is
    never set, and `proxy_headers` stays off, so no header can set the scheme, the host
    name or the client address."""
    import uvicorn

    if set(extra) & set(SERVER_SETTINGS) or "forwarded_allow_ips" in extra:
        raise ValueError("the server settings are fixed")
    return uvicorn.Config(app, port=port, **SERVER_SETTINGS, **extra)


@dataclass(frozen=True)
class BuildFile:
    path: str
    sha256: str
    size: int
    gzip: bool


class BuildManifest:
    """The release build's file list (`dist/.docsuri-build.json`).

    Format, written by `scripts/u8_build_workspace.py`: `{"version": 1, "files": [{"path",
    "sha256", "size", "contentHashed"}]}`. Every content-hashed file has a `.gz` copy
    beside it. Each listed content-hashed file is checked against its digest and size
    when the manifest loads, so the host serves only the bytes the build listed."""

    def __init__(self, folder: Path, files: dict[str, BuildFile]):
        self.folder = folder
        self.files = files

    @classmethod
    def empty(cls, folder: Path) -> BuildManifest:
        return cls(folder, {})

    @classmethod
    def load(cls, folder: Path) -> BuildManifest:
        path = folder / BUILD_MANIFEST
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BUILD_MANIFEST:
            raise ValueError("build manifest must be a bounded regular file")
        value = json.loads(path.read_bytes())
        if (
            not isinstance(value, dict)
            or value.get("version") != 1
            or not isinstance(value.get("files"), list)
            or len(value["files"]) > MAX_BUILD_FILES
        ):
            raise ValueError("build manifest outside its format")
        files = {}
        for item in value["files"]:
            if not isinstance(item, dict) or set(item) != {
                "path", "sha256", "size", "contentHashed"
            }:
                raise ValueError("build manifest entry outside its format")
            name = item["path"]
            if (
                not isinstance(name, str)
                or _BUILD_PATH.fullmatch(name) is None
                or ".." in name.split("/")
                or type(item["contentHashed"]) is not bool
            ):
                raise ValueError("build manifest path outside its form")
            if not item["contentHashed"]:
                continue
            entry = BuildFile(name, item["sha256"], item["size"], gzip=True)
            raw = _regular_bytes(folder / name)
            if len(raw) != entry.size or hashlib.sha256(raw).hexdigest() != entry.sha256:
                raise ValueError("a content-hashed build file differs from its manifest")
            _regular_bytes(folder / (name + ".gz"))
            files["/" + name] = entry
        return cls(folder, files)

    def lookup(self, path: str) -> BuildFile | None:
        return self.files.get(path)


def _regular_bytes(path: Path) -> bytes:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError("a build file must be a regular file")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            return stream.read()
    finally:
        os.close(descriptor)


def accepts_gzip(value: str) -> bool:
    """True when `Accept-Encoding` names gzip with a non-zero quality."""
    for part in value.split(","):
        token, _, parameters = part.strip().partition(";")
        if token.strip().lower() != "gzip":
            continue
        quality = parameters.strip().lower()
        if quality.startswith("q="):
            try:
                return float(quality[2:]) > 0
            except ValueError:
                return False
        return True
    return False


@dataclass(frozen=True)
class BoundaryHosts:
    """The host names one listener accepts: the public authority, bare `127.0.0.1`, and
    its own listen authority."""

    public_authority: str
    listen_authority: str

    @classmethod
    def for_profile(cls, profile) -> BoundaryHosts:
        from .u8_profile import listen_port, public_authority

        return cls(public_authority(profile), f"127.0.0.1:{listen_port(profile)}")

    @property
    def accepted(self) -> frozenset[str]:
        return frozenset({self.public_authority, "127.0.0.1", self.listen_authority})

    @property
    def trusted_hosts(self) -> tuple[str, ...]:
        """The names without ports, for the built `TrustedHostMiddleware`."""
        return tuple(sorted({name.split(":", 1)[0] for name in self.accepted}))


class ProductionBoundary:
    """D7's outermost layer. `context` (the request context) runs just inside it."""

    def __init__(self, hosts: BoundaryHosts, build: BuildManifest, *, context=None):
        self.hosts = hosts
        self.build = build
        self.context = context

    @property
    def trusted_hosts(self) -> tuple[str, ...]:
        return self.hosts.trusted_hosts

    def wrap(self, app):
        inner = app if self.context is None else self.context.wrap(app)
        return _BoundaryApp(inner, self)


def _header(scope, name: bytes) -> list[bytes]:
    return [value for key, value in scope.get("headers", ()) if key.lower() == name]


class _BoundaryApp:
    def __init__(self, app, boundary: ProductionBoundary):
        self.app = app
        self.boundary = boundary

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)
        hosts = _header(scope, b"host")
        host = hosts[0].decode("latin-1") if len(hosts) == 1 else None
        if host not in self.boundary.hosts.accepted:
            return await self._refuse(send, public=False)
        public = host == self.boundary.hosts.public_authority
        # The scheme follows the host name alone; a forwarded header never sets it.
        scope = dict(scope, scheme=("https" if public else "http"))
        if scope["type"] == "websocket":
            return await self._refuse(send, public=public)
        if scope["method"] in ("GET", "HEAD"):
            entry = self.boundary.build.lookup(scope["path"])
            if entry is not None:
                return await self._serve(scope, send, entry, public=public)
        connecting = [
            value.decode("latin-1") for value in _header(scope, b"cf-connecting-ip")
        ]
        peer = (scope.get("client") or (None,))[0]
        refusal: dict = {}
        address = CLIENT_ADDRESS.set(address_key(connecting, public=public, peer=peer))
        waits = REFUSAL.set(refusal)
        try:
            return await self.app(
                scope, receive, self._headers(send, public=public, refusal=refusal)
            )
        finally:
            REFUSAL.reset(waits)
            CLIENT_ADDRESS.reset(address)

    def _headers(self, send, *, public: bool, cache: str = NO_STORE,
                 refusal: dict | None = None):
        async def bounded(message):
            if message["type"] == "http.response.start":
                wait = (refusal or {}).get("retryAfterSeconds")
                limited = message.get("status") == 429 and wait is not None
                headers = [
                    (key, value)
                    for key, value in message.get("headers", ())
                    if key.lower() not in _REPLACED
                    and not (limited and key.lower() == b"retry-after")
                ]
                headers.extend(FIXED_HEADERS)
                headers.append((b"cache-control", cache.encode()))
                if public:
                    headers.append((b"strict-transport-security", HSTS.encode()))
                if limited:
                    headers.append((b"retry-after", str(int(wait)).encode()))
                message = dict(message, headers=headers)
            await send(message)

        return bounded

    async def _refuse(self, send, *, public: bool):
        body = json.dumps(
            {
                "code": "FORBIDDEN",
                "messageKey": "request.host",
                "requestId": request_identifier(),
                "retryable": False,
            }
        ).encode()
        bounded = self._headers(send, public=public)
        await bounded(
            {
                "type": "http.response.start",
                "status": 400,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await bounded({"type": "http.response.body", "body": body})

    async def _serve(self, scope, send, entry: BuildFile, *, public: bool):
        accept = b",".join(_header(scope, b"accept-encoding")).decode("latin-1")
        compressed = accepts_gzip(accept)
        name = entry.path + (".gz" if compressed else "")
        body = _regular_bytes(self.boundary.build.folder / name)
        kind = mimetypes.guess_type(entry.path)[0] or "application/octet-stream"
        headers = [
            (b"content-type", kind.encode()),
            (b"content-length", str(len(body)).encode()),
            (b"vary", b"Accept-Encoding"),
        ]
        if compressed:
            headers.append((b"content-encoding", b"gzip"))
        bounded = self._headers(send, public=public, cache=IMMUTABLE)
        await bounded({"type": "http.response.start", "status": 200, "headers": headers})
        await bounded(
            {"type": "http.response.body", "body": b"" if scope["method"] == "HEAD" else body}
        )
