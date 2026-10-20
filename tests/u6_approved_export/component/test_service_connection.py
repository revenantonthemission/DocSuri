"""Export service, connection: connect, replace, disconnect, revocation, pending rows."""

import datetime as dt
from uuid import UUID, uuid4

from backend.modules.export.fake_notion import Answer
from docsuri_shared.workspace import wire

from tests.u6_approved_export import service_flows as sf
from tests.u6_approved_export import store_flows as flows


def connection_rows(connect, account) -> list:
    with connect("export") as conn:
        return conn.execute(
            "SELECT id,state,revision,pending_holder FROM export.connection WHERE account_id=%s",
            (account,),
        ).fetchall()


def test_first_connect_stores_the_token_and_reads_connected_with_its_workspace(
    transactions, connect, authority, tmp_path
):
    rig = sf.build(transactions, connect, authority, tmp_path)
    key = uuid4()

    view = rig.configure(key=key)

    wire.ExportConnection.model_validate(view)
    assert (view["state"], view["revision"]) == ("connected", "1")
    assert view["workspaceName"] == "Synthetic Workspace"
    assert view["destinationScopeIds"] == [] and "synthetic-only" in view["limitations"]
    assert rig.token not in repr(view)
    assert rig.connection() == view
    checks = [entry for entry in rig.fake.requests if entry.path == "/v1/users/me"]
    assert [entry.authorization for entry in checks] == [f"Bearer {rig.token}"]
    # A replay returns the original, even with another token, and asks Notion nothing.
    other, _ = rig.new_token()
    assert rig.configure(key=key, token=other) == view
    assert len(rig.fake.requests) == len(checks)


def test_replace_advances_the_revision_ends_older_work_and_resets_the_capability(
    transactions, connect, authority, tmp_path
):
    rig = sf.build(transactions, connect, authority, tmp_path)
    first = rig.configure()
    approval = rig.approve(rig.preview(rig.page()))
    with connect("export") as conn:
        conn.execute(
            "UPDATE export.connection SET creation_capability='confirmed' WHERE id=%s",
            (UUID(first["connectionId"]),),
        )
    token, bot = rig.new_token()

    replaced = rig.configure(token=token, expected=1)

    assert (replaced["connectionId"], replaced["revision"]) == (first["connectionId"], "2")
    row = flows.connection_row(connect, UUID(first["connectionId"]))
    assert row["creation_capability"] == "unknown"
    invalidated = flows.approval_row(connect, UUID(approval["approvalId"]))
    assert (invalidated["state"], invalidated["invalidation_reason"]) == (
        "invalidated",
        "connection-changed",
    )
    # A stale expected revision is a compare-and-set refusal (BR1.3).
    assert sf.refuse("configure", lambda: rig.configure(token=token, expected=1)) == "CONFLICT"


def test_disconnect_ends_approvals_and_accepted_effects_but_keeps_unknown_ones(
    transactions, connect, authority, tmp_path
):
    rig = sf.build(transactions, connect, authority, tmp_path)
    rig.configure()
    unknown = rig.press(rig.page())["effect"]
    rig.uncertain(unknown)
    accepted = rig.press(rig.page())["effect"]
    approval = rig.approve(rig.preview(rig.page()))

    view = rig.service.disconnect(authority, {})

    assert (view["state"], view["revision"]) == ("disconnected", "2")
    assert flows.effect_row(connect, UUID(unknown["effectId"]))["state"] == "unknown"
    ended = flows.effect_row(connect, UUID(accepted["effectId"]))
    assert (ended["state"], ended["outcome_reason"]) == ("invalidated", "connection-changed")
    assert flows.approval_row(connect, UUID(approval["approvalId"]))["invalidation_reason"] == (
        "connection-changed"
    )
    # A repeat returns the disconnected connection unchanged.
    assert rig.service.disconnect(authority, {}) == view


def test_disconnect_lets_an_executing_export_finish(transactions, connect, authority, tmp_path):
    rig = sf.build(transactions, connect, authority, tmp_path)
    rig.configure()
    effect = rig.press(rig.page())["effect"]
    claimed = rig.claim(effect)
    approval = rig.approve(rig.preview(rig.page()))

    rig.service.disconnect(authority, {})

    assert flows.effect_row(connect, UUID(effect["effectId"]))["state"] == "executing"
    assert flows.approval_row(connect, UUID(approval["approvalId"]))["state"] == "invalidated"
    finished = rig.repo.record_write_outcome(
        claimed.effect["id"],
        claimed.attempt["id"],
        claimed.effect["revision"],
        sf.outcome_created(),
        now=rig.clock.now,
    )
    assert finished["state"] == "succeeded"


def test_a_stored_token_refused_during_a_listing_revokes_with_the_same_consequences(
    transactions, connect, authority, tmp_path
):
    rig = sf.build(transactions, connect, authority, tmp_path)
    rig.configure()
    approval = rig.approve(rig.preview(rig.page()))
    rig.fake.queue("search", Answer.error(401))

    code = sf.refuse("list_destinations", lambda: rig.service.list_destinations(authority, {}))

    assert code == "NOT_FOUND"
    view = rig.connection()
    assert (view["state"], view["revision"]) == ("revoked", "2")
    assert flows.approval_row(connect, UUID(approval["approvalId"]))["invalidation_reason"] == (
        "connection-changed"
    )


def test_shape_and_policy_refusals_never_contact_notion(transactions, connect, authority, tmp_path):
    rig = sf.build(transactions, connect, authority, tmp_path)
    policy = rig.policy.reference()
    for token in ("", "   ", "line\nbreak", "x" * (rig.policy.token_max_length + 1), 7):
        value = {"token": token, "credentialPolicy": policy}
        code, error = sf.refusal(
            lambda v=value: rig.service.configure(authority, v, operation=uuid4())
        )
        assert code == "INVALID_ARGUMENT" and error.current == {"field": "token"}
        assert "line" not in str(error)
    other = {"token": rig.token, "credentialPolicy": {"policyId": "other", "revision": "1"}}
    assert sf.refuse(
        "configure", lambda: rig.service.configure(authority, other, operation=uuid4())
    ) == ("POLICY_UNRESOLVED")
    assert rig.fake.requests == []
    assert connection_rows(connect, authority.account_id) == []


def test_refused_and_unreachable_checks_release_the_pending_row_and_store_nothing(
    transactions, connect, authority, tmp_path
):
    rig = sf.build(transactions, connect, authority, tmp_path)
    key = uuid4()

    assert sf.refuse("configure", lambda: rig.configure(token="unknown-token", key=key)) == (
        "INVALID_TOKEN"
    )
    assert connection_rows(connect, authority.account_id) == []
    asked = len(rig.fake.requests)
    # The same key answers the recorded refusal, without asking Notion again.
    assert sf.refuse("configure", lambda: rig.configure(key=key)) == "INVALID_TOKEN"
    assert len(rig.fake.requests) == asked

    rig.fake.queue("users.me", Answer.error(503))
    assert sf.refuse("configure", rig.configure) == "DEPENDENCY_UNAVAILABLE"
    assert connection_rows(connect, authority.account_id) == []
    assert sf.refuse("read_connection", rig.connection) == "NOT_FOUND"


def test_a_stale_pending_row_is_taken_over_and_a_fresh_one_refuses(
    transactions, connect, authority, tmp_path
):
    rig = sf.build(transactions, connect, authority, tmp_path)
    takeover = rig.policy.pending_takeover_seconds
    stale = rig.repo.reserve_connection(
        authority, None, now=rig.clock.now - dt.timedelta(seconds=takeover + 1)
    )

    view = rig.configure()

    assert (view["connectionId"], view["revision"]) == (str(stale.connection_id), "1")
    flows.fresh(connect, authority.account_id)
    held = rig.repo.reserve_connection(authority, None, now=rig.clock.now)
    assert sf.refuse("configure", rig.configure) == "CONFLICT"
    rows = connection_rows(connect, authority.account_id)
    assert [(row["state"], row["pending_holder"]) for row in rows] == [("pending", held.holder)]


def test_configure_from_unavailable_answers_conflict(transactions, connect, authority, tmp_path):
    rig = sf.build(transactions, connect, authority, tmp_path)
    view = rig.configure()
    assert rig.repo.set_availability(
        authority.account_id, UUID(view["connectionId"]), 1, available=False
    )

    assert sf.refuse("configure", lambda: rig.configure(expected=1)) == "CONFLICT"
    assert (rig.connection()["state"], rig.connection()["revision"]) == ("unavailable", "1")
    assert (
        sf.refuse("list_destinations", lambda: rig.service.list_destinations(authority, {}))
        == "POLICY_UNRESOLVED"
    )
