"""`ExportPolicy`: the NFR4.10 operating values and §9.1 budgets as finite positive
integers, its reference, and the refusals of the real activation policy (BR8.2, BR8.3)."""

from dataclasses import FrozenInstanceError, fields

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


# The thirteen NFR4.10 rows, keyed by their row names, each to the fields and the
# approved values it fixes (security-requirements.md, NFR4.10).
NFR4_10_ROWS = {
    "Write attempt deadline": (("write_deadline_seconds", 90),),
    "Read request timeout": (("read_timeout_seconds", 30),),
    "Settling wait before the first check of an unclear export": (
        ("settling_wait_seconds", 180),
    ),
    "Check schedule for an unclear export": (
        ("check_offsets_seconds", (180, 600, 1800)),
        ("check_hourly_seconds", 3600),
        ("check_hourly_until_seconds", 21600),
        ("check_late_interval_seconds", 10800),
        ("check_total_seconds", 86400),
    ),
    "Rate-limit retries for a write": (
        ("rate_limit_max_attempts", 4),
        ("rate_limit_window_seconds", 600),
    ),
    "Read retries": (("read_retries", 3),),
    "Client-side pace per connection": (("pace_interval_ms", 500),),
    "Could-not-check wait for an accepted export": (("could_not_check_wait_seconds", 86400),),
    "Abandoned request detection": (("orphan_after_seconds", 900),),
    "Clock margin for finding exported pages": (("clock_margin_seconds", 300),),
    "Per-owner limits": (
        ("in_flight_per_owner", 1),
        ("binds_per_window", 20),
        ("binds_window_seconds", 3600),
    ),
    "Rendered copy retention": (("preview_retention_days", 7),),
    "Response size cap": (("response_cap_bytes", 2_000_000),),
}


def test_the_synthetic_policy_holds_the_approved_operating_values():
    policy = SYNTHETIC_EXPORT
    assert len(NFR4_10_ROWS) == 13
    known = {item.name for item in fields(ExportPolicy)}
    for row, checks in NFR4_10_ROWS.items():
        for name, value in checks:
            assert name in known, row
            assert getattr(policy, name) == value, (row, name)
    assert (policy.pending_takeover_seconds, policy.synthetic_only) == (120, True)
    assert policy.reference() == {"policyId": "u6-synthetic-export", "revision": "1"}


def test_the_read_budgets_the_gates_and_the_bounds_are_the_approved_values():
    policy = SYNTHETIC_EXPORT
    assert (policy.token_check_budget_seconds, policy.listing_budget_seconds) == (30, 30)
    assert (policy.page_read_budget_seconds, policy.read_back_budget_seconds) == (30, 60)
    assert policy.scan_budget_seconds == 300
    assert (policy.interactive_per_process, policy.interactive_per_connection) == (2, 1)
    assert (policy.key_lock_retry_ms, policy.key_lock_wait_ms) == (100, 5000)
    assert policy.token_max_length == 512
    assert (policy.pass_batch, policy.housekeeping_batch, policy.history_page_max) == (10, 50, 20)
    assert policy.read_timeout_seconds <= policy.page_read_budget_seconds


def test_the_policy_is_frozen_and_its_reference_is_a_fresh_copy():
    policy = ExportPolicy()
    with pytest.raises(FrozenInstanceError):
        policy.write_deadline_seconds = 1
    with pytest.raises(FrozenInstanceError):
        policy.revision = "2"
    with pytest.raises(FrozenInstanceError):
        policy.policy_id = "other"
    reference = policy.reference()
    reference["revision"] = "9"
    assert policy.reference() == {"policyId": "u6-synthetic-export", "revision": "1"}
    assert hash(SYNTHETIC_EXPORT) == hash(ExportPolicy())


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
    ("overrides", "match"),
    [
        ({"check_offsets_seconds": ()}, "finite positive"),
        ({"check_offsets_seconds": (600, 180)}, "strictly increase"),
        ({"check_offsets_seconds": (180, 180)}, "strictly increase"),
        ({"check_hourly_until_seconds": 1800}, "check schedule phases"),
        ({"check_total_seconds": 3600}, "check schedule phases"),
        ({"read_timeout_seconds": 31}, "read budget"),
        ({"key_lock_retry_ms": 6000}, "waiting lock"),
        ({"history_page_max": 21}, "history pages"),
        ({"policy_id": ""}, "policy reference"),
    ],
)
def test_inconsistent_values_are_refused(overrides, match):
    with pytest.raises(ValueError, match=match):
        ExportPolicy(**overrides)


def test_a_small_strictly_increasing_schedule_is_accepted():
    policy = ExportPolicy(
        check_offsets_seconds=(1, 2, 3),
        check_hourly_until_seconds=4,
        check_late_interval_seconds=5,
        check_total_seconds=5,
    )
    assert policy.check_offsets_seconds == (1, 2, 3)
    assert policy.check_hourly_until_seconds == 4


def test_the_real_policy_needs_its_activation_destination_and_evidence():
    policy = real_activation_export(
        activation_destination_id=DESTINATION, free_terms_reference=EVIDENCE
    )
    assert REAL_ACTIVATION_EXPORT is real_activation_export
    assert policy.synthetic_only is False
    assert policy.activation_destination_id == DESTINATION
    assert policy.reference() == {"policyId": "u6-real-activation", "revision": "1"}
    differing = {
        item.name
        for item in fields(ExportPolicy)
        if getattr(policy, item.name) != getattr(SYNTHETIC_EXPORT, item.name)
    }
    assert differing == {"policy_id", "activation_destination_id", "free_terms_reference"}
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
