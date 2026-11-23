"""R-08: the request-body limit on the public host (U8 plan Step 40; security-design § 4).

The complete host runs under Uvicorn with Step 9's settings on the realm's application
port, behind the public stand-in on `https://127.0.0.1:18110`. Through the stand-in, a
signed-in member's largest legitimate body passes the boundary's bound (64 KiB for the
public host), and one byte more is refused as INVALID_ARGUMENT before any owner work.
The production host's entry is in the same list; every other host keeps 8 KiB.
"""

from __future__ import annotations

import asyncio
import json
import ssl
import sys
import threading
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
import uvicorn
from starlette.requests import Request

from backend.local_browser import BrowserDenied, read_payload
from backend.modules.accounts.local_http import ENTRY_POLICY
from backend.production_boundary import server_config
from backend.u8_host import compose, host_app
from backend.u8_profile import listen_port
from docsuri_ops.local_transport import inspect_transport
from tests.u8_service_operations_integration.conftest import SIGN_IN_PASSWORD

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

from u8_tunnel_standin import ACTIVE_FILE, TunnelStandin, set_route  # noqa: E402

LIMIT = 65_536
DRAFT = "/api/v2/c07/save-draft"


def wait_port(port: int) -> None:
    import socket
    import time

    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.05)
    raise AssertionError(f"port {port} did not open")


@pytest.fixture(scope="module")
def served(realm):
    composition = compose(realm)
    app = host_app(composition)
    app.state.control_capacity.refresh()
    server = uvicorn.Server(server_config(app, listen_port(realm), log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        wait_port(listen_port(realm))
        set_route(realm, "v2-host")
        certificate = inspect_transport(realm).certificate
        with TunnelStandin(realm).running():
            yield ssl.create_default_context(cafile=str(certificate))
    finally:
        server.should_exit = True
        thread.join(15)
        (realm.root / ACTIVE_FILE).unlink(missing_ok=True)
        composition.close()


def draft(size: int) -> bytes:
    """A save-draft body of exactly `size` bytes: its text fills the rest."""
    value = {"contextId": str(uuid4()), "draftId": str(uuid4()), "kind": "research-question",
             "baseRevision": None, "text": "", "policy": {"policyId": "x", "revision": "1"}}
    empty = len(json.dumps(value, separators=(",", ":")).encode())
    value["text"] = "가" * ((size - empty) // 3) + "a" * ((size - empty) % 3)
    body = json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode()
    assert len(body) == size
    return body


def test_the_largest_legitimate_body_passes_and_one_more_byte_is_refused(
    served, sign_in_account,
):
    _, email = sign_in_account("sign-in-member")
    with httpx.Client(base_url="https://127.0.0.1:18110", verify=served, timeout=20) as http:
        csrf = http.get("/api/v2/session").json()["csrfToken"]
        headers = {"origin": "https://127.0.0.1:18110", "content-type": "application/json"}
        login = http.post("/api/v2/c02/access-login", headers={
            **headers, "x-csrf-token": csrf, "idempotency-key": str(uuid4())},
            content=json.dumps({"email": email, "password": SIGN_IN_PASSWORD,
                                "policyRef": ENTRY_POLICY}))
        assert login.status_code == 200 and login.json()["state"] == "authenticated", login.text
        csrf = http.get("/api/v2/session").json()["csrfToken"]

        def send(body: bytes) -> httpx.Response:
            return http.post(DRAFT, content=body, headers={
                **headers, "x-csrf-token": csrf, "idempotency-key": str(uuid4())})

        accepted = send(draft(LIMIT))
        # Past the bound and the schema, the owner answers: the draft's context is not
        # the member's, so it is missing (never a too-large refusal).
        assert (accepted.status_code, accepted.json()["code"]) == (404, "NOT_FOUND"), (
            accepted.text)
        refused = send(draft(LIMIT + 1))
        # `ControlAdmission`'s own bound (the same 64 KiB) refuses it first, as 413.
        assert (refused.status_code, refused.json()["code"]) == (413, "INVALID_ARGUMENT")
        assert set(refused.json()) == {"code", "requestId", "retryable", "messageKey"}


def request_for(host: str, body: bytes) -> Request:
    sent = {"done": False}

    async def receive():
        if sent["done"]:
            return {"type": "http.request", "body": b"", "more_body": False}
        sent["done"] = True
        return {"type": "http.request", "body": body, "more_body": False}

    return Request({"type": "http", "method": "POST", "path": "/x", "headers": [
        (b"host", host.encode()), (b"content-type", b"application/json")]}, receive)


@pytest.mark.parametrize("host,limit", [
    ("docsuri.rvnnt.dev", LIMIT), ("127.0.0.1:18110", LIMIT), ("127.0.0.1:18109", 8192),
    ("127.0.0.1", 8192), ("elsewhere.example", 8192),
])
def test_each_host_has_its_own_bound(host, limit):
    class Any:
        @staticmethod
        def model_validate(value):
            class Dumped:
                @staticmethod
                def model_dump(**options):
                    return value
            return Dumped()

    fits = json.dumps({"text": "a" * (limit - 12)}).encode()
    assert len(fits) == limit
    assert asyncio.run(read_payload(request_for(host, fits), Any))["text"]
    with pytest.raises(BrowserDenied):
        asyncio.run(read_payload(request_for(host, fits + b" "), Any))
