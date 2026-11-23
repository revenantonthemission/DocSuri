"""Operator-only real composition, its public cancellation boundary
(`backend/modules/topics/unsubscribe.py`): the public origin is admitted only on the
cancellation path and methods, the page carries its own referrer policy and CSP, and a
browser's confirm under that policy passes the host boundary (R-15).

No database and no provider: a recording service stands in for the capability store.
Moved unchanged from `test_real_composition.py` (plan Step 35, decision L3-1).
"""

import asyncio
from types import SimpleNamespace

import pytest
from backend.local_host import assemble
from backend.modules.topics.unsubscribe import (
    HEADERS,
    PREFIX,
    PublicCancellationOrigin,
    unsubscribe_router,
)
from fastapi.testclient import TestClient

from tests.u5_topics_digests.fetch_origin import NULL_ORIGIN, form_post_origin
from tests.u5_topics_digests.real_composition_kit import PUBLIC


def test_public_cancellation_origin_is_admitted_only_on_cancellation_paths():
    seen = []

    async def inner(scope, receive, send):
        seen.append(dict(scope["headers"]).get(b"origin"))

    middleware = PublicCancellationOrigin(inner, origin=PUBLIC)
    token_path = "/api/v2/topics/email-unsubscribe/" + "z" * 43

    def call(path, origin, method="POST"):
        scope = {"type": "http", "method": method, "path": path, "headers": [(b"origin", origin)]}
        asyncio.run(middleware(scope, None, None))

    call(token_path, PUBLIC.encode())
    call(token_path, b"https://elsewhere.fixture.invalid")
    call("/api/v2/topics", PUBLIC.encode())
    call(token_path + "x", PUBLIC.encode())
    call(token_path, PUBLIC.encode(), method="DELETE")
    assert seen == [
        None,
        b"https://elsewhere.fixture.invalid",
        PUBLIC.encode(),
        PUBLIC.encode(),
        PUBLIC.encode(),
    ]
    with pytest.raises(ValueError):
        PublicCancellationOrigin(inner, origin="http://unsubscribe.fixture.invalid")


class RecordingCancellation:
    def __init__(self):
        self.calls = []

    def cancel(self, token):
        self.calls.append(token)


def boundary_client(service):
    """The real host boundary, the cancellation router and the middleware.

    Same order as `assemble_u5_real`: `local_host.assemble` installs the
    boundary, then the middleware is added outermost. No database is needed
    because the recording service stands in for the capability store.
    """
    app = assemble(
        SimpleNamespace(origin="https://127.0.0.1:18089"), routers=[unsubscribe_router(service)]
    )
    app.add_middleware(PublicCancellationOrigin, origin=PUBLIC)
    return TestClient(app, base_url="https://127.0.0.1")


FORM = {"List-Unsubscribe": "One-Click"}


def test_fetch_origin_rule_follows_the_standard():
    page = PUBLIC + PREFIX + "a" * 43
    assert form_post_origin("no-referrer", page, page) == NULL_ORIGIN
    assert form_post_origin("same-origin", page, page) == PUBLIC
    assert form_post_origin("same-origin", page, "https://other.invalid/x") == NULL_ORIGIN
    assert form_post_origin("strict-origin", page, "http://other.invalid/x") == NULL_ORIGIN
    assert form_post_origin("strict-origin-when-cross-origin", page, page) == PUBLIC
    assert form_post_origin("origin", "https://h.invalid:8443/p", page) == "https://h.invalid:8443"


def test_cancellation_page_is_served_with_its_own_referrer_policy_and_csp():
    with boundary_client(RecordingCancellation()) as client:
        page = client.get(PREFIX + "b" * 43)
        other = client.get("/health/live")
    assert page.status_code == 200
    for name, value in HEADERS.items():
        # Exactly one value: the boundary's host-wide header must not survive.
        assert page.headers.get_list(name) == [value]
    assert page.headers["referrer-policy"] == "same-origin"
    assert "form-action 'self'" in page.headers["content-security-policy"]
    # Paths other than the cancellation path keep the boundary's headers.
    assert other.headers["referrer-policy"] == "no-referrer"
    assert "form-action" not in other.headers["content-security-policy"]


def test_browser_confirm_under_the_served_policy_passes_the_boundary():
    """R-15: the page's own form POST, with the Origin a browser derives from its policy."""
    service = RecordingCancellation()
    token = "c" * 43
    with boundary_client(service) as client:
        page = client.get(PREFIX + token)
        public_url = PUBLIC + PREFIX + token
        origin = form_post_origin(page.headers["referrer-policy"], public_url, public_url)
        assert origin == PUBLIC
        confirmed = client.post(PREFIX + token, data=FORM, headers={"Origin": origin})
    assert confirmed.status_code == 200
    assert confirmed.headers["referrer-policy"] == "same-origin"
    assert service.calls == [token]


def test_the_previous_no_referrer_page_produced_a_refused_null_origin():
    """Reproduces the live failure: `no-referrer` makes the browser send `Origin: null`."""
    service = RecordingCancellation()
    public_url = PUBLIC + PREFIX + "d" * 43
    origin = form_post_origin("no-referrer", public_url, public_url)
    with boundary_client(service) as client:
        refused = client.post(PREFIX + "d" * 43, data=FORM, headers={"Origin": origin})
    assert origin == NULL_ORIGIN
    assert refused.status_code == 403
    assert refused.json()["messageKey"] == "request.origin"
    assert service.calls == []


def test_only_the_exact_origin_on_the_exact_path_and_methods_is_admitted():
    service = RecordingCancellation()
    path = PREFIX + "e" * 43
    with boundary_client(service) as client:
        # Header-less RFC 8058 one-click POST (mail provider or mail app).
        assert client.post(path, data=FORM).status_code == 200
        for origin in (
            NULL_ORIGIN,
            "https://other.invalid",
            PUBLIC + ":8443",
            "http://unsubscribe.fixture.invalid",
        ):
            assert client.post(path, data=FORM, headers={"Origin": origin}).status_code == 403
        assert client.post(path + "x", data=FORM, headers={"Origin": PUBLIC}).status_code == 403
        assert client.post("/api/v2/topics", json={}, headers={"Origin": PUBLIC}).status_code == 403
        assert client.delete(path, headers={"Origin": PUBLIC}).status_code == 403
    assert service.calls == ["e" * 43]
