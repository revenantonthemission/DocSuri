"""Disposable native Keychain smoke; no host signer or acceptance receipt is provisioned."""

import base64
import os
import secrets
import subprocess
import sys
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from docsuri_platform_integrity.adapters.keychain import KeychainReader, KeyUnavailable
from docsuri_platform_integrity.adapters.keychain_provisioning import (
    KeychainOperationError,
    NativeKeychain,
)


@pytest.mark.skipif(sys.platform != "darwin", reason="native Security.framework required")
def test_native_create_locked_refusal_unlock_and_cross_process_read(tmp_path):
    directory = tmp_path / "purpose"
    directory.mkdir(mode=0o700)
    path = directory / "disposable.keychain-db"
    manager = NativeKeychain()
    key = Ed25519PrivateKey.generate()
    password = secrets.token_urlsafe(32)
    service, account = "org.docsuri.test.receipt", "disposable"
    try:
        manager.create(path, password, service, account, key.private_bytes_raw(),
                       Path(sys.executable))
        reader = KeychainReader(path)
        signer = Ed25519PrivateKey.from_private_bytes(reader.get(service, account))
        key.public_key().verify(signer.sign(b"native-keychain-proof"), b"native-keychain-proof")
        with pytest.raises(FileExistsError):
            manager.create(path, password, service, account, key.private_bytes_raw(),
                           Path(sys.executable))
        manager.lock(path)
        with pytest.raises(KeyUnavailable):
            reader.get(service, account)
        with pytest.raises(KeychainOperationError):
            manager.unlock(path, "wrong-password-for-test")
        manager.unlock(path, password)
        program = (
            "import base64,sys; from pathlib import Path; "
            "from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey; "
            "from docsuri_platform_integrity.adapters.keychain import KeychainReader; "
            "key=Ed25519PrivateKey.from_private_bytes(KeychainReader(Path(sys.argv[1]))"
            ".get(sys.argv[2],sys.argv[3])); "
            "print(base64.b64encode(key.public_key().public_bytes_raw()).decode())"
        )
        result = subprocess.run([sys.executable, "-I", "-B", "-c", program,
                                 str(path), service, account], capture_output=True, text=True,
                                timeout=15,
                                env={"PATH": "/usr/bin:/bin", "HOME": os.environ["HOME"]},
                                check=True)
        public = base64.b64encode(key.public_key().public_bytes_raw()).decode()
        assert result.stdout.strip() == public
    finally:
        if path.exists():
            manager.delete_disposable(path)


@pytest.mark.skipif(sys.platform != "darwin", reason="native Security.framework required")
def test_reader_reports_the_security_status_instead_of_a_bare_reason(tmp_path, monkeypatch):
    """`KeyUnavailable("...locked")` cannot be acted on.

    Locked (-25308), absent (-128) and ACL-refused (-60) were indistinguishable, so a wrong fix
    looked identical to a right one. The status is the discriminator, so the reader must carry it.
    """
    import ctypes

    path = tmp_path / "purpose.keychain-db"
    path.write_bytes(b"")
    path.chmod(0o600)

    class FakeFunction:
        def __init__(self, result):
            self.result = result
            self.argtypes = None
            self.restype = None

        def __call__(self, *args):
            return self.result

    class FakeSecurity:
        SecKeychainSetUserInteractionAllowed = FakeFunction(0)
        SecKeychainOpen = FakeFunction(0)
        SecKeychainItemFreeContent = FakeFunction(0)
        # errSecItemNotFound
        SecKeychainFindGenericPassword = FakeFunction(-128)
        CFRelease = FakeFunction(0)

    monkeypatch.setattr(ctypes, "CDLL", lambda name, *a, **k: FakeSecurity())
    with pytest.raises(KeyUnavailable, match=r"security status -128 \(0xffffff80\)"):
        KeychainReader(path).get("service", "account")
