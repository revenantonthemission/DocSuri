"""Real Ed25519 verification with synthetic owner/key observations; no host key provisioning."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Barrier, Event

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from evidence_support import SUBJECT, request, result, selected

from docsuri_platform_integrity.adapters.authority import (
    CurrentEvidenceVerifier,
    CurrentReadAuthority,
    EvidenceVerificationKey,
    ReadGrant,
)
from docsuri_platform_integrity.application.evidence import EvidenceService
from docsuri_platform_integrity.contracts.codec import sign
from docsuri_platform_integrity.contracts.models import GateVerdict, ValidityWindow
from docsuri_platform_integrity.domain.gate import pending_selection, reserve_selection


@pytest.fixture
def material():
    reservation = reserve_selection(request(), None, expected_revision="0")
    record = result(reservation)
    private = Ed25519PrivateKey.generate()
    key = EvidenceVerificationKey(
        "test-key", private.public_key(), frozenset({SUBJECT.subject}), "trust-1",
        ValidityWindow(valid_from="0", valid_until="1000"), False,
    )
    envelope = sign(
        record.model_dump(mode="json"), kind="evidence", purpose="attest",
        key_id=key.key_id, key=private,
    )
    return record, private, key, envelope


def service_for(record, verifier, reader=None):
    class Reader:
        def snapshot(self, subject):
            return (selected(record),), (record,)

    grant = ReadGrant("cert", frozenset({SUBJECT.subject}), 1000)
    return EvidenceService(
        reader or Reader(), CurrentReadAuthority(lambda _: grant, lambda: (100, 100)),
        lambda: (100, 100), {SUBJECT.subject: (SUBJECT, ("schema",))}, current=verifier,
    )


def test_key_revocation_and_missing_trust_are_observed_on_every_read(material):
    record, _, key, envelope = material
    live = {key.key_id: key}
    verifier = CurrentEvidenceVerifier(
        lambda _: SUBJECT, lambda _: envelope, lambda identity, _: live.get(identity),
    )
    service = service_for(record, verifier)
    assert service.read("cert", SUBJECT.subject).eligible
    live[key.key_id] = replace(key, revoked=True, revision="trust-2")
    assert service.read("cert", SUBJECT.subject).verdict == GateVerdict.BLOCKED
    live.clear()
    assert service.read("cert", SUBJECT.subject).verdict == GateVerdict.INCOMPLETE


def test_unknown_revocation_is_not_coerced_to_an_active_key(material):
    _, _, key, _ = material
    with pytest.raises(ValueError):
        replace(key, revoked=None)


@pytest.mark.parametrize("kind", ["purpose", "payload", "scope", "signature"])
def test_invalid_signatures_or_key_scope_do_not_become_evidence(material, kind):
    record, private, key, envelope = material
    if kind == "purpose":
        envelope = sign(
            record.model_dump(mode="json"), kind="evidence", purpose="approve",
            key_id=key.key_id, key=private,
        )
    elif kind == "payload":
        record = record.model_copy(update={"reasons": ("PRIVATE-SENTINEL",)})
    elif kind == "scope":
        key = replace(key, subjects=frozenset({"other-subject"}))
    else:
        envelope = {**envelope, "signature": "invalid"}
    verifier = CurrentEvidenceVerifier(lambda _: SUBJECT, lambda _: envelope, lambda *_: key)
    evaluated = service_for(record, verifier).read("cert", SUBJECT.subject)
    assert evaluated.verdict == GateVerdict.BLOCKED
    assert "PRIVATE-SENTINEL" not in evaluated.model_dump_json()


def test_owner_source_error_is_unknown_and_does_not_leak_private_error(material):
    record, _, key, _ = material

    def unavailable(_):
        raise OSError("PRIVATE-SENTINEL /internal/path credential=value")

    verifier = CurrentEvidenceVerifier(lambda _: SUBJECT, unavailable, lambda *_: key)
    evaluated = service_for(record, verifier).read("cert", SUBJECT.subject)
    assert evaluated.verdict == GateVerdict.INCOMPLETE
    assert "PRIVATE-SENTINEL" not in evaluated.model_dump_json()


def test_new_pending_head_during_trust_lookup_invalidates_observation(material):
    record, _, key, envelope = material
    state = {"head": selected(record)}

    class Reader:
        def snapshot(self, subject):
            return (state["head"],), (record,) if state["head"].state == "RESOLVED" else ()

    def lookup(*_):
        state["head"] = pending_selection(reserve_selection(
            request("new-verification"), state["head"], expected_revision="1"
        ))
        return key

    verifier = CurrentEvidenceVerifier(lambda _: SUBJECT, lambda _: envelope, lookup)
    evaluated = service_for(record, verifier, Reader()).read("cert", SUBJECT.subject)
    assert not evaluated.eligible


def test_key_change_during_final_store_read_cannot_reuse_earlier_trust(material):
    record, _, key, envelope = material
    state = {"key": key, "reads": 0}

    class Reader:
        def snapshot(self, subject):
            state["reads"] += 1
            if state["reads"] == 2:
                state["key"] = replace(key, revoked=True, revision="trust-2")
            return (selected(record),), (record,)

    verifier = CurrentEvidenceVerifier(
        lambda _: SUBJECT, lambda _: envelope, lambda *_: state["key"],
    )
    assert not service_for(record, verifier, Reader()).read("cert", SUBJECT.subject).eligible


def test_inflight_workers_keep_the_eight_request_admission(material):
    record, _, _, _ = material
    entered, release = Barrier(9), Event()

    class Reader:
        def snapshot(self, subject):
            entered.wait(timeout=5)
            assert release.wait(timeout=5)
            return (selected(record),), (record,)

    service = service_for(record, None, Reader())
    with ThreadPoolExecutor(max_workers=8) as pool:
        pending = [pool.submit(service.read, "cert", SUBJECT.subject) for _ in range(8)]
        try:
            entered.wait(timeout=5)
            with pytest.raises(OSError, match="busy"):
                service.read("cert", SUBJECT.subject)
        finally:
            release.set()
        assert all(not future.result(timeout=5).eligible for future in pending)


def test_expired_budget_does_not_start_more_owner_lookups(material, monkeypatch):
    from docsuri_platform_integrity.adapters import authority

    record, _, key, envelope = material
    elapsed = [0.0]
    calls = []
    monkeypatch.setattr(authority, "monotonic", lambda: elapsed[0])

    def observe(_):
        elapsed[0] = 3.0
        return SUBJECT

    def lookup(*_):
        calls.append("lookup")
        return key

    verifier = CurrentEvidenceVerifier(observe, lambda _: envelope, lookup)
    with pytest.raises(TimeoutError):
        verifier.inspect(SUBJECT, (record,), deadline=2.5)
    assert calls == []
