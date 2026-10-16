import pytest

from backend.u4_policy import ResearchPolicy


@pytest.mark.parametrize("field", ["upload_bytes", "queue_depth", "retries", "lease_seconds"])
def test_unbounded_or_zero_allocation_refused(field):
    with pytest.raises(ValueError, match="finite positive"):
        ResearchPolicy(**{field: 0})


def test_only_synthetic_serial_profile_enabled():
    for values in ({"synthetic_only": False}, {"concurrency": 2}):
        with pytest.raises(ValueError):
            ResearchPolicy(**values)


def test_private_material_stays_policy_suspended():
    policy = ResearchPolicy()
    assert not policy.durable_drafts and not policy.private_attachments
    assert policy.reference() == {"policyId": "u4-synthetic-research", "revision": "1"}
