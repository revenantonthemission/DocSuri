"""The fake Notion answers as the 2026-03-11 reference documents, with stateful pages."""

import json
from pathlib import Path

import httpx
import pytest
from backend.modules.export.fake_notion import (
    LOST_AFTER_SUCCESS,
    SAVED_BUSY,
    Answer,
    FakeNotion,
)
from backend.modules.export.rendering import content_hash
from notion_client.errors import APIErrorCode, APIResponseError, build_request_error

from tests.u6_approved_export import notion_flows as nf

VECTORS = Path(__file__).resolve().parents[3] / "shared" / "export-hash-vectors.json"
TOKEN = nf.synthetic_token()
API = "https://api.notion.com/v1"


@pytest.fixture
def bot():
    return nf.bot_id()


@pytest.fixture
def fake(bot):
    return nf.fake_with(TOKEN, bot)


def client(fake, token=TOKEN) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=fake, headers={"Authorization": f"Bearer {token}"})


def sdk_error(response: httpx.Response):
    return build_request_error(response, response.text)


async def test_the_bot_user_carries_the_documented_workspace_fields(fake, bot):
    async with client(fake) as http:
        me = (await http.get(f"{API}/users/me")).json()
    assert me["object"] == "user" and me["type"] == "bot"
    assert me["id"].replace("-", "") == bot
    assert me["bot"]["workspace_id"] == nf.WORKSPACE_ID
    assert me["bot"]["workspace_name"] == nf.WORKSPACE_NAME
    assert me["bot"]["owner"] == {"type": "workspace", "workspace": True}
    assert set(me["bot"]) == {"owner", "workspace_id", "workspace_name", "workspace_limits"}


async def test_an_unknown_token_answers_401_unauthorized(fake):
    async with client(fake, token="synthetic-unknown") as http:
        response = await http.get(f"{API}/users/me")
    error = sdk_error(response)
    assert isinstance(error, APIResponseError) and error.code == APIErrorCode.Unauthorized


async def test_documented_error_bodies(fake):
    destination = fake.add_page(title="대상")
    fake.queue("pages.create", Answer.rate_limited(wait=4))
    fake.queue("pages.create", Answer.rate_limited(wait=4, blocked=True))
    fake.queue("pages.create", Answer.block_limit())
    fake.queue("pages.create", Answer.overloaded(wait=2))
    body = {"parent": {"page_id": destination}, **nf.page_body("marker")}
    async with client(fake) as http:
        answers = [(await http.post(f"{API}/pages", json=body)) for _ in range(4)]
    limited, blocked, limit, overloaded = answers
    assert limited.status_code == 429 and limited.headers["retry-after"] == "4"
    assert limited.json()["additional_data"]["retry_after"] == "4"
    assert blocked.json()["additional_data"]["rate_limit_reason"] == "public_api_request_blocked"
    assert limit.status_code == 403 and limit.json()["code"] == "restricted_resource"
    assert limit.json()["additional_data"] == {"block_limit": "block_creation"}
    assert overloaded.status_code == 529 and overloaded.json()["code"] == "service_overload"
    assert all("request_id" in answer.json() for answer in answers)
    assert fake.pages_under(destination) == []


async def test_saved_but_busy_names_the_saved_page_and_a_lost_answer_still_creates(fake):
    destination = fake.add_page(title="대상")
    fake.queue("pages.create", Answer.of(SAVED_BUSY))
    fake.queue("pages.create", Answer.of(LOST_AFTER_SUCCESS))
    body = {"parent": {"page_id": destination}, **nf.page_body("marker")}
    async with client(fake) as http:
        busy = await http.post(f"{API}/pages", json=body)
        with pytest.raises(httpx.RemoteProtocolError):
            await http.post(f"{API}/pages", json=body)
    saved = busy.json()["additional_data"]["committed_resource_id"].replace("-", "")
    assert busy.status_code == 503 and busy.json()["code"] == "service_unavailable"
    pages = fake.pages_under(destination)
    assert len(pages) == 2 and pages[0] == saved


async def test_search_pages_are_complete_partial_or_unavailable(fake):
    for index in range(3):
        fake.add_page(title=f"페이지 {index}")
    fake.set_search("complete", page_size=2)
    async with client(fake) as http:
        first = (await http.post(f"{API}/search", json={"page_size": 100})).json()
        second = (
            await http.post(
                f"{API}/search", json={"page_size": 100, "start_cursor": first["next_cursor"]}
            )
        ).json()
        fake.set_search("partial", page_size=2)
        partial = await http.post(
            f"{API}/search", json={"page_size": 100, "start_cursor": first["next_cursor"]}
        )
        fake.set_search("unavailable")
        unavailable = await http.post(f"{API}/search", json={"page_size": 100})
    assert first["has_more"] and len(first["results"]) == 2
    assert not second["has_more"] and len(second["results"]) == 1
    assert partial.status_code == 500 and unavailable.status_code == 503


async def test_a_counting_page_answers_its_first_n_page_requests_then_503(fake):
    page = fake.add_page(title="취소 대상")
    fake.limit_page_reads(page, 2)
    async with client(fake) as http:
        statuses = []
        for _ in range(3):
            statuses.append((await http.get(f"{API}/pages/{page}")).status_code)
            statuses.append((await http.get(f"{API}/blocks/{page}/children")).status_code)
    assert statuses == [200, 200, 200, 200, 503, 503]


async def test_children_answer_503_only_after_a_create_under_the_page(fake):
    page = fake.add_page(title="정리 대상")
    fake.busy_children_after_create(page)
    fake.queue("pages.create", Answer.error(504), target=page)
    body = {"parent": {"page_id": page}, **nf.page_body("marker")}
    async with client(fake) as http:
        before = (await http.get(f"{API}/blocks/{page}/children")).status_code
        created = (await http.post(f"{API}/pages", json=body)).status_code
        after = (await http.get(f"{API}/blocks/{page}/children")).status_code
        page_read = (await http.get(f"{API}/pages/{page}")).status_code
    assert (before, created, after, page_read) == (200, 504, 503, 200)


async def test_the_fake_hashes_with_the_backend_function_against_the_golden_vectors(fake):
    destination = fake.add_page(title="대상")
    cases = json.loads(VECTORS.read_text(encoding="utf-8"))["renderedContentHash"]["cases"]
    async with client(fake) as http:
        for case in cases:
            assert content_hash(case["input"]) == case["sha256"]
            body = {"parent": {"page_id": destination}, **case["input"]}
            await http.post(f"{API}/pages", json=body)
    assert [entry.content_hash for entry in fake.writes] == [case["sha256"] for case in cases]


async def test_an_expected_hash_mismatch_is_notions_validation_refusal(fake):
    destination = fake.add_page(title="대상")
    fake.expect_content_hash("0" * 64, parent_id=destination)
    body = {"parent": {"page_id": destination}, **nf.page_body("marker")}
    async with client(fake) as http:
        response = await http.post(f"{API}/pages", json=body)
    assert response.status_code == 400 and response.json()["code"] == "validation_error"
    assert fake.pages_under(destination) == []


async def test_the_request_log_holds_method_path_authorization_and_body_hash(fake):
    async with client(fake) as http:
        await http.get(f"{API}/users/me")
        await http.post(f"{API}/search", json={"page_size": 100})
    first, second = fake.requests
    assert (first.method, first.path, first.authorization) == ("GET", "/v1/users/me", f"Bearer {TOKEN}")
    assert first.body_hash is None and len(second.body_hash) == 64


def test_a_scenario_file_is_bound_to_its_run(tmp_path, bot):
    page = nf.bot_id()
    scenario = {
        "runId": "run-a",
        "tokens": {TOKEN: {"botId": bot, "workspaceId": nf.WORKSPACE_ID}},
        "pages": [{"id": page, "title": "공유됨", "normalPageReads": 2}],
    }
    with pytest.raises(ValueError):
        FakeNotion.from_scenario(scenario, run_id="run-b")
    path = tmp_path / "fake-notion.json"
    path.write_text(json.dumps(scenario), encoding="utf-8")
    path.chmod(0o600)
    loaded = FakeNotion.load(path, run_id="run-a")
    assert loaded.page(page).title == "공유됨"
