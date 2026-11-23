"""The composed host's own routes behind D7's boundary (U8 plan Steps 10 and 12; A9).

`host_app` assembles the shared host (`local_host.assemble`) with the boundary it is
given: the capability catalog over HTTP, and the static workspace route, which answers a
missing API or health route as not ready, refuses a path outside the build, and serves
the build's index (or says the build is missing) for every other path.
"""

from __future__ import annotations

import httpx
import pytest
from docsuri_shared.workspace import wire

from backend.u8_host import compose, host_app

ORIGIN = "https://127.0.0.1:18110"


@pytest.fixture
def app(realm):
    composition = compose(realm)
    try:
        yield host_app(composition)
    finally:
        composition.close()


async def ask(app, path: str) -> httpx.Response:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                 base_url=ORIGIN) as client:
        return await client.get(path)


async def test_the_capability_list_answers_a_caller_with_no_session_its_projection(app):
    """Since Step 39 the capability route answers from the registry: a caller with no
    session gets only the public projection (BR5.9), in its wire shape."""
    answer = await ask(app, "/api/v2/capabilities")
    assert answer.status_code == 200, answer.text
    page = wire.HostPublicCapabilityPage.model_validate(answer.json())
    assert {item.capabilityId.root for item in page.items} >= {
        "account.entry", "provider.google", "provider.orcid", "provider.resend"}
    assert app.state.capability_catalog  # the signed-in catalog's rows


async def test_api_work_waits_for_admission_until_capacity_is_refreshed(app):
    """Before the capacity refresher has run, `ControlAdmission` admits no API request:
    the answer is retryable, never a route's own work."""
    answer = await ask(app, "/api/v2/c99/no-such-operation")
    assert answer.status_code == 503
    assert answer.json()["code"] == "NOT_READY" and answer.json()["retryable"] is True
    assert answer.headers["retry-after"] == "1"


async def test_an_unmounted_health_path_is_not_ready_and_not_retryable(app):
    answer = await ask(app, "/health/nothing")
    assert answer.status_code == 503
    assert answer.json()["code"] == "NOT_READY" and answer.json()["retryable"] is False


async def test_a_path_outside_the_build_is_refused(app):
    answer = await ask(app, "/..%2F..%2Fbackend%2Fu8_host.py")
    assert answer.status_code in (403, 404)
    assert "u8_host" not in answer.text


async def test_a_workspace_path_serves_the_index_or_says_the_build_is_missing(app):
    from pathlib import Path

    import backend.local_host as local_host

    answer = await ask(app, "/library/some-deep-link")
    build = Path(local_host.__file__).resolve().parents[1] / "frontend/dist"
    if (build / "index.html").is_file():
        assert answer.status_code == 200
        assert answer.headers["content-type"].startswith("text/html")
    else:
        assert answer.status_code == 503
        assert answer.json()["messageKey"] == "build.missing"
