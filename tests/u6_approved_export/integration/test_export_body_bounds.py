"""U6:NFR1.3: the body bounds of every export route (the shared boundary's 64 KB list).

A 65,536-byte body passes and 65,537 answers 422 on the router and 413 on the assembled
app, before routing; a body that stalls past the boundary's 5-second read bound answers
504; and the router reads every body only through `read_payload` (no FastAPI echo).
"""

import asyncio
import json
from pathlib import Path
from uuid import uuid4

import pytest
from docsuri_shared.workspace import wire

from tests.u6_approved_export import http_flows as hf

BASE = '{"connectionId": null}'
REPOSITORY = Path(__file__).resolve().parents[3]


def padded(size: int) -> bytes:
    body = BASE + " " * (size - len(BASE))
    assert len(body.encode()) == size
    return body.encode()


@pytest.fixture
def mount(realm, transactions, connect, authority, authority_b, tmp_path):
    mounted = hf.mount(realm, transactions, connect, authority, authority_b, tmp_path)
    yield mounted
    mounted.close()


def post_raw(m, body: bytes):
    return m.client.post(
        hf.PREFIX + hf.ROUTE["read_connection"],
        content=body,
        headers={"Idempotency-Key": str(uuid4()), "Content-Type": "application/json"},
    )


def test_the_size_guard_passes_the_bound_and_refuses_one_byte_more(mount):
    m = mount

    oversized = post_raw(m, padded(65537))
    assert (oversized.status_code, oversized.json()["code"]) == (422, "INVALID_ARGUMENT")
    wire.Error.model_validate(oversized.json())
    assert oversized.headers["cache-control"] == "no-store"
    assert m.rig.fake.requests == []

    accepted = post_raw(m, padded(65536))
    assert (accepted.status_code, accepted.json()["code"]) == (404, "NOT_FOUND")
    m.connect_owner()
    after = post_raw(m, padded(65536))
    assert after.status_code == 200


def test_the_assembled_app_answers_413_before_routing(realm):
    from fastapi.testclient import TestClient

    from backend.u6_host import assemble_u6

    app = assemble_u6(realm)
    with TestClient(app, base_url=realm.origin) as client:
        app.state.control_capacity.refresh()
        client.headers.update({"Origin": realm.origin})
        oversized = client.post(
            hf.PREFIX + hf.ROUTE["read_connection"],
            content=padded(65537),
            headers={"Idempotency-Key": str(uuid4()), "Content-Type": "application/json"},
        )
        inside = client.post(
            hf.PREFIX + hf.ROUTE["read_connection"],
            content=padded(65536),
            headers={
                "Idempotency-Key": str(uuid4()),
                "Content-Type": "application/json",
                "X-CSRF-Token": "0" * 64,
            },
        )

    assert (
        oversized.status_code,
        oversized.json()["code"],
        oversized.json()["messageKey"],
    ) == (413, "INVALID_ARGUMENT", "request.tooLarge")
    assert (inside.status_code, inside.json()["code"]) == (401, "UNAUTHENTICATED")


async def test_a_body_that_stalls_past_the_read_bound_answers_504(mount):
    m = mount
    path = hf.PREFIX + hf.ROUTE["read_connection"]
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "https",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": [
            (b"host", b"127.0.0.1:18099"),
            (b"origin", m.realm.origin.encode()),
            (b"content-type", b"application/json"),
            (b"idempotency-key", str(uuid4()).encode()),
            (b"x-csrf-token", m.own.csrf.encode()),
            (b"cookie", f"session_id={m.own.token}".encode()),
        ],
        "client": ("127.0.0.1", 41234),
        "server": ("127.0.0.1", 18099),
    }
    sent = []
    messages = []

    async def receive():
        if not sent:
            sent.append(True)
            return {"type": "http.request", "body": b'{"connectionId":', "more_body": True}
        await asyncio.sleep(5.3)
        return {"type": "http.request", "body": b" null}", "more_body": False}

    async def send(message):
        messages.append(message)

    await m.app(scope, receive, send)

    start = next(message for message in messages if message["type"] == "http.response.start")
    body = json.loads(
        b"".join(message["body"] for message in messages if message["type"] == "http.response.body")
    )
    assert start["status"] == 504 and body["code"] == "DEADLINE_EXCEEDED"
    assert m.refused("read_connection", {}) == "NOT_FOUND"  # no connection was created
    assert m.rig.fake.requests == []


def test_the_router_reads_the_body_only_through_read_payload():
    source = (REPOSITORY / "backend/modules/export/http.py").read_text()
    assert source.count("read_payload(") == 1
    for pattern in ("request.json(", "request.body(", "request.stream(", "request.form("):
        assert pattern not in source
