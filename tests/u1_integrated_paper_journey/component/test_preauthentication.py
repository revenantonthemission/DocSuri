"""Signed anonymous context faults; real credential authority is tested separately."""

import hashlib
import hmac
from types import SimpleNamespace

import pytest

from backend.modules.accounts.preauthentication import Preauthentication

pytestmark = pytest.mark.u1_component


def entry(monkeypatch):
    monkeypatch.setattr("backend.modules.accounts.preauthentication.time.time", lambda: 1000)
    profile = SimpleNamespace(
        run_id="owned",
        database_name="diagnostic",
        origin="https://127.0.0.1:18039",
        expires_at=5000,
    )
    return SimpleNamespace(
        transactions=SimpleNamespace(profile=profile),
        verifier=lambda purpose, value: hmac.new(
            b"diagnostic-key", (purpose + "\0" + value).encode(), hashlib.sha256
        ).hexdigest(),
    )


def test_fresh_context_recovers_exact_csrf_and_does_not_accept_another_context(monkeypatch):
    service = entry(monkeypatch)
    first = Preauthentication(service).issue()
    restored = Preauthentication(service).read(first.cookie, csrf=first.csrf)
    assert restored == first
    second = Preauthentication(service).issue()
    assert first.flow != second.flow
    with pytest.raises(PermissionError):
        Preauthentication(service).read(first.cookie, csrf=second.csrf)


@pytest.mark.parametrize("mutation", ["signature", "expiry", "realm", "origin"])
def test_changed_context_or_binding_refuses(monkeypatch, mutation):
    service = entry(monkeypatch)
    context = Preauthentication(service).issue()
    cookie = context.cookie
    if mutation == "signature":
        cookie = cookie[:-1] + ("a" if cookie[-1] != "a" else "b")
    elif mutation == "expiry":
        cookie = cookie.replace(".1900.", ".4900.")
    elif mutation == "realm":
        service.transactions.profile.database_name = "journey"
    else:
        service.transactions.profile.origin = "https://other.invalid"
    with pytest.raises(PermissionError):
        Preauthentication(service).read(cookie)


def test_expired_future_and_oversized_contexts_refuse(monkeypatch):
    service = entry(monkeypatch)
    context = Preauthentication(service).issue()
    monkeypatch.setattr("backend.modules.accounts.preauthentication.time.time", lambda: 1900)
    with pytest.raises(PermissionError):
        Preauthentication(service).read(context.cookie)
    monkeypatch.setattr("backend.modules.accounts.preauthentication.time.time", lambda: 999)
    with pytest.raises(PermissionError):
        Preauthentication(service).read(context.cookie)
    with pytest.raises(PermissionError):
        Preauthentication(service).read("x" * 257)


def test_unicode_signature_and_csrf_are_denied_without_comparison_type_error(monkeypatch):
    service = entry(monkeypatch)
    context = Preauthentication(service).issue()
    with pytest.raises(PermissionError):
        Preauthentication(service).read(context.cookie.rsplit(".", 1)[0] + "." + "한" * 64)
    with pytest.raises(PermissionError):
        Preauthentication(service).read(context.cookie, csrf="한" * 64)
