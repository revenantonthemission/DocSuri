"""Operator-only real composition, its host binding (`backend/u5_host.py` with
`backend/u5_policy.py`) and the operator's outcome view (`scripts/u5_real_delivery.py`):
local and test profiles ignore ambient real configuration, capability labels follow the
adapter actually bound, the real policy's finite bounds, and the outcome view's receipt.

Fake transport and fake credentials only; no check here contacts a provider, and none
is evidence of external delivery. Moved unchanged from `test_real_composition.py`
(plan Step 35, decision L3-1); the shared builders are in `real_composition_kit.py`.
"""

import datetime as dt
from types import SimpleNamespace
from uuid import uuid4

import pytest
from backend.modules.accounts.integrations.digest_email import digest_mail_binding
from backend.u5_host import digest_capability, topics_contribution
from backend.u5_policy import REAL_DEMONSTRATION_TOPICS, SYNTHETIC_TOPICS, TopicsPolicy
from backend.u5_real_delivery import RealDeliveryRefused, real_mail, real_topics_factory

from tests.u5_topics_digests.real_composition_kit import (
    ENVIRON,
    FAKE_KEY,
    NOW,
    FakeClient,
    activation,
    fake_transactions,
)


def test_local_and_test_profiles_ignore_ambient_real_configuration(monkeypatch):
    monkeypatch.setenv("EMAIL_PROVIDER", "resend")
    monkeypatch.setenv("RESEND_API_KEY", FAKE_KEY)
    contribution = topics_contribution(fake_transactions(), SimpleNamespace(), None, None)
    assert contribution["delivery"].path_kind() == "local-sink"
    assert contribution["delivery"].recipient_scope() is None
    assert contribution["capabilities"][0]["modeIds"] == ["synthetic-only"]
    with pytest.raises(ValueError):
        digest_mail_binding(synthetic=True, client_factory=FakeClient(None))
    with pytest.raises(ValueError):
        digest_mail_binding(synthetic=True, provider="resend", configuration={"apiKey": "x"})
    real = real_mail(activation(), ENVIRON, client_factory=FakeClient(None))
    with pytest.raises(ValueError):
        topics_contribution(fake_transactions(), SimpleNamespace(), None, None, mail=real)


def test_capability_labels_follow_the_bound_adapter():
    synthetic = topics_contribution(fake_transactions(), SimpleNamespace(), None, None)
    assert synthetic["capabilities"][0] | {"policy": None} == {
        "id": "topics.digest",
        "state": "degraded",
        "modeIds": ["synthetic-only"],
        "languageIds": ["en", "ko"],
        "levelIds": ["standard"],
        "formatIds": ["email"],
        "policy": None,
    }
    mail = real_mail(activation(), ENVIRON, client_factory=FakeClient(None))
    real = real_topics_factory(activation(), mail)(
        fake_transactions(), SimpleNamespace(), None, None
    )
    record = real["capabilities"][0]
    assert record["modeIds"] == ["real-bounded"] and record["state"] == "degraded"
    assert record["policy"] == {"policyId": "u5-real-demonstration", "revision": "1"}
    assert real["delivery"].recipient_scope() == "owner@fixture.invalid"
    with pytest.raises(ValueError):
        digest_capability(SYNTHETIC_TOPICS, real["delivery"])
    with pytest.raises(ValueError):
        digest_capability(REAL_DEMONSTRATION_TOPICS, synthetic["delivery"])


def test_real_policy_is_one_send_and_thirty_day_retention():
    assert REAL_DEMONSTRATION_TOPICS.real_send_limit == 1
    assert REAL_DEMONSTRATION_TOPICS.real_evidence_retention_days == 30
    assert not REAL_DEMONSTRATION_TOPICS.synthetic_only
    for invalid in (
        {"synthetic_only": False, "real_send_limit": 1},
        {"synthetic_only": False, "real_send_limit": 1, "real_evidence_retention_days": 31},
        {"real_evidence_retention_days": 30},
        {"synthetic_only": False, "real_send_limit": 1, "real_evidence_retention_days": "30"},
    ):
        with pytest.raises(ValueError):
            TopicsPolicy(**invalid)
    with pytest.raises(RealDeliveryRefused):
        real_topics_factory(activation(), None, policy=SYNTHETIC_TOPICS)


def test_a_fixture_clock_binds_only_with_synthetic_delivery():
    """Plan Step 38, L3-1 (3): the host binding's fifth test. A fixture clock replaces
    the scheduler's clock in a synthetic composition and is refused beside real delivery,
    so a test clock can never move a real send's schedule."""

    def fixed():
        return NOW

    synthetic = topics_contribution(fake_transactions(), SimpleNamespace(), None, None, clock=fixed)
    assert synthetic["scheduler"]._now is fixed
    mail = real_mail(activation(), ENVIRON, client_factory=FakeClient(None))
    with pytest.raises(ValueError, match="fixture clock requires synthetic delivery"):
        topics_contribution(
            fake_transactions(),
            SimpleNamespace(),
            None,
            None,
            policy=REAL_DEMONSTRATION_TOPICS,
            mail=mail,
            unsubscribe=SimpleNamespace(),
            clock=fixed,
        )


def test_outcome_view_reports_receipt_and_its_digest():
    import hashlib

    from scripts.u5_real_delivery import outcome_view

    receipt = str(uuid4())
    base = {
        "id": uuid4(),
        "state": "sent",
        "window_start": dt.date(2026, 10, 13),
        "window_end": dt.date(2026, 10, 19),
        "observed_state": "sent",
        "reconciled_state": None,
        "failure_reason": None,
        "path_kind": "real",
        "attempted_at": NOW,
        "acknowledged_at": NOW,
        "transport_receipt": receipt,
        "evidence_retain_until": NOW + dt.timedelta(days=30),
        "evidence_expired_at": None,
    }
    view = outcome_view(base)
    assert view["sendLog"]["providerReceipt"] == receipt
    assert view["sendLog"]["providerReceiptSha256"] == hashlib.sha256(receipt.encode()).hexdigest()
    assert view["sendLog"]["evidenceExpired"] is False
    expired = outcome_view(dict(base, transport_receipt=None, evidence_expired_at=NOW))
    assert expired["sendLog"]["providerReceiptSha256"] is None
    assert expired["sendLog"]["evidenceExpired"] is True
    assert outcome_view(dict(base, path_kind=None, state="prepared"))["sendLog"] is None
