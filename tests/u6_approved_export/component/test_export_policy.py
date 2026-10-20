"""`ExportPolicy`: the NFR4.10 operating values and §9.1 budgets as finite positive
integers, its reference, and the refusals of the real activation policy (BR8.2, BR8.3)."""

from dataclasses import fields

import pytest
from backend.u6_policy import (
    REAL_ACTIVATION_EXPORT,
    REAL_MAXIMA,
    REAL_MINIMA,
    SYNTHETIC_EXPORT,
    ExportPolicy,
    real_activation_export,
)

DESTINATION = "0123456789abcdef0123456789abcdef"
EVIDENCE = "notion-free:2026-10-01:" + "a" * 64
TEXT = {"policy_id", "revision", "activation_destination_id", "free_terms_reference"}


def real(**overrides) -> ExportPolicy:
    return ExportPolicy(
        policy_id="u6-real-activation",
        activation_destination_id=DESTINATION,
        free_terms_reference=EVIDENCE,
        **overrides,
    )


def test_the_synthetic_policy_holds_the_approved_operating_values():
    policy = SYNTHETIC_EXPORT
    assert (policy.write_deadline_seconds, policy.read_timeout_seconds) == (90, 30)
    assert (policy.token_check_budget_seconds, policy.listing_budget_seconds) == (30, 30)
    assert (policy.read_back_budget_seconds, policy.scan_budget_seconds) == (60, 300)
    assert (policy.settling_wait_seconds, policy.check_offsets_seconds) == (180, (180, 600, 1800))
    assert (policy.rate_limit_window_seconds, policy.rate_limit_max_attempts) == (600, 4)
    assert (policy.read_retries, policy.pace_interval_ms) == (3, 500)
    assert (policy.could_not_check_wait_seconds, policy.orphan_after_seconds) == (86400, 900)
    assert (policy.in_flight_per_owner, policy.binds_per_window) == (1, 20)
    assert (policy.preview_retention_days, policy.response_cap_bytes) == (7, 2_000_000)
    assert (policy.interactive_per_process, policy.interactive_per_connection) == (2, 1)
    assert policy.pending_takeover_seconds == 120 and policy.synthetic_only is True
    assert policy.reference() == {"policyId": "u6-synthetic-export", "revision": "1"}


@pytest.mark.parametrize(
    "name", [item.name for item in fields(ExportPolicy) if item.name not in TEXT]
)
@pytest.mark.parametrize("value", [0, -1, 1.5, True, "1"])
def test_every_operating_value_must_be_a_finite_positive_integer(name, value):
    if name == "check_offsets_seconds":
        value = (value,)
    with pytest.raises(ValueError, match=name):
        ExportPolicy(**{name: value})


@pytest.mark.parametrize(
    "overrides",
    [
        {"check_offsets_seconds": ()},
        {"check_offsets_seconds": (600, 180)},
        {"check_offsets_seconds": (180, 180)},
        {"check_hourly_until_seconds": 1800},
        {"check_total_seconds": 3600},
        {"read_timeout_seconds": 31},
        {"key_lock_retry_ms": 6000},
        {"history_page_max": 21},
        {"policy_id": ""},
    ],
)
def test_inconsistent_values_are_refused(overrides):
    with pytest.raises(ValueError):
        ExportPolicy(**overrides)


def test_the_real_policy_needs_its_activation_destination_and_evidence():
    policy = real_activation_export(
        activation_destination_id=DESTINATION, free_terms_reference=EVIDENCE
    )
    assert REAL_ACTIVATION_EXPORT is real_activation_export
    assert policy.synthetic_only is False
    assert policy.activation_destination_id == DESTINATION
    assert policy.reference() == {"policyId": "u6-real-activation", "revision": "1"}
    for destination in (None, "0123", DESTINATION.upper(), DESTINATION + "0"):
        with pytest.raises(ValueError, match="destination"):
            ExportPolicy(activation_destination_id=destination, free_terms_reference=EVIDENCE)
    for evidence in (None, "", "with space", "x" * 257):
        with pytest.raises(ValueError, match="evidence"):
            ExportPolicy(activation_destination_id=DESTINATION, free_terms_reference=evidence)


@pytest.mark.parametrize("name,limit", sorted(REAL_MAXIMA.items()))
def test_the_real_policy_refuses_values_above_the_free_limits(name, limit):
    assert getattr(real(**{name: limit}), name) == limit
    with pytest.raises(ValueError, match=name):
        real(**{name: limit + 1})


@pytest.mark.parametrize("name,limit", sorted(REAL_MINIMA.items()))
def test_the_real_policy_refuses_values_faster_than_the_free_limits(name, limit):
    if name == "write_deadline_seconds":
        assert getattr(real(**{name: limit}), name) == limit
    with pytest.raises(ValueError, match=name):
        real(**{name: limit - 1})


def test_a_synthetic_policy_may_be_smaller_for_tests():
    policy = ExportPolicy(
        pace_interval_ms=1, settling_wait_seconds=1, rate_limit_window_seconds=1, binds_per_window=1
    )
    assert policy.synthetic_only is True and policy.pace_interval_ms == 1
