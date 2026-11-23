"""U6:NFR3.8/provider-text: provider-supplied text stays data, never a path or a field.

Titles, contexts, message bodies and links arrive from an untrusted provider: they are
bounded and mirrored into `title`/`context` only, address nothing, and never reach a
field, a boundary link check or a stored row as text.
"""

import asyncio
import json
from dataclasses import fields
from uuid import UUID

import httpx
from docsuri_shared.workspace import wire
from notion_client.errors import build_request_error

from backend.modules.export import notion_adapter as adapter_module
from backend.modules.export.classification import (
    COULD_NOT_CHECK,
    CREATED,
    REFUSED,
    Verdict,
    classify_read,
)
from backend.modules.export.fake_notion import Answer
from backend.modules.export.notion_session import StoredConnection
from tests.u6_approved_export import notion_flows as nf
from tests.u6_approved_export import service_flows as sf


def hostile_title(token: str) -> str:
    return "<img src=x onerror=alert(1)>{0}" + token + " " + "가" * 5000


def write_setup(transactions, connect, authority, tmp_path) -> dict:
    policy = nf.policy()
    repo = nf.repository(transactions, policy)
    opener = nf.vault(tmp_path)
    token, bot = nf.synthetic_token(), nf.bot_id()
    fake = nf.fake_with(token, bot)
    target, connection = nf.stored_connection(repo, connect, authority, opener, token, user=bot)
    destination = fake.add_page(title="대상")
    adapter = nf.adapter(repo, opener, fake, policy)
    return {
        "policy": policy,
        "repo": repo,
        "vault": opener,
        "token": token,
        "bot": bot,
        "fake": fake,
        "target": target,
        "connection": connection,
        "destination": destination,
        "adapter": adapter,
    }


def test_a_hostile_title_lists_as_text_and_validates_on_the_wire(
    transactions, connect, authority, tmp_path
):
    rig = sf.build(transactions, connect, authority, tmp_path)
    rig.configure()
    secret_parent = rig.page("{secret}")
    hostile = hostile_title(rig.token)
    child = rig.page(hostile, parent_id=secret_parent)

    view = rig.service.list_destinations(authority, {})

    entry = next(item for item in view["destinations"] if item["destinationId"] == child)
    assert entry["title"] == hostile.strip()[:2000]
    assert entry["context"] == "상위 페이지: {secret}"
    wire.ExportDestinationEntry.model_validate(entry)
    target = StoredConnection(authority.account_id, UUID(view["connectionId"]))
    read = asyncio.run(rig.service.adapter.read_destination(target, child))
    assert read.context == f"상위 페이지 · {secret_parent[:8]}"
    assert (
        adapter_module.page_title({"properties": {"title": {"type": "title", "title": 7}}})
        is None
    )
    assert rig.fake.writes == []


def test_titles_shaped_like_identifiers_urls_or_paths_stay_in_the_title(
    transactions, connect, authority, tmp_path
):
    rig = sf.build(transactions, connect, authority, tmp_path)
    rig.configure()
    shaped = [
        "0123456789abcdef0123456789abcdef",
        "https://www.notion.so/0123456789abcdef0123456789abcdef",
        "../v1/users",
    ]
    pages = [rig.page(title=value) for value in shaped]

    view = rig.service.list_destinations(authority, {})

    entries = {item["destinationId"]: item for item in view["destinations"]}
    for value, page in zip(shaped, pages, strict=True):
        assert entries[page]["title"] == value
    for request in rig.fake.requests:
        assert all(value not in request.path for value in shaped)


async def test_page_links_are_accepted_only_on_the_notion_hosts(
    transactions, connect, authority, tmp_path
):
    for value in (
        "javascript:alert(1)",
        "http://www.notion.so/x",
        "https://notion.so.evil.example/x",
        "https://x.notion.site/abc",
        "https://www.notion.so/",
        "7",
    ):
        assert adapter_module._page_url(value) is None, value
    for value in (
        f"https://www.notion.so/{'a' * 32}",
        f"https://notion.so/{'a' * 32}",
        f"https://www.notion.site/{'a' * 32}",
        f"https://notion.site/{'a' * 32}",
    ):
        assert adapter_module._page_url(value) == value

    setup = write_setup(transactions, connect, authority, tmp_path)
    bound = nf.bound_effect(
        setup["repo"], authority, setup["connection"], setup["destination"]
    )

    result = await setup["adapter"].create_page(
        setup["target"],
        nf.write_request(bound, setup["connection"], setup["bot"]),
        deadline_seconds=5,
    )

    assert result.category == CREATED
    assert adapter_module._NOTION_URL.fullmatch(result.outcome.remote_url)


async def test_provider_message_text_never_becomes_a_field_or_a_row(
    transactions, connect, authority, tmp_path
):
    response = httpx.Response(
        500,
        text=json.dumps(
            {
                "object": "error",
                "status": 500,
                "code": "internal_server_error",
                "message": "<script>sentinel</script>",
            }
        ),
    )
    verdict = classify_read(build_request_error(response, response.text))
    assert verdict.category == COULD_NOT_CHECK
    assert {item.name for item in fields(Verdict)} == {
        "category",
        "refusal",
        "retry_after",
        "request_id",
        "committed_page_id",
        "cause",
    }
    assert "sentinel" not in repr(verdict)

    setup = write_setup(transactions, connect, authority, tmp_path)
    bound = nf.bound_effect(
        setup["repo"], authority, setup["connection"], setup["destination"]
    )
    setup["fake"].queue("pages.create", Answer.error(403))

    result = await setup["adapter"].create_page(
        setup["target"],
        nf.write_request(bound, setup["connection"], setup["bot"]),
        deadline_seconds=5,
    )

    assert result.category == REFUSED and result.outcome.reason == "no-access"
    for value in (result, result.provider_result(), result.provider_outcome()):
        assert all(
            not isinstance(seen, str) or "synthetic answer" not in seen
            for seen in nf.walk(value)
        )
    assert "synthetic answer" not in repr(result)
    with connect("export") as conn:
        rows = conn.execute(
            "SELECT to_jsonb(e)::text AS t FROM export.effect e WHERE e.account_id=%s "
            "UNION ALL SELECT to_jsonb(a)::text FROM export.attempt a JOIN export.effect e2 "
            "ON e2.id=a.effect_id WHERE e2.account_id=%s",
            (authority.account_id, authority.account_id),
        ).fetchall()
    assert all("synthetic answer" not in row["t"] for row in rows)
