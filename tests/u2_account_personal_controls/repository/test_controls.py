"""Actual owner-store recovery; no in-memory substitutes."""

from uuid import NAMESPACE_URL, uuid4, uuid5

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
def authority(connect, realm, request, fixture_discard):
    """Dedicated run-scoped owner; the finite outstanding-reset cap stays free."""
    identity = realm[0].run_id + ":repository:" + request.node.name
    account, session = uuid5(NAMESPACE_URL, identity), uuid5(NAMESPACE_URL, identity + ":session")
    revision = uuid4()
    with connect("accounts") as conn:
        conn.execute(
            "INSERT INTO accounts.account(id,email,password_hash,verified,active,authority_revision,display_name) "
            "VALUES(%s,%s,'database-fixture-not-a-login-hash',true,true,%s,'Synthetic repository owner') "
            "ON CONFLICT(id) DO UPDATE SET active=true,verified=true,lifecycle_state='active',"
            "authority_revision=excluded.authority_revision",
            (account, str(account) + "@fixture.invalid", revision),
        )
        conn.execute(
            "INSERT INTO accounts.session(id,account_id,token_hash,csrf_hash,authority_revision,expires_at,purpose) "
            "VALUES(%s,%s,%s,%s,%s,clock_timestamp()+interval '15 minutes','full_session') "
            "ON CONFLICT(id) DO UPDATE SET revoked=false,expires_at=excluded.expires_at,"
            "authority_revision=excluded.authority_revision",
            (session, account, str(uuid4()), str(uuid4()), revision),
        )
        for purpose in ("local-research", "personalization"):
            conn.execute(
                "INSERT INTO accounts.consent(account_id,purpose,granted) VALUES(%s,%s,true) "
                "ON CONFLICT(account_id,purpose) DO UPDATE SET granted=true",
                (account, purpose),
            )
    yield Authority(account, session)
    fixture_discard(account)


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
    accept(resets, authority)
    accept(resets, authority)
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
    identity = transactions.profile.run_id + ":absent-assignment-fixture"
    account, session, revision = (
        uuid5(NAMESPACE_URL, identity),
        uuid5(NAMESPACE_URL, identity + ":session"),
        uuid4(),
    )
    with connect("accounts") as conn:
        conn.execute(
            "INSERT INTO accounts.account(id,email,password_hash,display_name,verified,active,authority_revision) "
            "VALUES(%s,%s,'not-a-login-hash','read-only assignment fixture',true,true,%s) "
            "ON CONFLICT(id) DO UPDATE SET active=true,authority_revision=excluded.authority_revision",
            (account, str(account) + "@fixture.invalid", revision),
        )
        conn.execute(
            "INSERT INTO accounts.session(id,account_id,token_hash,csrf_hash,authority_revision,expires_at) "
            "VALUES(%s,%s,%s,%s,%s,clock_timestamp()+interval '15 minutes') ON CONFLICT(id) DO UPDATE "
            "SET revoked=false,authority_revision=excluded.authority_revision,expires_at=excluded.expires_at",
            (session, account, str(uuid4()), str(uuid4()), revision),
        )
    authority = Authority(account, session)
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
    with connect("accounts") as conn:
        conn.execute("UPDATE accounts.account SET active=false WHERE id=%s", (account,))


def test_usage_records_keep_original_period_without_writes(transactions, authority, connect):
    from backend.modules.plans.control_service import ControlUsageService

    reservation = uuid4()
    with connect("usage") as conn:
        conn.execute(
            "INSERT INTO usage.entitlement(account_id,allocation,policy) "
            "VALUES(%s,3,'u2-synthetic-v1') ON CONFLICT DO NOTHING",
            (authority.account_id,),
        )
        conn.execute(
            "INSERT INTO usage.reservation(id,account_id,operation_id,intent_hash,disposition,period_id) "
            "VALUES(%s,%s,%s,%s,'reserved','original-acceptance-period')",
            (reservation, authority.account_id, uuid4(), "f" * 64),
        )

    def snapshot():
        with connect("usage") as conn:
            return conn.execute(
                "SELECT id,disposition,period_id,quantity,xmin::text FROM usage.reservation "
                "WHERE account_id=%s ORDER BY id",
                (authority.account_id,),
            ).fetchall()

    before = snapshot()
    service = ControlUsageService(transactions, SYNTHETIC_POLICY)
    page = service.records(authority, {"limit": 50}, ControlCursor(b"u" * 32))
    items = [item for item in page["items"] if item["usageRecordId"] == str(reservation)]
    assert items and items[0]["periodId"] == "original-acceptance-period"
    assert snapshot() == before
    with connect("usage") as conn:
        conn.execute("DELETE FROM usage.reservation WHERE id=%s", (reservation,))


def test_missing_store_fails_instead_of_substituting_success(realm, authority):
    """A closed owner facility is never answered from an in-memory fallback."""
    from backend.transactions import OwnerTransactions

    closed = OwnerTransactions(realm[0])
    closed.close()
    with pytest.raises(ValueError, match="closed or unknown owner pool"):
        GuardedUsageRepository(closed).inspect_assignment(authority)


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
