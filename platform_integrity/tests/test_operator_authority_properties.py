"""Exact current-source scope invariants; native login/locking lives in the PostgreSQL tests."""

from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st
from run_support import plans

from docsuri_platform_integrity.adapters.operator_authority import check_source
from docsuri_platform_integrity.contracts.codec import canonical, digest
from docsuri_platform_integrity.contracts.models import ApprovalBinding, ValidityWindow


@given(plan=plans(), field=st.sampled_from([
    "actor", "purpose", "target", "namespace", "incarnation", "plan", "artifact", "policy",
    "revision", "revoked",
]))
def test_current_source_must_match_every_bound_authority_dimension(plan, field):
    binding = ApprovalBinding(
        approval_id="approval", actor="operator", purpose="run", target=plan.target,
        plan=digest(canonical(plan.model_dump(mode="json"))), artifact=plan.artifact_digest,
        policy=plan.policy_digest, authority_revision="1",
        validity=ValidityWindow(valid_from="0", valid_until="10"),
    )
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    row = (binding.actor, binding.purpose, binding.target.target_id, binding.target.namespace,
           binding.target.incarnation, binding.plan, binding.artifact, binding.policy, 1,
           epoch, epoch + timedelta(microseconds=10), False)
    assert check_source(binding, row, lambda: (4, 6), purpose="run") == (4, 6)
    indices = {name: i for i, name in enumerate((
        "actor", "purpose", "target", "namespace", "incarnation", "plan", "artifact", "policy",
        "revision", "valid_from", "valid_until", "revoked",
    ))}
    changed = list(row)
    replacement = {"revoked": True, "revision": 2}.get(field, "changed")
    changed[indices[field]] = replacement
    with pytest.raises(PermissionError):
        check_source(binding, tuple(changed), lambda: (4, 6), purpose="run")
