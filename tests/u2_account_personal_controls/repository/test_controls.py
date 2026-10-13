"""Actual owner-store recovery; no in-memory substitutes."""

from uuid import uuid4

import pytest
from backend.modules.accounts.control_cursor import ControlCursor
from backend.modules.accounts.control_policy import SYNTHETIC_POLICY
from backend.modules.accounts.control_repository import ControlRepository
from backend.modules.personalization.guarded_service import GuardedSettingsService
from backend.modules.personalization.reset_repository import ResetRepository
from backend.modules.plans.guarded_repository import GuardedUsageRepository
from backend.transactions import Authority

pytestmark = pytest.mark.u2_repository


@pytest.fixture
def resets(transactions):
    return ResetRepository(transactions, SYNTHETIC_POLICY, ControlCursor(b"r" * 32))


def accept(resets, authority):
    revision = GuardedSettingsService(resets.transactions).read(authority)["revision"]
    return resets.accept(
        authority,
        uuid4(),
        uuid4() if revision is None else __import__("uuid").UUID(revision),
        "delete_behavior",
        manifest=(("Personalization", "behavior"), ("ServiceOperations", "restore")),
        manifest_revision="installed-u2-v1",
    )


def test_reset_survives_new_repository_and_discovery(resets, authority):
    result = accept(resets, authority)
    fresh = ResetRepository(resets.transactions, SYNTHETIC_POLICY, ControlCursor(b"r" * 32))
    page = fresh.list(authority, view="outstanding", limit=50)
    assert result["resetId"] in [item["resetId"] for item in page["items"]]
    state = fresh.inspect(authority, __import__("uuid").UUID(result["resetId"]))
    assert state["reset"]["statusRevision"] == "1"
    assert len(state["scopes"]) == 2


def test_reset_lost_ack_replays_immutable_outcome(resets, authority):
    from uuid import UUID

    operation = uuid4()
    expected = UUID(GuardedSettingsService(resets.transactions).read(authority)["revision"])
    args = (authority, operation, expected, "delete_behavior")
    options = dict(manifest=(("Personalization", "behavior"),), manifest_revision="installed-u2-v1")
    original = resets.accept(*args, **options)
    assert resets.accept(*args, **options) == original


def test_reset_changed_intent_conflicts(resets, authority):
    from uuid import UUID

    operation = uuid4()
    expected = UUID(GuardedSettingsService(resets.transactions).read(authority)["revision"])
    options = dict(manifest=(("Personalization", "behavior"),), manifest_revision="installed-u2-v1")
    resets.accept(authority, operation, expected, "delete_behavior", **options)
    with pytest.raises(ValueError, match="operation conflict"):
        resets.accept(authority, operation, expected, "reset_profile", **options)


def test_reset_stale_control_fails(resets, authority):
    with pytest.raises(ValueError, match="stale settings"):
        resets.accept(
            authority,
            uuid4(),
            uuid4(),
            "delete_behavior",
            manifest=(("Personalization", "behavior"),),
            manifest_revision="installed-u2-v1",
        )


def test_reset_absent_and_foreign_reveal_no_state(resets, authority, identities):
    from uuid import UUID

    result = accept(resets, authority)
    with pytest.raises(PermissionError):
        resets.inspect(authority, uuid4())
    # A session for a different supplied owner does not become that owner.
    with pytest.raises(Exception) as failure:
        resets.inspect(Authority(identities["b"], identities["session"]), UUID(result["resetId"]))
    assert "authority denied" in str(failure.value)


def test_reset_pagination_has_no_duplicates(resets, authority):
    accept(resets, authority)
    accept(resets, authority)
    first = resets.list(authority, view="history", limit=1)
    second = resets.list(authority, view="history", limit=1, cursor=first["page"]["nextCursor"])
    assert first["items"][0]["resetId"] != second["items"][0]["resetId"]
    assert first["page"]["snapshotRevision"] == second["page"]["snapshotRevision"]


def test_reset_cursor_cannot_change_view_or_size(resets, authority):
    first = resets.list(authority, view="history", limit=1)
    assert first["page"]["nextCursor"]
    with pytest.raises(ValueError):
        resets.list(authority, view="outstanding", limit=1, cursor=first["page"]["nextCursor"])
    with pytest.raises(ValueError):
        resets.list(authority, view="history", limit=2, cursor=first["page"]["nextCursor"])


def test_reset_reads_do_not_write(resets, authority, connect):
    from uuid import UUID

    result = accept(resets, authority)

    def snapshot():
        with connect("personalization") as conn:
            return conn.execute(
                "SELECT id,status_revision,disposition,xmin::text FROM personalization.reset_responsibility WHERE account_id=%s ORDER BY id",
                (authority.account_id,),
            ).fetchall()

    before = snapshot()
    resets.list(authority, view="history", limit=50)
    resets.inspect(authority, UUID(result["resetId"]))
    assert snapshot() == before


def test_reset_scope_fences_stale_worker_and_preserves_ack(resets, authority):
    from uuid import UUID

    result = accept(resets, authority)
    identifier = UUID(result["resetId"])
    claim = resets.claim_scope(identifier, "Personalization", "behavior")
    with pytest.raises(ValueError, match="stale"):
        resets.record_scope(
            identifier,
            "Personalization",
            "behavior",
            claim["generation"] + 1,
            evidence=uuid4(),
            reason="done",
        )
    resets.record_scope(
        identifier,
        "Personalization",
        "behavior",
        claim["generation"],
        evidence=uuid4(),
        reason="done",
    )
    state = resets.inspect(authority, identifier)
    assert state["reset"]["statusRevision"] == "2"
    assert state["reset"]["disposition"] == "pending"
    assert result["disposition"] == "pending"


def test_absent_assignment_is_read_only(transactions, authority, connect):
    repository = GuardedUsageRepository(transactions)
    with connect("usage") as conn:
        before = conn.execute(
            "SELECT count(*) AS n FROM usage.entitlement WHERE account_id=%s",
            (authority.account_id,),
        ).fetchone()["n"]
    value = repository.inspect_assignment(authority)
    assert value["revision"] and value["disposition"] == "unassigned"
    with connect("usage") as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM usage.entitlement WHERE account_id=%s",
                (authority.account_id,),
            ).fetchone()["n"]
            == before
        )


def test_profile_receipt_survives_new_revision(transactions, authority):
    from uuid import UUID

    repository = ControlRepository(transactions, SYNTHETIC_POLICY)
    revision = UUID(repository.profile(authority)["revision"])
    operation = uuid4()
    result = repository.update_profile(authority, operation, revision, {"displayName": "연구자"})
    assert (
        repository.update_profile(authority, operation, revision, {"displayName": "연구자"})
        == result
    )
    assert repository.profile(authority)["displayName"] == "연구자"


def test_profile_conflicting_tab_cannot_overwrite(transactions, authority):
    from uuid import UUID

    repository = ControlRepository(transactions, SYNTHETIC_POLICY)
    revision = UUID(repository.profile(authority)["revision"])
    repository.update_profile(authority, uuid4(), revision, {"displayName": "먼저 저장"})
    with pytest.raises(ValueError, match="stale profile"):
        repository.update_profile(authority, uuid4(), revision, {"displayName": "늦게 저장"})
    assert repository.profile(authority)["displayName"] == "먼저 저장"
