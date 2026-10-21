"""The guarded transport: origin, path identifiers, the 2,000,000-byte cap, redirects."""

import httpx
import pytest
from backend.modules.export.fake_notion import (
    OVERSIZE_DECLARED,
    OVERSIZE_STREAMED,
    REDIRECT,
    Answer,
    FakeNotion,
)
from backend.modules.export.notion_session import (
    GuardedTransport,
    RequestRefused,
    ResponseTooLarge,
    UnexpectedResponse,
)

from tests.u6_approved_export import notion_flows as nf

CAP = 2_000_000
TOKEN = nf.synthetic_token()


def client(fake: FakeNotion, *, timeout: float = 5.0) -> httpx.AsyncClient:
    guard = GuardedTransport(fake, cap_bytes=CAP, request_timeout=timeout)
    return httpx.AsyncClient(
        transport=guard,
        follow_redirects=False,
        trust_env=False,
        headers={"Authorization": f"Bearer {TOKEN}", "Notion-Version": "2026-03-11"},
    )


@pytest.fixture
def fake():
    return nf.fake_with(TOKEN, nf.bot_id())


@pytest.mark.parametrize(
    "url",
    [
        "http://api.notion.com/v1/users/me",
        "https://api.notion.com:8443/v1/users/me",
        "https://evil.example/v1/users/me",
        "https://user:pass@api.notion.com/v1/users/me",
    ],
)
async def test_another_origin_is_refused_before_it_leaves(fake, url):
    async with client(fake) as http:
        with pytest.raises(RequestRefused):
            await http.get(url)
    assert fake.requests == []


@pytest.mark.parametrize(
    "path",
    [
        "/v1/pages/" + "A" * 32,
        "/v1/pages/0b7d2a51-c4e9-4f36-a8e1-d2c3b4a59687",
        "/v1/pages/%2e%2e/users",
        "/v1/blocks/" + "0" * 31 + "/children",
        "/v1/users",
        "/v1/pages/" + "0" * 32 + "/properties/title",
    ],
)
async def test_a_malformed_identifier_or_path_is_refused_before_it_leaves(fake, path):
    async with client(fake) as http:
        with pytest.raises(RequestRefused):
            await http.get("https://api.notion.com" + path)
    assert fake.requests == []


async def test_an_unexpected_query_parameter_is_refused(fake):
    async with client(fake) as http:
        with pytest.raises(RequestRefused):
            await http.get("https://api.notion.com/v1/users/me", params={"filter": "x"})
    assert fake.requests == []


async def test_a_permitted_request_passes_with_an_identity_body(fake):
    async with client(fake) as http:
        response = await http.get("https://api.notion.com/v1/users/me")
    assert response.status_code == 200 and response.json()["type"] == "bot"
    assert len(fake.requests) == 1 and fake.requests[0].path == "/v1/users/me"


@pytest.mark.parametrize("kind", [OVERSIZE_DECLARED, OVERSIZE_STREAMED])
async def test_an_answer_past_the_cap_is_aborted(fake, kind):
    fake.queue("users.me", Answer.of(kind))
    async with client(fake) as http:
        with pytest.raises(ResponseTooLarge):
            await http.get("https://api.notion.com/v1/users/me")


async def test_a_redirect_is_an_unexpected_answer(fake):
    fake.queue("users.me", Answer.of(REDIRECT))
    async with client(fake) as http:
        with pytest.raises(UnexpectedResponse):
            await http.get("https://api.notion.com/v1/users/me")


async def test_a_slow_request_times_out_with_nothing_chained(fake):
    fake.queue("users.me", Answer.slow(1.0))
    async with client(fake, timeout=0.05) as http:
        with pytest.raises(httpx.ReadTimeout) as raised:
            await http.get("https://api.notion.com/v1/users/me")
    assert raised.value.__cause__ is None and raised.value.__context__ is None


def test_the_guard_refuses_a_bad_configuration(fake):
    with pytest.raises(TypeError):
        GuardedTransport(object(), cap_bytes=CAP, request_timeout=1)
    with pytest.raises(ValueError):
        GuardedTransport(fake, cap_bytes=0, request_timeout=1)
    with pytest.raises(ValueError):
        GuardedTransport(fake, cap_bytes=CAP, request_timeout=0)
