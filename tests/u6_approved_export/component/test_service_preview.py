"""Export service, preview: U4's answers, the destination read, the frozen binding,
earlier-export notices, size refusals and zero provider writes (BR2.1–BR2.5)."""

from uuid import UUID, uuid4

import psycopg
import pytest
from docsuri_shared.workspace import wire

from backend.modules.export.fake_notion import Answer
from backend.modules.export.rendering import binding_hash, content_hash
from backend.modules.research.errors import ResearchError
from backend.u6_policy import real_activation_export
from tests.u6_approved_export import notion_flows as nf
from tests.u6_approved_export import service_flows as sf


def test_a_ready_result_previews_with_its_frozen_binding_and_writes_nothing(
    transactions, connect, authority, tmp_path
):
    rig = sf.build(transactions, connect, authority, tmp_path)
    rig.configure()
    page = rig.page("내보낼 곳")
    source = rig.research.ready()
    value = rig.preview_value(page, source)
    value["destination"]["title"] = "브라우저가 보낸 제목"

    preview = rig.service.prepare_preview(authority, value)

    wire.ExportPreview.model_validate(preview)
    assert preview["revision"] == "1" and preview["source"] == source
    assert preview["destination"]["title"] == "내보낼 곳"
    assert preview["destination"]["destinationId"] == page
    assert preview["sourceTitle"].startswith("신규성 분석 — ")
    assert preview["renderedText"].splitlines()[-1] == preview["marker"]
    assert preview["earlierExports"] == []
    expected = binding_hash(
        {
            "ownerId": str(authority.account_id),
            "previewId": preview["previewId"],
            "revision": "1",
            "source": source,
            "sourceEligibilityRevision": "1",
            "connectionRevision": "1",
            "destination": preview["destination"],
            "renderedContentHash": preview["renderedContentHash"],
            "renderPolicy": rig.policy.reference(),
        }
    )
    assert preview["bindingHash"] == expected
    # The frozen tree is exactly the hashed one (D12).
    with connect("export") as conn:
        tree = conn.execute(
            "SELECT rendered_blocks FROM export.preview_revision WHERE preview_id=%s",
            (UUID(preview["previewId"]),),
        ).fetchone()["rendered_blocks"]
    assert content_hash(tree) == preview["renderedContentHash"]
    again = rig.preview(page, source)
    assert (again["previewId"], again["revision"]) == (preview["previewId"], "2")
    assert rig.fake.writes == []


@pytest.mark.parametrize(
    ("answer", "code"),
    [
        ("absent", "NOT_FOUND"),
        ("changed", "CONFLICT"),
        (ResearchError("SOURCE_INELIGIBLE"), "SOURCE_INELIGIBLE"),
        (ResearchError("DEPENDENCY_UNAVAILABLE"), "DEPENDENCY_UNAVAILABLE"),
        (psycopg.OperationalError("unreachable"), "DEPENDENCY_UNAVAILABLE"),
        (ResearchError("POLICY_UNRESOLVED"), "POLICY_UNRESOLVED"),
    ],
)
def test_u4_answers_map_as_br2_1(transactions, connect, authority, tmp_path, answer, code):
    rig = sf.build(transactions, connect, authority, tmp_path)
    rig.configure()
    page = rig.page()
    source = rig.research.ready()
    if answer == "absent":
        source = {**source, "artifactId": str(uuid4())}
    elif answer == "changed":
        source = {**source, "contentHash": "f" * 64}
    else:
        rig.research.failure = answer

    assert sf.refuse("prepare_preview", lambda: rig.preview(page, source)) == code
    assert [entry.path for entry in rig.fake.requests if "/pages/" in entry.path] == []


def test_a_page_outside_a_complete_listing_is_conflict_with_no_page_request(
    transactions, connect, authority, tmp_path
):
    rig = sf.build(transactions, connect, authority, tmp_path)
    rig.configure()
    rig.page("목록에 있음")
    outside = uuid4().hex

    assert sf.refuse("prepare_preview", lambda: rig.preview(outside)) == "CONFLICT"

    searches = [entry for entry in rig.fake.requests if entry.path == "/v1/search"]
    assert len(searches) == 1
    hyphenated = str(UUID(hex=outside))
    assert all(
        outside not in entry.path and hyphenated not in entry.path
        for entry in rig.fake.requests
    )
    with connect("export") as conn:
        pairs = conn.execute(
            "SELECT count(*) AS n FROM export.preview_pair WHERE account_id=%s",
            (authority.account_id,),
        ).fetchone()["n"]
    assert pairs == 0
    assert rig.fake.writes == []


def test_a_page_missing_from_a_partial_or_unavailable_listing_is_could_not_check(
    transactions, connect, authority, tmp_path
):
    rig = sf.build(transactions, connect, authority, tmp_path)
    rig.configure()
    rig.page("먼저 온 페이지")
    page = rig.page("목록 밖으로 밀림")
    rig.fake.set_search("partial", page_size=1)

    assert sf.refuse("prepare_preview", lambda: rig.preview(page)) == "DEPENDENCY_UNAVAILABLE"

    rig.fake.set_search("unavailable")
    assert sf.refuse("prepare_preview", lambda: rig.preview(page)) == "DEPENDENCY_UNAVAILABLE"
    assert rig.fake.writes == []


def test_the_request_identity_prefers_destination_id_and_needs_agreement(
    transactions, connect, authority, tmp_path
):
    rig = sf.build(transactions, connect, authority, tmp_path)
    rig.configure()
    first = rig.page("A")
    second = rig.page("B")
    source = rig.research.ready()

    disagreeing = rig.preview_value(first, source)
    disagreeing["destination"]["parentPageId"] = second
    asked = len(rig.fake.requests)
    assert (
        sf.refuse("prepare_preview", lambda: rig.service.prepare_preview(authority, disagreeing))
        == "CONFLICT"
    )
    assert len(rig.fake.requests) == asked

    agreeing = rig.preview_value(first, source)
    assert agreeing["destination"]["destinationId"] == agreeing["destination"]["parentPageId"]
    preview = rig.service.prepare_preview(authority, agreeing)
    assert preview["destination"]["destinationId"] == first

    only_parent = rig.preview_value(first, source)
    only_parent["destination"].pop("destinationId")
    again = rig.service.prepare_preview(authority, only_parent)
    assert (again["previewId"], again["revision"]) == (preview["previewId"], "2")


def test_the_recorded_destination_comes_from_the_listing_entry(
    transactions, connect, authority, tmp_path
):
    rig = sf.build(transactions, connect, authority, tmp_path)
    rig.configure()
    parent = rig.page("연구 노트")
    child = rig.page("내보낼 곳", parent_id=parent)
    source = rig.research.ready()
    value = rig.preview_value(str(UUID(hex=child)), source)
    value["destination"]["parentPageId"] = str(UUID(hex=child))
    value["destination"]["title"] = "브라우저가 보낸 제목"

    preview = rig.service.prepare_preview(authority, value)

    destination = preview["destination"]
    assert destination["destinationId"] == child
    assert destination["title"] == "내보낼 곳"
    assert destination["context"] == "상위 페이지: 연구 노트"
    paths = [
        entry.path
        for entry in rig.fake.requests
        if "/v1/pages/" in entry.path or "/v1/blocks/" in entry.path
    ]
    assert paths and all(child in path for path in paths)
    expected = binding_hash(
        {
            "ownerId": str(authority.account_id),
            "previewId": preview["previewId"],
            "revision": preview["revision"],
            "source": source,
            "sourceEligibilityRevision": "1",
            "connectionRevision": "1",
            "destination": destination,
            "renderedContentHash": preview["renderedContentHash"],
            "renderPolicy": rig.policy.reference(),
        }
    )
    assert preview["bindingHash"] == expected
    assert rig.fake.writes == []


def test_destination_refusals_and_the_real_allowance(transactions, connect, authority, tmp_path):
    rig = sf.build(transactions, connect, authority, tmp_path)
    rig.configure()
    hidden = rig.page("숨김", readable=False)
    busy = rig.page("바쁨")
    rig.fake.queue("pages.retrieve", Answer.error(503), target=busy)
    connection_id = UUID(rig.connection()["connectionId"])

    asked = len(rig.gate.asked)
    assert sf.refuse("prepare_preview", lambda: rig.preview(hidden)) == "CONFLICT"
    assert rig.gate.asked[asked:] == [connection_id]
    asked = len(rig.gate.asked)
    assert sf.refuse("prepare_preview", lambda: rig.preview(busy)) == "DEPENDENCY_UNAVAILABLE"
    assert rig.gate.asked[asked:] == [connection_id]

    good = rig.page("성공")
    asked = len(rig.gate.asked)
    rig.preview(good)
    assert rig.gate.asked[asked:] == [connection_id]
    assert any(entry.path.endswith(f"/blocks/{good}/children") for entry in rig.fake.requests)

    stale = rig.preview_value(busy)
    stale["destination"]["connectionId"] = str(uuid4())
    assert (
        sf.refuse("prepare_preview", lambda: rig.service.prepare_preview(authority, stale))
        == "CONFLICT"
    )
    other = {**rig.preview_value(busy), "renderPolicy": {"policyId": "x", "revision": "1"}}
    assert (
        sf.refuse("prepare_preview", lambda: rig.service.prepare_preview(authority, other))
        == "POLICY_UNRESOLVED"
    )

    activation = uuid4().hex
    real = sf.build(
        transactions,
        connect,
        authority,
        tmp_path,
        keys="real-keys",
        policy=real_activation_export(
            activation_destination_id=activation, free_terms_reference="free-terms-2026-10"
        ),
    )
    real.configure()
    elsewhere = real.page("허용되지 않음")
    asked = len(real.fake.requests)
    assert sf.refuse("prepare_preview", lambda: real.preview(elsewhere)) == "FORBIDDEN"
    assert len(real.fake.requests) == asked
    assert rig.fake.writes == [] and real.fake.writes == []


def test_earlier_exports_list_successes_and_ones_that_may_exist(
    transactions, connect, authority, tmp_path
):
    rig = sf.build(
        transactions,
        connect,
        authority,
        tmp_path,
        policy=nf.policy(write_deadline_seconds=1, settling_wait_seconds=1),
    )
    rig.configure()
    page = rig.page()
    source = rig.research.ready()
    succeeded = rig.succeed(rig.press(page, source)["effect"])
    rig.clock.advance(5)
    settled = rig.uncertain(rig.press(page, source)["effect"])
    rig.clock.advance(5)
    rig.check(settled, "listing-unavailable")
    rig.service.settle(
        authority,
        {
            "effectId": str(settled["id"]),
            "expectedRevision": str(settled["revision"] + 1),
            "disposition": "not-delivered",
            "assumptionAccepted": True,
        },
        operation=uuid4(),
    )
    rig.clock.advance(5)
    unseen = rig.uncertain(rig.press(page, source)["effect"])
    rig.clock.advance(5)
    unseen = rig.check(unseen, "not-found")
    rig.clock.advance(5)
    assert rig.check(unseen, "not-found")["state"] == "failed"
    rig.clock.advance(5)

    notices = rig.preview(page, source)["earlierExports"]

    assert [(item["disposition"], item.get("outcomeReason")) for item in notices] == [
        ("may-exist", "not-found-after-checks"),
        ("may-exist", "owner-settled-not-delivered"),
        ("exported", None),
    ]
    assert notices[-1]["remoteUrl"] == succeeded["remote_url"]
    assert notices[-1]["effectId"] == str(succeeded["id"])
    assert rig.fake.writes == []


def test_an_oversized_result_is_refused_and_nothing_is_frozen(
    transactions, connect, authority, tmp_path
):
    rig = sf.build(transactions, connect, authority, tmp_path)
    rig.configure()
    page = rig.page()
    source = rig.research.ready(output=sf.novelty_output(evidence_items=120))

    assert sf.refuse("prepare_preview", lambda: rig.preview(page, source)) == "SOURCE_INELIGIBLE"
    with connect("export") as conn:
        pairs = conn.execute(
            "SELECT count(*) AS n FROM export.preview_pair WHERE account_id=%s",
            (authority.account_id,),
        ).fetchone()["n"]
    assert pairs == 0
    malformed = rig.research.ready(output={"summary": 3})
    assert sf.refuse("prepare_preview", lambda: rig.preview(page, malformed)) == (
        "SOURCE_INELIGIBLE"
    )
    assert rig.fake.writes == []
