"""Production fails closed without U8's parts (U8 plan Step 44; the person's decision of
2026-10-24, "Move, scope tools, test U2").

U2's files keep only seams whose default is U2's built behaviour, so the complete realms
run on U8's own parts. These tests show, in the composed realm and on the production
stand-in, that the composition builds U8's capacity, lifecycle worker, entry, lifecycle
service and every usage authority, and that the start is refused when any of them is
U2's; that each U8 part refuses U2's in its place; and that each U2 default refuses or
blocks there.
"""

from __future__ import annotations

import dataclasses
from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.control_runtime import ControlCapacity
from backend.control_worker import ControlWorker
from backend.modules.accounts.control_policy import SYNTHETIC_POLICY, PolicyUnavailable
from backend.modules.accounts.password import get_password_hasher
from backend.modules.accounts.services.control_lifecycle import ControlLifecycleService
from backend.modules.accounts.services.guarded_entry import GuardedEntryService
from backend.modules.accounts.u8_control_http import d1_control_router
from backend.modules.accounts.u8_control_policy import PRODUCTION_POLICY, U8_SYNTHETIC_POLICY
from backend.modules.accounts.u8_entry import CompleteControlEntryService
from backend.modules.accounts.u8_lifecycle import CompleteLifecycleService
from backend.modules.accounts.u8_local_http import d1_account_router
from backend.modules.accounts.u8_verifier_key import KeyringRefused, recover_production
from backend.modules.operations.lifecycle import GatedLifecycle
from backend.modules.plans.guarded_repository import GuardedUsageRepository
from backend.modules.plans.u8_usage import CompleteUsage, ImportedUsage, use_complete_usage
from backend.u8_capacity import BudgetedCapacity, CapacityRefresher
from backend.u8_host import (
    LIFECYCLE_MANIFEST,
    StartRefused,
    compose,
    host_app,
    require_complete_parts,
)
from backend.u8_workers import CompleteLifecycleWorker, CompleteWorker
from tests.u8_service_operations_integration.conftest import _make_account
from tests.u8_service_operations_integration.host_flows import (
    OTHER_MEMBER,
    production_composition,
    standin_account,
)

THREE = ("ResearchWorkspace", "ApprovedExport", "ServiceOperations")
PASSWORD = "synthetic-plain-worker-" + uuid4().hex[:12]  # per run (L1-36)


@pytest.fixture(scope="module")
def composed(realm):
    value = compose(realm, process="workers")
    yield value
    value.close()


def assert_u8_parts(composition) -> None:
    parts = composition.parts
    assert isinstance(parts["account-controls"]["entry"], CompleteControlEntryService)
    assert isinstance(parts["account-controls"]["lifecycle"], CompleteLifecycleService)
    lifecycle = composition.worker.lifecycle
    assert isinstance(lifecycle, CompleteLifecycleWorker)
    assert isinstance(lifecycle.lifecycle, GatedLifecycle)
    assert isinstance(lifecycle.lifecycle.service, CompleteLifecycleService)
    execution = parts["research-workspace"]["execution"]
    dispatch = parts["paper-corpus"]["dispatch"]
    for usage in (execution.usage, dispatch.usage, dispatch.admission.usage):
        assert isinstance(usage, CompleteUsage)
    app = host_app(composition)
    assert isinstance(app.state.control_capacity, BudgetedCapacity)
    assert isinstance(app.state.capacity_refresher, CapacityRefresher)
    require_complete_parts(composition)  # passes as composed


def test_the_composed_realm_builds_u8s_parts(composed):
    assert_u8_parts(composed)


def test_the_production_stand_in_builds_u8s_parts(realm):
    with production_composition(realm, mode="live") as env:
        assert_u8_parts(env.composition)
        assert env.composition.parts["account-controls"]["entry"].control_policy is (
            PRODUCTION_POLICY)
        # An account without a grant gets none from an assistance request.
        owner = standin_account(env.standin, "ungranted", grant=False)
        env.composition.parts["paper-corpus"]["dispatch"].usage.ensure_entitlement(owner)
        with env.standin.connect("usage") as conn:
            assert conn.execute("SELECT 1 FROM usage.entitlement WHERE account_id=%s",
                                (owner.account_id,)).fetchone() is None


def test_the_start_is_refused_when_any_part_is_u2s(composed, monkeypatch):
    parts, transactions = composed.parts, composed.transactions
    controls = parts["account-controls"]
    entry = controls["entry"]
    plain_lifecycle = ControlLifecycleService(entry, LIFECYCLE_MANIFEST, revision="u8-owners-v1")
    plain_worker = ControlWorker(entry, controls["lifecycle"], controls["personalization"],
                                 parts["paper-journey"]["assistance_files"])
    execution = parts["research-workspace"]["execution"]
    dispatch = parts["paper-corpus"]["dispatch"]
    built = GuardedUsageRepository(transactions)
    replacements = (
        ("account-entry", lambda: monkeypatch.setitem(controls, "entry", GuardedEntryService(
            transactions))),
        ("lifecycle-service", lambda: monkeypatch.setitem(controls, "lifecycle",
                                                          plain_lifecycle)),
        ("lifecycle-worker", lambda: monkeypatch.setattr(composed.worker, "lifecycle",
                                                         plain_worker)),
        ("research-usage", lambda: monkeypatch.setattr(execution, "usage", built)),
        ("assistance-usage", lambda: monkeypatch.setattr(dispatch, "usage", built)),
        ("assistance-admission-usage",
         lambda: monkeypatch.setattr(dispatch.admission, "usage", built)),
    )
    for detail, replace in replacements:
        replace()
        with pytest.raises(StartRefused) as refused:
            require_complete_parts(composed)
        assert (refused.value.check, refused.value.detail) == ("composition", detail)
        monkeypatch.undo()
    require_complete_parts(composed)
    # An earlier realm's composition is never checked: it has none of these parts.
    earlier = SimpleNamespace(profile=SimpleNamespace(realm="approved-export"), parts={},
                              worker=None)
    require_complete_parts(earlier)


def test_the_lifecycle_worker_runs_only_u8s_lifecycle_service(composed):
    controls = composed.parts["account-controls"]
    files = composed.parts["paper-journey"]["assistance_files"]
    entry, complete = controls["entry"], controls["lifecycle"]
    plain = ControlLifecycleService(entry, LIFECYCLE_MANIFEST, revision="u8-owners-v1")
    for service in (complete, GatedLifecycle(complete)):
        CompleteLifecycleWorker(entry, service, controls["personalization"], files)
    for service in (plain, GatedLifecycle(plain)):
        with pytest.raises(TypeError):
            CompleteLifecycleWorker(entry, service, controls["personalization"], files)
    # A recorder is refused with any other lifecycle worker.
    plain_worker = ControlWorker(entry, complete, controls["personalization"], files)
    with pytest.raises(TypeError):
        CompleteWorker(SimpleNamespace(run_once=lambda limit=1: {}), plain_worker,
                       set_aside=lambda *args: None)


def test_a_plain_worker_leaves_the_three_parts_blocked(composed, connect, realm):
    """U2's built table has none of the three complete-realm participants, so each of
    their parts is acknowledged without evidence (`required-scope-evidence-unavailable`).

    The pass runs on the realm's real transactions and the real admission reads (your
    answer of 2026-11-11, "Rewrite, keep two"). Its one open request is written through
    AccountAccess's own lifecycle service under a manifest revision of this run's own, so
    the built selection's lifecycle and manifest revision filters pick exactly it."""
    controls = composed.parts["account-controls"]
    entry = controls["entry"]
    revision = "u8-plain-worker-" + uuid4().hex[:12]
    manifest = tuple((name, "live_records") for name in THREE)
    authority = _make_account(connect, realm, suffix="plain-worker")
    with connect("accounts") as conn:
        conn.execute(
            "UPDATE accounts.account SET lifecycle_state='active',active=true,password_hash=%s "
            "WHERE id=%s", (get_password_hasher().hash(PASSWORD), authority.account_id))
        current = conn.execute("SELECT lifecycle_revision FROM accounts.account WHERE id=%s",
                               (authority.account_id,)).fetchone()["lifecycle_revision"]
    claimed, acknowledged = [], []

    class Lifecycle:
        def __init__(self):
            self.manifest, self.revision = manifest, revision

        def claim(self, request_id, participant, scope):
            claimed.append(request_id)
            return {"participant": participant, "scope": scope}

        def acknowledge(self, ticket, *, evidence, reason, **options):
            acknowledged.append((ticket["participant"], evidence, reason))

    try:
        request = ControlLifecycleService(entry, manifest, revision=revision).request(
            authority, uuid4(), current, "withdraw", PASSWORD)["requestId"]
        plain = ControlWorker(entry, Lifecycle(), controls["personalization"],
                              composed.parts["paper-journey"]["assistance_files"])
        assert not set(THREE) & set(plain.participants)
        assert [str(row["id"]) for row in plain._open_requests(4)] == [request]
        plain.run_once(limit=1)
        assert [str(item) for item in claimed] == [request] * len(THREE)
        assert acknowledged == [(name, None, "required-scope-evidence-unavailable")
                                for name in THREE]
    finally:
        # The account is active again under a new lifecycle revision, so no selection
        # reads the request this test left open.
        with connect("accounts") as conn:
            conn.execute(
                "UPDATE accounts.account SET lifecycle_state='active',active=true,"
                "lifecycle_revision=gen_random_uuid() WHERE id=%s", (authority.account_id,))


def test_a_built_capacity_never_admits_and_the_refresher_refuses_it(composed):
    built = ControlCapacity(composed.transactions)
    assert built.admitting is False
    with pytest.raises(TypeError):
        CapacityRefresher(built)
    # The budgeted capacity is the complete realms' alone.
    earlier = SimpleNamespace(profile=dataclasses.replace(
        composed.profile, realm="account-controls"))
    with pytest.raises(ValueError):
        BudgetedCapacity(earlier)


def test_the_entry_refuses_u2s_policy_and_production_without_its_admission(composed):
    transactions = composed.transactions
    with pytest.raises(PolicyUnavailable):
        CompleteControlEntryService(transactions, SYNTHETIC_POLICY)
    with pytest.raises(PolicyUnavailable, match="admission"):
        CompleteControlEntryService(transactions, PRODUCTION_POLICY)


def test_the_d1_routers_refuse_a_u2_entry(composed):
    plain = GuardedEntryService(composed.transactions)
    with pytest.raises(PermissionError):
        d1_account_router(plain)
    with pytest.raises(PermissionError):
        d1_control_router(plain, composed.parts["account-controls"]["lifecycle"])


def test_imported_usage_and_the_complete_usage_refuse_u2s_realm_and_policy(composed):
    u2 = SimpleNamespace(profile=SimpleNamespace(realm="account-controls"))
    with pytest.raises(PolicyUnavailable):
        ImportedUsage(u2, U8_SYNTHETIC_POLICY)
    with pytest.raises(PolicyUnavailable):
        ImportedUsage(composed.transactions, SYNTHETIC_POLICY)
    with pytest.raises(PolicyUnavailable):
        use_complete_usage(SimpleNamespace(usage=None), u2)


def test_production_key_recovery_refuses_another_folder_and_u2s_snapshot(tmp_path):
    import os

    profile = tmp_path / "profile"
    keys = profile / "control-keys"
    keys.mkdir(parents=True, mode=0o700)
    os.chmod(profile, 0o700)
    # A snapshot in U2's own folder and format is never read in production.
    u2_folder = keys / "account-key-recovery"
    u2_folder.mkdir(mode=0o700)
    (u2_folder / ("a" * 64 + ".json")).write_text("{}")
    identity = {"run_id": "docsuri-v2-" + "0" * 16, "expected_digest": "a" * 64,
                "expected_generation": 1}
    with pytest.raises(KeyringRefused, match="snapshot-missing"):
        recover_production(keys, profile_root=profile, **identity)
    with pytest.raises(KeyringRefused, match="recovery-folder-refused"):
        recover_production(u2_folder, profile_root=profile, **identity)
    assert sorted(os.listdir(keys)) == ["account-key-recovery"]  # nothing was written


def test_the_fixtures_novelty_reserves_through_u2s_controls_as_research(
        composed, connect, realm):
    """Step 44's correction: the composed realm's fixtures run novelty through U2's usage
    controls under the realm's policy, in its period, recorded for ResearchWorkspace;
    the fixture account's own grant pays for it and nothing is granted on the way."""
    import secrets
    import sys
    from pathlib import Path

    from backend.transactions import Authority
    from tests.u8_service_operations_integration import recovery_flows as rf

    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
    import u8_fixtures

    owner = _make_account(connect, realm, suffix=OTHER_MEMBER)
    with rf.admin(realm, realm.database_name) as conn, conn.transaction():
        for table in ("rejected_operation", "reservation", "entitlement"):
            conn.execute(f"DELETE FROM usage.{table} WHERE account_id=%s", (owner.account_id,))
    assert ImportedUsage(composed.transactions, U8_SYNTHETIC_POLICY).grant_imported(
        owner.account_id, source="realm_fixture")["disposition"] == "imported"
    session = uuid4()
    with connect("accounts") as conn:
        revision = conn.execute("SELECT authority_revision FROM accounts.account WHERE id=%s",
                                (owner.account_id,)).fetchone()["authority_revision"]
        conn.execute(
            "INSERT INTO accounts.session(id,account_id,token_hash,csrf_hash,"
            "authority_revision,expires_at,purpose) VALUES(%s,%s,%s,%s,%s,"
            "clock_timestamp()+interval '30 minutes','full_session')",
            (session, owner.account_id, secrets.token_hex(32), secrets.token_hex(32), revision))
    result = u8_fixtures.ready_novelty(composed.transactions,
                                       Authority(owner.account_id, session), None)
    assert result["artifactId"]
    with connect("usage") as conn:
        rows = conn.execute("SELECT * FROM usage.reservation WHERE account_id=%s",
                            (owner.account_id,)).fetchall()
        entitlement = conn.execute("SELECT * FROM usage.entitlement WHERE account_id=%s",
                                   (owner.account_id,)).fetchone()
    assert len(rows) == 1
    [row] = rows
    assert row["operation_owner"] == "ResearchWorkspace"
    assert row["period_id"].startswith("u2-period:")
    assert row["policy_ref"] == U8_SYNTHETIC_POLICY.reference
    assert entitlement["policy"] == U8_SYNTHETIC_POLICY.policy_id  # the grant, unchanged


def test_an_ungranted_assistance_request_writes_no_usage(composed, connect, realm):
    """Step 44's correction (both complete realms build the same dispatch): the dispatch's
    usage authority grants nothing, so an account without a grant gets none from an
    assistance request; the production stand-in's is the same `CompleteUsage`."""
    from tests.u8_service_operations_integration import recovery_flows as rf

    authority = _make_account(connect, realm, suffix=OTHER_MEMBER)
    with rf.admin(realm, realm.database_name) as conn, conn.transaction():
        for table in ("rejected_operation", "reservation", "entitlement"):
            conn.execute(f"DELETE FROM usage.{table} WHERE account_id=%s",
                         (authority.account_id,))
    dispatch = composed.parts["paper-corpus"]["dispatch"]
    dispatch.usage.ensure_entitlement(authority)  # what the accept route calls first
    with connect("usage") as conn:
        assert conn.execute("SELECT 1 FROM usage.entitlement WHERE account_id=%s",
                            (authority.account_id,)).fetchone() is None
