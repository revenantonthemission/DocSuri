"""Builders shared by the operator-only real composition's tests (plan Step 35, decision
L3-1): `component/test_real_activation.py`, `component/test_real_host_binding.py` and
`component/test_cancellation_origin.py`, moved unchanged from `test_real_composition.py`.

Fake transport and fake credentials only; nothing here contacts a provider, and no
check built on it is evidence of external delivery.
"""

import datetime as dt
from types import SimpleNamespace

from backend.u5_real_delivery import parse_activation

PUBLIC = "https://unsubscribe.fixture.invalid"
FAKE_KEY = "re_fakeCredentialNeverReal_0123456789"
ENVIRON = {"EMAIL_PROVIDER": "resend", "RESEND_API_KEY": FAKE_KEY}
NOW = dt.datetime(2026, 10, 19, 3, 0, tzinfo=dt.UTC)


def profile(tmp_path=None):
    return SimpleNamespace(
        run_id="docsuri-u5-0123456789abcdef",
        realm="topics-digests",
        origin="https://127.0.0.1:18089",
        expires_at=(NOW + dt.timedelta(hours=20)).timestamp(),
        root=tmp_path,
    )


def activation_value(**changes):
    value = {
        "runId": "docsuri-u5-0123456789abcdef",
        "sender": "no-reply@docsuri.fixture.invalid",
        "permittedRecipient": "owner@fixture.invalid",
        "unsubscribeOrigin": PUBLIC,
        "capabilityExpiresAt": (NOW + dt.timedelta(hours=12)).isoformat(),
        "freePlanVerified": True,
        "unsubscribeEndpointVerified": True,
    }
    value.update(changes)
    return value


def activation(**changes):
    return parse_activation(activation_value(**changes), profile(), now=NOW)


class FakeClient:
    def __init__(self, response):
        self.response, self.calls = response, []

    def __call__(self, **kwargs):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.response


def fake_transactions():
    return SimpleNamespace(profile=profile())
