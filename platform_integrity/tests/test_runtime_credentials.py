import json
import os
import stat

import pytest
from test_tls_server import certificate

from docsuri_platform_integrity.adapters.credentials import KeychainTLS, TLSReference
from docsuri_platform_integrity.adapters.keychain import KeyUnavailable


@pytest.fixture
def bundle(tmp_path):
    ca_key, ca_cert, ca, _ = certificate(tmp_path, "ca")
    _, _, cert, key = certificate(tmp_path, "server", ca_key=ca_key, ca_cert=ca_cert)
    return {"certificate": cert.read_text(), "privateKey": key.read_text(), "ca": ca.read_text()}


def provider(tmp_path, bundle, **kwargs):
    class Reader:
        def get(self, service, account):
            assert (service, account) == ("docsuri.test.tls", "reader")
            return json.dumps(bundle).encode()

    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    reference = TLSReference(keychain=tmp_path / "fixture.keychain-db",
                             service="docsuri.test.tls", account="reader")
    return KeychainTLS(reference, runtime, reader_factory=lambda _: Reader(),
                       encryption_check=kwargs.get("encryption_check", lambda: True))


def test_materials_are_private_and_removed_after_context(tmp_path, bundle):
    secret = provider(tmp_path, bundle)
    with secret.materialize() as material:
        paths = material.certificate, material.private_key, material.ca
        for path in paths:
            assert stat.S_IMODE(path.stat().st_mode) == 0o600
            assert path.stat().st_uid == os.getuid()
        assert stat.S_IMODE(material.private_key.parent.stat().st_mode) == 0o700
        assert material.private_key.read_text() == bundle["privateKey"]
    assert all(not path.exists() for path in paths)
    assert not list((tmp_path / "runtime").iterdir())


def test_mismatched_key_fails_before_materialization(tmp_path, bundle):
    _, _, _, other_key = certificate(tmp_path, "other")
    secret = provider(tmp_path, bundle | {"privateKey": other_key.read_text()})
    with pytest.raises(KeyUnavailable):
        with secret.materialize():
            pytest.fail("mismatched credential accepted")
    assert not list((tmp_path / "runtime").iterdir())


@pytest.mark.parametrize("encrypted", [False, None, 1])
def test_unverified_host_encryption_blocks_secret_use(tmp_path, bundle, encrypted):
    secret = provider(tmp_path, bundle, encryption_check=lambda: encrypted)
    with pytest.raises(KeyUnavailable):
        with secret.materialize():
            pytest.fail("unverified encryption accepted")


def test_downstream_failure_does_not_leave_plaintext_files(tmp_path, bundle):
    secret = provider(tmp_path, bundle)
    with pytest.raises(RuntimeError):
        with secret.materialize():
            raise RuntimeError("handshake failed")
    assert not list((tmp_path / "runtime").iterdir())


def test_locked_keychain_has_no_cached_plaintext_fallback(tmp_path, bundle):
    secret = provider(tmp_path, bundle)
    with secret.materialize():
        pass

    class Locked:
        def get(self, *args):
            raise KeyUnavailable("locked")

    secret.reader_factory = lambda _: Locked()
    with pytest.raises(KeyUnavailable):
        with secret.materialize():
            pytest.fail("locked keychain accepted")
    assert not list((tmp_path / "runtime").iterdir())
