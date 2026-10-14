"""Owner export shape and live-realm denial; actual quarantine replay is separate."""

from dataclasses import replace
from uuid import uuid4

import pytest
from psycopg.errors import InsufficientPrivilege

from backend.control_restore import (
    AccountsRestore,
    AssistanceRestore,
    DiscoveryRestore,
    UsageRestore,
)
from docsuri_ops.u2_restore_context import RestoreContext, fragment_digest

pytestmark = pytest.mark.u2_operations
OWNERS = (AccountsRestore, UsageRestore, AssistanceRestore, DiscoveryRestore)


def context(transactions):
    return RestoreContext(
        run_id=transactions.profile.run_id,
        checkpoint_id=uuid4(),
        sequence=1,
        previous_digest=None,
        checkpoint_digest="0" * 64,
        backup_digest="1" * 64,
        source_digest="2" * 64,
        schema_digest="3" * 64,
        policy_digest="4" * 64,
        manifest_digest="5" * 64,
    )


@pytest.mark.parametrize("owner", OWNERS)
def test_owner_exports_current_bounded_noncredential_fragment(transactions, owner):
    bound = context(transactions)
    fragment = owner.export_restrictions(
        transactions,
        bound,
        accounts_fragment=AccountsRestore.export_restrictions(transactions, bound),
    )
    assert fragment["owner"] == owner.owner
    assert len(fragment_digest(bound, fragment)) == 64
    assert len(fragment["records"]) <= 2000
    if owner is AccountsRestore:
        accounts = [item for item in fragment["records"] if item["kind"] == "account"]
        assert accounts
        assert all(
            set(item)
            == {
                "kind",
                "accountId",
                "lifecycleState",
                "active",
                "verified",
                "authorityRevision",
                "lifecycleRevision",
                "credentialDigest",
            }
            for item in accounts
        )
        assert all(len(item["credentialDigest"]) == 64 for item in accounts)


@pytest.mark.parametrize("owner", OWNERS)
def test_restore_owner_functions_cannot_mutate_live_runtime(transactions, owner):
    bound = context(transactions)
    fragment = owner.export_restrictions(
        transactions,
        bound,
        accounts_fragment=AccountsRestore.export_restrictions(transactions, bound),
    )
    # Source realms intentionally withhold public restore-guard privileges too.
    # Either owner gate must deny with PostgreSQL's authorization error class.
    with pytest.raises(InsufficientPrivilege):
        owner.reconcile_restore(transactions, fragment, bound)


def test_owner_export_rejects_other_run_before_store_access(transactions):
    bound = replace(context(transactions), run_id="docsuri-u2-" + "f" * 16)
    with pytest.raises(ValueError, match="run mismatch"):
        AccountsRestore.export_restrictions(transactions, bound)
