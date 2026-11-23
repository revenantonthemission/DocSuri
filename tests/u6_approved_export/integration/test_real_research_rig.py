"""U6:unit-test-instructions:never-mocked: the integration rigs run U4's real export read.

The mounted service, a lane rig beside it and the pass all hold the same `ResearchService`
the host builds; the ready result comes through U4 (cached run-bound), U4's ownership
answers for another owner, housekeeping reaches the real read, and the cache is reused,
rebuilt when stale, and refused for a foreign run (L1-2).
"""

import json
from uuid import UUID, uuid4

import pytest

from backend.modules.research.service import ResearchService
from backend.transactions import Authority
from tests.u6_approved_export import http_flows as hf
from tests.u6_approved_export import lane_flows as lf
from tests.u6_approved_export import store_flows as flows


class Inherited:
    def run_once(self, limit=1):
        return {}


@pytest.fixture
def mount(realm, transactions, connect, authority, authority_b, tmp_path):
    mounted = hf.mount(realm, transactions, connect, authority, authority_b, tmp_path)
    yield mounted
    mounted.close()


def reference_of(novelty: dict) -> dict:
    return {key: novelty[key] for key in ("artifactId", "revision", "contentHash")}


def test_the_rigs_share_one_real_research_service(
    mount, transactions, connect, authority, tmp_path
):
    m = mount
    lr = lf.build(
        transactions, connect, authority, tmp_path, keys="lane-keys", research=m.rig.research
    )

    service = m.rig.service.research

    assert isinstance(service, ResearchService)
    assert m.rig.research is service
    assert lr.rig.research is service
    assert lr.step._research is service
    reference = m.rig.ready(authority=m.authority)
    answer = service.readNoveltyArtifactForExport(m.authority, reference_of(reference))
    assert answer["availability"] == "ready"
    assert answer["prepared"]["ownerId"] == str(m.authority.account_id)
    assert m.rig.ready(authority=m.authority) == reference


def test_a_press_on_the_real_result_is_written_from_u4s_output(
    mount, transactions, connect, authority, tmp_path
):
    m = mount
    lr = lf.build(
        transactions, connect, authority, tmp_path, keys="lane-keys", research=m.rig.research
    )
    m.connect_owner()
    page = m.rig.page()
    reference = reference_of(lr.rig.ready(authority=m.authority))
    prepared = m.rig.service.research.readNoveltyArtifactForExport(
        m.authority, reference
    )["prepared"]["output"]

    flow = hf.press(m, page, source=reference)
    assert m.rig.fake.writes == []
    # The lane over the mounted rig: its write reaches the fake the routes share.
    assert lf.lane_over(m.rig).run_item(lf.item(flow["effect"])) != "skipped"

    with connect("export") as conn:
        stored = conn.execute(
            "SELECT source_revision,source_content_hash,rendered_text "
            "FROM export.preview_revision WHERE preview_id=%s AND revision=%s",
            (UUID(flow["preview"]["previewId"]), int(flow["preview"]["revision"])),
        ).fetchone()
    assert stored["source_revision"] == reference["revision"]
    assert stored["source_content_hash"] == reference["contentHash"]
    summary = prepared.get("summary")
    assert isinstance(summary, str) and summary[:10] in stored["rendered_text"]
    assert len(m.rig.fake.writes) == 1


def test_another_owners_post_of_the_reference_is_not_found(
    mount, transactions, connect, authority, tmp_path
):
    m = mount
    lr = lf.build(
        transactions, connect, authority, tmp_path, keys="lane-keys", research=m.rig.research
    )
    source = reference_of(lr.rig.ready(authority=m.authority))
    own_page, other_page = m.rig.page(), m.rig.page()
    m.connect_owner()
    other_token, _ = m.rig.new_token()
    other_connection = m.connect_owner(client=m.other, token=other_token)

    reads_before = len([entry for entry in m.rig.fake.requests if "/pages/" in entry.path])
    refused = m.post(
        "prepare_preview",
        {
            "source": source,
            "destination": m.rig.destination(other_page, other_connection),
            "renderPolicy": m.rig.policy.reference(),
        },
        client=m.other,
    )
    reads_after = len([entry for entry in m.rig.fake.requests if "/pages/" in entry.path])
    own = m.ok("prepare_preview", m.rig.preview_value(own_page, source))

    assert refused.status_code == 404 and refused.json()["code"] == "NOT_FOUND"
    assert reads_after == reads_before
    assert own["destination"]["destinationId"] == own_page


def test_a_housekeeping_pass_reaches_the_real_service(
    mount, transactions, connect, authority, tmp_path, monkeypatch
):
    m = mount
    lr = lf.build(
        transactions,
        connect,
        authority,
        tmp_path,
        keys="lane-keys",
        lane=lf.LaneDouble(idle=False),
        research=m.rig.research,
    )
    m.connect_owner()
    recorded = []
    service = m.rig.service.research
    original = service.readNoveltyArtifactForExport

    def recording(receiving, reference):
        recorded.append((receiving, dict(reference)))
        return original(receiving, reference)

    monkeypatch.setattr(service, "readNoveltyArtifactForExport", recording)
    preview = m.ok(
        "prepare_preview",
        m.rig.preview_value(m.rig.page(), reference_of(lr.rig.ready(authority=m.authority))),
    )
    approval = m.ok("approve", m.rig.approval_value(preview))

    lr.step.run_once()

    ours = [item for item in recorded if item[0] == m.authority]
    assert ours and isinstance(ours[-1][0], Authority)
    assert ours[-1][1]["artifactId"] and ours[-1][1]["revision"]
    row = flows.approval_row(connect, UUID(approval["approvalId"]))
    assert row["state"] == "approved" and row["invalidation_reason"] is None
    kept = flows.revision_row(connect, UUID(preview["previewId"]), int(preview["revision"]))
    assert kept["rendered_blocks"] is not None


def test_the_run_bound_cache_is_reused_rebuilt_and_refused(
    mount, transactions, connect, authority, tmp_path
):
    m = mount
    lr = lf.build(
        transactions, connect, authority, tmp_path, keys="lane-keys", research=m.rig.research
    )
    path = m.rig.transactions.profile.root / "integration-novelty.json"
    original = path.read_text() if path.exists() else None
    try:
        first = lr.rig.ready(authority=m.authority)
        again = m.rig.ready(authority=m.authority)
        assert again == first

        cached = json.loads(path.read_text())
        stale = {"artifactId": uuid4().hex, "revision": "1", "contentHash": "0" * 64}
        cached["accounts"][str(m.authority.account_id)] = stale
        path.write_text(json.dumps(cached))
        rebuilt = lr.rig.ready(authority=m.authority)
        assert rebuilt != stale and rebuilt["artifactId"] != stale["artifactId"]

        cached = json.loads(path.read_text())
        cached["runId"] = "docsuri-u6-another-run"
        path.write_text(json.dumps(cached))
        with pytest.raises(AssertionError):
            m.rig.ready(authority=m.authority)
    finally:
        if original is None:
            path.unlink(missing_ok=True)
        else:
            path.write_text(original)
