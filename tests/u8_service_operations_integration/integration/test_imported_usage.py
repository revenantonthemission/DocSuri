"""Imported usage (U8 plan Step 32; the person's decision of 2026-10-23, "Grant migrated
accounts"): UsageEntitlements' `grantImportedUsage`, run by the import phases after the
accounts, on a dry run of the synthetic v1 into a rehearsal database of the run's own
(`test_migration_run.Stage`):

1. each imported account that is active in v2 holds a grant under the run's realm policy
   (`u8-synthetic-v1`), the full quota and not revoked: what the reservation checks before
   paper assistance may reserve;
2. a closed or not-active imported account gets none, and an account the run did not
   import is never granted;
3. the idempotency pass over the same snapshot grants nothing new;
4. the parity report counts the grants by outcome, and the kind reconciles.
"""

from __future__ import annotations

import pytest

from backend.modules.accounts.u8_control_policy import U8_SYNTHETIC_POLICY
from backend.modules.operations.migration.misfits import Decisions
from backend.modules.operations.migration.phases import ImportRun
from backend.modules.operations.migration.v1_source import V1Source
from docsuri_ops.migration.realm import owners_for
from tests.u8_service_operations_integration import recovery_flows as rf
from tests.u8_service_operations_integration import v1_flows as vf
from tests.u8_service_operations_integration.integration.test_migration_run import Stage

POLICY = U8_SYNTHETIC_POLICY


@pytest.fixture(scope="module")
def v1_database(realm):
    value = vf.SyntheticV1(realm).create()
    yield value
    value.drop()


@pytest.fixture
def stage(tmp_path, realm, clock, v1_database):
    value = Stage(tmp_path, realm, clock, v1_database)
    yield value
    value.cleanup()


@pytest.fixture
def reported(stage):
    run = stage.started()
    assert stage.tool.run(run["runId"])["state"] == "reported"
    current = stage.runs.require(run["runId"])
    target = stage.databases_of(current)["rehearsal-database"][0]
    return run, target


def accounts_and_grants(realm, target):
    with rf.admin(realm, target) as conn:
        active = {row[0] for row in conn.execute(
            "SELECT id FROM accounts.account WHERE active AND verified "
            "AND lifecycle_state='active'").fetchall()}
        every = {row[0] for row in conn.execute("SELECT id FROM accounts.account").fetchall()}
        grants = {row[0]: row[1:] for row in conn.execute(
            "SELECT account_id,allocation,policy,revoked FROM usage.entitlement").fetchall()}
    return active, every, grants


def test_each_active_imported_account_holds_a_grant_under_the_realm_policy(reported, realm):
    _, target = reported
    active, _, grants = accounts_and_grants(realm, target)
    assert active, "the synthetic v1 imports active accounts"
    for account in active:
        assert grants[account] == (POLICY.quota, POLICY.policy_id, False), account


def test_a_closed_or_not_imported_account_gets_none(reported, realm):
    _, target = reported
    active, every, grants = accounts_and_grants(realm, target)
    # Only accounts the run imported, and only the active ones, hold a grant.
    assert set(grants) == active
    assert not set(grants) & (every - active)


def test_the_idempotency_pass_grants_nothing_new(reported, stage, realm):
    run, target = reported
    _, _, before = accounts_and_grants(realm, target)
    owners, close = owners_for(stage.realm)(target)
    try:
        with stage.v1.connect() as conn:
            tallies = ImportRun(V1Source(conn, index_documents=stage.v1.index_documents(),
                                         objects=stage.v1.objects()),
                                owners, Decisions.from_ledger(stage.ledger),
                                clock=stage.clock).run()
    finally:
        close()
    grants = tallies["usage-grant"]
    assert grants.imported == 0 and grants.updated == 0
    assert grants.unchanged == len(before)
    _, _, after = accounts_and_grants(realm, target)
    assert after == before


def test_the_parity_report_counts_the_grants_by_outcome(reported, stage, realm):
    import json
    from pathlib import Path

    run, target = reported
    active, every, _ = accounts_and_grants(realm, target)
    record = stage.ledger.get("parity-report", run["runId"])
    path = stage.tool.platform.evidence / Path(record["reportRef"]).name
    report = json.loads(path.read_text())
    entry = next(kind for kind in report["kinds"] if kind["kind"] == "usage-grant")
    assert entry["imported"] == len(active)
    assert entry["unchanged"] == 0 and entry["updated"] == 0
    assert sum(entry["skipped"].values()) == len(every - active)
    assert set(entry["skipped"]) <= {"account-not-active"}
    assert entry["reconciles"] is True and record["reconciles"] is True
