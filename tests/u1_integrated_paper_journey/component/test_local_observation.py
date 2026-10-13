"""Bounded owner observation probes and truthful readiness (component boundary)."""

from __future__ import annotations

from pathlib import Path
import os

import pytest

from backend import local_observation
from backend.local_profile import LocalProfile
from backend.transactions import OwnerTransactions

pytestmark = pytest.mark.u1_component

OWNERS = (
    "accounts",
    "corpus",
    "discovery",
    "library",
    "personalization",
    "usage",
    "assistance",
    "operations",
)


def profile() -> LocalProfile:
    return LocalProfile.load(Path(os.environ["DOCSURI_U1_ENVIRONMENT_FILE"]))


def test_every_installed_owner_probe_reports_bounded_counts():
    transactions = OwnerTransactions(profile(), process="observation")
    try:
        observed = local_observation.observe_all(transactions)
        assert set(observed) == set(OWNERS)
        for owner, row in observed.items():
            assert row["capability"] == owner
            assert row["disposition"] == "available", (owner, row)
            assert row["expiresAt"] > row["observedAt"]
            assert row["evidence"], owner
            assert all(type(value) is int for value in row["evidence"].values())
    finally:
        transactions.close()


def test_closed_owner_store_observation_never_raises():
    transactions = OwnerTransactions(profile(), process="observation")
    assert local_observation.probe_owner(transactions, "accounts")["disposition"] == "available"
    transactions.close()
    observed = local_observation.probe_owner(transactions, "accounts")
    assert observed["disposition"] == "unavailable"
    assert observed["evidence"] == {"reasonKey": "observation.storeUnavailable"}


def test_readiness_without_a_readable_operations_store_is_unknown():
    transactions = OwnerTransactions(profile(), process="observation")
    transactions.close()
    report = local_observation.readiness(transactions, {"accounts", "operations"})
    assert report["ready"] is False
    assert report["missing"] == ["accounts", "operations"]
    assert all(row["status"] == "unknown" for row in report["observations"])
    assert all(row["reasonKey"] == "observation.storeUnavailable" for row in report["observations"])
