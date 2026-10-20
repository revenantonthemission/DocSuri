"""Export service, preview: U4's answers, the destination read, the frozen binding,
earlier-export notices, size refusals and zero provider writes (BR2.1–BR2.5)."""

from uuid import UUID, uuid4

import psycopg
import pytest
from backend.modules.export.fake_notion import Answer
from backend.modules.export.rendering import binding_hash, content_hash
from backend.modules.research.errors import ResearchError
from backend.u6_policy import real_activation_export
from docsuri_shared.workspace import wire

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


def test_destination_refusals_and_the_real_allowance(transactions, connect, authority, tmp_path):
    rig = sf.build(transactions, connect, authority, tmp_path)
    rig.configure()
    hidden = rig.page("숨김", readable=False)
    busy = rig.page("바쁨")
    rig.fake.queue("pages.retrieve", Answer.error(503), target=busy)

    assert sf.refuse("prepare_preview", lambda: rig.preview(hidden)) == "CONFLICT"
    assert sf.refuse("prepare_preview", lambda: rig.preview(busy)) == "DEPENDENCY_UNAVAILABLE"
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
