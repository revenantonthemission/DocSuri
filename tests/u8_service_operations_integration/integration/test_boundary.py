"""D7's browser boundary through the public stand-in and on loopback (U8 plan Step 10).

A real Uvicorn host with Step 9's server settings listens on the realm's application
port (18109); the public stand-in (`scripts/u8_tunnel_standin.py`) terminates TLS on
18110 and forwards to it. One probe route of the built route class stands for a browser
route; the health routes are the shared host's own. The workspace build is a small
fixture build with its manifest.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import socket
import ssl
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest
import uvicorn
from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from backend.local_browser import boundary_route
from backend.local_host import assemble
from backend.production_boundary import (
    BoundaryHosts,
    BuildManifest,
    ProductionBoundary,
    server_config,
)
from backend.request_context import RequestContext
from backend.transactions import Busy
from backend.u8_profile import listen_port
from docsuri_ops.local_transport import inspect_transport

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

from u8_tunnel_standin import ACTIVE_FILE, TunnelStandin, set_route  # noqa: E402

HASHED = "assets/app-3f9a1c2b.js"
STYLE = "assets/app-5d6e7f80.css"
UNLISTED = "assets/other-9b8c7d6e.js"
SCRIPT = b"console.log('docsuri');\n" * 64
SHEET = b"body { color: #222; }\n" * 64
HASHED_FILES = {HASHED: SCRIPT, STYLE: SHEET}
WEAK_CACHE = "public, max-age=600"
# Security-design section 4's headers, written out as literals (Step 84(e)).
LITERAL_HEADERS = {
    "content-security-policy": (
        "default-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; "
        "frame-ancestors 'none'; form-action 'self' https://accounts.google.com "
        "https://orcid.org"
    ),
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "permissions-policy": "camera=(), microphone=(), geolocation=()",
    "cross-origin-opener-policy": "same-origin",
}
FORGED = {
    "x-forwarded-proto": "http",
    "x-forwarded-for": "198.51.100.7",
    "x-forwarded-host": "elsewhere.example",
    "forwarded": "for=198.51.100.7;proto=http;host=elsewhere.example",
}


def precompressed(name: str, body: bytes) -> bytes:
    """A `.gz` no per-answer compressor writes: the file's name, a 2009 time, level 1."""
    buffer = io.BytesIO()
    with gzip.GzipFile(
        filename=name, mode="wb", fileobj=buffer, mtime=1234567890, compresslevel=1
    ) as stream:
        stream.write(body)
    return buffer.getvalue()


def manifest_entry(path: str, body: bytes, hashed: bool) -> dict:
    return {
        "path": path, "sha256": hashlib.sha256(body).hexdigest(),
        "size": len(body), "contentHashed": hashed,
    }


def write_build(folder: Path) -> Path:
    (folder / "assets").mkdir(parents=True)
    files = []
    for path, body in HASHED_FILES.items():
        (folder / path).write_bytes(body)
        (folder / (path + ".gz")).write_bytes(precompressed(Path(path).name, body))
        files.append(manifest_entry(path, body, True))
    index = b"<!doctype html><title>DocSuri</title>"
    (folder / "index.html").write_bytes(index)
    files.append(manifest_entry("index.html", index, False))
    # Present in the folder, absent from the manifest.
    (folder / UNLISTED).write_bytes(b"console.log('unlisted');\n")
    (folder / ".docsuri-build.json").write_text(json.dumps({"version": 1, "files": files}))
    return folder


def wait_port(port: int) -> None:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.05)
    raise AssertionError(f"port {port} did not open")


@pytest.fixture(scope="module")
def served(realm, tmp_path_factory):
    router = APIRouter(route_class=boundary_route(realm.origin))

    @router.get("/probe/scheme")
    async def probe(request: Request):
        return {
            "scheme": request.url.scheme,
            "host": request.headers.get("host"),
            "client": request.client.host,
            "connectingIp": request.headers.get("cf-connecting-ip"),
        }

    @router.get("/probe/raise")
    async def probe_raise():
        # Unhandled: Starlette's ServerErrorMiddleware answers 500 outside local_boundary.
        raise RuntimeError("probe failure")

    @router.get("/probe/busy")
    async def probe_busy():
        raise Busy("probe busy")

    @router.get("/probe/cached")
    async def probe_cached():
        return JSONResponse({"cached": True}, headers={"Cache-Control": WEAK_CACHE})

    @router.get("/probe/stream")
    async def probe_stream():
        async def frames():
            yield b"id: 1\ndata: one\n\n"
            yield b"id: 2\ndata: two\n\n"

        return StreamingResponse(
            frames(), media_type="text/event-stream", headers={"Cache-Control": WEAK_CACHE}
        )

    asset = tmp_path_factory.mktemp("asset") / "figure.png"
    asset.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)

    @router.get("/probe/asset")
    async def probe_asset():
        return FileResponse(asset, headers={"Cache-Control": WEAK_CACHE})

    @router.get("/probe/weak")
    async def probe_weak():
        return {"weak": True}

    build = write_build(tmp_path_factory.mktemp("build"))
    boundary = ProductionBoundary(
        BoundaryHosts.for_profile(realm), BuildManifest.load(build),
        context=RequestContext(None, None),
    )
    app = assemble(realm, routers=(router,), boundary=boundary)

    @app.middleware("http")
    async def weaken(request: Request, call_next):
        # Added after `assemble`: outside local_boundary, inside the boundary.
        response = await call_next(request)
        if request.url.path == "/probe/weak":
            response.headers["Content-Security-Policy"] = "default-src *"
            response.headers["Referrer-Policy"] = "unsafe-url"
            response.headers["Cache-Control"] = WEAK_CACHE
        return response

    server = uvicorn.Server(server_config(app, listen_port(realm), log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    wait_port(listen_port(realm))
    set_route(realm, "v2-host")
    standin = TunnelStandin(realm)
    certificate = inspect_transport(realm).certificate
    try:
        with standin.running():
            yield ssl.create_default_context(cafile=str(certificate))
    finally:
        server.should_exit = True
        thread.join(15)
        (realm.root / ACTIVE_FILE).unlink(missing_ok=True)


def public(context) -> httpx.Client:
    return httpx.Client(base_url="https://127.0.0.1:18110", verify=context, timeout=10)


def loopback() -> httpx.Client:
    return httpx.Client(base_url="http://127.0.0.1:18109", timeout=10)


def test_a_request_through_the_standin_reaches_its_browser_route_as_https(served):
    with public(served) as http:
        answer = http.get("/probe/scheme", headers={"cf-connecting-ip": "203.0.113.9"})
    assert answer.status_code == 200, answer.text
    value = answer.json()
    assert value["scheme"] == "https" and value["host"] == "127.0.0.1:18110"
    # The stand-in replaces any incoming connecting address with the socket's peer.
    assert value["connectingIp"] == "127.0.0.1"


@pytest.mark.parametrize("name", sorted(FORGED))
def test_a_forged_forwarded_header_changes_neither_scheme_nor_client(served, name):
    with loopback() as http:
        public_host = http.get(
            "/probe/scheme", headers={"host": "127.0.0.1:18110", name: FORGED[name]}
        )
        local_host = http.get(
            "/probe/scheme",
            headers={"host": "127.0.0.1:18109", name: FORGED[name], "x-forwarded-proto": "https"},
        )
    assert public_host.status_code == 200
    assert public_host.json()["scheme"] == "https"
    assert public_host.json()["client"] == "127.0.0.1"
    # A loopback host name stays http whatever a header says: no browser route.
    assert local_host.status_code == 403


def test_a_request_for_loopback_reaches_the_health_routes_and_no_browser_route(served):
    with loopback() as http:
        for host in ("127.0.0.1:18109", "127.0.0.1"):
            live = http.get("/health/live", headers={"host": host})
            assert live.status_code == 200 and live.json()["process"] == "alive"
            browser = http.get("/probe/scheme", headers={"host": host})
            assert browser.status_code == 403 and browser.json()["code"] == "FORBIDDEN"


@pytest.mark.parametrize(
    "host", ["elsewhere.example", "docsuri.rvnnt.dev", "127.0.0.1:9999", "localhost:18109"]
)
def test_a_host_name_other_than_the_accepted_ones_is_refused(served, host):
    with loopback() as http:
        answer = http.get("/health/live", headers={"host": host})
    assert answer.status_code == 400
    assert answer.json()["messageKey"] == "request.host"


def assert_fallback(answer: httpx.Response) -> None:
    """The shared host's fallback over the repository's `frontend/dist`."""
    if answer.status_code == 503:
        assert answer.json()["messageKey"] == "build.missing"
    else:
        assert answer.status_code == 200, answer.text


def test_the_cacheable_answer_is_literal_and_every_other_is_no_store(served):
    with public(served) as http:
        for path in HASHED_FILES:
            for encoding in ("gzip", "identity"):
                answer = http.get(f"/{path}", headers={"accept-encoding": encoding})
                assert answer.status_code == 200
                assert answer.headers.get_list("cache-control") == [
                    "public, max-age=31536000, immutable"
                ]
            head = http.head(f"/{path}", headers={"accept-encoding": "gzip"})
            assert head.status_code == 200
            assert head.headers.get_list("cache-control") == [
                "public, max-age=31536000, immutable"
            ]
        unlisted = http.get(f"/{UNLISTED}")
        shell = http.get("/index.html")
        others = {
            "cached": (http.get("/probe/cached"), 200),
            "stream": (http.get("/probe/stream"), 200),
            "asset": (http.get("/probe/asset"), 200),
            "method": (http.post("/probe/scheme"), 405),
            "raise": (http.get("/probe/raise"), 500),
            "busy": (http.get("/probe/busy"), 429),
            "weak": (http.get("/probe/weak"), 200),
            "health": (http.get("/health/live"), 200),
        }
    with loopback() as http:
        others["loopback-browser"] = (http.get("/probe/scheme"), 403)
        others["loopback-health"] = (http.get("/health/live"), 200)
    assert_fallback(unlisted)
    assert_fallback(shell)
    assert unlisted.content != b"console.log('unlisted');\n"
    for answer in (unlisted, shell):
        assert answer.headers.get_list("cache-control") == ["no-store"]
    for name, (answer, status) in others.items():
        assert answer.status_code == status, (name, answer.status_code)
        assert answer.headers.get_list("cache-control") == ["no-store"], name


def test_hashed_scripts_and_styles_are_cached_a_year_and_sent_precompressed(served):
    with public(served) as http:
        for path, body in HASHED_FILES.items():
            with http.stream("GET", f"/{path}", headers={"accept-encoding": "gzip"}) as answer:
                raw = b"".join(answer.iter_raw())
                assert answer.status_code == 200
                assert answer.headers.get_list("vary") == ["Accept-Encoding"]
                assert answer.headers.get_list("content-encoding") == ["gzip"]
            assert raw == precompressed(Path(path).name, body)
            assert raw != gzip.compress(body, mtime=0)
            for encoding in ("identity", "gzip;q=0", "br"):
                plain = http.get(f"/{path}", headers={"accept-encoding": encoding})
                assert plain.status_code == 200
                assert plain.headers.get_list("vary") == ["Accept-Encoding"]
                assert "content-encoding" not in plain.headers, encoding
                assert plain.content == body, encoding


def assert_literal_headers(answer: httpx.Response, *, public_origin: bool, name: str) -> None:
    for header, value in LITERAL_HEADERS.items():
        assert answer.headers.get_list(header) == [value], (name, header)
    if public_origin:
        assert answer.headers.get_list("strict-transport-security") == ["max-age=31536000"], name
    else:
        assert "strict-transport-security" not in answer.headers, name


def test_every_kind_of_answer_carries_the_literal_headers(served):
    with public(served) as http:
        answers = {
            "scheme": http.get("/probe/scheme"),
            "cached": http.get("/probe/cached"),
            "method": http.post("/probe/scheme"),
            "raise": http.get("/probe/raise"),
            "busy": http.get("/probe/busy"),
            "hashed-get": http.get(f"/{HASHED}"),
            "hashed-head": http.head(f"/{HASHED}"),
            "stream": http.get("/probe/stream"),
            "asset": http.get("/probe/asset"),
            "weak": http.get("/probe/weak"),
            "health": http.get("/health/live"),
        }
    with loopback() as http:
        local = {
            "health": http.get("/health/live"),
            "browser": http.get("/probe/scheme"),
            "host": http.get("/health/live", headers={"host": "elsewhere.example"}),
        }
    statuses = {name: answer.status_code for name, answer in answers.items()}
    assert statuses == {
        "scheme": 200, "cached": 200, "method": 405, "raise": 500, "busy": 429,
        "hashed-get": 200, "hashed-head": 200, "stream": 200, "asset": 200, "weak": 200,
        "health": 200,
    }
    assert {name: answer.status_code for name, answer in local.items()} == {
        "health": 200, "browser": 403, "host": 400,
    }
    assert local["host"].json()["messageKey"] == "request.host"
    for name, answer in answers.items():
        assert_literal_headers(answer, public_origin=True, name=name)
    for name, answer in local.items():
        assert_literal_headers(answer, public_origin=False, name=name)


def test_the_server_settings_trust_no_forwarded_header():
    config = server_config(object(), 18109)
    assert config.log_config is None
    assert config.proxy_headers is False and config.access_log is False
    assert (config.host, config.workers, config.limit_concurrency, config.backlog) == (
        "127.0.0.1", 1, 32, 16,
    )
    assert config.timeout_graceful_shutdown == 10
    with pytest.raises(ValueError):
        server_config(object(), 18109, forwarded_allow_ips="*")
    with pytest.raises(ValueError):
        server_config(object(), 18109, proxy_headers=True)
