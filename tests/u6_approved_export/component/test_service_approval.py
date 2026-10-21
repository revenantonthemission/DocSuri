"""Export service, approve: replays, explicit approval, current revision, re-derived
binding, newer succeeded exports, and refusals that record nothing (BR3.1, BR3.2)."""

from uuid import UUID, uuid4

from backend.modules.research.errors import ResearchError
from docsuri_shared.workspace import wire

from tests.u6_approved_export import service_flows as sf


def approval_count(connect, account) -> int:
    with connect("export") as conn:
        return conn.execute(
            "SELECT count(*) AS n FROM export.approval WHERE account_id=%s", (account,)
        ).fetchone()["n"]


def test_an_approval_records_the_current_revision_with_no_expiry(
    transactions, connect, authority, tmp_path
):
    rig = sf.build(transactions, connect, authority, tmp_path)
    rig.configure()
    preview = rig.preview(rig.page())

    approval = rig.approve(preview)

    wire.ExportApproval.model_validate(approval)
    assert (approval["state"], approval["expiresAt"]) == ("approved", None)
    assert approval["policy"] == {"policyId": "u6-approval-validity", "revision": "1"}
    assert (approval["previewId"], approval["previewRevision"]) == (preview["previewId"], "1")
    assert "invalidationReason" not in approval
    # The binding check read the destination through the gate, keyed by the connection.
    assert rig.gate.asked[-1] == UUID(rig.connection()["connectionId"])


def test_a_replay_returns_the_original_before_any_check(transactions, connect, authority, tmp_path):
    rig = sf.build(transactions, connect, authority, tmp_path)
    rig.configure()
    page = rig.page()
    preview = rig.preview(page)
    key = uuid4()
    approval = rig.approve(preview, key=key)
    rig.fake.page(page).readable = False
    rig.research.failure = ResearchError("SOURCE_INELIGIBLE")
    asked = len(rig.fake.requests)

    assert rig.approve(preview, key=key) == approval
    # Another tab on the same revision gets the same approval (BR3.2).
    assert rig.approve(preview) == approval
    assert len(rig.fake.requests) == asked


def test_a_changed_payload_under_the_same_key_is_idempotency_conflict(
    transactions, connect, authority, tmp_path
):
    rig = sf.build(transactions, connect, authority, tmp_path)
    rig.configure()
    first, second = rig.preview(rig.page()), rig.preview(rig.page())
    key = uuid4()
    rig.approve(first, key=key)

    assert sf.refuse("approve", lambda: rig.approve(second, key=key)) == "IDEMPOTENCY_CONFLICT"
    assert approval_count(connect, authority.account_id) == 1


def test_a_missing_explicit_approval_is_invalid_and_records_nothing(
    transactions, connect, authority, tmp_path
):
    rig = sf.build(transactions, connect, authority, tmp_path)
    rig.configure()
    preview = rig.preview(rig.page())

    for value in (
        {k: v for k, v in rig.approval_value(preview).items() if k != "explicitApproval"},
        rig.approval_value(preview, explicitApproval=False),
        rig.approval_value(preview, previewRevision="0"),
        rig.approval_value(preview, bindingHash="not-a-hash"),
    ):
        code = sf.refuse(
            "approve", lambda v=value: rig.service.approve(authority, v, operation=uuid4())
        )
        assert code == "INVALID_ARGUMENT"
    assert approval_count(connect, authority.account_id) == 0


def test_a_stale_revision_or_a_newer_succeeded_export_is_conflict(
    transactions, connect, authority, tmp_path
):
    rig = sf.build(transactions, connect, authority, tmp_path)
    rig.configure()
    page = rig.page()
    source = rig.research.ready()
    stale = rig.preview(page, source)
    exported = rig.preview(page, source)
    assert sf.refuse("approve", lambda: rig.approve(stale)) == "CONFLICT"
    key = uuid4()
    effect = rig.execute(rig.approve(exported, key=key), key=key)
    rig.clock.advance(1)
    current = rig.preview(page, source)
    rig.clock.advance(1)
    rig.succeed(effect)

    # The pair's export succeeded after the current revision was prepared.
    assert sf.refuse("approve", lambda: rig.approve(current)) == "CONFLICT"
    assert approval_count(connect, authority.account_id) == 1


def test_a_changed_binding_refuses_with_the_calls_own_code_and_records_nothing(
    transactions, connect, authority, tmp_path
):
    rig = sf.build(transactions, connect, authority, tmp_path)
    rig.configure()
    page = rig.page()
    preview = rig.preview(page)

    rig.research.failure = ResearchError("SOURCE_INELIGIBLE")
    assert sf.refuse("approve", lambda: rig.approve(preview)) == "SOURCE_INELIGIBLE"
    rig.research.failure = ResearchError("DEPENDENCY_UNAVAILABLE")
    assert sf.refuse("approve", lambda: rig.approve(preview)) == "DEPENDENCY_UNAVAILABLE"
    rig.research.failure = None
    rig.fake.page(page).readable = False
    assert sf.refuse("approve", lambda: rig.approve(preview)) == "CONFLICT"
    assert approval_count(connect, authority.account_id) == 0
    assert rig.fake.writes == []
