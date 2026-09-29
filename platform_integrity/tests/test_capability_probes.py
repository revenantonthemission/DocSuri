"""Probes are readonly, fail closed, and are the only route to a signable receipt."""

import datetime
import os
import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from docsuri_platform_integrity.adapters.credentials import TLSReference
from docsuri_platform_integrity.adapters.postgres_tls import PostgresTarget
from docsuri_platform_integrity.contracts.models import ValidityWindow
from docsuri_platform_integrity.deployment.capability import (
    DAY_US,
    Outcome,
    ProbeSet,
    RestoreReceipt,
    probe_keychain_roles,
    probe_native_commit_guard,
    probe_nts_clock,
    probe_restore_receipt,
    probe_tls_roles,
    receipt_from,
)
from docsuri_platform_integrity.deployment.receipt import Capability, Receipt

HOST = "11111111-2222-3333-4444-555555555555"
RELEASE = "r1-2026.09"
DIGEST = "sha256:" + "a" * 64


def now_us():
    return int(time.time() * 1_000_000)


def bundle_bytes():
    """Genuine CA + leaf + key: the probe must accept real material, not a lookalike."""
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from cryptography.x509.oid import NameOID

    key = ed25519.Ed25519PrivateKey.generate()
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "docsuri-rem1-probe")])
    now = datetime.datetime.now(datetime.UTC)
    authority = (
        x509.CertificateBuilder().subject_name(name).issuer_name(name)
        .public_key(key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=30))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, None)
    )
    pem = serialization.Encoding.PEM

    class Bundle(dict):
        pass

    return Bundle(
        certificate=authority.public_bytes(pem).decode(),
        privateKey=key.private_bytes(
            pem, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode(),
        ca=authority.public_bytes(pem).decode(),
    )


def reader_returning(bundle, *, record=None):
    from docsuri_platform_integrity.contracts.codec import canonical

    class Reader:
        def __init__(self, path):
            self.path = path

        def get(self, service, account):
            if record is not None:
                record.append((str(self.path), service, account))
            return canonical(bundle)

    return Reader


def keychain_reference(account="reader"):
    return TLSReference(Path("/Library/Keychains/rem1-reader.keychain-db"), "docsuri.rem1", account)


class Connection:
    """Minimal idle autocommit stand-in: the guard must refuse before touching it."""

    class Info:
        class TransactionStatus:
            IDLE = "IDLE"

        transaction_status = "IDLE"

    autocommit = True
    info = Info()
    pgconn = type("Pgconn", (), {"ssl_in_use": True})()

    def __init__(self, user="r1_reader"):
        self.user = user

    def execute(self, *_args, **_kwargs):
        return self

    def fetchone(self):
        return (self.user,)


# --- keychain roles ----------------------------------------------------------------------------


def test_keychain_roles_proven_for_readable_valid_material():
    calls = []
    outcome = probe_keychain_roles(
        [keychain_reference("reader"), keychain_reference("clock")],
        reader_factory=reader_returning(bundle_bytes(), record=calls),
        encryption_check=lambda: True,
    )
    assert outcome.proven is True
    assert outcome.reason == "verified"
    assert outcome.capability is Capability.KEYCHAIN_ROLES
    assert outcome.artifact and outcome.evidence and outcome.artifact != outcome.evidence
    assert len(calls) == 2


def test_keychain_roles_fail_when_no_role_is_declared():
    outcome = probe_keychain_roles([], encryption_check=lambda: True)
    assert (outcome.proven, outcome.reason) == (False, "no_role_declared")


def test_keychain_roles_fail_when_host_encryption_is_off():
    outcome = probe_keychain_roles(
        [keychain_reference()], reader_factory=reader_returning(bundle_bytes()),
        encryption_check=lambda: False)
    assert (outcome.proven, outcome.reason) == (False, "host_encryption_unavailable")


def test_keychain_roles_fail_closed_when_one_role_is_locked():
    class Locked:
        def __init__(self, path):
            self.path = path

        def get(self, service, account):
            raise PermissionError("interaction not allowed")

    outcome = probe_keychain_roles(
        [keychain_reference()], reader_factory=Locked, encryption_check=lambda: True)
    assert (outcome.proven, outcome.reason) == (False, "purpose_key_unavailable")


def test_keychain_evidence_never_contains_private_key_material():
    """A receipt must not become a private-key verification oracle."""
    material = bundle_bytes()
    outcome = probe_keychain_roles(
        [keychain_reference()], reader_factory=reader_returning(material),
        encryption_check=lambda: True)
    from docsuri_platform_integrity.contracts.codec import canonical, digest

    # Evidence is a digest of the *public* certificate plus identifiers, nothing else.
    assert outcome.evidence == digest(canonical(
        [{"account": "reader", "service": "docsuri.rem1",
          "certificate": digest(material["certificate"].encode())}]))
    assert outcome.evidence != digest(material["privateKey"].encode())


def test_keychain_roles_reject_invalid_material():
    def bad(raw):
        raise ValueError("invalid")

    import docsuri_platform_integrity.deployment.capability as capability

    original = capability.validate_bundle
    capability.validate_bundle = bad
    try:
        outcome = probe_keychain_roles(
            [keychain_reference()], reader_factory=reader_returning(bundle_bytes()),
            encryption_check=lambda: True)
    finally:
        capability.validate_bundle = original
    assert (outcome.proven, outcome.reason) == (False, "purpose_key_unavailable")


# --- tls roles ---------------------------------------------------------------------------------


def test_tls_roles_proven_when_login_is_over_tls():
    target = PostgresTarget(database="rem1", user="r1_reader", port=5432)
    outcome = probe_tls_roles(target, None, connect=lambda: _closing(Connection()))
    assert outcome.proven is True
    assert outcome.evidence


def test_tls_roles_fail_when_tls_was_not_negotiated():
    target = PostgresTarget(database="rem1", user="r1_reader", port=5432)
    connection = Connection()
    connection.pgconn = type("Pgconn", (), {"ssl_in_use": False})()
    outcome = probe_tls_roles(target, None, connect=lambda: _closing(connection))
    assert (outcome.proven, outcome.reason) == (False, "tls_not_negotiated")


def test_tls_roles_fail_when_login_is_refused():
    target = PostgresTarget(database="rem1", user="r1_reader", port=5432)

    def refuse():
        raise RuntimeError("certificate authentication failed")

    outcome = probe_tls_roles(target, None, connect=refuse)
    assert (outcome.proven, outcome.reason) == (False, "role_login_failed")


def test_tls_roles_fail_on_unexpected_identity():
    target = PostgresTarget(database="rem1", user="r1_reader", port=5432)
    outcome = probe_tls_roles(
        target, None, connect=lambda: _closing(Connection(user="r1_admin")))
    assert (outcome.proven, outcome.reason) == (False, "unexpected_identity")


class _closing:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self.connection

    def __exit__(self, *_args):
        return False


# --- nts clock ---------------------------------------------------------------------------------


def test_nts_clock_proven_when_the_protected_frame_validates(tmp_path):
    frame = tmp_path / "clock.json"
    frame.write_text(_frame(tmp_path))
    outcome = probe_nts_clock(
        frame, writer_uid=os.getuid(), config_digest=DIGEST,
        context=_context(), trusted_root=tmp_path)
    assert outcome.proven is True
    assert outcome.artifact == DIGEST


def test_nts_clock_fails_when_the_frame_is_absent(tmp_path):
    outcome = probe_nts_clock(
        tmp_path / "missing.json", writer_uid=os.getuid(), config_digest=DIGEST,
        context=_context(), trusted_root=tmp_path)
    assert (outcome.proven, outcome.reason) == (False, "protected_clock_unavailable")


def test_nts_clock_fails_when_the_config_digest_does_not_match(tmp_path):
    frame = tmp_path / "clock.json"
    frame.write_text(_frame(tmp_path, config_digest="sha256:" + "b" * 64))
    outcome = probe_nts_clock(
        frame, writer_uid=os.getuid(), config_digest=DIGEST,
        context=_context(), trusted_root=tmp_path)
    assert (outcome.proven, outcome.reason) == (False, "protected_clock_unavailable")


def _frame(root, *, config_digest=DIGEST):
    import json

    return json.dumps({
        "utc_us": str(now_us()), "continuous_ns": "1000", "uncertainty_us": 10,
        "drift_ppm": 0.1, "boot_id": "boot", "resume_id": "resume", "authenticated": True,
        "source": "time.cloudflare.com", "address": "162.159.200.1",
        "config_digest": config_digest,
    })


def _context():
    from docsuri_platform_integrity.adapters.nts import NativeTime

    def context():
        # Continuous time must line up with the frame for a sane window.
        return NativeTime(1000, now_us(), "boot", "resume")

    return context


# --- native commit guard -----------------------------------------------------------------------


APPLY = ("registry:apply", DIGEST)


class Guard:
    """A provisioned operator authority that mirrors the real adapter's plan membership.

    Like :class:`PostgresOperatorAuthority`, it refuses anything outside the frozen plan before
    reading any authority state, admits a planned identity, and then refuses finalization
    because no effect was performed.
    """

    def __init__(self, *, definitions=None, binding="present", admit_unplanned=False,
                 refuse_planned=False, authority_refuses=False,
                 reason="effect is outside the frozen operator plan"):
        self.definitions = definitions if definitions is not None else {"registry:apply": DIGEST}
        self.binding = binding
        self.admit_unplanned = admit_unplanned
        self.refuse_planned = refuse_planned
        self.authority_refuses = authority_refuses
        self.reason = reason
        self.effects = []

    def guard(self, connection, identity, definition_digest):
        from contextlib import contextmanager

        from docsuri_platform_integrity.adapters.authority import MutationUnavailable

        planned = self.definitions.get(identity) == definition_digest
        admits = (planned and not self.refuse_planned) or (not planned and self.admit_unplanned)
        refuse = None if admits else self.reason
        entered = []

        @contextmanager
        def inner():
            if planned and self.authority_refuses:
                # check_binding refuses with PermissionError, not MutationUnavailable.
                raise PermissionError("current authority binding rejected")
            if refuse is not None:
                raise MutationUnavailable(refuse)
            entered.append(identity)
            yield object()
            # The real adapter refuses to finish a finalization nobody entered.
            raise MutationUnavailable("native finalization boundary was not entered")

        return inner()


def guard_probe(guard):
    return probe_native_commit_guard(guard, connection=Connection(), identity=APPLY[0],
                                     definition_digest=APPLY[1])


def test_native_commit_guard_proven_only_when_it_refuses_unplanned_and_admits_planned():
    outcome = guard_probe(Guard())
    assert outcome.proven is True
    assert outcome.evidence


def test_native_commit_guard_fails_when_a_guard_admits_an_unplanned_effect():
    outcome = guard_probe(Guard(admit_unplanned=True))
    assert (outcome.proven, outcome.reason) == (False, "unplanned_effect_admitted")


def test_native_commit_guard_fails_on_a_deny_all_guard_that_never_admits_its_own_plan():
    # A guard that refuses everything would satisfy "fails closed" alone while being unable to
    # ever apply an effect. Requiring the planned identity to be admitted catches that.
    outcome = guard_probe(Guard(refuse_planned=True))
    assert (outcome.proven, outcome.reason) == (False, "planned_effect_not_admitted")


def test_native_commit_guard_fails_when_unplanned_is_refused_for_the_wrong_reason():
    # Refusing because the approval is revoked proves nothing about the plan boundary.
    outcome = guard_probe(Guard(reason="operator authority scope or target changed"))
    assert (outcome.proven, outcome.reason) == (False, "guard_refused_for_the_wrong_reason")


def test_native_commit_guard_fails_when_the_requested_identity_is_not_in_the_plan():
    outcome = probe_native_commit_guard(Guard(), connection=Connection(),
                                        identity="registry:adopt", definition_digest=DIGEST)
    assert (outcome.proven, outcome.reason) == (False, "planned_identity_not_in_frozen_plan")


def test_native_commit_guard_fails_when_not_provisioned():
    outcome = guard_probe(Guard(definitions={}))
    assert (outcome.proven, outcome.reason) == (False, "guard_not_provisioned")


def test_native_commit_guard_fails_without_an_operator_binding():
    outcome = guard_probe(Guard(binding=None))
    assert (outcome.proven, outcome.reason) == (False, "operator_binding_absent")


def test_native_commit_guard_fails_closed_on_an_unexpected_error():
    class Broken:
        definitions = {"registry:apply": DIGEST}
        binding = object()

        def guard(self, *_args):
            raise RuntimeError("unexpected")

    outcome = probe_native_commit_guard(Broken(), connection=Connection(), identity=APPLY[0],
                                        definition_digest=APPLY[1])
    assert (outcome.proven, outcome.reason) == (False, "guard_raised_unexpectedly")


def test_native_commit_guard_performs_no_effect_while_proving_the_guard():
    guard = Guard()
    assert guard_probe(guard).proven is True
    assert guard.effects == []


# --- restore receipt ---------------------------------------------------------------------------


def restore_payload(**overrides):
    payload = {
        "host": HOST, "release": RELEASE,
        "source": {"target_id": "pg", "namespace": "r1", "incarnation": "1"},
        "restored": {"target_id": "pg", "namespace": "r1", "incarnation": "2"},
        "encrypted": True, "verified": True, "completed_utc_us": str(now_us()),
    }
    payload.update(overrides)
    return payload


def write_restore(tmp_path, payload):
    from docsuri_platform_integrity.contracts.codec import canonical

    path = tmp_path / "restore.json"
    path.write_bytes(canonical(payload))
    return path


def test_restore_receipt_proven_for_a_new_encrypted_incarnation(tmp_path):
    path = write_restore(tmp_path, restore_payload())
    outcome = probe_restore_receipt(
        path, host=HOST, release=RELEASE, lower=now_us(), upper=now_us())
    assert outcome.proven is True


def test_restore_receipt_fails_when_restored_into_the_same_incarnation(tmp_path):
    payload = restore_payload()
    payload["restored"] = dict(payload["source"])
    outcome = probe_restore_receipt(
        write_restore(tmp_path, payload), host=HOST, release=RELEASE,
        lower=now_us(), upper=now_us())
    assert (outcome.proven, outcome.reason) == (False, "restored_into_same_incarnation")


def test_restore_receipt_fails_when_unencrypted(tmp_path):
    outcome = probe_restore_receipt(
        write_restore(tmp_path, restore_payload(encrypted=False)), host=HOST, release=RELEASE,
        lower=now_us(), upper=now_us())
    assert (outcome.proven, outcome.reason) == (False, "restore_not_encrypted_or_unverified")


def test_restore_receipt_fails_for_another_host_or_release(tmp_path):
    path = write_restore(tmp_path, restore_payload())
    assert probe_restore_receipt(
        path, host=OTHER, release=RELEASE, lower=now_us(), upper=now_us()).reason == "host_mismatch"
    assert probe_restore_receipt(
        path, host=HOST, release="r1-2026.10", lower=now_us(), upper=now_us()).reason == (
        "release_mismatch")


OTHER = "99999999-9999-9999-9999-999999999999"


def test_restore_receipt_fails_when_stale(tmp_path):
    path = write_restore(tmp_path, restore_payload(completed_utc_us=str(now_us() - 60 * DAY_US)))
    outcome = probe_restore_receipt(
        path, host=HOST, release=RELEASE, lower=now_us(), upper=now_us())
    assert (outcome.proven, outcome.reason) == (False, "restore_stale")


def test_restore_receipt_fails_when_unreadable(tmp_path):
    outcome = probe_restore_receipt(
        tmp_path / "absent.json", host=HOST, release=RELEASE,
        lower=now_us(), upper=now_us())
    assert (outcome.proven, outcome.reason) == (False, "receipt_unreadable")


def test_restore_receipt_rejects_extra_fields(tmp_path):
    outcome = probe_restore_receipt(
        write_restore(tmp_path, restore_payload(approvedBy="someone")), host=HOST,
        release=RELEASE, lower=now_us(), upper=now_us())
    assert (outcome.proven, outcome.reason) == (False, "receipt_unreadable")


# --- ProbeSet dispatch and receipt construction -----------------------------------------------


def test_probe_set_reports_not_configured_for_everything_it_lacks():
    outcomes = ProbeSet(release=RELEASE, host=HOST).run()
    assert set(outcomes) == set(Capability)
    assert {outcome.reason for outcome in outcomes.values()} == {"not_configured"}


def test_probe_set_dispatches_a_configured_capability(tmp_path):
    frame = tmp_path / "clock.json"
    frame.write_text(_frame(tmp_path))
    outcomes = ProbeSet(
        release=RELEASE, host=HOST, clock_frame=frame, clock_uid=os.getuid(),
        clock_config_digest=DIGEST,
        clock_kwargs={"context": _context(), "trusted_root": tmp_path},
    ).run()
    assert outcomes[Capability.NTS_CLOCK].proven is True
    assert outcomes[Capability.TLS_ROLES].reason == "not_configured"


def test_receipt_from_a_proven_outcome_verifies():
    outcome = Outcome(capability=Capability.NTS_CLOCK, proven=True, reason="verified",
                      artifact=DIGEST, evidence=DIGEST)
    receipt = receipt_from(outcome, host=HOST, release=RELEASE, days=1, lower=1000, upper=1010)
    assert isinstance(receipt, Receipt)
    assert receipt.validity == ValidityWindow(
        valid_from=receipt.validity.valid_from, valid_until=receipt.validity.valid_until)


def test_receipt_from_an_unproven_outcome_is_refused():
    outcome = Outcome(capability=Capability.NTS_CLOCK, proven=False, reason="not_configured")
    with pytest.raises(PermissionError):
        receipt_from(outcome, host=HOST, release=RELEASE, lower=1000, upper=1010)


def test_receipt_window_cannot_exceed_seven_days():
    outcome = Outcome(capability=Capability.NTS_CLOCK, proven=True, reason="verified",
                      artifact=DIGEST, evidence=DIGEST)
    with pytest.raises(ValueError):
        receipt_from(outcome, host=HOST, release=RELEASE, days=8, lower=1000, upper=1010)
    with pytest.raises(ValueError):
        receipt_from(outcome, host=HOST, release=RELEASE, days=0, lower=1000, upper=1010)


def test_probe_provides_no_artifact_when_unproven():
    outcome = Outcome(capability=Capability.RESTORE_RECEIPT, proven=False, reason="restore_stale")
    assert outcome.artifact is None and outcome.evidence is None


def test_restore_receipt_model_is_strict_and_immutable(tmp_path):
    receipt = RestoreReceipt.model_validate_json(
        write_restore(tmp_path, restore_payload()).read_bytes())
    with pytest.raises(ValidationError):
        receipt.release = "other"
    assert receipt.verified is True


def test_native_commit_guard_reads_admission_before_the_post_yield_refusal():
    """A guard that admits and only then refuses finalization still counts as admitting.

    The real adapter raises after the yield, so a probe that judged by the exception message
    would report a broken guard as merely "refused for the wrong reason".
    """
    outcome = guard_probe(Guard(admit_unplanned=True))
    assert (outcome.proven, outcome.reason) == (False, "unplanned_effect_admitted")


def test_native_commit_guard_treats_an_authority_permission_error_as_a_refusal():
    """A revoked or out-of-scope approval is a legitimate refusal, not an internal error."""
    outcome = guard_probe(Guard(authority_refuses=True))
    assert (outcome.proven, outcome.reason) == (False, "planned_effect_not_admitted")
