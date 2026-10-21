"""Preview pairs and frozen revisions (BR2.3), earlier-export summaries (BR2.5) and the trim."""

from uuid import uuid4

import pytest
from backend.modules.export.errors import ExportError
from backend.modules.export.repository import CheckResult

from tests.u6_approved_export import export_rows as rows
from tests.u6_approved_export import store_flows as flows


def test_each_preparation_adds_the_next_revision_of_one_pair(
    transactions, connect, authority, authority_b
):
    repo, now = flows.repository(transactions), flows.at()
    connection = flows.connected(repo, connect, authority, now)
    pair = {"artifact": uuid4(), "destination": rows.destination_id()}
    prepared = [flows.prepare(repo, authority, connection, now, **pair) for _ in range(3)]
    assert [p["revision"] for p in prepared] == [1, 2, 3]
    assert len({p["preview_id"] for p in prepared}) == 1
    assert prepared[-1]["current_revision"] == 3 and prepared[0]["prepared_at"] == now
    assert prepared[1]["marker"] == f"docsuri-export:v1:{prepared[1]['preview_id'].hex}:2"
    other = flows.prepare(repo, authority, connection, now, artifact=pair["artifact"])
    assert other["preview_id"] != prepared[0]["preview_id"] and other["revision"] == 1

    preview_id = prepared[0]["preview_id"]
    assert repo.read_preview(authority, preview_id)["revision"] == 3
    first = repo.read_preview(authority, preview_id, 1)
    assert first["rendered_text"].endswith(first["marker"]) and first["trimmed_at"] is None
    flows.fresh(connect, authority_b.account_id)
    for call in (
        lambda: repo.read_preview(authority_b, preview_id),
        lambda: repo.read_preview(authority, uuid4()),
        lambda: repo.read_preview(authority, preview_id, 9),
    ):
        with pytest.raises(LookupError):
            call()


def test_a_preparation_needs_the_connection_it_was_read_under(transactions, connect, authority):
    repo, now = flows.repository(transactions), flows.at()
    connection = flows.connected(repo, connect, authority, now)
    flows.configure(repo, authority, now, expected=1)
    with pytest.raises(ExportError) as caught:
        flows.prepare(repo, authority, connection, now)  # read at revision 1, now 2
    assert caught.value.code == "CONFLICT"
    assert caught.value.current == {"connectionRevision": 2}


def _fail_after_two_clean_scans(repo, connect, effect, start):
    unknown = flows.uncertain(repo, effect, start)
    evidence = "e" * 64
    first = flows.at(300, base=start)
    checked = repo.record_check(
        effect["id"], unknown["revision"], CheckResult("not-found", start, evidence), now=first
    )
    second = flows.at(480, base=start)
    return repo.record_check(
        effect["id"], checked["revision"], CheckResult("not-found", start, evidence), now=second
    )


def test_earlier_exports_are_frozen_at_preparation_and_kept_through_a_trim(
    transactions, connect, authority
):
    """BR2.5: exported and may-exist summaries; BR2.6: a trim keeps them."""
    repo = flows.repository(transactions, housekeeping_batch=1000)
    start = flows.at()
    connection = flows.connected(repo, connect, authority, start)
    pair = {"artifact": uuid4(), "destination": rows.destination_id()}
    exported = flows.bound(repo, authority, connection, start, **pair)
    succeeded = flows.succeed(repo, exported["effect"], flows.at(1, base=start))

    second = flows.bound(repo, authority, connection, flows.at(2, base=start), **pair)
    assert second["preview"]["earlier_exports"] == [
        {
            "effectId": str(succeeded["id"]),
            "disposition": "exported",
            "endedAt": succeeded["ended_at"].isoformat(),
            "remoteUrl": succeeded["remote_url"],
        }
    ]
    failed = _fail_after_two_clean_scans(repo, connect, second["effect"], flows.at(3, base=start))
    assert (failed["state"], failed["outcome_reason"]) == ("failed", "not-found-after-checks")

    third = flows.prepare(repo, authority, connection, flows.at(600, base=start), **pair)
    assert [entry["disposition"] for entry in third["earlier_exports"]] == ["may-exist", "exported"]
    assert third["earlier_exports"][0]["outcomeReason"] == "not-found-after-checks"
    preview_id, revision = second["preview"]["preview_id"], second["preview"]["revision"]
    assert len(repo.read_preview(authority, preview_id, revision)["earlier_exports"]) == 1

    assert repo.trim_settled_revisions(flows.at(700, base=start)) >= 2
    trimmed = flows.revision_row(connect, preview_id, revision)
    assert trimmed["rendered_blocks"] is None and trimmed["rendered_text"] is None
    assert trimmed["trimmed_at"] == flows.at(700, base=start)
    assert trimmed["earlier_exports"] == second["preview"]["earlier_exports"]
    summary = repo.read_preview(authority, preview_id, revision)
    assert summary["marker"] == second["preview"]["marker"]
    assert summary["binding_hash"] == second["preview"]["binding_hash"]
    assert flows.revision_row(connect, preview_id, 3)["rendered_text"] is not None
